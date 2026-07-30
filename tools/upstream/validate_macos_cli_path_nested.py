#!/usr/bin/env python3
"""Validate a non-admitted macOS Qt5 CLI path and nested candidate."""

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
COLLECTOR = "tools/upstream/collect_macos_cli_path_nested.py"
BASELINE_COLLECTOR = "tools/upstream/collect_macos_cli_baseline.py"
BASELINE_VALIDATOR = "tools/upstream/validate_macos_cli_baseline.py"
PATH_NESTED_HELPER = (
    "tools/upstream/collect_windows_cli_path_nested.py"
)
MATRIX_DEFINITIONS = "tools/upstream/compare_cli_oracles.py"
ORACLE_VALIDATOR = (
    "tools/upstream/validate_macos_qt5_oracle_report.py"
)
PATH_MANIFEST = "docs/research/data/path-corpus.json"
NESTED_MANIFEST = "docs/research/data/nested-corpus.json"
LINUX_PATH_REFERENCE = (
    "docs/research/data/cli-path-matrix-linux-qt5-qt6.json"
)
LINUX_NESTED_REFERENCE = (
    "docs/research/data/cli-scan-nested-matrix-linux-qt5-qt6.json"
)


class ReportError(ValueError):
    """The path/nested candidate is incomplete or inconsistent."""


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


def _differences(
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
    root: Path,
) -> None:
    bundle = report_path.parent
    if report_path != (
        bundle / "cli-path-nested-candidate.json"
    ).resolve(strict=True):
        raise ReportError(
            "report must be bundle-local: "
            "cli-path-nested-candidate.json"
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
        "fixtures",
        "linux_qt5_references",
        "local_paths",
        "path",
        "nested",
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
        "macos_cli_path_nested_collector_validation",
    )
    baseline_collector = _load(
        root,
        BASELINE_COLLECTOR,
        "macos_cli_baseline_collector_path_nested_validation",
    )
    baseline_validator = _load(
        root,
        BASELINE_VALIDATOR,
        "macos_cli_baseline_validator_path_nested_validation",
    )
    helper = _load(
        root,
        PATH_NESTED_HELPER,
        "windows_cli_path_nested_helper_macos_validation",
    )
    definitions = _load(
        root,
        MATRIX_DEFINITIONS,
        "cli_matrix_definitions_path_nested_validation",
    )
    oracle_validator = _load(
        root,
        ORACLE_VALIDATOR,
        "macos_oracle_validator_path_nested_validation",
    )
    common = baseline_collector.load_module(
        "windows_cli_common_path_nested_validation",
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

    path_manifest, path_manifest_raw = baseline_validator.load_json(
        root / PATH_MANIFEST
    )
    nested_manifest, nested_manifest_raw = (
        baseline_validator.load_json(root / NESTED_MANIFEST)
    )
    nested_samples = nested_manifest.get("samples")
    if not isinstance(nested_samples, list):
        raise ReportError("nested manifest samples missing")
    expected_fixtures = {
        "path": {
            "manifest": PATH_MANIFEST,
            "sha256": sha256(path_manifest_raw),
            "directories": path_manifest["directories"],
            "entries": path_manifest["entries"],
        },
        "nested": {
            "manifest": NESTED_MANIFEST,
            "sha256": sha256(nested_manifest_raw),
            "samples": nested_samples,
        },
    }
    if report["fixtures"] != expected_fixtures:
        raise ReportError("path/nested fixture binding drift")

    path_reference, path_reference_raw = (
        baseline_validator.load_json(root / LINUX_PATH_REFERENCE)
    )
    nested_reference, nested_reference_raw = (
        baseline_validator.load_json(root / LINUX_NESTED_REFERENCE)
    )
    expected_references = {
        "path": {
            "path": LINUX_PATH_REFERENCE,
            "sha256": sha256(path_reference_raw),
        },
        "nested": {
            "path": LINUX_NESTED_REFERENCE,
            "sha256": sha256(nested_reference_raw),
        },
    }
    if report["linux_qt5_references"] != expected_references:
        raise ReportError("Linux path/nested reference binding drift")
    try:
        helper.validate_reference_cases(
            path_reference,
            nested_reference,
            nested_samples,
        )
    except ValueError as error:
        raise ReportError(
            f"Linux path/nested reference invalid: {error}"
        ) from error
    linux_path_cases = path_reference["path_corpus"]["cases"]
    linux_nested_cases = nested_reference["nested_corpus"]["cases"]

    local_paths = require_object(report["local_paths"], "local_paths")
    if set(local_paths) != {
        "path_corpus_dir",
        "nested_corpus_dir",
    }:
        raise ReportError("local path fields changed")
    values = {}
    for field in ("path_corpus_dir", "nested_corpus_dir"):
        value = local_paths[field]
        if (
            not isinstance(value, str)
            or not PurePosixPath(value).is_absolute()
        ):
            raise ReportError(
                f"{field} local path must be absolute"
            )
        values[field] = PurePosixPath(value)
    source_value = oracle["local_paths"]["source_dir"]
    if (
        not isinstance(source_value, str)
        or not PurePosixPath(source_value).is_absolute()
    ):
        raise ReportError("oracle source local path must be absolute")
    source_dir = PurePosixPath(source_value)
    path_corpus_dir = values["path_corpus_dir"]
    nested_corpus_dir = values["nested_corpus_dir"]

    path_root = require_object(report["path"], "path")
    path_cases = require_object(path_root.get("cases"), "path.cases")
    if set(path_root) != {"cases"} or set(path_cases) != {
        case.name for case in definitions.PATH_CASES
    }:
        raise ReportError("path case set drift")
    nested_root = require_object(report["nested"], "nested")
    nested_cases = require_object(
        nested_root.get("cases"), "nested.cases"
    )
    sample_names = [str(sample["name"]) for sample in nested_samples]
    if set(nested_root) != {"cases"} or set(nested_cases) != set(
        sample_names
    ):
        raise ReportError("nested sample set drift")

    determinism_failures: list[str] = []
    exit_failures: list[str] = []
    path_prefix_failures: list[str] = []
    nested_projection_failures: list[str] = []
    declared_raw: set[str] = set()
    path_observations: dict[
        str,
        tuple[
            tuple[int, bytes, bytes],
            tuple[int, bytes, bytes],
        ],
    ] = {}
    for case in definitions.PATH_CASES:
        description = f"path.cases.{case.name}"
        entry = require_object(path_cases[case.name], description)
        fields = {
            "first",
            "second",
            "determinism_differences",
            "arguments",
            "first_filename_prefixes",
            "second_filename_prefixes",
            "linux_qt5_filename_prefixes",
            "linux_qt5_filename_prefixes_equal",
            "linux_qt5_raw_differences",
        }
        if case.name.endswith("_json"):
            fields.update(
                {
                    "first_valid_json",
                    "second_valid_json",
                    "linux_qt5_valid_json",
                }
            )
        elif case.name.endswith("_xml"):
            fields.update(
                {
                    "first_valid_xml",
                    "second_valid_xml",
                    "linux_qt5_valid_xml",
                }
            )
        if case.name == "tree_recursive_json":
            fields.update(
                {
                    "first_changes_from_tree_json",
                    "second_changes_from_tree_json",
                }
            )
        if set(entry) != fields:
            raise ReportError(f"path field set drift: {case.name}")
        expected_arguments = helper.translate_arguments(
            case.arguments,
            source_dir,
            path_corpus_dir,
            nested_corpus_dir,
            report=True,
        )
        if entry["arguments"] != list(expected_arguments):
            raise ReportError(f"path arguments drift: {case.name}")
        try:
            first, second = baseline_validator.validate_pair(
                entry,
                bundle,
                description,
                f"cli-path-nested/path/{case.name}",
            )
        except baseline_validator.ReportError as error:
            raise ReportError(str(error)) from error
        path_observations[case.name] = (first, second)
        for side in ("first", "second"):
            raw = require_object(entry[side], f"{description}.{side}")
            declared_raw.update(
                {raw["stdout_path"], raw["stderr_path"]}
            )
        first_prefixes = helper.relative_filename_prefixes(
            first[1], path_corpus_dir
        )
        second_prefixes = helper.relative_filename_prefixes(
            second[1], path_corpus_dir
        )
        linux_case = linux_path_cases[case.name]
        linux_prefixes = helper.normalized_linux_prefixes(
            linux_case["left_filename_prefixes"]
        )
        expected_projection = {
            "first_filename_prefixes": first_prefixes,
            "second_filename_prefixes": second_prefixes,
            "linux_qt5_filename_prefixes": linux_prefixes,
            "linux_qt5_filename_prefixes_equal": (
                first_prefixes == linux_prefixes
            ),
            "linux_qt5_raw_differences": (
                helper.raw_differences(
                    _summary(first), linux_case["left"]
                )
            ),
        }
        for field, expected in expected_projection.items():
            if entry[field] != expected:
                raise ReportError(
                    f"path projection drift: {case.name}.{field}"
                )
        if case.name.endswith("_json"):
            expected_validity = {
                "first_valid_json": (
                    definitions.document_is_valid(
                        first[1], "json"
                    )
                ),
                "second_valid_json": (
                    definitions.document_is_valid(
                        second[1], "json"
                    )
                ),
                "linux_qt5_valid_json": (
                    linux_case["left_valid_json"]
                ),
            }
        elif case.name.endswith("_xml"):
            expected_validity = {
                "first_valid_xml": (
                    definitions.document_is_valid(
                        first[1], "xml"
                    )
                ),
                "second_valid_xml": (
                    definitions.document_is_valid(
                        second[1], "xml"
                    )
                ),
                "linux_qt5_valid_xml": (
                    linux_case["left_valid_xml"]
                ),
            }
        else:
            expected_validity = {}
        for field, expected in expected_validity.items():
            if entry[field] != expected:
                raise ReportError(
                    f"path validity drift: {case.name}.{field}"
                )
        if first != second:
            determinism_failures.append(f"path.{case.name}")
        if first[0] != linux_case["left"]["exit_code"]:
            exit_failures.append(f"path.{case.name}")
        if first_prefixes != linux_prefixes:
            path_prefix_failures.append(case.name)

    default_first, default_second = path_observations["tree_json"]
    recursive_first, recursive_second = path_observations[
        "tree_recursive_json"
    ]
    recursive_entry = path_cases["tree_recursive_json"]
    expected_changes = {
        "first_changes_from_tree_json": _differences(
            default_first, recursive_first
        ),
        "second_changes_from_tree_json": _differences(
            default_second, recursive_second
        ),
    }
    for field, expected in expected_changes.items():
        if recursive_entry[field] != expected:
            raise ReportError(f"path recursive drift: {field}")

    for sample_name in sample_names:
        sample_report = require_object(
            nested_cases[sample_name],
            f"nested.cases.{sample_name}",
        )
        if set(sample_report) != {
            case.name for case in definitions.NESTED_MATRIX
        }:
            raise ReportError(
                f"nested case set drift: {sample_name}"
            )
        observations = {}
        for case in definitions.NESTED_MATRIX:
            description = (
                f"nested.cases.{sample_name}.{case.name}"
            )
            entry = require_object(
                sample_report[case.name], description
            )
            fields = {
                "first",
                "second",
                "determinism_differences",
                "arguments",
                "first_detect_tree",
                "second_detect_tree",
                "linux_qt5_detect_tree",
                "linux_qt5_detect_tree_equal",
                "linux_qt5_raw_differences",
                "first_changes_from_default",
                "second_changes_from_default",
            }
            if set(entry) != fields:
                raise ReportError(
                    "nested field set drift: "
                    f"{sample_name}.{case.name}"
                )
            arguments = (
                *case.arguments,
                f"/nested/{sample_name}",
            )
            expected_arguments = helper.translate_arguments(
                arguments,
                source_dir,
                path_corpus_dir,
                nested_corpus_dir,
                report=True,
            )
            if entry["arguments"] != list(expected_arguments):
                raise ReportError(
                    "nested arguments drift: "
                    f"{sample_name}.{case.name}"
                )
            try:
                first, second = baseline_validator.validate_pair(
                    entry,
                    bundle,
                    description,
                    (
                        "cli-path-nested/nested/"
                        f"{sample_name}/{case.name}"
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
                    {raw["stdout_path"], raw["stderr_path"]}
                )
            first_tree = common.json_detect_tree(first[1])
            second_tree = common.json_detect_tree(second[1])
            linux_case = linux_nested_cases[sample_name][case.name]
            linux_tree = linux_case["left_detect_tree"]
            expected_projection = {
                "first_detect_tree": first_tree,
                "second_detect_tree": second_tree,
                "linux_qt5_detect_tree": linux_tree,
                "linux_qt5_detect_tree_equal": (
                    first_tree == linux_tree
                ),
                "linux_qt5_raw_differences": (
                    helper.raw_differences(
                        _summary(first), linux_case["left"]
                    )
                ),
            }
            for field, expected in expected_projection.items():
                if entry[field] != expected:
                    raise ReportError(
                        "nested projection drift: "
                        f"{sample_name}.{case.name}.{field}"
                    )
            identity = f"nested.{sample_name}.{case.name}"
            if first != second:
                determinism_failures.append(identity)
            if first[0] != linux_case["left"]["exit_code"]:
                exit_failures.append(identity)
            if first_tree != linux_tree:
                nested_projection_failures.append(identity)

        default_first, default_second = observations["default"]
        for case_name, (first, second) in observations.items():
            entry = sample_report[case_name]
            expected_changes = {
                "first_changes_from_default": _differences(
                    default_first, first
                ),
                "second_changes_from_default": _differences(
                    default_second, second
                ),
            }
            for field, expected in expected_changes.items():
                if entry[field] != expected:
                    raise ReportError(
                        "nested default projection drift: "
                        f"{sample_name}.{case_name}.{field}"
                    )

    path_case_count = len(definitions.PATH_CASES)
    nested_case_count = len(nested_samples) * len(
        definitions.NESTED_MATRIX
    )
    case_count = path_case_count + nested_case_count
    expected_summary = {
        "path_case_count": path_case_count,
        "nested_sample_count": len(nested_samples),
        "nested_case_count": nested_case_count,
        "case_count": case_count,
        "execution_count": 2 * case_count,
        "raw_stream_count": 4 * case_count,
        "determinism_failures": determinism_failures,
        "linux_exit_code_failures": exit_failures,
        "path_prefix_failures": path_prefix_failures,
        "nested_projection_failures": nested_projection_failures,
        "deterministic": not determinism_failures,
        "linux_exit_codes_equal": not exit_failures,
        "path_prefixes_equal": not path_prefix_failures,
        "nested_projections_equal": (
            not nested_projection_failures
        ),
    }
    if report["summary"] != expected_summary:
        raise ReportError("path/nested summary drift")
    if report["admission"] != {
        "platform_admitted": False,
        "capability_rows_admitted": 0,
        "reason": collector.ADMISSION_REASON,
    }:
        raise ReportError("candidate must not admit capability evidence")
    if report["limitations"] != collector.LIMITATIONS:
        raise ReportError("path/nested limitations drift")
    raw_root = bundle / "raw" / "cli-path-nested"
    actual_raw = {
        path.relative_to(bundle).as_posix()
        for path in raw_root.rglob("*")
        if path.is_file()
    }
    if actual_raw != declared_raw:
        raise ReportError(
            "path/nested raw file inventory differs from report"
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
            "macos_cli_baseline_validator_path_nested_entry",
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
            f"macOS CLI path/nested validation error: {error}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
