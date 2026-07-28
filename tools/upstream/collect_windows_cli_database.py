#!/usr/bin/env python3
"""Collect a deterministic native-Windows Qt5 CLI database matrix."""

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
    "collect_windows_cli_baseline_database_helper",
    BASELINE_SCRIPT,
)
matrix_definitions = load_module(
    "compare_cli_oracles_database_definitions",
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


def translate_argument(
    argument: str,
    source_dir: Path,
    fixture_dir: Path,
    *,
    report: bool,
) -> str:
    source_prefix = "/opt/die-source"
    fixture_prefix = "/dbfx"
    if argument == source_prefix or argument.startswith(source_prefix + "/"):
        suffix = argument[len(source_prefix) :].lstrip("/")
        if report:
            return "<source>" + (f"/{suffix}" if suffix else "")
        return str(source_dir.joinpath(*suffix.split("/")))
    if argument == fixture_prefix or argument.startswith(fixture_prefix + "/"):
        suffix = argument[len(fixture_prefix) :].lstrip("/")
        if report:
            return "<dbfx>" + (f"/{suffix}" if suffix else "")
        return str(fixture_dir.joinpath(*suffix.split("/")))
    if argument.startswith((source_prefix, fixture_prefix)):
        raise MatrixError(f"untranslated database path: {argument}")
    return argument


def translate_arguments(
    arguments: Sequence[str],
    source_dir: Path,
    fixture_dir: Path,
    *,
    report: bool,
) -> tuple[str, ...]:
    return tuple(
        translate_argument(
            argument,
            source_dir,
            fixture_dir,
            report=report,
        )
        for argument in arguments
    )


def normalize_windows_stdout_for_linux(
    data: bytes,
    actual_arguments: Sequence[str],
    linux_arguments: Sequence[str],
) -> bytes:
    if len(actual_arguments) != len(linux_arguments):
        raise MatrixError("argument lists differ in length")
    normalized = data
    replacements = []
    for actual, linux in zip(actual_arguments, linux_arguments, strict=True):
        if actual == linux:
            continue
        actual_variants = {
            actual.encode("utf-8"),
            actual.replace("\\", "/").encode("utf-8"),
        }
        for variant in actual_variants:
            replacements.append((variant, linux.encode("utf-8")))
    for actual, linux in sorted(
        replacements,
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        normalized = normalized.replace(actual, linux)
    return normalized.replace(b"\r\n", b"\n")


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


def validate_linux_reference(
    reference: dict[str, object],
) -> dict[str, object]:
    fixture = reference.get("database_fixture")
    if not isinstance(fixture, dict):
        raise MatrixError("Linux database reference has no fixture")
    cases = fixture.get("cases")
    expected_cases = {
        case.name for case in matrix_definitions.DATABASE_CASES
    }
    if not isinstance(cases, dict) or set(cases) != expected_cases:
        raise MatrixError("Linux database reference case set differs")
    return cases


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--qt-dir", type=Path, required=True)
    parser.add_argument("--fixture-dir", type=Path, required=True)
    parser.add_argument("--expected-binary-sha256", required=True)
    parser.add_argument(
        "--fixture-manifest",
        type=Path,
        default=ROOT / "docs/research/data/database-fixture.json",
    )
    parser.add_argument(
        "--linux-reference",
        type=Path,
        default=ROOT
        / "docs/research/data/cli-database-matrix-linux-qt5-qt6.json",
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
    fixture_dir = args.fixture_dir.resolve(strict=True)
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
    fixture_manifest_path = args.fixture_manifest.resolve(strict=True)
    fixture_manifest_raw = (fixture_dir / "manifest.json").read_bytes()
    if fixture_manifest_raw != fixture_manifest_path.read_bytes():
        raise MatrixError("database fixture manifest differs from reference")
    fixture_manifest = matrix_definitions.load_database_fixture(fixture_dir)

    linux_reference_path = args.linux_reference.resolve(strict=True)
    linux_reference, linux_reference_raw = read_json(
        linux_reference_path
    )
    linux_cases = validate_linux_reference(linux_reference)

    report_cases: dict[str, object] = {}
    determinism_failures: list[str] = []
    linux_exit_code_failures: list[str] = []
    linux_load_error_failures: list[str] = []
    linux_document_validity_failures: list[str] = []
    linux_normalized_stdout_failures: list[str] = []

    for case in matrix_definitions.DATABASE_CASES:
        actual_arguments = translate_arguments(
            case.arguments,
            source_dir,
            fixture_dir,
            report=False,
        )
        report_arguments = translate_arguments(
            case.arguments,
            source_dir,
            fixture_dir,
            report=True,
        )
        first, second, paired = collect_pair(
            binary,
            qt_dir,
            actual_arguments,
            timeout_seconds=args.timeout_seconds,
        )
        linux_case = linux_cases[case.name]
        first_load_error = b"Cannot load database:" in first.stdout
        second_load_error = b"Cannot load database:" in second.stdout
        linux_load_error = linux_case["left_reports_load_error"]
        normalized_stdout = normalize_windows_stdout_for_linux(
            first.stdout,
            actual_arguments,
            case.arguments,
        )
        normalized_stdout_sha256 = hashlib.sha256(
            normalized_stdout
        ).hexdigest()
        normalized_stdout_equal = (
            normalized_stdout_sha256
            == linux_case["left"]["stdout_sha256"]
        )
        paired.update(
            {
                "arguments": list(report_arguments),
                "first_reports_load_error": first_load_error,
                "second_reports_load_error": second_load_error,
                "linux_qt5_reports_load_error": linux_load_error,
                "linux_qt5_reports_load_error_equal": (
                    first_load_error == linux_load_error
                ),
                "reports_parse_error": (
                    b"SyntaxError: Parse error" in first.stdout
                ),
                "reports_runtime_error": (
                    b"Error: database fixture" in first.stdout
                ),
                "linux_qt5_raw_differences": raw_differences(
                    first.summary(),
                    linux_case["left"],
                ),
                "linux_normalized_stdout_sha256": (
                    normalized_stdout_sha256
                ),
                "linux_qt5_normalized_stdout_equal": (
                    normalized_stdout_equal
                ),
            }
        )
        if case.name.endswith("_json"):
            first_valid_json = matrix_definitions.document_is_valid(
                first.stdout,
                "json",
            )
            second_valid_json = matrix_definitions.document_is_valid(
                second.stdout,
                "json",
            )
            linux_valid_json = linux_case["left_valid_json"]
            paired.update(
                {
                    "first_valid_json": first_valid_json,
                    "second_valid_json": second_valid_json,
                    "linux_qt5_valid_json": linux_valid_json,
                    "linux_qt5_valid_json_equal": (
                        first_valid_json == linux_valid_json
                    ),
                }
            )
            if first_valid_json != linux_valid_json:
                linux_document_validity_failures.append(case.name)
        report_cases[case.name] = paired
        if paired["determinism_differences"]:
            determinism_failures.append(case.name)
        if first.exit_code != linux_case["left"]["exit_code"]:
            linux_exit_code_failures.append(case.name)
        if first_load_error != linux_load_error:
            linux_load_error_failures.append(case.name)
        if not normalized_stdout_equal:
            linux_normalized_stdout_failures.append(case.name)

    case_count = len(matrix_definitions.DATABASE_CASES)
    report = {
        "schema_version": 1,
        "generator": "tools/upstream/collect_windows_cli_database.py",
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
        "fixture": {
            "manifest": "docs/research/data/database-fixture.json",
            "sha256": hashlib.sha256(fixture_manifest_raw).hexdigest(),
            "directories": fixture_manifest["directories"],
            "entries": fixture_manifest["entries"],
        },
        "linux_qt5_reference": {
            "path": (
                "docs/research/data/"
                "cli-database-matrix-linux-qt5-qt6.json"
            ),
            "sha256": hashlib.sha256(linux_reference_raw).hexdigest(),
        },
        "cases": report_cases,
        "summary": {
            "case_count": case_count,
            "execution_count": 2 * case_count,
            "determinism_failures": determinism_failures,
            "linux_exit_code_failures": linux_exit_code_failures,
            "linux_load_error_failures": linux_load_error_failures,
            "linux_document_validity_failures": (
                linux_document_validity_failures
            ),
            "linux_normalized_stdout_failures": (
                linux_normalized_stdout_failures
            ),
            "deterministic": not determinism_failures,
            "linux_exit_codes_equal": not linux_exit_code_failures,
            "linux_load_errors_equal": not linux_load_error_failures,
            "linux_document_validity_equal": (
                not linux_document_validity_failures
            ),
            "linux_normalized_stdout_equal": (
                not linux_normalized_stdout_failures
            ),
        },
        "normalization": {
            "purpose": (
                "compare raw Windows output to the committed Linux Qt5 "
                "stdout hashes after only named platform transformations"
            ),
            "operations": [
                (
                    "replace each actual Windows path argument with the exact "
                    "corresponding original Linux matrix argument"
                ),
                "replace CRLF with LF",
            ],
            "not_performed": [
                "JSON parsing or reserialization",
                "diagnostic removal or rewriting",
                "record sorting",
                "whitespace changes other than CRLF line endings",
            ],
        },
        "limitations": [
            (
                "this report covers the 18 committed release-CLI database "
                "cases; ZIP archive/cache boundaries and engine-only cache "
                "controls remain in separate Linux harness evidence"
            ),
            (
                "Windows ACL/permission-denied databases and unreadable input "
                "are not represented by this ordinary-user fixture"
            ),
            (
                "raw stream hashes remain authoritative observations; the "
                "named path/line-ending normalization is an additional "
                "cross-platform comparison, not a replacement"
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
