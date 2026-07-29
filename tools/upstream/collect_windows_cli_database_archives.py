#!/usr/bin/env python3
"""Collect native-Windows Qt5 ZIP-database CLI behavior."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
WINDOWS_DATABASE_SCRIPT = (
    ROOT / "tools/upstream/collect_windows_cli_database.py"
)
ARCHIVE_DEFINITIONS_SCRIPT = (
    ROOT / "tools/upstream/probe_database_archives.py"
)
FIXTURE_GENERATOR = (
    ROOT / "tools/corpus/generate_database_fixture.py"
)


def load_helper(name: str, path: Path) -> object:
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load helper module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


windows_database = load_helper(
    "collect_windows_cli_database_archive_helper",
    WINDOWS_DATABASE_SCRIPT,
)
# probe_database_archives imports this helper by its ordinary module name.
sys.modules.setdefault(
    "compare_cli_oracles",
    windows_database.matrix_definitions,
)
archive_definitions = load_helper(
    "probe_database_archives_windows_definitions",
    ARCHIVE_DEFINITIONS_SCRIPT,
)
baseline = windows_database.baseline
MatrixError = windows_database.MatrixError


def validate_linux_reference(
    reference: dict[str, object],
    fixture_manifest_sha256: str,
) -> dict[str, object]:
    expected_header = {
        "schema_version": 1,
        "generator": "tools/upstream/probe_database_archives.py",
        "generator_sha256": baseline.sha256_file(
            ARCHIVE_DEFINITIONS_SCRIPT
        ),
        "shared_helper": "tools/upstream/compare_cli_oracles.py",
        "shared_helper_sha256": baseline.sha256_file(
            windows_database.MATRIX_SCRIPT
        ),
        "fixture_generator_sha256": baseline.sha256_file(
            FIXTURE_GENERATOR
        ),
        "expected_revision": baseline.UPSTREAM_COMMIT,
        "left_revision": baseline.UPSTREAM_COMMIT,
        "right_revision": baseline.UPSTREAM_COMMIT,
        "equal": True,
        "failures": [],
    }
    for key, expected in expected_header.items():
        if reference.get(key) != expected:
            raise MatrixError(
                f"Linux archive reference {key!r} differs from expected"
            )

    fixture = reference.get("database_fixture")
    if not isinstance(fixture, dict):
        raise MatrixError("Linux archive reference has no fixture")
    if fixture.get("manifest_sha256") != fixture_manifest_sha256:
        raise MatrixError("Linux archive reference fixture hash differs")
    cases = fixture.get("cases")
    expected_cases = {
        case.name for case in archive_definitions.ARCHIVE_CASES
    }
    if not isinstance(cases, dict) or set(cases) != expected_cases:
        raise MatrixError("Linux archive reference case set differs")
    for name, case in cases.items():
        if not isinstance(case, dict):
            raise MatrixError(f"Linux archive case is invalid: {name}")
        if case.get("differences") != []:
            raise MatrixError(f"Linux archive case is not equal: {name}")
        if case.get("left") != case.get("right"):
            raise MatrixError(
                f"Linux archive raw summaries differ: {name}"
            )
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
        default=(
            ROOT
            / "docs/research/data/database-archive-linux-qt5.json"
        ),
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
    fixture_manifest_sha256 = hashlib.sha256(
        fixture_manifest_raw
    ).hexdigest()
    fixture_manifest = (
        windows_database.matrix_definitions.load_database_fixture(
            fixture_dir
        )
    )

    linux_reference_path = args.linux_reference.resolve(strict=True)
    linux_reference, linux_reference_raw = windows_database.read_json(
        linux_reference_path
    )
    linux_cases = validate_linux_reference(
        linux_reference,
        fixture_manifest_sha256,
    )

    report_cases: dict[str, object] = {}
    determinism_failures: list[str] = []
    linux_exit_code_failures: list[str] = []
    linux_stderr_failures: list[str] = []
    linux_document_validity_failures: list[str] = []
    linux_normalized_stdout_failures: list[str] = []

    for case in archive_definitions.ARCHIVE_CASES:
        actual_arguments = windows_database.translate_arguments(
            case.arguments,
            source_dir,
            fixture_dir,
            report=False,
        )
        report_arguments = windows_database.translate_arguments(
            case.arguments,
            source_dir,
            fixture_dir,
            report=True,
        )
        first, second, paired = windows_database.collect_pair(
            binary,
            qt_dir,
            actual_arguments,
            timeout_seconds=args.timeout_seconds,
        )
        linux_case = linux_cases[case.name]
        linux_summary = linux_case["left"]
        normalized_stdout = (
            windows_database.normalize_windows_stdout_for_linux(
                first.stdout,
                actual_arguments,
                case.arguments,
            )
        )
        normalized_stdout_sha256 = hashlib.sha256(
            normalized_stdout
        ).hexdigest()
        normalized_stdout_equal = (
            normalized_stdout_sha256
            == linux_summary["stdout_sha256"]
        )
        stderr_equal = (
            first.summary()["stderr_sha256"]
            == linux_summary["stderr_sha256"]
        )
        paired.update(
            {
                "arguments": list(report_arguments),
                "reports_parse_error": (
                    b"SyntaxError: Parse error" in first.stdout
                ),
                "linux_qt5_raw_differences": (
                    windows_database.raw_differences(
                        first.summary(),
                        linux_summary,
                    )
                ),
                "linux_normalized_stdout_sha256": (
                    normalized_stdout_sha256
                ),
                "linux_qt5_normalized_stdout_equal": (
                    normalized_stdout_equal
                ),
                "linux_qt5_stderr_equal": stderr_equal,
            }
        )
        if case.name.endswith("_json"):
            first_valid_json = (
                windows_database.matrix_definitions.document_is_valid(
                    first.stdout,
                    "json",
                )
            )
            second_valid_json = (
                windows_database.matrix_definitions.document_is_valid(
                    second.stdout,
                    "json",
                )
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
        if first.exit_code != linux_summary["exit_code"]:
            linux_exit_code_failures.append(case.name)
        if not stderr_equal:
            linux_stderr_failures.append(case.name)
        if not normalized_stdout_equal:
            linux_normalized_stdout_failures.append(case.name)

    case_count = len(archive_definitions.ARCHIVE_CASES)
    failures = (
        determinism_failures
        + linux_exit_code_failures
        + linux_stderr_failures
        + linux_document_validity_failures
        + linux_normalized_stdout_failures
    )
    report = {
        "schema_version": 1,
        "generator": (
            "tools/upstream/collect_windows_cli_database_archives.py"
        ),
        "generator_sha256": baseline.sha256_file(Path(__file__)),
        "windows_database_helper": {
            "path": "tools/upstream/collect_windows_cli_database.py",
            "sha256": baseline.sha256_file(WINDOWS_DATABASE_SCRIPT),
        },
        "archive_definitions": {
            "path": "tools/upstream/probe_database_archives.py",
            "sha256": baseline.sha256_file(
                ARCHIVE_DEFINITIONS_SCRIPT
            ),
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
            "sha256": fixture_manifest_sha256,
            "directories": fixture_manifest["directories"],
            "entries": fixture_manifest["entries"],
        },
        "linux_qt5_reference": {
            "path": (
                "docs/research/data/database-archive-linux-qt5.json"
            ),
            "sha256": hashlib.sha256(linux_reference_raw).hexdigest(),
        },
        "cases": report_cases,
        "summary": {
            "case_count": case_count,
            "execution_count": 2 * case_count,
            "determinism_failures": determinism_failures,
            "linux_exit_code_failures": linux_exit_code_failures,
            "linux_stderr_failures": linux_stderr_failures,
            "linux_document_validity_failures": (
                linux_document_validity_failures
            ),
            "linux_normalized_stdout_failures": (
                linux_normalized_stdout_failures
            ),
            "deterministic": not determinism_failures,
            "linux_exit_codes_equal": not linux_exit_code_failures,
            "linux_stderr_equal": not linux_stderr_failures,
            "linux_document_validity_equal": (
                not linux_document_validity_failures
            ),
            "linux_normalized_stdout_equal": (
                not linux_normalized_stdout_failures
            ),
        },
        "normalization": {
            "purpose": (
                "compare native Windows output to committed Linux Qt5 "
                "stdout hashes after only named platform transformations"
            ),
            "operations": [
                (
                    "replace each actual Windows path argument with the "
                    "exact corresponding original Linux archive argument"
                ),
                "replace CRLF with LF",
            ],
            "not_performed": [
                "JSON parsing or reserialization",
                "ZIP entry-name rewriting",
                "diagnostic removal or rewriting",
                "record sorting",
                "whitespace changes other than CRLF line endings",
            ],
        },
        "limitations": [
            (
                "this report covers release-CLI ZIP database loading; "
                "engine bUseCache controls are not exposed by the CLI"
            ),
            (
                "Windows ACL/permission-denied cache behavior requires a "
                "separate native engine harness"
            ),
            (
                "raw stream hashes remain authoritative observations; "
                "the named normalization is an additional comparison"
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
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
