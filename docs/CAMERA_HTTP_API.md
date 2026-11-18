# Camera web interface — HTTP API evidence

**Source:** user-supplied saved camera web page `IPCamera.tar.gz`, captured from a Hiseeu 5522-F-Q camera. Inspected on 5 November 2026. Original archive has **not been published**. These notes describe observed behaviour without reproducing the manufacturer's full source code.

## Camera-specific local HTTP APIs observed in `IPcamera_files/function.js`

| Operation | HTTP method | Relative endpoint | Evidence |
|---|---|---|---|
| PTZ action | PUT | `/cgi-bin/hi3510/ptzctrl.cgi` | Query parameters `-step`, `-act`, `-speed`, `-presetNUM` |
| PTZ preset | PUT | `/cgi-bin/hi3510/preset.cgi` | Query parameters `-status`, `-act`, `-number` |
| Device information | GET | `/netsdk/system/deviceinfo` | JSON response handling |
| Privacy masks | GET | `/netsdk/video/input/channel/1/privacyMasks` | JSON response handling |
| Camera SD-card recording search | GET | `/netsdk/sdcard/media/search` | Query parameters `beginUTC`, `endUTC` generated from time selection |

Other observed endpoint paths: `/netsdk/image`, `/netsdk/video/encode/channel/101`, `/NetSDK/Video/motionDetection/channel/1`, `/netsdk/system/time/localTime`. The precise operations and response formats of these require separate verification.

## Authentication behaviour

- The saved JavaScript builds an HTTP Basic Authorization header from runtime variables representing the username and password; its example comment refers to an empty password, but **does not establish that the actual device password is blank**.
- The saved HTML includes links to a local private camera IP address. These addresses are device-specific and are intentionally omitted from this API reference.
- The live preview embeds obsolete Flash `JaViewer.swf`; snapshot URLs are generated dynamically and can embed authentication data in query parameters.
- **Never commit populated snapshot URLs, real credentials, cookies, authentication headers, session tokens, downloaded video, or unsanitised saved browser pages.**
- Use read-only requests as the initial tests; avoid PTZ movement or PUT configuration actions until authorised and verified.

## Protocol boundaries and limitations

The methods above originate from the **camera's** web UI, not the D8208-5 NVR's browser interface. The camera's `/netsdk/sdcard/media/search` is not evidence of NVR recording search support. Camera PTZ and preset methods are visible in the source but **not yet validated against live hardware**.

The NVR's proprietary ActiveX playback interfaces are documented separately in [PROJECT_STATUS.md](PROJECT_STATUS.md), along with the extracted 2018 WebClient COM library names.

## Follow-up

1. Safely confirm the result and required credentials for the camera's read-only `/netsdk/system/deviceinfo` endpoint without printing secrets.
2. Determine whether RTSP or ONVIF works for native live viewing and PTZ, before reimplementing any video protocol.
3. Investigate NVR recording playback separately only after verifying available interfaces.

Original manufacturer-supplied scripts, media and plugin binaries remain in the private uploaded archive, not distributed by this repository. Their licence and redistribution permissions have not been established.
