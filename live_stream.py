"""Bounded, authenticated KP2P live-video receiver for the Hiseeu NVR.

Wire fields are taken from the original vendor client (import.js), not from
the recording replay API. This module does not modify the working replay path.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import secrets
import struct
import time

from websockets.sync.client import connect
from websockets.exceptions import WebSocketException

from live_playback import (
    ARQ_ACCEPT, ARQ_LENGTH, ARQ_OPEN, APP_MAGIC, IOT_MAGIC,
    application, auth_payload, expect_reply, recording_frames, send, transport,
)

MAX_FRAME_BYTES = 16 * 1024 * 1024
MAX_MESSAGE_BYTES = 2 * 1024 * 1024
LIVE_START = 2
LIVE_STOP = 1
LIVE_REQUEST = 30
LIVE_RESPONSE = 31


@dataclass(frozen=True)
class LiveFrame:
    channel: int
    timestamp_ms: int
    frame_type: int
    codec: str
    fps: int
    width: int
    height: int
    data: bytes


def live_request(channel, stream, instruction):
    """Vendor import.js: live_req(channel, streamid, live_cmd)."""
    if not 0 <= channel <= 7 or stream not in (0, 1):
        raise ValueError("Invalid live-stream channel or quality")
    if instruction not in (LIVE_START, LIVE_STOP):
        raise ValueError("Invalid live-stream instruction")
    return application(LIVE_REQUEST, 2 if instruction == LIVE_START else 3,
                       struct.pack("<3I", channel, stream, instruction))


def live_frames_from_packets(packets):
    """Reassemble NARF/MARF live frames, including fragmented HEVC keyframes.

    The outer transport header and 8-byte ARQ length messages are the same
    as recording replay. The live metadata layout differs from replay:
    MARF(24) + live-head(8) + video-param(24) + reserved(8).
    """
    pending = bytearray()
    remaining = 0
    metadata = None
    advertised = None

    for message in packets:
        if len(message) == 8 and message.startswith(ARQ_LENGTH):
            if advertised is not None:
                raise ValueError("Missing advertised transport message")
            advertised, = struct.unpack_from("<I", message, 4)
            if not 0 < advertised <= MAX_MESSAGE_BYTES:
                raise ValueError("Invalid transport message length")
            continue
        if not message.startswith(struct.pack("<I", IOT_MAGIC)):
            continue
        if len(message) < 32 or len(message) > MAX_MESSAGE_BYTES:
            raise ValueError("Invalid live transport header")
        if advertised is not None and advertised != len(message):
            raise ValueError("Live transport length mismatch")
        advertised = None
        command, = struct.unpack_from("<I", message, 4)
        if command != 19:
            continue
        payload = message[32:]
        prefix = 40 if payload.startswith(b"NARF") else 0
        if payload[prefix:prefix + 4] == b"MARF":
            if remaining:
                raise ValueError("New live frame before previous frame completed")
            if len(payload) < prefix + 64:
                raise ValueError("Incomplete live frame header")
            frame_type_marker, size = struct.unpack_from("<II", payload, prefix + 8)
            timestamp_ms, = struct.unpack_from("<Q", payload, prefix + 16)
            frame_type, channel = struct.unpack_from("<II", payload, prefix + 24)
            codec = payload[prefix + 32:prefix + 40].split(b"\0", 1)[0].decode("ascii")
            fps, width, height = struct.unpack_from("<III", payload, prefix + 40)
            if frame_type_marker != 0 or not 0 < size <= MAX_FRAME_BYTES:
                raise ValueError("Invalid live frame type or size")
            if channel > 7 or frame_type not in (0, 1, 2, 15):
                raise ValueError("Invalid live frame metadata")
            if frame_type in (1, 2) and (not 0 < fps <= 120 or not 0 < width <= 8192
                                         or not 0 < height <= 8192):
                raise ValueError("Invalid live video dimensions")
            metadata = (channel, timestamp_ms, frame_type, codec, fps, width, height)
            payload = payload[prefix + 64:]
            remaining = size
        elif not remaining:
            continue
        if len(payload) > remaining:
            raise ValueError("Live packet exceeds declared frame size")
        pending.extend(payload)
        remaining -= len(payload)
        if remaining == 0:
            channel, timestamp_ms, frame_type, codec, fps, width, height = metadata
            if frame_type in (1, 2) and codec in ("H264", "H265"):
                yield LiveFrame(channel, timestamp_ms, frame_type, codec,
                                fps, width, height, bytes(pending))
            pending.clear()
            metadata = None
    # An interrupted connection may end mid-frame. Never yield that frame.


@contextmanager
def receive_live(url, username, password, channel=0, stream=1):
    """Open an NVR live stream. Always request CLOSE, even on early exit."""
    request = live_request(channel, stream, LIVE_START)
    stop = live_request(channel, stream, LIVE_STOP)
    session = secrets.randbelow(10_000) + 1
    with connect(url, open_timeout=8, close_timeout=2, ping_interval=None,
                 compression=None, max_size=MAX_MESSAGE_BYTES, proxy=None) as socket:
        socket.send(ARQ_OPEN + struct.pack("<I", session))
        if socket.recv(timeout=8) != ARQ_ACCEPT:
            raise ValueError("Unexpected NVR handshake reply")
        send(socket, transport(20, session, struct.pack("<II", session, 0)))
        expect_reply(socket, session, "LAN session open", (21,))
        send(socket, transport(19, session, application(10, 1, auth_payload(username, password))))
        expect_reply(socket, session, "NVR login", (19, 43), 11)
        send(socket, transport(19, session, request))
        expect_reply(socket, session, "Live stream open", (19, 43), LIVE_RESPONSE)
        try:
            # Bounded to an hour; browsers can open a new session after expiry.
            packets = recording_frames(socket, session, time.monotonic() + 3600)
            yield (frame for frame in live_frames_from_packets(packets)
                   if frame.channel == channel)
        finally:
            try:
                send(socket, transport(19, session, stop))
            except (OSError, WebSocketException):
                pass
