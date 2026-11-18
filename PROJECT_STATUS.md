# Hiseeu CCTV — PROJECT_STATUS

**Updated:** 18 November 2026  
**Repository:** Inforce855/CCTV  
**Status:** Offline firmware investigations and local NVR recording search are completed; reliable continuous playback and temporary serial/SSH access remain outstanding.

> **Privacy:** IP addresses below are illustrative, **not** the actual addresses of the investigated equipment. NVR: \`192.168.1.100\`; cameras: \`192.168.1.101\`–\`192.168.1.104\`. Never publish actual internal addresses, credentials, authenticated URLs, camera footage, or unsanitised captures.

## Objective

Develop a Linux-native/browser-based and Home Assistant-compatible solution for Hiseeu D8208-5 NVR live camera viewing, PTZ, configuration and NVR recording search/playback/download, without relying on EseeCloud under Wine, obsolete Flash or Windows ActiveX. Preserve the working Home Assistant Generic Camera snapshot functionality and original NVR configuration.

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
- Init scripts, device-tree boot args and \`/etc/inittab\` indicate a possible **root shell via \`ttyS0\` at 115200 baud**, but physical header pinout/voltage and interactive access are **not yet tested**.
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

## COMPLETED — REMAINING — NEXT ACTION

**COMPLETED:** Original discovery and HTTP snapshot path; local NVR HTTP/WebSocket/recording-search tests; playable HEVC sample reconstruction; firmware XOR decoding/extraction; static cloud, startup, hidden maintenance and LUI audits; public documentation and sample extractor.

**REMAINING:** Verify serial console and runtime mounts; establish on-demand SSH/Telnet without persistent changes; observe external cloud egress passively; develop continuous local stream receiver, full playback/download and Home Assistant/browser interface. Optional future task: identify feasible LUI/HDMI customisation.

**NEXT ACTION:** When physically at the NVR, identify the serial header and logic levels, connect **GND + receive-only** initially, capture \`ttyS0\` boot messages at **115200 baud**, and establish whether the indicated root console is usable. Then examine current mounts and run only reversible, deliberately started maintenance experiments. **No firmware flashing, no remote VPN/router changes, no automatic SSH/Telnet startup.**

## Documentation and security rules

- [Firmware extraction and maintenance evidence](docs/FIRMWARE_ANALYSIS.md)
- [Local NVR recordings and KP2P protocol](docs/NVR_API.md)
- [Individual camera HTTP interface](docs/CAMERA_HTTP_API.md)
- [Offline sample extraction tool](tools/extract_firmware.py)

Original vendor firmware, extracted binaries, private reports/evidence bundles, authenticated links, internal addresses, unredacted network logs and footage remain outside the public repository. Findings clearly distinguish **observed on physical hardware**, **confirmed offline from firmware**, and **not yet tested**.
