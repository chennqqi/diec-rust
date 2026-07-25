#!/usr/bin/env python3
"""Probe persistent cross-evaluate state in pinned Qt oracles."""

from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys


BASE_PATH = pathlib.Path(__file__).with_name("probe_script_scope.py")
SPEC = importlib.util.spec_from_file_location(
    "probe_script_scope_for_state", BASE_PATH
)
assert SPEC is not None and SPEC.loader is not None
BASE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = BASE
SPEC.loader.exec_module(BASE)


def main() -> int:
    parser = argparse.ArgumentParser()
    repo = pathlib.Path(__file__).resolve().parents[2]
    parser.add_argument("--fixture-dir", type=pathlib.Path, required=True)
    parser.add_argument(
        "--manifest",
        type=pathlib.Path,
        default=repo
        / "docs"
        / "research"
        / "data"
        / "script-state-fixture.json",
    )
    parser.add_argument("--raw-dir", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()
    report = BASE.build_report(
        args.fixture_dir.resolve(),
        args.manifest.resolve(),
        args.raw_dir.resolve(),
        expected_generator=(
            "tools/corpus/generate_script_state_fixture.py"
        ),
        report_generator="tools/upstream/probe_script_state.py",
        manifest_report_path=(
            "docs/research/data/script-state-fixture.json"
        ),
    )
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
