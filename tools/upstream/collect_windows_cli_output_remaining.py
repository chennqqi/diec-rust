#!/usr/bin/env python3
"""Collect Windows Qt5 output modes for non-representative samples."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
BASELINE_SCRIPT = ROOT / "tools/upstream/collect_windows_cli_baseline.py"
MATRIX_SCRIPT = ROOT / "tools/upstream/compare_cli_oracles.py"
PRIMARY_MATRIX_SCRIPT = (
    ROOT / "tools/upstream/collect_windows_cli_matrix.py"
)
ALREADY_COVERED = (
    "empty.bin",
    "minimal.exe",
    "minimal.pdf",
    "payload.zip",
    "plain.txt",
)
EXPECTED_INVALID_XML = (
    "minimal-fat.macho",
    "Minimal.class",
    "minimal.pyc",
    "minimal.iso",
)


def load_module(name: str, path: Path) -> object:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load helper module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


baseline = load_module(
    "collect_windows_cli_baseline_output_remaining_helper",
    BASELINE_SCRIPT,
)
matrix_definitions = load_module(
    "compare_cli_oracles_output_remaining_definitions",
    MATRIX_SCRIPT,
)
primary_matrix = load_module(
    "collect_windows_cli_output_remaining_primary_helper",
    PRIMARY_MATRIX_SCRIPT,
)
ProbeError = baseline.BaselineError


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
        "--primary-windows-matrix",
        type=Path,
        default=ROOT
        / "docs/research/data/windows-qt5-cli-matrix.json",
    )
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def output_validity(case_name: str, data: bytes) -> bool:
    if case_name == "json":
        return matrix_definitions.document_is_valid(data, "json")
    if case_name == "xml":
        return matrix_definitions.document_is_valid(data, "xml")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return bool(text)


def main() -> int:
    args = parse_args()
    if os.name != "nt":
        raise ProbeError("native Windows probe requires os.name == 'nt'")
    if args.timeout_seconds < 1 or args.timeout_seconds > 3600:
        raise ProbeError("timeout-seconds must be in 1..3600")

    source_dir = args.source_dir.resolve(strict=True)
    qt_dir = args.qt_dir.resolve(strict=True)
    corpus_dir = args.corpus_dir.resolve(strict=True)
    binary = args.binary.resolve(strict=True)
    expected_binary = (
        source_dir / "build" / "release" / "diec.exe"
    ).resolve(strict=True)
    if binary != expected_binary:
        raise ProbeError("binary must be <source>/build/release/diec.exe")
    binary_sha256 = baseline.sha256_file(binary)
    if binary_sha256 != args.expected_binary_sha256:
        raise ProbeError("binary SHA-256 mismatch")

    source_identity = baseline.validate_source(source_dir)
    qt_identity = baseline.validate_qt(qt_dir)
    samples, manifest_sha256 = baseline.load_corpus(
        corpus_dir,
        args.reference_manifest.resolve(strict=True),
    )
    sample_names = [str(sample["name"]) for sample in samples]
    if not set(ALREADY_COVERED).issubset(sample_names):
        raise ProbeError("primary output selection is absent from corpus")
    selected_samples = [
        name for name in sample_names if name not in ALREADY_COVERED
    ]
    if len(sample_names) != 26 or len(selected_samples) != 21:
        raise ProbeError("Windows output sample partition changed")

    windows_path = args.windows_reference.resolve(strict=True)
    windows_raw = windows_path.read_bytes()
    windows_reference = json.loads(windows_raw)
    windows_corpus = windows_reference.get("corpus")
    if not isinstance(windows_corpus, dict):
        raise ProbeError("Windows default reference has no corpus")
    if set(windows_corpus) != set(sample_names):
        raise ProbeError("Windows default reference corpus set differs")
    if windows_reference.get("source") != source_identity:
        raise ProbeError("Windows default source identity differs")
    if windows_reference.get("qt") != qt_identity:
        raise ProbeError("Windows default Qt identity differs")
    if windows_reference["binary"]["sha256"] != binary_sha256:
        raise ProbeError("Windows default binary identity differs")

    primary_path = args.primary_windows_matrix.resolve(strict=True)
    primary_raw = primary_path.read_bytes()
    primary_report = json.loads(primary_raw)
    if primary_report["selection"]["output"] != list(ALREADY_COVERED):
        raise ProbeError("primary Windows output selection changed")
    if primary_report["binary"]["sha256"] != binary_sha256:
        raise ProbeError("primary Windows matrix binary differs")

    cases = matrix_definitions.OUTPUT_MATRIX
    reports = {}
    determinism_failures = []
    expected_exit_failures = []
    stderr_failures = []
    validity_expectation_failures = []
    json_reference_failures = []
    csv_priority_failures = []
    for sample_name in selected_samples:
        sample_cases = {}
        reports[sample_name] = sample_cases
        observations = {}
        for case in cases:
            actual_arguments = (
                *primary_matrix.translate_arguments(
                    case.arguments,
                    source_dir,
                    report=False,
                ),
                str(corpus_dir / sample_name),
            )
            report_arguments = [
                *primary_matrix.translate_arguments(
                    case.arguments,
                    source_dir,
                    report=True,
                ),
                f"<corpus>/{sample_name}",
            ]
            first, second, paired = primary_matrix.collect_pair(
                binary,
                qt_dir,
                actual_arguments,
                timeout_seconds=args.timeout_seconds,
            )
            observations[case.name] = (first, second)
            valid_first = output_validity(case.name, first.stdout)
            valid_second = output_validity(case.name, second.stdout)
            expected_valid = not (
                case.name == "xml"
                and sample_name in EXPECTED_INVALID_XML
            )
            paired.update(
                {
                    "arguments": report_arguments,
                    "expected_exit_code": 0,
                    "expected_exit_code_equal": first.exit_code == 0,
                    "expected_empty_stderr": True,
                    "first_stderr_empty": first.stderr == b"",
                    "second_stderr_empty": second.stderr == b"",
                    "first_output_valid": valid_first,
                    "second_output_valid": valid_second,
                    "expected_output_valid": expected_valid,
                    "output_validity_expected_equal": (
                        valid_first == expected_valid
                        and valid_second == expected_valid
                    ),
                }
            )
            if case.name == "json":
                first_tree = baseline.json_detect_tree(first.stdout)
                second_tree = baseline.json_detect_tree(second.stdout)
                reference = windows_corpus[sample_name]
                reference_equal = (
                    first.summary() == reference["first"]
                    and second.summary() == reference["second"]
                    and first_tree == reference["first_detect_tree"]
                    and second_tree == reference["second_detect_tree"]
                )
                paired.update(
                    {
                        "first_detect_tree": first_tree,
                        "second_detect_tree": second_tree,
                        "windows_default_reference_equal": (
                            reference_equal
                        ),
                    }
                )
                if not reference_equal:
                    json_reference_failures.append(sample_name)
            sample_cases[case.name] = paired
            prefix = f"matrix.{sample_name}.{case.name}"
            if paired["determinism_differences"]:
                determinism_failures.append(prefix)
            if first.exit_code != 0:
                expected_exit_failures.append(prefix)
            if first.stderr != b"" or second.stderr != b"":
                stderr_failures.append(prefix)
            if (
                valid_first != expected_valid
                or valid_second != expected_valid
            ):
                validity_expectation_failures.append(prefix)

        csv_first, csv_second = observations["csv"]
        all_first, all_second = observations["all_output_flags"]
        priority_equal = (
            csv_first == all_first and csv_second == all_second
        )
        sample_cases["all_output_flags"][
            "csv_priority_reference_equal"
        ] = priority_equal
        if not priority_equal:
            csv_priority_failures.append(sample_name)

    case_count = len(selected_samples) * len(cases)
    report = {
        "schema_version": 1,
        "generator": (
            "tools/upstream/"
            "collect_windows_cli_output_remaining.py"
        ),
        "generator_sha256": baseline.sha256_file(Path(__file__)),
        "helpers": {
            "matrix_definitions": {
                "path": "tools/upstream/compare_cli_oracles.py",
                "sha256": baseline.sha256_file(MATRIX_SCRIPT),
            },
            "primary_collector": {
                "path": (
                    "tools/upstream/collect_windows_cli_matrix.py"
                ),
                "sha256": baseline.sha256_file(
                    PRIMARY_MATRIX_SCRIPT
                ),
            },
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
        "primary_windows_matrix": {
            "path": (
                "docs/research/data/windows-qt5-cli-matrix.json"
            ),
            "sha256": hashlib.sha256(primary_raw).hexdigest(),
            "covered_samples": list(ALREADY_COVERED),
        },
        "selection": selected_samples,
        "cases": [case.name for case in cases],
        "matrix": reports,
        "summary": {
            "sample_count": len(selected_samples),
            "case_count": case_count,
            "execution_count": 2 * case_count,
            "determinism_failures": determinism_failures,
            "expected_exit_failures": expected_exit_failures,
            "stderr_failures": stderr_failures,
            "validity_expectation_failures": (
                validity_expectation_failures
            ),
            "json_reference_failures": json_reference_failures,
            "csv_priority_failures": csv_priority_failures,
            "expected_invalid_xml_samples": list(
                EXPECTED_INVALID_XML
            ),
            "deterministic": not determinism_failures,
            "expected_exits_equal": not expected_exit_failures,
            "stderr_empty": not stderr_failures,
            "output_validity_matches_expected": (
                not validity_expectation_failures
            ),
            "json_default_references_equal": (
                not json_reference_failures
            ),
            "csv_priority_equal": not csv_priority_failures,
        },
        "limitations": [
            (
                "this closes ordinary output modes for the 21 baseline "
                "samples omitted by the primary matrix; special entropy/info/"
                "struct modes remain separate"
            ),
            (
                "four filetypes containing spaces produce invalid XML element "
                "names; this upstream behavior is fixed explicitly rather than "
                "treated as valid XML"
            ),
            (
                "only JSON and XML have document parsers; text/CSV/TSV "
                "validity means non-empty UTF-8 plus stable raw evidence"
            ),
            (
                "no Linux output matrix exists for these 21 samples, so "
                "cross-platform raw/semantic output comparison remains open"
            ),
            (
                "raw stdout/stderr hashes are unnormalized; no local absolute "
                "path or raw stream bytes are committed"
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
    sys.stdout.buffer.write(serialized)
    return (
        0
        if not (
            determinism_failures
            or expected_exit_failures
            or stderr_failures
            or validity_expectation_failures
            or json_reference_failures
            or csv_priority_failures
        )
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
