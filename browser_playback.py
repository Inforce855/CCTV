"""Progressive, single-camera browser playback preview."""
import contextlib
from itertools import chain
import struct
import subprocess
from threading import Thread

from websockets.exceptions import WebSocketException

from live_playback import replay_frames


@contextlib.contextmanager
def browser_stream(url, username, password, channel, start, end, kinds):
    with replay_frames(url, username, password, channel, start, end, kinds) as (frames, _):
        video = (f for f in frames if f.channel == channel and f.codec == "H265")
        first = next((f for f in video if f.frame_type == 1), None)
        if first is None or first.timestamp_ms >= end * 1000:
            raise ValueError("No decodable video for this recording")
        # The first browser preview uses the verified camera cadence.
        with subprocess.Popen([
            "ffmpeg", "-nostdin", "-v", "error", "-f", "hevc",
            "-framerate", "15", "-probesize", "32768", "-analyzeduration", "1",
            "-i", "pipe:0", "-an", "-c:v", "libx264", "-preset", "ultrafast",
            "-tune", "zerolatency", "-vf", "scale=1280:-2", "-pix_fmt", "yuv420p",
            "-profile:v", "baseline", "-level:v", "3.1", "-g", "15",
            "-movflags", "+empty_moov+default_base_moof",
            "-frag_duration", "250000", "-f", "mp4", "pipe:1",
        ], stdin=subprocess.PIPE, stdout=subprocess.PIPE) as process:
            errors = []

            def feed():
                try:
                    with process.stdin:
                        for frame in chain((first,), video):
                            if frame.timestamp_ms >= end * 1000:
                                break
                            process.stdin.write(frame.data)
                            process.stdin.flush()
                except (OSError, ValueError, WebSocketException) as error:
                    errors.append(error)

            thread = Thread(target=feed)
            thread.start()
            try:
                yield first.timestamp_ms, process.stdout, process, errors
            finally:
                if process.poll() is None:
                    process.terminate()
                thread.join()


def mp4_boxes(source):
    while header := source.read(8):
        if len(header) != 8:
            raise ValueError("Incomplete MP4 header")
        size, _ = struct.unpack(">I4s", header)
        if not 8 <= size <= 16 * 1024 * 1024:
            raise ValueError("Unexpected MP4 box size")
        body = source.read(size - 8)
        if len(body) != size - 8:
            raise ValueError("Incomplete MP4 box")
        yield header + body
