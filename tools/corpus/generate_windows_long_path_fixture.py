#!/usr/bin/env python3
"""Generate deterministic paths longer than MAX_PATH on native Windows."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys


SCHEMA_VERSION = 1
GENERATOR = "tools/corpus/generate_windows_long_path_fixture.py"
SOURCE_NAME = "minimal.pdf"
MAX_PATH = 260
SEGMENTS = tuple(
    f"level-{index:02d}-" + chr(ord("a") + index) * 40
    for index in range(6)
)
CONTROL_PATH = "control/target.pdf"
EXPLICIT_PATH = "/".join(("explicit-root", *SEGMENTS, "target.pdf"))
DISCOVERY_PATH = "/".join(
    ("discovery-root", *SEGMENTS, "target.pdf")
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_payload(baseline_dir: Path) -> bytes:
    manifest = json.loads(
        (baseline_dir / "manifest.json").read_text(encoding="utf-8")
    )
    samples = manifest.get("samples")
    if manifest.get("schema_version") != 1 or not isinstance(samples, list):
        raise ValueError("unsupported baseline corpus manifest")
    matches = [
        item
        for item in samples
        if isinstance(item, dict) and item.get("name") == SOURCE_NAME
    ]
    if len(matches) != 1:
        raise ValueError(f"baseline must contain one {SOURCE_NAME}")
    payload = (baseline_dir / SOURCE_NAME).read_bytes()
    if (
        len(payload) != matches[0].get("size")
        or sha256(payload) != matches[0].get("sha256")
    ):
        raise ValueError("baseline payload identity mismatch")
    return payload


def extended_path(path: Path) -> str:
    absolute = str(path.absolute())
    if absolute.startswith("\\\\"):
        return "\\\\?\\UNC\\" + absolute[2:]
    return "\\\\?\\" + absolute


def fixture_path(root: Path, relative: str) -> Path:
    if (
        not relative
        or "\\" in relative
        or relative.startswith("/")
        or ".." in relative.split("/")
    ):
        raise ValueError(f"unsafe fixture path: {relative!r}")
    return root.joinpath(*relative.split("/"))


def write_long_file(path: Path, payload: bytes) -> None:
    extended = Path(extended_path(path))
    extended.parent.mkdir(parents=True, exist_ok=True)
    extended.write_bytes(payload)


def read_long_file(path: Path) -> bytes:
    return Path(extended_path(path)).read_bytes()


def serialize_manifest(manifest: dict[str, object]) -> bytes:
    return (
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def validate_fixture(root: Path, manifest: dict[str, object]) -> None:
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported Windows long-path fixture schema")
    if manifest.get("generator") != GENERATOR:
        raise ValueError("unexpected Windows long-path fixture generator")
    entries = manifest.get("files")
    if not isinstance(entries, list) or len(entries) != 3:
        raise ValueError("fixture manifest files changed")
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("invalid fixture file entry")
        relative = str(entry.get("path", ""))
        path = fixture_path(root, relative)
        data = (
            read_long_file(path)
            if bool(entry.get("long_path"))
            else path.read_bytes()
        )
        if (
            len(data) != entry.get("size")
            or sha256(data) != entry.get("sha256")
            or len(relative) != entry.get("relative_code_units")
        ):
            raise ValueError(f"fixture file mismatch: {relative!r}")
        if bool(entry.get("long_path")) != (len(relative) > MAX_PATH):
            raise ValueError(f"long-path classification mismatch: {relative!r}")


def generate(
    baseline_dir: Path,
    output_dir: Path,
    manifest_output: Path | None,
) -> dict[str, object]:
    if os.name != "nt":
        raise ValueError("native Windows fixture requires os.name == 'nt'")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("output directory must be absent or empty")
    payload = load_payload(baseline_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    files = []
    for case_id, relative in (
        ("control", CONTROL_PATH),
        ("explicit", EXPLICIT_PATH),
        ("discovery", DISCOVERY_PATH),
    ):
        path = fixture_path(output_dir, relative)
        is_long = len(relative) > MAX_PATH
        if is_long:
            write_long_file(path, payload)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        files.append(
            {
                "id": case_id,
                "path": relative,
                "relative_code_units": len(relative),
                "long_path": is_long,
                "size": len(payload),
                "sha256": sha256(payload),
            }
        )

    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "generator": GENERATOR,
        "license": "project-generated paths; baseline corpus bytes only",
        "max_path_reference": MAX_PATH,
        "payload": {
            "source": SOURCE_NAME,
            "size": len(payload),
            "sha256": sha256(payload),
        },
        "segments": list(SEGMENTS),
        "files": files,
        "guarantee": (
            "each long relative path alone exceeds MAX_PATH, so every "
            "absolute materialization remains over MAX_PATH"
        ),
    }
    serialized = serialize_manifest(manifest)
    (output_dir / "manifest.json").write_bytes(serialized)
    if manifest_output is not None:
        manifest_output.parent.mkdir(parents=True, exist_ok=True)
        manifest_output.write_bytes(serialized)
    validate_fixture(output_dir, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--manifest-output", type=Path)
    args = parser.parse_args()
    manifest = generate(
        args.baseline_dir.resolve(strict=True),
        args.output_dir.resolve(),
        (
            args.manifest_output.resolve()
            if args.manifest_output is not None
            else None
        ),
    )
    json.dump(manifest, sys.stdout, ensure_ascii=True, indent=2, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
