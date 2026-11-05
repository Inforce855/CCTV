# Hiseeu CCTV — investigation status (5 November 2026)

## Objective
Develop a Linux-native / browser or Home Assistant solution for camera live viewing, PTZ, configuration, and NVR recording search/playback/download, avoiding dependency on EseeCloud under Wine or obsolete Flash/ActiveX. Preserve existing working Home Assistant Generic Camera functionality and NVR configuration.

## Equipment and verified environment
- NVR: Hiseeu D8208-5, firmware 3.2.4.0, LAN address **10.85.0.40** (observed in Chrome browser management screenshot).
- Four PoE PTZ cameras: **5522-F-Q**, addresses **10.85.0.41–10.85.0.44** (observed in NVR management screenshot). NVR listed communication protocol **N1**, port **80**, all four connected.
- Camera 10.85.0.41: Home Assistant Generic Camera successfully retrieves images at `/snapshot.jpg` using an `auth` query parameter. **Do not commit the actual URL with a credential**.
- The NVR web interface `http://10.85.0.40/#/manage` renders in Linux Chrome, including Preview / Playback / Settings / Management navigation, but video requires obsolete Windows ActiveX. Browser inspection showed a download for `WebClient.exe` and a `client_ocx` object (CLSID `69AF533A-A219-452D-89B1-16A9E65D6AAA`).
- Individual cameras also serve an old browser interface using Flash (`JaViewer.swf`). Snapshot access is independently working. Camera control from HA, NVR recorded playback and direct live streaming have **not yet been verified**.

## Windows artefacts examined (read-only)
### EseeCloud
- Existing installation under Wine, and scaling within the window reportedly worked previously but later regressed following Wine updates. Root cause **not established**.
- `EseeCloud.exe` approximately 2.6 MiB, surrounded by networking and video DLLs: `libcef.dll` (~47.5 MiB), FFmpeg libraries, `IOTLink.dll`, `P2PSDKClient.dll`, `libonvifc.dll`, etc.
- `objdump -x EseeCloud.exe` showed CodeView RSDS debug reference `D:\\jvanProj\\gles_cms_local\\gles_cms\\build\\win32\\depends\\output_new\\cms.pdb`, GUID `568b336492c04e5aa99959fa142ab374`, age 3. A `cms.pdb` is present in the install directory (~9.8 MiB), but GUID/age **not yet checked against the file**.

### WebClient.exe from NVR
- Downloaded to `~/Downloads/WebClient.exe`; `7z l` identified 32-bit NSIS installer v1.3.0.2, 610,224 bytes, containing 18 files (~1.9 MB unpacked), dated 2017–2018.
- Extracted **without executing** to `~/Downloads/WebClient-inspect/`. Important components:
  - `WebCtrlLite.ocx` (125,080 B): live-channel ActiveX.
  - `playbackwnd.ocx` (96,296 B): recorded-video playback ActiveX.
  - `HiSiClientSdk.dll`, `iotlink.dll`, `NetSdk.dll`, `P2PSDKClient.dll`, `HW_H265dec_Win32D.dll`, `hi_h264dec_w.dll`, `arq.dll`.
  - `inst.bat`, `unst.bat`, `WebCtrlLiteSettings.ini`, `playbackwndmsg.ini`.
- Both OCXs are 32-bit PE COM objects exporting `DllGetClassObject`, `DllRegisterServer`, `DllUnregisterServer`.
- `objdump -x` confirmed embedded `TYPELIB` resources in both OCXs; `winedump dump -j resource` successfully decoded them. Local output files: `WebCtrlLite-resources.txt` and `playbackwnd-resources.txt`.

## COM methods recovered from embedded type libraries
`WebCtrlLite.ocx` includes `CheckConnect`, `OpenChannel`, `OpenChannelEx`, `CloseChannel`, `CloseChannelEx`, `OpenAll`, `CloseAll`, `OpenStream`, `CloseStream`, `SetDispWndDivMode`, `CaptureChlImage`, `getCurChannelBitrate`, `GetChannelStatus`, etc. Binary strings also contain `SetCtlPtz`, but that symbol is **not confirmed as a COM-dispatch method**.

`playbackwnd.ocx` type-library name table includes `ConnectRecServer`, `StartReplay`, `StartReplayEx`, `RecPlay`, `RecPause`, `RecStop`, `RecByFrame`, `GetPlayStatus`, `GetConnectStatus`, `RecFast`, `RecSlow`, `RecGetCurrentTimet`, `ConnectAndLogin`. Binary strings contain `PLAYBACKWND_KP2P.PlaybackwndCtrl.1`; internal messages mention KP2P. This **suggests** a proprietary protocol but does not prove the network packet structure.

First playback TypeInfo 0 function records, *provisionally aligned to name-table order*:
- `ConnectRecServer(BSTR address, int32 port) -> int32`
- `StartReplay(int32 channels, int32 types, int32 start, int32 end, int32 cleanBuffer) -> void`
- Subsequent playback actions use no parameters; confirmed types include `VT_VOID`, `VT_I4`, `VT_BOOL`. Mapping each to method name still requires verifying name/dispatch-ID associations. The encoding of `start` and `end` is unknown.

## Saved camera webpage archive
User provided `IPCamera.tar.gz` (~302 KB; 30 tar entries), a saved camera web page containing `IPCamera/IPcamera.htm`, `IPCamera/IPcamera_files/function.js`, other JS/CSS, and Flash files. The archive remains in the conversation attachment and user's copy, **not yet committed to GitHub**.
Earlier inspection of `function.js` identified these API paths in the saved JavaScript (existence in code is confirmed; successful calls on this specific firmware are **not yet verified**):
- PTZ: `/cgi-bin/hi3510/ptzctrl.cgi`
- Presets: `/cgi-bin/hi3510/preset.cgi`
- Privacy masks: `/netsdk/video/input/channel/1/privacyMasks`
- Image: `/netsdk/image`
- Video encoding: `/netsdk/video/encode/channel/101`
- Motion detection: `/NetSDK/Video/motionDetection/channel/1`
- Device info: `/netsdk/system/deviceinfo`
- Time: `/netsdk/system/time/localTime`
- SD media search: `/netsdk/sdcard/media/search`

**Security:** Before publishing any saved web-page file or scripts to this public repository, inspect for authentication tokens, passwords, cookies, private URLs, and other personal data. Never publish camera credentials or raw camera footage.

## Completed — Remaining — Next action
**COMPLETED:** Located working camera snapshot endpoint and NVR browser management UI; identified obsolete ActiveX and Flash dependencies; extracted WebClient installer; recovered COM method names and preliminary playback signatures; found HTTP camera API paths in saved JavaScript.

**REMAINING:** Verify real camera API responses safely, establish native live stream and PTZ support, understand NVR recording search/download/network API, choose whether browser UI or HA integration best serves the full objective. Confirm PDB match only if reverse-engineering EseeCloud becomes necessary.

**NEXT ACTION:** Preserve/sanitise the saved camera-page archive, then test a read-only camera HTTP endpoint using existing credentials without exposing them in GitHub or logs. Do not modify NVR settings or assume protocol compatibility from names alone.

## Notes
Avoid constructing a parallel implementation before evaluating existing HTTP endpoints. Use local network and existing facilities where possible. No application code, camera/NVR configuration, or Wine installation was modified as part of these investigations.
