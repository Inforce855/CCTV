"""Offline tests for per-camera live preview frame-rate selection."""
import unittest

from gateway import live_preview_query
from live_preview import preview_command


class LivePreviewRateTests(unittest.TestCase):
    def test_fps_defaults_to_5_for_existing_urls(self):
        self.assertEqual(live_preview_query("channel=1&stream=1"), (1, 5))

    def test_each_channel_accepts_all_preview_rates(self):
        for channel in range(1, 5):
            for fps in (5, 10, 15):
                with self.subTest(channel=channel, fps=fps):
                    self.assertEqual(
                        live_preview_query(
                            f"channel={channel}&stream=1&fps={fps}"
                        ), (channel, fps)
                    )

    def test_invalid_queries_rejected(self):
        invalid_queries = (
            "channel=0&stream=1&fps=10",
            "channel=5&stream=1&fps=5",
            "channel=1&stream=0&fps=10",
            "channel=1&stream=1&fps=12",
            "channel=1&stream=1&fps=-5",
            "channel=1&stream=1&fps=abc",
            "channel=1&stream=1&fps=10&fps=15",
            "channel=1&stream=1&fps=10&other=1",
            "channel=1&fps=10",
        )
        for query in invalid_queries:
            with self.subTest(query=query), self.assertRaises(ValueError):
                live_preview_query(query)

    def test_ffmpeg_filter_selects_requested_rate(self):
        for codec in ("H264", "H265"):
            for fps in (5, 10, 15):
                with self.subTest(codec=codec, fps=fps):
                    command = preview_command(codec, 15, fps)
                    self.assertEqual(command[command.index("-vf") + 1],
                                     f"fps={fps}")
                    self.assertEqual(command[command.index("-framerate") + 1],
                                     "15")
                    self.assertEqual(command[command.index("-f") + 1],
                                     "hevc" if codec == "H265" else "h264")

    def test_invalid_ffmpeg_rate_rejected(self):
        for fps in (0, 1, 7, 16, 100):
            with self.subTest(fps=fps), self.assertRaises(ValueError):
                preview_command("H265", 15, fps)


if __name__ == "__main__":
    unittest.main()
