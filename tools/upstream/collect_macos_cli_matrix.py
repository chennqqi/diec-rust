#!/usr/bin/env python3
"""Collect the primary macOS Qt5 CLI option matrix candidate bundle."""

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
WINDOWS_MATRIX_HELPER = "tools/upstream/collect_windows_cli_matrix.py"
MATRIX_DEFINITIONS = "tools/upstream/compare_cli_oracles.py"
VALIDATOR = "tools/upstream/validate_macos_cli_matrix.py"
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
OUTPUT_SAMPLES = (
    "empty.bin",
    "minimal.exe",
    "minimal.pdf",
    "payload.zip",
    "plain.txt",
)
SPECIAL_SAMPLES = OUTPUT_SAMPLES
ADMISSION_REASON = (
    "primary CLI option matrix candidate only; the complete 68-row "
    "macOS closure and remaining CLI/engine matrices are missing"
)
LIMITATIONS = [
    (
        "scan options cover all 26 baseline samples; output and "
        "entropy/info/struct modes cover five representative samples"
    ),
    (
        "ordinary output and special modes for the other 21 samples "
        "remain a separate candidate matrix"
    ),
    (
        "nested, path, database-error, count-boundary, dispatch, "
        "result-model, signature-path, and other engine-only matrices "
        "remain uncollected on macOS"
    ),
    (
        "all raw stdout and stderr streams are retained; Linux Qt5 "
        "comparison is limited to fixed exit codes where the committed "
        "reference exposes them"
    ),
]


class MatrixError(ValueError):
    """The matrix candidate cannot be collected safely."""


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def observation_identity(value: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "exit_code",
        "stdout_bytes",
        "stdout_sha256",
        "stderr_bytes",
        "stderr_sha256",
    )
    if any(field not in value for field in fields):
        raise MatrixError("baseline observation identity is incomplete")
    return {field: value[field] for field in fields}


def collect(
    *,
    root: Path,
    binary: Path,
    source_dir: Path,
    qt_dir: Path,
    corpus_dir: Path,
    oracle_path: Path,
    baseline_path: Path,
    output: Path,
    timeout_seconds: int,
) -> dict[str, Any]:
    if sys.platform != "darwin" or platform.machine() != "x86_64":
        raise MatrixError("collector requires native Darwin x86_64")
    if not 1 <= timeout_seconds <= 3600:
        raise MatrixError("timeout-seconds must be in 1..3600")

    source_dir = source_dir.resolve(strict=True)
    qt_dir = qt_dir.resolve(strict=True)
    corpus_dir = corpus_dir.resolve(strict=True)
    binary = binary.resolve(strict=True)
    oracle_path = oracle_path.resolve(strict=True)
    baseline_path = baseline_path.resolve(strict=True)
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise MatrixError("candidate report already exists")
    if baseline_path != (
        output.parent / "cli-baseline-candidate.json"
    ).resolve(strict=True):
        raise MatrixError(
            "baseline must be bundle-local cli-baseline-candidate.json"
        )
    matrix_raw_dir = output.parent / "raw" / "cli-matrix"
    matrix_raw_dir.mkdir(parents=True, exist_ok=True)
    if any(matrix_raw_dir.iterdir()):
        raise MatrixError("matrix raw directory must be empty")

    baseline_collector = _load(
        root,
        BASELINE_COLLECTOR,
        "macos_cli_baseline_collector_for_matrix",
    )
    baseline_validator = _load(
        root,
        BASELINE_VALIDATOR,
        "macos_cli_baseline_validator_for_matrix",
    )
    common = baseline_collector.load_module(
        "windows_cli_baseline_common_for_macos_matrix",
        root / baseline_collector.SHARED_COLLECTOR,
    )
    matrix_helper = _load(
        root,
        WINDOWS_MATRIX_HELPER,
        "windows_cli_matrix_helper_for_macos",
    )
    definitions = _load(
        root,
        MATRIX_DEFINITIONS,
        "cli_matrix_definitions_for_macos",
    )

    baseline_report = baseline_validator.load_json(baseline_path)[0]
    baseline_validator.validate_report(
        baseline_report,
        report_path=baseline_path,
        oracle_path=oracle_path,
        root=root,
    )
    baseline_raw = baseline_path.read_bytes()
    oracle, oracle_raw = baseline_collector.validate_oracle_inputs(
        root, oracle_path, source_dir, qt_dir, binary
    )
    expected_binary = (
        source_dir / "build" / "release" / "diec"
    ).resolve(strict=True)
    if binary != expected_binary:
        raise MatrixError(
            "binary must be <source>/build/release/diec"
        )
    source = common.validate_source(source_dir)
    source["tracked_files_clean_before_and_after"] = True
    qt = baseline_collector.validate_qt(
        common, qt_dir, oracle
    )
    binary_sha256 = common.sha256_file(binary)
    if binary_sha256 != oracle["artifact"]["sha256"]:
        raise MatrixError("binary differs from oracle report")
    for field, actual in (
        ("source", source),
        ("qt", qt),
    ):
        if baseline_report[field] != actual:
            raise MatrixError(
                f"baseline {field} identity differs"
            )
    if (
        baseline_report["binary"]["sha256"] != binary_sha256
        or baseline_report["binary"]["size"]
        != binary.stat().st_size
    ):
        raise MatrixError("baseline binary identity differs")

    manifest_path = root / BASELINE_MANIFEST
    samples, manifest_sha256 = common.load_corpus(
        corpus_dir, manifest_path
    )
    sample_names = [str(sample["name"]) for sample in samples]
    if len(sample_names) != 26:
        raise MatrixError("baseline sample count changed")
    if (
        baseline_report["corpus_manifest"]["sha256"]
        != manifest_sha256
        or set(baseline_report["corpus"]) != set(sample_names)
    ):
        raise MatrixError("baseline corpus binding differs")
    missing = (
        set(OUTPUT_SAMPLES) | set(SPECIAL_SAMPLES)
    ) - set(sample_names)
    if missing:
        raise MatrixError(
            f"matrix selections are absent: {sorted(missing)}"
        )

    cases_by_kind = {
        "output": definitions.OUTPUT_MATRIX,
        "scan": definitions.SCAN_MATRIX,
        "special": definitions.SPECIAL_MATRIX,
    }
    selected = {
        "output": OUTPUT_SAMPLES,
        "scan": tuple(sample_names),
        "special": SPECIAL_SAMPLES,
    }
    linux_reports: dict[str, dict[str, Any]] = {}
    linux_raw: dict[str, bytes] = {}
    for kind, relative in LINUX_REFERENCES.items():
        path = root / relative
        linux_reports[kind], linux_raw[kind] = (
            baseline_collector.load_json(path)
        )
        matrix_helper.validate_reference_matrix(
            linux_reports[kind],
            kind=kind,
            samples=OUTPUT_SAMPLES,
            cases=cases_by_kind[kind],
        )

    report_matrix: dict[str, dict[str, object]] = {}
    determinism_failures: list[str] = []
    default_reference_failures: list[str] = []
    linux_exit_code_failures: list[str] = []
    for kind in ("output", "scan", "special"):
        for sample_name in selected[kind]:
            sample_report = report_matrix.setdefault(
                sample_name, {}
            )
            kind_report: dict[str, object] = {}
            sample_report[kind] = kind_report
            observations: dict[str, tuple[Any, Any]] = {}
            for case in cases_by_kind[kind]:
                actual_arguments = (
                    *matrix_helper.translate_arguments(
                        case.arguments,
                        source_dir,
                        report=False,
                    ),
                    str(corpus_dir / sample_name),
                )
                report_arguments = [
                    *matrix_helper.translate_arguments(
                        case.arguments,
                        source_dir,
                        report=True,
                    ),
                    f"<corpus>/{sample_name}",
                ]
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
                paired = baseline_collector.pair_report(
                    common,
                    output.parent,
                    (
                        "cli-matrix/"
                        f"{sample_name}/{kind}/{case.name}"
                    ),
                    first,
                    second,
                )
                paired["arguments"] = report_arguments
                if kind == "scan":
                    paired["first_detect_tree"] = (
                        common.json_detect_tree(first.stdout)
                    )
                    paired["second_detect_tree"] = (
                        common.json_detect_tree(second.stdout)
                    )
                if sample_name in OUTPUT_SAMPLES:
                    linux_entry = linux_reports[kind]["matrix"][
                        sample_name
                    ][kind][case.name]
                    linux_exit_code = linux_entry["left"][
                        "exit_code"
                    ]
                    paired["linux_qt5_exit_code"] = linux_exit_code
                    paired["linux_qt5_exit_code_equal"] = (
                        first.exit_code == linux_exit_code
                    )
                    if first.exit_code != linux_exit_code:
                        linux_exit_code_failures.append(
                            "matrix."
                            f"{sample_name}.{kind}.{case.name}"
                        )
                kind_report[case.name] = paired
                if paired["determinism_differences"]:
                    determinism_failures.append(
                        "matrix."
                        f"{sample_name}.{kind}.{case.name}"
                    )

            if kind == "scan":
                default_first, default_second = observations[
                    "default"
                ]
                default_entry = kind_report["default"]
                baseline_entry = baseline_report["corpus"][
                    sample_name
                ]
                reference_equal = (
                    default_first.summary()
                    == observation_identity(
                        baseline_entry["first"]
                    )
                    and default_second.summary()
                    == observation_identity(
                        baseline_entry["second"]
                    )
                    and default_entry["first_detect_tree"]
                    == baseline_entry["first_detect_tree"]
                    and default_entry["second_detect_tree"]
                    == baseline_entry["second_detect_tree"]
                )
                default_entry[
                    "cli_baseline_reference_equal"
                ] = reference_equal
                if not reference_equal:
                    default_reference_failures.append(sample_name)
                for case_name, (first, second) in (
                    observations.items()
                ):
                    entry = kind_report[case_name]
                    entry["first_changes_from_default"] = (
                        matrix_helper.observation_differences(
                            default_first, first
                        )
                    )
                    entry["second_changes_from_default"] = (
                        matrix_helper.observation_differences(
                            default_second, second
                        )
                    )

    post_source = common.validate_source(source_dir)
    post_source["tracked_files_clean_before_and_after"] = True
    if post_source != source:
        raise MatrixError("source identity changed during collection")
    if common.sha256_file(binary) != binary_sha256:
        raise MatrixError("binary changed during collection")
    _, post_manifest_sha256 = common.load_corpus(
        corpus_dir, manifest_path
    )
    if post_manifest_sha256 != manifest_sha256:
        raise MatrixError("corpus changed during collection")

    case_counts = {
        kind: len(selected[kind]) * len(cases_by_kind[kind])
        for kind in selected
    }
    report = {
        "schema_version": 1,
        "result": "candidate",
        "platform": PLATFORM,
        "generator": {
            "path": (
                "tools/upstream/collect_macos_cli_matrix.py"
            ),
            "sha256": sha256(Path(__file__).read_bytes()),
            "validator_path": VALIDATOR,
            "validator_sha256": sha256(
                (root / VALIDATOR).read_bytes()
            ),
            "baseline_collector_path": BASELINE_COLLECTOR,
            "baseline_collector_sha256": sha256(
                (root / BASELINE_COLLECTOR).read_bytes()
            ),
            "baseline_validator_path": BASELINE_VALIDATOR,
            "baseline_validator_sha256": sha256(
                (root / BASELINE_VALIDATOR).read_bytes()
            ),
            "windows_matrix_helper_path": (
                WINDOWS_MATRIX_HELPER
            ),
            "windows_matrix_helper_sha256": sha256(
                (root / WINDOWS_MATRIX_HELPER).read_bytes()
            ),
            "matrix_definitions_path": MATRIX_DEFINITIONS,
            "matrix_definitions_sha256": sha256(
                (root / MATRIX_DEFINITIONS).read_bytes()
            ),
        },
        "oracle_report": {
            "path": "oracle-candidate.json",
            "sha256": sha256(oracle_raw),
        },
        "cli_baseline_report": {
            "path": "cli-baseline-candidate.json",
            "sha256": sha256(baseline_raw),
        },
        "source": source,
        "qt": qt,
        "binary": {
            "size": binary.stat().st_size,
            "sha256": binary_sha256,
            "relative_path": "build/release/diec",
        },
        "corpus_manifest": {
            "path": BASELINE_MANIFEST,
            "sha256": manifest_sha256,
            "sample_count": len(samples),
        },
        "linux_qt5_references": {
            kind: {
                "path": LINUX_REFERENCES[kind],
                "sha256": sha256(linux_raw[kind]),
            }
            for kind in ("output", "scan", "special")
        },
        "selection": {
            kind: list(names) for kind, names in selected.items()
        },
        "matrix": report_matrix,
        "summary": {
            "sample_count": len(report_matrix),
            "case_counts": case_counts,
            "case_count": sum(case_counts.values()),
            "execution_count": 2 * sum(case_counts.values()),
            "raw_stream_count": 4 * sum(case_counts.values()),
            "determinism_failures": determinism_failures,
            "default_reference_failures": (
                default_reference_failures
            ),
            "linux_exit_code_failures": (
                linux_exit_code_failures
            ),
            "deterministic": not determinism_failures,
            "default_reference_equal": (
                not default_reference_failures
            ),
            "linux_exit_codes_equal": (
                not linux_exit_code_failures
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


def _load(root: Path, relative: str, name: str) -> Any:
    path = root / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise MatrixError(f"cannot load helper module: {relative}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--qt-dir", type=Path, required=True)
    parser.add_argument("--corpus-dir", type=Path, required=True)
    parser.add_argument("--oracle-report", type=Path, required=True)
    parser.add_argument("--cli-baseline-report", type=Path, required=True)
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
            corpus_dir=args.corpus_dir,
            oracle_path=args.oracle_report,
            baseline_path=args.cli_baseline_report,
            output=args.output,
            timeout_seconds=args.timeout_seconds,
        )
    except (MatrixError, OSError, ValueError) as error:
        print(f"macOS CLI matrix error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
