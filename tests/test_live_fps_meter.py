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

    def test_native_timestamps_show_100ms_for_10_fps(self):
        meter = LiveFpsMeter()
        clock = [200.0]
        with patch("gateway.time.monotonic", side_effect=lambda: clock[0]):
            meter.begin(15)
            for i in range(30):
                clock[0] = 200.0 + i * .1
                meter.source_frame(1720000000000 + i * 100)
            clock[0] = 203.0
            data = meter.snapshot()
            self.assertEqual(data["nvr_timestamp_gap_ms"], 100.0)
            self.assertEqual(data["nvr_timestamp_fps"], 10.0)
            self.assertEqual(data["source_fps"], 10.0)

    def test_native_timestamps_show_about_67ms_for_15_fps(self):
        meter = LiveFpsMeter()
        clock = [300.0]
        with patch("gateway.time.monotonic", side_effect=lambda: clock[0]):
            meter.begin(15)
            for i in range(30):
                clock[0] = 300.0 + i * .1
                meter.source_frame(1720000000000 + round(i * (1000 / 15)))
            clock[0] = 303.0
            data = meter.snapshot()
            self.assertEqual(data["source_fps"], 10.0)
            self.assertEqual(data["nvr_timestamp_gap_ms"], 67.0)
            self.assertAlmostEqual(data["nvr_timestamp_fps"], 15.0, delta=0.1)

    def test_backward_nvr_timestamp_suppresses_rate(self):
        meter = LiveFpsMeter()
        clock = [400.0]
        with patch("gateway.time.monotonic", side_effect=lambda: clock[0]):
            meter.begin(10)
            for i in range(12):
                clock[0] = 400.0 + i * .1
                meter.source_frame(2000 + i * 100 if i != 7 else 1000)
            clock[0] = 402.0
            data = meter.snapshot()
            self.assertIsNone(data["nvr_timestamp_gap_ms"])
            self.assertIsNone(data["nvr_timestamp_fps"])
            self.assertEqual(data["nvr_timestamp_backwards_window"], 1)

    def test_duplicate_nvr_timestamps_do_not_inflate_derived_rate(self):
        meter = LiveFpsMeter()
        clock = [500.0]
        with patch("gateway.time.monotonic", side_effect=lambda: clock[0]):
            meter.begin(15)
            for i in range(20):
                clock[0] = 500.0 + i * .1
                meter.source_frame(400000 + (i // 2) * 200)
            clock[0] = 502.0
            data = meter.snapshot()
            self.assertEqual(data["nvr_timestamp_gap_ms"], 200.0)
            self.assertEqual(data["nvr_timestamp_fps"], 5.0)
            self.assertEqual(data["nvr_timestamp_repeats_window"], 10)

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
