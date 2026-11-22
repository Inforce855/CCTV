"""Read-only HTTP gateway for the Hiseeu D8208-5."""
import argparse
import base64
from collections import OrderedDict, deque
from datetime import date
import getpass
from itertools import chain
from http.client import HTTPException
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
from threading import Lock
import time
from urllib.error import URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


MAX_CACHED_CLIPS = 4
MAX_CACHED_CLIP_BYTES = 32 * 1024 * 1024


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class LiveFpsMeter:
    """Five-second rolling KP2P input and HTTP JPEG delivery frame rates.

    Source counts encoded video frames handed to FFmpeg, not unique pixels.
    JPEG counts complete multipart images written to the local HTTP client,
    not browser-rendered frames. Neither metric alone establishes latency.
    """

    WINDOW_SECONDS = 5.0

    def __init__(self):
        self.lock = Lock()
        self.started = None
        self.requested_fps = None
        self.source_times = deque()
        self.jpeg_times = deque()
        self.source_count = 0
        self.jpeg_count = 0
        self.last_source_timestamp = None
        self.repeat_timestamp_count = 0

    def begin(self, requested_fps):
        with self.lock:
            self.started = time.monotonic()
            self.requested_fps = requested_fps
            self.source_times.clear()
            self.jpeg_times.clear()
            self.source_count = 0
            self.jpeg_count = 0
            self.last_source_timestamp = None
            self.repeat_timestamp_count = 0

    def source_frame(self, timestamp_ms):
        with self.lock:
            if self.started is None:
                return
            self.source_times.append(time.monotonic())
            self.source_count += 1
            if self.last_source_timestamp == timestamp_ms:
                self.repeat_timestamp_count += 1
            self.last_source_timestamp = timestamp_ms

    def jpeg_frame(self):
        with self.lock:
            if self.started is None:
                return
            self.jpeg_times.append(time.monotonic())
            self.jpeg_count += 1

    def finish(self):
        with self.lock:
            self.started = None
            self.requested_fps = None
            self.source_times.clear()
            self.jpeg_times.clear()

    def snapshot(self):
        with self.lock:
            if self.started is None:
                return {
                    "active": False, "target_fps": None,
                    "source_fps": None, "jpeg_fps": None,
                    "source_frames": 0, "jpeg_frames": 0,
                    "repeated_source_timestamps": 0,
                }
            now = time.monotonic()
            threshold = now - self.WINDOW_SECONDS
            for events in (self.source_times, self.jpeg_times):
                while events and events[0] < threshold:
                    events.popleft()
            elapsed = min(now - self.started, self.WINDOW_SECONDS)

            def rate(events):
                return round(len(events) / elapsed, 1) if elapsed >= 1 else None

            return {
                "active": True, "target_fps": self.requested_fps,
                "source_fps": rate(self.source_times),
                "jpeg_fps": rate(self.jpeg_times),
                "source_frames": self.source_count,
                "jpeg_frames": self.jpeg_count,
                "repeated_source_timestamps": self.repeat_timestamp_count,
            }


class Nvr:
    def __init__(self, origin, username, password):
        self.origin = origin
        self.username = username
        self.password = password
        self.replay_lock = Lock()
        # One active MJPEG viewer per camera; four independent KP2P sessions.
        self.live_locks = tuple(Lock() for _ in range(4))
        self.live_fps_meters = tuple(LiveFpsMeter() for _ in range(4))
        self.replay_cache = OrderedDict()
        token = base64.b64encode(f"{username}:{password}".encode()).decode()
        self.authorization = f"Basic {token}"
        self.opener = build_opener(ProxyHandler({}), NoRedirects())

    def request(self, path, parameters=None):
        headers = {"Authorization": self.authorization, "Accept": "application/json"}
        data = None
        if parameters is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps({
                "DEV": "XVR", "VER": "1.0", "API": "R.SearchRecord",
                "Parameter": parameters,
            }).encode()
        request = Request(self.origin + "/netsdk/" + path, data, headers)
        with self.opener.open(request, timeout=10) as response:
            body = response.read(2_000_001)
        if len(body) > 2_000_000:
            raise ValueError("NVR response exceeds size limit")
        result = json.loads(body)
        if isinstance(result, dict) and str(result.get("RetCode", "0")) != "0":
            raise ValueError("NVR rejected request")
        return result

    def status(self):
        status = self.request("Stat")
        inventory = self.request("Channel/IPCamInfo")
        if not isinstance(inventory, list):
            raise ValueError("Unexpected camera inventory")
        cameras = {str(row["ID"]): row for row in inventory if isinstance(row, dict)}
        disk = status["HDDState"]
        return {
            "storage": {
                **fields(disk, "Count", "Total", "Used", "Free", "UsedPercentage"),
                "drives": [
                    fields(row, "ID", "Model", "Capacity", "Used", "Status")
                    for row in disk["HDDInfo"] if isinstance(row, dict) and row.get("ID")
                ],
            },
            "channels": [
                {
                    **fields(row, "ID", "Status", "RecordingState", "BcamOnline"),
                    **fields(cameras.get(str(row["ID"]), {}), "Enable", "Modelname"),
                }
                for row in status["IPC"] if isinstance(row, dict)
            ],
        }

    def recordings(self, day, channel, page):
        result = self.request("R.SearchRecord", {
            "Channel": ["True" if slot == channel else "False" for slot in range(1, 9)],
            "Type": ["True", "True", "True"],
            "Date": day,
            "BeginTime": "00:00:00",
            "EndTime": "23:59:59",
            "PageSize": 12,
            "CurrentPage": page,
            "Reload": "True",
        })
        return {
            **fields(result, "ReadCnt", "SearchCnt"),
            "items": [
                fields(row, "ID", "Channel", "Type", "Disk", "TotalSize", "TimeStart", "TimeEnd")
                for row in result.get("Item", []) or [] if isinstance(row, dict)
            ],
        }


def fields(value, *keys):
    return {key: value[key] for key in keys if key in value}


def live_preview_query(query):
    """Validate the on-demand SD preview query without changing NVR settings."""
    values = parse_qs(query, max_num_fields=3, keep_blank_values=True)
    if (set(values) not in ({"channel", "stream"}, {"channel", "stream", "fps"})
            or any(len(items) != 1 for items in values.values())
            or values["stream"] != ["1"]):
        raise ValueError("Invalid live preview query")
    channel = int(values["channel"][0])
    fps = int(values.get("fps", ["5"])[0])
    if not 1 <= channel <= 4 or fps not in (5, 10, 15):
        raise ValueError("Invalid live preview channel or frame rate")
    return channel, fps


def recording_query(query):
    values = parse_qs(query, keep_blank_values=True, max_num_fields=3)
    if set(values) - {"date", "channel", "page"} or any(len(v) != 1 for v in values.values()):
        raise ValueError
    day = values.get("date", [""])[0]
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", day):
        raise ValueError
    date.fromisoformat(day)
    channel = int(values.get("channel", ["1"])[0])
    page = int(values.get("page", ["1"])[0])
    if not 1 <= channel <= 8 or not 1 <= page <= 2_147_483_647:
        raise ValueError
    return day, channel, page


def handler(nvr, port):
    class GatewayHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def reply(self, status, body):
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def live(self, query):
            """Read-only, on-demand SD MJPEG preview for cameras 1–4."""
            try:
                channel, fps = live_preview_query(query)
            except (ValueError, KeyError):
                self.reply(400, {"error": "Use channel=1–4, stream=1 (SD), fps=5/10/15"})
                return
            live_lock = nvr.live_locks[channel - 1]
            if not live_lock.acquire(blocking=False):
                self.reply(409, {"error": f"Camera {channel} SD preview is already running"})
                return
            meter = nvr.live_fps_meters[channel - 1]
            meter.begin(fps)
            started = False
            try:
                from live_preview import mjpeg_preview
                host = urlsplit(nvr.origin).hostname
                if ":" in host:
                    host = f"[{host}]"
                self.log_message("Starting Camera %d SD live preview at %d fps", channel, fps)
                with mjpeg_preview(f"ws://{host}:10000/", nvr.username, nvr.password,
                                   channel - 1, 1, fps=fps,
                                   on_source_frame=meter.source_frame) as (images, errors):
                    first = next(images, None)
                    if first is None:
                        raise ValueError("No JPEG received from live video")
                    self.send_response(200)
                    self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                    self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                    self.send_header("Connection", "close")
                    self.close_connection = True
                    self.end_headers()
                    started = True
                    for frame in chain((first,), images):
                        self.wfile.write(
                            b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " +
                            str(len(frame)).encode() + b"\r\n\r\n" + frame + b"\r\n"
                        )
                        meter.jpeg_frame()
                    if errors:
                        self.log_message("Live preview source error: %s", errors[0])
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception as error:
                self.log_message("Live preview error: %s", error)
                if not started:
                    self.reply(502, {"error": f"Could not start Camera {channel} SD live preview"})
            finally:
                meter.finish()
                live_lock.release()
                self.log_message("Stopped Camera %d SD live preview", channel)

        def playback(self, query):
            try:
                values = parse_qs(query, max_num_fields=4, keep_blank_values=True)
                if set(values) != {"start", "channel", "seconds", "type"} or any(len(v) != 1 for v in values.values()):
                    raise ValueError
                start, channel, seconds, kinds = (
                    int(values[key][0]) for key in ("start", "channel", "seconds", "type")
                )
                if not (1 <= channel <= 8 and 1 <= seconds <= 30 and
                        0 <= start <= 0xFFFFFFFF - seconds and kinds in (1, 2, 4, 8)):
                    raise ValueError
            except ValueError:
                self.reply(400, {"error": "Invalid recording time, camera, duration or type"})
                return
            try:
                from browser_playback import browser_stream, mp4_boxes
            except ImportError:
                self.reply(503, {"error": "Install the playback dependencies listed in the README"})
                return
            if not nvr.replay_lock.acquire(blocking=False):
                self.reply(409, {"error": "Another recording is still loading. Try again shortly."})
                return
            sent = False
            key = (start, channel, seconds, kinds)
            try:
                if key in nvr.replay_cache:
                    first, media = nvr.replay_cache[key]
                    nvr.replay_cache.move_to_end(key)
                    self.log_message("Replay cache hit (%d bytes)", len(media))
                    self.send_response(200)
                    self.send_header("Content-Type", "video/mp4")
                    self.send_header("Content-Length", str(len(media)))
                    self.send_header("X-First-Frame-MS", str(first))
                    self.send_header("X-Replay-Cache", "hit")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    sent = True
                    self.wfile.write(media)
                    return
                self.log_message("Replay cache miss")
                host = urlsplit(nvr.origin).hostname
                if ":" in host:
                    host = f"[{host}]"
                with browser_stream(f"ws://{host}:10000/", nvr.username, nvr.password,
                                    channel - 1, start, start + seconds, kinds) as (first, output, process, errors, complete):
                    boxes = mp4_boxes(output)
                    initial = next(boxes, None)
                    if initial is None:
                        raise ValueError("No browser video returned")
                    self.send_response(200)
                    self.send_header("Content-Type", "video/mp4")
                    self.send_header("X-Replay-Cache", "miss")
                    self.send_header("Transfer-Encoding", "chunked")
                    self.send_header("Connection", "close")
                    self.close_connection = True
                    self.send_header("X-First-Frame-MS", str(first))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    sent = True
                    cached = bytearray()
                    for box in chain((initial,), boxes):
                        if cached is not None:
                            if len(cached) + len(box) <= MAX_CACHED_CLIP_BYTES:
                                cached.extend(box)
                            else:
                                cached = None
                        self.wfile.write(f"{len(box):X}\r\n".encode() + box + b"\r\n")
                    if process.wait() == 0 and not errors:
                        if complete.is_set() and cached:
                            nvr.replay_cache[key] = (first, cached)
                            if len(nvr.replay_cache) > MAX_CACHED_CLIPS:
                                nvr.replay_cache.popitem(last=False)
                            self.log_message("Replay cached (%d bytes)", len(cached))
                        elif not complete.is_set():
                            self.log_message("Replay not cached: recording ended before the requested boundary")
                        elif cached is None:
                            self.log_message("Replay not cached: exceeded %d bytes", MAX_CACHED_CLIP_BYTES)
                        self.wfile.write(b"0\r\n\r\n")
                    else:
                        self.log_message("Replay not cached: media stream failed")
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:
                if not sent:
                    self.reply(502, {"error": "Could not start recording playback"})
            finally:
                nvr.replay_lock.release()

        def do_GET(self):
            if self.headers.get("Host") not in {f"127.0.0.1:{port}", f"localhost:{port}"}:
                self.reply(400, {"error": "Use the local gateway address"})
                return
            target = urlsplit(self.path)
            if target.path == "/live":
                try:
                    data = Path(__file__).with_name("live.html").read_bytes()
                except OSError:
                    self.reply(503, {"error": "The live-view page is missing"})
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)
                return
            if target.path == "/playback":
                try:
                    data = Path(__file__).with_name("playback.html").read_bytes()
                except OSError:
                    self.reply(503, {"error": "The browser playback page is missing"})
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)
                return
            if target.path == "/api/live/metrics":
                if self.headers.get("Sec-Fetch-Site") != "same-origin":
                    self.reply(403, {"error": "Open the local live page to read FPS metrics"})
                    return
                self.reply(200, {
                    "window_seconds": LiveFpsMeter.WINDOW_SECONDS,
                    "cameras": [
                        {"channel": channel, **meter.snapshot()}
                        for channel, meter in enumerate(nvr.live_fps_meters, 1)
                    ],
                })
                return
            if target.path == "/api/live":
                if self.headers.get("Sec-Fetch-Site") != "same-origin":
                    self.reply(403, {"error": "Open the local live page to view live video"})
                    return
                self.live(target.query)
                return
            if target.path == "/api/playback":
                if self.headers.get("Sec-Fetch-Site") != "same-origin":
                    self.reply(403, {"error": "Open the gateway playback page to start a recording"})
                    return
                self.playback(target.query)
                return
            if target.path == "/api/recordings":
                try:
                    parameters = recording_query(target.query)
                except ValueError:
                    self.reply(400, {"error": "Use date=YYYY-MM-DD, channel=1–8 and page>=1"})
                    return
                operation = lambda: nvr.recordings(*parameters)
            elif target.path == "/api/status":
                operation = nvr.status
            else:
                self.reply(404, {"error": "Unknown route"})
                return
            try:
                result = operation()
            except (URLError, OSError, HTTPException, ValueError, KeyError, TypeError, AttributeError):
                self.reply(502, {"error": "NVR request failed or returned unexpected data"})
                return
            self.reply(200, result)

    return GatewayHandler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("origin", help="NVR base URL, e.g. http://192.168.1.100")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    origin = urlsplit(args.origin)
    if (origin.scheme not in {"http", "https"} or not origin.hostname
            or origin.username is not None or origin.path not in {"", "/"}
            or origin.query or origin.fragment or not 1 <= args.port <= 65535):
        parser.error("Provide a plain HTTP(S) origin and a valid local port")
    password = os.environ.get("CCTV_NVR_PASSWORD")
    if password is None:
        password = getpass.getpass("NVR password: ")
    nvr = Nvr(args.origin.rstrip("/"), args.username, password)
    with ThreadingHTTPServer(("127.0.0.1", args.port), handler(nvr, args.port)) as server:
        print(f"CCTV gateway listening at http://127.0.0.1:{args.port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
