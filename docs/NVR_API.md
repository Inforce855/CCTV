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
| Recording search | `POST /netsdk/R.SearchRecord` | **Verified with actual NVR** |
| Recording configuration | `/netsdk/Record` | Found in client code; do not assume read/write operations are safe |
| PTZ | `POST /netsdk/Channel/PTZ` | Found in client code; end-to-end control not yet verified |
| WebSocket KP2P | `ws://192.168.1.100:10000/` | **Local connection/login observed** |
| NVR browser management | `http://192.168.1.100/` | Management UI works; old playback plugin is obsolete on Linux |

The saved JavaScript uses `apip2p.connectbyip(conn, ip, "10000")`, `apip2p.replay_start()` and `apip2p.onrecvrecframe()`. A separate WebSocket login/handshake is required: a plain HTTP GET to port 10000 is **not** the correct protocol.

## Video data / recording playback

**Verified proof of concept:** The original JavaScript receiver truncated large HEVC/H.265 keyframes by discarding continuation packets. The actual keyframe was **312,768 bytes**, but only **65,432 bytes** were initially delivered to the decoder (a buffer with 104 bytes reserved for a protocol header). By collecting **five** packets and reconstructing the whole frame, a short **nine-frame, ~0.87-second** H.265/MP4 sequence played without the green corruption caused by the missing frame data.

This is evidence that the NVR's local KP2P stream can carry decodable recording video. **Not yet delivered:** a complete tested recording downloader, continuously running live/record playback or Home Assistant component. Rebuilding the player and retrieving an entire recorded clip remain project work.

## Practical next steps

1. Preserve the existing working snapshot integration.
2. Implement a reliable receive/reassembly path using the already captured WebSocket protocol evidence rather than repeatedly probing the NVR.
3. Test continuous recording playback and metadata/time synchronisation before implementing download and Home Assistant playback.
4. Do not expose NVR HTTP or WebSocket services to the public internet.
