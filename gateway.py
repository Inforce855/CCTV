"""Read-only HTTP gateway for the Hiseeu D8208-5."""
import argparse
import base64
from datetime import date
import getpass
from http.client import HTTPException
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import re
from urllib.error import URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Nvr:
    def __init__(self, origin, username, password):
        self.origin = origin
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
        def reply(self, status, body):
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.headers.get("Host") not in {f"127.0.0.1:{port}", f"localhost:{port}"}:
                self.reply(400, {"error": "Use the local gateway address"})
                return
            target = urlsplit(self.path)
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
    with HTTPServer(("127.0.0.1", args.port), handler(nvr, args.port)) as server:
        print(f"CCTV gateway listening at http://127.0.0.1:{args.port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
