#!/usr/bin/env python3
"""Validate remaining macOS Qt5 output and special CLI candidates."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Any

UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
PLATFORM = "macos-x86_64-qt5"
COLLECTOR = "tools/upstream/collect_macos_cli_remaining.py"
BASELINE_COLLECTOR = "tools/upstream/collect_macos_cli_baseline.py"
BASELINE_VALIDATOR = "tools/upstream/validate_macos_cli_baseline.py"
PRIMARY_VALIDATOR = "tools/upstream/validate_macos_cli_matrix.py"
WINDOWS_MATRIX_HELPER = "tools/upstream/collect_windows_cli_matrix.py"
OUTPUT_HELPER = (
    "tools/upstream/collect_windows_cli_output_remaining.py"
)
SPECIAL_HELPER = (
    "tools/upstream/collect_windows_cli_special_remaining.py"
)
MATRIX_DEFINITIONS = "tools/upstream/compare_cli_oracles.py"
BASELINE_MANIFEST = "docs/research/data/baseline-corpus.json"


class ReportError(ValueError):
    """The remaining CLI candidate is incomplete or inconsistent."""


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


def _identity(value: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "exit_code",
        "stdout_bytes",
        "stdout_sha256",
        "stderr_bytes",
        "stderr_sha256",
    )
    if any(field not in value for field in fields):
        raise ReportError("baseline observation identity incomplete")
    return {field: value[field] for field in fields}


def validate_report(
    report: dict[str, Any],
    *,
    report_path: Path,
    oracle_path: Path,
    baseline_path: Path,
    primary_path: Path,
    root: Path,
) -> None:
    bundle = report_path.parent
    expected_paths = {
        report_path: "cli-remaining-candidate.json",
        oracle_path: "oracle-candidate.json",
        baseline_path: "cli-baseline-candidate.json",
        primary_path: "cli-matrix-candidate.json",
    }
    for path, name in expected_paths.items():
        if path != (bundle / name).resolve(strict=True):
            raise ReportError(
                f"report must be bundle-local: {name}"
            )
    expected_root = {
        "schema_version",
        "result",
        "platform",
        "generator",
        "oracle_report",
        "cli_baseline_report",
        "cli_primary_matrix_report",
        "source",
        "qt",
        "binary",
        "corpus_manifest",
        "selection",
        "cases",
        "output_classification",
        "priority_references",
        "matrix",
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
        root, COLLECTOR, "macos_cli_remaining_collector_validation"
    )
    baseline_collector = _load(
        root,
        BASELINE_COLLECTOR,
        "macos_cli_baseline_collector_remaining_validation",
    )
    baseline_validator = _load(
        root,
        BASELINE_VALIDATOR,
        "macos_cli_baseline_validator_remaining_validation",
    )
    primary_validator = _load(
        root,
        PRIMARY_VALIDATOR,
        "macos_cli_primary_validator_remaining_validation",
    )
    matrix_helper = _load(
        root,
        WINDOWS_MATRIX_HELPER,
        "windows_cli_matrix_helper_remaining_validation",
    )
    output_helper = _load(
        root,
        OUTPUT_HELPER,
        "windows_output_remaining_helper_validation",
    )
    special_helper = _load(
        root,
        SPECIAL_HELPER,
        "windows_special_remaining_helper_validation",
    )
    definitions = _load(
        root,
        MATRIX_DEFINITIONS,
        "cli_matrix_definitions_remaining_validation",
    )
    common = baseline_collector.load_module(
        "windows_cli_common_remaining_validation",
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
        primary_report = baseline_validator.load_json(
            primary_path
        )[0]
        primary_validator.validate_report(
            primary_report,
            report_path=primary_path,
            oracle_path=oracle_path,
            baseline_path=baseline_path,
            root=root,
        )
    except (
        baseline_validator.ReportError,
        primary_validator.ReportError,
    ) as error:
        raise ReportError(
            f"input CLI bundle is invalid: {error}"
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
        "cli_primary_matrix_report": {
            "path": "cli-matrix-candidate.json",
            "sha256": sha256(primary_path.read_bytes()),
        },
    }
    for field, expected in expected_bindings.items():
        if report[field] != expected:
            raise ReportError(f"{field} binding drift")
    for field in ("source", "qt", "binary", "corpus_manifest"):
        if (
            report[field] != baseline_report[field]
            or report[field] != primary_report[field]
        ):
            raise ReportError(
                f"remaining {field} identity differs"
            )
    if report["source"] != {
        "repository": "https://github.com/horsicq/DIE-engine",
        "commit": UPSTREAM_COMMIT,
        "recursive_submodule_count": 58,
        "rules_commit": RULES_COMMIT,
        "tracked_files_clean_before_and_after": True,
    }:
        raise ReportError("source identity drift")
    if (
        report["binary"].get("relative_path")
        != "build/release/diec"
        or report["corpus_manifest"].get("path")
        != BASELINE_MANIFEST
        or report["corpus_manifest"].get("sample_count") != 26
    ):
        raise ReportError("binary or corpus identity drift")

    manifest = baseline_collector.load_json(
        root / BASELINE_MANIFEST
    )[0]
    manifest_samples = manifest.get("samples")
    if not isinstance(manifest_samples, list):
        raise ReportError("baseline manifest samples missing")
    sample_names = [str(item["name"]) for item in manifest_samples]
    covered = list(primary_report["selection"]["output"])
    selection = [
        name for name in sample_names if name not in covered
    ]
    if len(selection) != 21 or report["selection"] != selection:
        raise ReportError("remaining sample selection drift")
    cases_by_kind = {
        "output": definitions.OUTPUT_MATRIX,
        "special": definitions.SPECIAL_MATRIX,
    }
    expected_cases = {
        kind: [case.name for case in cases_by_kind[kind]]
        for kind in cases_by_kind
    }
    if report["cases"] != expected_cases:
        raise ReportError("remaining case inventory drift")
    expected_classification = {
        "expected_invalid_xml_samples": list(
            output_helper.EXPECTED_INVALID_XML
        ),
        "special_json": list(special_helper.JSON_CASES),
        "special_xml": list(special_helper.XML_CASES),
    }
    if report["output_classification"] != expected_classification:
        raise ReportError("output classification drift")
    expected_priorities = {
        "output_all_flags": "csv",
        "special": special_helper.PRIORITY_REFERENCES,
    }
    if report["priority_references"] != expected_priorities:
        raise ReportError("priority reference drift")

    matrix = require_object(report["matrix"], "matrix")
    if set(matrix) != set(selection):
        raise ReportError("remaining matrix sample set drift")
    determinism_failures: list[str] = []
    exit_failures: list[str] = []
    stderr_failures: list[str] = []
    validity_failures: list[str] = []
    json_reference_failures: list[str] = []
    priority_failures: list[str] = []
    declared_raw: set[str] = set()

    for sample_name in selection:
        sample_report = require_object(
            matrix[sample_name], f"matrix.{sample_name}"
        )
        if set(sample_report) != {"output", "special"}:
            raise ReportError(
                f"remaining matrix kind set drift: {sample_name}"
            )
        for kind in ("output", "special"):
            kind_report = require_object(
                sample_report[kind],
                f"matrix.{sample_name}.{kind}",
            )
            if set(kind_report) != set(expected_cases[kind]):
                raise ReportError(
                    f"remaining case set drift: {sample_name}.{kind}"
                )
            observations = {}
            for case in cases_by_kind[kind]:
                description = (
                    f"matrix.{sample_name}.{kind}.{case.name}"
                )
                entry = require_object(
                    kind_report[case.name], description
                )
                fields = {
                    "first",
                    "second",
                    "determinism_differences",
                    "arguments",
                    "expected_exit_code",
                    "expected_exit_code_equal",
                    "expected_empty_stderr",
                    "first_stderr_empty",
                    "second_stderr_empty",
                    "first_output_valid",
                    "second_output_valid",
                }
                if kind == "output":
                    fields.update(
                        {
                            "expected_output_valid",
                            "output_validity_expected_equal",
                        }
                    )
                    if case.name == "json":
                        fields.update(
                            {
                                "first_detect_tree",
                                "second_detect_tree",
                                "cli_baseline_reference_equal",
                            }
                        )
                    if case.name == "all_output_flags":
                        fields.add(
                            "csv_priority_reference_equal"
                        )
                else:
                    if (
                        case.name in special_helper.JSON_CASES
                        or case.name in special_helper.XML_CASES
                    ):
                        fields.update(
                            {
                                "first_projection",
                                "second_projection",
                            }
                        )
                    if (
                        case.name
                        in special_helper.PRIORITY_REFERENCES
                    ):
                        fields.update(
                            {
                                "priority_reference_case",
                                "priority_reference_equal",
                            }
                        )
                if set(entry) != fields:
                    raise ReportError(
                        f"remaining field set drift: {description}"
                    )
                expected_arguments = [
                    *matrix_helper.translate_arguments(
                        case.arguments,
                        Path("<source>"),
                        report=True,
                    ),
                    f"<corpus>/{sample_name}",
                ]
                if entry["arguments"] != expected_arguments:
                    raise ReportError(
                        f"remaining arguments drift: {description}"
                    )
                try:
                    first, second = baseline_validator.validate_pair(
                        entry,
                        bundle,
                        description,
                        (
                            "cli-remaining/"
                            f"{sample_name}/{kind}/{case.name}"
                        ),
                    )
                except baseline_validator.ReportError as error:
                    raise ReportError(str(error)) from error
                observations[case.name] = (first, second)
                for side in ("first", "second"):
                    raw = require_object(
                        entry[side], f"{description}.{side}"
                    )
                    declared_raw.update(
                        {
                            raw["stdout_path"],
                            raw["stderr_path"],
                        }
                    )
                if first != second:
                    determinism_failures.append(description)
                expected_exit_equal = first[0] == 0
                first_stderr_empty = first[2] == b""
                second_stderr_empty = second[2] == b""
                if (
                    entry["expected_exit_code"] != 0
                    or entry["expected_exit_code_equal"]
                    is not expected_exit_equal
                    or entry["expected_empty_stderr"] is not True
                    or entry["first_stderr_empty"]
                    is not first_stderr_empty
                    or entry["second_stderr_empty"]
                    is not second_stderr_empty
                ):
                    raise ReportError(
                        f"exit/stderr projection drift: {description}"
                    )
                if not expected_exit_equal:
                    exit_failures.append(description)
                if not first_stderr_empty or not second_stderr_empty:
                    stderr_failures.append(description)

                if kind == "output":
                    first_valid = output_helper.output_validity(
                        case.name, first[1]
                    )
                    second_valid = output_helper.output_validity(
                        case.name, second[1]
                    )
                    expected_valid = not (
                        case.name == "xml"
                        and sample_name
                        in output_helper.EXPECTED_INVALID_XML
                    )
                    validity_equal = (
                        first_valid == expected_valid
                        and second_valid == expected_valid
                    )
                    if (
                        entry["first_output_valid"]
                        is not first_valid
                        or entry["second_output_valid"]
                        is not second_valid
                        or entry["expected_output_valid"]
                        is not expected_valid
                        or entry["output_validity_expected_equal"]
                        is not validity_equal
                    ):
                        raise ReportError(
                            f"output validity drift: {description}"
                        )
                    if not validity_equal:
                        validity_failures.append(description)
                    if case.name == "json":
                        first_tree = common.json_detect_tree(first[1])
                        second_tree = common.json_detect_tree(
                            second[1]
                        )
                        baseline_entry = baseline_report["corpus"][
                            sample_name
                        ]
                        reference_equal = (
                            _summary(first)
                            == _identity(baseline_entry["first"])
                            and _summary(second)
                            == _identity(baseline_entry["second"])
                            and first_tree
                            == baseline_entry["first_detect_tree"]
                            and second_tree
                            == baseline_entry["second_detect_tree"]
                        )
                        if (
                            entry["first_detect_tree"] != first_tree
                            or entry["second_detect_tree"]
                            != second_tree
                            or entry["cli_baseline_reference_equal"]
                            is not reference_equal
                        ):
                            raise ReportError(
                                f"JSON baseline drift: {description}"
                            )
                        if not reference_equal:
                            json_reference_failures.append(
                                sample_name
                            )
                else:
                    first_valid, first_projection = (
                        special_helper.parse_output(
                            case.name, first[1]
                        )
                    )
                    second_valid, second_projection = (
                        special_helper.parse_output(
                            case.name, second[1]
                        )
                    )
                    first_projection = (
                        special_helper.normalize_projection(
                            case.name,
                            first_projection,
                            sample_name,
                        )
                    )
                    second_projection = (
                        special_helper.normalize_projection(
                            case.name,
                            second_projection,
                            sample_name,
                        )
                    )
                    if (
                        entry["first_output_valid"]
                        is not first_valid
                        or entry["second_output_valid"]
                        is not second_valid
                    ):
                        raise ReportError(
                            f"special validity drift: {description}"
                        )
                    if not first_valid or not second_valid:
                        validity_failures.append(description)
                    if (
                        case.name in special_helper.JSON_CASES
                        or case.name in special_helper.XML_CASES
                    ) and (
                        entry["first_projection"] != first_projection
                        or entry["second_projection"]
                        != second_projection
                    ):
                        raise ReportError(
                            f"special projection drift: {description}"
                        )

            if kind == "output":
                equal = (
                    observations["all_output_flags"]
                    == observations["csv"]
                )
                entry = kind_report["all_output_flags"]
                if entry["csv_priority_reference_equal"] is not equal:
                    raise ReportError(
                        f"CSV priority drift: {sample_name}"
                    )
                if not equal:
                    priority_failures.append(
                        f"matrix.{sample_name}.output.all_output_flags"
                    )
            else:
                for case_name, reference_name in (
                    special_helper.PRIORITY_REFERENCES.items()
                ):
                    equal = (
                        observations[case_name]
                        == observations[reference_name]
                    )
                    entry = kind_report[case_name]
                    if (
                        entry["priority_reference_case"]
                        != reference_name
                        or entry["priority_reference_equal"]
                        is not equal
                    ):
                        raise ReportError(
                            "special priority drift: "
                            f"{sample_name}.{case_name}"
                        )
                    if not equal:
                        priority_failures.append(
                            "matrix."
                            f"{sample_name}.special.{case_name}"
                        )

    case_counts = {
        kind: len(selection) * len(cases_by_kind[kind])
        for kind in cases_by_kind
    }
    case_count = sum(case_counts.values())
    expected_summary = {
        "sample_count": len(selection),
        "case_counts": case_counts,
        "case_count": case_count,
        "execution_count": 2 * case_count,
        "raw_stream_count": 4 * case_count,
        "determinism_failures": determinism_failures,
        "expected_exit_failures": exit_failures,
        "stderr_failures": stderr_failures,
        "validity_failures": validity_failures,
        "json_reference_failures": json_reference_failures,
        "priority_failures": priority_failures,
        "deterministic": not determinism_failures,
        "expected_exits_equal": not exit_failures,
        "stderr_empty": not stderr_failures,
        "outputs_valid_as_expected": not validity_failures,
        "json_baseline_references_equal": (
            not json_reference_failures
        ),
        "priority_references_equal": not priority_failures,
    }
    if report["summary"] != expected_summary:
        raise ReportError("summary drift")
    if report["admission"] != {
        "platform_admitted": False,
        "capability_rows_admitted": 0,
        "reason": collector.ADMISSION_REASON,
    }:
        raise ReportError("candidate must not admit capability evidence")
    if report["limitations"] != collector.LIMITATIONS:
        raise ReportError("limitations drift")
    raw_root = bundle / "raw" / "cli-remaining"
    actual_raw = {
        path.relative_to(bundle).as_posix()
        for path in raw_root.rglob("*")
        if path.is_file()
    }
    if actual_raw != declared_raw:
        raise ReportError(
            "remaining raw file inventory differs from report"
        )


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--oracle-report", type=Path, required=True)
    parser.add_argument("--cli-baseline-report", type=Path, required=True)
    parser.add_argument("--cli-primary-matrix-report", type=Path, required=True)
    parser.set_defaults(root=root)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report_path = args.report.resolve(strict=True)
        oracle_path = args.oracle_report.resolve(strict=True)
        baseline_path = args.cli_baseline_report.resolve(strict=True)
        primary_path = args.cli_primary_matrix_report.resolve(strict=True)
        baseline_validator = _load(
            args.root.resolve(),
            BASELINE_VALIDATOR,
            "macos_cli_baseline_validator_remaining_entry",
        )
        report = baseline_validator.load_json(report_path)[0]
        validate_report(
            report,
            report_path=report_path,
            oracle_path=oracle_path,
            baseline_path=baseline_path,
            primary_path=primary_path,
            root=args.root.resolve(),
        )
    except (ReportError, OSError, ValueError) as error:
        print(
            f"macOS CLI remaining validation error: {error}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
