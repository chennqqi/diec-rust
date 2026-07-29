#!/usr/bin/env python3
"""Validate the primary macOS Qt5 CLI option matrix candidate bundle."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path
from typing import Any

UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
PLATFORM = "macos-x86_64-qt5"
COLLECTOR = "tools/upstream/collect_macos_cli_matrix.py"
BASELINE_COLLECTOR = "tools/upstream/collect_macos_cli_baseline.py"
BASELINE_VALIDATOR = "tools/upstream/validate_macos_cli_baseline.py"
WINDOWS_MATRIX_HELPER = "tools/upstream/collect_windows_cli_matrix.py"
MATRIX_DEFINITIONS = "tools/upstream/compare_cli_oracles.py"
BASELINE_MANIFEST = "docs/research/data/baseline-corpus.json"
LINUX_REFERENCES = {
    "output": "docs/research/data/cli-output-matrix-linux-qt5-qt6.json",
    "scan": (
        "docs/research/data/"
        "cli-scan-nested-matrix-linux-qt5-qt6.json"
    ),
    "special": (
        "docs/research/data/cli-special-matrix-linux-qt5-qt6.json"
    ),
}


class ReportError(ValueError):
    """The matrix candidate is incomplete, unsafe, or inconsistent."""


def require_object(value: Any, description: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReportError(f"{description} must be an object")
    return value


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def observation_summary(
    observation: tuple[int, bytes, bytes],
) -> dict[str, Any]:
    return {
        "exit_code": observation[0],
        "stdout_bytes": len(observation[1]),
        "stdout_sha256": sha256(observation[1]),
        "stderr_bytes": len(observation[2]),
        "stderr_sha256": sha256(observation[2]),
    }


def report_observation_identity(
    value: dict[str, Any],
) -> dict[str, Any]:
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


def observation_differences(
    first: tuple[int, bytes, bytes],
    second: tuple[int, bytes, bytes],
) -> list[str]:
    differences = []
    if first[0] != second[0]:
        differences.append("exit_code")
    if first[1] != second[1]:
        differences.append("stdout")
    if first[2] != second[2]:
        differences.append("stderr")
    return differences


def validate_report(
    report: dict[str, Any],
    *,
    report_path: Path,
    oracle_path: Path,
    baseline_path: Path,
    root: Path,
) -> None:
    expected_report_path = (
        report_path.parent / "cli-matrix-candidate.json"
    ).resolve(strict=True)
    if report_path != expected_report_path:
        raise ReportError(
            "report must be bundle-local cli-matrix-candidate.json"
        )
    expected_oracle = (
        report_path.parent / "oracle-candidate.json"
    ).resolve(strict=True)
    if oracle_path != expected_oracle:
        raise ReportError(
            "oracle must be bundle-local oracle-candidate.json"
        )
    expected_baseline = (
        report_path.parent / "cli-baseline-candidate.json"
    ).resolve(strict=True)
    if baseline_path != expected_baseline:
        raise ReportError(
            "baseline must be bundle-local cli-baseline-candidate.json"
        )

    expected_root = {
        "schema_version",
        "result",
        "platform",
        "generator",
        "oracle_report",
        "cli_baseline_report",
        "source",
        "qt",
        "binary",
        "corpus_manifest",
        "linux_qt5_references",
        "selection",
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
        root, COLLECTOR, "macos_cli_matrix_collector_for_validation"
    )
    baseline_collector = _load(
        root,
        BASELINE_COLLECTOR,
        "macos_cli_baseline_collector_for_matrix_validation",
    )
    baseline_validator = _load(
        root,
        BASELINE_VALIDATOR,
        "macos_cli_baseline_validator_for_matrix_validation",
    )
    matrix_helper = _load(
        root,
        WINDOWS_MATRIX_HELPER,
        "windows_cli_matrix_helper_for_macos_validation",
    )
    definitions = _load(
        root,
        MATRIX_DEFINITIONS,
        "cli_matrix_definitions_for_macos_validation",
    )
    common = baseline_collector.load_module(
        "windows_cli_common_for_macos_matrix_validation",
        root / baseline_collector.SHARED_COLLECTOR,
    )

    expected_generator = {
        "path": COLLECTOR,
        "sha256": sha256((root / COLLECTOR).read_bytes()),
        "validator_path": (
            "tools/upstream/validate_macos_cli_matrix.py"
        ),
        "validator_sha256": sha256(Path(__file__).read_bytes()),
        "baseline_collector_path": BASELINE_COLLECTOR,
        "baseline_collector_sha256": sha256(
            (root / BASELINE_COLLECTOR).read_bytes()
        ),
        "baseline_validator_path": BASELINE_VALIDATOR,
        "baseline_validator_sha256": sha256(
            (root / BASELINE_VALIDATOR).read_bytes()
        ),
        "windows_matrix_helper_path": WINDOWS_MATRIX_HELPER,
        "windows_matrix_helper_sha256": sha256(
            (root / WINDOWS_MATRIX_HELPER).read_bytes()
        ),
        "matrix_definitions_path": MATRIX_DEFINITIONS,
        "matrix_definitions_sha256": sha256(
            (root / MATRIX_DEFINITIONS).read_bytes()
        ),
    }
    if report["generator"] != expected_generator:
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
            f"CLI baseline bundle is invalid: {error}"
        ) from error
    oracle_raw = oracle_path.read_bytes()
    baseline_raw = baseline_path.read_bytes()
    if report["oracle_report"] != {
        "path": "oracle-candidate.json",
        "sha256": sha256(oracle_raw),
    }:
        raise ReportError("oracle report binding drift")
    if report["cli_baseline_report"] != {
        "path": "cli-baseline-candidate.json",
        "sha256": sha256(baseline_raw),
    }:
        raise ReportError("CLI baseline report binding drift")
    for field in ("source", "qt", "binary", "corpus_manifest"):
        if report[field] != baseline_report[field]:
            raise ReportError(
                f"matrix {field} differs from CLI baseline"
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

    cases_by_kind = {
        "output": definitions.OUTPUT_MATRIX,
        "scan": definitions.SCAN_MATRIX,
        "special": definitions.SPECIAL_MATRIX,
    }
    manifest = baseline_collector.load_json(
        root / BASELINE_MANIFEST
    )[0]
    manifest_samples = manifest.get("samples")
    if not isinstance(manifest_samples, list):
        raise ReportError("baseline manifest samples missing")
    samples = [str(sample["name"]) for sample in manifest_samples]
    if set(samples) != set(baseline_report["corpus"]):
        raise ReportError("baseline corpus set differs from manifest")
    expected_selection = {
        "output": list(collector.OUTPUT_SAMPLES),
        "scan": samples,
        "special": list(collector.SPECIAL_SAMPLES),
    }
    if report["selection"] != expected_selection:
        raise ReportError("matrix selection drift")

    linux_reports: dict[str, dict[str, Any]] = {}
    expected_linux_bindings = {}
    for kind, relative in LINUX_REFERENCES.items():
        value, raw = baseline_collector.load_json(root / relative)
        linux_reports[kind] = value
        expected_linux_bindings[kind] = {
            "path": relative,
            "sha256": sha256(raw),
        }
        matrix_helper.validate_reference_matrix(
            value,
            kind=kind,
            samples=collector.OUTPUT_SAMPLES,
            cases=cases_by_kind[kind],
        )
    if report["linux_qt5_references"] != expected_linux_bindings:
        raise ReportError("Linux reference bindings drift")

    matrix = require_object(report["matrix"], "matrix")
    if set(matrix) != set(samples):
        raise ReportError("matrix sample set drift")
    for sample_name in samples:
        sample_report = require_object(
            matrix[sample_name], f"matrix.{sample_name}"
        )
        expected_kinds = {
            kind
            for kind, selected_samples in expected_selection.items()
            if sample_name in selected_samples
        }
        if set(sample_report) != expected_kinds:
            raise ReportError(
                f"matrix kind set drift: {sample_name}"
            )
    determinism_failures: list[str] = []
    default_reference_failures: list[str] = []
    linux_exit_code_failures: list[str] = []
    declared_raw: set[str] = set()

    for kind in ("output", "scan", "special"):
        selected_samples = expected_selection[kind]
        expected_case_names = {
            case.name for case in cases_by_kind[kind]
        }
        for sample_name in selected_samples:
            sample_report = require_object(
                matrix[sample_name], f"matrix.{sample_name}"
            )
            kind_report = require_object(
                sample_report.get(kind),
                f"matrix.{sample_name}.{kind}",
            )
            if set(kind_report) != expected_case_names:
                raise ReportError(
                    f"matrix case set drift: {sample_name}.{kind}"
                )
            observations: dict[
                str,
                tuple[
                    tuple[int, bytes, bytes],
                    tuple[int, bytes, bytes],
                ],
            ] = {}
            for case in cases_by_kind[kind]:
                description = (
                    f"matrix.{sample_name}.{kind}.{case.name}"
                )
                entry = require_object(
                    kind_report[case.name], description
                )
                expected_fields = {
                    "first",
                    "second",
                    "determinism_differences",
                    "arguments",
                }
                if kind == "scan":
                    expected_fields.update(
                        {
                            "first_detect_tree",
                            "second_detect_tree",
                            "first_changes_from_default",
                            "second_changes_from_default",
                        }
                    )
                    if case.name == "default":
                        expected_fields.add(
                            "cli_baseline_reference_equal"
                        )
                if sample_name in collector.OUTPUT_SAMPLES:
                    expected_fields.update(
                        {
                            "linux_qt5_exit_code",
                            "linux_qt5_exit_code_equal",
                        }
                    )
                if set(entry) != expected_fields:
                    raise ReportError(
                        f"matrix field set drift: {description}"
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
                        f"matrix arguments drift: {description}"
                    )
                try:
                    first, second = baseline_validator.validate_pair(
                        entry,
                        report_path.parent,
                        description,
                        (
                            "cli-matrix/"
                            f"{sample_name}/{kind}/{case.name}"
                        ),
                    )
                except baseline_validator.ReportError as error:
                    raise ReportError(str(error)) from error
                observations[case.name] = (first, second)
                for observation_name in ("first", "second"):
                    observation = require_object(
                        entry[observation_name],
                        f"{description}.{observation_name}",
                    )
                    declared_raw.update(
                        {
                            observation["stdout_path"],
                            observation["stderr_path"],
                        }
                    )
                if first != second:
                    determinism_failures.append(description)
                if kind == "scan":
                    first_tree = common.json_detect_tree(first[1])
                    second_tree = common.json_detect_tree(second[1])
                    if (
                        entry["first_detect_tree"] != first_tree
                        or entry["second_detect_tree"] != second_tree
                    ):
                        raise ReportError(
                            f"detect tree drift: {description}"
                        )
                if sample_name in collector.OUTPUT_SAMPLES:
                    linux_entry = linux_reports[kind]["matrix"][
                        sample_name
                    ][kind][case.name]
                    linux_exit = linux_entry["left"]["exit_code"]
                    equal = first[0] == linux_exit
                    if (
                        entry["linux_qt5_exit_code"] != linux_exit
                        or entry["linux_qt5_exit_code_equal"]
                        is not equal
                    ):
                        raise ReportError(
                            f"Linux exit projection drift: {description}"
                        )
                    if not equal:
                        linux_exit_code_failures.append(description)

            if kind == "scan":
                default_first, default_second = observations["default"]
                default_entry = kind_report["default"]
                baseline_entry = baseline_report["corpus"][
                    sample_name
                ]
                reference_equal = (
                    observation_summary(default_first)
                    == report_observation_identity(
                        baseline_entry["first"]
                    )
                    and observation_summary(default_second)
                    == report_observation_identity(
                        baseline_entry["second"]
                    )
                    and default_entry["first_detect_tree"]
                    == baseline_entry["first_detect_tree"]
                    and default_entry["second_detect_tree"]
                    == baseline_entry["second_detect_tree"]
                )
                if (
                    default_entry["cli_baseline_reference_equal"]
                    is not reference_equal
                ):
                    raise ReportError(
                        "CLI baseline projection drift: "
                        f"{sample_name}"
                    )
                if not reference_equal:
                    default_reference_failures.append(sample_name)
                for case_name, (first, second) in (
                    observations.items()
                ):
                    entry = kind_report[case_name]
                    expected_first = observation_differences(
                        default_first, first
                    )
                    expected_second = observation_differences(
                        default_second, second
                    )
                    if (
                        entry["first_changes_from_default"]
                        != expected_first
                        or entry["second_changes_from_default"]
                        != expected_second
                    ):
                        raise ReportError(
                            "default delta drift: "
                            f"{sample_name}.{case_name}"
                        )

    case_counts = {
        kind: len(expected_selection[kind])
        * len(cases_by_kind[kind])
        for kind in expected_selection
    }
    case_count = sum(case_counts.values())
    expected_summary = {
        "sample_count": len(samples),
        "case_counts": case_counts,
        "case_count": case_count,
        "execution_count": 2 * case_count,
        "raw_stream_count": 4 * case_count,
        "determinism_failures": determinism_failures,
        "default_reference_failures": default_reference_failures,
        "linux_exit_code_failures": linux_exit_code_failures,
        "deterministic": not determinism_failures,
        "default_reference_equal": not default_reference_failures,
        "linux_exit_codes_equal": not linux_exit_code_failures,
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

    raw_root = report_path.parent / "raw" / "cli-matrix"
    actual_raw = {
        path.relative_to(report_path.parent).as_posix()
        for path in raw_root.rglob("*")
        if path.is_file()
    }
    if actual_raw != declared_raw:
        raise ReportError("matrix raw file inventory differs from report")


def _load(root: Path, relative: str, name: str) -> Any:
    import importlib.util

    path = root / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ReportError(f"cannot load helper module: {relative}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--oracle-report", type=Path, required=True)
    parser.add_argument("--cli-baseline-report", type=Path, required=True)
    parser.set_defaults(root=root)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report_path = args.report.resolve(strict=True)
        oracle_path = args.oracle_report.resolve(strict=True)
        baseline_path = args.cli_baseline_report.resolve(strict=True)
        baseline_validator = _load(
            args.root.resolve(),
            BASELINE_VALIDATOR,
            "macos_cli_baseline_validator_for_matrix_entry",
        )
        report = baseline_validator.load_json(report_path)[0]
        validate_report(
            report,
            report_path=report_path,
            oracle_path=oracle_path,
            baseline_path=baseline_path,
            root=args.root.resolve(),
        )
    except (ReportError, OSError, ValueError) as error:
        print(
            f"macOS CLI matrix validation error: {error}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
