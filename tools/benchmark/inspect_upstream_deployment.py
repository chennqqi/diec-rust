#!/usr/bin/env python3
"""Inspect one trusted upstream ELF deployment and its runtime rule assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
from typing import Any


SCHEMA_VERSION = 1
RUNTIME_TREES = ("db", "db_extra", "db_custom")
NEEDED = re.compile(r"\(NEEDED\).*Shared library: \[(?P<name>[^\]]+)\]")
LDD_ARROW = re.compile(
    r"^(?P<name>\S+)\s+=>\s+(?P<path>/\S+)\s+\(0x[0-9a-fA-F]+\)$"
)
LDD_LOADER = re.compile(r"^(?P<path>/\S+)\s+\(0x[0-9a-fA-F]+\)$")
LDD_PSEUDO = re.compile(r"^(?P<name>\S+)\s+\(0x[0-9a-fA-F]+\)$")


class InspectionError(ValueError):
    """The ELF deployment cannot be measured without ambiguity."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def run_tool(arguments: list[str]) -> bytes:
    completed = subprocess.run(arguments, capture_output=True)
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace")
        raise InspectionError(
            f"{arguments[0]} exited {completed.returncode}: {stderr}"
        )
    if completed.stderr:
        raise InspectionError(f"{arguments[0]} emitted stderr")
    return completed.stdout


def parse_needed(raw: bytes) -> list[str]:
    text = raw.decode("utf-8", errors="strict")
    names = [
        match.group("name")
        for line in text.splitlines()
        if (match := NEEDED.search(line))
    ]
    if not names or len(names) != len(set(names)):
        raise InspectionError("DT_NEEDED entries are empty or duplicated")
    return names


def parse_ldd(raw: bytes) -> list[dict[str, str]]:
    text = raw.decode("utf-8", errors="strict")
    records: list[dict[str, str]] = []
    for source_line in text.splitlines():
        line = source_line.strip()
        if not line:
            continue
        if "=> not found" in line:
            raise InspectionError(f"unresolved dependency: {line}")
        arrow = LDD_ARROW.fullmatch(line)
        if arrow:
            records.append(
                {
                    "requested_name": arrow.group("name"),
                    "resolved_path": arrow.group("path"),
                }
            )
            continue
        loader = LDD_LOADER.fullmatch(line)
        if loader:
            path = loader.group("path")
            records.append(
                {
                    "requested_name": Path(path).name,
                    "resolved_path": path,
                }
            )
            continue
        pseudo = LDD_PSEUDO.fullmatch(line)
        if pseudo and pseudo.group("name").startswith("linux-vdso."):
            continue
        raise InspectionError(f"unsupported ldd output line: {line}")
    if not records:
        raise InspectionError("ldd returned no real dependencies")
    return records


def dependency_inventory(
    records: list[dict[str, str]],
    direct_needed: list[str],
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for record in records:
        source = Path(record["resolved_path"])
        try:
            real = source.resolve(strict=True)
        except OSError as error:
            raise InspectionError(
                f"cannot resolve dependency {source}: {error}"
            ) from error
        if not real.is_file():
            raise InspectionError(f"dependency is not a file: {real}")
        canonical = real.as_posix()
        item = grouped.setdefault(
            canonical,
            {
                "real_path": canonical,
                "requested_names": set(),
                "resolved_paths": set(),
            },
        )
        item["requested_names"].add(record["requested_name"])
        item["resolved_paths"].add(source.as_posix())

    result = []
    direct = set(direct_needed)
    for canonical, item in sorted(grouped.items()):
        path = Path(canonical)
        requested_names = sorted(item["requested_names"])
        result.append(
            {
                "bytes": path.stat().st_size,
                "direct": bool(direct.intersection(requested_names)),
                "real_path": canonical,
                "requested_names": requested_names,
                "resolved_paths": sorted(item["resolved_paths"]),
                "sha256": sha256_file(path),
            }
        )
    return result


def iter_tree_files(root: Path, tree: str) -> list[Path]:
    tree_root = root / tree
    if not tree_root.is_dir():
        raise InspectionError(f"missing runtime rule tree: {tree_root}")
    candidates = list(tree_root.rglob("*"))
    links = [path for path in candidates if path.is_symlink()]
    if links:
        raise InspectionError(
            f"runtime rule tree contains symlink: {links[0]}"
        )
    return sorted(
        (path for path in candidates if path.is_file()),
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


def rule_inventory(root: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    all_files: list[Path] = []
    trees = []
    for tree in RUNTIME_TREES:
        files = iter_tree_files(root, tree)
        all_files.extend(files)
        trees.append(
            {
                "bytes": sum(path.stat().st_size for path in files),
                "file_count": len(files),
                "path": tree,
                "tree_sha256": tree_digest(root, files),
            }
        )
    return {
        "bytes": sum(path.stat().st_size for path in all_files),
        "combined_tree_sha256": tree_digest(root, all_files),
        "file_count": len(all_files),
        "root": root.as_posix(),
        "trees": trees,
    }


def inspect(binary: Path, detect_root: Path) -> dict[str, Any]:
    binary = binary.resolve(strict=True)
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise InspectionError(f"binary is not executable: {binary}")
    readelf = run_tool(["readelf", "-d", str(binary)])
    ldd = run_tool(["ldd", str(binary)])
    direct_needed = parse_needed(readelf)
    records = parse_ldd(ldd)
    dependencies = dependency_inventory(records, direct_needed)
    resolved_names = {
        name
        for dependency in dependencies
        for name in dependency["requested_names"]
    }
    missing_direct = sorted(set(direct_needed) - resolved_names)
    if missing_direct:
        raise InspectionError(
            f"direct dependencies absent from ldd closure: {missing_direct}"
        )

    binary_bytes = binary.stat().st_size
    dependency_bytes = sum(item["bytes"] for item in dependencies)
    rules = rule_inventory(detect_root)
    rules_bytes = rules["bytes"]
    return {
        "binary": {
            "bytes": binary_bytes,
            "direct_needed": direct_needed,
            "path": binary.as_posix(),
            "sha256": sha256_file(binary),
        },
        "dynamic_dependencies": {
            "accounting": "unique resolved real files, symlink aliases deduplicated",
            "closure_sha256": sha256_bytes(canonical_json(dependencies)),
            "dependencies": dependencies,
            "file_count": len(dependencies),
            "method": "readelf -d plus ldd on a trusted pinned ELF",
            "total_bytes": dependency_bytes,
        },
        "host": {
            "machine": platform.machine(),
            "system": platform.system(),
        },
        "rules": rules,
        "schema_version": SCHEMA_VERSION,
        "totals": {
            "binary_and_dependencies_bytes": (
                binary_bytes + dependency_bytes
            ),
            "binary_and_rules_bytes": binary_bytes + rules_bytes,
            "full_closure_and_rules_bytes": (
                binary_bytes + dependency_bytes + rules_bytes
            ),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--binary",
        type=Path,
        default=Path("/opt/die-build/src/console/diec"),
    )
    parser.add_argument(
        "--detect-root",
        type=Path,
        default=Path("/opt/die-source/Detect-It-Easy"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = inspect(args.binary, args.detect_root)
    except (InspectionError, OSError) as error:
        print(f"deployment inspection error: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
