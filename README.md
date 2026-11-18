# CCTV — Hiseeu Linux & Home Assistant

Investigating a Linux-native, browser-based and/or Home Assistant interface for the Hiseeu D8208-5 NVR and 5522-F-Q PoE PTZ cameras, without requiring EseeCloud under Wine or obsolete Flash/ActiveX controls.

**Project status and dated technical findings:** [PROJECT_STATUS.md](PROJECT_STATUS.md) (updated 18 November 2026).

## Current progress

- Local NVR HTTP/WebSocket access and recording search demonstrated without manufacturer cloud dependence.
- Complete H.265 keyframe reconstructed from five WebSocket packets; a short playable MP4 sample confirms the underlying video data is recoverable. Continuous playback/live streaming is not yet implemented.
- Original vendor firmware decoded and extracted **offline** (Mission 11); cloud/startup paths and potential serial maintenance access analysed (Mission 12).
- Hidden Telnet activation logic, the \`dbgmode\` command path, engineering interface and LUI command-dispatch architecture identified by **static analysis** (Mission 13). No runtime Telnet/SSH access has been established.
- Home Assistant Generic Camera snapshot access already works and must remain intact.

## Next milestone

Verify the NVR serial console physically and investigate temporary, manually launched maintenance access. Avoid boot-time services, unverified persistent markers, firmware flashing and unnecessary network changes. Then finish a continuous local video receiver and the browser/Home Assistant interface.

The original firmware, evidence bundles, footage, private endpoint credentials and unsanitised capture logs are not included in this repository. Historical investigation details and outstanding uncertainties are recorded in [PROJECT_STATUS.md](PROJECT_STATUS.md).

## Technical guides

- [Offline firmware decoding and extraction](docs/FIRMWARE_ANALYSIS.md) — exact verified model/firmware signature, XOR method, SquashFS offsets, serial console and maintenance evidence, with compatibility warnings.
- [Firmware extraction utility](tools/extract_firmware.py) — SHA-256-pinned, copy-only offline decoder for the documented ROM; not a flashing tool.
- [NVR recording search and local video protocol](docs/NVR_API.md) — the tested read-only HTTP recording query, example NVR address \`192.168.1.100\`, returned fields and current KP2P/HEVC reassembly status.

These materials describe one tested firmware version. A serial root shell, temporary Telnet activation and an SSH daemon remain unverified on the physical NVR.
