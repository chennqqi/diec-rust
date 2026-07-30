#!/usr/bin/env python3
"""Build the pre-execution macOS Qt5 oracle bootstrap plan."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
EVALUATED_ON = "2026-07-30"
UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
PLATFORM = "macos-x86_64-qt5"
SOURCE_PATHS = (
    ".github/workflows/macos-qt5-oracle-candidate.yml",
    "upstream/DIE-engine/.github/workflows/builder.yml",
    "upstream/DIE-engine/build.pri",
    "upstream/DIE-engine/build_mac.sh",
    "upstream/DIE-engine/console_source/console_source.pro",
    "upstream/DIE-engine/die_source.pro",
    "tools/upstream/build_macos_qt5_oracle.sh",
    "tools/corpus/generate_database_fixture.py",
    "tools/corpus/generate_nested_corpus.py",
    "tools/corpus/generate_macos_special_path_fixture.py",
    "tools/corpus/generate_path_corpus.py",
    "tools/corpus/validate_macos_special_path_fixture.py",
    "tools/upstream/collect_macos_cli_baseline.py",
    "tools/upstream/collect_macos_cli_database.py",
    "tools/upstream/collect_macos_cli_database_archives.py",
    "tools/upstream/collect_macos_cli_matrix.py",
    "tools/upstream/collect_macos_cli_remaining.py",
    "tools/upstream/collect_macos_cli_path_nested.py",
    "tools/upstream/validate_macos_cli_baseline.py",
    "tools/upstream/validate_macos_cli_database.py",
    "tools/upstream/validate_macos_cli_database_archives.py",
    "tools/upstream/validate_macos_cli_matrix.py",
    "tools/upstream/validate_macos_cli_remaining.py",
    "tools/upstream/validate_macos_cli_path_nested.py",
    "tools/upstream/validate_macos_qt5_oracle_report.py",
)


class PlanError(ValueError):
    """The macOS bootstrap plan cannot be generated safely."""


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def build_plan(root: Path) -> dict[str, Any]:
    sources = {}
    for relative in SOURCE_PATHS:
        path = root / relative
        if not path.is_file():
            raise PlanError(f"source path missing: {relative}")
        sources[relative] = sha256(path.read_bytes())
    return {
        "schema_version": SCHEMA_VERSION,
        "evaluated_on": EVALUATED_ON,
        "result": "infrastructure_ready_runtime_missing",
        "platform": PLATFORM,
        "upstream_commit": UPSTREAM_COMMIT,
        "rules_commit": RULES_COMMIT,
        "sources": dict(sorted(sources.items())),
        "fixed_contract": {
            "recursive_submodule_count": 58,
            "qt_version": "5.15.2",
            "qmake_spec": "macx-clang",
            "host_architecture": "x86_64",
            "build_system": "qmake",
            "configuration": "release",
            "targets": [
                "sub-build_libs-make_first",
                "sub-console_source-make_first",
            ],
            "version_stdout": "die 4.0.0",
        },
        "candidate_report_contract": {
            "validator": (
                "tools/upstream/"
                "validate_macos_qt5_oracle_report.py"
            ),
            "captures": [
                "clean root and 58 recursive submodule identities",
                "Qt qmake, QtCore, and QtScript SHA-256",
                "macOS, x86_64 CPU, Xcode, clang, CMake, and qmake identity",
                "CLI size, SHA-256, Mach-O architecture, dependencies, and version smoke",
            ],
            "contains_local_paths": True,
            "commit_policy": (
                "sanitize local paths before committing a collected report"
            ),
        },
        "dispatch_workflow": {
            "path": (
                ".github/workflows/"
                "macos-qt5-oracle-candidate.yml"
            ),
            "trigger": "workflow_dispatch",
            "runner": "macos-15-intel",
            "qt_installer": "aqtinstall==3.3.0",
            "artifact_retention_days": 14,
            "automatically_admits_evidence": False,
            "candidate_reports": [
                "oracle-candidate.json",
                "cache-state-candidate.json",
                "cli-baseline-candidate.json",
                "cli-matrix-candidate.json",
                "cli-remaining-candidate.json",
                "cli-database-candidate.json",
                "cli-path-nested-candidate.json",
                "cli-database-archive-candidate.json",
                "special-path-fixture-candidate.json",
            ],
            "raw_cli_streams_retained": True,
            "special_path_fixture_candidate": True,
            "remaining_cli_execution_count": 1092,
            "database_cli_execution_count": 36,
            "path_nested_cli_execution_count": 92,
            "database_archive_cli_execution_count": 34,
            "general_cli_execution_count": 1994,
            "general_cli_raw_stream_count": 3988,
        },
        "runtime_closure": {
            "required_capability_count": 68,
            "minimum_repetitions_per_case": 2,
            "required_evidence": [
                "hash-bound safe corpus and raw stdout/stderr",
                "complete CLI and engine capability projections",
                "macOS path, normalization, case, permission, and filesystem profiles",
                "determinism and Linux Qt5 semantic comparisons with classified differences",
            ],
        },
        "admission": {
            "platform_admitted": False,
            "coverage_status": "platform_missing",
            "reason": (
                "the build script and validator are ready, but no macOS "
                "candidate report or 68-row runtime closure has been collected"
            ),
        },
    }


def serialize(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=root)
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            root
            / "docs"
            / "research"
            / "data"
            / "macos-qt5-oracle-plan.json"
        ),
    )
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = serialize(build_plan(args.root.resolve()))
    if args.check:
        if not args.output.is_file() or args.output.read_bytes() != report:
            raise PlanError("committed macOS oracle plan differs")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
