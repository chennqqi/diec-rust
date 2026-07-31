#!/usr/bin/env python3
"""Inspect one trusted upstream Mach-O deployment and its runtime rule assets."""

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

# otool -L line: <path> (compatibility version X, current version Y)
OTOOL_L_LINE = re.compile(
    r"^\s*(?P<path>\S+)\s+"
    r"\(compatibility version (?P<compat>[^,]+), "
    r"current version (?P<current>[^)]+)\)\s*$"
)

# otool -l LC_RPATH path line
RPATH_PATH = re.compile(r"^\s+path\s+(?P<path>\S+)\s+\(offset \d+\)\s*$")


class InspectionError(ValueError):
    """The Mach-O deployment cannot be measured without ambiguity."""


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


def parse_otool_l(raw: bytes) -> list[dict[str, str]]:
    """Parse otool -L output, skipping the first line (binary self-reference)."""
    text = raw.decode("utf-8", errors="strict")
    records: list[dict[str, str]] = []
    lines = text.splitlines()
    for line in lines[1:]:
        match = OTOOL_L_LINE.match(line)
        if match:
            records.append(
                {
                    "path": match.group("path"),
                    "compatibility_version": match.group("compat"),
                    "current_version": match.group("current"),
                }
            )
    return records


def parse_rpaths(raw: bytes) -> list[str]:
    """Parse otool -l output for LC_RPATH entries."""
    text = raw.decode("utf-8", errors="strict")
    rpaths: list[str] = []
    in_rpath = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "cmd LC_RPATH":
            in_rpath = True
            continue
        if in_rpath:
            match = RPATH_PATH.match(line)
            if match:
                rpaths.append(match.group("path"))
                in_rpath = False
    return rpaths


def resolve_dependency(
    raw_path: str,
    rpaths: list[str],
    executable: Path,
    loader_path: Path,
) -> Path | None:
    """Resolve a Mach-O dependency path to a real file path.

    Returns None for system libraries that exist only in the dyld shared
    cache and have no on-disk file (e.g. libSystem.B.dylib on macOS 12+).
    """
    if raw_path.startswith("@rpath/"):
        relative = raw_path[len("@rpath/") :]
        for rpath in rpaths:
            resolved = resolve_rpath_entry(rpath, relative, executable, loader_path)
            if resolved is not None:
                return resolved
        raise InspectionError(f"cannot resolve @rpath dependency: {raw_path}")
    if raw_path.startswith("@executable_path/"):
        relative = raw_path[len("@executable_path/") :]
        candidate = executable.parent / relative
        if candidate.exists():
            return candidate.resolve(strict=True)
        raise InspectionError(f"cannot resolve @executable_path: {raw_path}")
    if raw_path.startswith("@loader_path/"):
        relative = raw_path[len("@loader_path/") :]
        candidate = loader_path / relative
        if candidate.exists():
            return candidate.resolve(strict=True)
        raise InspectionError(f"cannot resolve @loader_path: {raw_path}")
    # Absolute path — may be a system library in the shared cache
    candidate = Path(raw_path)
    if candidate.exists():
        return candidate.resolve(strict=True)
    # System frameworks/dylibs in the shared cache have no on-disk binary
    if (
        raw_path.startswith("/System/Library/Frameworks/")
        or raw_path.startswith("/usr/lib/lib")
        or raw_path.startswith("/System/Library/PrivateFrameworks/")
    ):
        return None
    raise InspectionError(f"cannot resolve absolute dependency: {raw_path}")


def resolve_rpath_entry(
    rpath: str,
    relative: str,
    executable: Path,
    loader_path: Path,
) -> Path | None:
    """Resolve a single @rpath entry."""
    if rpath.startswith("@executable_path/"):
        base = executable.parent / rpath[len("@executable_path/") :]
    elif rpath.startswith("@loader_path/"):
        base = loader_path / rpath[len("@loader_path/") :]
    else:
        base = Path(rpath)
    candidate = base / relative
    if candidate.exists():
        try:
            return candidate.resolve(strict=True)
        except OSError:
            return None
    return None


def collect_dependencies(
    binary: Path,
    executable: Path,
    visited: set[str],
    direct_names: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Recursively collect all dynamic dependencies.

    Returns (on_disk_dependencies, system_shared_cache_entries).
    """
    dependencies: dict[str, dict[str, Any]] = {}
    system_cache: dict[str, dict[str, Any]] = {}

    def record_system_cache(name: str, is_direct: bool) -> None:
        key = name
        item = system_cache.setdefault(
            key,
            {
                "requested_name": name,
                "requested_names": set(),
                "direct": is_direct,
            },
        )
        item["requested_names"].add(name)
        if is_direct:
            item["direct"] = True

    def visit(
        path: Path,
        loader_path: Path,
        is_direct: bool,
        requested_name: str,
    ) -> None:
        real = path.resolve(strict=True)
        canonical = real.as_posix()
        if canonical in visited:
            if canonical in dependencies:
                if is_direct:
                    dependencies[canonical]["direct"] = True
                dependencies[canonical]["requested_names"].add(requested_name)
            return
        visited.add(canonical)
        otool_l = run_tool(["otool", "-L", str(real)])
        otool_l_output = run_tool(["otool", "-l", str(real)])
        rpaths = parse_rpaths(otool_l_output)
        deps = parse_otool_l(otool_l)
        item = dependencies.setdefault(
            canonical,
            {
                "real_path": canonical,
                "requested_names": set(),
                "resolved_paths": set(),
                "direct": is_direct,
            },
        )
        item["requested_names"].add(requested_name)
        item["resolved_paths"].add(path.as_posix())
        if is_direct:
            item["direct"] = True
        for dep in deps:
            dep_path = dep["path"]
            try:
                resolved = resolve_dependency(
                    dep_path, rpaths, executable, real.parent
                )
            except InspectionError:
                continue
            if resolved is None:
                record_system_cache(dep_path, dep_path in direct_names)
                continue
            is_dep_direct = dep_path in direct_names
            visit(resolved, real.parent, is_dep_direct, dep_path)

    otool_l = run_tool(["otool", "-L", str(binary)])
    otool_l_output = run_tool(["otool", "-l", str(binary)])
    rpaths = parse_rpaths(otool_l_output)
    deps = parse_otool_l(otool_l)
    for dep in deps:
        try:
            resolved = resolve_dependency(
                dep["path"], rpaths, executable, binary.parent
            )
        except InspectionError as error:
            raise InspectionError(
                f"cannot resolve direct dependency {dep['path']}: {error}"
            ) from error
        if resolved is None:
            record_system_cache(dep["path"], True)
            continue
        visit(resolved, binary.parent, True, dep["path"])

    result = []
    for canonical, item in sorted(dependencies.items()):
        path = Path(canonical)
        requested_names = sorted(item["requested_names"])
        result.append(
            {
                "bytes": path.stat().st_size,
                "direct": item["direct"],
                "real_path": canonical,
                "requested_names": requested_names,
                "resolved_paths": sorted(item["resolved_paths"]),
                "sha256": sha256_file(path),
            }
        )
    system_result = [
        {
            "direct": item["direct"],
            "requested_name": item["requested_name"],
            "requested_names": sorted(item["requested_names"]),
        }
        for key, item in sorted(system_cache.items())
    ]
    return result, system_result


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

    # Get direct dependencies
    otool_l = run_tool(["otool", "-L", str(binary)])
    direct_deps = parse_otool_l(otool_l)
    direct_needed = [dep["path"] for dep in direct_deps]

    # Collect full dependency closure
    dependencies, system_cache = collect_dependencies(
        binary, binary, set(), direct_needed
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
            "method": "otool -L plus otool -l rpath resolution on a trusted pinned Mach-O",
            "system_shared_cache": system_cache,
            "system_shared_cache_note": (
                "system frameworks and dylibs in the dyld shared cache "
                "have no on-disk binary file on macOS 12+"
            ),
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
        required=True,
    )
    parser.add_argument(
        "--detect-root",
        type=Path,
        required=True,
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
