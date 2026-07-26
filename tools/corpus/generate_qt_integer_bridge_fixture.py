#!/usr/bin/env python3
"""Generate benign PE rules probing Qt QObject integer return bridging."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys


DIRECTORIES = (
    "main",
    "main/PE",
    "empty-extra",
    "empty-custom",
)

RULES = (
    (
        "main/PE/qint64_getSize.1.sg",
        "qint64",
        "PE.getSize()",
    ),
    (
        "main/PE/quint64_getImageFileHeader.2.sg",
        "quint64",
        'PE.getImageFileHeader("Machine")',
    ),
    (
        "main/PE/qint32_getNumberOfImports.3.sg",
        "qint32",
        "PE.getNumberOfImports()",
    ),
    (
        "main/PE/quint32_getSectionFileOffset.4.sg",
        "quint32",
        "PE.getSectionFileOffset(0)",
    ),
)


def rule_source(type_name: str, expression: str) -> bytes:
    return (
        "function detect() {\n"
        f"    var value = {expression};\n"
        f'    _setResult("bridge", "{type_name}", '
        'typeof value, String(value));\n'
        "    return true;\n"
        "}\n"
    ).encode()


def generate(output_dir: pathlib.Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    for directory in DIRECTORIES:
        (output_dir / pathlib.PurePosixPath(directory)).mkdir(
            parents=True, exist_ok=True
        )

    entries = []
    for relative_path, type_name, expression in RULES:
        data = rule_source(type_name, expression)
        destination = output_dir / pathlib.PurePosixPath(relative_path)
        destination.write_bytes(data)
        entries.append(
            {
                "path": relative_path,
                "source": "project-generated",
                "purpose": (
                    f"observe {type_name} QObject slot return in JavaScript"
                ),
                "expression": expression,
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )

    manifest: dict[str, object] = {
        "schema_version": 1,
        "generator": (
            "tools/corpus/generate_qt_integer_bridge_fixture.py"
        ),
        "license": "project-generated; no third-party sample or rule bytes",
        "input": {
            "manifest": "docs/research/data/baseline-corpus.json",
            "name": "minimal.exe",
            "sha256": (
                "afb1bcd812caa45095075a60ff49599c7d5e767c7732226c3e0007708cb198a2"
            ),
        },
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
