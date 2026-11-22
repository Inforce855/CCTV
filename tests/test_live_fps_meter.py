"""Offline rolling live-camera FPS counter tests (no NVR needed)."""
import threading
import unittest
from unittest.mock import patch

from gateway import LiveFpsMeter


class LiveFpsMeterTests(unittest.TestCase):
    def test_initially_inactive(self):
        meter = LiveFpsMeter()
        snapshot = meter.snapshot()
        self.assertFalse(snapshot["active"])
        self.assertIsNone(snapshot["source_fps"])
        self.assertIsNone(snapshot["jpeg_fps"])

    def test_counts_input_and_output_independently(self):
        meter = LiveFpsMeter()
        clock = [100.0]
        with patch("gateway.time.monotonic", side_effect=lambda: clock[0]):
            meter.begin(15)
            for i in range(30):
                clock[0] = 100.05 + (i * .05)
                meter.source_frame(1720000000000 + i * 50)
            for i in range(10):
                clock[0] = 100.1 + (i * .1)
                meter.jpeg_frame()
            clock[0] = 102.0
            data = meter.snapshot()
            self.assertEqual(data["target_fps"], 15)
            self.assertEqual(data["source_fps"], 15.0)
            self.assertEqual(data["jpeg_fps"], 5.0)
            self.assertEqual(data["source_frames"], 30)
            self.assertEqual(data["jpeg_frames"], 10)

    def test_window_removes_stale_events(self):
        meter = LiveFpsMeter()
        clock = [10.0]
        with patch("gateway.time.monotonic", side_effect=lambda: clock[0]):
            meter.begin(10)
            clock[0] = 11.0
            for i in range(10):
                meter.source_frame(i * 100)
            clock[0] = 17.0
            data = meter.snapshot()
            self.assertEqual(data["source_fps"], 0.0)
            self.assertEqual(data["source_frames"], 10)

    def test_repeat_timestamp_not_automatically_unique(self):
        meter = LiveFpsMeter()
        clock = [0.0]
        with patch("gateway.time.monotonic", side_effect=lambda: clock[0]):
            meter.begin(5)
            meter.source_frame(123456)
            meter.source_frame(123456)
            meter.source_frame(123500)
            clock[0] = 1.0
            data = meter.snapshot()
            self.assertEqual(data["source_frames"], 3)
            self.assertEqual(data["repeated_source_timestamps"], 1)

    def test_reset_on_restart(self):
        meter = LiveFpsMeter()
        clock = [100.0]
        with patch("gateway.time.monotonic", side_effect=lambda: clock[0]):
            meter.begin(5)
            meter.source_frame(100)
            meter.jpeg_frame()
            meter.finish()
            self.assertFalse(meter.snapshot()["active"])
            clock[0] = 110.0
            meter.begin(15)
            clock[0] = 111.0
            data = meter.snapshot()
            self.assertEqual(data["source_frames"], 0)
            self.assertEqual(data["jpeg_frames"], 0)
            self.assertEqual(data["target_fps"], 15)


if __name__ == "__main__":
    unittest.main()
