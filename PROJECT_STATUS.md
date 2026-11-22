# Hiseeu CCTV — PROJECT_STATUS

**Updated:** 21 November 2026  
**Repository:** Inforce855/CCTV  
**Status:** Offline firmware and local NVR recording investigations completed; physical UART and interactive U-Boot confirmed on 21 November. Linux shell/temporary SSH, continuous video playback, and browser/HA application remain outstanding.

> **Privacy:** IP addresses below are illustrative, **not** the actual addresses of the investigated equipment. NVR: \`192.168.1.100\`; cameras: \`192.168.1.101\`–\`192.168.1.104\`. Never publish actual internal addresses, credentials, authenticated URLs, camera footage, or unsanitised captures.

## Objective

Develop an **independent Linux CCTV server** with a **modern browser-based full NVR management interface** and **Home Assistant integration**, avoiding EseeCloud under Wine and obsolete Flash/ActiveX. Target NVR feature parity (viewing, PTZ, settings, recordings, search, playback and export) subject to verification of protocol capabilities. The NVR retains all PoE camera connections, its 3 TB HDD, continuous recording and built-in 10-inch monitoring display. Home Assistant connects as a client for monitoring, playback access, events, alerts and automation; the core server and browser UI must work without HA. Preserve the working Home Assistant Generic Camera snapshot functionality and original NVR configuration.

## Equipment and environment

- NVR: Hiseeu D8208-5, firmware **3.2.4.0** (26 August 2023). Example address: **192.168.1.100**.
- Four PoE PTZ cameras: Hiseeu **5522-F-Q**, example addresses **192.168.1.101–192.168.1.104**; original NVR configuration showed communication protocol **N1**, port **80**, all connected.
- Home Assistant Generic Camera successfully retrieves an individual camera snapshot from \`/snapshot.jpg\` with an \`auth\` query parameter (actual authenticated URL is private; camera address shown here is only an example).
- Linux Chrome renders the NVR's management site at \`http://192.168.1.100/#/manage\`. Legacy browser video requires Windows ActiveX/other obsolete clients; alternative local HTTP and WebSocket paths have since been identified.
- Separate camera browser pages rely on obsolete Flash (\`JaViewer.swf\`).
- The NVR has an integrated display and a separate HDMI output. Its local GUI uses text-based \`.lui\` resources.

## Completed: live local NVR investigations (17–18 November 2026)

- **Verified:** Local HTTP API, recording search and WebSocket/KP2P connection work without relying on the vendor cloud.
- **Verified recording query:** \`POST /netsdk/R.SearchRecord\` with a JSON \`DEV\`/\`VER\`/\`API\` envelope and \`Parameter\` object. Responses include \`Item\`, \`ReadCnt\`, \`SearchCnt\`; each recording contains its channel/type, start/end times and disk metadata. A tested request body using **192.168.1.100** is documented in [docs/NVR_API.md](docs/NVR_API.md). Metadata lookup is **not** equivalent to complete recording download.
- **Verified video recovery:** Original web JavaScript discarded continuation packets of large H.265/HEVC keyframes. A keyframe of **312,768 bytes** was truncated to an initial **65,432 bytes**. Reassembling five WebSocket packets produced a playable nine-frame (~0.87-second) HEVC/MP4 sample without the green corruption of the incomplete frame.
- **Not yet complete:** A continuous native stream receiver, full recording playback/download, integrated PTZ/audio, and Home Assistant/browser frontend.
- The NVR client code contains \`apip2p.connectbyip\` (WebSocket port **10000**), \`apip2p.replay_start\`, \`apip2p.onrecvrecframe\` and an \`arq_open_conn\` handshake. A plain HTTP GET to port 10000 is not the protocol.

## Completed: Mission 11 — original ROM format and extraction

- Manufacturer-supplied sample: \`FWHI10E_20230826_NVR_D8208-5_3_2_4_0_0x6810E105_RELEASE.rom\`, **14,124,060 bytes**; SHA-256 \`77647dd058dea55ed1c6dd54c0ab3496d6afdd3392a1afba8f9ee57be4fffb5a\`.
- Vendor container uses repeating **64-byte XOR obfuscation**, not standard encrypted firmware. Five sections identified: two FDT, XZ kernel stream and two SquashFS images; **544 files / approximately 52 MB** extracted offline.
- Identified **Molchip MC6810E**, ARM32 little-endian Linux, **uClibc 0.9.33.2**, BusyBox and \`app.out\` (**10,253,848 bytes**, SHA-256 \`d0a17ccf5ec71ec7a511a42cfa27f007552b33856d5d5abd2846b3b136255f50\`).
- Section offsets and exact decoding procedure are in [docs/FIRMWARE_ANALYSIS.md](docs/FIRMWARE_ANALYSIS.md); a deliberately SHA-256-locked, read-only sample extractor is in [tools/extract_firmware.py](tools/extract_firmware.py).
- **Limits:** Firmware compatibility varies with hardware, even within nominally identical models. No safe flash recovery, A/B rollback or guaranteed rescue route has been established. Preserve the original ROM; do not flash it during this project.

## Completed: Mission 12 — cloud, security and startup audit (static only)

- Firmware contains code/strings for cloud P2P, push, diagnostics, vendor time/licence services and firmware updates. This is **code-capability evidence**, **not** proof that any particular endpoint was contacted by the running NVR. Outbound-traffic observation remains outstanding.
- Init scripts, device-tree boot args and \`/etc/inittab\` indicate a possible **root shell via \`ttyS0\` at 115200 baud**. **Physical bidirectional UART and interactive U-Boot are now confirmed (21 November 2026); an interactive Linux shell is not yet confirmed.**
- Telnet utilities \`telnet\` and \`telnetd\` were found in the extracted firmware; **live TCP port 23 was connection refused** in earlier tests. Telnet does **not** appear enabled under the observed normal configuration.
- Startup mounts the application storage under \`/opt\`; extracted application startup scripts, config and maintenance flags warrant inspection on real hardware before assuming any writes survive a reboot.
- The upgrade utility checks various identifiers/version/magic/CRC values. A matching model label **does not** demonstrate firmware compatibility.

## Completed: Mission 13 — hidden commands and LUI framework (static only)

- \`NK_UpdateMaintenanceInfo\` at \`0x1386c0\` checks \`$.Stat.Proc.IsOpen\` and contains conditional Telnet start/stop commands.
- \`NK_CMDLINE_todo\` at \`0x10fc6c\` handles a \`dbgmode 1\`/\`dbgmode 0\` path; \`sub_137f7c\` at \`0x137f7c\` reads command lines from \`/tmp/in\`. Whether this input endpoint exists and works on actual hardware remains unverified.
- \`nvr_app_init0\` at \`0x138204\` tests \`/tmp/debug\`, \`/config/test\` and \`/cf/test\` as possible maintenance markers. **Do not assume \`/config/test\` or \`/cf/test\` is volatile**; check mount persistence before use.
- Existing \`contractor_mode.lui\` and engineer-mode commands were identified. The GUI loads resources via \`/opt/app/dialog/conf/n9204_janewui1.conf\`; \`GUIControl::SyncCall\`/\`AsyncCAll\` dispatch to internally registered JSON-API handlers (~164 identified). Exposing new shell commands by editing LUI alone was **not** demonstrated.
- No preinstalled Dropbear/OpenSSH server was identified. A manually invoked compatible ARM32 Dropbear **may** be feasible without altering \`app.out\`, but requires physical access and compatibility testing. An SSH **button** in the LUI is a different, unresolved task.
- **Goal for maintenance access:** Manually start Telnet or SSH only as needed; **never** enable automatic boot startup. Keep the first tests in RAM where possible so reboot restores normal behaviour. A reboot does not undo changes to persistent files.

## Earlier investigation — useful retained evidence (5 November 2026)

### Windows software and historical interfaces

- EseeCloud under Wine was examined without running unknown installers during the investigation; an earlier window-scaling regression after Wine updates remained unexplained. EseeCloud includes \`libcef.dll\`, FFmpeg components, \`IOTLink.dll\`, \`P2PSDKClient.dll\`, \`libonvifc.dll\` and other libraries.
- \`EseeCloud.exe\` has a CodeView RSDS reference to a Windows \`cms.pdb\` build path; a candidate \`cms.pdb\` was present but its GUID/age match was **not verified**.
- NVR-supplied \`WebClient.exe\` was an NSIS 1.3.0.2 installer (610,224 bytes, 18 files, dated 2017–2018), **extracted without execution**. Relevant libraries: \`WebCtrlLite.ocx\` (125,080 B), \`playbackwnd.ocx\` (96,296 B), \`HiSiClientSdk.dll\`, \`iotlink.dll\`, \`NetSdk.dll\`, \`P2PSDKClient.dll\`, H.265/H.264 decoders and \`arq.dll\`.
- Both OCX files are PE32 COM libraries containing \`TYPELIB\` resources, inspected with \`objdump\` and \`winedump\`. Their methods provide background context, **not** a replacement for the since-verified direct APIs.
- \`WebCtrlLite.ocx\` exposed method names including \`CheckConnect\`, \`OpenChannel\`, \`OpenChannelEx\`, \`CloseChannel\`, \`OpenAll\`, \`OpenStream\`, \`CloseStream\`, \`SetDispWndDivMode\`, \`CaptureChlImage\`, \`GetChannelStatus\`, \`getCurChannelBitrate\`. \`SetCtlPtz\` appeared in strings but was **not** confirmed as a COM-dispatch method.
- \`playbackwnd.ocx\` exposed names including \`ConnectRecServer\`, \`StartReplay\`, \`StartReplayEx\`, \`RecPlay\`, \`RecPause\`, \`RecStop\`, \`RecByFrame\`, \`GetPlayStatus\`, \`GetConnectStatus\`, \`RecFast\`, \`RecSlow\`, \`ConnectAndLogin\`. Provisional signatures: \`ConnectRecServer(BSTR address, int32 port)\`; \`StartReplay(int32 channels, int32 types, int32 start, int32 end, int32 cleanBuffer)\`. Exact dispatch-ID association was **not established**.

### Additional notes from the original 5 November investigation

- The NVR web client embedded a `client_ocx` object with CLSID `69AF533A-A219-452D-89B1-16A9E65D6AAA`. Both extracted OCXs exported `DllGetClassObject`, `DllRegisterServer` and `DllUnregisterServer`. The installer also contained `inst.bat`, `unst.bat`, `WebCtrlLiteSettings.ini` and `playbackwndmsg.ini`.
- The live-control type library also listed `CloseChannelEx`. The playback type library named the class `PLAYBACKWND_KP2P.PlaybackwndCtrl.1` and listed `RecGetCurrentTimet` (spelling as observed).
- The original TypeInfo inspection provisionally associated an `int32` return with `ConnectRecServer` and a `void` return with `StartReplay`. The dispatch-ID associations and the encoding of the legacy COM start and end parameters remain unverified. These are observations from the legacy type library.
- The EseeCloud CodeView record gave a PDB age of 3. The candidate `cms.pdb` was approximately 9.8 MiB. Its identity remains unverified.

### Individual camera webpage evidence

- Previously supplied \`IPCamera.tar.gz\` camera-page archive contains \`IPcamera.htm\`, \`function.js\`, CSS, Flash and other resources. It remains **private** and has not been published.
- Paths in the saved camera JavaScript include \`/cgi-bin/hi3510/ptzctrl.cgi\`, \`/cgi-bin/hi3510/preset.cgi\`, \`/netsdk/video/input/channel/1/privacyMasks\`, \`/netsdk/image\`, \`/netsdk/video/encode/channel/101\`, \`/NetSDK/Video/motionDetection/channel/1\`, \`/netsdk/system/deviceinfo\`, \`/netsdk/system/time/localTime\`, \`/netsdk/sdcard/media/search\`. Methods and limitations documented in [docs/CAMERA_HTTP_API.md](docs/CAMERA_HTTP_API.md).
- Camera HTTP/SD endpoints must **not** be mistaken for the NVR's own \`R.SearchRecord\` API. Camera PTZ is not yet confirmed end to end.

## Confirmed: physical UART and U-Boot access (21 November 2026)

- **Hardware:** Installed four-pin header at NVR J18; silkscreen identifies GND, RXD, TXD, 3V3. Used a 3.3 V USB-to-UART adapter and a common ground; serial input/output was subsequently confirmed. Initial apparent lack of output came from mistakenly opening the CH341 at `/dev/ttyUSB0` rather than the connected CP2102 at `/dev/ttyUSB1`. Port numbers are not permanent identifiers.
- **Boot log captured:** U-Boot **2017.09** (13 July 2021), Linux **4.9.138** (15 June 2022 build), ARMv7 dual-core FY10D/Molchip hardware, `console=ttyS0,115200`, SquashFS read-only root on `/dev/mtdblock3`, 16 MB SPI NOR with nine MTD partitions. NVR application `./app.out` started and identified firmware as **3.2.4.0F**, built 26 August 2023. U-Boot environment `bootargs` showed `mem=118M` whereas captured kernel command line showed `mem=128M`; discrepancy remains unexplained, not a confirmed defect.
- **Interactive bootloader confirmed:** Pressing a key during startup produced `uboot#`; `?` listed commands and `printenv` returned the full environment without changes. The normal path is `sf probe`, kernel read from 0x70000, FDT read from 0x2f0000, then `bootz`. `bootdelay=0`; interruption was nevertheless achieved.
- **Recovery-related evidence:** U-Boot environment also contains `usb start` and `fatload usb 0:1 0x41000000 help.rom` in later script variables. This does **not** establish a tested recovery procedure; no recovery image was loaded.
- **Preservation:** No SPI writes, firmware flash, `saveenv`, configuration changes or permanent maintenance services performed. Header left fitted; serial adapter disconnected; enclosure reassembled and NVR returned to normal operation with cameras. Bootloader interaction does **not** yet establish interactive Linux/root access.
- **Privacy:** Do not publish unredacted serial logs: they include actual equipment IDs, internal network addresses and configuration. Keep full raw capture privately; only publish sanitised excerpts.

## Agreed application architecture (21 November 2026)

- **Independent Linux-hosted CCTV service** (prefer ordinary service management, e.g. systemd), not dependent on Home Assistant for operation; similar deployment principle to the separately maintained Traccar server.
- **One browser-based frontend** for Chrome and other modern desktop/mobile browsers: live multiview, individual camera/PTZ controls, recording search, timeline playback, exports, device and recording settings, storage/status and alerts, subject to verified NVR capabilities.
- **Server API plus Home Assistant integration**: HA receives cameras/streams, snapshots, relevant status, events/alerts and playback links/actions; the direct web interface remains the full administrative experience. Do not duplicate the NVR's PoE switching, 3 TB local recording or ten-inch display.
- **Implementation rule:** Review existing source and documented protocol tests before building. Preserve already working local HTTP/WebSocket recording search, HEVC keyframe reconstruction, and HA Generic Camera snapshots. Confirm each additional feature before claiming it implemented. Updates and changes belong in this repository, with dated status and README updates.

## Offline startup and API evidence review (21 November 2026)

- **Sources rechecked:** Existing [firmware analysis](docs/FIRMWARE_ANALYSIS.md), [NVR API evidence](docs/NVR_API.md), [camera HTTP API evidence](docs/CAMERA_HTTP_API.md) and the private Mission 12 firmware security audit. No repeat extraction, new device probing or firmware modification.
- **Startup evidence:** The extracted root filesystem's four-line `/etc/inittab` executes `/bin/sh /etc/init.d/rcS`, configures loopback and contains `::respawn:-/bin/sh`. The documented `rcS` → `S99` startup chain starts the upgrade utility, mounts the application SquashFS under `/opt` and invokes `run_app.sh`. Combined with the now-confirmed physical `ttyS0` serial console, the shell respawn line makes a serial shell plausible **without any boot or firmware changes**. Actual interactive Linux shell access is **not yet demonstrated**; do not state it as completed.
- **Local API coverage:** Verified on hardware: local HTTP/WebSocket connection, `R.SearchRecord` metadata query, HEVC keyframe reconstruction and brief playable sample; existing HA snapshot works. Found in source but not end-to-end verified: NVR/camera PTZ, other configuration endpoints, continuous stream receiver, complete recording playback/download, events and HA integration. Avoid claiming parity or implementing a parallel recording system.
- **Decision:** No reason to take the NVR off-line for serial tests now. Primary development blocker for full web playback is the unimplemented continuous KP2P receive/reassembly and time-synchronised playback, not lack of root/SSH access. Preserve the proven API work and obtain its original private implementation/capture evidence before modifying code.

## Read-only gateway (21 November 2026)

- Added [gateway.py](gateway.py) with loopback JSON endpoints for disk and camera status and paginated recording metadata. It uses the verified NVR calls documented in [NVR_API.md](docs/NVR_API.md).
- Local HTTP integration checks passed against a mock NVR, covering authenticated requests, camera ID joins, empty drive slots, recording query validation and upstream failure. Live smoke test passed from Nobara on the NVR LAN on 21 November 2026. Status returned one drive and four enabled, connected cameras reporting recording. Channel 1 recording search returned 12 rows from 63 matches, including timed and motion recordings.
- The private Operation De-Hulk capture was recovered and reconstructed byte for byte against the known-good HEVC output. It is available as an offline regression fixture for the continuous receiver.

## Offline playback receiver (22 November 2026)

- [playback.py](playback.py) assembles complete KP2P replay frames from the private capture and retains original timestamps, frame type, channel and codec.
- The HEVC output matched the nine-frame De-Hulk reference byte for byte and decoded without errors in FFmpeg. The parser also identified 22 G.711A audio frames and passed repeated-keyframe and truncation checks. The raw HEVC preview is video only.
- Next verify the same receiver with a longer, authenticated single-camera playback session over the LAN. Measure delivery cadence and seek alignment before browser integration. Browser targets include typed time selection, exact forward/back frame stepping, short jumps, and synchronised multi-camera review.

## LAN playback client (22 November 2026)

- Added [live_playback.py](live_playback.py) for bounded, authenticated single-camera replay on the NVR LAN. A mock WebSocket handshake and replay using the private capture returned all nine reference frames exactly and verified that the client sent replay STOP. A live Nobara run on the physical NVR succeeded after allowing priority transport login replies. Camera 2 returned 240 HEVC frames spanning 15.933 seconds at about 15 fps. The first and last frame were 18.506 and 2.573 seconds before the requested start respectively. This verifies retrieval. The saved clip played cleanly in FFplay at 15 fps on Nobara. A longer repeat reached the full requested interval. For a ten-second Camera 2 window, the NVR delivered 278 lead-in frames, then 150 in-range frames. The first in-range frame was 27 ms after the requested start and the client stopped on the end timestamp. The command took about 36 seconds overall. This confirms timestamp-based selection and documents the latency cost of the observed lead-in. The reason the NVR chose that starting keyframe remains unverified.

## Seekable playback container (22 November 2026)

- The raw HEVC live capture displayed grey corruption after backwards seeking in VLC and an erratic progress bar in GNOME Videos. The same live clip played and sought smoothly in VLC after remuxing to MP4 with copied HEVC and a generated 15 fps timeline. No re-encoding was needed for this test.
- Use a seekable container for delivery. The 15 fps timing was specific to the test clip. Gateway integration should derive timing from the original NVR frame timestamps and preserve decoding lead-in for accurate seeks.

- The LAN client can now package a bounded replay as HEVC MP4 using its original relative NVR frame timestamps. FFprobe verified all nine fixture timestamps and FFmpeg decoded after seeking. The client also measures time to the first in-range frame. Live MP4 output succeeded on Nobara after preserving FFmpeg’s packet time base. Camera 2 yielded 428 frames (278 lead-in, 150 in range) and three keyframes. The first in-range frame was 27 ms after the requested start and arrived 23.386 seconds after replay began. The command took 35.414 seconds overall and stopped at the end timestamp. The automatically generated MP4 loaded, played and sought without corruption in both VLC and GNOME Videos on Nobara.

- The playback client now aligns the observed 8 kHz mono G.711A audio with the HEVC timestamps and encodes audio to AAC in MP4. Offline capture tests verified both streams and unchanged video timestamps, plus video-only fallback. Live Camera 2 MP4 playback on Nobara was confirmed with audible ambient wind. A second live clip (Camera 4, 19 November 2026, 07:51:46–07:52:15 GMT) included visible activity and corresponding audio. Tim confirmed that sound matched the video by ear. The exporter received 1,175 G.711A packets and 705 HEVC frames: 270 lead-in and 435 in range. The first in-range frame was 58 ms after the requested start and arrived 23.456 seconds after replay began. Total command time was 54.892 seconds. This is a subjective sync check; exact A/V offset remains unmeasured.

## Progressive playback preparation

- The replay client exposes an iterator that yields complete timestamped frames as they arrive. It sends replay STOP on exit. A mock WebSocket replay delivered the first complete De-Hulk keyframe while the source was still connected and confirmed STOP on early exit. The MP4 exporter uses the same receive path. The loopback gateway now serves an initial Chrome player at `/playback`. It sends 720p H.264 fragmented MP4 while the receiver is active. An HTTP fixture test proved fragments reached the client before recording completion and that repeat requests released the playback lock. The initial preview is video-only, single-camera and uses a nominal 15 fps timeline. The live Chrome preview displayed Camera 2 footage on Nobara, and ±5-second jumps and the native timeline worked after the capture completed. Initial picture delay was noticeable. The precise time to first displayed frame and jumps during capture were not measured. The progressive preview now muxes timestamp-aligned G.711A as AAC alongside H.264. Offline tests verified that the first media fragment arrived before capture completion, both tracks decoded, and cameras without audio can still play through a silent track. Live Chrome audio and seek behaviour await confirmation. The preview video still uses a nominal 15 fps timeline.

- The initial automatic seek produced a visible jump in live Chrome playback. The player starts from the first buffered frame and labels the measured lead-in. Tim confirmed the updated player worked in live Chrome on Nobara.

## Replay cache (22 November 2026)

- The loopback gateway caches up to four complete browser clips in memory, up to 32 MiB each. Cache keys include camera, requested start, duration and recording type. An HTTP fixture test verified that identical requests bypass the replay source, partial captures are excluded and older entries are evicted. The first live repeat appeared to reload. The cache now admits clean captures ending within 100 ms of the requested boundary, even when the recorder sends no frame at or beyond the boundary, and logs hits, misses and admission failures. A fixture verified the near-boundary case and exclusion of an early truncation. Live Nobara retest passed: the 29-second Camera 4 request (plus lead-in) produced a 28,562,137-byte browser clip. After one miss and cache admission, six identical repeats hit the cache. Tim reported no noticeable wait. The clip exceeded the old 8 MiB limit.

## Paused frame stepping (22 November 2026)

- The Chrome player has Previous frame and Next frame controls for buffered, paused playback. They use the last presented frame timestamp and the current preview’s 15 fps frame grid. A JavaScript test verified the requested targets round-trip three frames forward and three back and that the controls respect playback state and the buffered range. Tim confirmed both paused frame controls work in live Chrome after the clip has loaded. Tim also confirmed visually that stepping back and then forward by the same number of frames returned to the starting point. His 15-step check agreed with the 15 fps preview cadence. This was a visual check, with no pixel comparison.

## Live viewer dashboard groundwork (22 November 2026)

- **Implemented (code committed, not yet visually tested in Chrome):** `/live` serves `live.html` from the existing loopback `gateway.py`; four-camera grid and single-camera selection, planned SD/HD view indicators, read-only camera connection labels sourced from `/api/status`, and 15-second status refresh while the page is visible.
- **Preserved:** The proven replay transport, `/playback`, short-jump/frame-step controls, and in-memory cache are unchanged. No camera/NVR configuration writes, audio/lighting/PTZ commands or new transport commands are made.
- **Not implemented:** Video frames are not delivered to `/live`; the page visibly says 'Live feed pending'. SD/HD controls currently select only a planned view profile, not NVR streams.
- **Deployment:** Preferred eventual host is Debian **Debdock** (i5-6500T, 8 GB RAM, Intel iHD H.264 encode/HEVC Main decode); A8 (Ryzen 7 8745HS, Radeon 780M) is fallback for heavier transcoding. Strix Halo is the development workstation, **not** the production host.
- **Verified recent replay:** A Camera 1 ten-second HD replay within the current hour succeeded with 150 in-range frames, G.711A audio and original HEVC remuxed to seekable MP4; therefore waiting for an NVR one-hour block to close is not required for that tested window. Planned rolling two-day local archive is not yet implemented.
- **Next action:** Visually verify `/live` and the status/channel mapping, then implement/test the genuine live KP2P stream-open protocol starting with Camera 1 SD. Do not misrepresent replay as real-time video.

- **Live UI sizing revision (22 November 2026):** Tim's Chrome screenshot verified all four NVR-connected indicators and the `/live` dashboard, but the original intrinsic 16:9 tile dimensions pushed the second row below the viewport. Revised `live.html` to use a viewport-height flex layout, a constrained 2×2 grid, compact headings/footers, and a collapsed implementation-note section. This change is committed but **awaits a browser recheck**. No live receiver or playback code was changed.

## Native Camera 1 SD live-preview implementation (22 November 2026)

- **Direct source evidence:** Recovered the original vendor `Netword video client.tar(1).gz` from the project archive and inspected its actual `import.js`. It explicitly defines KP2P live request command 30 / response 31, the 12-byte `channel, streamid, live_cmd` body (start 2 / stop 1), and live video frame parsing. This removes the uncertainty about the native live-stream request format; no additional protocol discovery is needed before the first hardware test.
- **Committed:** `live_stream.py` implements authenticated native stream start/stop and live frame reassembly; `live_preview.py` transcodes one camera to a 5 fps MJPEG browser preview; `gateway.py` adds a same-origin, loopback, single-viewer `/api/live` endpoint; `live.html` adds a manual **Start SD live / Stop live** control in Camera 1. Stream credentials remain only in the gateway process. No configuration writes, PTZ requests or camera audio commands.
- **Offline tests supplied, not yet run:** `tests/test_live_stream.py` exercises command encoding, a fragmented keyframe, transport length prefix and size/error boundaries using synthetic packets constructed from the vendor format. The source was reviewed, but the tests have **not** been executed in the user's local environment.
- **Hardware test outstanding:** The actual NVR Camera 1 SD live request, ack, continuous packet framing, HEVC/H.264 decoding, picture quality and resource usage still need observation in Chrome. This is an **experimental** one-camera route; four-camera streaming, HD switching and audio remain outstanding. The proven replay code, cache and `/playback` remain unchanged.
- **Next action:** Pull the latest main branch, restart the loopback gateway on port 8082, run the offline unit tests, open `/live` and press **Start SD live** on Camera 1. Record the browser result and any gateway error, then fix only what that test demonstrates.

## Camera 1 SD browser live-picture milestone (22 November 2026, 17:07 GMT)

- **Verified visually on the physical NVR in Chrome:** Tim's screenshot of `http://127.0.0.1:8082/live` at 17:07 shows a camera image with the NVR's timestamp overlay from Camera 1 and the page displaying **Stop live**, with all four camera channels reporting NVR connected. The compact four-tile layout fits on screen without scrolling. This confirms that the experimental native KP2P stream-open request, incoming frame handling, FFmpeg conversion and MJPEG browser rendering together delivered at least one actual Camera 1 SD image on the NVR LAN.
- **Verification limits:** A screenshot does not establish continuous-frame cadence, latency, audio or long-term stability. Only Camera 1 SD video has been visually confirmed. Camera 2–4, HD switching and multistream capacity remain untested, as do live timing/performance. The user's reported success is noted; don't claim sustained 5 fps was measured.
- **Preservation:** No further code changes made as part of recording this result. Playback, replay cache, single-camera frame stepping and HTTP status remain unchanged.
- **Next action:** Confirm Camera 1 continues updating over time and stops cleanly; then extend the already working live receiver to other SD channels in the same `/live` dashboard. Evaluate aspect-ratio presentation with real feeds afterwards.

## Continuous Camera 1 live video confirmed (22 November 2026)

- Tim confirmed that the Camera 1 SD browser preview displayed **a car driving by and a person walking past**. This establishes motion and continuous frame updates on the physical NVR, beyond the earlier single-image screenshot. Duration, actual effective frame cadence, latency and Stop behaviour have not been measured.
- The existing `live_preview.py` intentionally outputs MJPEG at **5 fps** (`-vf fps=5`), although the NVR's configured SD profiles are **15 fps at 800 × 448**. Tim reports movement looks very blurry/choppy at 5 fps; distinguish low frame cadence from SD resolution, JPEG compression and any true motion blur before diagnosing image quality.
- **Agreed next work:** Extend the existing native live receiver to the other three SD cameras without altering proven replay functionality, then compare preview output at **5/10/15 fps** with four simultaneous feeds. Observe CPU, memory, latency and picture quality; consider full configured SD 15 fps as the target if the host can sustain it. Individual-camera HD may be evaluated later.
- No claim is made that four feeds, higher fps or the planned deployment host have been tested.

## Four-camera SD preview extension — code ready, hardware verification pending (22 November 2026)

- **Confirmed basis:** Camera 1 SD produced continuous motion in Chrome, including a car passing and a person walking by. This existing path remains unchanged (native KP2P command 30/31, read-only stream start/stop, FFmpeg-to-MJPEG preview at 5 fps).
- **Implemented in the existing repository:** `gateway.py` now accepts `/api/live?channel=1–4&stream=1`, validates the one-based channel number, maps to a zero-based native KP2P channel and holds an independent non-blocking lock per camera (one active browser preview per channel, up to four independent camera sessions). `live.html` provides individual Start/Stop buttons and Start all SD / Stop all; all streams remain manual, and the same compact 2×2 layout is retained. No changes to `live_stream.py`, `live_preview.py` or the playback transport.
- **Not yet verified on hardware:** Cameras 2–4 actually delivering video; concurrent four-session operation; NVR capacity, CPU/memory/latency, stop/restart behaviour. The new frontend/backend have been source-reviewed but not run against the user's current workstation in this chat. No claim of four-stream success yet.
- **Agreed follow-up:** Test Cameras 2–4 SD individually, then use **Start all SD** to observe four simultaneous feeds at the existing 5 fps. If stable, compare 10 and 15 fps in a later change, measuring decoding load and visible motion. Do not change the cameras' configured recording bitrates or exposure settings based only on the night-time 5 fps preview.

## Four simultaneous SD live pictures verified (22 November 2026, 17:16 GMT)

- **Physical hardware confirmation:** Tim reported **all four cameras working** and supplied a Chrome screenshot of `http://127.0.0.1:8082/live` at approximately 17:16, visibly showing Camera 1, Camera 2, Camera 3 and Camera 4 SD pictures at once. Each tile displays `Stop live`, all four show `NVR connected`, and the 2×2 layout fits within the browser viewport. The screenshot shows on-camera time overlays close together, but **does not establish exact stream synchronisation or latency**.
- **Validated scope:** Four concurrent authenticated native KP2P camera streams can produce browser MJPEG video simultaneously on the Nobara workstation. Camera 1 was additionally verified earlier to show a moving car and a passing person. Tim confirms the four-camera setup works; continuous motion on each of Cameras 2–4, extended stability, measured effective fps, resource utilisation and clean stop/restart are not independently quantified.
- **Current preview:** `live_preview.py` outputs **5 fps per camera**, with NVR SD profiles configured for **15 fps, 800 × 448**. Night-time ghosting may result from exposure/noise reduction and is distinct from low preview frame rate. No NVR image/exposure/recording settings altered.
- **Preservation:** No application code was modified to record this successful hardware result. The verified replay player/cache and frame stepping are unchanged.
- **Next action:** Test raising the browser preview output to **10 fps**, then **15 fps**, under four-camera load, observing CPU, memory, visible motion, latency and picture quality. Keep results separate from assumptions; confirm settings only after hardware test.

## Independent 5 / 10 / 15 fps controls added for four SD previews (22 November 2026)

- **Current verified baseline preserved:** Four SD live pictures were simultaneously shown in Chrome on 22 November 2026 at the original 5 fps MJPEG preview setting, over separate authenticated KP2P live sessions. Tim confirmed all four working. The NVR SD streams remain configured for 15 fps, 800 × 448.
- **Implemented, not yet hardware-tested at new rates:** Each camera tile in `live.html` now has its own compact **5 / 10 / 15 fps** control with 5 fps selected by default. Selecting a different rate on an active preview automatically stops and reconnects that camera after a short delay, with up to four retry attempts for slow stream teardown; other live camera previews are left running. Selecting while stopped stores the desired value for that camera's next Start. No extra service or alternate architecture.
- **Gateway:** `/api/live?channel=N&stream=1&fps=F` validates one-based channel N=1–4 and F ∈ {5,10,15}; `fps` is optional for backwards-compatible 5 fps default. Existing per-camera viewer locks remain in place. `live_preview.py` passes the requested rate into FFmpeg's `fps=F` output filter; native KP2P stream rate, NVR encoding and recording settings are unchanged. No changes to proven replay or caching code.
- **Verification:** In-chat review confirms the committed browser JavaScript compiles. `tests/test_live_preview_fps.py` contains offline tests for accepted/rejected query values and the selected FFmpeg filter, but these tests **have not been executed in the user's Nobara environment**. Do not claim 10/15 fps or live switching works until checked on the NVR.
- **Next action:** Pull the latest GitHub branch and restart the same gateway (port 8082); first test a single camera at 10 and 15 fps, including switching while active; then test mixed rates and all four at 15 fps. Check CPU/memory, smoothness and live-view delay. Existing night-time exposure-related ghosting may remain at higher preview fps.

## First 15 fps preview observation and Home Assistant comparison (22 November 2026, Sunday evening)

- Tim tested the new per-camera preview rate controls after four simultaneous SD previews had worked. He is **not convinced the display is actually showing 15 distinct frames/s**, but reports very little movement around the cameras on Sunday evening, so smoothness could not be judged reliably. **Actual input/output fps remains unmeasured.** The browser FFmpeg `fps=15` filter specifies output cadence and can duplicate source frames, so its value alone cannot establish unique-frame rate.
- Tim observes the browser CCTV live view is **about two seconds behind his Home Assistant connection**. This is a relative, informal observation, not a measured end-to-end latency or a confirmed FFmpeg/browser defect. The precise HA stream path and delay measurement method have not been verified here.
- **Decision:** Preserve the verified four-camera live functionality and defer speculative buffering/codec changes. Next obtain an objective frame-count/cadence and repeatable latency comparison before optimising the live preview. Investigate FFmpeg/browser buffering only if supported by measurements.

## User screen recording review — 15 fps uncertainty (22 November 2026, 17:34 GMT)

- Tim provided `Screencast_20261122_173453.webm`, a **20.314-second, 237 × 69 px** VP9 recording cropped to a camera on-screen timestamp and a small area of the static scene. The visible camera clock advances from approximately **17:34:50 to 17:35:10** on 22 November 2026.
- Inspecting extracted frames confirmed small pixel changes in the static scene, but no clear moving object. Night-time background noise looked visually muted. The recording's nominal **60 fps screen-capture** metadata and its **681 decoded video frames** are attributes of the screencast, **not measurements of unique camera frames or MJPEG delivery cadence**.
- **Conclusion:** The user-observed lack of grain animation and uncertainty about true 15 fps are legitimate questions; this clip does **not** establish a 15 fps native frame rate or prove a fault. The ~2-second relative delay previously observed against Home Assistant remains unmeasured. No speculative buffering/codec changes justified.
- **Next diagnostic, when desired:** Measure unique frame arrival/cadence at the KP2P receiver and MJPEG output independently, alongside gateway-to-browser delay. Compare 5/10/15 fps without conflating FFmpeg's requested output cadence with unique incoming NVR frames. Existing four-camera operation and replay functionality are preserved.

## Live frame-rate instrumentation (22 November 2026)

- **Goal:** Tim requested a real FPS meter after the 20-second 237×69 WebM crop could not establish whether 15 fps browser previews were displaying 15 native frames/s; he had also observed an approximately two-second lag relative to Home Assistant. Do not infer a decoding/buffering defect from the quiet night-time footage.
- **Implemented in the existing gateway:** `LiveFpsMeter` maintains a monotonic-time five-second rolling count per camera for **source encoded video frames handed to FFmpeg** and **MJPEG JPEG images written to the HTTP browser response**. It records the requested 5/10/15 preview rate, counts total source/output frames and repeated successive NVR frame timestamps, resets on new stream/reconnect and reports inactive on stop. The read-only same-origin JSON route `/api/live/metrics` returns these per-camera measurements, without contacting the NVR again.
- **UI:** `live.html` displays `In x.x · Out y.y fps` in each camera heading, polling every two seconds while visible. A stopped camera displays `FPS —`; values start as unknown until at least one second has elapsed. Both values are server-side counts. They **do not prove visually unique frame content**, Chrome's actual image render rate, or network-to-display latency; FFmpeg's fps filter can duplicate frames.
- **Implementation scope:** Only `gateway.py`, `live_preview.py` and `live.html` were changed for instrumentation. Existing NVR KP2P frame parsing, FFmpeg encoding settings, 5/10/15 selectors, multistream start/stop, recording replay and cache remain intact. Instrumentation callback fires on successful input-pipe writes; output counter advances after successful HTTP multipart writes. `tests/test_live_fps_meter.py` added for rolling rates and lifecycle, but hardware testing and execution of the new unit tests on the user's Nobara environment are **still outstanding**. The browser JavaScript syntax was checked in the tool environment.
- **Next action:** Pull GitHub and restart the existing gateway. Start all four cameras and record the measured **In / Out** figures at selected preview rates, especially 15 fps. Measure further only if the counters show evidence of duplication, dropping or buffering.

## First measured browser live FPS readings (22 November 2026)

- Tim reports the new live FPS meter displaying **In and Out mostly 10.0 / 10.0 fps**, varying around **9.8–10.2 fps**. The selected 5/10/15 fps setting and individual camera(s) were **not specified** in that report; do not assume the selector was at 15 fps.
- Instrumentation meanings: **In** counts encoded video frames successfully written to FFmpeg's input pipe; **Out** counts JPEG images successfully written to the loopback HTTP response. Near-equal readings suggest no measurable loss between these instrumented points over the rolling window, but cannot prove 10 distinct pictures rendered by Chrome, rule out FFmpeg backpressure, or establish the NVR's intrinsic source cadence.
- **Next narrow check:** Record the selected preview rate (5, 10, or 15) for this observation. If set to 15, investigate the source/FFmpeg throughput mismatch with measured evidence before modifying working video transport. Preserve verified four-camera preview, recording playback and cache.

## Live FPS meter follow-up: startup bursts (22 November 2026)

- Tim reports trying the live preview with **1, 2, 3 and 4 cameras active**. He previously observed measured **In/Out around 9.8–10.2 fps**, usually 10.0/10.0. On changing the preview fps, **In briefly rises to approximately 20 fps for one or two seconds** and then settles. The specific selected 5/10/15 values and Out reading during the burst are not yet supplied; do not infer them.
- **Code-verified meter behaviour:** `LiveFpsMeter.begin()` resets the five-second rolling wall-clock counter for each restarted camera, with the denominator initially equal to time since that restart. The `In` counter is taken only **after** a native encoded frame was successfully written to FFmpeg's stdin, not immediately when it was produced by the camera. Early 20 fps readings could reflect queued frame delivery and/or the abbreviated measurement window; this is a hypothesis, not a verified source-rate change.
- The apparently similar sustained rate with 1–4 active streams makes an aggregate four-camera throughput collapse less likely, but does not demonstrate the NVR's true capture rate, eliminate per-stream processing limits, or measure browser latency. No native transport/decoder changes justified yet.
- **Next narrow measurement:** Using existing frame `timestamp_ms` data, compare successive distinct NVR timestamps and monotonic arrival intervals, separately from FFmpeg input write and JPEG output rates. This can identify nominal camera timestamp cadence versus delayed/bursty delivery without altering the working stream or recording playback.

## COMPLETED — REMAINING — NEXT ACTION

**COMPLETED:** Original discovery and HTTP snapshot path; local NVR HTTP/WebSocket/recording-search tests; playable HEVC sample reconstruction; firmware XOR decoding/extraction; static cloud, startup, hidden maintenance and LUI audits; **physical UART boot capture and interactive U-Boot access**; NVR restored to operation; independent-server/browser/HA project architecture agreed.

**REMAINING:** Verify **interactive Linux shell** and runtime mounts when hardware access is next needed; establish on-demand SSH/Telnet only if safe without persistent changes; observe external cloud egress passively; develop continuous local stream receiver, full playback/download, complete browser interface and HA integration. Optional future task: identify feasible LUI/HDMI customisation.

**NEXT ACTION:** Run the new FPS-meter offline test and verify per-camera In (native video frame input) and Out (JPEG images sent) counters against the real four-camera NVR setup at 5, 10 and 15 fps. Compare actual values before changing pipeline buffering or codec settings; preserve the working recording playback and replay cache.

## Documentation and security rules

- [Firmware extraction and maintenance evidence](docs/FIRMWARE_ANALYSIS.md)
- [Local NVR recordings and KP2P protocol](docs/NVR_API.md)
- [Individual camera HTTP interface](docs/CAMERA_HTTP_API.md)
- [Offline sample extraction tool](tools/extract_firmware.py)

Original vendor firmware, extracted binaries, private reports/evidence bundles, authenticated links, internal addresses, unredacted network logs and footage remain outside the public repository. Findings clearly distinguish **observed on physical hardware**, **confirmed offline from firmware**, and **not yet tested**.
