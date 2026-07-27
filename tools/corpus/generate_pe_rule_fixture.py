#!/usr/bin/env python3
"""Generate project-owned PE inputs for an end-to-end fixed-rule oracle."""

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
RULE_PATH = "PE/compiler_Cygwin32.4.sg"
RULE_SHA256 = "de563e3333c54b966efb7aa3d678acd56ca5fa9b83a7b8356b3a4e71e47dc4cd"
CYGWIN_EP = bytes.fromhex("5589e583ec04833d")


def mapped_pe32(entry_point: bytes, size: int = 0x600) -> bytes:
    if size < 0x1C8:
        raise ValueError("fixture must retain the complete PE and section headers")
    image = bytearray(0x600)
    image[0:2] = b"MZ"
    struct.pack_into("<I", image, 0x3C, 0x80)
    image[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", image, 0x84, 0x14C, 2, 0, 0, 0, 224, 0x0102)
    optional = 0x98
    struct.pack_into("<H", image, optional, 0x10B)
    struct.pack_into("<I", image, optional + 16, 0x1000)
    struct.pack_into("<I", image, optional + 28, 0x400000)
    struct.pack_into("<II", image, optional + 32, 0x1000, 0x200)
    struct.pack_into("<II", image, optional + 56, 0x3000, 0x200)
    struct.pack_into("<H", image, optional + 68, 3)
    struct.pack_into("<I", image, optional + 92, 16)
    section = 0x178
    for index, (name, virtual_address, raw_offset) in enumerate(
        ((b".one\0\0\0\0", 0x1000, 0x200), (b".two\0\0\0\0", 0x2000, 0x400))
    ):
        struct.pack_into(
            "<8sIIIIIIHHI",
            image,
            section + index * 40,
            name,
            0x100,
            virtual_address,
            0x200,
            raw_offset,
            0,
            0,
            0,
            0,
            0x60000020,
        )
    image[0x200 : 0x200 + len(entry_point)] = entry_point
    return bytes(image[:size])


def case(case_id: str, data: bytes) -> dict[str, object]:
    return {
        "id": case_id,
        "data_hex": data.hex(),
        "data_sha256": hashlib.sha256(data).hexdigest(),
    }


def manifest() -> dict[str, object]:
    positive = mapped_pe32(CYGWIN_EP)
    negative = mapped_pe32(bytes([CYGWIN_EP[0] ^ 0xFF]) + CYGWIN_EP[1:])
    truncated = mapped_pe32(CYGWIN_EP, 0x200)
    cases = [
        case("cygwin32_entry_point_match", positive),
        case("cygwin32_entry_point_mismatch", negative),
        case("cygwin32_entry_point_truncated", truncated),
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "generator": {
            "path": "tools/corpus/generate_pe_rule_fixture.py",
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
