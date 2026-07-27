#!/usr/bin/env python3
"""Generate project-owned ELF32/64 inputs for a fixed-rule oracle."""

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
RULE_PATH = "ELF/protector_Burneye.2.sg"
RULE_SHA256 = "35461b495f056d98de9af44eda91df3c6412d22555b182834af9b6a68842d44c"
BURN_EYE_EP = bytes.fromhex("ff35112233449c608b0daabbccdde9")


def mapped_elf64(entry_point: bytes, size: int = 0x200) -> bytes:
    if size < 0xB0:
        raise ValueError("fixture must retain the ELF64 header and program table")
    image = bytearray(0x200)
    ident = b"\x7fELF" + bytes((2, 1, 1, 0, 0)) + bytes(7)
    image[:64] = ident + struct.pack(
        "<HHIQQQIHHHHHH",
        3,
        62,
        1,
        0x400100,
        64,
        0,
        0,
        64,
        56,
        2,
        0,
        0,
        0,
    )
    struct.pack_into(
        "<IIQQQQQQ",
        image,
        64,
        1,
        5,
        0x100,
        0x400100,
        0x400100,
        0x20,
        0x20,
        1,
    )
    struct.pack_into(
        "<IIQQQQQQ",
        image,
        120,
        1,
        5,
        0x180,
        0x401000,
        0x401000,
        0x20,
        0x20,
        1,
    )
    image[0x100 : 0x100 + len(entry_point)] = entry_point
    return bytes(image[:size])


def mapped_elf32(entry_point: bytes, size: int = 0x200) -> bytes:
    if size < 0x74:
        raise ValueError("fixture must retain the ELF32 header and program table")
    image = bytearray(0x200)
    ident = b"\x7fELF" + bytes((1, 1, 1, 0, 0)) + bytes(7)
    image[:52] = ident + struct.pack(
        "<HHIIIIIHHHHHH",
        3,
        3,
        1,
        0x8048100,
        52,
        0,
        0,
        52,
        32,
        2,
        0,
        0,
        0,
    )
    struct.pack_into(
        "<IIIIIIII",
        image,
        52,
        1,
        0x100,
        0x8048100,
        0x8048100,
        0x20,
        0x20,
        5,
        1,
    )
    struct.pack_into(
        "<IIIIIIII",
        image,
        84,
        1,
        0x180,
        0x8049000,
        0x8049000,
        0x20,
        0x20,
        5,
        1,
    )
    image[0x100 : 0x100 + len(entry_point)] = entry_point
    return bytes(image[:size])


def case(case_id: str, elf_class: int, data: bytes) -> dict[str, object]:
    return {
        "id": case_id,
        "elf_class": elf_class,
        "data_hex": data.hex(),
        "data_sha256": hashlib.sha256(data).hexdigest(),
    }


def manifest() -> dict[str, object]:
    mismatch = bytes([BURN_EYE_EP[0] ^ 0xFF]) + BURN_EYE_EP[1:]
    cases = [
        case("burneye_elf32_entry_point_match", 32, mapped_elf32(BURN_EYE_EP)),
        case("burneye_elf32_entry_point_mismatch", 32, mapped_elf32(mismatch)),
        case(
            "burneye_elf32_entry_point_truncated",
            32,
            mapped_elf32(BURN_EYE_EP, 0x100),
        ),
        case("burneye_elf64_entry_point_match", 64, mapped_elf64(BURN_EYE_EP)),
        case("burneye_elf64_entry_point_mismatch", 64, mapped_elf64(mismatch)),
        case(
            "burneye_elf64_entry_point_truncated",
            64,
            mapped_elf64(BURN_EYE_EP, 0x100),
        ),
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "generator": {
            "path": "tools/corpus/generate_elf_rule_fixture.py",
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
