"""Offline protocol regression tests based on the saved vendor import.js layout."""
import struct
import unittest

from live_playback import IOT_MAGIC
from live_stream import (
    LIVE_REQUEST, LIVE_START, LIVE_STOP, live_frames_from_packets, live_request,
)


def packet(payload):
    return struct.pack("<8I", IOT_MAGIC, 19, 1 << 24, 0, 25, 0, 0, len(payload)) + payload


def fixture(data=b"\x00\x00\x00\x01\x40\x01ABCDEF"):
    # NARF(40) + MARF(24) + live-head(8) + video-param(24) + extra(8)
    header = b"NARF" + bytes(36)
    header += struct.pack("<IIIIQ", 0x4652414D, 1, 0, len(data), 1750000000123)
    header += struct.pack("<II", 1, 0)
    header += b"H265\0\0\0\0"
    header += struct.pack("<4I", 15, 800, 448, 0)
    header += bytes(8)
    assert len(header) == 104
    return header + data


class LiveProtocolTests(unittest.TestCase):
    def test_open_request(self):
        data = live_request(0, 1, LIVE_START)
        self.assertEqual(len(data), 36)
        self.assertEqual(struct.unpack_from("<I", data, 12)[0], LIVE_REQUEST)
        self.assertEqual(struct.unpack_from("<3I", data, 24), (0, 1, 2))

    def test_stop_request(self):
        data = live_request(0, 1, LIVE_STOP)
        self.assertEqual(struct.unpack_from("<3I", data, 24), (0, 1, 1))

    def test_fragmented_keyframe(self):
        data = fixture()
        output = list(live_frames_from_packets([packet(data[:108]),
                                                packet(data[108:])]))
        self.assertEqual(len(output), 1)
        frame = output[0]
        self.assertEqual(frame.channel, 0)
        self.assertEqual(frame.codec, "H265")
        self.assertEqual(frame.frame_type, 1)
        self.assertEqual((frame.fps, frame.width, frame.height), (15, 800, 448))
        self.assertEqual(frame.timestamp_ms, 1750000000123)
        self.assertEqual(frame.data, data[104:])

    def test_arq_advertisement(self):
        data = packet(fixture())
        ad = b"\xce\xfa\xef\xfe" + struct.pack("<I", len(data))
        self.assertEqual(len(list(live_frames_from_packets([ad, data]))), 1)

    def test_invalid_quality(self):
        with self.assertRaises(ValueError):
            live_request(0, 3, LIVE_START)

    def test_reject_oversized_frame(self):
        data = bytearray(fixture())
        struct.pack_into("<I", data, 52, 20 * 1024 * 1024)
        with self.assertRaisesRegex(ValueError, "size"):
            list(live_frames_from_packets([packet(data)]))

    def test_discard_incomplete_tail(self):
        data = fixture()
        self.assertEqual(list(live_frames_from_packets([packet(data[:108])])), [])


if __name__ == "__main__":
    unittest.main()
