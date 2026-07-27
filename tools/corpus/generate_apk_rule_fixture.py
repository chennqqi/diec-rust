#!/usr/bin/env python3
"""Generate project-owned APK inputs for a fixed-rule oracle."""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import struct
from pathlib import Path


SCHEMA_VERSION = 1
GENERATOR_VERSION = 1
UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
XARCHIVE_COMMIT = "0fcd4e8d3e9933baac3b12246d82ac026557ffd0"
XSCANENGINE_COMMIT = "dfe4a419e4f491bb23688ba03c5a5bf39e34da83"
RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
RULE_PATH = "APK/protector_QDBH.2.sg"
RULE_SHA256 = "cc20faadf1aec677679151a1997ea95184b265db2dbb1d4fcf56f0b62cead752"


def make_zip_entries(entries: tuple[tuple[bytes, bytes], ...]) -> bytes:
    local_parts = []
    central_parts = []
    offset = 0
    for name, data in entries:
        crc = binascii.crc32(data)
        local = (
            struct.pack(
                "<IHHHHHIIIHH",
                0x04034B50,
                20,
                0,
                0,
                0,
                0x0021,
                crc,
                len(data),
                len(data),
                len(name),
                0,
            )
            + name
            + data
        )
        central = (
            struct.pack(
                "<IHHHHHHIIIHHHHHII",
                0x02014B50,
                0x0314,
                20,
                0,
                0,
                0,
                0x0021,
                crc,
                len(data),
                len(data),
                len(name),
                0,
                0,
                0,
                0,
                0,
                offset,
            )
            + name
        )
        local_parts.append(local)
        central_parts.append(central)
        offset += len(local)
    local_bytes = b"".join(local_parts)
    central_bytes = b"".join(central_parts)
    end = struct.pack(
        "<IHHHHIIH",
        0x06054B50,
        0,
        0,
        len(entries),
        len(entries),
        len(central_bytes),
        len(local_bytes),
        0,
    )
    return local_bytes + central_bytes + end


def apk_with_asset(asset_name: bytes) -> bytes:
    return make_zip_entries(((b"classes.dex", b""), (asset_name, b"")))


def without_local_records(archive: bytes) -> bytes:
    """Retain the central directory while removing every local record."""
    end_offset = len(archive) - 22
    if archive[end_offset : end_offset + 4] != b"PK\x05\x06":
        raise ValueError("fixture ZIP must end in an empty-comment EOCD")
    central_size = struct.unpack_from("<I", archive, end_offset + 12)[0]
    central_offset = struct.unpack_from("<I", archive, end_offset + 16)[0]
    central = archive[central_offset : central_offset + central_size]
    if len(central) != central_size:
        raise ValueError("fixture central directory is truncated")
    empty_end = struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, 0, 0, 0, 0, 0)
    real_end = bytearray(archive[end_offset:])
    struct.pack_into("<I", real_end, 16, len(empty_end))
    return empty_end + central + bytes(real_end)


def case(case_id: str, data: bytes) -> dict[str, object]:
    return {
        "id": case_id,
        "data_hex": data.hex(),
        "data_sha256": hashlib.sha256(data).hexdigest(),
    }


def manifest() -> dict[str, object]:
    positive = apk_with_asset(b"assets/qdbh")
    cases = [
        case("qdbh_archive_record_match", positive),
        case("qdbh_archive_record_case_mismatch", apk_with_asset(b"assets/QDBH")),
        case("qdbh_local_records_truncated", without_local_records(positive)),
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "generator": {
            "path": "tools/corpus/generate_apk_rule_fixture.py",
            "version": GENERATOR_VERSION,
        },
        "license": "project-generated; no third-party sample bytes",
        "upstream_commit": UPSTREAM_COMMIT,
        "xarchive_commit": XARCHIVE_COMMIT,
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
