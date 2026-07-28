#!/usr/bin/env python3
"""Audit pinned, externally stored compressed RAR test fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
import zlib
from typing import Any


SOURCE_REMOTE = "https://github.com/ssokolow/rar-test-files.git"
SOURCE_COMMIT = "16b785c2b1b504e99fc307676e5369a26d3ce060"
RARLAB_EULA_URL = "https://www.rarlab.com/license.htm"
SELECTED_SAMPLES = (
    "build/testfile.rar3.rar",
    "build/testfile.rar3.solid.cbr",
    "build/testfile.rar5.cbr",
    "build/testfile.rar5.solid.cbr",
)
EXPECTED_SOURCES = {
    "testfile.txt": "sources/testfile.txt",
    "testfile.jpg": "sources/testfile.jpg",
    "testfile.png": "sources/testfile.png",
}
RAR3_SIGNATURE = b"Rar!\x1a\x07\x00"
RAR5_SIGNATURE = b"Rar!\x1a\x07\x01\x00"


class FixtureAuditError(ValueError):
    """The fixture source cannot produce trustworthy evidence."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run_git(path: pathlib.Path, *arguments: str) -> str:
    process = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={path}",
            "-C",
            str(path),
            *arguments,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    if process.stderr:
        raise FixtureAuditError(
            f"git wrote stderr: {path}: {' '.join(arguments)}"
        )
    return process.stdout.strip()


def verify_checkout(root: pathlib.Path) -> None:
    if run_git(root, "rev-parse", "HEAD") != SOURCE_COMMIT:
        raise FixtureAuditError("fixture source commit mismatch")
    if run_git(root, "status", "--porcelain"):
        raise FixtureAuditError("fixture source checkout is dirty")
    remote = run_git(root, "remote", "get-url", "origin")
    if remote.rstrip("/") != SOURCE_REMOTE.rstrip("/"):
        raise FixtureAuditError("fixture source remote mismatch")


def file_record(path: pathlib.Path, root: pathlib.Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": len(data),
        "sha256": sha256(data),
    }


def read_uint(data: bytes, offset: int, size: int) -> tuple[int, int]:
    end = offset + size
    if end > len(data):
        raise FixtureAuditError("truncated fixed-width integer")
    return int.from_bytes(data[offset:end], "little"), end


def read_vint(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    for shift in range(0, 70, 7):
        if offset >= len(data):
            raise FixtureAuditError("truncated RAR5 vint")
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, offset
    raise FixtureAuditError("oversized RAR5 vint")


def decode_name(data: bytes) -> str:
    try:
        name = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise FixtureAuditError("fixture member name is not UTF-8") from error
    if not name or name.startswith(("/", "\\")):
        raise FixtureAuditError("unsafe fixture member name")
    if ".." in name.replace("\\", "/").split("/"):
        raise FixtureAuditError("unsafe fixture member path")
    return name


def parse_rar3(data: bytes) -> dict[str, Any]:
    if not data.startswith(RAR3_SIGNATURE):
        raise FixtureAuditError("missing RAR3 signature")
    offset = len(RAR3_SIGNATURE)
    members = []
    archive_solid = False
    saw_main = False
    saw_end = False
    while offset < len(data):
        header_start = offset
        header_crc, offset = read_uint(data, offset, 2)
        header_type, offset = read_uint(data, offset, 1)
        flags, offset = read_uint(data, offset, 2)
        header_size, offset = read_uint(data, offset, 2)
        header_end = header_start + header_size
        if header_size < 7 or header_end > len(data):
            raise FixtureAuditError("invalid RAR3 header size")
        expected_header_crc = (
            zlib.crc32(data[header_start + 2 : header_end]) & 0xFFFF
        )
        if header_crc != expected_header_crc:
            raise FixtureAuditError("invalid RAR3 header CRC")
        packed_size = 0
        if header_type == 0x73:
            if saw_main or members:
                raise FixtureAuditError("misplaced RAR3 main header")
            archive_solid = bool(flags & 0x0008)
            saw_main = True
        elif header_type == 0x74:
            if not saw_main:
                raise FixtureAuditError("RAR3 file precedes main header")
            packed_size, offset = read_uint(data, offset, 4)
            unpacked_size, offset = read_uint(data, offset, 4)
            _, offset = read_uint(data, offset, 1)
            data_crc32, offset = read_uint(data, offset, 4)
            _, offset = read_uint(data, offset, 4)
            unpack_version, offset = read_uint(data, offset, 1)
            method, offset = read_uint(data, offset, 1)
            name_size, offset = read_uint(data, offset, 2)
            _, offset = read_uint(data, offset, 4)
            if flags & 0x0100:
                high_packed, offset = read_uint(data, offset, 4)
                high_unpacked, offset = read_uint(data, offset, 4)
                packed_size |= high_packed << 32
                unpacked_size |= high_unpacked << 32
            name_end = offset + name_size
            if name_end > header_end:
                raise FixtureAuditError("RAR3 member name exceeds header")
            name = decode_name(data[offset:name_end])
            data_start = header_end
            data_end = data_start + packed_size
            if data_end > len(data):
                raise FixtureAuditError("RAR3 packed data exceeds file")
            members.append(
                {
                    "name": name,
                    "packed_size": packed_size,
                    "unpacked_size": unpacked_size,
                    "packed_sha256": sha256(data[data_start:data_end]),
                    "data_crc32": f"{data_crc32:08x}",
                    "unpack_version": unpack_version,
                    "method": method,
                    "method_hex": f"0x{method:02x}",
                    "solid": bool(flags & 0x0010),
                }
            )
        elif header_type == 0x7B:
            saw_end = True
        else:
            raise FixtureAuditError(
                f"unsupported RAR3 header type: {header_type:#x}"
            )
        offset = header_end + packed_size
        if saw_end:
            break
    if not saw_main or not saw_end or offset != len(data) or not members:
        raise FixtureAuditError("incomplete RAR3 fixture")
    return {
        "format": "RAR3",
        "archive_solid": archive_solid,
        "members": members,
    }


def parse_rar5(data: bytes) -> dict[str, Any]:
    if not data.startswith(RAR5_SIGNATURE):
        raise FixtureAuditError("missing RAR5 signature")
    offset = len(RAR5_SIGNATURE)
    members = []
    archive_solid = False
    saw_main = False
    saw_end = False
    while offset < len(data):
        header_start = offset
        header_crc, offset = read_uint(data, offset, 4)
        protected_start = offset
        header_size, offset = read_vint(data, offset)
        header_end = offset + header_size
        if header_end > len(data):
            raise FixtureAuditError("invalid RAR5 header size")
        header_type, offset = read_vint(data, offset)
        flags, offset = read_vint(data, offset)
        extra_size = 0
        data_size = 0
        if flags & 0x0001:
            extra_size, offset = read_vint(data, offset)
        if flags & 0x0002:
            data_size, offset = read_vint(data, offset)
        if zlib.crc32(data[protected_start:header_end]) != header_crc:
            raise FixtureAuditError("invalid RAR5 header CRC")
        if header_type == 1:
            if saw_main or members:
                raise FixtureAuditError("misplaced RAR5 main header")
            archive_flags, offset = read_vint(data, offset)
            archive_solid = bool(archive_flags & 0x0004)
            saw_main = True
        elif header_type == 2:
            if not saw_main:
                raise FixtureAuditError("RAR5 file precedes main header")
            file_flags, offset = read_vint(data, offset)
            unpacked_size, offset = read_vint(data, offset)
            _, offset = read_vint(data, offset)
            if file_flags & 0x0002:
                _, offset = read_uint(data, offset, 4)
            data_crc32 = None
            if file_flags & 0x0004:
                data_crc32, offset = read_uint(data, offset, 4)
            compression_info, offset = read_vint(data, offset)
            host_os, offset = read_vint(data, offset)
            name_size, offset = read_vint(data, offset)
            name_end = offset + name_size
            if name_end > header_end - extra_size:
                raise FixtureAuditError("RAR5 member name exceeds header")
            name = decode_name(data[offset:name_end])
            data_start = header_end
            data_end = data_start + data_size
            if data_end > len(data):
                raise FixtureAuditError("RAR5 packed data exceeds file")
            members.append(
                {
                    "name": name,
                    "packed_size": data_size,
                    "unpacked_size": unpacked_size,
                    "packed_sha256": sha256(data[data_start:data_end]),
                    "data_crc32": (
                        None
                        if data_crc32 is None
                        else f"{data_crc32:08x}"
                    ),
                    "algorithm_version": compression_info & 0x3F,
                    "method": (compression_info & 0x0380) >> 7,
                    "dictionary_exponent": (
                        (compression_info & 0x7C00) >> 10
                    ),
                    "solid": bool(compression_info & 0x0040),
                    "host_os": host_os,
                }
            )
        elif header_type == 5:
            saw_end = True
        else:
            raise FixtureAuditError(
                f"unsupported RAR5 header type: {header_type}"
            )
        offset = header_end + data_size
        if saw_end:
            break
    if not saw_main or not saw_end or offset != len(data) or not members:
        raise FixtureAuditError("incomplete RAR5 fixture")
    return {
        "format": "RAR5",
        "archive_solid": archive_solid,
        "members": members,
    }


def parse_archive(data: bytes) -> dict[str, Any]:
    if data.startswith(RAR3_SIGNATURE):
        return parse_rar3(data)
    if data.startswith(RAR5_SIGNATURE):
        return parse_rar5(data)
    raise FixtureAuditError("unsupported RAR signature")


def build_report(root: pathlib.Path) -> dict[str, Any]:
    verify_checkout(root)
    readme = (root / "README.md").read_bytes()
    license_md = (root / "LICENSE.md").read_bytes()
    license_cc0 = (root / "LICENSE.cc0").read_bytes()
    makefile = (root / "Makefile").read_bytes()
    samples = []
    for relative in SELECTED_SAMPLES:
        path = root / relative
        data = path.read_bytes()
        parsed = parse_archive(data)
        source_records = []
        for member in parsed["members"]:
            source_relative = EXPECTED_SOURCES.get(member["name"])
            if source_relative is None:
                raise FixtureAuditError(
                    f"unexpected fixture member: {member['name']}"
                )
            source = root / source_relative
            if source.stat().st_size != member["unpacked_size"]:
                raise FixtureAuditError(
                    f"source size mismatch: {member['name']}"
                )
            source_records.append(file_record(source, root))
        samples.append(
            {
                **file_record(path, root),
                **parsed,
                "source_files": source_records,
                "contains_sfx": path.suffix.lower() in {".exe", ".bin"},
            }
        )

    relationships = {
        "four_selected_non_sfx_archives_are_present": (
            len(samples) == 4
            and all(not sample["contains_sfx"] for sample in samples)
        ),
        "rar3_samples_use_compressed_method_0x35": all(
            member["method"] == 0x35
            for sample in samples
            if sample["format"] == "RAR3"
            for member in sample["members"]
        ),
        "rar5_samples_include_compressed_method_5": all(
            any(member["method"] == 5 for member in sample["members"])
            for sample in samples
            if sample["format"] == "RAR5"
        ),
        "rar5_methods_are_store_or_method_5": all(
            member["method"] in {0, 5}
            for sample in samples
            if sample["format"] == "RAR5"
            for member in sample["members"]
        ),
        "rar5_non_solid_has_creator_store_fallback": any(
            member["method"] == 0
            for sample in samples
            if sample["path"] == "build/testfile.rar5.cbr"
            for member in sample["members"]
        ),
        "solid_samples_have_a_solid_following_member": all(
            any(member["solid"] for member in sample["members"][1:])
            for sample in samples
            if ".solid." in sample["path"]
        ),
        "plain_samples_are_not_solid": all(
            not sample["archive_solid"]
            and all(
                not member["solid"] for member in sample["members"]
            )
            for sample in samples
            if ".solid." not in sample["path"]
        ),
        "makefile_requests_best_compression": (
            b"RAR_OPTS := -m5" in makefile
        ),
        "readme_claims_registered_creator": (
            b"I bought a WinRAR license" in readme
        ),
        "readme_claims_legally_redistributable_test_files": (
            b"minimal, legally redistributable `.rar`" in readme
        ),
        "creator_applies_cc0_to_owned_content": (
            b"I hereby release anything in these archives"
            in license_md
            and b"CC0 1.0 Universal" in license_cc0
        ),
        "purchase_evidence_is_present": (
            (root / "purchase_evidence.png").is_file()
        ),
    }
    if not all(relationships.values()):
        failed = [
            name for name, value in relationships.items() if not value
        ]
        raise FixtureAuditError(
            f"fixture source relationships failed: {failed}"
        )
    return {
        "schema_version": 1,
        "generator": (
            "tools/corpus/audit_rar_compressed_fixture_source.py"
        ),
        "generator_sha256": sha256(pathlib.Path(__file__).read_bytes()),
        "source": {
            "remote": SOURCE_REMOTE,
            "commit": SOURCE_COMMIT,
            "rarlab_eula_url": RARLAB_EULA_URL,
            "evidence_files": [
                file_record(root / relative, root)
                for relative in (
                    "README.md",
                    "LICENSE.md",
                    "LICENSE.cc0",
                    "Makefile",
                    "purchase_evidence.png",
                )
            ],
        },
        "selection": {
            "policy": (
                "compressed RAR3/RAR5 controls and solid pairs; "
                "exclude all SFX, authenticity, recovery and locked cases"
            ),
            "external_storage": True,
            "binary_files_committed_to_project": False,
            "samples": samples,
        },
        "redistribution_review": {
            "creator_license_claim_present": True,
            "creator_purchase_evidence_present": True,
            "creator_owned_content_cc0": True,
            "rarlab_eula_allows_licensed_creator_to_distribute_archives": (
                True
            ),
            "project_legal_review_complete": False,
            "project_redistribution_approved": False,
        },
        "relationships": relationships,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()
    report = build_report(args.source_root.resolve())
    serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        sys.stdout.write(serialized)
    else:
        args.output.write_text(
            serialized, encoding="utf-8", newline="\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
