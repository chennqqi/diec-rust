#!/usr/bin/env python3
"""Generate benign rules that expose DIE rule orchestration semantics."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from typing import Any


DIRECTORIES = (
    "main",
    "main/Binary",
    "main/PE",
    "extra",
    "extra/Binary",
    "custom",
    "custom/Binary",
    "empty-main",
    "empty-extra",
    "empty-custom",
    "priority-main",
    "priority-main/Binary",
    "priority-extra",
    "priority-custom",
    "sort-main",
    "sort-main/Binary",
    "sort-extra",
    "sort-custom",
    "break-main",
    "break-main/Binary",
    "break-extra",
    "break-custom",
    "input",
)


def detection_rule(
    name: str,
    version_expression: bytes = b"orchestrationType",
) -> bytes:
    return (
        b"function detect() {\n"
        b'    _setResult("format", "'
        + name.encode("ascii")
        + b'", '
        + version_expression
        + b', "");\n'
        b"    return true;\n"
        b"}\n"
    )


FILES: tuple[dict[str, Any], ...] = (
    {
        "path": "input/probe.bin",
        "data": b"diec-rust rule orchestration probe\n",
        "purpose": "benign Binary scan input",
    },
    {
        "path": "main/_init",
        "data": (
            b'var orchestrationGlobal = "main-global";\n'
            b'includeScript("shared_helper");\n'
        ),
        "purpose": "winning global init from the main database",
    },
    {
        "path": "main/shared_helper",
        "data": b'var orchestrationHelper = "main-helper";\n',
        "purpose": "winning same-name include from the main database",
    },
    {
        "path": "extra/_init",
        "data": b'var orchestrationGlobal = "extra-global";\n',
        "purpose": "shadowed global init",
    },
    {
        "path": "extra/shared_helper",
        "data": b'var orchestrationHelper = "extra-helper";\n',
        "purpose": "shadowed same-name include",
    },
    {
        "path": "custom/_init",
        "data": b'var orchestrationGlobal = "custom-global";\n',
        "purpose": "shadowed global init",
    },
    {
        "path": "custom/shared_helper",
        "data": b'var orchestrationHelper = "custom-helper";\n',
        "purpose": "shadowed same-name include",
    },
    {
        "path": "main/Binary/_init",
        "data": (
            b"var orchestrationType = orchestrationGlobal + "
            b'":" + orchestrationHelper + ":main-type";\n'
        ),
        "purpose": "winning Binary type init from the main database",
    },
    {
        "path": "extra/Binary/_init",
        "data": b'var orchestrationType = "extra-type";\n',
        "purpose": "shadowed Binary type init",
    },
    {
        "path": "custom/Binary/_init",
        "data": b'var orchestrationType = "custom-type";\n',
        "purpose": "shadowed Binary type init",
    },
    {
        "path": "main/Binary/z_normal.1.sg",
        "data": detection_rule("Main normal"),
        "purpose": (
            "ordinary main rule whose priority is disrupted by the "
            "non-transitive comparison with _init"
        ),
        "detection_name": "Main normal",
    },
    {
        "path": "main/Binary/DS.deep.2.sg",
        "data": detection_rule("Main deep"),
        "purpose": "DS deep-only rule",
        "detection_name": "Main deep",
    },
    {
        "path": "main/Binary/HEUR.heuristic.3.sg",
        "data": detection_rule("Main heuristic"),
        "purpose": "HEUR heuristic-only rule",
        "detection_name": "Main heuristic",
    },
    {
        "path": "main/Binary/EP.entrypoint.4.sg",
        "data": detection_rule("Main entrypoint"),
        "purpose": "EP deep-only rule",
        "detection_name": "Main entrypoint",
    },
    {
        "path": "extra/Binary/a_extra.0.sg",
        "data": detection_rule("Extra normal"),
        "purpose": "extra rule with lower priority appended after main",
        "detection_name": "Extra normal",
    },
    {
        "path": "custom/Binary/a_custom.0.sg",
        "data": detection_rule("Custom normal"),
        "purpose": "custom rule with lower priority appended after extra",
        "detection_name": "Custom normal",
    },
    {
        "path": "main/PE/decoy.0.sg",
        "data": detection_rule("PE decoy"),
        "purpose": "wrong-file-type rule that must not execute for Binary",
        "detection_name": "PE decoy",
    },
    {
        "path": "priority-main/Binary/z_priority.1.sg",
        "data": detection_rule(
            "Priority one",
            b'"priority-only"',
        ),
        "purpose": "priority 1 rule with lexically last name",
        "detection_name": "Priority one",
    },
    {
        "path": "priority-main/Binary/a_priority.2.sg",
        "data": detection_rule(
            "Priority two",
            b'"priority-only"',
        ),
        "purpose": "priority 2 rule with lexically first name",
        "detection_name": "Priority two",
    },
    {
        "path": "priority-main/Binary/m_priority.4.sg",
        "data": detection_rule(
            "Priority four",
            b'"priority-only"',
        ),
        "purpose": "priority 4 rule",
        "detection_name": "Priority four",
    },
    {
        "path": "sort-main/Binary/sort_records.1.sg",
        "data": (
            b"function detect() {\n"
            b'    _setResult("packer", "Packer last", "", "");\n'
            b'    _setResult("format", "Format first", "", "");\n'
            b'    _setResult("compiler", "Compiler middle", "", "");\n'
            b"    return true;\n"
            b"}\n"
        ),
        "purpose": "emit records in reverse type-priority order",
        "detection_name": "Sort records",
    },
    {
        "path": "break-main/Binary/break_scan.1.sg",
        "data": (
            b"function detect() {\n"
            b'    _setResult("format", "Break first", "", "");\n'
            b"    _breakScan();\n"
            b"    return true;\n"
            b"}\n"
        ),
        "purpose": "emit one result and stop the shared scan state",
        "detection_name": "Break first",
    },
    {
        "path": "break-main/Binary/after_break.2.sg",
        "data": detection_rule(
            "After break",
            b'""',
        ),
        "purpose": "must not execute after _breakScan",
        "detection_name": "After break",
    },
)

MODE_ORDERS = {
    "default": [
        "z_normal.1.sg",
        "a_extra.0.sg",
        "a_custom.0.sg",
    ],
    "deep": [
        "DS.deep.2.sg",
        "EP.entrypoint.4.sg",
        "z_normal.1.sg",
        "a_extra.0.sg",
        "a_custom.0.sg",
    ],
    "heuristic": [
        "HEUR.heuristic.3.sg",
        "z_normal.1.sg",
        "a_extra.0.sg",
        "a_custom.0.sg",
    ],
    "combined": [
        "DS.deep.2.sg",
        "HEUR.heuristic.3.sg",
        "EP.entrypoint.4.sg",
        "z_normal.1.sg",
        "a_extra.0.sg",
        "a_custom.0.sg",
    ],
}

PRIORITY_ONLY_ORDER = [
    "z_priority.1.sg",
    "a_priority.2.sg",
    "m_priority.4.sg",
]


def generate(output_dir: pathlib.Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    for directory in DIRECTORIES:
        (output_dir / pathlib.PurePosixPath(directory)).mkdir(
            parents=True,
            exist_ok=True,
        )

    entries = []
    for file in FILES:
        relative_path = pathlib.PurePosixPath(file["path"])
        data = file["data"]
        destination = output_dir / relative_path
        destination.write_bytes(data)
        entry = {
            "path": relative_path.as_posix(),
            "source": "project-generated",
            "purpose": file["purpose"],
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        if "detection_name" in file:
            entry["detection_name"] = file["detection_name"]
        entries.append(entry)

    manifest = {
        "schema_version": 1,
        "generator": (
            "tools/corpus/generate_rule_orchestration_fixture.py"
        ),
        "license": "project-generated; no third-party sample or rule bytes",
        "directories": list(DIRECTORIES),
        "expected_init_value": (
            "main-global:main-helper:main-type"
        ),
        "mode_orders": MODE_ORDERS,
        "priority_only_order": PRIORITY_ONLY_ORDER,
        "engine_contract": {
            "sort_unsorted_names": [
                "Packer last",
                "Format first",
                "Compiler middle",
            ],
            "sort_sorted_names": [
                "Format first",
                "Compiler middle",
                "Packer last",
            ],
            "break_execution_order": [
                "break_scan.1.sg",
            ],
            "break_detection_names": [
                "Break first",
            ],
        },
        "wrong_type_decoy": "decoy.0.sg",
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
