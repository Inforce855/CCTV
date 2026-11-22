"""Recover timestamped KP2P playback frames from a length-prefixed capture."""
import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import struct

MAX_MESSAGE = 2 * 1024 * 1024
MAX_FRAME = 16 * 1024 * 1024
TRANSPORT_HEADER = 32
REPLAY_HEADER = 104


@dataclass(frozen=True)
class Frame:
    channel: int
    timestamp_ms: int
    frame_type: int
    codec: str
    data: bytes


def messages(source):
    while prefix := source.read(4):
        if len(prefix) != 4:
            raise ValueError("Incomplete capture length")
        size, = struct.unpack("<I", prefix)
        if not 0 < size <= MAX_MESSAGE:
            raise ValueError("Invalid capture message length")
        message = source.read(size)
        if len(message) != size:
            raise ValueError("Incomplete capture message")
        yield message


def frames(stream, *, allow_incomplete_tail=False):
    """Yield complete frames from the observed ordered playback message format."""
    header = None
    pending = bytearray()
    remaining = 0
    advertised_size = None
    for message in stream:
        if len(message) == 8 and message.startswith(b"\xce\xfa\xef\xfe"):
            if advertised_size is not None:
                raise ValueError("Missing transport message")
            advertised_size, = struct.unpack_from("<I", message, 4)
            continue
        if not message.startswith(b"\xab\xbc\xcd\xde"):
            continue
        if len(message) < TRANSPORT_HEADER:
            raise ValueError("Incomplete transport header")
        if advertised_size is not None and advertised_size != len(message):
            raise ValueError("Transport message size mismatch")
        advertised_size = None
        command, = struct.unpack_from("<I", message, 4)
        if command != 19:
            continue
        payload = message[TRANSPORT_HEADER:]
        if payload.startswith(b"NARF") and payload[40:44] == b"MARF":
            if remaining:
                raise ValueError("New frame arrived before the previous frame was complete")
            if len(payload) < REPLAY_HEADER:
                raise ValueError("Incomplete replay header")
            size, timestamp = struct.unpack_from("<IQ", payload, 52)
            frame_type, channel = struct.unpack_from("<II", payload, 64)
            codec = payload[80:88].split(b"\0", 1)[0].decode("ascii")
            if not 0 < size <= MAX_FRAME:
                raise ValueError("Invalid replay frame size")
            header = (channel, timestamp, frame_type, codec)
            payload = payload[REPLAY_HEADER:]
            remaining = size
        elif not remaining:
            continue
        if len(payload) > remaining:
            raise ValueError("Payload exceeds declared frame size")
        pending.extend(payload)
        remaining -= len(payload)
        if remaining == 0:
            yield Frame(*header, bytes(pending))
            pending.clear()
    if not allow_incomplete_tail and (remaining or advertised_size is not None):
        raise ValueError("Capture ended before the next frame could be read")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("output", type=Path, help="New raw HEVC file")
    parser.add_argument("--channel", type=int, default=1, help="One-based camera number")
    args = parser.parse_args()
    if args.channel < 1:
        parser.error("Camera number must be positive")
    count = 0
    try:
        with args.capture.open("rb") as source, args.output.open("xb") as output:
            try:
                for frame in frames(messages(source), allow_incomplete_tail=True):
                    if frame.channel != args.channel - 1 or frame.codec != "H265":
                        continue
                    offset = output.tell()
                    output.write(frame.data)
                    print(json.dumps({
                        "timestamp_ms": frame.timestamp_ms,
                        "frame_type": frame.frame_type,
                        "offset": offset,
                        "size": len(frame.data),
                    }))
                    count += 1
                if not count:
                    raise ValueError("No complete HEVC frames for that camera")
            except BaseException:
                args.output.unlink()
                raise
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Playback capture error: {exc}\n")


if __name__ == "__main__":
    main()
