# Local NVR HTTP and WebSocket recording access

**Scope:** Hiseeu D8208-5 firmware 3.2.4.0. Tested with an actual device on 17 November 2026. **All addresses below are examples**: substitute your own NVR address. Never upload passwords, cookies, camera footage or captured authenticated WebSocket data to public repositories.

## Read-only recording search — tested

The NVR responds to **HTTP POST** at `/netsdk/R.SearchRecord`. Its saved browser client issues a JSON request with a `DEV`/`VER`/`API` envelope and a `Parameter` object. A live test with the same structure returned an `Item` array of recording entries. This is **verified**, not merely a string found in the firmware.

Replace `192.168.1.100` with your NVR address, and choose a day on which recordings exist. The command prompts for the NVR admin password; it does not put the password directly into shell history:

```bash
curl --max-time 15 -sS \
  --basic --user admin \
  -H 'Content-Type: application/json' \
  --request POST \
  'http://192.168.1.100/netsdk/R.SearchRecord' \
  --data '{
    "DEV": "XVR",
    "VER": "1.0",
    "API": "R.SearchRecord",
    "Parameter": {
      "Channel": ["True","False","False","False","False","False","False","False"],
      "Type": ["True","True","True"],
      "Date": "2026-11-17",
      "BeginTime": "00:00:00",
      "EndTime": "23:59:59",
      "PageSize": 12,
      "CurrentPage": 1,
      "Reload": "True"
    }
  }' | python3 -m json.tool
```

- This example searches the **first of eight NVR channels** (the API returned `"Channel":"0"` for this physical first channel). A channel selector is an **array of string booleans**, not JSON booleans.
- The `Type` filter has three string entries as observed in the saved web client; it is **not** interchangeable with the per-record `Type` codes returned by the API.
- `PageSize` and `CurrentPage` control pagination. Live responses contained `Item`, `ReadCnt`, `SearchCnt` and recording metadata.
- Recorded item fields included `ID`, `Channel`, `Type`, `Disk`, `TotalSize`, `TimeStart` and `TimeEnd`. These timestamps were Unix seconds represented as strings.
- In the web client's display logic, recording `Type` values are `1` (Timing), `2` (Motion), `4` (Alarm) and `8` (Manual). Do not assume every model uses the same categories.
- This call **searches metadata only**. It does not retrieve the recording file or initiate playback.

For machines where no administrator password is configured, the behaviour may differ, but deliberately avoid publishing an unauthenticated NVR to the internet.

## Other local endpoints identified in the saved client

| Function | Path or transport | Evidence status |
| --- | --- | --- |
| Device information | `GET /netsdk/Stat/DeviceInfo` | **Verified with actual NVR**. Authenticated JSON includes firmware build time and maximum channel count. |
| Camera/channel inventory | `GET /netsdk/Channel/IPCamInfo` | **Verified with actual NVR**. Returns channel IDs, enabled flags, model, protocol and advertised capabilities. |
| Recording search | `POST /netsdk/R.SearchRecord` | **Verified with actual NVR** |
| Recording schedules | `GET /netsdk/Record` | **Read verified with actual NVR**. Returns per-channel timer, motion and alarm schedules. Write behaviour remains unverified. |
| PTZ | `POST /netsdk/Channel/PTZ` | Found in client code; end-to-end control not yet verified |
| WebSocket KP2P | `ws://192.168.1.100:10000/` | **Local connection/login observed** |
| NVR browser management | `http://192.168.1.100/` | Management UI works; old playback plugin is obsolete on Linux |

The saved JavaScript uses `apip2p.connectbyip(conn, ip, "10000")`, `apip2p.replay_start()` and `apip2p.onrecvrecframe()`. A separate WebSocket login/handshake is required: a plain HTTP GET to port 10000 is **not** the correct protocol.

## Further API coverage

The saved local client calls KP2P `open_stream` and `close_stream` for live video and `ptz_ctrl` for camera movement. These call sites establish client support. End-to-end live video and PTZ still require verification for this project. The identified HTTP PTZ command is also unverified. Storage status is hardware-verified. Camera connection and recording indicators were observed in the same live response under `IPC[]`. A real-time event feed, settings writes and full clip export remain open. The camera inventory's enabled flag is a configuration field and does not establish online status. Recording search type filters do not establish a live event feed.

Sources for the additional verified HTTP reads are the archived 17–18 November bench results, reviewed 21 November 2026. Camera snapshot support is documented separately in [CAMERA_HTTP_API.md](CAMERA_HTTP_API.md).

## Additional management API calls from the saved web interface

Source: the NVR's saved web bundle (`build.js`), inspected on 21 November 2026. These call sites have been identified offline. Storage status was subsequently verified on the physical NVR. The table records which calls have live evidence.

| Function | Request | Client evidence |
| --- | --- | --- |
| Storage status | `GET /netsdk/Stat` | **Verified on the physical NVR.** The HardDiskSetting component reads `HDDState.HDDInfo[]` and displays `ID`, `Model`, `Capacity`, `Used` and `Status`. A `harddisk` route exists in the bundle. Its visibility in the active menu is unverified. |
| Camera connection status | `GET /netsdk/Stat/IPC` | The channel view polls this endpoint and copies the returned per-channel `Status` into the channel list. Response values and channel mapping still need hardware confirmation. |
| Log history | `POST /netsdk/LogSearch`, `POST /netsdk/LogPageChange` | **Verified via Log Information.** Entries contain `ID`, `Logtime` and `Logdetail`. Captures show timer and motion recording starts and recording stops. `LogSearch` returned eight log rows and `SearchCnt: "814"`. Each captured `LogPageChange` contained eight rows despite `SearchCnt: "0"`. Parse actual object rows in `Item[]` (a numeric placeholder was also observed), and do not use the pagination response’s count to infer an empty page. Human classification and live event delivery remain unverified. |
| Detection and alarm configuration | `GET /netsdk/Event` | **Verified via Video Detection.** Returns eight entries each for `MotionDetection`, `VideoCover` and `VideoLoss`, plus six configured `Error` categories. Motion entries include schedules, region data, human detection options and alarm actions. Live event delivery remains unverified. |
| Per-channel bitrate | `POST /netsdk/GetChannelDetail` | **Verified via captured response.** Returns `Item[]` with channel label, `Kb/s` and `MB/H`, and aggregate totals. |
| NVR snapshots | `POST /NetworkSnap`, then `POST /netsdk/R.RmScreenShotFile` | The client requests a JPEG for region editing and cleans up the temporary file. The Video Detection capture included a JPEG data URL and a successful cleanup response. |

The live `HDDState` response reported one drive (`Count: "1"`) and eight `HDDInfo` slots, seven with empty IDs. Capacity and percentage values are formatted strings. The populated slot reported `Status: "Formatted"`. This field does not establish SMART health or overwrite behaviour.

The same live `GET /netsdk/Stat` response contained `IPC[]`. Zero-based IDs 0–3 (connected cameras) reported `Status: "Connect success"` and `RecordingState: "1"`. IDs 4–7 (unused slots on this unit) reported `Status: "Updating"` and `RecordingState: "0"`. One expanded camera entry also showed `BcamOnline: "True"`. Join by `IPC[].ID` with the configured inventory from `/netsdk/Channel/IPCamInfo` to distinguish unused slots. The response's `ChnInfo[]` status fields were empty. Motion-related fields were present, but transitions and real-time event delivery remain unverified. Treat the observed status strings as observations, not a complete enumeration.

Use the GET method for the storage check. The separate POST to `/netsdk/Stat` is used by the disk-format workflow.

### Browser checks on the physical NVR

- **Channel Detail** displayed configured main streams of 2880 × 1620 at 15 fps (3 or 5 Mbps by channel) and substreams of 800 × 448 at 15 fps (512 kbps) on all four connected cameras. Unused slots were blank. These are configured profiles. Measured bitrate comes from the separately captured channel bitrate response.
- **Log Information** offers System startup, System shutdown, System config change, Record, Alarm, Device warning, Exception log and All. An Alarm search for 21 November 2026 returned 54 entries. Its first page contained video-loss entries (`EVT_VLOSS_1` through `EVT_VLOSS_4`). Human detection entries were not established by this sample.

## Native live-stream wire format (vendor source, 22 November 2026)

The original saved `Netword video client_files/import.js` was re-examined, rather than inferring wire commands from API names. It explicitly constructs:

- `open_stream(conn, channel, stream)`: `APP_PROTO_CMD_LIVE_REQ = 30` with a 12-byte little-endian body `(channel, streamid, live_cmd=2)`.
- `close_stream(conn, channel, stream)`: the same command with `live_cmd=1`.
- Acknowledgement: `APP_PROTO_CMD_LIVE_RSP = 31`, whose body returns channel, stream ID and live command.
- Stream selection: `0` main (HD), `1` substream (SD). Camera/channel indices start at zero.
- Video reception: `FRAM`/optional `FRAN` prefix, a 24-byte common frame header with type `0` for live, an 8-byte live head, a 24-byte codec/video-parameter header and eight additional bytes before raw video data. The video callback exposes codec, frames per second, width, height, channel and I/P-frame type. Multi-packet frame reassembly must be maintained.

The new `live_stream.py` requests this exact live command through the already tested login transport. The new on-demand `/api/live?channel=1&stream=1` route feeds a 5 fps MJPEG preview via FFmpeg to Camera 1 in the existing `/live` page. **Only the original vendor JavaScript command layout and offline synthetic packet tests are confirmed at this point; a live-camera hardware test remains outstanding.** No PTZ or NVR configuration writes are sent.

## Video data / recording playback

**Verified proof of concept:** The original JavaScript receiver truncated large HEVC/H.265 keyframes by discarding continuation packets. The actual keyframe was **312,768 bytes**, but only **65,432 bytes** were initially delivered to the decoder (a buffer with 104 bytes reserved for a protocol header). By collecting **five** packets and reconstructing the whole frame, a short **nine-frame, ~0.87-second** H.265/MP4 sequence played without the green corruption caused by the missing frame data.

This is evidence that the NVR's local KP2P stream can carry decodable recording video. **Not yet delivered:** a complete tested recording downloader, continuously running live/record playback or Home Assistant component. Rebuilding the player and retrieving an entire recorded clip remain project work.

## Practical next steps

1. Preserve the existing working snapshot integration.
2. Implement a reliable receive/reassembly path using the already captured WebSocket protocol evidence rather than repeatedly probing the NVR.
3. Test continuous recording playback and metadata/time synchronisation before implementing download and Home Assistant playback.
4. Do not expose NVR HTTP or WebSocket services to the public internet.


## Settings inventory (21 November 2026)

All 16 visible Settings pages and the separate Management page were opened on the physical NVR. No settings were submitted. Related API paths below come from the saved client. The browser walkthrough did not independently capture every request or test writes.

| Page | Controls or information observed | Related API |
| --- | --- | --- |
| Device Information | Model, firmware, build time and identifiers | `GET /netsdk/Stat` |
| Video Settings | Weekly per-channel timing, motion and alarm recording grid | `GET /netsdk/Record` |
| Time Settings | Clock, time zone, date format, key buzzer, OSD transparency and VGA resolution | `GET /netsdk/General`, `GET /netsdk/Stat` |
| Network Settings | DHCP, static addressing, web port, DDNS and PPPoE | `GET /netsdk/Network`, `GET /netsdk/Network/PPPoE` |
| E-mail Settings | SMTP and encryption, sender/recipients, notification and health-mail intervals | `GET /netsdk/Network/SMTP` |
| Wifi Settings | ESSID, wireless channel and region, link information | `GET /netsdk/Network/WIFI` |
| Color Settings | Per-channel tone, contrast, brightness and saturation | `GET /netsdk/Stream/Color` |
| Encoding Settings | Main/substream rate control, resolution, bitrate and frame rate, plus main-stream audio/video mode | `GET /netsdk/Stream/Encode` |
| Stream Value | Per-channel throughput in Kb/s and MB/H | See captured bitrate response above |
| Channel Detail | Configured main/substream profiles and software-version column | See browser observations above |
| Channel OSD | Channel title setting | Channel configuration in saved client |
| Video Detection | Motion sensitivity, region editor, arming schedule and notification options | `GET /netsdk/Event`, snapshot workflow above |
| Change Password | Account password form | Form viewed only |
| Log Information | Event filters, time range, retrieval and paging | `POST /netsdk/LogSearch`, `POST /netsdk/LogPageChange` |
| Online Upgrade | Local ROM file selection | Upgrade screen viewed only |
| Factory Settings | Simple restore (preserves channel/network configuration per UI) and full restore | Restore screen viewed only |
| Management | Camera inventory, protocol and add/edit/remove controls | `GET /netsdk/Channel/IPCamInfo`, `GET /netsdk/Stat/IPC` |
