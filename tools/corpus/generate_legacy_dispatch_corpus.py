#!/usr/bin/env python3
"""Generate deterministic Amiga Hunk and Atari ST dispatch fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import struct
import sys
from collections.abc import Callable
from typing import Any


FORMATS_REPOSITORY = "https://github.com/horsicq/Formats.git"
FORMATS_COMMIT = "1151e7254fdee3c0294ff7095edbdd7bfccf8201"
TARGET_FILETYPES = ("Amiga Hunk", "Atari ST")


def make_amiga_hunk() -> bytes:
    """Return the benign HUNK_HEADER image used by the memory-map oracle."""
    words = (
        0x000003F3,  # HUNK_HEADER
        0,
        1,
        0,
        0,
        4,
        0x000003E9,  # HUNK_CODE
        4,
        0xAA000400,
        0x00BB0000,
        0,
        0,
        0x000003F2,  # HUNK_END
    )
    return b"".join(struct.pack(">I", word) for word in words)


def make_atari_st() -> bytes:
    """Return the smallest Atari ST image accepted by the pinned Linux ABI."""
    wire_header = struct.pack(
        ">HIIIIIIH",
        0x601A,
        0,  # text
        0,  # data
        0,  # bss
        0,  # symbols
        0,  # reserved
        0,  # flags
        1,  # absolute image; no relocation table
    )
    # XAtariST::isValid compares the input size with sizeof(HEADER).
    # The declared fields occupy 28 bytes, but the pinned Linux C++ ABI adds
    # four bytes of trailing struct padding and therefore requires 32 bytes.
    return wire_header + b"\x00" * 4


def _amiga_truncated() -> bytes:
    return make_amiga_hunk()[:8]


def _amiga_wrong_endian() -> bytes:
    data = bytearray(make_amiga_hunk())
    data[:4] = data[:4][::-1]
    return bytes(data)


def _amiga_near_magic() -> bytes:
    data = bytearray(make_amiga_hunk())
    data[:4] = struct.pack(">I", 0x000003F4)
    return bytes(data)


def _atari_truncated() -> bytes:
    return make_atari_st()[:31]


def _atari_wrong_endian() -> bytes:
    data = bytearray(make_atari_st())
    data[:2] = data[:2][::-1]
    return bytes(data)


def _atari_near_magic() -> bytes:
    data = bytearray(make_atari_st())
    data[:2] = struct.pack(">H", 0x601B)
    return bytes(data)


GENERATORS: tuple[
    tuple[str, str, str, Callable[[], bytes]],
    ...,
] = (
    (
        "minimal-amiga-hunk.bin",
        "positive",
        "Amiga Hunk",
        make_amiga_hunk,
    ),
    (
        "amiga-hunk-truncated.bin",
        "truncated",
        "Amiga Hunk",
        _amiga_truncated,
    ),
    (
        "amiga-hunk-wrong-endian.bin",
        "wrong_endian",
        "Amiga Hunk",
        _amiga_wrong_endian,
    ),
    (
        "amiga-hunk-near-magic.bin",
        "near_magic",
        "Amiga Hunk",
        _amiga_near_magic,
    ),
    (
        "minimal-atari-st.prg",
        "positive",
        "Atari ST",
        make_atari_st,
    ),
    (
        "atari-st-truncated.prg",
        "truncated",
        "Atari ST",
        _atari_truncated,
    ),
    (
        "atari-st-wrong-endian.prg",
        "wrong_endian",
        "Atari ST",
        _atari_wrong_endian,
    ),
    (
        "atari-st-near-magic.prg",
        "near_magic",
        "Atari ST",
        _atari_near_magic,
    ),
)


def _expectations(case_kind: str, target: str) -> dict[str, object]:
    if case_kind == "positive":
        scanner_present = [target] if target == "Amiga Hunk" else []
        return {
            "present_filetypes": scanner_present,
            "absent_filetypes": [
                item
                for item in TARGET_FILETYPES
                if item not in scanner_present
            ],
            "info_filetype": target,
        }
    return {
        "present_filetypes": [],
        "absent_filetypes": list(TARGET_FILETYPES),
        "info_filetype": "Binary",
    }


def generate(output_dir: pathlib.Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    samples = []
    for name, case_kind, target, factory in GENERATORS:
        data = factory()
        (output_dir / name).write_bytes(data)
        samples.append(
            {
                "name": name,
                "case_kind": case_kind,
                "target_filetype": target,
                "expected_dispatch": _expectations(case_kind, target),
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "generator": (
            "tools/corpus/generate_legacy_dispatch_corpus.py"
        ),
        "license": "project-generated; no third-party sample bytes",
        "capability": "CAP-DISPATCH-003",
        "source_identity": {
            "repository": FORMATS_REPOSITORY,
            "commit": FORMATS_COMMIT,
            "validity_sources": [
                "exec/xamigahunk.cpp",
                "exec/xamigahunk_def.h",
                "exec/xatarist.cpp",
                "exec/xatarist_def.h",
                "xformats.cpp",
            ],
        },
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=pathlib.Path)
    args = parser.parse_args()
    manifest = generate(args.output_dir.resolve())
    json.dump(
        manifest,
        fp=sys.stdout,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    )
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
