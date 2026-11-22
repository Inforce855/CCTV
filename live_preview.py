"""Convert one authenticated NVR SD live stream into browser-viewable MJPEG."""
from contextlib import contextmanager
from itertools import chain
import os
import subprocess
import time
from threading import Event, Thread
from websockets.exceptions import WebSocketException

from live_stream import receive_live

MAX_JPEG = 2 * 1024 * 1024


def jpeg_images(source):
    """Extract complete JPEGs from ffmpeg's MJPEG pipe, with a size cap."""
    buffer = bytearray()
    while block := os.read(source.fileno(), 65536):
        buffer.extend(block)
        start = buffer.find(b"\xff\xd8")
        if start < 0:
            if len(buffer) > 1:
                del buffer[:-1]
            continue
        if start:
            del buffer[:start]
        while True:
            end = buffer.find(b"\xff\xd9", 2)
            if end < 0:
                if len(buffer) > MAX_JPEG:
                    raise ValueError("JPEG preview exceeded size limit")
                break
            end += 2
            yield bytes(buffer[:end])
            del buffer[:end]
            start = buffer.find(b"\xff\xd8")
            if start > 0:
                del buffer[:start]
            elif start < 0:
                buffer.clear()
                break


def effective_live_input_fps(advertised_fps, stream, width, height):
    """Correct the verified Hiseeu SD input time base.

    On this NVR all four 800x448 SD feeds advertise 15 fps, but their
    frame headers advance by 100 ms (10 real video frames/s).
    Leave unknown profiles unchanged rather than assuming they run at 10.
    """
    if stream == 1 and advertised_fps == 15 and (width, height) == (800, 448):
        return 10
    return advertised_fps


def preview_command(codec, source_fps, output_fps, *, retime_input=False):
    """Build MJPEG conversion; retime only when native timestamps prove needed.

    Raw HEVC/H.264 may carry its own picture timing. FFmpeg's demuxer
    -framerate option does not necessarily replace decoded frame PTS;
    explicitly set decoded PTS for the verified Hiseeu 10 fps SD profile.
    """
    if codec not in ("H264", "H265") or not 1 <= source_fps <= 120:
        raise ValueError("Unsupported source codec or frame rate")
    if output_fps not in (5, 10, 15):
        raise ValueError("Preview fps must be 5, 10 or 15")
    format_name = "hevc" if codec == "H265" else "h264"
    video_filter = (f"setpts=N/({source_fps}*TB),fps={output_fps}"
                    if retime_input else f"fps={output_fps}")
    return [
        "ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error",
        "-f", format_name, "-framerate", str(source_fps),
        "-probesize", "32768", "-analyzeduration", "1", "-i", "pipe:0",
        "-an", "-vf", video_filter, "-c:v", "mjpeg", "-q:v", "6",
        "-f", "image2pipe", "pipe:1",
    ]


@contextmanager
def mjpeg_preview(url, username, password, channel=0, stream=1, fps=5,
                  on_source_frame=None):
    """Yield JPEGs while optionally observing encoded frames fed to FFmpeg."""
    if fps not in (5, 10, 15):
        raise ValueError("Unsupported browser preview frame rate")
    with receive_live(url, username, password, channel, stream) as frames:
        first = None
        first_deadline = time.monotonic() + 20
        for candidate in frames:
            if candidate.frame_type == 1:
                first = candidate
                break
            if time.monotonic() > first_deadline:
                raise TimeoutError("No live keyframe within 20 seconds")
        if first is None or first.codec not in ("H264", "H265"):
            raise ValueError("No supported video keyframe from NVR")
        source_fps = effective_live_input_fps(
            first.fps, stream, first.width, first.height
        )
        process = subprocess.Popen(
            preview_command(first.codec, source_fps, fps,
                            retime_input=(source_fps != first.fps)),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, bufsize=0
        )
        stop = Event()
        errors = []

        def feed():
            try:
                with process.stdin:
                    for frame in chain((first,), frames):
                        if stop.is_set() or process.poll() is not None:
                            break
                        if frame.codec != first.codec:
                            raise ValueError("Camera codec changed while streaming")
                        process.stdin.write(frame.data)
                        if on_source_frame is not None:
                            on_source_frame(frame.timestamp_ms)
            except (OSError, ValueError, TimeoutError, WebSocketException) as error:
                if not stop.is_set():
                    errors.append(error)

        thread = Thread(target=feed, name="cctv-live-feed", daemon=True)
        thread.start()
        try:
            yield jpeg_images(process.stdout), errors
        finally:
            stop.set()
            if process.poll() is None:
                process.terminate()
            try:
                process.stdout.close()
            except OSError:
                pass
            thread.join(timeout=3)
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
