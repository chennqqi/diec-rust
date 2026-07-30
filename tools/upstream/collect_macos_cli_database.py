#!/usr/bin/env python3
"""Collect a non-admitted macOS Qt5 CLI database candidate."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import sys
from pathlib import Path
from typing import Any

UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
PLATFORM = "macos-x86_64-qt5"
BASELINE_COLLECTOR = "tools/upstream/collect_macos_cli_baseline.py"
BASELINE_VALIDATOR = "tools/upstream/validate_macos_cli_baseline.py"
DATABASE_HELPER = "tools/upstream/collect_windows_cli_database.py"
MATRIX_DEFINITIONS = "tools/upstream/compare_cli_oracles.py"
VALIDATOR = "tools/upstream/validate_macos_cli_database.py"
FIXTURE_MANIFEST = "docs/research/data/database-fixture.json"
LINUX_REFERENCE = (
    "docs/research/data/cli-database-matrix-linux-qt5-qt6.json"
)
ADMISSION_REASON = (
    "database CLI candidate only; macOS runtime evidence has not been "
    "reviewed or projected into the 68-row capability closure"
)
LIMITATIONS = [
    (
        "the candidate covers the 18 committed release-CLI database "
        "success, missing, empty, malformed, throwing, and layer cases"
    ),
    (
        "ZIP archive/cache boundaries, permission-denied databases, "
        "unreadable inputs, and engine-only cache controls remain open"
    ),
    (
        "raw streams remain authoritative; the named path and line-ending "
        "normalization is an additional Linux Qt5 comparison"
    ),
]
NORMALIZATION = {
    "purpose": (
        "compare raw macOS output to the committed Linux Qt5 stdout hashes "
        "after only named platform transformations"
    ),
    "operations": [
        (
            "replace each actual macOS path argument with the exact "
            "corresponding original Linux matrix argument"
        ),
        "replace CRLF with LF",
    ],
    "not_performed": [
        "JSON parsing or reserialization",
        "diagnostic removal or rewriting",
        "record sorting",
        "whitespace changes other than CRLF line endings",
    ],
}


class DatabaseError(ValueError):
    """The database candidate cannot be collected safely."""


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _load(root: Path, relative: str, name: str) -> Any:
    path = root / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise DatabaseError(f"cannot load helper module: {relative}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _generator_bindings(root: Path) -> dict[str, str]:
    paths = {
        "path": "tools/upstream/collect_macos_cli_database.py",
        "validator_path": VALIDATOR,
        "baseline_collector_path": BASELINE_COLLECTOR,
        "baseline_validator_path": BASELINE_VALIDATOR,
        "database_helper_path": DATABASE_HELPER,
        "matrix_definitions_path": MATRIX_DEFINITIONS,
    }
    result = dict(paths)
    for field, relative in paths.items():
        digest_field = (
            "sha256"
            if field == "path"
            else field.removesuffix("_path") + "_sha256"
        )
        result[digest_field] = sha256((root / relative).read_bytes())
    return result


def _raw_differences(
    actual: dict[str, Any],
    linux: dict[str, Any],
) -> list[str]:
    differences = []
    if actual["exit_code"] != linux["exit_code"]:
        differences.append("exit_code")
    if actual["stdout_sha256"] != linux["stdout_sha256"]:
        differences.append("stdout")
    if actual["stderr_sha256"] != linux["stderr_sha256"]:
        differences.append("stderr")
    return differences


def collect(
    *,
    root: Path,
    binary: Path,
    source_dir: Path,
    qt_dir: Path,
    fixture_dir: Path,
    oracle_path: Path,
    output: Path,
    timeout_seconds: int,
) -> dict[str, Any]:
    if sys.platform != "darwin" or platform.machine() != "x86_64":
        raise DatabaseError("collector requires native Darwin x86_64")
    if not 1 <= timeout_seconds <= 3600:
        raise DatabaseError("timeout-seconds must be in 1..3600")
    source_dir = source_dir.resolve(strict=True)
    qt_dir = qt_dir.resolve(strict=True)
    fixture_dir = fixture_dir.resolve(strict=True)
    binary = binary.resolve(strict=True)
    oracle_path = oracle_path.resolve(strict=True)
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if oracle_path != (
        output.parent / "oracle-candidate.json"
    ).resolve(strict=True):
        raise DatabaseError(
            "oracle report must be bundle-local: oracle-candidate.json"
        )
    if output.exists():
        raise DatabaseError("candidate report already exists")
    raw_dir = output.parent / "raw" / "cli-database"
    raw_dir.mkdir(parents=True, exist_ok=True)
    if any(raw_dir.iterdir()):
        raise DatabaseError("database raw directory must be empty")

    baseline_collector = _load(
        root,
        BASELINE_COLLECTOR,
        "macos_cli_baseline_collector_for_database",
    )
    database_helper = _load(
        root,
        DATABASE_HELPER,
        "windows_cli_database_helper_for_macos",
    )
    definitions = _load(
        root,
        MATRIX_DEFINITIONS,
        "cli_matrix_definitions_for_macos_database",
    )
    common = baseline_collector.load_module(
        "windows_cli_common_for_macos_database",
        root / baseline_collector.SHARED_COLLECTOR,
    )
    oracle, oracle_raw = baseline_collector.validate_oracle_inputs(
        root, oracle_path, source_dir, qt_dir, binary
    )
    expected_binary = (
        source_dir / "build" / "release" / "diec"
    ).resolve(strict=True)
    if binary != expected_binary:
        raise DatabaseError(
            "binary must be <source>/build/release/diec"
        )
    source = common.validate_source(source_dir)
    source["tracked_files_clean_before_and_after"] = True
    qt = baseline_collector.validate_qt(common, qt_dir, oracle)
    binary_sha256 = common.sha256_file(binary)
    if binary_sha256 != oracle["artifact"]["sha256"]:
        raise DatabaseError("binary differs from oracle report")

    fixture_manifest_path = root / FIXTURE_MANIFEST
    fixture_manifest_raw = (fixture_dir / "manifest.json").read_bytes()
    if fixture_manifest_raw != fixture_manifest_path.read_bytes():
        raise DatabaseError(
            "database fixture manifest differs from reference"
        )
    fixture_manifest = definitions.load_database_fixture(fixture_dir)
    linux_path = root / LINUX_REFERENCE
    linux_reference, linux_raw = database_helper.read_json(linux_path)
    linux_cases = database_helper.validate_linux_reference(
        linux_reference
    )

    reports: dict[str, object] = {}
    determinism_failures: list[str] = []
    exit_failures: list[str] = []
    load_error_failures: list[str] = []
    validity_failures: list[str] = []
    normalized_stdout_failures: list[str] = []
    for case in definitions.DATABASE_CASES:
        actual_arguments = database_helper.translate_arguments(
            case.arguments,
            source_dir,
            fixture_dir,
            report=False,
        )
        report_arguments = database_helper.translate_arguments(
            case.arguments,
            source_dir,
            fixture_dir,
            report=True,
        )
        first = common.observe(
            binary,
            qt_dir,
            actual_arguments,
            timeout_seconds=timeout_seconds,
        )
        second = common.observe(
            binary,
            qt_dir,
            actual_arguments,
            timeout_seconds=timeout_seconds,
        )
        entry = baseline_collector.pair_report(
            common,
            output.parent,
            f"cli-database/{case.name}",
            first,
            second,
        )
        linux_case = linux_cases[case.name]
        first_load_error = b"Cannot load database:" in first.stdout
        second_load_error = b"Cannot load database:" in second.stdout
        linux_load_error = linux_case["left_reports_load_error"]
        normalized = (
            database_helper.normalize_windows_stdout_for_linux(
                first.stdout,
                actual_arguments,
                case.arguments,
            )
        )
        normalized_sha256 = sha256(normalized)
        normalized_equal = (
            normalized_sha256
            == linux_case["left"]["stdout_sha256"]
        )
        entry.update(
            {
                "arguments": list(report_arguments),
                "first_reports_load_error": first_load_error,
                "second_reports_load_error": second_load_error,
                "linux_qt5_reports_load_error": linux_load_error,
                "linux_qt5_reports_load_error_equal": (
                    first_load_error == linux_load_error
                ),
                "reports_parse_error": (
                    b"SyntaxError: Parse error" in first.stdout
                ),
                "reports_runtime_error": (
                    b"Error: database fixture" in first.stdout
                ),
                "linux_qt5_raw_differences": _raw_differences(
                    first.summary(), linux_case["left"]
                ),
                "linux_normalized_stdout_sha256": normalized_sha256,
                "linux_qt5_normalized_stdout_equal": normalized_equal,
            }
        )
        if case.name.endswith("_json"):
            first_valid = definitions.document_is_valid(
                first.stdout, "json"
            )
            second_valid = definitions.document_is_valid(
                second.stdout, "json"
            )
            linux_valid = linux_case["left_valid_json"]
            entry.update(
                {
                    "first_valid_json": first_valid,
                    "second_valid_json": second_valid,
                    "linux_qt5_valid_json": linux_valid,
                    "linux_qt5_valid_json_equal": (
                        first_valid == linux_valid
                    ),
                }
            )
            if first_valid != linux_valid:
                validity_failures.append(case.name)
        reports[case.name] = entry
        if entry["determinism_differences"]:
            determinism_failures.append(case.name)
        if first.exit_code != linux_case["left"]["exit_code"]:
            exit_failures.append(case.name)
        if first_load_error != linux_load_error:
            load_error_failures.append(case.name)
        if not normalized_equal:
            normalized_stdout_failures.append(case.name)

    post_source = common.validate_source(source_dir)
    post_source["tracked_files_clean_before_and_after"] = True
    if post_source != source:
        raise DatabaseError("source identity changed during collection")
    if common.sha256_file(binary) != binary_sha256:
        raise DatabaseError("binary changed during collection")
    if (fixture_dir / "manifest.json").read_bytes() != fixture_manifest_raw:
        raise DatabaseError("database fixture changed during collection")

    case_count = len(definitions.DATABASE_CASES)
    report = {
        "schema_version": 1,
        "result": "candidate",
        "platform": PLATFORM,
        "generator": _generator_bindings(root),
        "oracle_report": {
            "path": "oracle-candidate.json",
            "sha256": sha256(oracle_raw),
        },
        "source": source,
        "qt": qt,
        "binary": {
            "size": binary.stat().st_size,
            "sha256": binary_sha256,
            "relative_path": "build/release/diec",
        },
        "fixture": {
            "manifest": FIXTURE_MANIFEST,
            "sha256": sha256(fixture_manifest_raw),
            "directories": fixture_manifest["directories"],
            "entries": fixture_manifest["entries"],
        },
        "linux_qt5_reference": {
            "path": LINUX_REFERENCE,
            "sha256": sha256(linux_raw),
        },
        "local_paths": {
            "fixture_dir": str(fixture_dir),
        },
        "cases": reports,
        "summary": {
            "case_count": case_count,
            "execution_count": 2 * case_count,
            "raw_stream_count": 4 * case_count,
            "determinism_failures": determinism_failures,
            "linux_exit_code_failures": exit_failures,
            "linux_load_error_failures": load_error_failures,
            "linux_document_validity_failures": validity_failures,
            "linux_normalized_stdout_failures": (
                normalized_stdout_failures
            ),
            "deterministic": not determinism_failures,
            "linux_exit_codes_equal": not exit_failures,
            "linux_load_errors_equal": not load_error_failures,
            "linux_document_validity_equal": not validity_failures,
            "linux_normalized_stdout_equal": (
                not normalized_stdout_failures
            ),
        },
        "normalization": NORMALIZATION,
        "admission": {
            "platform_admitted": False,
            "capability_rows_admitted": 0,
            "reason": ADMISSION_REASON,
        },
        "limitations": LIMITATIONS,
    }
    output.write_bytes(
        (
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    )
    return report


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--qt-dir", type=Path, required=True)
    parser.add_argument("--fixture-dir", type=Path, required=True)
    parser.add_argument("--oracle-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.set_defaults(root=root)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        collect(
            root=args.root.resolve(),
            binary=args.binary,
            source_dir=args.source_dir,
            qt_dir=args.qt_dir,
            fixture_dir=args.fixture_dir,
            oracle_path=args.oracle_report,
            output=args.output,
            timeout_seconds=args.timeout_seconds,
        )
    except (DatabaseError, OSError, ValueError) as error:
        print(f"macOS CLI database error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
