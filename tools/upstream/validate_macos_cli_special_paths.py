#!/usr/bin/env python3
"""Validate a non-admitted macOS Qt5 special-path CLI candidate."""

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
COLLECTOR = "tools/upstream/collect_macos_cli_special_paths.py"
BASELINE_COLLECTOR = "tools/upstream/collect_macos_cli_baseline.py"
BASELINE_VALIDATOR = "tools/upstream/validate_macos_cli_baseline.py"
FIXTURE_GENERATOR = (
    "tools/corpus/generate_macos_special_path_fixture.py"
)
FIXTURE_VALIDATOR = (
    "tools/corpus/validate_macos_special_path_fixture.py"
)


class ReportError(ValueError):
    """The special-path CLI candidate is inconsistent."""


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
    expected_paths = {
        report_path: "cli-special-path-candidate.json",
        oracle_path: "oracle-candidate.json",
        baseline_path: "cli-baseline-candidate.json",
        fixture_report_path: "special-path-fixture-candidate.json",
    }
    for path, name in expected_paths.items():
        if path != (bundle / name).resolve(strict=True):
            raise ReportError(f"report must be bundle-local: {name}")
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
        "findings",
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
        root,
        COLLECTOR,
        "macos_cli_special_path_collector_validation",
    )
    baseline_collector = _load(
        root,
        BASELINE_COLLECTOR,
        "macos_cli_baseline_collector_special_path_validation",
    )
    baseline_validator = _load(
        root,
        BASELINE_VALIDATOR,
        "macos_cli_baseline_validator_special_path_validation",
    )
    fixture_generator = _load(
        root,
        FIXTURE_GENERATOR,
        "macos_special_path_fixture_generator_cli_validation",
    )
    fixture_validator = _load(
        root,
        FIXTURE_VALIDATOR,
        "macos_special_path_fixture_validator_cli_validation",
    )
    common = baseline_collector.load_module(
        "windows_cli_common_special_path_validation",
        root / baseline_collector.SHARED_COLLECTOR,
    )
    if report["generator"] != collector._generator_bindings(root):
        raise ReportError("generator identity drift")

    try:
        baseline_report = baseline_validator.load_json(
            baseline_path
        )[0]
        baseline_validator.validate_report(
            baseline_report,
            report_path=baseline_path,
            oracle_path=oracle_path,
            root=root,
        )
    except baseline_validator.ReportError as error:
        raise ReportError(
            f"CLI baseline input is invalid: {error}"
        ) from error
    fixture_report = fixture_validator.load_json(
        fixture_report_path
    )[0]
    try:
        fixture_validator.validate_report(
            fixture_report,
            report_path=fixture_report_path,
            root=root,
        )
    except fixture_validator.ReportError as error:
        raise ReportError(
            f"fixture input is invalid: {error}"
        ) from error

    expected_bindings = {
        "oracle_report": {
            "path": "oracle-candidate.json",
            "sha256": sha256(oracle_path.read_bytes()),
        },
        "cli_baseline_report": {
            "path": "cli-baseline-candidate.json",
            "sha256": sha256(baseline_path.read_bytes()),
        },
        "fixture_report": {
            "path": "special-path-fixture-candidate.json",
            "sha256": sha256(fixture_report_path.read_bytes()),
        },
    }
    for field, expected in expected_bindings.items():
        if report[field] != expected:
            raise ReportError(f"{field} binding drift")
    for field in ("source", "qt", "binary"):
        if report[field] != baseline_report[field]:
            raise ReportError(f"special-path {field} identity differs")
    if report["source"] != {
        "repository": "https://github.com/horsicq/DIE-engine",
        "commit": UPSTREAM_COMMIT,
        "recursive_submodule_count": 58,
        "rules_commit": RULES_COMMIT,
        "tracked_files_clean_before_and_after": True,
    }:
        raise ReportError("source identity drift")

    fixture_value = fixture_report["fixture"]["local_path"]
    if (
        not isinstance(fixture_value, str)
        or not PurePosixPath(fixture_value).is_absolute()
    ):
        raise ReportError("fixture local path must be POSIX absolute")
    oracle = baseline_collector.load_module(
        "macos_oracle_validator_special_path_validation",
        root / baseline_collector.ORACLE_VALIDATOR,
    ).load_report(oracle_path)
    source_value = oracle["local_paths"]["source_dir"]
    artifact_value = oracle["local_paths"]["artifact"]
    if (
        not isinstance(source_value, str)
        or not PurePosixPath(source_value).is_absolute()
        or not isinstance(artifact_value, str)
        or not PurePosixPath(artifact_value).is_absolute()
    ):
        raise ReportError("oracle local paths must be POSIX absolute")
    fixture_dir = PurePosixPath(fixture_value)
    cases_contract = collector.build_cases(
        source_dir=PurePosixPath(source_value),
        fixture_dir=fixture_dir,
        binary_dir=PurePosixPath(artifact_value).parent,
        fixture_generator=fixture_generator,
    )
    logical = collector.logical_entries(fixture_generator)
    expected_selection = {
        "logical_entries": [
            {"id": case_id, "path": relative}
            for case_id, relative in logical
        ],
        "case_names": [case.name for case in cases_contract],
    }
    if report["selection"] != expected_selection:
        raise ReportError("special-path selection drift")

    cases = require_object(report["cases"], "cases")
    if set(cases) != {case.name for case in cases_contract}:
        raise ReportError("special-path case set drift")
    reference_tree = baseline_report["corpus"]["minimal.pdf"][
        "first_detect_tree"
    ]
    determinism_failures = []
    exit_failures = []
    projection_failures = []
    declared_raw: set[str] = set()
    for case in cases_contract:
        description = f"cases.{case.name}"
        entry = require_object(cases[case.name], description)
        expected_fields = {
            "first",
            "second",
            "determinism_differences",
            "cwd",
            "arguments",
            "expected_exit_code",
            "expected_exit_code_equal",
            "first_valid_json",
            "second_valid_json",
            "first_detect_tree",
            "second_detect_tree",
            "reference_projection_applies",
            "minimal_pdf_detect_tree_equal",
            "first_prefix_tokens",
            "second_prefix_tokens",
        }
        if set(entry) != expected_fields:
            raise ReportError(
                f"special-path field set drift: {case.name}"
            )
        if (
            entry["cwd"] != case.report_cwd
            or entry["arguments"] != list(case.report_arguments)
            or entry["expected_exit_code"] != case.expected_exit
            or entry["reference_projection_applies"]
            is not case.reference_projection_applies
        ):
            raise ReportError(
                f"special-path case contract drift: {case.name}"
            )
        try:
            first, second = baseline_validator.validate_pair(
                entry,
                bundle,
                description,
                f"cli-special-path/{case.name}",
            )
        except baseline_validator.ReportError as error:
            raise ReportError(str(error)) from error
        for side in ("first", "second"):
            raw = require_object(entry[side], f"{description}.{side}")
            declared_raw.update(
                {raw["stdout_path"], raw["stderr_path"]}
            )
        first_tree = common.json_detect_tree(first[1])
        second_tree = common.json_detect_tree(second[1])
        projection_equal = (
            first_tree == reference_tree
            if case.reference_projection_applies
            else None
        )
        expected_projection = {
            "expected_exit_code_equal": (
                first[0] == case.expected_exit
            ),
            "first_valid_json": collector.valid_json(first[1]),
            "second_valid_json": collector.valid_json(second[1]),
            "first_detect_tree": first_tree,
            "second_detect_tree": second_tree,
            "minimal_pdf_detect_tree_equal": projection_equal,
            "first_prefix_tokens": collector.prefix_tokens(
                first[1],
                fixture_dir=fixture_dir,
                fixture_report=fixture_report,
            ),
            "second_prefix_tokens": collector.prefix_tokens(
                second[1],
                fixture_dir=fixture_dir,
                fixture_report=fixture_report,
            ),
        }
        for field, expected in expected_projection.items():
            if entry[field] != expected:
                raise ReportError(
                    "special-path projection drift: "
                    f"{case.name}.{field}"
                )
        if first != second:
            determinism_failures.append(case.name)
        if first[0] != case.expected_exit:
            exit_failures.append(case.name)
        if (
            case.reference_projection_applies
            and first_tree != reference_tree
        ):
            projection_failures.append(case.name)

    observations = fixture_report["filesystem_observations"]
    expected_findings = {
        "logical_single_case_count": len(logical),
        "directory_special_sequence": cases[
            "directory_special"
        ]["first_prefix_tokens"],
        "directory_nonutf8_sequence": cases[
            "directory_nonutf8"
        ]["first_prefix_tokens"],
        "explicit_target_sequence": cases["explicit_order"][
            "first_prefix_tokens"
        ],
        "explicit_target_order_is_preserved": (
            cases["explicit_order"]["first_prefix_tokens"]
            == ["emoji", "nfc", "ascii"]
        ),
        "case_alias_same_file": observations[
            "lowercase_alias_is_same_file"
        ],
        "unicode_alias_same_file": observations[
            "nfd_alias_is_same_file"
        ],
        "created_raw_name_count": sum(
            attempt["created"]
            for attempt in fixture_report["fixture"]["raw_attempts"]
        ),
        "leading_dash_requires_option_terminator_when_relative": (
            cases["leading_dash_relative_unescaped"]["first"][
                "exit_code"
            ]
            == 1
            and cases["leading_dash_relative_escaped"]["first"][
                "exit_code"
            ]
            == 0
        ),
    }
    if report["findings"] != expected_findings:
        raise ReportError("special-path findings drift")
    case_count = len(cases_contract)
    expected_summary = {
        "case_count": case_count,
        "execution_count": 2 * case_count,
        "raw_stream_count": 4 * case_count,
        "determinism_failures": determinism_failures,
        "expected_exit_failures": exit_failures,
        "reference_projection_failures": projection_failures,
        "deterministic": not determinism_failures,
        "expected_exits_equal": not exit_failures,
        "reference_projections_equal": not projection_failures,
    }
    if report["summary"] != expected_summary:
        raise ReportError("special-path summary drift")
    if report["admission"] != {
        "platform_admitted": False,
        "capability_rows_admitted": 0,
        "reason": collector.ADMISSION_REASON,
    }:
        raise ReportError("candidate must not admit capability evidence")
    if report["limitations"] != collector.LIMITATIONS:
        raise ReportError("special-path limitations drift")
    raw_root = bundle / "raw" / "cli-special-path"
    actual_raw = {
        path.relative_to(bundle).as_posix()
        for path in raw_root.rglob("*")
        if path.is_file()
    }
    if actual_raw != declared_raw:
        raise ReportError(
            "special-path raw file inventory differs from report"
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
            "macos_cli_baseline_validator_special_path_entry",
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
            f"macOS CLI special-path validation error: {error}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
