#!/usr/bin/env python3
"""Collect deterministic native-Windows Qt5 CLI path and nested matrices."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from typing import Sequence


ROOT = Path(__file__).resolve().parents[2]
BASELINE_SCRIPT = ROOT / "tools/upstream/collect_windows_cli_baseline.py"
MATRIX_SCRIPT = ROOT / "tools/upstream/compare_cli_oracles.py"


def load_module(name: str, path: Path) -> object:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load helper module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


baseline = load_module(
    "collect_windows_cli_baseline_path_nested_helper",
    BASELINE_SCRIPT,
)
matrix_definitions = load_module(
    "compare_cli_oracles_path_nested_definitions",
    MATRIX_SCRIPT,
)
MatrixError = baseline.BaselineError


def read_json(path: Path) -> tuple[dict[str, object], bytes]:
    raw = path.read_bytes()
    document = json.loads(raw)
    if not isinstance(document, dict):
        raise MatrixError(f"JSON report is not an object: {path}")
    return document, raw


def raw_differences(
    windows_summary: dict[str, object],
    linux_summary: dict[str, object],
) -> list[str]:
    differences = []
    if windows_summary["exit_code"] != linux_summary["exit_code"]:
        differences.append("exit_code")
    if windows_summary["stdout_sha256"] != linux_summary["stdout_sha256"]:
        differences.append("stdout")
    if windows_summary["stderr_sha256"] != linux_summary["stderr_sha256"]:
        differences.append("stderr")
    return differences


def observation_differences(first: object, second: object) -> list[str]:
    differences = []
    if first.exit_code != second.exit_code:
        differences.append("exit_code")
    if first.stdout != second.stdout:
        differences.append("stdout")
    if first.stderr != second.stderr:
        differences.append("stderr")
    return differences


def translate_argument(
    argument: str,
    source_dir: Path,
    path_corpus_dir: Path,
    nested_corpus_dir: Path,
    *,
    report: bool,
) -> str:
    replacements = {
        "/opt/die-source/Detect-It-Easy/db": (
            "<source>/Detect-It-Easy/db"
            if report
            else str(source_dir / "Detect-It-Easy" / "db")
        ),
        "/opt/die-source/Detect-It-Easy/db_extra": (
            "<source>/Detect-It-Easy/db_extra"
            if report
            else str(source_dir / "Detect-It-Easy" / "db_extra")
        ),
        "/opt/die-source/Detect-It-Easy/db_custom": (
            "<source>/Detect-It-Easy/db_custom"
            if report
            else str(source_dir / "Detect-It-Easy" / "db_custom")
        ),
    }
    if argument in replacements:
        return replacements[argument]
    roots = (
        ("/paths", "<paths>", path_corpus_dir),
        ("/nested", "<nested>", nested_corpus_dir),
    )
    for prefix, placeholder, actual_root in roots:
        if argument == prefix or argument.startswith(prefix + "/"):
            suffix = argument[len(prefix) :].lstrip("/")
            if report:
                return placeholder + (f"/{suffix}" if suffix else "")
            return str(actual_root.joinpath(*suffix.split("/")))
    if argument.startswith(("/opt/die-source", "/paths", "/nested")):
        raise MatrixError(f"untranslated matrix path: {argument}")
    return argument


def translate_arguments(
    arguments: Sequence[str],
    source_dir: Path,
    path_corpus_dir: Path,
    nested_corpus_dir: Path,
    *,
    report: bool,
) -> tuple[str, ...]:
    return tuple(
        translate_argument(
            argument,
            source_dir,
            path_corpus_dir,
            nested_corpus_dir,
            report=report,
        )
        for argument in arguments
    )


def relative_filename_prefixes(data: bytes, path_root: Path) -> list[str]:
    normalized_root = str(path_root).replace("\\", "/").rstrip("/")
    folded_root = normalized_root.casefold()
    result = []
    for line in data.decode("utf-8", errors="replace").splitlines():
        if not line.endswith(":"):
            continue
        candidate = line[:-1].replace("\\", "/")
        folded = candidate.casefold()
        if not folded.startswith(folded_root + "/"):
            continue
        relative = candidate[len(normalized_root) + 1 :]
        result.append(f"<paths>/{relative}")
    return result


def normalized_linux_prefixes(prefixes: object) -> list[str]:
    if not isinstance(prefixes, list) or not all(
        isinstance(prefix, str) and prefix.startswith("/paths/")
        for prefix in prefixes
    ):
        raise MatrixError("Linux path reference has invalid filename prefixes")
    return ["<paths>/" + prefix[len("/paths/") :] for prefix in prefixes]


def collect_pair(
    binary: Path,
    qt_dir: Path,
    arguments: Sequence[str],
    *,
    timeout_seconds: int,
) -> tuple[object, object, dict[str, object]]:
    first = baseline.observe(
        binary,
        qt_dir,
        arguments,
        timeout_seconds=timeout_seconds,
    )
    second = baseline.observe(
        binary,
        qt_dir,
        arguments,
        timeout_seconds=timeout_seconds,
    )
    return first, second, baseline.pair_report(first, second)


def validate_reference_cases(
    path_reference: dict[str, object],
    nested_reference: dict[str, object],
    nested_samples: Sequence[dict[str, object]],
) -> None:
    path_report = path_reference.get("path_corpus")
    if not isinstance(path_report, dict):
        raise MatrixError("Linux path reference has no path_corpus")
    path_cases = path_report.get("cases")
    expected_path_cases = {case.name for case in matrix_definitions.PATH_CASES}
    if not isinstance(path_cases, dict) or set(path_cases) != expected_path_cases:
        raise MatrixError("Linux path reference case set differs")

    nested_report = nested_reference.get("nested_corpus")
    if not isinstance(nested_report, dict):
        raise MatrixError("Linux nested reference has no nested_corpus")
    nested_cases = nested_report.get("cases")
    sample_names = {str(sample["name"]) for sample in nested_samples}
    if not isinstance(nested_cases, dict) or set(nested_cases) != sample_names:
        raise MatrixError("Linux nested reference sample set differs")
    expected_nested_cases = {
        case.name for case in matrix_definitions.NESTED_MATRIX
    }
    for name in sample_names:
        if (
            not isinstance(nested_cases[name], dict)
            or set(nested_cases[name]) != expected_nested_cases
        ):
            raise MatrixError(
                f"Linux nested reference case set differs for {name}"
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--qt-dir", type=Path, required=True)
    parser.add_argument("--path-corpus-dir", type=Path, required=True)
    parser.add_argument("--nested-corpus-dir", type=Path, required=True)
    parser.add_argument("--expected-binary-sha256", required=True)
    parser.add_argument(
        "--path-manifest",
        type=Path,
        default=ROOT / "docs/research/data/path-corpus.json",
    )
    parser.add_argument(
        "--nested-manifest",
        type=Path,
        default=ROOT / "docs/research/data/nested-corpus.json",
    )
    parser.add_argument(
        "--linux-path-reference",
        type=Path,
        default=ROOT
        / "docs/research/data/cli-path-matrix-linux-qt5-qt6.json",
    )
    parser.add_argument(
        "--linux-nested-reference",
        type=Path,
        default=ROOT
        / "docs/research/data/cli-scan-nested-matrix-linux-qt5-qt6.json",
    )
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if os.name != "nt":
        raise MatrixError("native Windows matrix requires os.name == 'nt'")
    if args.timeout_seconds < 1 or args.timeout_seconds > 3600:
        raise MatrixError("timeout-seconds must be in 1..3600")
    if (
        len(args.expected_binary_sha256) != 64
        or any(
            character not in "0123456789abcdef"
            for character in args.expected_binary_sha256
        )
    ):
        raise MatrixError("expected binary SHA-256 must be lowercase hex")

    source_dir = args.source_dir.resolve(strict=True)
    qt_dir = args.qt_dir.resolve(strict=True)
    path_corpus_dir = args.path_corpus_dir.resolve(strict=True)
    nested_corpus_dir = args.nested_corpus_dir.resolve(strict=True)
    binary = args.binary.resolve(strict=True)
    expected_binary = (
        source_dir / "build" / "release" / "diec.exe"
    ).resolve(strict=True)
    if binary != expected_binary:
        raise MatrixError("binary must be <source>/build/release/diec.exe")
    binary_sha256 = baseline.sha256_file(binary)
    if binary_sha256 != args.expected_binary_sha256:
        raise MatrixError(
            "binary SHA-256 mismatch: "
            f"expected {args.expected_binary_sha256}, got {binary_sha256}"
        )

    source_identity = baseline.validate_source(source_dir)
    qt_identity = baseline.validate_qt(qt_dir)
    path_manifest_path = args.path_manifest.resolve(strict=True)
    nested_manifest_path = args.nested_manifest.resolve(strict=True)
    path_manifest_raw = (path_corpus_dir / "manifest.json").read_bytes()
    nested_manifest_raw = (nested_corpus_dir / "manifest.json").read_bytes()
    if path_manifest_raw != path_manifest_path.read_bytes():
        raise MatrixError("path corpus manifest differs from reference")
    if nested_manifest_raw != nested_manifest_path.read_bytes():
        raise MatrixError("nested corpus manifest differs from reference")
    path_manifest = matrix_definitions.load_path_corpus(path_corpus_dir)
    nested_samples = matrix_definitions.load_nested_corpus(
        nested_corpus_dir
    )

    path_reference_path = args.linux_path_reference.resolve(strict=True)
    nested_reference_path = args.linux_nested_reference.resolve(strict=True)
    path_reference, path_reference_raw = read_json(path_reference_path)
    nested_reference, nested_reference_raw = read_json(
        nested_reference_path
    )
    validate_reference_cases(
        path_reference,
        nested_reference,
        nested_samples,
    )
    linux_path_cases = path_reference["path_corpus"]["cases"]
    linux_nested_cases = nested_reference["nested_corpus"]["cases"]

    report_path_cases: dict[str, object] = {}
    report_nested_cases: dict[str, object] = {}
    determinism_failures: list[str] = []
    linux_exit_code_failures: list[str] = []
    path_prefix_failures: list[str] = []
    nested_projection_failures: list[str] = []

    path_observations: dict[str, tuple[object, object]] = {}
    for case in matrix_definitions.PATH_CASES:
        actual_arguments = translate_arguments(
            case.arguments,
            source_dir,
            path_corpus_dir,
            nested_corpus_dir,
            report=False,
        )
        report_arguments = translate_arguments(
            case.arguments,
            source_dir,
            path_corpus_dir,
            nested_corpus_dir,
            report=True,
        )
        first, second, paired = collect_pair(
            binary,
            qt_dir,
            actual_arguments,
            timeout_seconds=args.timeout_seconds,
        )
        path_observations[case.name] = (first, second)
        windows_prefixes = relative_filename_prefixes(
            first.stdout,
            path_corpus_dir,
        )
        second_prefixes = relative_filename_prefixes(
            second.stdout,
            path_corpus_dir,
        )
        linux_case = linux_path_cases[case.name]
        linux_prefixes = normalized_linux_prefixes(
            linux_case["left_filename_prefixes"]
        )
        paired.update(
            {
                "arguments": list(report_arguments),
                "first_filename_prefixes": windows_prefixes,
                "second_filename_prefixes": second_prefixes,
                "linux_qt5_filename_prefixes": linux_prefixes,
                "linux_qt5_filename_prefixes_equal": (
                    windows_prefixes == linux_prefixes
                ),
                "linux_qt5_raw_differences": raw_differences(
                    first.summary(),
                    linux_case["left"],
                ),
            }
        )
        if case.name.endswith("_json"):
            paired["first_valid_json"] = (
                matrix_definitions.document_is_valid(first.stdout, "json")
            )
            paired["second_valid_json"] = (
                matrix_definitions.document_is_valid(second.stdout, "json")
            )
            paired["linux_qt5_valid_json"] = linux_case["left_valid_json"]
        elif case.name.endswith("_xml"):
            paired["first_valid_xml"] = (
                matrix_definitions.document_is_valid(first.stdout, "xml")
            )
            paired["second_valid_xml"] = (
                matrix_definitions.document_is_valid(second.stdout, "xml")
            )
            paired["linux_qt5_valid_xml"] = linux_case["left_valid_xml"]
        report_path_cases[case.name] = paired
        if paired["determinism_differences"]:
            determinism_failures.append(f"path.{case.name}")
        if first.exit_code != linux_case["left"]["exit_code"]:
            linux_exit_code_failures.append(f"path.{case.name}")
        if windows_prefixes != linux_prefixes:
            path_prefix_failures.append(case.name)

    default_first, default_second = path_observations["tree_json"]
    recursive_first, recursive_second = path_observations[
        "tree_recursive_json"
    ]
    recursive_entry = report_path_cases["tree_recursive_json"]
    recursive_entry["first_changes_from_tree_json"] = (
        observation_differences(default_first, recursive_first)
    )
    recursive_entry["second_changes_from_tree_json"] = (
        observation_differences(default_second, recursive_second)
    )

    for sample in nested_samples:
        name = str(sample["name"])
        sample_report: dict[str, object] = {}
        report_nested_cases[name] = sample_report
        observations: dict[str, tuple[object, object]] = {}
        for case in matrix_definitions.NESTED_MATRIX:
            arguments = (*case.arguments, f"/nested/{name}")
            actual_arguments = translate_arguments(
                arguments,
                source_dir,
                path_corpus_dir,
                nested_corpus_dir,
                report=False,
            )
            report_arguments = translate_arguments(
                arguments,
                source_dir,
                path_corpus_dir,
                nested_corpus_dir,
                report=True,
            )
            first, second, paired = collect_pair(
                binary,
                qt_dir,
                actual_arguments,
                timeout_seconds=args.timeout_seconds,
            )
            observations[case.name] = (first, second)
            first_tree = baseline.json_detect_tree(first.stdout)
            second_tree = baseline.json_detect_tree(second.stdout)
            linux_case = linux_nested_cases[name][case.name]
            linux_tree = linux_case["left_detect_tree"]
            paired.update(
                {
                    "arguments": list(report_arguments),
                    "first_detect_tree": first_tree,
                    "second_detect_tree": second_tree,
                    "linux_qt5_detect_tree": linux_tree,
                    "linux_qt5_detect_tree_equal": first_tree == linux_tree,
                    "linux_qt5_raw_differences": raw_differences(
                        first.summary(),
                        linux_case["left"],
                    ),
                }
            )
            sample_report[case.name] = paired
            identity = f"nested.{name}.{case.name}"
            if paired["determinism_differences"]:
                determinism_failures.append(identity)
            if first.exit_code != linux_case["left"]["exit_code"]:
                linux_exit_code_failures.append(identity)
            if first_tree != linux_tree:
                nested_projection_failures.append(identity)

        nested_default_first, nested_default_second = observations["default"]
        for case_name, (first, second) in observations.items():
            entry = sample_report[case_name]
            entry["first_changes_from_default"] = observation_differences(
                nested_default_first,
                first,
            )
            entry["second_changes_from_default"] = observation_differences(
                nested_default_second,
                second,
            )

    path_case_count = len(matrix_definitions.PATH_CASES)
    nested_case_count = len(nested_samples) * len(
        matrix_definitions.NESTED_MATRIX
    )
    report = {
        "schema_version": 1,
        "generator": (
            "tools/upstream/collect_windows_cli_path_nested.py"
        ),
        "generator_sha256": baseline.sha256_file(Path(__file__)),
        "matrix_definitions": {
            "path": "tools/upstream/compare_cli_oracles.py",
            "sha256": baseline.sha256_file(MATRIX_SCRIPT),
        },
        "platform": "windows-x86_64-qt5",
        "source": source_identity,
        "qt": qt_identity,
        "binary": {
            "size": binary.stat().st_size,
            "sha256": binary_sha256,
            "relative_path": "build/release/diec.exe",
        },
        "fixtures": {
            "path": {
                "manifest": "docs/research/data/path-corpus.json",
                "sha256": hashlib.sha256(path_manifest_raw).hexdigest(),
                "directories": path_manifest["directories"],
                "entries": path_manifest["entries"],
            },
            "nested": {
                "manifest": "docs/research/data/nested-corpus.json",
                "sha256": hashlib.sha256(nested_manifest_raw).hexdigest(),
                "samples": nested_samples,
            },
        },
        "linux_qt5_references": {
            "path": {
                "path": (
                    "docs/research/data/"
                    "cli-path-matrix-linux-qt5-qt6.json"
                ),
                "sha256": hashlib.sha256(path_reference_raw).hexdigest(),
            },
            "nested": {
                "path": (
                    "docs/research/data/"
                    "cli-scan-nested-matrix-linux-qt5-qt6.json"
                ),
                "sha256": hashlib.sha256(nested_reference_raw).hexdigest(),
            },
        },
        "path": {"cases": report_path_cases},
        "nested": {"cases": report_nested_cases},
        "summary": {
            "path_case_count": path_case_count,
            "nested_sample_count": len(nested_samples),
            "nested_case_count": nested_case_count,
            "case_count": path_case_count + nested_case_count,
            "execution_count": 2 * (path_case_count + nested_case_count),
            "determinism_failures": determinism_failures,
            "linux_exit_code_failures": linux_exit_code_failures,
            "path_prefix_failures": path_prefix_failures,
            "nested_projection_failures": nested_projection_failures,
            "deterministic": not determinism_failures,
            "linux_exit_codes_equal": not linux_exit_code_failures,
            "path_prefixes_equal": not path_prefix_failures,
            "nested_projections_equal": not nested_projection_failures,
        },
        "limitations": [
            (
                "path evidence covers the committed five-file directory tree, "
                "multi-target framing, duplicates, missing paths, and formatter "
                "validity; special Unicode, reparse points, permissions, large "
                "directories, and filesystem ordering need separate evidence"
            ),
            (
                "nested evidence covers the eight committed safe fixtures and "
                "four published recursive/aggressive combinations; engine-only "
                "archive/resource controls need a native Windows harness"
            ),
            (
                "raw streams remain platform observations; only named exit, "
                "relative path-prefix order, and detection-tree projections are "
                "compared across platforms"
            ),
        ],
    }
    serialized = (
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(serialized)
    print(serialized.decode("utf-8"), end="")
    return 0 if not determinism_failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
