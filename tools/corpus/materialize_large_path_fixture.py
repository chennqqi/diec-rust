#!/usr/bin/env python3
"""Materialize and validate the deterministic large-directory fixture."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any, Iterable


GENERATOR = "tools/corpus/generate_large_path_fixture.py"
MANIFEST = "docs/research/data/large-path-fixture.json"


class FixtureError(ValueError):
    """The large-directory fixture cannot be materialized safely."""


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_generator(root: Path) -> Any:
    path = root / GENERATOR
    spec = importlib.util.spec_from_file_location(
        "large_path_fixture_generator_for_materializer", path
    )
    if spec is None or spec.loader is None:
        raise FixtureError("cannot load large-path fixture generator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_manifest(
    root: Path, manifest_path: Path
) -> tuple[dict[str, Any], bytes]:
    raw = manifest_path.read_bytes()
    generator = load_generator(root)
    expected = generator.serialize(generator.build_manifest())
    if raw != expected:
        raise FixtureError("large-path fixture manifest differs")
    manifest = json.loads(raw)
    return manifest, raw


def relative_files(case: dict[str, Any]) -> Iterable[str]:
    count = case["file_count"]
    if case["layout"] == "flat":
        for index in range(count):
            yield f"item-{index:06d}.empty"
        return
    for bucket in range(case["bucket_count"]):
        for index in range(case["files_per_bucket"]):
            yield (
                f"bucket-{bucket:03d}/"
                f"item-{index:06d}.empty"
            )


def root_entries(case: dict[str, Any]) -> list[str]:
    if case["layout"] == "flat":
        return list(relative_files(case))
    return [
        f"bucket-{index:03d}"
        for index in range(case["bucket_count"])
    ]


def sequence_sha256(values: list[str]) -> str:
    raw = ("\n".join(values) + ("\n" if values else "")).encode()
    return sha256(raw)


def preflight(case: dict[str, Any]) -> dict[str, Any]:
    files = list(relative_files(case))
    entries = root_entries(case)
    return {
        "file_count": len(files),
        "first_file": files[0] if files else None,
        "last_file": files[-1] if files else None,
        "file_sequence_sha256": sequence_sha256(files),
        "root_entry_count": len(entries),
        "first_root_entry": entries[0] if entries else None,
        "last_root_entry": entries[-1] if entries else None,
        "root_entry_sequence_sha256": sequence_sha256(entries),
    }


def materialize_case(case: dict[str, Any], directory: Path) -> None:
    directory.mkdir()
    if case["layout"] == "flat":
        for index in range(case["file_count"] - 1, -1, -1):
            (directory / f"item-{index:06d}.empty").touch()
        return
    for bucket in range(case["bucket_count"] - 1, -1, -1):
        bucket_dir = directory / f"bucket-{bucket:03d}"
        bucket_dir.mkdir()
        for index in range(case["files_per_bucket"] - 1, -1, -1):
            (bucket_dir / f"item-{index:06d}.empty").touch()


def validate_case(
    case: dict[str, Any], directory: Path
) -> dict[str, Any]:
    if directory.is_symlink() or not directory.is_dir():
        raise FixtureError(f"case directory missing: {case['name']}")
    actual_files = sorted(
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file() and not path.is_symlink()
    )
    expected_files = list(relative_files(case))
    if actual_files != expected_files:
        raise FixtureError(f"case file inventory differs: {case['name']}")
    actual_entries = sorted(path.name for path in directory.iterdir())
    if actual_entries != root_entries(case):
        raise FixtureError(f"case root inventory differs: {case['name']}")
    for path in directory.rglob("*"):
        if path.is_symlink():
            raise FixtureError(f"fixture contains symlink: {path}")
        if path.is_file() and path.stat().st_size != 0:
            raise FixtureError(f"fixture payload is not empty: {path}")
    return preflight(case)


def validate_materialized(
    manifest: dict[str, Any], output_dir: Path
) -> dict[str, Any]:
    expected_names = [case["name"] for case in manifest["cases"]]
    actual_names = sorted(path.name for path in output_dir.iterdir())
    if actual_names != sorted(expected_names):
        raise FixtureError("large-path case directory inventory differs")
    return {
        case["name"]: validate_case(case, output_dir / case["name"])
        for case in manifest["cases"]
    }


def materialize(
    root: Path, manifest_path: Path, output_dir: Path
) -> dict[str, Any]:
    manifest, manifest_raw = load_manifest(root, manifest_path)
    if output_dir.exists():
        if output_dir.is_symlink() or not output_dir.is_dir():
            raise FixtureError("output path is not a real directory")
        if any(output_dir.iterdir()):
            raise FixtureError("output directory must be empty")
    else:
        output_dir.mkdir(parents=True)
    for case in manifest["cases"]:
        materialize_case(case, output_dir / case["name"])
    preflights = validate_materialized(manifest, output_dir)
    return {
        "schema_version": 1,
        "generator": "tools/corpus/materialize_large_path_fixture.py",
        "manifest": MANIFEST,
        "manifest_sha256": sha256(manifest_raw),
        "local_path": str(output_dir.resolve()),
        "cases": preflights,
    }


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=root / MANIFEST,
    )
    parser.set_defaults(root=root)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = materialize(
            args.root.resolve(),
            args.manifest.resolve(strict=True),
            args.output_dir.resolve(),
        )
    except (FixtureError, OSError, ValueError) as error:
        print(f"large-path fixture error: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            report,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
