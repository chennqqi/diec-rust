#!/usr/bin/env python3
"""Collect a non-admitted macOS Qt5 CLI path and nested candidate."""

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
PATH_NESTED_HELPER = (
    "tools/upstream/collect_windows_cli_path_nested.py"
)
MATRIX_DEFINITIONS = "tools/upstream/compare_cli_oracles.py"
VALIDATOR = "tools/upstream/validate_macos_cli_path_nested.py"
PATH_MANIFEST = "docs/research/data/path-corpus.json"
NESTED_MANIFEST = "docs/research/data/nested-corpus.json"
LINUX_PATH_REFERENCE = (
    "docs/research/data/cli-path-matrix-linux-qt5-qt6.json"
)
LINUX_NESTED_REFERENCE = (
    "docs/research/data/cli-scan-nested-matrix-linux-qt5-qt6.json"
)
ADMISSION_REASON = (
    "path and nested CLI candidate only; macOS runtime evidence has not "
    "been reviewed or projected into the 68-row capability closure"
)
LIMITATIONS = [
    (
        "path evidence covers the committed five-file directory tree, "
        "multi-target framing, duplicates, missing paths, and formatter "
        "validity"
    ),
    (
        "nested evidence covers eight committed safe fixtures and the four "
        "published recursive/aggressive combinations"
    ),
    (
        "Unicode normalization, symlink cycles, permissions, large "
        "directories, filesystem ordering, TOCTOU, and engine-only "
        "archive/resource controls remain open"
    ),
    (
        "raw streams remain authoritative; only named exit, relative "
        "path-prefix order, formatter validity, and detection-tree "
        "projections are compared with Linux Qt5"
    ),
]


class PathNestedError(ValueError):
    """The path/nested candidate cannot be collected safely."""


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _load(root: Path, relative: str, name: str) -> Any:
    path = root / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise PathNestedError(f"cannot load helper module: {relative}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _generator_bindings(root: Path) -> dict[str, str]:
    paths = {
        "path": "tools/upstream/collect_macos_cli_path_nested.py",
        "validator_path": VALIDATOR,
        "baseline_collector_path": BASELINE_COLLECTOR,
        "baseline_validator_path": BASELINE_VALIDATOR,
        "path_nested_helper_path": PATH_NESTED_HELPER,
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


def collect(
    *,
    root: Path,
    binary: Path,
    source_dir: Path,
    qt_dir: Path,
    path_corpus_dir: Path,
    nested_corpus_dir: Path,
    oracle_path: Path,
    output: Path,
    timeout_seconds: int,
) -> dict[str, Any]:
    if sys.platform != "darwin" or platform.machine() != "x86_64":
        raise PathNestedError("collector requires native Darwin x86_64")
    if not 1 <= timeout_seconds <= 3600:
        raise PathNestedError("timeout-seconds must be in 1..3600")
    source_dir = source_dir.resolve(strict=True)
    qt_dir = qt_dir.resolve(strict=True)
    path_corpus_dir = path_corpus_dir.resolve(strict=True)
    nested_corpus_dir = nested_corpus_dir.resolve(strict=True)
    binary = binary.resolve(strict=True)
    oracle_path = oracle_path.resolve(strict=True)
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if oracle_path != (
        output.parent / "oracle-candidate.json"
    ).resolve(strict=True):
        raise PathNestedError(
            "oracle report must be bundle-local: oracle-candidate.json"
        )
    if output.exists():
        raise PathNestedError("candidate report already exists")
    raw_dir = output.parent / "raw" / "cli-path-nested"
    raw_dir.mkdir(parents=True, exist_ok=True)
    if any(raw_dir.iterdir()):
        raise PathNestedError("path/nested raw directory must be empty")

    baseline_collector = _load(
        root,
        BASELINE_COLLECTOR,
        "macos_cli_baseline_collector_for_path_nested",
    )
    helper = _load(
        root,
        PATH_NESTED_HELPER,
        "windows_cli_path_nested_helper_for_macos",
    )
    definitions = _load(
        root,
        MATRIX_DEFINITIONS,
        "cli_matrix_definitions_for_macos_path_nested",
    )
    common = baseline_collector.load_module(
        "windows_cli_common_for_macos_path_nested",
        root / baseline_collector.SHARED_COLLECTOR,
    )
    oracle, oracle_raw = baseline_collector.validate_oracle_inputs(
        root, oracle_path, source_dir, qt_dir, binary
    )
    expected_binary = (
        source_dir / "build" / "release" / "diec"
    ).resolve(strict=True)
    if binary != expected_binary:
        raise PathNestedError(
            "binary must be <source>/build/release/diec"
        )
    source = common.validate_source(source_dir)
    source["tracked_files_clean_before_and_after"] = True
    qt = baseline_collector.validate_qt(common, qt_dir, oracle)
    binary_sha256 = common.sha256_file(binary)
    if binary_sha256 != oracle["artifact"]["sha256"]:
        raise PathNestedError("binary differs from oracle report")

    path_manifest_raw = (path_corpus_dir / "manifest.json").read_bytes()
    nested_manifest_raw = (
        nested_corpus_dir / "manifest.json"
    ).read_bytes()
    if path_manifest_raw != (root / PATH_MANIFEST).read_bytes():
        raise PathNestedError("path corpus manifest differs")
    if nested_manifest_raw != (root / NESTED_MANIFEST).read_bytes():
        raise PathNestedError("nested corpus manifest differs")
    path_manifest = definitions.load_path_corpus(path_corpus_dir)
    nested_samples = definitions.load_nested_corpus(
        nested_corpus_dir
    )
    path_reference, path_reference_raw = helper.read_json(
        root / LINUX_PATH_REFERENCE
    )
    nested_reference, nested_reference_raw = helper.read_json(
        root / LINUX_NESTED_REFERENCE
    )
    helper.validate_reference_cases(
        path_reference,
        nested_reference,
        nested_samples,
    )
    linux_path_cases = path_reference["path_corpus"]["cases"]
    linux_nested_cases = nested_reference["nested_corpus"]["cases"]

    path_reports: dict[str, object] = {}
    nested_reports: dict[str, object] = {}
    determinism_failures: list[str] = []
    exit_failures: list[str] = []
    path_prefix_failures: list[str] = []
    nested_projection_failures: list[str] = []
    path_observations: dict[str, tuple[Any, Any]] = {}
    for case in definitions.PATH_CASES:
        actual_arguments = helper.translate_arguments(
            case.arguments,
            source_dir,
            path_corpus_dir,
            nested_corpus_dir,
            report=False,
        )
        report_arguments = helper.translate_arguments(
            case.arguments,
            source_dir,
            path_corpus_dir,
            nested_corpus_dir,
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
        path_observations[case.name] = (first, second)
        entry = baseline_collector.pair_report(
            common,
            output.parent,
            f"cli-path-nested/path/{case.name}",
            first,
            second,
        )
        first_prefixes = helper.relative_filename_prefixes(
            first.stdout, path_corpus_dir
        )
        second_prefixes = helper.relative_filename_prefixes(
            second.stdout, path_corpus_dir
        )
        linux_case = linux_path_cases[case.name]
        linux_prefixes = helper.normalized_linux_prefixes(
            linux_case["left_filename_prefixes"]
        )
        entry.update(
            {
                "arguments": list(report_arguments),
                "first_filename_prefixes": first_prefixes,
                "second_filename_prefixes": second_prefixes,
                "linux_qt5_filename_prefixes": linux_prefixes,
                "linux_qt5_filename_prefixes_equal": (
                    first_prefixes == linux_prefixes
                ),
                "linux_qt5_raw_differences": helper.raw_differences(
                    first.summary(), linux_case["left"]
                ),
            }
        )
        if case.name.endswith("_json"):
            entry.update(
                {
                    "first_valid_json": (
                        definitions.document_is_valid(
                            first.stdout, "json"
                        )
                    ),
                    "second_valid_json": (
                        definitions.document_is_valid(
                            second.stdout, "json"
                        )
                    ),
                    "linux_qt5_valid_json": (
                        linux_case["left_valid_json"]
                    ),
                }
            )
        elif case.name.endswith("_xml"):
            entry.update(
                {
                    "first_valid_xml": (
                        definitions.document_is_valid(
                            first.stdout, "xml"
                        )
                    ),
                    "second_valid_xml": (
                        definitions.document_is_valid(
                            second.stdout, "xml"
                        )
                    ),
                    "linux_qt5_valid_xml": (
                        linux_case["left_valid_xml"]
                    ),
                }
            )
        path_reports[case.name] = entry
        if entry["determinism_differences"]:
            determinism_failures.append(f"path.{case.name}")
        if first.exit_code != linux_case["left"]["exit_code"]:
            exit_failures.append(f"path.{case.name}")
        if first_prefixes != linux_prefixes:
            path_prefix_failures.append(case.name)

    default_first, default_second = path_observations["tree_json"]
    recursive_first, recursive_second = path_observations[
        "tree_recursive_json"
    ]
    recursive_entry = path_reports["tree_recursive_json"]
    recursive_entry["first_changes_from_tree_json"] = (
        helper.observation_differences(
            default_first, recursive_first
        )
    )
    recursive_entry["second_changes_from_tree_json"] = (
        helper.observation_differences(
            default_second, recursive_second
        )
    )

    for sample in nested_samples:
        sample_name = str(sample["name"])
        sample_report: dict[str, object] = {}
        nested_reports[sample_name] = sample_report
        observations: dict[str, tuple[Any, Any]] = {}
        for case in definitions.NESTED_MATRIX:
            arguments = (*case.arguments, f"/nested/{sample_name}")
            actual_arguments = helper.translate_arguments(
                arguments,
                source_dir,
                path_corpus_dir,
                nested_corpus_dir,
                report=False,
            )
            report_arguments = helper.translate_arguments(
                arguments,
                source_dir,
                path_corpus_dir,
                nested_corpus_dir,
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
            observations[case.name] = (first, second)
            entry = baseline_collector.pair_report(
                common,
                output.parent,
                (
                    "cli-path-nested/nested/"
                    f"{sample_name}/{case.name}"
                ),
                first,
                second,
            )
            first_tree = common.json_detect_tree(first.stdout)
            second_tree = common.json_detect_tree(second.stdout)
            linux_case = linux_nested_cases[sample_name][case.name]
            linux_tree = linux_case["left_detect_tree"]
            entry.update(
                {
                    "arguments": list(report_arguments),
                    "first_detect_tree": first_tree,
                    "second_detect_tree": second_tree,
                    "linux_qt5_detect_tree": linux_tree,
                    "linux_qt5_detect_tree_equal": (
                        first_tree == linux_tree
                    ),
                    "linux_qt5_raw_differences": (
                        helper.raw_differences(
                            first.summary(), linux_case["left"]
                        )
                    ),
                }
            )
            sample_report[case.name] = entry
            identity = f"nested.{sample_name}.{case.name}"
            if entry["determinism_differences"]:
                determinism_failures.append(identity)
            if first.exit_code != linux_case["left"]["exit_code"]:
                exit_failures.append(identity)
            if first_tree != linux_tree:
                nested_projection_failures.append(identity)

        nested_default_first, nested_default_second = observations[
            "default"
        ]
        for case_name, (first, second) in observations.items():
            entry = sample_report[case_name]
            entry["first_changes_from_default"] = (
                helper.observation_differences(
                    nested_default_first, first
                )
            )
            entry["second_changes_from_default"] = (
                helper.observation_differences(
                    nested_default_second, second
                )
            )

    post_source = common.validate_source(source_dir)
    post_source["tracked_files_clean_before_and_after"] = True
    if post_source != source:
        raise PathNestedError("source identity changed during collection")
    if common.sha256_file(binary) != binary_sha256:
        raise PathNestedError("binary changed during collection")
    if (path_corpus_dir / "manifest.json").read_bytes() != path_manifest_raw:
        raise PathNestedError("path corpus changed during collection")
    if (
        nested_corpus_dir / "manifest.json"
    ).read_bytes() != nested_manifest_raw:
        raise PathNestedError("nested corpus changed during collection")

    path_case_count = len(definitions.PATH_CASES)
    nested_case_count = len(nested_samples) * len(
        definitions.NESTED_MATRIX
    )
    case_count = path_case_count + nested_case_count
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
        "fixtures": {
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
        },
        "linux_qt5_references": {
            "path": {
                "path": LINUX_PATH_REFERENCE,
                "sha256": sha256(path_reference_raw),
            },
            "nested": {
                "path": LINUX_NESTED_REFERENCE,
                "sha256": sha256(nested_reference_raw),
            },
        },
        "local_paths": {
            "path_corpus_dir": str(path_corpus_dir),
            "nested_corpus_dir": str(nested_corpus_dir),
        },
        "path": {"cases": path_reports},
        "nested": {"cases": nested_reports},
        "summary": {
            "path_case_count": path_case_count,
            "nested_sample_count": len(nested_samples),
            "nested_case_count": nested_case_count,
            "case_count": case_count,
            "execution_count": 2 * case_count,
            "raw_stream_count": 4 * case_count,
            "determinism_failures": determinism_failures,
            "linux_exit_code_failures": exit_failures,
            "path_prefix_failures": path_prefix_failures,
            "nested_projection_failures": (
                nested_projection_failures
            ),
            "deterministic": not determinism_failures,
            "linux_exit_codes_equal": not exit_failures,
            "path_prefixes_equal": not path_prefix_failures,
            "nested_projections_equal": (
                not nested_projection_failures
            ),
        },
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
    parser.add_argument("--path-corpus-dir", type=Path, required=True)
    parser.add_argument("--nested-corpus-dir", type=Path, required=True)
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
            path_corpus_dir=args.path_corpus_dir,
            nested_corpus_dir=args.nested_corpus_dir,
            oracle_path=args.oracle_report,
            output=args.output,
            timeout_seconds=args.timeout_seconds,
        )
    except (PathNestedError, OSError, ValueError) as error:
        print(
            f"macOS CLI path/nested error: {error}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
