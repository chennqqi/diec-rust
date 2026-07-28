#!/usr/bin/env python3
"""Generate a deterministic plan for large-directory path probes."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from typing import Any


SCHEMA_VERSION = 1
GENERATOR = "tools/corpus/generate_large_path_fixture.py"
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
CASES = (
    {
        "name": "empty_0",
        "layout": "flat",
        "file_count": 0,
        "bucket_count": 0,
        "files_per_bucket": 0,
    },
    {
        "name": "single_1",
        "layout": "flat",
        "file_count": 1,
        "bucket_count": 0,
        "files_per_bucket": 0,
    },
    {
        "name": "flat_256",
        "layout": "flat",
        "file_count": 256,
        "bucket_count": 0,
        "files_per_bucket": 0,
    },
    {
        "name": "flat_4096",
        "layout": "flat",
        "file_count": 4096,
        "bucket_count": 0,
        "files_per_bucket": 0,
    },
    {
        "name": "nested_4096",
        "layout": "nested",
        "file_count": 4096,
        "bucket_count": 16,
        "files_per_bucket": 256,
    },
)


def build_manifest() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generator": GENERATOR,
        "license": "project-generated empty files and path names",
        "materialization": {
            "file_name_pattern": "item-{index:06d}.empty",
            "bucket_name_pattern": "bucket-{index:03d}",
            "creation_order": "descending",
            "payload_size": 0,
            "payload_sha256": EMPTY_SHA256,
        },
        "cases": [dict(case) for case in CASES],
    }


def serialize(manifest: dict[str, Any]) -> bytes:
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()
    manifest = build_manifest()
    raw = serialize(manifest)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(raw)
    sys.stdout.buffer.write(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
