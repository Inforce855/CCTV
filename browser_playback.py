"""Progressive, single-camera browser playback preview."""
import contextlib
from itertools import chain
import os
from queue import SimpleQueue
import struct
import subprocess
from threading import Thread

from websockets.exceptions import WebSocketException

from live_playback import ALAW_RATE, MAX_OUTPUT, replay_frames


@contextlib.contextmanager
def browser_stream(url, username, password, channel, start, end, kinds):
    with replay_frames(url, username, password, channel, start, end, kinds) as (frames, _):
        selected = (f for f in frames if f.channel == channel)
        first = next((f for f in selected if f.codec == "H265" and f.frame_type == 1), None)
        if first is None or first.timestamp_ms >= end * 1000:
            raise ValueError("No decodable video for this recording")
        with contextlib.ExitStack() as resources:
            read_fd, write_fd = os.pipe()
            audio_input = resources.enter_context(os.fdopen(read_fd, "rb"))
            audio_output = resources.enter_context(os.fdopen(write_fd, "wb"))
            process = resources.enter_context(subprocess.Popen([
                "ffmpeg", "-nostdin", "-v", "error",
                "-thread_queue_size", "64", "-f", "hevc", "-framerate", "15",
                "-probesize", "32768", "-analyzeduration", "1", "-i", "pipe:0",
                "-thread_queue_size", "64", "-f", "alaw", "-ar", str(ALAW_RATE),
                "-ac", "1", "-probesize", "32", "-analyzeduration", "1",
                "-i", f"pipe:{read_fd}", "-map", "0:v:0", "-map", "1:a:0",
                "-c:a", "aac", "-ar", "48000", "-b:a", "48k",
                "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
                "-vf", "scale=1280:-2", "-pix_fmt", "yuv420p",
                "-profile:v", "baseline", "-level:v", "3.1", "-g", "15",
                "-movflags", "+empty_moov+default_base_moof",
                "-frag_duration", "250000", "-f", "mp4", "pipe:1",
            ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, pass_fds=(read_fd,)))
            audio_input.close()
            errors = []
            video_queue, audio_queue = SimpleQueue(), SimpleQueue()

            def write_pipe(destination, queue):
                try:
                    with destination:
                        for data in iter(queue.get, None):
                            destination.write(data)
                            destination.flush()
                except OSError as error:
                    errors.append(error)

            def feed():
                audio_position = 0
                video_end = 0
                video_bytes = 0
                samples_per_ms = ALAW_RATE // 1000
                limit = (end * 1000 - first.timestamp_ms) * samples_per_ms

                def silence_until(position):
                    nonlocal audio_position
                    if position > audio_position:
                        audio_queue.put(b"\xd5" * (position - audio_position))
                        audio_position = position

                try:
                    for frame in chain((first,), selected):
                        if process.poll() is not None:
                            break
                        if frame.codec == "H265":
                            if frame.timestamp_ms >= end * 1000:
                                break
                            video_bytes += len(frame.data)
                            if video_bytes > MAX_OUTPUT:
                                raise ValueError("Preview exceeded the video size limit")
                            video_queue.put(frame.data)
                            video_end = min(limit, (frame.timestamp_ms - first.timestamp_ms + 67) * samples_per_ms)
                            silence_until(video_end - ALAW_RATE // 4)
                        elif frame.codec == "G711A" and frame.frame_type == 0:
                            start_sample = (frame.timestamp_ms - first.timestamp_ms) * samples_per_ms
                            position = max(start_sample, audio_position)
                            data = frame.data[position - start_sample:position - start_sample + max(0, limit - position)]
                            if data:
                                silence_until(position)
                                audio_queue.put(data)
                                audio_position += len(data)
                    silence_until(video_end)
                except (OSError, ValueError, WebSocketException) as error:
                    errors.append(error)
                finally:
                    video_queue.put(None)
                    audio_queue.put(None)

            threads = [
                Thread(target=write_pipe, args=(process.stdin, video_queue)),
                Thread(target=write_pipe, args=(audio_output, audio_queue)),
                Thread(target=feed),
            ]
            for thread in threads:
                thread.start()
            try:
                yield first.timestamp_ms, process.stdout, process, errors
            finally:
                if process.poll() is None:
                    process.terminate()
                for thread in threads:
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
