# Hiseeu/Molchip NVR firmware: offline inspection and extraction

**Evidence status:** Reproduced on the D8208-5 firmware described below; not a universal Hiseeu firmware format. **Do not flash, modify or execute extracted binaries on an NVR.**

## Safety and compatibility

The vendor asks for both model and equipment sequence number because even units with the same model label may contain different internal hardware. Firmware for another unit can make a recorder unbootable. This document is for **offline inspection of firmware you are authorised to analyse**; it is **not** an upgrade, repair, rollback or guaranteed recovery procedure. Maintain an unchanged original and compare its SHA-256 before proceeding. No firmware image or vendor binaries are distributed in this repository.

Analysis scripts should be used on a trusted Linux workstation. The procedure below extracts data only; it never writes to an NVR. Treat extracted files as untrusted.

## Proven sample

- Model: D8208-5; firmware version 3.2.4.0; firmware build date 26 August 2023.
- File: \`FWHI10E_20230826_NVR_D8208-5_3_2_4_0_0x6810E105_RELEASE.rom\`
- Length: **14,124,060 bytes**
- SHA-256: \`77647dd058dea55ed1c6dd54c0ab3496d6afdd3392a1afba8f9ee57be4fffb5a\`
- Container: proprietary header and **five** embedded sections; repeating 64-byte XOR obfuscation rather than cryptographic encryption.
- Decoding key: bytes \`0x54000\`–\`0x5403f\` of this **specific** ROM, repeated from the beginning of the file. The key is derived from a region observed to represent zero padding in the decoded image; **do not assume the same location/key works on other firmware**.
- Decoded header starts \`69 ae 10 7c 05 e1 10 68\` (embedded identifier \`0x6810E105\`, little-endian).
- Regions identified offline:

| Offset (decoded ROM) | Format | Observed length |
| --- | --- | ---: |
| \`0x528c0\` | Flattened device tree (FDT) | 1,879 bytes |
| \`0x667bb\` | XZ-compressed stream (kernel candidate) | 2,527,788 bytes |
| \`0x2cfa27\` | FDT | 18,933 bytes |
| \`0x2d441c\` | SquashFS 4.x, XZ-compressed (root filesystem) | 889,348 bytes |
| \`0x3ae41c\` | SquashFS 4.x, XZ-compressed (application filesystem) | 10,262,288 bytes |

Mission 11's tool-assisted extraction recovered 544 files (~52 MB). The reference executable is ARM32 little-endian \`app.out\`, linked for uClibc (\`/lib/ld-uClibc.so.0\`); platform is Molchip MC6810E. This is evidence from **one** firmware build only.

## Offline extraction procedure (Nobara/Fedora/Linux)

Install \`squashfs-tools\` using your distribution's package manager if not already installed. Python 3 uses only the standard library.

The companion script [\`tools/extract_firmware.py\`](../tools/extract_firmware.py) verifies the *reference* ROM's SHA-256 by default and refuses unrelated images. It writes a decoded **copy**, carves the two checked SquashFS images and optionally extracts them using \`unsquashfs\`. It does not need root privileges.

\`\`\`bash
python3 tools/extract_firmware.py \
  "/path/to/FWHI10E_20230826_NVR_D8208-5_3_2_4_0_0x6810E105_RELEASE.rom" \
  --output "./firmware-work"
\`\`\`

The output includes \`firmware.decoded.bin\`, \`rootfs.squashfs\`, \`application.squashfs\`, \`rootfs/\`, \`application/\` and a manifest. The extracted main application is normally \`application/app/app.out\`.

Use \`--carve-only\` to create the decoded copy and the images without calling \`unsquashfs\`.

**Other firmware:** This utility intentionally **does not offer a force/skip-hash mode**. Different hardware revisions may use different containers, section layouts, and even different XOR keys. Analyse them separately before adapting the method; never apply these sample offsets blindly.

## Further findings (static analysis; hardware testing pending)

- Root filesystem uses BusyBox and uClibc; presence of the word 'Debian' in the ELF compiler comment is **not** evidence that Debian/APT is installed.
- Startup references \`ttyS0,115200\`, and \`/etc/inittab\` contains a shell respawn entry. **A usable root shell over a physically connected serial adapter is indicated by firmware, not yet proven on this NVR.** Determine voltage, ground and pinout before attaching anything; use receive-only wiring initially and **never** connect adapter power.
- Telnet utilities \`telnet\` and \`telnetd\` are present, but port 23 was **connection refused** in live tests. Telnet is **not normally enabled** in the observed configuration.
- Mission 13 statically traced \`NK_CMDLINE_todo\` (\`0x10fc6c\`) reading a \`/tmp/in\` command path (reader \`0x137f7c\`); \`dbgmode 1\`/\`dbgmode 0\` control a Telnet-related flag \`$.Stat.Proc.IsOpen\` and launch/stop \`telnetd\`. A separate maintenance function \`NK_UpdateMaintenanceInfo\` (\`0x1386c0\`) also controls this state. **Do not assume a live shell command interface or \`/tmp/in\` FIFO exists until checked on hardware.**
- Startup tests for \`/tmp/debug\`, \`/config/test\` and \`/cf/test\`. Those paths are **not interchangeable**: \`/config\` and \`/cf\` may persist across reboot. Do not create persistent debug markers when the goal is temporary access.
- LUI is text-based GUI configuration loaded under \`/opt/app\` through \`n9204_janewui1.conf\`; its keys dispatch to registered internal JSON-API handlers. \`contractor_mode.lui\` and engineer-related handlers exist. A resource-only Telnet/SSH button is **not verified**.
- SSH/Dropbear is **not present in the extracted firmware**. Later experimentation may explore a manually launched compatible ARM32 Dropbear server from a serial shell, without replacing the OS or changing startup scripts.
- No safe flash recovery or proven bootloader rollback has been established.

## Reference evidence

- Mission 11: original firmware format analysis, recovered offsets and extracted file inventory.
- Mission 12: cloud endpoints, startup sequence, firmware upgrade checks and security audit.
- Mission 13: Telnet call chains, local command processor, engineering UI and LUI dispatch analysis.

These reports/evidence bundles remain stored privately. The repository records their conclusions without distributing vendor firmware or potentially sensitive raw captures.
