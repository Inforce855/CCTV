# CCTV — Hiseeu Linux & Home Assistant

Developing an **independent Linux CCTV server**, a **modern browser-based NVR management interface**, and **Home Assistant integration** for the Hiseeu D8208-5 NVR and 5522-F-Q PoE PTZ cameras, without requiring EseeCloud under Wine or obsolete Flash/ActiveX controls. The existing NVR continues to provide PoE connectivity, 3 TB HDD recording and its integrated 10-inch display; the server provides remote access and management rather than replacing those functions.

**Project status and dated technical findings:** [PROJECT_STATUS.md](PROJECT_STATUS.md) (updated 21 November 2026).

## Current progress

- Local NVR HTTP/WebSocket access and recording search demonstrated without manufacturer cloud dependence.
- Complete H.265 keyframe reconstructed from five WebSocket packets; a short playable MP4 sample confirms the underlying video data is recoverable. Continuous playback/live streaming is not yet implemented.
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

## Target application

- **Standalone Linux service:** Handles NVR/camera connections, stream delivery, recording search/playback, management functions and a local API, independently of Home Assistant.
- **Full web interface:** Modern, responsive browser access to live views, PTZ, timelines, recording playback/export, camera and NVR settings, storage status and event management. Feature parity is a goal, not a claim that all NVR functions are already verified.
- **Home Assistant client:** Live monitoring, events/alerts, status and playback access through the same service; no dependency of core CCTV operations on Home Assistant.
- **Preservation:** NVR remains the recorder and works without the new server; preserve its existing configuration and Home Assistant snapshot functionality.

## Technical guides

- [Offline firmware decoding and extraction](docs/FIRMWARE_ANALYSIS.md) — exact verified model/firmware signature, XOR method, SquashFS offsets, serial console and maintenance evidence, with compatibility warnings.
- [Firmware extraction utility](tools/extract_firmware.py) — SHA-256-pinned, copy-only offline decoder for the documented ROM; not a flashing tool.
- [NVR recording search and local video protocol](docs/NVR_API.md) — the tested read-only HTTP recording query, example NVR address \`192.168.1.100\`, returned fields and current KP2P/HEVC reassembly status.

These materials describe one tested firmware version. Interactive **U-Boot** access is confirmed on the physical NVR; an interactive **Linux/root shell**, temporary Telnet activation and an SSH daemon remain unverified.
