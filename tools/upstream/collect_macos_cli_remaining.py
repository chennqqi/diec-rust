#!/usr/bin/env python3
"""Collect remaining macOS Qt5 output and special CLI candidates."""

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
PRIMARY_COLLECTOR = "tools/upstream/collect_macos_cli_matrix.py"
PRIMARY_VALIDATOR = "tools/upstream/validate_macos_cli_matrix.py"
WINDOWS_MATRIX_HELPER = "tools/upstream/collect_windows_cli_matrix.py"
OUTPUT_HELPER = (
    "tools/upstream/collect_windows_cli_output_remaining.py"
)
SPECIAL_HELPER = (
    "tools/upstream/collect_windows_cli_special_remaining.py"
)
MATRIX_DEFINITIONS = "tools/upstream/compare_cli_oracles.py"
VALIDATOR = "tools/upstream/validate_macos_cli_remaining.py"
BASELINE_MANIFEST = "docs/research/data/baseline-corpus.json"
ADMISSION_REASON = (
    "remaining output and special CLI matrix candidate only; nested, "
    "path, database-error, and engine-only macOS closure remains missing"
)
LIMITATIONS = [
    (
        "the candidate extends ordinary output and entropy/info/struct "
        "modes from the five primary samples to the other 21 generated "
        "baseline samples"
    ),
    (
        "four fixed filetypes containing spaces are expected to produce "
        "invalid XML element names, matching the pinned upstream contract"
    ),
    (
        "JSON/XML projections, UTF-8 validity, CSV/all-flags priority, "
        "special priority, exit code, stderr, and every raw stream are "
        "recomputed by the validator"
    ),
    (
        "no Linux remaining-sample output/special matrix exists, so "
        "cross-platform raw and semantic comparison remains open"
    ),
]


class RemainingError(ValueError):
    """The remaining CLI candidate cannot be collected safely."""


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _load(root: Path, relative: str, name: str) -> Any:
    path = root / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RemainingError(f"cannot load helper module: {relative}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def collect(
    *,
    root: Path,
    binary: Path,
    source_dir: Path,
    qt_dir: Path,
    corpus_dir: Path,
    oracle_path: Path,
    baseline_path: Path,
    primary_path: Path,
    output: Path,
    timeout_seconds: int,
) -> dict[str, Any]:
    if sys.platform != "darwin" or platform.machine() != "x86_64":
        raise RemainingError("collector requires native Darwin x86_64")
    if not 1 <= timeout_seconds <= 3600:
        raise RemainingError("timeout-seconds must be in 1..3600")
    source_dir = source_dir.resolve(strict=True)
    qt_dir = qt_dir.resolve(strict=True)
    corpus_dir = corpus_dir.resolve(strict=True)
    binary = binary.resolve(strict=True)
    oracle_path = oracle_path.resolve(strict=True)
    baseline_path = baseline_path.resolve(strict=True)
    primary_path = primary_path.resolve(strict=True)
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    expected_paths = {
        baseline_path: "cli-baseline-candidate.json",
        primary_path: "cli-matrix-candidate.json",
    }
    for path, name in expected_paths.items():
        if path != (output.parent / name).resolve(strict=True):
            raise RemainingError(
                f"input report must be bundle-local: {name}"
            )
    if output.exists():
        raise RemainingError("candidate report already exists")
    raw_dir = output.parent / "raw" / "cli-remaining"
    raw_dir.mkdir(parents=True, exist_ok=True)
    if any(raw_dir.iterdir()):
        raise RemainingError("remaining raw directory must be empty")

    baseline_collector = _load(
        root,
        BASELINE_COLLECTOR,
        "macos_cli_baseline_collector_for_remaining",
    )
    baseline_validator = _load(
        root,
        BASELINE_VALIDATOR,
        "macos_cli_baseline_validator_for_remaining",
    )
    primary_validator = _load(
        root,
        PRIMARY_VALIDATOR,
        "macos_cli_primary_validator_for_remaining",
    )
    matrix_helper = _load(
        root,
        WINDOWS_MATRIX_HELPER,
        "windows_cli_matrix_helper_for_macos_remaining",
    )
    output_helper = _load(
        root,
        OUTPUT_HELPER,
        "windows_output_remaining_helper_for_macos",
    )
    special_helper = _load(
        root,
        SPECIAL_HELPER,
        "windows_special_remaining_helper_for_macos",
    )
    definitions = _load(
        root,
        MATRIX_DEFINITIONS,
        "cli_matrix_definitions_for_macos_remaining",
    )
    common = baseline_collector.load_module(
        "windows_cli_common_for_macos_remaining",
        root / baseline_collector.SHARED_COLLECTOR,
    )

    baseline_report = baseline_validator.load_json(baseline_path)[0]
    baseline_validator.validate_report(
        baseline_report,
        report_path=baseline_path,
        oracle_path=oracle_path,
        root=root,
    )
    primary_report = baseline_validator.load_json(primary_path)[0]
    primary_validator.validate_report(
        primary_report,
        report_path=primary_path,
        oracle_path=oracle_path,
        baseline_path=baseline_path,
        root=root,
    )
    oracle, oracle_raw = baseline_collector.validate_oracle_inputs(
        root, oracle_path, source_dir, qt_dir, binary
    )
    expected_binary = (
        source_dir / "build" / "release" / "diec"
    ).resolve(strict=True)
    if binary != expected_binary:
        raise RemainingError(
            "binary must be <source>/build/release/diec"
        )
    source = common.validate_source(source_dir)
    source["tracked_files_clean_before_and_after"] = True
    qt = baseline_collector.validate_qt(common, qt_dir, oracle)
    binary_sha256 = common.sha256_file(binary)
    if binary_sha256 != oracle["artifact"]["sha256"]:
        raise RemainingError("binary differs from oracle report")
    for reference in (baseline_report, primary_report):
        for field, actual in (
            ("source", source),
            ("qt", qt),
        ):
            if reference[field] != actual:
                raise RemainingError(
                    f"input report {field} identity differs"
                )
        if reference["binary"]["sha256"] != binary_sha256:
            raise RemainingError("input report binary differs")

    manifest_path = root / BASELINE_MANIFEST
    samples, manifest_sha256 = common.load_corpus(
        corpus_dir, manifest_path
    )
    sample_names = [str(sample["name"]) for sample in samples]
    covered = tuple(primary_report["selection"]["output"])
    if covered != tuple(output_helper.ALREADY_COVERED):
        raise RemainingError("primary sample selection drift")
    selected = [
        name for name in sample_names if name not in covered
    ]
    if len(sample_names) != 26 or len(selected) != 21:
        raise RemainingError("remaining sample partition drift")

    cases_by_kind = {
        "output": definitions.OUTPUT_MATRIX,
        "special": definitions.SPECIAL_MATRIX,
    }
    reports: dict[str, dict[str, object]] = {}
    determinism_failures: list[str] = []
    exit_failures: list[str] = []
    stderr_failures: list[str] = []
    validity_failures: list[str] = []
    json_reference_failures: list[str] = []
    priority_failures: list[str] = []

    for sample_name in selected:
        sample_report = reports.setdefault(sample_name, {})
        for kind in ("output", "special"):
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
                entry = baseline_collector.pair_report(
                    common,
                    output.parent,
                    (
                        "cli-remaining/"
                        f"{sample_name}/{kind}/{case.name}"
                    ),
                    first,
                    second,
                )
                entry.update(
                    {
                        "arguments": report_arguments,
                        "expected_exit_code": 0,
                        "expected_exit_code_equal": (
                            first.exit_code == 0
                        ),
                        "expected_empty_stderr": True,
                        "first_stderr_empty": first.stderr == b"",
                        "second_stderr_empty": second.stderr == b"",
                    }
                )
                if kind == "output":
                    first_valid = output_helper.output_validity(
                        case.name, first.stdout
                    )
                    second_valid = output_helper.output_validity(
                        case.name, second.stdout
                    )
                    expected_valid = not (
                        case.name == "xml"
                        and sample_name
                        in output_helper.EXPECTED_INVALID_XML
                    )
                    entry.update(
                        {
                            "first_output_valid": first_valid,
                            "second_output_valid": second_valid,
                            "expected_output_valid": expected_valid,
                            "output_validity_expected_equal": (
                                first_valid == expected_valid
                                and second_valid == expected_valid
                            ),
                        }
                    )
                    if case.name == "json":
                        first_tree = common.json_detect_tree(
                            first.stdout
                        )
                        second_tree = common.json_detect_tree(
                            second.stdout
                        )
                        baseline_entry = baseline_report["corpus"][
                            sample_name
                        ]
                        reference_equal = (
                            first.summary()
                            == _observation_identity(
                                baseline_entry["first"]
                            )
                            and second.summary()
                            == _observation_identity(
                                baseline_entry["second"]
                            )
                            and first_tree
                            == baseline_entry["first_detect_tree"]
                            and second_tree
                            == baseline_entry["second_detect_tree"]
                        )
                        entry.update(
                            {
                                "first_detect_tree": first_tree,
                                "second_detect_tree": second_tree,
                                "cli_baseline_reference_equal": (
                                    reference_equal
                                ),
                            }
                        )
                        if not reference_equal:
                            json_reference_failures.append(
                                sample_name
                            )
                    if (
                        first_valid != expected_valid
                        or second_valid != expected_valid
                    ):
                        validity_failures.append(
                            f"matrix.{sample_name}.output.{case.name}"
                        )
                else:
                    first_valid, first_projection = (
                        special_helper.parse_output(
                            case.name, first.stdout
                        )
                    )
                    second_valid, second_projection = (
                        special_helper.parse_output(
                            case.name, second.stdout
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
                    entry.update(
                        {
                            "first_output_valid": first_valid,
                            "second_output_valid": second_valid,
                        }
                    )
                    if (
                        case.name in special_helper.JSON_CASES
                        or case.name in special_helper.XML_CASES
                    ):
                        entry["first_projection"] = first_projection
                        entry["second_projection"] = second_projection
                    if not first_valid or not second_valid:
                        validity_failures.append(
                            f"matrix.{sample_name}.special.{case.name}"
                        )
                kind_report[case.name] = entry
                prefix = (
                    f"matrix.{sample_name}.{kind}.{case.name}"
                )
                if entry["determinism_differences"]:
                    determinism_failures.append(prefix)
                if first.exit_code != 0:
                    exit_failures.append(prefix)
                if first.stderr or second.stderr:
                    stderr_failures.append(prefix)

            if kind == "output":
                csv_pair = observations["csv"]
                all_pair = observations["all_output_flags"]
                equal = csv_pair == all_pair
                kind_report["all_output_flags"][
                    "csv_priority_reference_equal"
                ] = equal
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
                    kind_report[case_name][
                        "priority_reference_case"
                    ] = reference_name
                    kind_report[case_name][
                        "priority_reference_equal"
                    ] = equal
                    if not equal:
                        priority_failures.append(
                            "matrix."
                            f"{sample_name}.special.{case_name}"
                        )

    post_source = common.validate_source(source_dir)
    post_source["tracked_files_clean_before_and_after"] = True
    if post_source != source:
        raise RemainingError("source identity changed during collection")
    if common.sha256_file(binary) != binary_sha256:
        raise RemainingError("binary changed during collection")
    _, post_manifest_sha256 = common.load_corpus(
        corpus_dir, manifest_path
    )
    if post_manifest_sha256 != manifest_sha256:
        raise RemainingError("corpus changed during collection")

    case_counts = {
        kind: len(selected) * len(cases_by_kind[kind])
        for kind in cases_by_kind
    }
    case_count = sum(case_counts.values())
    report = {
        "schema_version": 1,
        "result": "candidate",
        "platform": PLATFORM,
        "generator": _generator_bindings(root),
        "oracle_report": {
            "path": "oracle-candidate.json",
            "sha256": sha256(oracle_raw),
        },
        "cli_baseline_report": {
            "path": "cli-baseline-candidate.json",
            "sha256": sha256(baseline_path.read_bytes()),
        },
        "cli_primary_matrix_report": {
            "path": "cli-matrix-candidate.json",
            "sha256": sha256(primary_path.read_bytes()),
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
        "selection": selected,
        "cases": {
            kind: [case.name for case in cases_by_kind[kind]]
            for kind in cases_by_kind
        },
        "output_classification": {
            "expected_invalid_xml_samples": list(
                output_helper.EXPECTED_INVALID_XML
            ),
            "special_json": list(special_helper.JSON_CASES),
            "special_xml": list(special_helper.XML_CASES),
        },
        "priority_references": {
            "output_all_flags": "csv",
            "special": special_helper.PRIORITY_REFERENCES,
        },
        "matrix": reports,
        "summary": {
            "sample_count": len(selected),
            "case_counts": case_counts,
            "case_count": case_count,
            "execution_count": 2 * case_count,
            "raw_stream_count": 4 * case_count,
            "determinism_failures": determinism_failures,
            "expected_exit_failures": exit_failures,
            "stderr_failures": stderr_failures,
            "validity_failures": validity_failures,
            "json_reference_failures": (
                json_reference_failures
            ),
            "priority_failures": priority_failures,
            "deterministic": not determinism_failures,
            "expected_exits_equal": not exit_failures,
            "stderr_empty": not stderr_failures,
            "outputs_valid_as_expected": not validity_failures,
            "json_baseline_references_equal": (
                not json_reference_failures
            ),
            "priority_references_equal": not priority_failures,
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


def _observation_identity(value: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "exit_code",
        "stdout_bytes",
        "stdout_sha256",
        "stderr_bytes",
        "stderr_sha256",
    )
    if any(field not in value for field in fields):
        raise RemainingError("observation identity is incomplete")
    return {field: value[field] for field in fields}


def _generator_bindings(root: Path) -> dict[str, str]:
    paths = {
        "path": "tools/upstream/collect_macos_cli_remaining.py",
        "validator_path": VALIDATOR,
        "baseline_collector_path": BASELINE_COLLECTOR,
        "baseline_validator_path": BASELINE_VALIDATOR,
        "primary_collector_path": PRIMARY_COLLECTOR,
        "primary_validator_path": PRIMARY_VALIDATOR,
        "windows_matrix_helper_path": WINDOWS_MATRIX_HELPER,
        "output_helper_path": OUTPUT_HELPER,
        "special_helper_path": SPECIAL_HELPER,
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


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--qt-dir", type=Path, required=True)
    parser.add_argument("--corpus-dir", type=Path, required=True)
    parser.add_argument("--oracle-report", type=Path, required=True)
    parser.add_argument("--cli-baseline-report", type=Path, required=True)
    parser.add_argument("--cli-primary-matrix-report", type=Path, required=True)
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
            primary_path=args.cli_primary_matrix_report,
            output=args.output,
            timeout_seconds=args.timeout_seconds,
        )
    except (RemainingError, OSError, ValueError) as error:
        print(f"macOS CLI remaining error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
