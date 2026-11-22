"""Offline tests for per-camera live preview frame-rate selection."""
import shutil
import subprocess
import tempfile
from pathlib import Path
import unittest

from gateway import live_preview_query
from live_preview import effective_live_input_fps, preview_command


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

    def test_verified_sd_profile_uses_measured_10_fps_input_timebase(self):
        for stream, expected in ((1, 10), (0, 15)):
            with self.subTest(stream=stream):
                self.assertEqual(
                    effective_live_input_fps(15, stream, 800, 448), expected
                )
        command = preview_command(
            "H265", effective_live_input_fps(15, 1, 800, 448), 10,
            retime_input=True
        )
        self.assertEqual(command[command.index("-framerate") + 1], "10")
        self.assertEqual(command[command.index("-vf") + 1],
                         "setpts=N/(10*TB),fps=10")

    def test_unknown_live_profiles_retain_advertised_timebase(self):
        examples = ((10, 1, 800, 448), (15, 1, 1280, 720),
                    (20, 1, 800, 448), (15, 0, 800, 448))
        for advertised, stream, width, height in examples:
            with self.subTest(profile=(advertised, stream, width, height)):
                self.assertEqual(
                    effective_live_input_fps(advertised, stream, width, height),
                    advertised
                )

    def test_real_hevc_filter_retimestamps_decoded_frames(self):
        """Exercise FFmpeg itself: demuxer -framerate alone is insufficient."""
        if not shutil.which("ffmpeg"):
            self.skipTest("FFmpeg not installed")
        with tempfile.TemporaryDirectory() as directory:
            raw_file = Path(directory) / "frames.h265"
            generated = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "testsrc2=size=64x64:rate=15",
                "-frames:v", "30", "-c:v", "libx265",
                "-preset", "ultrafast",
                "-x265-params", "log-level=error:pools=1:frame-threads=1",
                "-f", "hevc", "-y", str(raw_file),
            ], capture_output=True, timeout=25, check=False)
            if generated.returncode:
                self.skipTest("FFmpeg libx265 encoder unavailable")
            source = raw_file.read_bytes()
            for fps, expected in ((5, 15), (10, 30), (15, 45)):
                with self.subTest(fps=fps):
                    result = subprocess.run(
                        preview_command("H265", 10, fps, retime_input=True),
                        input=source, capture_output=True, timeout=25,
                        check=True,
                    )
                    # JPEG SOI marker occurs once per image; JPEG entropy
                    # data escapes literal 0xff bytes.
                    self.assertEqual(result.stdout.count(b"\\xff\\xd8"), expected)

    def test_invalid_ffmpeg_rate_rejected(self):
        for fps in (0, 1, 7, 16, 100):
            with self.subTest(fps=fps), self.assertRaises(ValueError):
                preview_command("H265", 15, fps)


if __name__ == "__main__":
    unittest.main()
