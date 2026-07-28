#!/usr/bin/env python3
"""Generate a deterministic NTFS alternate-data-stream fixture."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys


SCHEMA_VERSION = 1
GENERATOR = "tools/corpus/generate_windows_ads_fixture.py"
DIRECTORY = "ads"
CARRIER_PATH = "ads/carrier.bin"
STREAM_NAME = "payload.pdf"
BASE_SOURCE = "plain.txt"
STREAM_SOURCE = "minimal.pdf"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_payload(baseline_dir: Path, name: str) -> bytes:
    manifest = json.loads(
        (baseline_dir / "manifest.json").read_text(encoding="utf-8")
    )
    samples = manifest.get("samples")
    if manifest.get("schema_version") != 1 or not isinstance(samples, list):
        raise ValueError("unsupported baseline corpus manifest")
    matches = [
        item
        for item in samples
        if isinstance(item, dict) and item.get("name") == name
    ]
    if len(matches) != 1:
        raise ValueError(f"baseline must contain one {name}")
    payload = (baseline_dir / name).read_bytes()
    if (
        len(payload) != matches[0].get("size")
        or sha256(payload) != matches[0].get("sha256")
    ):
        raise ValueError(f"baseline payload identity mismatch: {name}")
    return payload


def fixture_path(root: Path, relative: str) -> Path:
    if (
        not relative
        or "\\" in relative
        or relative.startswith("/")
        or ".." in relative.split("/")
    ):
        raise ValueError(f"unsafe fixture path: {relative!r}")
    return root.joinpath(*relative.split("/"))


def ads_path(carrier: Path) -> Path:
    return Path(f"{carrier}:{STREAM_NAME}")


def extended_path(path: Path) -> str:
    absolute = str(path.absolute())
    if absolute.startswith("\\\\"):
        return "\\\\?\\UNC\\" + absolute[2:]
    return "\\\\?\\" + absolute


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
        raise ValueError("unsupported Windows ADS fixture schema")
    if manifest.get("generator") != GENERATOR:
        raise ValueError("unexpected Windows ADS fixture generator")
    carrier_entry = manifest.get("carrier")
    stream_entry = manifest.get("named_stream")
    if not isinstance(carrier_entry, dict) or not isinstance(
        stream_entry,
        dict,
    ):
        raise ValueError("fixture manifest stream entries changed")

    carrier = fixture_path(root, str(carrier_entry.get("path", "")))
    stream = ads_path(carrier)
    base_data = carrier.read_bytes()
    stream_data = stream.read_bytes()
    if (
        len(base_data) != carrier_entry.get("size")
        or sha256(base_data) != carrier_entry.get("sha256")
    ):
        raise ValueError("carrier default stream identity mismatch")
    if (
        stream_entry.get("carrier_path") != carrier_entry.get("path")
        or stream_entry.get("stream_name") != STREAM_NAME
        or len(stream_data) != stream_entry.get("size")
        or sha256(stream_data) != stream_entry.get("sha256")
    ):
        raise ValueError("named stream identity mismatch")

    ordinary_files = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    if ordinary_files != {CARRIER_PATH}:
        raise ValueError("named stream appeared as an ordinary directory entry")


def generate(
    baseline_dir: Path,
    output_dir: Path,
    manifest_output: Path | None,
) -> dict[str, object]:
    if os.name != "nt":
        raise ValueError("native Windows fixture requires os.name == 'nt'")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("output directory must be absent or empty")
    base_payload = load_payload(baseline_dir, BASE_SOURCE)
    stream_payload = load_payload(baseline_dir, STREAM_SOURCE)
    output_dir.mkdir(parents=True, exist_ok=True)
    carrier = fixture_path(output_dir, CARRIER_PATH)
    carrier.parent.mkdir(parents=True, exist_ok=True)
    carrier.write_bytes(base_payload)
    try:
        ads_path(carrier).write_bytes(stream_payload)
    except OSError as error:
        raise ValueError(
            "fixture filesystem does not support NTFS named streams"
        ) from error

    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "generator": GENERATOR,
        "license": "baseline corpus bytes in project-generated NTFS streams",
        "directory": DIRECTORY,
        "carrier": {
            "path": CARRIER_PATH,
            "source": BASE_SOURCE,
            "size": len(base_payload),
            "sha256": sha256(base_payload),
        },
        "named_stream": {
            "carrier_path": CARRIER_PATH,
            "stream_name": STREAM_NAME,
            "display_path": f"{CARRIER_PATH}:{STREAM_NAME}",
            "source": STREAM_SOURCE,
            "size": len(stream_payload),
            "sha256": sha256(stream_payload),
        },
        "filesystem_contract": {
            "named_stream_readable": True,
            "named_stream_not_an_ordinary_directory_entry": True,
        },
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
