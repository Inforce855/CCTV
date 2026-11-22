# CCTV — Hiseeu Linux & Home Assistant

Developing an **independent Linux CCTV server**, a **modern browser-based NVR management interface**, and **Home Assistant integration** for the Hiseeu D8208-5 NVR and 5522-F-Q PoE PTZ cameras, without requiring EseeCloud under Wine or obsolete Flash/ActiveX controls. The existing NVR continues to provide PoE connectivity, 3 TB HDD recording and its integrated 10-inch display; the server provides remote access and management rather than replacing those functions.

**Project status and dated technical findings:** [PROJECT_STATUS.md](PROJECT_STATUS.md) (updated 22 November 2026).

## Current progress

- Local NVR HTTP/WebSocket access and recording search demonstrated without manufacturer cloud dependence.
- Recorded HEVC video and G.711A audio are retrievable through local KP2P; progressive browser recording playback and replay caching are confirmed. Native Camera 1 SD video **and moving footage** were verified in Chrome on 22 November 2026. All four SD feeds have now been confirmed visible simultaneously in Chrome against the physical NVR (22 November 2026, 17:16 GMT).
- Original vendor firmware decoded and extracted **offline** (Mission 11); cloud/startup paths and potential serial maintenance access analysed (Mission 12).
- Hidden Telnet activation logic, the \`dbgmode\` command path, engineering interface and LUI command-dispatch architecture identified by **static analysis** (Mission 13). Physical 115200-baud UART and **interactive U-Boot access** were confirmed on 21 November 2026; an interactive Linux shell and runtime Telnet/SSH remain unverified.
- Home Assistant Generic Camera snapshot access already works and must remain intact.

## Run the read-only gateway

From the repository on a machine that can reach the NVR, run the following with Python 3.10 or later. Replace the example address with your NVR’s address.

```sh
python3 gateway.py http://192.168.1.100
```

Enter the NVR password when prompted. Use `--username` for an account other than `admin`, or `--port` to change the local port. The service listens on loopback and returns JSON.

```sh
curl -fsS http://127.0.0.1:8080/api/status
curl -fsS 'http://127.0.0.1:8080/api/recordings?date=2026-11-21&channel=1&page=1'
```

- `/api/status` returns disk usage and populated drive slots, plus camera inventory and current connection/recording indicators. Channel IDs in this response are zero-based.
- `/api/recordings` takes the NVR’s calendar date, a one-based channel and a one-based page. Channel and page default to 1. Returned recording metadata retains the original NVR timestamps and zero-based channel numbering.

Both routes passed mock HTTP integration checks and a live smoke test from Nobara on the NVR LAN on 21 November 2026. Continuous recording playback is the next milestone.

The original firmware, evidence bundles, footage, private endpoint credentials and unsanitised capture logs are not included in this repository. Historical investigation details and outstanding uncertainties are recorded in [PROJECT_STATUS.md](PROJECT_STATUS.md).

## Offline playback check

With the private Operation De-Hulk WebSocket capture in your working directory, recover the first camera’s HEVC and its original frame timestamps:

```sh
python3 playback.py hiseeu_raw_websocket.bin recovered.h265 > frames.jsonl
ffplay -framerate 10 -f hevc recovered.h265
```

The 10 fps preview cadence matches the observed interval in this fixture. The JSON Lines output retains the exact timestamps for later playback integration. The capture is kept private. Live WebSocket playback is the next step.

## Live playback smoke test

From the repository on the NVR LAN, use a Python virtual environment for the test dependencies. Replace the example address and choose a start time within a known timed recording.

```sh
python3 -m venv ~/.venvs/cctv-playback
~/.venvs/cctv-playback/bin/python -m pip install 'websockets>=16,<17' cryptography
~/.venvs/cctv-playback/bin/python live_playback.py 192.168.1.100 2026-11-22T08:05:00+00:00 clip.mp4 --channel 2 --seconds 10
ffplay clip.mp4
```

The test prompts for the NVR password and reports frame count and first/last original timestamps. An MP4 output requires FFmpeg and preserves relative NVR frame timing without re-encoding. It retains the decode lead-in and includes an AAC track when the capture provides G.711A audio in the clip window. The summary reports `g711a_frames` and `audio_in_mp4`. Use a .h265 output for the previous raw mode. The summary reports the wait from the start of the replay request to the first frame in range. The client sends a playback stop request at the end and closes the WebSocket. The mock WebSocket test passed. Live retrieval was verified on the physical NVR. The captured clip played cleanly in FFplay at 15 fps on Nobara. Exact seek alignment remains open.

## Four-camera SD live dashboard (22 November 2026)

Start the existing gateway with the playback virtual environment (containing `websockets` and `cryptography`) and FFmpeg installed. Open `http://127.0.0.1:8080/live` (substitute your configured local port). The page shows the four cameras, their NVR connection status and compact grid/single-camera layouts.

**Verified:** Tim viewed moving footage from Camera 1 SD in Chrome on 22 November 2026. Native KP2P session setup, continuous frame reception and the FFmpeg-to-MJPEG browser delivery work on that channel. The initial browser output uses **5 fps** from cameras configured for **800 × 448 at 15 fps**. This preview rate is intentional and does not change the NVR's stream or recording settings.

**Confirmed four-camera operation:** Cameras **1–4** have individual **Start SD live / Stop live** controls, and the toolbar offers **Start all SD / Stop all**. Each active camera opens its own authenticated KP2P session and 5 fps MJPEG FFmpeg conversion at `/api/live?channel=N&stream=1` (N=1–4). The gateway limits each camera to **one active preview**, while permitting up to four distinct camera previews concurrently. **All four live pictures were displayed simultaneously in Chrome** on 22 November 2026, confirming that four independent sessions and FFmpeg preview pipelines can coexist on the tested Nobara machine. Effective frame cadence, long-term stability, CPU/memory usage, latency and stop/restart behaviour still need measurement; start Cameras 2–4 individually if diagnosing issues. In single-camera layout, other started streams remain active until stopped.

HD switching, camera audio and higher preview frame rates are not implemented yet. **Next:** compare the already working four-camera 5 fps preview against 10 and 15 fps under simultaneous load. The existing `/playback`, replay cache, recording frame stepping, and other gateway functionality are preserved.

The original vendor `import.js` confirms the native request command 30, body `<3I` (zero-based channel, 0 main/1 substream, 2 start/1 stop) and response command 31. `live_stream.py` reassembles live frames, and `live_preview.py` converts HEVC/H.264 to MJPEG. Offline synthetic protocol regression tests are available with `~/.venvs/cctv-playback/bin/python -m unittest discover -s tests -p 'test_live_stream.py' -v`; they have not been executed here against your workstation.

## Browser playback preview

Start the gateway with the playback virtual environment described above and open `http://127.0.0.1:8080/playback`. Enter the camera, recording type and local start time. The gateway streams 720p H.264 fragments progressively, using FFmpeg with libx264. Chrome retains the current clip's buffered video for short backwards and forwards jumps. Pause to use Previous frame and Next frame within buffered footage. Playback starts at the first available frame and displays the duration of any lead-in before the requested start.

The preview is single-camera with H.264 video and AAC audio, and uses a nominal 15 fps timeline. Repeat the same camera, start, duration and recording type to reuse a complete clip from the gateway’s in-memory replay cache. The cache holds four clips up to 32 MiB each and clears on restart. The separate MP4 exporter still supports original timestamped HEVC and audio. Progressive delivery passed an HTTP fixture test. Live Chrome on Nobara displayed the recording and supported buffered jumps and timeline seeking after the capture completed. Time to first picture and seeking during capture still need measurement.

## Target application

- **Standalone Linux service:** Handles NVR/camera connections, stream delivery, recording search/playback, management functions and a local API, independently of Home Assistant.
- **Full web interface:** Modern, responsive browser access to live views, PTZ, timelines, recording playback/export, camera and NVR settings, storage status and event management. Feature parity is a goal, not a claim that all NVR functions are already verified.
- **Home Assistant client:** Live monitoring, events/alerts, status and playback access through the same service; no dependency of core CCTV operations on Home Assistant.
- **Preservation:** NVR remains the recorder and works without the new server; preserve its existing configuration and Home Assistant snapshot functionality.

## The completely fictional marketing department

For a deliberately absurd parody of AI CCTV advertising, see [CCTV AI Pro Max Quantum Ultra™](docs/CCTV_AI_QUANTUM_ULTRA.md) and its mock marketing posters. This is satire, **not** a real gateway feature or product.

## Technical guides

- [Offline firmware decoding and extraction](docs/FIRMWARE_ANALYSIS.md) — exact verified model/firmware signature, XOR method, SquashFS offsets, serial console and maintenance evidence, with compatibility warnings.
- [Firmware extraction utility](tools/extract_firmware.py) — SHA-256-pinned, copy-only offline decoder for the documented ROM; not a flashing tool.
- [NVR recording search and local video protocol](docs/NVR_API.md) — the tested read-only HTTP recording query, example NVR address \`192.168.1.100\`, returned fields and current KP2P/HEVC reassembly status.

These materials describe one tested firmware version. Interactive **U-Boot** access is confirmed on the physical NVR; an interactive **Linux/root shell**, temporary Telnet activation and an SSH daemon remain unverified.
