#!/usr/bin/env python3
"""Collect deterministic native-Windows Qt5 CLI option matrices."""

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
OUTPUT_SAMPLES = (
    "empty.bin",
    "minimal.exe",
    "minimal.pdf",
    "payload.zip",
    "plain.txt",
)
SPECIAL_SAMPLES = OUTPUT_SAMPLES


def load_module(name: str, path: Path) -> object:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load helper module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


baseline = load_module("collect_windows_cli_baseline_helper", BASELINE_SCRIPT)
matrix_definitions = load_module(
    "compare_cli_oracles_matrix_definitions",
    MATRIX_SCRIPT,
)
MatrixError = baseline.BaselineError


def read_json(path: Path) -> tuple[dict[str, object], bytes]:
    raw = path.read_bytes()
    document = json.loads(raw)
    if not isinstance(document, dict):
        raise MatrixError(f"JSON report is not an object: {path}")
    return document, raw


def observation_differences(first: object, second: object) -> list[str]:
    differences = []
    if first.exit_code != second.exit_code:
        differences.append("exit_code")
    if first.stdout != second.stdout:
        differences.append("stdout")
    if first.stderr != second.stderr:
        differences.append("stderr")
    return differences


def validate_reference_matrix(
    report: dict[str, object],
    *,
    kind: str,
    samples: Sequence[str],
    cases: Sequence[object],
) -> None:
    matrix = report.get("matrix")
    if not isinstance(matrix, dict):
        raise MatrixError(f"Linux {kind} reference has no matrix")
    if set(matrix) != set(samples):
        raise MatrixError(f"Linux {kind} reference sample set differs")
    expected_cases = {case.name for case in cases}
    for sample in samples:
        sample_report = matrix.get(sample)
        if not isinstance(sample_report, dict):
            raise MatrixError(
                f"Linux {kind} reference sample is invalid: {sample}"
            )
        case_report = sample_report.get(kind)
        if not isinstance(case_report, dict):
            raise MatrixError(
                f"Linux {kind} reference has no cases for {sample}"
            )
        if set(case_report) != expected_cases:
            raise MatrixError(
                f"Linux {kind} reference case set differs for {sample}"
            )


def translate_arguments(
    arguments: Sequence[str],
    source_dir: Path,
    *,
    report: bool,
) -> tuple[str, ...]:
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
    translated = tuple(replacements.get(argument, argument) for argument in arguments)
    unresolved = [
        argument for argument in translated if argument.startswith("/opt/die-source")
    ]
    if unresolved:
        raise MatrixError(f"untranslated matrix path: {unresolved}")
    return translated


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--qt-dir", type=Path, required=True)
    parser.add_argument("--corpus-dir", type=Path, required=True)
    parser.add_argument("--expected-binary-sha256", required=True)
    parser.add_argument(
        "--reference-manifest",
        type=Path,
        default=ROOT / "docs/research/data/baseline-corpus.json",
    )
    parser.add_argument(
        "--windows-reference",
        type=Path,
        default=ROOT
        / "docs/research/data/baseline-corpus-windows-qt5.json",
    )
    parser.add_argument(
        "--linux-output-reference",
        type=Path,
        default=ROOT
        / "docs/research/data/cli-output-matrix-linux-qt5-qt6.json",
    )
    parser.add_argument(
        "--linux-scan-reference",
        type=Path,
        default=ROOT
        / "docs/research/data/cli-scan-nested-matrix-linux-qt5-qt6.json",
    )
    parser.add_argument(
        "--linux-special-reference",
        type=Path,
        default=ROOT
        / "docs/research/data/cli-special-matrix-linux-qt5-qt6.json",
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
    corpus_dir = args.corpus_dir.resolve(strict=True)
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
    samples, manifest_sha256 = baseline.load_corpus(
        corpus_dir,
        args.reference_manifest.resolve(strict=True),
    )
    sample_names = [str(sample["name"]) for sample in samples]
    missing_selections = sorted(
        (set(OUTPUT_SAMPLES) | set(SPECIAL_SAMPLES)) - set(sample_names)
    )
    if missing_selections:
        raise MatrixError(
            "matrix selections are absent from corpus: "
            + ", ".join(missing_selections)
        )

    windows_path = args.windows_reference.resolve(strict=True)
    windows_reference, windows_raw = read_json(windows_path)
    windows_corpus = windows_reference.get("corpus")
    if not isinstance(windows_corpus, dict):
        raise MatrixError("Windows default reference has no corpus")
    if set(windows_corpus) != set(sample_names):
        raise MatrixError("Windows default reference corpus set differs")
    if windows_reference.get("source") != source_identity:
        raise MatrixError("Windows default reference source identity differs")
    if windows_reference.get("qt") != qt_identity:
        raise MatrixError("Windows default reference Qt identity differs")
    windows_binary = windows_reference.get("binary")
    if (
        not isinstance(windows_binary, dict)
        or windows_binary.get("sha256") != binary_sha256
    ):
        raise MatrixError("Windows default reference binary identity differs")

    linux_paths = {
        "output": args.linux_output_reference.resolve(strict=True),
        "scan": args.linux_scan_reference.resolve(strict=True),
        "special": args.linux_special_reference.resolve(strict=True),
    }
    linux_reports: dict[str, dict[str, object]] = {}
    linux_raw: dict[str, bytes] = {}
    matrix_cases = {
        "output": matrix_definitions.OUTPUT_MATRIX,
        "scan": matrix_definitions.SCAN_MATRIX,
        "special": matrix_definitions.SPECIAL_MATRIX,
    }
    for kind, path in linux_paths.items():
        linux_reports[kind], linux_raw[kind] = read_json(path)
        validate_reference_matrix(
            linux_reports[kind],
            kind=kind,
            samples=OUTPUT_SAMPLES,
            cases=matrix_cases[kind],
        )

    selected_samples = {
        "output": OUTPUT_SAMPLES,
        "scan": tuple(sample_names),
        "special": SPECIAL_SAMPLES,
    }
    report_matrix: dict[str, dict[str, object]] = {}
    determinism_failures: list[str] = []
    default_reference_failures: list[str] = []
    linux_exit_code_failures: list[str] = []

    for kind in ("output", "scan", "special"):
        for name in selected_samples[kind]:
            sample_report = report_matrix.setdefault(name, {})
            kind_report: dict[str, object] = {}
            sample_report[kind] = kind_report
            observations: dict[str, tuple[object, object]] = {}
            for case in matrix_cases[kind]:
                actual_arguments = (
                    *translate_arguments(
                        case.arguments,
                        source_dir,
                        report=False,
                    ),
                    str(corpus_dir / name),
                )
                report_arguments = [
                    *translate_arguments(
                        case.arguments,
                        source_dir,
                        report=True,
                    ),
                    f"<corpus>/{name}",
                ]
                first, second, paired = collect_pair(
                    binary,
                    qt_dir,
                    actual_arguments,
                    timeout_seconds=args.timeout_seconds,
                )
                observations[case.name] = (first, second)
                paired["arguments"] = report_arguments
                if kind == "scan":
                    paired["first_detect_tree"] = baseline.json_detect_tree(
                        first.stdout
                    )
                    paired["second_detect_tree"] = baseline.json_detect_tree(
                        second.stdout
                    )
                if name in OUTPUT_SAMPLES:
                    linux_entry = linux_reports[kind]["matrix"][name][kind][
                        case.name
                    ]
                    linux_exit_code = linux_entry["left"]["exit_code"]
                    paired["linux_qt5_exit_code"] = linux_exit_code
                    paired["linux_qt5_exit_code_equal"] = (
                        first.exit_code == linux_exit_code
                    )
                    if first.exit_code != linux_exit_code:
                        linux_exit_code_failures.append(
                            f"matrix.{name}.{kind}.{case.name}"
                        )
                kind_report[case.name] = paired
                if paired["determinism_differences"]:
                    determinism_failures.append(
                        f"matrix.{name}.{kind}.{case.name}"
                    )

            if kind == "scan":
                default_first, default_second = observations["default"]
                default_entry = kind_report["default"]
                windows_entry = windows_corpus[name]
                reference_equal = (
                    default_first.summary() == windows_entry["first"]
                    and default_second.summary() == windows_entry["second"]
                    and default_entry["first_detect_tree"]
                    == windows_entry["first_detect_tree"]
                    and default_entry["second_detect_tree"]
                    == windows_entry["second_detect_tree"]
                )
                default_entry["windows_default_reference_equal"] = (
                    reference_equal
                )
                if not reference_equal:
                    default_reference_failures.append(name)
                for case_name, (first, second) in observations.items():
                    entry = kind_report[case_name]
                    entry["first_changes_from_default"] = (
                        observation_differences(default_first, first)
                    )
                    entry["second_changes_from_default"] = (
                        observation_differences(default_second, second)
                    )

    case_counts = {
        kind: len(selected_samples[kind]) * len(matrix_cases[kind])
        for kind in selected_samples
    }
    report = {
        "schema_version": 1,
        "generator": "tools/upstream/collect_windows_cli_matrix.py",
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
        "corpus_manifest": {
            "path": "docs/research/data/baseline-corpus.json",
            "sha256": manifest_sha256,
            "sample_count": len(samples),
        },
        "windows_default_reference": {
            "path": (
                "docs/research/data/baseline-corpus-windows-qt5.json"
            ),
            "sha256": hashlib.sha256(windows_raw).hexdigest(),
        },
        "linux_qt5_references": {
            kind: {
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "sha256": hashlib.sha256(linux_raw[kind]).hexdigest(),
            }
            for kind, path in linux_paths.items()
        },
        "selection": {
            kind: list(names) for kind, names in selected_samples.items()
        },
        "matrix": report_matrix,
        "summary": {
            "sample_count": len(report_matrix),
            "case_counts": case_counts,
            "case_count": sum(case_counts.values()),
            "execution_count": 2 * sum(case_counts.values()),
            "determinism_failures": determinism_failures,
            "default_reference_failures": default_reference_failures,
            "linux_exit_code_failures": linux_exit_code_failures,
            "deterministic": not determinism_failures,
            "default_reference_equal": not default_reference_failures,
            "linux_exit_codes_equal": not linux_exit_code_failures,
        },
        "limitations": [
            (
                "scan options cover all baseline corpus samples; output and "
                "special modes cover the same five representative samples as "
                "the committed Linux Qt5/Qt6 matrices"
            ),
            (
                "Linux references retain hashes and exit-code comparisons, but "
                "their reports do not retain raw stdout or semantic projections "
                "for every matrix case"
            ),
            (
                "nested/path/database-error and engine-only matrices require "
                "separate native Windows evidence"
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
    return (
        0
        if not (
            determinism_failures
            or default_reference_failures
            or linux_exit_code_failures
        )
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
