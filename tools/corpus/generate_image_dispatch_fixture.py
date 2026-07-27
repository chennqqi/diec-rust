#!/usr/bin/env python3
"""Generate benign image variants for the pinned engine dispatch oracle."""

from __future__ import annotations

import argparse
from collections.abc import Callable
import hashlib
import json
from pathlib import Path
import struct
import sys


def make_bmp() -> bytes:
    pixel_data = b"\x00\x00\xff\x00"
    file_size = 14 + 40 + len(pixel_data)
    return (
        b"BM"
        + struct.pack("<IHHI", file_size, 0, 0, 54)
        + struct.pack(
            "<IiiHHIIiiII",
            40,
            1,
            1,
            1,
            24,
            0,
            len(pixel_data),
            2835,
            2835,
            0,
            0,
        )
        + pixel_data
    )


def make_gif() -> bytes:
    # The pinned XGif validator requires size > 0x320 before checking GIF89a.
    image = bytearray(b"\xff" * 0x322)
    image[0:6] = b"GIF89a"
    image[6:13] = struct.pack("<HHBBB", 1, 1, 0, 0, 0)
    image[0x320] = 0
    image[0x321] = 0x3B
    return bytes(image)


def make_tiff() -> bytes:
    # Little-endian TIFF with one empty IFD and no successor.
    return b"II\x2a\x00" + struct.pack("<IHI", 8, 0, 0)


def make_icon(icon_type: int) -> bytes:
    if icon_type not in (1, 2):
        raise ValueError("icon type must be ICO (1) or CUR (2)")
    directory = struct.pack("<HHH", 0, icon_type, 1)
    entry = struct.pack(
        "<BBBBHHII",
        1,
        1,
        0,
        0,
        1 if icon_type == 1 else 0,
        32 if icon_type == 1 else 0,
        1,
        len(directory) + 16,
    )
    return directory + entry + b"\0"


def make_icc() -> bytes:
    profile = bytearray(128)
    struct.pack_into(">I", profile, 0, len(profile))
    profile[12:16] = b"mntr"
    profile[36:40] = b"acsp"
    return bytes(profile)


def make_webp() -> bytes:
    payload = b"\0" * 16
    body = b"WEBP" + b"VP8 " + struct.pack("<I", len(payload)) + payload
    return b"RIFF" + struct.pack("<I", len(body)) + body


GENERATORS: tuple[
    tuple[str, str, Callable[[], bytes]],
    ...,
] = (
    ("pixel.bmp", "BMP", make_bmp),
    ("pixel.gif", "GIF", make_gif),
    ("pixel.tiff", "TIFF", make_tiff),
    ("pixel.ico", "ICO", lambda: make_icon(1)),
    ("pointer.cur", "CUR", lambda: make_icon(2)),
    ("display.icc", "ICC", make_icc),
    ("pixel.webp", "WebP", make_webp),
)


def generate(output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    samples = []
    for name, specific_filetype, factory in GENERATORS:
        data = factory()
        (output_dir / name).write_bytes(data)
        samples.append(
            {
                "name": name,
                "specific_filetype": specific_filetype,
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    manifest: dict[str, object] = {
        "schema_version": 1,
        "generator": (
            "tools/corpus/generate_image_dispatch_fixture.py"
        ),
        "license": "project-generated; no third-party sample bytes",
        "capability": "CAP-DISPATCH-007",
        "coverage_gap": "CAP-GAP-012",
        "samples": samples,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = generate(args.output_dir.resolve())
    json.dump(
        manifest,
        sys.stdout,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    )
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
