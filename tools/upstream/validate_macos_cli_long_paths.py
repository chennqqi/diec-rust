#!/usr/bin/env python3
"""Validate a non-admitted macOS Qt5 CLI long-path candidate."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Any


PLATFORM = "macos-x86_64-qt5"
COLLECTOR = "tools/upstream/collect_macos_cli_long_paths.py"
BASELINE_COLLECTOR = "tools/upstream/collect_macos_cli_baseline.py"
BASELINE_VALIDATOR = "tools/upstream/validate_macos_cli_baseline.py"
FIXTURE_VALIDATOR = (
    "tools/corpus/validate_macos_long_path_fixture.py"
)
ORACLE_VALIDATOR = "tools/upstream/validate_macos_qt5_oracle_report.py"


class ReportError(ValueError):
    """The long-path CLI candidate is incomplete or inconsistent."""


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


def validate_report(
    report: dict[str, Any],
    *,
    report_path: Path,
    oracle_path: Path,
    baseline_path: Path,
    fixture_report_path: Path,
    root: Path,
) -> None:
    bundle = report_path.parent
    if report_path != (
        bundle / "cli-long-path-candidate.json"
    ).resolve(strict=True):
        raise ReportError(
            "report must be bundle-local: cli-long-path-candidate.json"
        )
    for path, name in (
        (oracle_path, "oracle-candidate.json"),
        (baseline_path, "cli-baseline-candidate.json"),
        (
            fixture_report_path,
            "long-path-fixture-candidate.json",
        ),
    ):
        if path != (bundle / name).resolve(strict=True):
            raise ReportError(f"input report must be bundle-local: {name}")
    expected_root = {
        "schema_version",
        "result",
        "platform",
        "generator",
        "oracle_report",
        "cli_baseline_report",
        "fixture_report",
        "source",
        "qt",
        "binary",
        "selection",
        "cases",
        "summary",
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
        root, COLLECTOR, "macos_cli_long_path_collector_validation"
    )
    baseline_collector = _load(
        root,
        BASELINE_COLLECTOR,
        "macos_baseline_collector_long_path_validation",
    )
    baseline_validator = _load(
        root,
        BASELINE_VALIDATOR,
        "macos_baseline_validator_long_path_validation",
    )
    fixture_validator = _load(
        root,
        FIXTURE_VALIDATOR,
        "macos_long_path_fixture_validator_cli_validation",
    )
    oracle_validator = _load(
        root,
        ORACLE_VALIDATOR,
        "macos_oracle_validator_long_path_validation",
    )
    common = baseline_collector.load_module(
        "windows_cli_common_long_path_validation",
        root / baseline_collector.SHARED_COLLECTOR,
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
    baseline_report = baseline_validator.load_json(baseline_path)[0]
    baseline_validator.validate_report(
        baseline_report,
        report_path=baseline_path,
        oracle_path=oracle_path,
        root=root,
    )
    if report["cli_baseline_report"] != {
        "path": "cli-baseline-candidate.json",
        "sha256": sha256(baseline_path.read_bytes()),
    }:
        raise ReportError("CLI baseline binding drift")
    fixture_report = fixture_validator.load_json(
        fixture_report_path
    )[0]
    fixture_validator.validate_report(
        fixture_report,
        report_path=fixture_report_path,
        root=root,
    )
    if report["fixture_report"] != {
        "path": "long-path-fixture-candidate.json",
        "sha256": sha256(fixture_report_path.read_bytes()),
    }:
        raise ReportError("fixture report binding drift")
    if report["source"] != baseline_report["source"]:
        raise ReportError("source identity drift")
    if report["qt"] != baseline_report["qt"]:
        raise ReportError("Qt identity drift")
    if report["binary"] != baseline_report["binary"]:
        raise ReportError("binary identity drift")

    expected_cases = collector.build_cases(fixture_report)
    expected_names = [case.name for case in expected_cases]
    if report["selection"] != {
        "case_names": expected_names,
        "minimum_repetitions_per_case": 2,
    }:
        raise ReportError("long-path case selection drift")
    cases = require_object(report["cases"], "cases")
    if set(cases) != set(expected_names):
        raise ReportError("long-path case inventory drift")
    report_db = collector.database_arguments(
        Path("<source>"), report=True
    )
    reference_tree = baseline_report["corpus"]["minimal.pdf"][
        "first_detect_tree"
    ]
    declared_raw: set[str] = set()
    determinism_failures = []
    timeout_cases = []
    reference_projection_failures = []
    for case in expected_cases:
        entry = require_object(cases[case.name], f"case {case.name}")
        if entry.get("arguments") != [
            "--json",
            *report_db,
            case.report_target,
        ]:
            raise ReportError(f"case arguments drift: {case.name}")
        timeout = entry.get("timeout_seconds")
        if (
            not isinstance(timeout, int)
            or not 1 <= timeout <= 3600
        ):
            raise ReportError(f"case timeout drift: {case.name}")
        try:
            first, second = baseline_validator.validate_pair(
                entry,
                bundle,
                f"long-path case {case.name}",
                f"cli-long-path/{case.name}",
            )
        except baseline_validator.ReportError as error:
            raise ReportError(str(error)) from error
        for side in ("first", "second"):
            raw = require_object(entry[side], f"{case.name}.{side}")
            declared_raw.update(
                {raw["stdout_path"], raw["stderr_path"]}
            )
        first_timeout = entry.get("first_timed_out")
        second_timeout = entry.get("second_timed_out")
        if not isinstance(first_timeout, bool) or not isinstance(
            second_timeout, bool
        ):
            raise ReportError(f"timeout flag drift: {case.name}")
        if (first_timeout and first[0] != 124) or (
            second_timeout and second[0] != 124
        ):
            raise ReportError(f"timeout exit drift: {case.name}")
        first_tree = common.json_detect_tree(first[1])
        second_tree = common.json_detect_tree(second[1])
        reference_equal = (
            first_tree == reference_tree
            if case.reference_projection_applies
            else None
        )
        expected_fields = {
            "mode": case.mode,
            "fixture_case_id": case.fixture_case_id,
            "reference_projection_applies": (
                case.reference_projection_applies
            ),
            "first_valid_json": collector.valid_json(first[1]),
            "second_valid_json": collector.valid_json(second[1]),
            "first_detect_tree": first_tree,
            "second_detect_tree": second_tree,
            "minimal_pdf_detect_tree_equal": reference_equal,
            "first_prefix_case_ids": collector.prefix_case_ids(
                first[1], fixture_report
            ),
            "second_prefix_case_ids": collector.prefix_case_ids(
                second[1], fixture_report
            ),
        }
        for field, expected in expected_fields.items():
            if entry.get(field) != expected:
                raise ReportError(
                    f"long-path projection drift: "
                    f"{case.name}.{field}"
                )
        if entry["determinism_differences"] or (
            first_timeout != second_timeout
        ):
            determinism_failures.append(case.name)
        if first_timeout or second_timeout:
            timeout_cases.append(case.name)
        if (
            case.reference_projection_applies
            and not reference_equal
        ):
            reference_projection_failures.append(case.name)

    count = len(expected_cases)
    expected_summary = {
        "case_count": count,
        "execution_count": 2 * count,
        "raw_stream_count": 4 * count,
        "determinism_failures": determinism_failures,
        "timeout_cases": timeout_cases,
        "reference_projection_failures": (
            reference_projection_failures
        ),
        "deterministic": not determinism_failures,
        "reference_projections_equal": (
            not reference_projection_failures
        ),
    }
    if report["summary"] != expected_summary:
        raise ReportError("long-path summary drift")
    if report["admission"] != {
        "platform_admitted": False,
        "capability_rows_admitted": 0,
        "reason": collector.ADMISSION_REASON,
    }:
        raise ReportError("candidate must not admit capability evidence")
    if report["limitations"] != collector.LIMITATIONS:
        raise ReportError("long-path limitations drift")
    raw_root = bundle / "raw" / "cli-long-path"
    actual_raw = {
        path.relative_to(bundle).as_posix()
        for path in raw_root.rglob("*")
        if path.is_file()
    }
    if actual_raw != declared_raw:
        raise ReportError(
            "long-path raw file inventory differs from report"
        )


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--oracle-report", type=Path, required=True)
    parser.add_argument("--cli-baseline-report", type=Path, required=True)
    parser.add_argument("--fixture-report", type=Path, required=True)
    parser.set_defaults(root=root)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report_path = args.report.resolve(strict=True)
        oracle_path = args.oracle_report.resolve(strict=True)
        baseline_path = args.cli_baseline_report.resolve(strict=True)
        fixture_report_path = args.fixture_report.resolve(strict=True)
        baseline_validator = _load(
            args.root.resolve(),
            BASELINE_VALIDATOR,
            "macos_baseline_validator_long_path_entry",
        )
        report = baseline_validator.load_json(report_path)[0]
        validate_report(
            report,
            report_path=report_path,
            oracle_path=oracle_path,
            baseline_path=baseline_path,
            fixture_report_path=fixture_report_path,
            root=args.root.resolve(),
        )
    except (ReportError, OSError, ValueError) as error:
        print(
            f"macOS CLI long-path report error: {error}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
