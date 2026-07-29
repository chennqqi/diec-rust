#!/usr/bin/env python3
"""Collect Linux Qt5/Qt6 output modes omitted by the primary matrix."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
WINDOWS_COLLECTOR_SCRIPT = (
    ROOT / "tools/upstream/collect_windows_cli_output_remaining.py"
)
LINUX_SPECIAL_COLLECTOR_SCRIPT = (
    ROOT / "tools/upstream/collect_linux_cli_special_remaining.py"
)


def load_module(name: str, path: Path) -> object:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load helper module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


linux_helper = load_module(
    "collect_linux_cli_output_remaining_common_helper",
    LINUX_SPECIAL_COLLECTOR_SCRIPT,
)
windows_collector = load_module(
    "collect_windows_cli_output_remaining_linux_helper",
    WINDOWS_COLLECTOR_SCRIPT,
)
matrix = linux_helper.matrix
EXPECTED_RAW_DIFFERENCES = {
    f"matrix.minimal-pe64.exe.{case.name}": ("stderr",)
    for case in matrix.OUTPUT_MATRIX
}


class CollectionError(RuntimeError):
    """Raised when a pinned input identity or report contract drifts."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-dir", type=Path, required=True)
    parser.add_argument("--qt5-image", default=linux_helper.QT5_IMAGE)
    parser.add_argument("--qt5-image-id", default=linux_helper.QT5_IMAGE_ID)
    parser.add_argument("--qt6-image", default=linux_helper.QT6_IMAGE)
    parser.add_argument("--qt6-image-id", default=linux_helper.QT6_IMAGE_ID)
    parser.add_argument("--qt5-binary", default=linux_helper.ORACLE_BINARY)
    parser.add_argument("--qt6-binary", default=linux_helper.ORACLE_BINARY)
    parser.add_argument(
        "--expected-revision",
        default=linux_helper.UPSTREAM_COMMIT,
    )
    parser.add_argument(
        "--reference-manifest",
        type=Path,
        default=ROOT / "docs/research/data/baseline-corpus.json",
    )
    parser.add_argument(
        "--windows-reference",
        type=Path,
        default=ROOT
        / "docs/research/data/windows-qt5-cli-output-remaining.json",
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def validate_report_binding(
    windows_report: dict[str, object],
    selected_samples: list[str],
    case_names: list[str],
) -> None:
    if windows_report.get("platform") != "windows-x86_64-qt5":
        raise CollectionError("unexpected Windows report platform")
    if windows_report.get("selection") != selected_samples:
        raise CollectionError("Windows output selection differs")
    if windows_report.get("cases") != case_names:
        raise CollectionError("Windows output cases differ")
    if windows_report.get("generator_sha256") != linux_helper.sha256_file(
        WINDOWS_COLLECTOR_SCRIPT
    ):
        raise CollectionError("Windows output collector binding differs")
    helper = windows_report.get("helpers", {}).get(
        "matrix_definitions",
        {},
    )
    if helper.get("sha256") != linux_helper.sha256_file(
        linux_helper.MATRIX_SCRIPT
    ):
        raise CollectionError("Windows matrix definition binding differs")


def main() -> int:
    args = parse_args()
    corpus_dir = args.corpus_dir.resolve(strict=True)
    reference_path = args.reference_manifest.resolve(strict=True)
    corpus_manifest_path = corpus_dir / "manifest.json"
    if corpus_manifest_path.read_bytes() != reference_path.read_bytes():
        raise CollectionError("generated corpus manifest differs from reference")
    samples = matrix.load_corpus(corpus_dir)
    sample_names = [str(sample["name"]) for sample in samples]
    already_covered = windows_collector.ALREADY_COVERED
    if not set(already_covered).issubset(sample_names):
        raise CollectionError("primary output selection is absent from corpus")
    selected_samples = [
        name for name in sample_names if name not in already_covered
    ]
    if len(sample_names) != 26 or len(selected_samples) != 21:
        raise CollectionError("Linux output sample partition changed")

    cases = matrix.OUTPUT_MATRIX
    case_names = [case.name for case in cases]
    if case_names != [
        case.name for case in windows_collector.matrix_definitions.OUTPUT_MATRIX
    ]:
        raise CollectionError("output matrix helper definitions differ")

    windows_path = args.windows_reference.resolve(strict=True)
    windows_raw = windows_path.read_bytes()
    windows_report = json.loads(windows_raw)
    validate_report_binding(windows_report, selected_samples, case_names)

    qt5_identity = linux_helper.inspect_image(
        args.qt5_image,
        args.qt5_image_id,
        args.expected_revision,
    )
    qt6_identity = linux_helper.inspect_image(
        args.qt6_image,
        args.qt6_image_id,
        args.expected_revision,
    )
    qt5_identity["binary"] = args.qt5_binary
    qt6_identity["binary"] = args.qt6_binary

    reports = {}
    observed_raw_differences = {}
    unexpected_raw_difference_failures = []
    exit_failures = []
    stderr_contract_failures = []
    validity_failures = []
    qt_json_projection_failures = []
    windows_json_projection_failures = []
    priority_failures = []
    expected_invalid_xml = set(windows_collector.EXPECTED_INVALID_XML)
    for sample_name in selected_samples:
        case_reports = {}
        reports[sample_name] = case_reports
        observations = {"qt5": {}, "qt6": {}}
        for case in cases:
            arguments = (*case.arguments, f"/corpus/{sample_name}")
            qt5 = matrix.observe(
                args.qt5_image,
                args.qt5_binary,
                arguments,
                corpus_dir,
            )
            qt6 = matrix.observe(
                args.qt6_image,
                args.qt6_binary,
                arguments,
                corpus_dir,
            )
            observations["qt5"][case.name] = qt5
            observations["qt6"][case.name] = qt6
            differences = matrix.compare_observations(qt5, qt6)
            prefix = f"matrix.{sample_name}.{case.name}"
            if differences:
                observed_raw_differences[prefix] = differences
            expected_differences = list(
                EXPECTED_RAW_DIFFERENCES.get(prefix, ())
            )
            raw_difference_expected_equal = (
                differences == expected_differences
            )

            qt5_valid = windows_collector.output_validity(
                case.name,
                qt5.stdout,
            )
            qt6_valid = windows_collector.output_validity(
                case.name,
                qt6.stdout,
            )
            expected_valid = not (
                case.name == "xml"
                and sample_name in expected_invalid_xml
            )
            windows_case = windows_report["matrix"][sample_name][case.name]
            qt5_tree = (
                matrix.json_detect_tree(qt5.stdout)
                if case.name == "json"
                else None
            )
            qt6_tree = (
                matrix.json_detect_tree(qt6.stdout)
                if case.name == "json"
                else None
            )
            windows_tree = windows_case.get("first_detect_tree")
            qt_json_projection_equal = (
                qt5_tree == qt6_tree if case.name == "json" else None
            )
            windows_json_projection_equal = (
                qt5_tree == windows_tree if case.name == "json" else None
            )
            expected_qt5_stderr_empty = True
            expected_qt6_stderr_empty = not expected_differences
            stderr_contract_equal = (
                (qt5.stderr == b"") == expected_qt5_stderr_empty
                and (qt6.stderr == b"") == expected_qt6_stderr_empty
            )
            case_reports[case.name] = {
                "arguments": list(arguments),
                "qt5": qt5.summary(),
                "qt6": qt6.summary(),
                "raw_differences": differences,
                "expected_raw_differences": expected_differences,
                "raw_difference_expected_equal": (
                    raw_difference_expected_equal
                ),
                "expected_exit_code": 0,
                "qt5_output_valid": qt5_valid,
                "qt6_output_valid": qt6_valid,
                "expected_output_valid": expected_valid,
                "output_validity_expected_equal": (
                    qt5_valid == expected_valid
                    and qt6_valid == expected_valid
                ),
                "expected_qt5_stderr_empty": (
                    expected_qt5_stderr_empty
                ),
                "expected_qt6_stderr_empty": (
                    expected_qt6_stderr_empty
                ),
                "stderr_contract_equal": stderr_contract_equal,
                "qt5_json_detect_tree": qt5_tree,
                "qt6_json_detect_tree": qt6_tree,
                "qt5_qt6_json_projection_equal": (
                    qt_json_projection_equal
                ),
                "windows_qt5_json_detect_tree": windows_tree,
                "windows_linux_qt5_json_projection_equal": (
                    windows_json_projection_equal
                ),
            }
            if not raw_difference_expected_equal:
                unexpected_raw_difference_failures.append(prefix)
            if qt5.exit_code != 0 or qt6.exit_code != 0:
                exit_failures.append(prefix)
            if not stderr_contract_equal:
                stderr_contract_failures.append(prefix)
            if qt5_valid != expected_valid or qt6_valid != expected_valid:
                validity_failures.append(prefix)
            if qt_json_projection_equal is False:
                qt_json_projection_failures.append(prefix)
            if windows_json_projection_equal is False:
                windows_json_projection_failures.append(prefix)

        for platform in ("qt5", "qt6"):
            equal = (
                observations[platform]["all_output_flags"]
                == observations[platform]["csv"]
            )
            case_reports["all_output_flags"][
                f"{platform}_priority_reference_case"
            ] = "csv"
            case_reports["all_output_flags"][
                f"{platform}_priority_reference_equal"
            ] = equal
            if not equal:
                priority_failures.append(
                    f"matrix.{sample_name}.all_output_flags.{platform}"
                )

    missing_expected_raw_differences = sorted(
        set(EXPECTED_RAW_DIFFERENCES) - set(observed_raw_differences)
    )
    case_count = len(selected_samples) * len(cases)
    report = {
        "schema_version": 1,
        "generator": (
            "tools/upstream/collect_linux_cli_output_remaining.py"
        ),
        "generator_sha256": linux_helper.sha256_file(Path(__file__)),
        "matrix_definitions": {
            "path": "tools/upstream/compare_cli_oracles.py",
            "sha256": linux_helper.sha256_file(
                linux_helper.MATRIX_SCRIPT
            ),
        },
        "linux_identity_helper": {
            "path": (
                "tools/upstream/"
                "collect_linux_cli_special_remaining.py"
            ),
            "sha256": linux_helper.sha256_file(
                LINUX_SPECIAL_COLLECTOR_SCRIPT
            ),
        },
        "windows_collector": {
            "path": (
                "tools/upstream/"
                "collect_windows_cli_output_remaining.py"
            ),
            "sha256": linux_helper.sha256_file(
                WINDOWS_COLLECTOR_SCRIPT
            ),
        },
        "platforms": {
            "linux-x86_64-qt5": qt5_identity,
            "linux-x86_64-qt6": qt6_identity,
        },
        "corpus_manifest": {
            "path": "docs/research/data/baseline-corpus.json",
            "sha256": linux_helper.sha256_file(reference_path),
            "sample_count": len(samples),
        },
        "windows_reference": {
            "path": (
                "docs/research/data/"
                "windows-qt5-cli-output-remaining.json"
            ),
            "sha256": hashlib.sha256(windows_raw).hexdigest(),
        },
        "selection": selected_samples,
        "cases": case_names,
        "expected_raw_differences": {
            key: list(value)
            for key, value in EXPECTED_RAW_DIFFERENCES.items()
        },
        "matrix": reports,
        "summary": {
            "sample_count": len(selected_samples),
            "case_count": case_count,
            "execution_count": 2 * case_count,
            "observed_raw_differences": observed_raw_differences,
            "expected_raw_difference_count": len(
                EXPECTED_RAW_DIFFERENCES
            ),
            "unexpected_raw_difference_failures": (
                unexpected_raw_difference_failures
            ),
            "missing_expected_raw_differences": (
                missing_expected_raw_differences
            ),
            "exit_failures": exit_failures,
            "stderr_contract_failures": stderr_contract_failures,
            "validity_failures": validity_failures,
            "qt_json_projection_failures": (
                qt_json_projection_failures
            ),
            "windows_json_projection_failures": (
                windows_json_projection_failures
            ),
            "priority_failures": priority_failures,
            "raw_differences_match_expected": not (
                unexpected_raw_difference_failures
                or missing_expected_raw_differences
            ),
            "all_exits_zero": not exit_failures,
            "stderr_contract_matches": not stderr_contract_failures,
            "output_validity_matches_expected": not validity_failures,
            "qt_json_projections_equal": (
                not qt_json_projection_failures
            ),
            "windows_linux_qt5_json_projections_equal": (
                not windows_json_projection_failures
            ),
            "priority_references_equal": not priority_failures,
            "expected_invalid_xml_samples": sorted(
                expected_invalid_xml
            ),
        },
        "limitations": [
            (
                "Linux Qt5 and Qt6 are each executed once per case; the "
                "Windows reference retains two-run determinism evidence"
            ),
            (
                "cross-platform Windows comparison is exact for JSON detect "
                "trees and document validity, not hash-only text/CSV/TSV"
            ),
            (
                "the seven expected Qt6 stderr differences for minimal-pe64 "
                "are retained exactly and are not normalized away"
            ),
            (
                "four filetypes containing spaces remain invalid XML on both "
                "Linux Qt versions and Windows"
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
    failures = (
        unexpected_raw_difference_failures
        or missing_expected_raw_differences
        or exit_failures
        or stderr_contract_failures
        or validity_failures
        or qt_json_projection_failures
        or windows_json_projection_failures
        or priority_failures
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
