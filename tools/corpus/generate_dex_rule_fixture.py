#!/usr/bin/env python3
"""Generate project-owned DEX inputs for a fixed-rule oracle."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path


SCHEMA_VERSION = 1
GENERATOR_VERSION = 1
UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
XDEX_COMMIT = "035c61966d3a9018edf80cd0013083ee32626e71"
XSCANENGINE_COMMIT = "dfe4a419e4f491bb23688ba03c5a5bf39e34da83"
RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
RULE_PATH = "DEX/protector_QDBH.2.sg"
RULE_SHA256 = "5280ae0425f47c03ca037002b29964fe59eb898e871a00ad266475856f0e7ba7"

HEADER_SIZE = 0x70
STRING_IDS_OFFSET = HEADER_SIZE
MAP_OFFSET = 0x74
STRING_DATA_OFFSET = 0xA8


def _map_item(item_type: int, count: int, offset: int) -> bytes:
    return struct.pack("<HHII", item_type, 0, count, offset)


def minimal_dex(value: bytes | None) -> bytes:
    """Build a one-string DEX; None leaves the string-data offset at EOF."""
    if value is not None and len(value) > 0x7F:
        raise ValueError("fixture string must use one-byte ULEB128 length")

    image = bytearray(STRING_DATA_OFFSET)
    image[0:8] = b"dex\n035\x00"
    struct.pack_into("<I", image, 36, HEADER_SIZE)
    struct.pack_into("<I", image, 40, 0x12345678)
    struct.pack_into("<I", image, 52, MAP_OFFSET)
    struct.pack_into("<I", image, 56, 1)
    struct.pack_into("<I", image, 60, STRING_IDS_OFFSET)
    struct.pack_into("<I", image, STRING_IDS_OFFSET, STRING_DATA_OFFSET)

    map_list = b"".join(
        (
            struct.pack("<I", 3),
            _map_item(0x0000, 1, 0),
            _map_item(0x0001, 1, STRING_IDS_OFFSET),
            _map_item(0x2002, 1, STRING_DATA_OFFSET),
        )
    )
    image[MAP_OFFSET : MAP_OFFSET + len(map_list)] = map_list
    if value is not None:
        image.extend(bytes((len(value),)) + value + b"\x00")

    struct.pack_into("<I", image, 32, len(image))
    struct.pack_into("<I", image, 104, len(image) - MAP_OFFSET)
    struct.pack_into("<I", image, 108, MAP_OFFSET)
    image[12:32] = hashlib.sha1(image[32:]).digest()
    struct.pack_into("<I", image, 8, zlib.adler32(image[12:]) & 0xFFFFFFFF)
    return bytes(image)


def case(case_id: str, data: bytes) -> dict[str, object]:
    return {
        "id": case_id,
        "data_hex": data.hex(),
        "data_sha256": hashlib.sha256(data).hexdigest(),
    }


def manifest() -> dict[str, object]:
    cases = [
        case("qdbh_string_match", minimal_dex(b"/qdbh")),
        case("qdbh_string_mismatch", minimal_dex(b"/nope")),
        case("qdbh_string_data_truncated", minimal_dex(None)),
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "generator": {
            "path": "tools/corpus/generate_dex_rule_fixture.py",
            "version": GENERATOR_VERSION,
        },
        "license": "project-generated; no third-party sample bytes",
        "upstream_commit": UPSTREAM_COMMIT,
        "xdex_commit": XDEX_COMMIT,
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
