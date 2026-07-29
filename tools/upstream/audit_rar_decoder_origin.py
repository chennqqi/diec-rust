#!/usr/bin/env python3
"""Compare XArchive's fixed RAR decoder with pinned UnRAR source."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import tarfile
from typing import Any


UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
XARCHIVE_COMMIT = "0fcd4e8d3e9933baac3b12246d82ac026557ffd0"
XARCHIVE_INTRODUCTION_COMMIT = (
    "d48321dcc54b5011756853437de1a7220fd2a440"
)
XARCHIVE_REMOTE = "https://github.com/horsicq/XArchive.git"
UNRAR_COMMIT = "9f1ce54025e0175634cbdb21b06341aa29eba591"
UNRAR_REMOTE = "https://github.com/pmachapman/unrar.git"
UNRAR_MIRROR_UPDATE_LABEL = "7.1.10"
UNRAR_SOURCE_VERSION = "7.13"
UNRAR_SOURCE_DATE = "2025-07-28"
UNRAR_OFFICIAL_SOURCE_PAGE = "https://www.rarlab.com/rar_add.htm"
UNRAR_OFFICIAL_ARCHIVE_URL = (
    "https://www.rarlab.com/rar/unrarsrc-7.1.10.tar.gz"
)
UNRAR_OFFICIAL_ARCHIVE_SHA256 = (
    "72a9ccca146174f41876e8b21ab27e973f039c6d10b13aabcb320e7055b9bb98"
)
UNRAR_OFFICIAL_ROOT = "unrar"
EXPECTED_LINE_ENDING_ONLY_PATHS = {
    "UnRAR.vcxproj",
    "UnRARDll.vcxproj",
    "acknow.txt",
    "dll.def",
    "dll.rc",
    "dll_nocrypt.def",
}
SHINGLE_LENGTHS = (12, 64)
TOKEN_PATTERN = re.compile(
    r"""//[^\n]*|/\*.*?\*/|"""
    r"""(?:u8|u|U|L)?"(?:\\.|[^"\\])*"|"""
    r"""(?:u8|u|U|L)?'(?:\\.|[^'\\])*'|"""
    r"""[A-Za-z_]\w*|"""
    r"""0[xX][0-9A-Fa-f]+|"""
    r"""\d+(?:\.\d+)?(?:[eEpP][+-]?\d+)?[uUlLfF]*|"""
    r""">>=|<<=|->|\+\+|--|&&|\|\||==|!=|<=|>=|<<|>>|##|\.\.\.|\S""",
    re.DOTALL,
)


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
        raise ValueError(
            f"git wrote stderr: {path}: {' '.join(arguments)}"
        )
    return process.stdout.strip()


def git_blob(path: pathlib.Path, object_name: str) -> bytes:
    process = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={path}",
            "-C",
            str(path),
            "show",
            object_name,
        ],
        check=True,
        capture_output=True,
    )
    if process.stderr:
        raise ValueError(f"git show wrote stderr: {object_name}")
    return process.stdout


def verify_checkout(
    path: pathlib.Path, commit: str, remote: str
) -> dict[str, str]:
    if run_git(path, "rev-parse", "HEAD") != commit:
        raise ValueError(f"checkout commit mismatch: {path}")
    if run_git(path, "status", "--porcelain"):
        raise ValueError(f"checkout is dirty: {path}")
    actual_remote = run_git(path, "remote", "get-url", "origin")
    if actual_remote.rstrip("/") != remote.rstrip("/"):
        raise ValueError(f"checkout remote mismatch: {path}")
    return {"commit": commit, "remote": remote}


def tokenize_c(data: bytes) -> list[str]:
    text = data.decode("utf-8-sig", errors="replace")
    return [
        match.group()
        for match in TOKEN_PATTERN.finditer(text)
        if not match.group().startswith(("//", "/*"))
    ]


def source_files(root: pathlib.Path) -> list[pathlib.Path]:
    return sorted(
        path
        for path in root.iterdir()
        if path.is_file() and path.suffix in {".cpp", ".hpp"}
    )


def read_official_archive(
    path: pathlib.Path,
    expected_sha256: str = UNRAR_OFFICIAL_ARCHIVE_SHA256,
) -> dict[str, bytes]:
    archive_bytes = path.read_bytes()
    if sha256(archive_bytes) != expected_sha256:
        raise ValueError("official UnRAR archive SHA-256 mismatch")
    result = {}
    with tarfile.open(path, mode="r:gz") as archive:
        for member in archive.getmembers():
            pure = pathlib.PurePosixPath(member.name)
            if pure.is_absolute() or ".." in pure.parts:
                raise ValueError(
                    f"unsafe official archive member: {member.name}"
                )
            if not member.isfile():
                continue
            if (
                not pure.parts
                or pure.parts[0] != UNRAR_OFFICIAL_ROOT
                or len(pure.parts) != 2
            ):
                raise ValueError(
                    f"unexpected official archive path: {member.name}"
                )
            relative = pure.parts[1]
            if relative in result:
                raise ValueError(
                    f"duplicate official archive member: {member.name}"
                )
            extracted = archive.extractfile(member)
            if extracted is None:
                raise ValueError(
                    f"cannot read official archive member: {member.name}"
                )
            result[relative] = extracted.read()
    if not result:
        raise ValueError("official UnRAR archive is empty")
    return result


def normalize_line_endings(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def official_archive_comparison(
    archive_files: dict[str, bytes],
    mirror_root: pathlib.Path,
) -> dict[str, Any]:
    missing = sorted(
        path
        for path in archive_files
        if not (mirror_root / path).is_file()
    )
    if missing:
        raise ValueError(f"official files missing in mirror: {missing}")
    exact = []
    line_ending_only = []
    content_mismatch = []
    for relative, official_data in sorted(archive_files.items()):
        mirror_data = (mirror_root / relative).read_bytes()
        if official_data == mirror_data:
            exact.append(relative)
        elif normalize_line_endings(
            official_data
        ) == normalize_line_endings(mirror_data):
            line_ending_only.append(relative)
        else:
            content_mismatch.append(relative)
    return {
        "official_regular_file_count": len(archive_files),
        "byte_identical_file_count": len(exact),
        "line_ending_only_file_count": len(line_ending_only),
        "line_ending_only_files": line_ending_only,
        "content_mismatch_file_count": len(content_mismatch),
        "content_mismatch_files": content_mismatch,
        "missing_in_mirror_count": len(missing),
        "missing_in_mirror": missing,
    }


def file_record(path: pathlib.Path, root: pathlib.Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": len(data),
        "sha256": sha256(data),
    }


def shingle_evidence(
    embedded_tokens: list[str],
    reference_root: pathlib.Path,
    reference_files: list[pathlib.Path],
    length: int,
) -> dict[str, Any]:
    index: dict[tuple[str, ...], set[str]] = {}
    for path in reference_files:
        relative = path.relative_to(reference_root).as_posix()
        tokens = tokenize_c(path.read_bytes())
        for position in range(len(tokens) - length + 1):
            shingle = tuple(tokens[position : position + length])
            index.setdefault(shingle, set()).add(relative)

    covered = [False] * len(embedded_tokens)
    matching_window_count = 0
    unique_counts: dict[str, int] = {}
    for position in range(len(embedded_tokens) - length + 1):
        shingle = tuple(embedded_tokens[position : position + length])
        origins = index.get(shingle)
        if not origins:
            continue
        matching_window_count += 1
        for covered_position in range(position, position + length):
            covered[covered_position] = True
        if len(origins) == 1:
            origin = next(iter(origins))
            unique_counts[origin] = unique_counts.get(origin, 0) + 1

    unique_origins = [
        {
            "path": relative,
            "sha256": sha256((reference_root / relative).read_bytes()),
            "unique_matching_window_count": count,
        }
        for relative, count in sorted(unique_counts.items())
    ]
    covered_count = sum(covered)
    return {
        "shingle_length": length,
        "embedded_token_count": len(embedded_tokens),
        "covered_token_count": covered_count,
        "coverage": covered_count / len(embedded_tokens),
        "matching_window_count": matching_window_count,
        "unique_origin_file_count": len(unique_origins),
        "unique_origin_files": unique_origins,
    }


def introduction_record(xarchive_root: pathlib.Path) -> dict[str, Any]:
    introduction = run_git(
        xarchive_root,
        "log",
        "--follow",
        "--diff-filter=A",
        "--format=%H%x09%aI%x09%s",
        "--",
        "Algos/xrardecoder.cpp",
    ).splitlines()
    if introduction != [
        (
            f"{XARCHIVE_INTRODUCTION_COMMIT}\t"
            "2025-09-23T20:43:14+02:00\t"
            "Add new file(s): 2025-09-23"
        )
    ]:
        raise ValueError("unexpected XArchive RAR decoder introduction")
    files = []
    for relative in (
        "Algos/xrardecoder.cpp",
        "Algos/xrardecoder.h",
    ):
        data = git_blob(
            xarchive_root,
            f"{XARCHIVE_INTRODUCTION_COMMIT}:{relative}",
        )
        files.append(
            {
                "path": relative,
                "bytes": len(data),
                "sha256": sha256(data),
            }
        )
    return {
        "commit": XARCHIVE_INTRODUCTION_COMMIT,
        "authored_at": "2025-09-23T20:43:14+02:00",
        "subject": "Add new file(s): 2025-09-23",
        "files": files,
    }


def build_report(
    xarchive_root: pathlib.Path,
    unrar_root: pathlib.Path,
    official_archive: pathlib.Path,
) -> dict[str, Any]:
    verify_checkout(
        xarchive_root, XARCHIVE_COMMIT, XARCHIVE_REMOTE
    )
    verify_checkout(unrar_root, UNRAR_COMMIT, UNRAR_REMOTE)
    archive_bytes = official_archive.read_bytes()
    archive_files = read_official_archive(official_archive)
    archive_comparison = official_archive_comparison(
        archive_files, unrar_root
    )
    decoder_paths = [
        xarchive_root / "Algos/xrardecoder.cpp",
        xarchive_root / "Algos/xrardecoder.h",
    ]
    decoder_data = [path.read_bytes() for path in decoder_paths]
    decoder_tokens = [
        token
        for data in decoder_data
        for token in tokenize_c(data)
    ]
    reference_files = source_files(unrar_root)
    shingles = [
        shingle_evidence(
            decoder_tokens,
            unrar_root,
            reference_files,
            length,
        )
        for length in SHINGLE_LENGTHS
    ]
    license_data = (unrar_root / "license.txt").read_bytes()
    readme_data = (unrar_root / "readme.txt").read_bytes()
    version_data = (unrar_root / "version.hpp").read_bytes()
    official_license_data = archive_files["license.txt"]
    official_readme_data = archive_files["readme.txt"]
    official_acknowledgments_data = archive_files["acknow.txt"]
    official_source_paths = sorted(
        path
        for path in archive_files
        if pathlib.PurePosixPath(path).suffix in {".cpp", ".hpp"}
    )
    latest_before_introduction = run_git(
        unrar_root,
        "log",
        "-1",
        "--until=2025-09-23T18:43:14Z",
        "--format=%H",
    )
    relationships = {
        "reference_is_latest_mirror_commit_before_decoder_introduction": (
            latest_before_introduction == UNRAR_COMMIT
        ),
        "decoder_12_token_coverage_exceeds_94_percent": (
            shingles[0]["coverage"] > 0.94
        ),
        "decoder_64_token_coverage_exceeds_74_percent": (
            shingles[1]["coverage"] > 0.74
        ),
        "decoder_files_declare_mit_permission": all(
            b"Permission is hereby granted, free of charge" in data
            for data in decoder_data
        ),
        "decoder_files_omit_unrar_distribution_notice": all(
            b"Distribution of modified UnRAR source code" not in data
            and b"Alexander L. Roshal" not in data
            for data in decoder_data
        ),
        "reference_license_requires_distribution_notice": (
            b"Distribution of modified UnRAR source code"
            in license_data
            and b"full text of this paragraph" in license_data
        ),
        "reference_license_restricts_compression_recreation": (
            b"re-create RAR compression algorithm" in license_data
        ),
        "reference_readme_identifies_generated_unrar_source": (
            b"generated from RAR source automatically" in readme_data
        ),
        "official_archive_sha256_is_fixed": (
            sha256(archive_bytes) == UNRAR_OFFICIAL_ARCHIVE_SHA256
        ),
        "official_and_mirror_declare_unrar_7_13": (
            b"#define RARVER_MAJOR     7" in version_data
            and b"#define RARVER_MINOR    13" in version_data
            and b"#define RARVER_DAY      28" in version_data
            and b"#define RARVER_MONTH     7" in version_data
            and b"#define RARVER_YEAR   2025" in version_data
            and archive_files["version.hpp"] == version_data
        ),
        "all_150_official_source_files_are_byte_identical_to_mirror": (
            len(official_source_paths) == 150
            and all(
                archive_files[path] == (unrar_root / path).read_bytes()
                for path in official_source_paths
            )
        ),
        "all_159_official_files_match_after_line_ending_normalization": (
            archive_comparison["official_regular_file_count"] == 159
            and archive_comparison["byte_identical_file_count"] == 153
            and set(archive_comparison["line_ending_only_files"])
            == EXPECTED_LINE_ENDING_ONLY_PATHS
            and archive_comparison["content_mismatch_file_count"] == 0
            and archive_comparison["missing_in_mirror_count"] == 0
        ),
        "official_and_mirror_license_are_byte_identical": (
            official_license_data == license_data
        ),
        "official_and_mirror_readme_are_byte_identical": (
            official_readme_data == readme_data
        ),
        "official_acknowledgments_contain_third_party_evidence": (
            b"Dmitry Shkarin PPMII" in official_acknowledgments_data
            and b"Szymon Stefanek AES" in official_acknowledgments_data
            and b"Copyright (c) 2004-2006 Intel Corporation"
            in official_acknowledgments_data
            and b"Redistribution and use in source and binary forms"
            in official_acknowledgments_data
        ),
        "decoder_files_omit_official_third_party_acknowledgments": (
            all(
                marker not in data
                for data in decoder_data
                for marker in (
                    b"Dmitry Shkarin",
                    b"Szymon Stefanek",
                    b"Intel Corporation",
                )
            )
        ),
    }
    if not all(relationships.values()):
        raise ValueError("RAR decoder origin relationships failed")

    return {
        "schema_version": 2,
        "generator": "tools/upstream/audit_rar_decoder_origin.py",
        "generator_sha256": sha256(pathlib.Path(__file__).read_bytes()),
        "upstream_commit": UPSTREAM_COMMIT,
        "xarchive": {
            "remote": XARCHIVE_REMOTE,
            "commit": XARCHIVE_COMMIT,
            "introduction": introduction_record(xarchive_root),
            "decoder_files": [
                file_record(path, xarchive_root)
                for path in decoder_paths
            ],
            "decoder_token_count": len(decoder_tokens),
        },
        "reference": {
            "kind": "Git mirror of RARLAB portable UnRAR source",
            "remote": UNRAR_REMOTE,
            "commit": UNRAR_COMMIT,
            "mirror_update_label": UNRAR_MIRROR_UPDATE_LABEL,
            "source_version": UNRAR_SOURCE_VERSION,
            "source_date": UNRAR_SOURCE_DATE,
            "source_file_count": len(reference_files),
            "license": file_record(
                unrar_root / "license.txt", unrar_root
            ),
            "readme": file_record(
                unrar_root / "readme.txt", unrar_root
            ),
        },
        "official_release": {
            "source_page": UNRAR_OFFICIAL_SOURCE_PAGE,
            "archive_url": UNRAR_OFFICIAL_ARCHIVE_URL,
            "archive_path_label": "unrarsrc-7.1.10.tar.gz",
            "archive_bytes": len(archive_bytes),
            "archive_sha256": sha256(archive_bytes),
            "archive_root": UNRAR_OFFICIAL_ROOT,
            "source_version": UNRAR_SOURCE_VERSION,
            "source_date": UNRAR_SOURCE_DATE,
            "license": {
                "path": "license.txt",
                "bytes": len(official_license_data),
                "sha256": sha256(official_license_data),
            },
            "readme": {
                "path": "readme.txt",
                "bytes": len(official_readme_data),
                "sha256": sha256(official_readme_data),
            },
            "acknowledgments": {
                "path": "acknow.txt",
                "bytes": len(archive_files["acknow.txt"]),
                "sha256": sha256(archive_files["acknow.txt"]),
            },
            "archive_to_mirror": archive_comparison,
        },
        "comparison": {
            "tokenization": (
                "C/C++ lexical tokens; comments and whitespace omitted; "
                "identifiers and literals preserved"
            ),
            "shingle_evidence": shingles,
        },
        "license_observation": {
            "decoder_files_contain_mit_permission": True,
            "decoder_files_contain_unrar_distribution_notice": False,
            "decoder_files_contain_official_third_party_acknowledgments":
                False,
            "reference_requires_notice_for_modified_distribution": True,
            "reference_restricts_rar_compression_recreation": True,
            "official_acknowledgments_include_public_domain_and_bsd":
                True,
            "third_party_attribution_review_complete": False,
            "legal_review_complete": False,
        },
        "implementation_constraint": {
            "copy_or_translation_approved": False,
            "reason": (
                "content provenance and conflicting notice evidence "
                "require legal review before reuse"
            ),
            "oracle_use_copies_decoder_into_project": False,
            "compressed_fixture_redistribution_approved": False,
        },
        "relationships": relationships,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--xarchive-root", type=pathlib.Path, required=True
    )
    parser.add_argument(
        "--unrar-root", type=pathlib.Path, required=True
    )
    parser.add_argument(
        "--official-archive", type=pathlib.Path, required=True
    )
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()
    report = build_report(
        args.xarchive_root.resolve(),
        args.unrar_root.resolve(),
        args.official_archive.resolve(),
    )
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
