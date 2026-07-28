#!/usr/bin/env python3
"""Generate a deterministic raw-name plan for locale/filesystem probes."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from typing import Any


SCHEMA_VERSION = 1
GENERATOR = "tools/corpus/generate_path_locale_fixture.py"
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
LOCALES = ("C", "C.utf8", "POSIX")
FILESYSTEMS = (
    {
        "name": "tmpfs",
        "docker_mount": "tmpfs",
        "expected_type": "tmpfs",
    },
    {
        "name": "volume",
        "docker_mount": "anonymous-volume",
        "expected_type": "ext2/ext3",
    },
)
NAMES = (
    ("leading_space", " leading-space.empty", False),
    ("leading_dash", "--leading-dash.empty", False),
    ("digit", "00-digit.empty", False),
    ("ascii_upper_a", "A-case.empty", False),
    ("ascii_lower_a", "a-case.empty", False),
    ("ascii_upper_i", "I-ascii.empty", False),
    ("ascii_lower_i", "i-ascii.empty", False),
    ("underscore", "_underscore.empty", False),
    ("nfd_e_acute", "e\u0301-nfd.empty", False),
    ("nfc_e_acute", "\u00e9-nfc.empty", False),
    ("german_a_umlaut", "\u00e4-german.empty", False),
    ("swedish_a_ring", "\u00e5-swedish.empty", False),
    ("turkish_capital_i_dot", "\u0130-turkish-capital.empty", False),
    ("turkish_small_dotless_i", "\u0131-turkish-small.empty", False),
    ("cjk", "\u4e2d\u6587.empty", False),
    ("emoji", "emoji-\U0001f600.empty", False),
    ("ascii_last", "z-last.empty", False),
    ("hidden", ".hidden.empty", True),
)
RAW_NAMES = (
    ("invalid_ff", b"invalid-\xff.empty"),
    ("invalid_overlong", b"invalid-\xc0\xaf.empty"),
    ("invalid_truncated", b"invalid-\xe2\x82.empty"),
)


def build_manifest() -> dict[str, Any]:
    names = [
        {
            "hidden": hidden,
            "id": name_id,
            "path_bytes_hex": name.encode("utf-8").hex(),
            "utf8": name,
            "valid_utf8": True,
        }
        for name_id, name, hidden in NAMES
    ]
    names.extend(
        {
            "hidden": False,
            "id": name_id,
            "path_bytes_hex": raw.hex(),
            "utf8": None,
            "valid_utf8": False,
        }
        for name_id, raw in RAW_NAMES
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generator": GENERATOR,
        "license": "project-generated empty files and path names",
        "locales": list(LOCALES),
        "filesystems": [dict(value) for value in FILESYSTEMS],
        "materialization": {
            "creation_order": "reverse-manifest",
            "payload_sha256": EMPTY_SHA256,
            "payload_size": 0,
        },
        "names": names,
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
