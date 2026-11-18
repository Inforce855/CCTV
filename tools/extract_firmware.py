#!/usr/bin/env python3
"""Extract the verified Hiseeu D8208-5 26-08-2023 ROM offline.

Read-only on the input file. Output is written only to a new directory.
Never flash firmware or execute extracted binaries.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import subprocess
import sys
from pathlib import Path

EXPECTED_SHA256 = "77647dd058dea55ed1c6dd54c0ab3496d6afdd3392a1afba8f9ee57be4fffb5a"
EXPECTED_SIZE = 14_124_060
KEY_OFFSET = 0x54000
KEY_SIZE = 64
EXPECTED_HEADER = bytes.fromhex("69ae107c05e11068")
IMAGES = (
    ("rootfs", 0x2D441C, 889_348),
    ("application", 0x3AE41C, 10_262_288),
)


def extract(source: Path, output: Path, carve_only: bool) -> None:
    if not source.is_file():
        raise ValueError(f"Source does not exist or is not a file: {source}")

    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if len(raw) != EXPECTED_SIZE or digest != EXPECTED_SHA256:
        raise ValueError(
            "Unsupported firmware image: file size or SHA-256 differs from the "
            "known reference. Refusing to apply model-specific offsets."
        )

    key = raw[KEY_OFFSET:KEY_OFFSET + KEY_SIZE]
    if len(key) != KEY_SIZE or raw[0x62000:0x62000 + KEY_SIZE] != key:
        raise ValueError("Reference XOR key/padding check failed")

    decoded = bytes(value ^ key[index % KEY_SIZE] for index, value in enumerate(raw))
    if not decoded.startswith(EXPECTED_HEADER):
        raise ValueError("Decoded firmware header validation failed")

    images = []
    for name, offset, expected_length in IMAGES:
        if decoded[offset:offset + 4] != b"hsqs":
            raise ValueError(f"{name}: invalid SquashFS signature")
        length = struct.unpack_from("<Q", decoded, offset + 40)[0]
        if length != expected_length or offset + length > len(decoded):
            raise ValueError(f"{name}: SquashFS length mismatch")
        images.append((name, decoded[offset:offset + length]))

    # Do not overwrite prior outputs or write into the original ROM's location.
    if output.exists():
        raise FileExistsError(f"Output path already exists: {output}")
    if output.resolve() == source.resolve() or source.resolve().is_relative_to(output.resolve()):
        raise ValueError("Output must not be an ancestor of the source ROM")
    if not carve_only and shutil.which("unsquashfs") is None:
        raise RuntimeError("unsquashfs not found: install squashfs-tools or use --carve-only")

    output.mkdir(parents=True)
    (output / "firmware.decoded.bin").write_bytes(decoded)

    for name, data in images:
        image_path = output / f"{name}.squashfs"
        image_path.write_bytes(data)
        if not carve_only:
            subprocess.run(
                ["unsquashfs", "-no-progress", "-d", str(output / name), str(image_path)],
                check=True,
            )

    manifest = {
        "input_filename": source.name,
        "input_size": len(raw),
        "input_sha256": digest,
        "decoded_sha256": hashlib.sha256(decoded).hexdigest(),
        "xor_key_offset": hex(KEY_OFFSET),
        "xor_key_length": KEY_SIZE,
        "images": [
            {"name": name, "offset": hex(offset), "length": size}
            for (name, offset, size) in IMAGES
        ],
        "extracted_filesystems": not carve_only,
        "warning": "Offline extraction only. No firmware flashing or runtime compatibility claim.",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Validated source SHA-256: {digest}")
    print(f"Output written to: {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path, help="Path to original vendor ROM")
    parser.add_argument("--output", required=True, type=Path, help="New output directory")
    parser.add_argument("--carve-only", action="store_true",
                        help="Decode and carve SquashFS images without unsquashfs")
    args = parser.parse_args()
    try:
        extract(args.rom.expanduser().resolve(), args.output.expanduser().resolve(), args.carve_only)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
