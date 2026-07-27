#!/usr/bin/env python3
"""Generate project-owned Mach-O64 inputs for a fixed-rule oracle."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


SCHEMA_VERSION = 1
GENERATOR_VERSION = 1
UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
FORMATS_COMMIT = "1151e7254fdee3c0294ff7095edbdd7bfccf8201"
XSCANENGINE_COMMIT = "dfe4a419e4f491bb23688ba03c5a5bf39e34da83"
RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
RULE_PATH = "MACH/compiler_Rust.4.sg"
RULE_SHA256 = "70fec4e86cd1a1a5b3e7663521cb45e3c4ce85d1e1f8ed80cf1d80f6d8268d84"
X86_64_CPU = 0x01000007
ARM64_CPU = 0x0100000C
X86_64_EP = bytes.fromhex(
    "554889e5415741564154534883ec2031ffbe1122334431c0e8aabbccdd83f8"
)
ARM64_EP = bytes.fromhex("ff8300d1fd7b01a9fd430091e30301aa027c4093")


def mapped_macho64(cpu_type: int, entry_point: bytes, size: int = 0x200) -> bytes:
    if size < 0x80:
        raise ValueError("fixture must retain the Mach-O64 header and commands")
    image = bytearray(0x200)
    image[:32] = struct.pack(
        "<IiiIIIII",
        0xFEEDFACF,
        cpu_type,
        3 if cpu_type == X86_64_CPU else 0,
        2,
        2,
        96,
        0,
        0,
    )
    image[32:104] = struct.pack(
        "<II16sQQQQiiII",
        0x19,
        72,
        b"__TEXT" + bytes(10),
        0x100000100,
        0x40,
        0x100,
        0x40,
        7,
        5,
        0,
        0,
    )
    image[104:128] = struct.pack(
        "<IIQQ",
        0x80000028,
        24,
        0x100,
        0,
    )
    image[0x100 : 0x100 + len(entry_point)] = entry_point
    return bytes(image[:size])


def case(
    case_id: str,
    architecture: str,
    cpu_type: int,
    data: bytes,
) -> dict[str, object]:
    return {
        "id": case_id,
        "architecture": architecture,
        "cpu_type": cpu_type,
        "data_hex": data.hex(),
        "data_sha256": hashlib.sha256(data).hexdigest(),
    }


def manifest() -> dict[str, object]:
    cases = [
        case(
            "rust_macho64_x86_64_entry_point_match",
            "x86_64",
            X86_64_CPU,
            mapped_macho64(X86_64_CPU, X86_64_EP),
        ),
        case(
            "rust_macho64_arm64_entry_point_match",
            "arm64",
            ARM64_CPU,
            mapped_macho64(ARM64_CPU, ARM64_EP),
        ),
        case(
            "rust_macho64_x86_64_entry_point_mismatch",
            "x86_64",
            X86_64_CPU,
            mapped_macho64(X86_64_CPU, bytes(64)),
        ),
        case(
            "rust_macho64_x86_64_entry_point_truncated",
            "x86_64",
            X86_64_CPU,
            mapped_macho64(X86_64_CPU, X86_64_EP, 0x100),
        ),
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "generator": {
            "path": "tools/corpus/generate_macho_rule_fixture.py",
            "version": GENERATOR_VERSION,
        },
        "license": "project-generated; no third-party sample bytes",
        "upstream_commit": UPSTREAM_COMMIT,
        "formats_commit": FORMATS_COMMIT,
        "xscanengine_commit": XSCANENGINE_COMMIT,
        "rules_commit": RULES_COMMIT,
        "rule": {
            "path": RULE_PATH,
            "sha256": RULE_SHA256,
            "preservation": "loaded byte-for-byte from the pinned rules subtree",
        },
        "case_count": len(cases),
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
