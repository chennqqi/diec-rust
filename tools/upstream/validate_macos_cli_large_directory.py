#!/usr/bin/env python3
"""Validate a non-admitted macOS Qt5 large-directory CLI candidate."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import sys
from pathlib import Path, PurePosixPath
from typing import Any


PLATFORM = "macos-x86_64-qt5"
COLLECTOR = "tools/upstream/collect_macos_cli_large_directory.py"
BASELINE_COLLECTOR = "tools/upstream/collect_macos_cli_baseline.py"
BASELINE_VALIDATOR = "tools/upstream/validate_macos_cli_baseline.py"
ORACLE_VALIDATOR = "tools/upstream/validate_macos_qt5_oracle_report.py"


class ReportError(ValueError):
    """The large-directory candidate is incomplete or inconsistent."""


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


def validate_report(
    report: dict[str, Any],
    *,
    report_path: Path,
    oracle_path: Path,
    baseline_path: Path,
    root: Path,
) -> None:
    bundle = report_path.parent
    if report_path != (
        bundle / "cli-large-directory-candidate.json"
    ).resolve(strict=True):
        raise ReportError(
            "report must be bundle-local: "
            "cli-large-directory-candidate.json"
        )
    for path, name in (
        (oracle_path, "oracle-candidate.json"),
        (baseline_path, "cli-baseline-candidate.json"),
    ):
        if path != (bundle / name).resolve(strict=True):
            raise ReportError(f"input report must be bundle-local: {name}")
    expected_root = {
        "schema_version",
        "result",
        "platform",
        "generator",
        "oracle_report",
        "cli_baseline_report",
        "source",
        "qt",
        "binary",
        "fixture",
        "linux_qt5_reference",
        "local_paths",
        "selection",
        "cases",
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
        "macos_cli_large_directory_collector_validation",
    )
    baseline_collector = _load(
        root,
        BASELINE_COLLECTOR,
        "macos_baseline_collector_large_directory_validation",
    )
    baseline_validator = _load(
        root,
        BASELINE_VALIDATOR,
        "macos_baseline_validator_large_directory_validation",
    )
    oracle_validator = _load(
        root,
        ORACLE_VALIDATOR,
        "macos_oracle_validator_large_directory_validation",
    )
    materializer = _load(
        root,
        collector.FIXTURE_MATERIALIZER,
        "large_path_materializer_macos_validation",
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
    baseline_report = baseline_validator.load_json(baseline_path)[0]
    baseline_validator.validate_report(
        baseline_report,
        report_path=baseline_path,
        oracle_path=oracle_path,
        root=root,
    )
    if report["cli_baseline_report"] != {
        "path": "cli-baseline-candidate.json",
        "sha256": sha256(baseline_path.read_bytes()),
    }:
        raise ReportError("CLI baseline binding drift")
    if report["source"] != baseline_report["source"]:
        raise ReportError("source identity drift")
    if report["qt"] != baseline_report["qt"]:
        raise ReportError("Qt identity drift")
    if report["binary"] != baseline_report["binary"]:
        raise ReportError("binary identity drift")

    manifest, manifest_raw = materializer.load_manifest(
        root, root / collector.FIXTURE_MANIFEST
    )
    expected_preflight = {
        case["name"]: materializer.preflight(case)
        for case in manifest["cases"]
    }
    expected_fixture = {
        "manifest": collector.FIXTURE_MANIFEST,
        "manifest_sha256": sha256(manifest_raw),
        "materializer": collector.FIXTURE_MATERIALIZER,
        "case_count": len(manifest["cases"]),
        "planned_file_count": sum(
            case["file_count"] for case in manifest["cases"]
        ),
        "live_preflight": expected_preflight,
    }
    if report["fixture"] != expected_fixture:
        raise ReportError("large-directory fixture binding drift")
    linux_reference, linux_raw = baseline_validator.load_json(
        root / collector.LINUX_REFERENCE
    )
    if report["linux_qt5_reference"] != {
        "path": collector.LINUX_REFERENCE,
        "sha256": sha256(linux_raw),
    }:
        raise ReportError("Linux reference binding drift")

    local_paths = require_object(report["local_paths"], "local_paths")
    if set(local_paths) != {"fixture_dir"}:
        raise ReportError("local path fields changed")
    fixture_text = local_paths["fixture_dir"]
    if (
        not isinstance(fixture_text, str)
        or not PurePosixPath(fixture_text).is_absolute()
        or "\\" in fixture_text
    ):
        raise ReportError("fixture local path is not absolute POSIX")
    fixture_dir = PurePosixPath(fixture_text)
    names = [case["name"] for case in manifest["cases"]]
    if report["selection"] != {
        "case_names": names,
        "minimum_repetitions_per_case": 2,
    }:
        raise ReportError("large-directory case selection drift")
    cases = require_object(report["cases"], "cases")
    if set(cases) != set(names):
        raise ReportError("large-directory case inventory drift")

    report_db = collector.database_arguments(
        Path("<source>"), report=True
    )
    declared_raw: set[str] = set()
    determinism_failures = []
    timeout_cases = []
    linux_semantic_failures = []
    name_order_failures = []
    for case in manifest["cases"]:
        name = case["name"]
        entry = require_object(cases[name], f"case {name}")
        if entry.get("arguments") != [
            "--entropy",
            "--json",
            *report_db,
            f"<fixture>/{name}",
        ]:
            raise ReportError(f"case arguments drift: {name}")
        timeout = entry.get("timeout_seconds")
        if not isinstance(timeout, int) or not 1 <= timeout <= 60:
            raise ReportError(f"case timeout drift: {name}")
        try:
            first, second = baseline_validator.validate_pair(
                entry,
                bundle,
                f"large-directory case {name}",
                f"cli-large-directory/{name}",
            )
        except baseline_validator.ReportError as error:
            raise ReportError(str(error)) from error
        for side in ("first", "second"):
            raw = require_object(entry[side], f"{name}.{side}")
            declared_raw.update(
                {raw["stdout_path"], raw["stderr_path"]}
            )
        first_timeout = entry.get("first_timed_out")
        second_timeout = entry.get("second_timed_out")
        if not isinstance(first_timeout, bool) or not isinstance(
            second_timeout, bool
        ):
            raise ReportError(f"timeout flag drift: {name}")
        if (first_timeout and first[0] != 124) or (
            second_timeout and second[0] != 124
        ):
            raise ReportError(f"timeout exit drift: {name}")

        case_dir = fixture_dir / name
        first_prefixes = collector.prefix_relatives(
            first[1], case_dir
        )
        second_prefixes = collector.prefix_relatives(
            second[1], case_dir
        )
        expected = collector.expected_prefixes(materializer, case)
        first_documents = collector.entropy_document_count(first[1])
        second_documents = collector.entropy_document_count(second[1])
        projection = collector.linux_projection(
            linux_reference, name
        )
        linux_equal = (
            first[0] == projection["exit_code"]
            and first[2] == b""
            and first_documents
            == projection["entropy_document_count"]
            and len(first_prefixes) == projection["prefix_count"]
        )
        name_order_equal = first_prefixes == expected
        expected_fields = {
            "first_entropy_document_count": first_documents,
            "second_entropy_document_count": second_documents,
            "first_prefix_count": len(first_prefixes),
            "second_prefix_count": len(second_prefixes),
            "first_prefix": (
                first_prefixes[0] if first_prefixes else None
            ),
            "last_prefix": (
                first_prefixes[-1] if first_prefixes else None
            ),
            "first_prefixes_sha256": collector.sequence_sha256(
                first_prefixes
            ),
            "second_prefixes_sha256": collector.sequence_sha256(
                second_prefixes
            ),
            "expected_name_order_sha256": collector.sequence_sha256(
                expected
            ),
            "complete_name_order_equal": name_order_equal,
            "linux_qt5_projection": projection,
            "linux_qt5_semantic_equal": linux_equal,
        }
        for field, expected_value in expected_fields.items():
            if entry.get(field) != expected_value:
                raise ReportError(
                    f"large-directory projection drift: {name}.{field}"
                )
        if entry["determinism_differences"] or (
            first_timeout != second_timeout
        ):
            determinism_failures.append(name)
        if first_timeout or second_timeout:
            timeout_cases.append(name)
        if not linux_equal:
            linux_semantic_failures.append(name)
        if not name_order_equal:
            name_order_failures.append(name)

    count = len(manifest["cases"])
    expected_summary = {
        "case_count": count,
        "execution_count": 2 * count,
        "raw_stream_count": 4 * count,
        "determinism_failures": determinism_failures,
        "timeout_cases": timeout_cases,
        "linux_semantic_failures": linux_semantic_failures,
        "name_order_failures": name_order_failures,
        "deterministic": not determinism_failures,
        "linux_semantics_equal": not linux_semantic_failures,
        "complete_name_order_equal": not name_order_failures,
    }
    if report["summary"] != expected_summary:
        raise ReportError("large-directory summary drift")
    if report["admission"] != {
        "platform_admitted": False,
        "capability_rows_admitted": 0,
        "reason": collector.ADMISSION_REASON,
    }:
        raise ReportError("candidate must not admit capability evidence")
    if report["limitations"] != collector.LIMITATIONS:
        raise ReportError("large-directory limitations drift")
    raw_root = bundle / "raw" / "cli-large-directory"
    actual_raw = {
        path.relative_to(bundle).as_posix()
        for path in raw_root.rglob("*")
        if path.is_file()
    }
    if actual_raw != declared_raw:
        raise ReportError(
            "large-directory raw file inventory differs from report"
        )


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--oracle-report", type=Path, required=True)
    parser.add_argument("--cli-baseline-report", type=Path, required=True)
    parser.set_defaults(root=root)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report_path = args.report.resolve(strict=True)
        oracle_path = args.oracle_report.resolve(strict=True)
        baseline_path = args.cli_baseline_report.resolve(strict=True)
        baseline_validator = _load(
            args.root.resolve(),
            BASELINE_VALIDATOR,
            "macos_baseline_validator_large_directory_entry",
        )
        report = baseline_validator.load_json(report_path)[0]
        validate_report(
            report,
            report_path=report_path,
            oracle_path=oracle_path,
            baseline_path=baseline_path,
            root=args.root.resolve(),
        )
    except (ReportError, OSError, ValueError) as error:
        print(
            f"macOS CLI large-directory report error: {error}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
