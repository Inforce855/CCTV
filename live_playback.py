"""Retrieve one short recording window from a Hiseeu NVR over the LAN."""
import argparse
from datetime import datetime
import getpass
import json
from pathlib import Path
import secrets
import struct
import time

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from websockets.sync.client import connect
from websockets.exceptions import WebSocketException

from playback import frames

ARQ_LENGTH = b"\xce\xfa\xef\xfe"
ARQ_OPEN = bytes.fromhex("d9ffcc028c38eed2d199ac6026947fae")
ARQ_ACCEPT = bytes.fromhex("96d5390d12fcbe8f4790d932ccd849f3")
IOT_MAGIC = 0xDECDBCAB
APP_MAGIC = 0x4B503250
MAX_OUTPUT = 64 * 1024 * 1024


def transport(command, session, payload):
    return struct.pack("<8I", IOT_MAGIC, command, 1 << 24, 0, session, 0, 0, len(payload)) + payload


def application(command, ticket, payload):
    return struct.pack("<6I", APP_MAGIC, 1, ticket, command, 0, len(payload)) + payload


def send(socket, packet):
    socket.send(ARQ_LENGTH + struct.pack("<I", len(packet)))
    socket.send(packet)


def auth_payload(username, password):
    # The stock client sends two AES blocks per credential field.
    values = [value.encode("utf-8") for value in (username, password)]
    if any(len(value) >= 32 for value in values):
        raise ValueError("NVR credentials must be shorter than 32 bytes")
    encryptor = Cipher(algorithms.AES(b"~!JUAN*&Vision-="), modes.ECB()).encryptor()
    return encryptor.update(b"".join(value.ljust(32, b"\0") for value in values)) + encryptor.finalize()


def replay_payload(command, channel=0, start=0, stop=0, kinds=0):
    payload = bytearray(52)
    struct.pack_into("<I", payload, 0, command)
    if command == 3:
        payload[8] = 1 << channel
    struct.pack_into("<I", payload, 24, kinds)
    struct.pack_into("<II", payload, 32, start, stop)
    return payload


def recording_frames(socket, session, deadline):
    next_ping = time.monotonic() + 8
    while time.monotonic() < deadline:
        now = time.monotonic()
        if now >= next_ping:
            send(socket, transport(17, session, str(session).encode().ljust(96, b"\0")))
            next_ping = now + 8
        try:
            packet = socket.recv(timeout=max(0, min(deadline, next_ping) - now))
        except TimeoutError:
            continue
        if not isinstance(packet, bytes):
            raise ValueError("Unexpected text message from the NVR")
        if len(packet) >= 56:
            magic, _, _, command, result, _ = struct.unpack_from("<4IiI", packet, 32)
            if magic == APP_MAGIC and command == 41 and result:
                raise ValueError(f"NVR rejected replay ({result})")
        yield packet


def expect_reply(socket, session, stage, transport_commands, app_command=None):
    deadline = time.monotonic() + 8
    seen = set()
    for packet in recording_frames(socket, session, deadline):
        if len(packet) < 32:
            continue
        magic, command, _, _, _, _, result, _ = struct.unpack_from("<6IiI", packet)
        if magic != IOT_MAGIC:
            continue
        seen.add(str(command))
        if command not in transport_commands:
            continue
        if result:
            raise ValueError(f"NVR rejected transport request ({result})")
        if app_command is not None:
            if len(packet) < 56:
                continue
            magic, _, _, command, result, _ = struct.unpack_from("<4IiI", packet, 32)
            if magic == APP_MAGIC:
                seen.add(f"app:{command}")
            if magic != APP_MAGIC or command != app_command:
                continue
            if result:
                raise ValueError(f"NVR rejected authentication ({result})")
        return
    raise TimeoutError(f"{stage}: no expected reply (received {', '.join(sorted(seen)) or 'no protocol commands'})")


def receive_clip(url, username, password, channel, start, end, kinds, output):
    session = secrets.randbelow(10_000) + 1
    with connect(url, open_timeout=8, close_timeout=2, ping_interval=None,
                 compression=None, max_size=2 * 1024 * 1024, proxy=None) as socket:
        socket.send(ARQ_OPEN + struct.pack("<I", session))
        if socket.recv(timeout=8) != ARQ_ACCEPT:
            raise ValueError("Unexpected NVR handshake reply")
        send(socket, transport(20, session, struct.pack("<II", session, 0)))
        expect_reply(socket, session, "LAN session open", (21,))
        send(socket, transport(19, session, application(10, 1, auth_payload(username, password))))
        expect_reply(socket, session, "NVR login", (19, 43), 11)
        replay = application(40, 2, replay_payload(3, channel, start, end, kinds))
        send(socket, transport(19, session, replay))
        count = 0
        first = last = first_in_range = None
        before_start = in_range = keyframes = 0
        stop_reason = "deadline"
        capture_started = time.monotonic()
        try:
            deadline = capture_started + (end - start) + 45
            for frame in frames(recording_frames(socket, session, deadline), allow_incomplete_tail=True):
                if frame.channel != channel or frame.codec != "H265":
                    continue
                if frame.timestamp_ms >= end * 1000:
                    stop_reason = "end_timestamp"
                    break
                if not count and frame.frame_type != 1:
                    continue
                if output.tell() + len(frame.data) > MAX_OUTPUT:
                    raise ValueError("Playback exceeded the clip size limit")
                first = frame.timestamp_ms if first is None else first
                last = frame.timestamp_ms
                output.write(frame.data)
                count += 1
                keyframes += frame.frame_type == 1
                if frame.timestamp_ms < start * 1000:
                    before_start += 1
                else:
                    if first_in_range is None:
                        first_in_range = frame.timestamp_ms
                    in_range += 1
        finally:
            try:
                send(socket, transport(19, session, application(40, 3, replay_payload(2))))
            except (OSError, WebSocketException):
                pass
    if count < 2:
        raise ValueError("The NVR did not return a playable HEVC sequence for that window")
    return {
        "frames": count, "keyframes": keyframes,
        "first_timestamp_ms": first, "last_timestamp_ms": last,
        "frames_before_start": before_start, "frames_in_range": in_range,
        "first_in_range_ms": first_in_range, "stop_reason": stop_reason,
    }


def parse_time(value):
    timestamp = datetime.fromisoformat(value)
    if timestamp.utcoffset() is None:
        raise ValueError("Include the time zone offset, e.g. +00:00")
    return int(timestamp.timestamp())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", help="NVR IP address or LAN hostname")
    parser.add_argument("start", help="ISO start date and time including UTC offset")
    parser.add_argument("output", type=Path, help="New raw HEVC output file")
    parser.add_argument("--channel", type=int, default=1, choices=range(1, 9))
    parser.add_argument("--seconds", type=int, default=10, choices=range(1, 31), metavar="1–30")
    parser.add_argument("--type", type=int, choices=(1, 2, 4, 8), default=1)
    parser.add_argument("--username", default="admin")
    args = parser.parse_args()
    try:
        if not args.host or any(c in args.host for c in "/?#@:\\"):
            raise ValueError("Enter only the NVR hostname or IPv4 address")
        start = parse_time(args.start)
        if not 0 <= start <= 0xFFFFFFFF - args.seconds:
            raise ValueError("Start time is outside the NVR timestamp range")
        password = getpass.getpass("NVR password: ")
        with args.output.open("xb") as output:
            try:
                report = receive_clip(f"ws://{args.host}:10000/", args.username, password,
                                      args.channel - 1, start, start + args.seconds, args.type, output)
            except BaseException:
                args.output.unlink()
                raise
        print(json.dumps(report))
    except (OSError, ValueError, WebSocketException) as exc:
        parser.exit(1, f"Live playback error: {exc}\n")


if __name__ == "__main__":
    main()
