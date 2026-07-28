#!/usr/bin/env python3
"""Audit pinned runtime PNG bytes, metadata, and original Git history."""

from __future__ import annotations

import argparse
import binascii
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import tomllib
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DETECT_ROOT = ROOT / "upstream" / "Detect-It-Easy"
COMPONENT_LOCK = ROOT / "upstream" / "components.lock.toml"
RUNTIME_REPORT = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "runtime-rule-assets-license.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "runtime-png-history.json"
)
GENERATOR = "tools/upstream/audit_runtime_png_history.py"
REPOSITORY = "https://github.com/horsicq/Detect-It-Easy.git"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
POLICY_BASENAMES = {
    "cla",
    "cla.md",
    "cla.txt",
    "code_of_conduct",
    "code_of_conduct.md",
    "code_of_conduct.txt",
    "contributing",
    "contributing.md",
    "contributing.txt",
    "contributors",
    "contributors.md",
    "contributors.txt",
    "dco",
    "dco.md",
    "dco.txt",
}
LICENSE_WORD = re.compile(
    r"\b(?:license|licence|copyright|author|creator|source|spdx)\b",
    re.IGNORECASE,
)


class AuditError(ValueError):
    """The pinned PNG inventory, Git history, or metadata is invalid."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob_oid(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def run_git(*arguments: str) -> bytes:
    process = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    if process.returncode != 0:
        raise AuditError(
            f"git {' '.join(arguments)} failed: "
            f"{process.stderr.decode('utf-8', 'replace').strip()}"
        )
    return process.stdout


def read_lock() -> tuple[str, str]:
    raw = COMPONENT_LOCK.read_bytes()
    lock = tomllib.loads(raw.decode("utf-8"))
    return (
        lock["gitlink"]["Detect-It-Easy"]["commit"],
        sha256(raw),
    )


def read_runtime_assets() -> tuple[list[dict[str, Any]], str]:
    raw = RUNTIME_REPORT.read_bytes()
    report = json.loads(raw)
    assets = report["binary_assets"]
    if (
        report["findings"]["binary_asset_count"] != 22
        or len(assets) != 22
        or any(not asset["path"].endswith(".png") for asset in assets)
    ):
        raise AuditError("runtime binary PNG inventory changed")
    return assets, sha256(raw)


def git_show(commit: str, path: str) -> bytes:
    return run_git("show", f"{commit}:{path}")


def parse_png(data: bytes) -> dict[str, Any]:
    if not data.startswith(PNG_SIGNATURE):
        raise AuditError("invalid PNG signature")
    offset = len(PNG_SIGNATURE)
    chunks = []
    text_chunks = []
    ihdr = None
    while offset < len(data):
        if offset + 12 > len(data):
            raise AuditError("truncated PNG chunk header")
        length = int.from_bytes(data[offset : offset + 4], "big")
        chunk_type = data[offset + 4 : offset + 8]
        end = offset + 12 + length
        if end > len(data):
            raise AuditError("truncated PNG chunk body")
        body = data[offset + 8 : offset + 8 + length]
        expected_crc = int.from_bytes(
            data[offset + 8 + length : end],
            "big",
        )
        actual_crc = binascii.crc32(chunk_type + body) & 0xFFFFFFFF
        try:
            type_name = chunk_type.decode("ascii")
        except UnicodeDecodeError as error:
            raise AuditError("non-ASCII PNG chunk type") from error
        chunks.append(
            {
                "type": type_name,
                "bytes": length,
                "crc32": f"{expected_crc:08x}",
                "crc_valid": expected_crc == actual_crc,
            }
        )
        if expected_crc != actual_crc:
            raise AuditError(f"invalid PNG chunk CRC: {type_name}")
        if chunk_type == b"IHDR":
            if ihdr is not None or length != 13:
                raise AuditError("invalid PNG IHDR inventory")
            (
                width,
                height,
                bit_depth,
                color_type,
                compression,
                filter_method,
                interlace,
            ) = struct.unpack(">IIBBBBB", body)
            ihdr = {
                "width": width,
                "height": height,
                "bit_depth": bit_depth,
                "color_type": color_type,
                "compression": compression,
                "filter": filter_method,
                "interlace": interlace,
            }
        elif chunk_type == b"tEXt":
            if b"\0" not in body:
                raise AuditError("invalid PNG tEXt chunk")
            keyword, value = body.split(b"\0", 1)
            text_chunks.append(
                {
                    "type": type_name,
                    "keyword": keyword.decode("latin-1"),
                    "text": value.decode("latin-1"),
                }
            )
        elif chunk_type in {b"zTXt", b"iTXt"}:
            text_chunks.append(
                {
                    "type": type_name,
                    "data_sha256": sha256(body),
                }
            )
        offset = end
        if chunk_type == b"IEND":
            if offset != len(data):
                raise AuditError("bytes follow PNG IEND")
            break
    if (
        ihdr is None
        or not chunks
        or chunks[0]["type"] != "IHDR"
        or chunks[-1]["type"] != "IEND"
    ):
        raise AuditError("invalid PNG chunk order")
    return {
        "ihdr": ihdr,
        "chunks": chunks,
        "chunk_types": [chunk["type"] for chunk in chunks],
        "text_chunks": text_chunks,
        "has_license_or_attribution_text": any(
            LICENSE_WORD.search(
                " ".join(
                    str(value)
                    for key, value in chunk.items()
                    if key != "type"
                )
            )
            for chunk in text_chunks
        ),
    }


def history_changes(commit: str, path: str) -> list[dict[str, Any]]:
    raw = run_git(
        "log",
        "--follow",
        "-M",
        "--format=@@%H",
        "--name-status",
        commit,
        "--",
        path,
    ).decode("utf-8")
    result = []
    current_commit = None
    for line in raw.splitlines():
        if line.startswith("@@"):
            current_commit = line[2:]
            result.append({"commit": current_commit, "changes": []})
            continue
        if not line or current_commit is None:
            continue
        fields = line.split("\t")
        status = fields[0]
        if status.startswith(("R", "C")) and len(fields) == 3:
            change = {
                "status": status,
                (
                    "old_path"
                    if status.startswith("R")
                    else "source_path"
                ): fields[1],
                (
                    "new_path"
                    if status.startswith("R")
                    else "destination_path"
                ): fields[2],
            }
        elif len(fields) == 2:
            change = {"status": status, "path": fields[1]}
        else:
            raise AuditError(
                f"unexpected git history status for {path}: {line}"
            )
        result[-1]["changes"].append(change)
    if not result or any(len(item["changes"]) != 1 for item in result):
        raise AuditError(f"unexpected Git history shape: {path}")
    return result


def commit_record(commit: str) -> dict[str, Any]:
    fields = run_git(
        "show",
        "-s",
        (
            "--format=%H%x00%P%x00%an%x00%ae%x00%aI%x00"
            "%cn%x00%ce%x00%cI%x00%s"
        ),
        commit,
    ).rstrip(b"\n").decode("utf-8").split("\0")
    if len(fields) != 9 or fields[0] != commit:
        raise AuditError(f"unexpected commit metadata: {commit}")
    raw_commit = run_git("cat-file", "commit", commit)
    if b"\n\n" not in raw_commit:
        raise AuditError(f"invalid commit object: {commit}")
    headers, message = raw_commit.split(b"\n\n", 1)
    license_data = git_show(commit, "LICENSE")
    return {
        "commit": commit,
        "parents": fields[1].split() if fields[1] else [],
        "author": {
            "name": fields[2],
            "email": fields[3],
            "date": fields[4],
        },
        "committer": {
            "name": fields[5],
            "email": fields[6],
            "date": fields[7],
        },
        "subject": fields[8],
        "message_sha256": sha256(message),
        "signed_off_by": [
            line.decode("utf-8", "replace")
            for line in message.splitlines()
            if line.lower().startswith(b"signed-off-by:")
        ],
        "gpg_signature_present": b"\ngpgsig " in b"\n" + headers,
        "root_license": {
            "path": "LICENSE",
            "git_blob_oid": git_blob_oid(license_data),
            "sha256": sha256(license_data),
            "declares_mit": b"MIT License" in license_data,
        },
    }


def policy_candidates(commit: str) -> list[str]:
    paths = run_git(
        "ls-tree",
        "-r",
        "--name-only",
        commit,
    ).decode("utf-8").splitlines()
    return sorted(
        path
        for path in paths
        if Path(path).name.casefold() in POLICY_BASENAMES
    )


def policy_report(commit: str) -> dict[str, Any]:
    records = []
    for path in policy_candidates(commit):
        data = git_show(commit, path)
        lowered = data.lower()
        records.append(
            {
                "path": path,
                "bytes": len(data),
                "sha256": sha256(data),
                "git_blob_oid": git_blob_oid(data),
                "mentions_license_or_copyright": any(
                    word in lowered
                    for word in (b"license", b"licence", b"copyright")
                ),
                "mentions_cla_dco_or_signoff": any(
                    word in lowered
                    for word in (
                        b"contributor license agreement",
                        b" cla ",
                        b"developer certificate of origin",
                        b" dco ",
                        b"signed-off-by",
                    )
                ),
            }
        )
    return {
        "commit": commit,
        "candidates": records,
        "candidate_count": len(records),
    }


def asset_introduction_commit(
    history: list[dict[str, Any]],
) -> str:
    for event in history:
        status = event["changes"][0]["status"]
        if status.startswith(("A", "C")):
            return event["commit"]
    raise AuditError("asset history lacks add/copy introduction")


def current_path_first_commit(commit: str, path: str) -> str:
    hashes = run_git(
        "log",
        "--format=%H",
        commit,
        "--",
        path,
    ).decode("ascii").splitlines()
    if not hashes:
        raise AuditError(f"current path lacks Git history: {path}")
    return hashes[-1]


def audit() -> dict[str, Any]:
    pinned_commit, lock_sha256 = read_lock()
    if run_git("cat-file", "-t", pinned_commit).strip() != b"commit":
        raise AuditError("pinned Detect-It-Easy commit is unavailable")
    runtime_assets, runtime_report_sha256 = read_runtime_assets()
    pinned_license = git_show(pinned_commit, "LICENSE")
    assets = []
    commit_hashes = set()
    software = Counter()
    for runtime_asset in runtime_assets:
        path = runtime_asset["path"]
        subtree_data = (DETECT_ROOT / path).read_bytes()
        original_data = git_show(pinned_commit, path)
        if subtree_data != original_data:
            raise AuditError(f"subtree/original blob mismatch: {path}")
        if (
            len(subtree_data) != runtime_asset["bytes"]
            or sha256(subtree_data) != runtime_asset["sha256"]
        ):
            raise AuditError(f"runtime report identity mismatch: {path}")
        png = parse_png(subtree_data)
        for chunk in png["text_chunks"]:
            if chunk.get("keyword") == "Software":
                software[chunk["text"]] += 1
        history = history_changes(pinned_commit, path)
        hashes = [item["commit"] for item in history]
        commit_hashes.update(hashes)
        assets.append(
            {
                "path": path,
                "bytes": len(subtree_data),
                "sha256": sha256(subtree_data),
                "git_blob_oid": git_blob_oid(subtree_data),
                "png": png,
                "history": {
                    "commit_count": len(history),
                    "lineage_first_commit": hashes[-1],
                    "last_change_commit": hashes[0],
                    "asset_introduction_commit": (
                        asset_introduction_commit(history)
                    ),
                    "current_path_first_commit": (
                        current_path_first_commit(
                            pinned_commit,
                            path,
                        )
                    ),
                    "changes_newest_first": history,
                },
            }
        )
    records_by_commit = {
        commit: commit_record(commit) for commit in commit_hashes
    }
    commits = sorted(
        records_by_commit.values(),
        key=lambda record: record["author"]["date"],
    )
    commit_by_hash = {
        record["commit"]: record for record in commits
    }
    for commit in commit_hashes:
        process = subprocess.run(
            [
                "git",
                "merge-base",
                "--is-ancestor",
                commit,
                pinned_commit,
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
        )
        if process.returncode != 0:
            raise AuditError(
                f"history commit is not pinned ancestor: {commit}"
            )
    lineage_first_counts = Counter(
        asset["history"]["lineage_first_commit"] for asset in assets
    )
    asset_introduction_counts = Counter(
        asset["history"]["asset_introduction_commit"]
        for asset in assets
    )
    current_path_first_counts = Counter(
        asset["history"]["current_path_first_commit"]
        for asset in assets
    )
    rename_assets = [
        asset["path"]
        for asset in assets
        if any(
            change["status"].startswith("R")
            for event in asset["history"]["changes_newest_first"]
            for change in event["changes"]
        )
    ]
    copy_assets = [
        asset["path"]
        for asset in assets
        if any(
            change["status"].startswith("C")
            for event in asset["history"]["changes_newest_first"]
            for change in event["changes"]
        )
    ]
    content_changes_after_add = [
        asset["path"]
        for asset in assets
        if any(
            change["status"].startswith("M")
            for event in asset["history"]["changes_newest_first"]
            for change in event["changes"]
        )
    ]
    contributor_identities = {
        (
            commit_by_hash[commit]["author"]["name"],
            commit_by_hash[commit]["author"]["email"],
        )
        for commit in commit_hashes
    }
    pinned_policy = policy_report(pinned_commit)
    origin_policies = [
        policy_report(record["commit"]) for record in commits
    ]
    limitations = [
        (
            "Git author and committer metadata attribute repository "
            "commits, not the underlying artwork authorship or source"
        ),
        (
            "repository-root MIT text at origin commits is evidence, "
            "not a legal conclusion for each PNG"
        ),
        (
            "CONTRIBUTING.md exists at the pinned commit but not at "
            "the two origin commits and contains no explicit license, "
            "CLA, DCO, or sign-off term"
        ),
        (
            "the two origin commits contain no GPG signature or "
            "Signed-off-by trailer"
        ),
        "the report does not include release-owner or legal approval",
    ]
    return {
        "schema_version": 1,
        "generator": GENERATOR,
        "generator_sha256": sha256((ROOT / GENERATOR).read_bytes()),
        "scope": {
            "repository": REPOSITORY,
            "commit": pinned_commit,
            "asset_root": "db/_icons",
            "asset_count": len(assets),
        },
        "identity": {
            "component_lock": "upstream/components.lock.toml",
            "component_lock_sha256": lock_sha256,
            "runtime_asset_report": (
                "docs/research/data/runtime-rule-assets-license.json"
            ),
            "runtime_asset_report_sha256": runtime_report_sha256,
            "pinned_root_license": {
                "path": "LICENSE",
                "git_blob_oid": git_blob_oid(pinned_license),
                "sha256": sha256(pinned_license),
                "declares_mit": b"MIT License" in pinned_license,
            },
        },
        "assets": assets,
        "history_commits": commits,
        "contribution_policy": {
            "pinned": pinned_policy,
            "origin_commits": origin_policies,
        },
        "summary": {
            "asset_count": len(assets),
            "unique_blob_count": len(
                {asset["git_blob_oid"] for asset in assets}
            ),
            "history_commit_count": len(commit_hashes),
            "lineage_first_counts": dict(
                sorted(lineage_first_counts.items())
            ),
            "asset_introduction_counts": dict(
                sorted(asset_introduction_counts.items())
            ),
            "current_path_first_counts": dict(
                sorted(current_path_first_counts.items())
            ),
            "rename_asset_count": len(rename_assets),
            "rename_assets": sorted(rename_assets),
            "copy_asset_count": len(copy_assets),
            "copy_assets": sorted(copy_assets),
            "content_change_after_add_count": len(
                content_changes_after_add
            ),
            "content_change_after_add_assets": sorted(
                content_changes_after_add
            ),
            "contributor_identity_count": len(
                contributor_identities
            ),
            "contributor_identities": [
                {"name": name, "email": email}
                for name, email in sorted(contributor_identities)
            ],
            "software_text_counts": dict(sorted(software.items())),
            "license_or_attribution_text_asset_count": sum(
                asset["png"]["has_license_or_attribution_text"]
                for asset in assets
            ),
        },
        "findings": {
            "all_subtree_bytes_match_pinned_original_blobs": True,
            "all_png_chunk_crcs_are_valid": True,
            "all_pngs_are_16x16_rgba8": all(
                asset["png"]["ihdr"]
                == {
                    "width": 16,
                    "height": 16,
                    "bit_depth": 8,
                    "color_type": 6,
                    "compression": 0,
                    "filter": 0,
                    "interlace": 0,
                }
                for asset in assets
            ),
            "all_history_commits_are_pinned_ancestors": True,
            "all_origin_commits_have_root_mit_text": all(
                record["root_license"]["declares_mit"]
                for record in commits
            ),
            "pinned_root_license_has_mit_text": (
                b"MIT License" in pinned_license
            ),
            "origin_license_blob_matches_pinned": all(
                record["root_license"]["git_blob_oid"]
                == git_blob_oid(pinned_license)
                for record in commits
            ),
            "asset_license_or_attribution_metadata_present": any(
                asset["png"]["has_license_or_attribution_text"]
                for asset in assets
            ),
            "pinned_contribution_policy_file_present": (
                pinned_policy["candidate_count"] > 0
            ),
            "origin_contribution_policy_file_present": any(
                policy["candidate_count"] > 0
                for policy in origin_policies
            ),
            "pinned_policy_explicit_license_or_dco_cla_present": any(
                record["mentions_license_or_copyright"]
                or record["mentions_cla_dco_or_signoff"]
                for record in pinned_policy["candidates"]
            ),
            "origin_commit_signature_or_signoff_present": any(
                record["gpg_signature_present"]
                or record["signed_off_by"]
                for record in commits
            ),
            "legal_review_complete": False,
            "limitations": limitations,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="machine-readable report path",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
