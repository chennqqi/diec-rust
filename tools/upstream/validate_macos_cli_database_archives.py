#!/usr/bin/env python3
"""Validate a non-admitted macOS Qt5 ZIP-database CLI candidate."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import sys
from pathlib import Path, PurePosixPath
from typing import Any

UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
PLATFORM = "macos-x86_64-qt5"
COLLECTOR = "tools/upstream/collect_macos_cli_database_archives.py"
BASELINE_COLLECTOR = "tools/upstream/collect_macos_cli_baseline.py"
BASELINE_VALIDATOR = "tools/upstream/validate_macos_cli_baseline.py"
DATABASE_HELPER = "tools/upstream/collect_windows_cli_database.py"
ARCHIVE_HELPER = (
    "tools/upstream/collect_windows_cli_database_archives.py"
)
ARCHIVE_DEFINITIONS = "tools/upstream/probe_database_archives.py"
FIXTURE_GENERATOR = "tools/corpus/generate_database_fixture.py"
ORACLE_VALIDATOR = (
    "tools/upstream/validate_macos_qt5_oracle_report.py"
)
FIXTURE_MANIFEST = "docs/research/data/database-fixture.json"
LINUX_REFERENCE = (
    "docs/research/data/database-archive-linux-qt5.json"
)


class ReportError(ValueError):
    """The ZIP-database candidate is incomplete or inconsistent."""


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def require_object(value: Any, description: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReportError(f"{description} must be an object")
    return value


def _load(root: Path, relative: str, name: str) -> Any:
    path = root / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ReportError(f"cannot load helper module: {relative}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _summary(observation: tuple[int, bytes, bytes]) -> dict[str, Any]:
    return {
        "exit_code": observation[0],
        "stdout_bytes": len(observation[1]),
        "stdout_sha256": sha256(observation[1]),
        "stderr_bytes": len(observation[2]),
        "stderr_sha256": sha256(observation[2]),
    }


def validate_report(
    report: dict[str, Any],
    *,
    report_path: Path,
    oracle_path: Path,
    root: Path,
) -> None:
    bundle = report_path.parent
    if report_path != (
        bundle / "cli-database-archive-candidate.json"
    ).resolve(strict=True):
        raise ReportError(
            "report must be bundle-local: "
            "cli-database-archive-candidate.json"
        )
    if oracle_path != (
        bundle / "oracle-candidate.json"
    ).resolve(strict=True):
        raise ReportError(
            "report must be bundle-local: oracle-candidate.json"
        )
    expected_root = {
        "schema_version",
        "result",
        "platform",
        "generator",
        "oracle_report",
        "source",
        "qt",
        "binary",
        "fixture",
        "linux_qt5_reference",
        "local_paths",
        "cases",
        "summary",
        "normalization",
        "admission",
        "limitations",
    }
    if set(report) != expected_root:
        raise ReportError("report root fields changed")
    if (
        report["schema_version"] != 1
        or report["result"] != "candidate"
        or report["platform"] != PLATFORM
    ):
        raise ReportError("report identity drift")

    collector = _load(
        root,
        COLLECTOR,
        "macos_cli_database_archive_collector_validation",
    )
    baseline_validator = _load(
        root,
        BASELINE_VALIDATOR,
        "macos_cli_baseline_validator_database_archive_validation",
    )
    archive_helper = _load(
        root,
        ARCHIVE_HELPER,
        "windows_cli_database_archive_helper_macos_validation",
    )
    database_helper = archive_helper.windows_database
    definitions = archive_helper.archive_definitions
    oracle_validator = _load(
        root,
        ORACLE_VALIDATOR,
        "macos_oracle_validator_database_archive_validation",
    )
    if report["generator"] != collector._generator_bindings(root):
        raise ReportError("generator identity drift")

    oracle = oracle_validator.load_report(oracle_path)
    oracle_validator.validate_report(oracle)
    if report["oracle_report"] != {
        "path": "oracle-candidate.json",
        "sha256": sha256(oracle_path.read_bytes()),
    }:
        raise ReportError("oracle report binding drift")
    if report["source"] != {
        "repository": "https://github.com/horsicq/DIE-engine",
        "commit": UPSTREAM_COMMIT,
        "recursive_submodule_count": 58,
        "rules_commit": RULES_COMMIT,
        "tracked_files_clean_before_and_after": True,
    }:
        raise ReportError("source identity drift")
    if report["qt"] != {
        "version": oracle["qt"]["version"],
        "qmake_spec": oracle["qt"]["qmake_spec"],
        "qmake_sha256": oracle["qt"]["qmake_sha256"],
        "qtcore_sha256": oracle["qt"]["qtcore_sha256"],
        "qtscript_sha256": oracle["qt"]["qtscript_sha256"],
    }:
        raise ReportError("Qt identity drift")
    if report["binary"] != {
        "size": oracle["artifact"]["size"],
        "sha256": oracle["artifact"]["sha256"],
        "relative_path": "build/release/diec",
    }:
        raise ReportError("binary identity drift")

    fixture, fixture_raw = baseline_validator.load_json(
        root / FIXTURE_MANIFEST
    )
    fixture_sha256 = sha256(fixture_raw)
    if report["fixture"] != {
        "manifest": FIXTURE_MANIFEST,
        "sha256": fixture_sha256,
        "directories": fixture["directories"],
        "entries": fixture["entries"],
    }:
        raise ReportError("database fixture binding drift")
    linux, linux_raw = baseline_validator.load_json(
        root / LINUX_REFERENCE
    )
    if report["linux_qt5_reference"] != {
        "path": LINUX_REFERENCE,
        "sha256": sha256(linux_raw),
    }:
        raise ReportError("Linux archive reference binding drift")
    try:
        linux_cases = archive_helper.validate_linux_reference(
            linux, fixture_sha256
        )
    except ValueError as error:
        raise ReportError(
            f"Linux archive reference invalid: {error}"
        ) from error

    local_paths = require_object(report["local_paths"], "local_paths")
    if set(local_paths) != {"fixture_dir"}:
        raise ReportError("local path fields changed")
    fixture_value = local_paths["fixture_dir"]
    if (
        not isinstance(fixture_value, str)
        or not PurePosixPath(fixture_value).is_absolute()
    ):
        raise ReportError("fixture local path must be absolute")
    source_value = oracle["local_paths"]["source_dir"]
    if (
        not isinstance(source_value, str)
        or not PurePosixPath(source_value).is_absolute()
    ):
        raise ReportError("oracle source local path must be absolute")
    fixture_dir = PurePosixPath(fixture_value)
    source_dir = PurePosixPath(source_value)

    cases = require_object(report["cases"], "cases")
    expected_cases = definitions.ARCHIVE_CASES
    if set(cases) != {case.name for case in expected_cases}:
        raise ReportError("archive case set drift")
    determinism_failures: list[str] = []
    exit_failures: list[str] = []
    stderr_failures: list[str] = []
    validity_failures: list[str] = []
    normalized_failures: list[str] = []
    declared_raw: set[str] = set()
    for case in expected_cases:
        description = f"cases.{case.name}"
        entry = require_object(cases[case.name], description)
        fields = {
            "first",
            "second",
            "determinism_differences",
            "arguments",
            "reports_parse_error",
            "linux_qt5_raw_differences",
            "linux_normalized_stdout_sha256",
            "linux_qt5_normalized_stdout_equal",
            "linux_qt5_stderr_equal",
        }
        if case.name.endswith("_json"):
            fields.update(
                {
                    "first_valid_json",
                    "second_valid_json",
                    "linux_qt5_valid_json",
                    "linux_qt5_valid_json_equal",
                }
            )
        if set(entry) != fields:
            raise ReportError(
                f"archive field set drift: {case.name}"
            )
        report_arguments = database_helper.translate_arguments(
            case.arguments,
            source_dir,
            fixture_dir,
            report=True,
        )
        if entry["arguments"] != list(report_arguments):
            raise ReportError(
                f"archive arguments drift: {case.name}"
            )
        try:
            first, second = baseline_validator.validate_pair(
                entry,
                bundle,
                description,
                f"cli-database-archive/{case.name}",
            )
        except baseline_validator.ReportError as error:
            raise ReportError(str(error)) from error
        for side in ("first", "second"):
            raw = require_object(entry[side], f"{description}.{side}")
            declared_raw.update(
                {raw["stdout_path"], raw["stderr_path"]}
            )
        if first != second:
            determinism_failures.append(case.name)
        linux_case = linux_cases[case.name]
        linux_summary = linux_case["left"]
        actual_arguments = database_helper.translate_arguments(
            case.arguments,
            source_dir,
            fixture_dir,
            report=False,
        )
        normalized = (
            database_helper.normalize_windows_stdout_for_linux(
                first[1],
                actual_arguments,
                case.arguments,
            )
        )
        normalized_sha256 = sha256(normalized)
        normalized_equal = (
            normalized_sha256 == linux_summary["stdout_sha256"]
        )
        stderr_equal = (
            sha256(first[2]) == linux_summary["stderr_sha256"]
        )
        expected_projection = {
            "reports_parse_error": (
                b"SyntaxError: Parse error" in first[1]
            ),
            "linux_qt5_raw_differences": (
                database_helper.raw_differences(
                    _summary(first), linux_summary
                )
            ),
            "linux_normalized_stdout_sha256": normalized_sha256,
            "linux_qt5_normalized_stdout_equal": normalized_equal,
            "linux_qt5_stderr_equal": stderr_equal,
        }
        for field, expected in expected_projection.items():
            if entry[field] != expected:
                raise ReportError(
                    f"archive projection drift: {case.name}.{field}"
                )
        if first[0] != linux_summary["exit_code"]:
            exit_failures.append(case.name)
        if not stderr_equal:
            stderr_failures.append(case.name)
        if not normalized_equal:
            normalized_failures.append(case.name)
        if case.name.endswith("_json"):
            first_valid = (
                database_helper.matrix_definitions.document_is_valid(
                    first[1], "json"
                )
            )
            second_valid = (
                database_helper.matrix_definitions.document_is_valid(
                    second[1], "json"
                )
            )
            linux_valid = linux_case["left_valid_json"]
            expected_validity = {
                "first_valid_json": first_valid,
                "second_valid_json": second_valid,
                "linux_qt5_valid_json": linux_valid,
                "linux_qt5_valid_json_equal": (
                    first_valid == linux_valid
                ),
            }
            for field, expected in expected_validity.items():
                if entry[field] != expected:
                    raise ReportError(
                        "archive validity drift: "
                        f"{case.name}.{field}"
                    )
            if first_valid != linux_valid:
                validity_failures.append(case.name)

    case_count = len(expected_cases)
    expected_summary = {
        "case_count": case_count,
        "execution_count": 2 * case_count,
        "raw_stream_count": 4 * case_count,
        "determinism_failures": determinism_failures,
        "linux_exit_code_failures": exit_failures,
        "linux_stderr_failures": stderr_failures,
        "linux_document_validity_failures": validity_failures,
        "linux_normalized_stdout_failures": normalized_failures,
        "deterministic": not determinism_failures,
        "linux_exit_codes_equal": not exit_failures,
        "linux_stderr_equal": not stderr_failures,
        "linux_document_validity_equal": not validity_failures,
        "linux_normalized_stdout_equal": not normalized_failures,
    }
    if report["summary"] != expected_summary:
        raise ReportError("archive summary drift")
    if report["normalization"] != collector.NORMALIZATION:
        raise ReportError("archive normalization drift")
    if report["admission"] != {
        "platform_admitted": False,
        "capability_rows_admitted": 0,
        "reason": collector.ADMISSION_REASON,
    }:
        raise ReportError("candidate must not admit capability evidence")
    if report["limitations"] != collector.LIMITATIONS:
        raise ReportError("archive limitations drift")
    raw_root = bundle / "raw" / "cli-database-archive"
    actual_raw = {
        path.relative_to(bundle).as_posix()
        for path in raw_root.rglob("*")
        if path.is_file()
    }
    if actual_raw != declared_raw:
        raise ReportError(
            "archive raw file inventory differs from report"
        )


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--oracle-report", type=Path, required=True)
    parser.set_defaults(root=root)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report_path = args.report.resolve(strict=True)
        oracle_path = args.oracle_report.resolve(strict=True)
        baseline_validator = _load(
            args.root.resolve(),
            BASELINE_VALIDATOR,
            "macos_cli_baseline_validator_database_archive_entry",
        )
        report = baseline_validator.load_json(report_path)[0]
        validate_report(
            report,
            report_path=report_path,
            oracle_path=oracle_path,
            root=args.root.resolve(),
        )
    except (ReportError, OSError, ValueError) as error:
        print(
            f"macOS CLI database archive validation error: {error}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
