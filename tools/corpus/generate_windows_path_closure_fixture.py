#!/usr/bin/env python3
"""Generate the hash-bound native-Windows path closure experiment plan."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


SCHEMA_VERSION = 1
CAPABILITY = "CAP-CLI-IN-003"
GENERATOR = (
    "tools/corpus/generate_windows_path_closure_fixture.py"
)
UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
PDF_SIZE = 331
PDF_SHA256 = (
    "47bd96bd99d3fd9d9edf09151f7c62999aaf71ed599bd975db9e46c4d6ef5d92"
)
TOCTOU_BLOCKER_COUNT = 128
TOCTOU_BLOCKER_SIZE = 1024 * 1024
TOCTOU_NEW_PAYLOAD = bytes(range(256)) * 16
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_manifest() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "capability": CAPABILITY,
        "generator": GENERATOR,
        "upstream_commit": UPSTREAM_COMMIT,
        "rules_commit": RULES_COMMIT,
        "license": (
            "project-generated paths and byte patterns; minimal PDF "
            "comes from the project-generated baseline corpus"
        ),
        "payload": {
            "source": "baseline-corpus/minimal.pdf",
            "size": PDF_SIZE,
            "sha256": PDF_SHA256,
        },
        "large_directory": {
            "reference_manifest": (
                "docs/research/data/large-path-fixture.json"
            ),
            "cases": [
                "empty_0",
                "single_1",
                "flat_256",
                "flat_4096",
                "nested_4096",
            ],
            "creation_order": "descending",
            "payload_size": 0,
            "payload_sha256": EMPTY_SHA256,
        },
        "reparse": {
            "kind": "ordinary-user directory junction",
            "cases": [
                "dangling_explicit",
                "dangling_parent",
                "two_node_cycle",
            ],
            "cycle_graph": {
                "a/to-b": "b",
                "b/to-a": "a",
            },
            "cycle_payloads": [
                "a/payload.pdf",
                "b/payload.pdf",
            ],
        },
        "toctou": {
            "kind": "directory junction target swap after enumeration",
            "blocker_count": TOCTOU_BLOCKER_COUNT,
            "blocker_size": TOCTOU_BLOCKER_SIZE,
            "blocker_payload_sha256": sha256(
                bytes(range(256))
                * (TOCTOU_BLOCKER_SIZE // 256)
            ),
            "stdout_sync_threshold_bytes": 4096,
            "old_target": {
                "size": 0,
                "sha256": EMPTY_SHA256,
            },
            "new_target": {
                "size": len(TOCTOU_NEW_PAYLOAD),
                "sha256": sha256(TOCTOU_NEW_PAYLOAD),
                "recipe": "bytes(range(256)) repeated 16 times",
            },
            "cases": [
                {
                    "name": "stable_old",
                    "action": "none",
                    "expected_open_target": "old",
                },
                {
                    "name": "stable_new",
                    "action": "none",
                    "expected_open_target": "new",
                },
                {
                    "name": "swap_old_to_new",
                    "action": "replace_junction_with_new_target",
                    "expected_open_target": "new",
                },
                {
                    "name": "remove_after_enumeration",
                    "action": "remove_junction",
                    "expected_open_target": "missing",
                },
            ],
        },
        "unc": {
            "provider": "WSL UNC redirector",
            "required_prefixes": [
                "\\\\wsl.localhost\\<distro>\\",
                "\\\\?\\UNC\\wsl.localhost\\<distro>\\",
            ],
            "cases": [
                "unc_file",
                "unc_directory",
                "extended_unc_file",
                "extended_unc_directory",
                "unc_missing",
                "unc_denied_file",
                "unc_denied_directory",
                "unc_directory_with_denied_child",
            ],
        },
        "acl": {
            "provider": "NTFS DACL applied to the current local user SID",
            "ace": "explicit deny (OI)(CI)F on a disposable directory",
            "cases": [
                "local_denied_file",
                "local_denied_directory",
                "local_directory_with_denied_child",
            ],
            "recovery": (
                "remove deny and reset the exact disposable directory "
                "before recursive cleanup"
            ),
        },
        "environment_classification": {
            "domain_identity": (
                "record whether the current account prefix equals the "
                "machine name; domain membership is descriptive"
            ),
            "administrative_share": (
                "record availability only; the experiment does not "
                "create or modify a machine SMB share"
            ),
            "source_contract": (
                "bind QFileInfo/QDir enumeration and the frozen-list "
                "open loop; verify no ACL/domain/UNC-specific branch"
            ),
        },
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
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    raw = serialize(build_manifest())
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(raw)
    sys.stdout.buffer.write(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
