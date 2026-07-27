#!/usr/bin/env python3
"""Audit the pinned Detect-It-Easy runtime rule distribution trees."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import tomllib
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DETECT_ROOT = ROOT / "upstream" / "Detect-It-Easy"
DEFAULT_OUTPUT = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "runtime-rule-assets-license.json"
)
COMPONENT_LOCK = ROOT / "upstream" / "components.lock.toml"
RUNTIME_TREES = ("db", "db_extra", "db_custom")
PROGRAM_SUFFIXES = {"", ".sg"}
TEXT_SUFFIXES = {"", ".ini", ".json", ".sg", ".txt"}

AUTHOR_LINE = re.compile(
    r"^\s*(?://+|/\*+|\*+|#+|;+)?\s*Author(?:s)?\s*:\s*(.+?)\s*(?:\*/)?$",
    re.IGNORECASE,
)
COPYRIGHT_LINE = re.compile(r"copyright\s*(?:\(c\)|©)?", re.IGNORECASE)
URL = re.compile(r"https?://[^\s<>'\"\])}]+", re.IGNORECASE)
LICENSE_PATTERNS = {
    "spdx": re.compile(r"SPDX-License-Identifier\s*:", re.IGNORECASE),
    "mit": re.compile(r"\bMIT License\b", re.IGNORECASE),
    "gpl": re.compile(
        r"\b(?:GNU\s+General\s+Public\s+License|GNU[- ]?GPL|GPLv[123])\b",
        re.IGNORECASE,
    ),
    "apache": re.compile(r"\bApache License(?:,?\s+Version)?\b", re.IGNORECASE),
    "bsd": re.compile(r"\bBSD License\b", re.IGNORECASE),
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_component_lock() -> tuple[dict[str, object], str]:
    raw = COMPONENT_LOCK.read_bytes()
    return tomllib.loads(raw.decode("utf-8")), sha256_bytes(raw)


def normalized_extension(path: Path) -> str:
    return path.suffix.lower() or "<none>"


def iter_tree_files(root: Path, tree: str) -> list[Path]:
    tree_root = root / tree
    if not tree_root.is_dir():
        raise ValueError(f"missing runtime rule tree: {tree_root}")
    return sorted(
        (path for path in tree_root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix().encode("utf-8"),
    )


def tree_digest(root: Path, files: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        data = path.read_bytes()
        digest.update(relative)
        digest.update(b"\0")
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
        digest.update(bytes.fromhex(sha256_bytes(data)))
    return digest.hexdigest()


def decode_text(path: Path, data: bytes) -> str | None:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return None
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace")


def marker_lines(
    relative: str,
    text: str,
) -> tuple[list[dict[str, object]], list[str], list[str], Counter[str]]:
    license_markers: list[dict[str, object]] = []
    authors: list[str] = []
    copyright_lines: list[str] = []
    domains: Counter[str] = Counter()
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        is_comment = stripped.startswith(("//", "/*", "*", "#", ";"))
        author = AUTHOR_LINE.match(line)
        if author:
            authors.append(author.group(1).strip())
        if is_comment and COPYRIGHT_LINE.search(line):
            copyright_lines.append(stripped)
        for marker, pattern in LICENSE_PATTERNS.items():
            if is_comment and pattern.search(line):
                license_markers.append(
                    {
                        "path": relative,
                        "line": line_number,
                        "marker": marker,
                        "text": stripped,
                    }
                )
        for raw_url in URL.findall(line) if is_comment else ():
            try:
                domain = (urlparse(raw_url).hostname or "").lower()
            except ValueError:
                domain = "<invalid-url>"
            if domain:
                domains[domain] += 1
    return license_markers, authors, copyright_lines, domains


def audit(detect_root: Path) -> dict[str, object]:
    detect_root = detect_root.resolve()
    lock, lock_sha256 = read_component_lock()
    pinned_commit = lock["gitlink"]["Detect-It-Easy"]["commit"]
    license_path = detect_root / "LICENSE"
    if not license_path.is_file():
        raise ValueError(f"missing Detect-It-Easy LICENSE: {license_path}")
    license_bytes = license_path.read_bytes()
    if b"MIT License" not in license_bytes:
        raise ValueError("Detect-It-Easy root LICENSE is not the expected MIT text")

    all_files: list[Path] = []
    tree_reports: list[dict[str, object]] = []
    extension_counts: Counter[str] = Counter()
    license_markers: list[dict[str, object]] = []
    author_paths: defaultdict[str, set[str]] = defaultdict(set)
    copyright_paths: set[str] = set()
    url_domains: Counter[str] = Counter()
    binary_assets: list[dict[str, object]] = []

    for tree in RUNTIME_TREES:
        files = iter_tree_files(detect_root, tree)
        all_files.extend(files)
        tree_extensions = Counter(normalized_extension(path) for path in files)
        extension_counts.update(tree_extensions)
        tree_reports.append(
            {
                "path": tree,
                "file_count": len(files),
                "byte_count": sum(path.stat().st_size for path in files),
                "tree_sha256": tree_digest(detect_root, files),
                "extension_counts": dict(sorted(tree_extensions.items())),
            }
        )
        for path in files:
            relative = path.relative_to(detect_root).as_posix()
            data = path.read_bytes()
            text = decode_text(path, data)
            if text is None:
                binary_assets.append(
                    {
                        "path": relative,
                        "bytes": len(data),
                        "sha256": sha256_bytes(data),
                    }
                )
                continue
            markers, authors, copyright_lines, domains = marker_lines(
                relative,
                text,
            )
            license_markers.extend(markers)
            for author in authors:
                author_paths[author].add(relative)
            if copyright_lines:
                copyright_paths.add(relative)
            url_domains.update(domains)

    program_files = [
        path for path in all_files if path.suffix.lower() in PROGRAM_SUFFIXES
    ]
    non_program_files = [
        path for path in all_files if path.suffix.lower() not in PROGRAM_SUFFIXES
    ]
    combined_digest = tree_digest(detect_root, all_files)
    authors = [
        {
            "author": author,
            "file_count": len(paths),
            "paths_sha256": sha256_bytes(
                "\n".join(sorted(paths)).encode("utf-8")
            ),
        }
        for author, paths in sorted(
            author_paths.items(),
            key=lambda item: (-len(item[1]), item[0].casefold()),
        )
    ]
    return {
        "schema_version": 1,
        "scope": {
            "repository": "https://github.com/horsicq/Detect-It-Easy.git",
            "commit": pinned_commit,
            "trees": list(RUNTIME_TREES),
            "purpose": "runtime rule distribution assets used by diec CLI",
            "excludes": [
                "yara_rules",
                "peid_rules",
                "dbs_min",
                "dbs_special",
            ],
        },
        "identity": {
            "component_lock": "upstream/components.lock.toml",
            "component_lock_sha256": lock_sha256,
            "root_license": "upstream/Detect-It-Easy/LICENSE",
            "root_license_sha256": sha256_bytes(license_bytes),
            "root_license_declared": "MIT",
            "combined_tree_sha256": combined_digest,
        },
        "inventory": {
            "file_count": len(all_files),
            "byte_count": sum(path.stat().st_size for path in all_files),
            "program_file_count": len(program_files),
            "program_byte_count": sum(
                path.stat().st_size for path in program_files
            ),
            "non_program_file_count": len(non_program_files),
            "extension_counts": dict(sorted(extension_counts.items())),
            "trees": tree_reports,
        },
        "visible_markers": {
            "license_markers": sorted(
                license_markers,
                key=lambda marker: (marker["path"], marker["line"]),
            ),
            "license_marker_counts": dict(
                sorted(
                    Counter(
                        marker["marker"] for marker in license_markers
                    ).items()
                )
            ),
            "author_marker_file_count": len(
                {path for paths in author_paths.values() for path in paths}
            ),
            "unique_author_marker_count": len(author_paths),
            "authors": authors,
            "copyright_marker_file_count": len(copyright_paths),
            "url_domain_counts": dict(
                sorted(url_domains.items(), key=lambda item: (-item[1], item[0]))
            ),
        },
        "binary_assets": binary_assets,
        "findings": {
            "all_runtime_assets_covered_by_tree_hash": True,
            "root_mit_license_present": True,
            "explicit_non_mit_license_marker_count": sum(
                marker["marker"] not in {"mit", "spdx"}
                for marker in license_markers
            ),
            "binary_asset_count": len(binary_assets),
            "legal_review_complete": False,
            "limitations": [
                "repository-root MIT text is evidence, not a legal conclusion for every contribution",
                "author and URL comments do not establish third-party source-license provenance",
                "binary PNG origins are not established by textual marker scanning",
                "the report does not include a release-owner or legal approval",
            ],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--detect-root",
        type=Path,
        default=DEFAULT_DETECT_ROOT,
        help="pinned Detect-It-Easy subtree root",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="machine-readable report path",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = audit(args.detect_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
