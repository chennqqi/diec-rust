#!/usr/bin/env python3
"""Generate a deterministic plan for path enumeration/open TOCTOU probes."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from typing import Any


SCHEMA_VERSION = 1
GENERATOR = "tools/corpus/generate_path_toctou_fixture.py"
BLOCKER_SIZE = 32 * 1024 * 1024
NEW_PAYLOAD = bytes(range(256)) * 16
CASES = (
    {
        "name": "stable_old",
        "initial_target": "../targets/old.bin",
        "action": "none",
        "expected_open_target": "old",
    },
    {
        "name": "stable_new",
        "initial_target": "../targets/new.bin",
        "action": "none",
        "expected_open_target": "new",
    },
    {
        "name": "swap_old_to_new",
        "initial_target": "../targets/old.bin",
        "action": "replace_symlink_with_new_target",
        "expected_open_target": "new",
    },
    {
        "name": "remove_old_after_enumeration",
        "initial_target": "../targets/old.bin",
        "action": "unlink_symlink",
        "expected_open_target": "missing",
    },
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def zero_sha256(size: int) -> str:
    digest = hashlib.sha256()
    block = b"\0" * (1024 * 1024)
    whole, remainder = divmod(size, len(block))
    for _ in range(whole):
        digest.update(block)
    digest.update(block[:remainder])
    return digest.hexdigest()


def build_manifest() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generator": GENERATOR,
        "license": "project-generated paths and byte patterns",
        "materialization": {
            "case_directory": "/work/case",
            "blocker": {
                "path": "/work/case/a-blocker.bin",
                "kind": "sparse_zero_file",
                "size": BLOCKER_SIZE,
                "sha256": zero_sha256(BLOCKER_SIZE),
            },
            "link": {
                "path": "/work/case/z-link.bin",
                "kind": "symlink",
            },
            "old_target": {
                "path": "/work/targets/old.bin",
                "size": 0,
                "sha256": sha256(b""),
            },
            "new_target": {
                "path": "/work/targets/new.bin",
                "size": len(NEW_PAYLOAD),
                "sha256": sha256(NEW_PAYLOAD),
                "recipe": "bytes(range(256)) repeated 16 times",
            },
        },
        "synchronization": {
            "stdout": "stdbuf -oL",
            "stop_after_line": "/work/case/a-blocker.bin:",
            "stop_signal": "SIGSTOP",
            "resume_signal": "SIGCONT",
            "mutation": "after waitpid(WUNTRACED), before SIGCONT",
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
    raw = serialize(build_manifest())
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(raw)
    sys.stdout.buffer.write(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
