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


def preview_command(codec, source_fps, output_fps):
    """Build the MJPEG encoder command for one SD camera preview."""
    if codec not in ("H264", "H265") or not 1 <= source_fps <= 120:
        raise ValueError("Unsupported source codec or frame rate")
    if output_fps not in (5, 10, 15):
        raise ValueError("Preview fps must be 5, 10 or 15")
    format_name = "hevc" if codec == "H265" else "h264"
    return [
        "ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error",
        "-f", format_name, "-framerate", str(source_fps),
        "-probesize", "32768", "-analyzeduration", "1", "-i", "pipe:0",
        "-an", "-vf", f"fps={output_fps}", "-c:v", "mjpeg", "-q:v", "6",
        "-f", "image2pipe", "pipe:1",
    ]


@contextmanager
def mjpeg_preview(url, username, password, channel=0, stream=1, fps=5):
    """Yield JPEGs at the chosen preview fps; closing stops the KP2P stream."""
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
        process = subprocess.Popen(
            preview_command(first.codec, first.fps, fps),
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
