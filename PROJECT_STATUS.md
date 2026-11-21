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
- Local HTTP integration checks passed against a mock NVR, covering authenticated requests, camera ID joins, empty drive slots, recording query validation and upstream failure. A live gateway run still requires a host on the NVR LAN.
- The private Operation De-Hulk capture was recovered and reconstructed byte for byte against the known-good HEVC output. It is available as an offline regression fixture for the continuous receiver.

## COMPLETED — REMAINING — NEXT ACTION

**COMPLETED:** Original discovery and HTTP snapshot path; local NVR HTTP/WebSocket/recording-search tests; playable HEVC sample reconstruction; firmware XOR decoding/extraction; static cloud, startup, hidden maintenance and LUI audits; **physical UART boot capture and interactive U-Boot access**; NVR restored to operation; independent-server/browser/HA project architecture agreed.

**REMAINING:** Verify **interactive Linux shell** and runtime mounts when hardware access is next needed; establish on-demand SSH/Telnet only if safe without persistent changes; observe external cloud egress passively; develop continuous local stream receiver, full playback/download, complete browser interface and HA integration. Optional future task: identify feasible LUI/HDMI customisation.

**NEXT ACTION:** Smoke-test the gateway endpoints from the NVR LAN, then build the continuous KP2P recording receiver using the private Operation De-Hulk fixture. Verify frame assembly and timestamp handling before integrating playback.

## Documentation and security rules

- [Firmware extraction and maintenance evidence](docs/FIRMWARE_ANALYSIS.md)
- [Local NVR recordings and KP2P protocol](docs/NVR_API.md)
- [Individual camera HTTP interface](docs/CAMERA_HTTP_API.md)
- [Offline sample extraction tool](tools/extract_firmware.py)

Original vendor firmware, extracted binaries, private reports/evidence bundles, authenticated links, internal addresses, unredacted network logs and footage remain outside the public repository. Findings clearly distinguish **observed on physical hardware**, **confirmed offline from firmware**, and **not yet tested**.
