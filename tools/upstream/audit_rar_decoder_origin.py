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
from typing import Any


UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
XARCHIVE_COMMIT = "0fcd4e8d3e9933baac3b12246d82ac026557ffd0"
XARCHIVE_INTRODUCTION_COMMIT = (
    "d48321dcc54b5011756853437de1a7220fd2a440"
)
XARCHIVE_REMOTE = "https://github.com/horsicq/XArchive.git"
UNRAR_COMMIT = "9f1ce54025e0175634cbdb21b06341aa29eba591"
UNRAR_REMOTE = "https://github.com/pmachapman/unrar.git"
UNRAR_RELEASE = "7.1.10"
UNRAR_OFFICIAL_SOURCE_URL = "https://www.rarlab.com/rar_add.htm"
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
) -> dict[str, Any]:
    verify_checkout(
        xarchive_root, XARCHIVE_COMMIT, XARCHIVE_REMOTE
    )
    verify_checkout(unrar_root, UNRAR_COMMIT, UNRAR_REMOTE)
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
    }
    if not all(relationships.values()):
        raise ValueError("RAR decoder origin relationships failed")

    return {
        "schema_version": 1,
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
            "mirror_release": UNRAR_RELEASE,
            "official_source_url": UNRAR_OFFICIAL_SOURCE_URL,
            "source_file_count": len(reference_files),
            "license": file_record(
                unrar_root / "license.txt", unrar_root
            ),
            "readme": file_record(
                unrar_root / "readme.txt", unrar_root
            ),
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
            "reference_requires_notice_for_modified_distribution": True,
            "reference_restricts_rar_compression_recreation": True,
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
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()
    report = build_report(
        args.xarchive_root.resolve(),
        args.unrar_root.resolve(),
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
