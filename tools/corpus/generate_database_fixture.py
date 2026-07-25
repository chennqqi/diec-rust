#!/usr/bin/env python3
"""Generate benign database success/failure fixtures for upstream CLI tests."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys


DIRECTORIES = (
    "empty-main",
    "empty-extra",
    "empty-custom",
    "malformed-main",
    "malformed-main/Binary",
    "throwing-main",
    "throwing-main/Binary",
    "valid-main",
    "valid-main/Binary",
    "input",
)

FILES = (
    (
        "input/plain.txt",
        b"diec-rust deterministic corpus\n",
        "benign scan input",
    ),
    (
        "not-a-database.bin",
        b"not a ZIP database\n",
        "invalid database archive",
    ),
    (
        "malformed-main/Binary/broken.1.sg",
        b"function detect( {\n",
        "JavaScript syntax error",
    ),
    (
        "throwing-main/Binary/throw.1.sg",
        (
            b'function detect() {\n'
            b'    throw new Error("database fixture");\n'
            b"}\n"
        ),
        "JavaScript runtime error",
    ),
    (
        "valid-main/Binary/fixture.1.sg",
        (
            b"function detect() {\n"
            b'    _setResult("format", "Fixture", "1", "");\n'
            b"    return true;\n"
            b"}\n"
        ),
        "deterministic successful detection",
    ),
)


def generate(output_dir: pathlib.Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    for directory in DIRECTORIES:
        (output_dir / pathlib.PurePosixPath(directory)).mkdir(
            parents=True, exist_ok=True
        )

    entries = []
    for relative_path, data, purpose in FILES:
        destination = output_dir / pathlib.PurePosixPath(relative_path)
        destination.write_bytes(data)
        entries.append(
            {
                "path": relative_path,
                "source": "project-generated",
                "purpose": purpose,
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )

    manifest: dict[str, object] = {
        "schema_version": 1,
        "generator": "tools/corpus/generate_database_fixture.py",
        "license": "project-generated; no third-party sample or rule bytes",
        "directories": list(DIRECTORIES),
        "entries": entries,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir", type=pathlib.Path)
    args = parser.parse_args()
    manifest = generate(args.output_dir.resolve())
    json.dump(manifest, fp=sys.stdout, indent=2, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
