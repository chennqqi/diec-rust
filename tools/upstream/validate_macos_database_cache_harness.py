#!/usr/bin/env python3
"""Validate a non-admitted macOS Qt5 database-cache engine candidate."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
from pathlib import Path, PurePosixPath
import sys
from typing import Any


PLATFORM = "macos-x86_64-qt5"
COLLECTOR = (
    "tools/upstream/collect_macos_database_cache_harness.py"
)
BASELINE_VALIDATOR = "tools/upstream/validate_macos_cli_baseline.py"


class ReportError(ValueError):
    """The database-cache candidate is incomplete or inconsistent."""


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _load(root: Path, relative: str, name: str) -> Any:
    path = root / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ReportError(f"cannot load helper module: {relative}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def require_object(value: Any, description: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReportError(f"{description} must be an object")
    return value


def validate_report(
    report: dict[str, Any],
    *,
    report_path: Path,
    oracle_path: Path,
    build_report_path: Path,
    binary_path: Path,
    root: Path,
) -> None:
    bundle = report_path.parent
    collector = _load(
        root, COLLECTOR, "macos_database_cache_collector_validation"
    )
    build_validator = _load(
        root,
        collector.BUILD_VALIDATOR,
        "macos_cache_build_validator_for_cache_validation",
    )
    if report_path != (
        bundle / collector.REPORT_NAME
    ).resolve(strict=True):
        raise ReportError(
            f"report must be bundle-local: {collector.REPORT_NAME}"
        )
    expected_inputs = (
        (oracle_path, "oracle-candidate.json"),
        (
            build_report_path,
            "database-cache-harness-build-candidate.json",
        ),
        (
            binary_path,
            "database-cache-harness-candidate",
        ),
    )
    for path, name in expected_inputs:
        if path != (bundle / name).resolve(strict=True):
            raise ReportError(f"input must be bundle-local: {name}")
    if set(report) != {
        "schema_version",
        "result",
        "platform",
        "generator",
        "oracle_report",
        "build_report",
        "source",
        "qt",
        "binary",
        "fixture",
        "linux_qt5_reference",
        "local_paths",
        "selection",
        "run",
        "observation",
        "relationships",
        "linux_qt5_comparison",
        "summary",
        "normalization",
        "admission",
        "limitations",
    }:
        raise ReportError("report root fields changed")
    if (
        report["schema_version"] != 1
        or report["result"] != "candidate"
        or report["platform"] != PLATFORM
    ):
        raise ReportError("report identity drift")
    if report["generator"] != collector.generator_bindings(root):
        raise ReportError("generator identity drift")

    build_report, build_raw = build_validator.load_json(
        build_report_path
    )
    build_validator.validate_report(
        build_report,
        report_path=build_report_path,
        oracle_path=oracle_path,
        artifact_path=binary_path,
        root=root,
    )
    if report["oracle_report"] != {
        "path": "oracle-candidate.json",
        "sha256": sha256(oracle_path.read_bytes()),
    }:
        raise ReportError("oracle report binding drift")
    if report["build_report"] != {
        "path": build_report_path.name,
        "sha256": sha256(build_raw),
    }:
        raise ReportError("build report binding drift")
    for field in ("source", "qt"):
        if report[field] != build_report[field]:
            raise ReportError(f"{field} identity drift")
    if report["binary"] != build_report["artifact"]:
        raise ReportError("harness binary identity drift")

    fixture_raw = (root / collector.FIXTURE_MANIFEST).read_bytes()
    if report["fixture"] != {
        "manifest": collector.FIXTURE_MANIFEST,
        "sha256": sha256(fixture_raw),
    }:
        raise ReportError("database fixture binding drift")
    baseline_validator = _load(
        root,
        BASELINE_VALIDATOR,
        "macos_baseline_validator_for_cache_validation",
    )
    linux, linux_raw = baseline_validator.load_json(
        root / collector.LINUX_REFERENCE
    )
    if report["linux_qt5_reference"] != {
        "path": collector.LINUX_REFERENCE,
        "sha256": sha256(linux_raw),
    }:
        raise ReportError("Linux reference binding drift")
    windows = _load(
        root,
        collector.WINDOWS_COLLECTOR,
        "windows_cache_helper_for_macos_validation",
    )
    linux_observation = windows.validate_linux_reference(
        linux, sha256(fixture_raw)
    )
    linux_probe = _load(
        root,
        collector.LINUX_PROBE,
        "linux_cache_probe_for_macos_validation",
    )

    local_paths = require_object(report["local_paths"], "local_paths")
    if set(local_paths) != {"working_dir", "home_dir"}:
        raise ReportError("local path fields changed")
    parsed_paths = {}
    for field, value in local_paths.items():
        if (
            not isinstance(value, str)
            or not PurePosixPath(value).is_absolute()
            or "\\" in value
        ):
            raise ReportError(f"local_paths.{field} is not POSIX")
        parsed_paths[field] = PurePosixPath(value)
    if parsed_paths["home_dir"] != (
        parsed_paths["working_dir"] / "home"
    ):
        raise ReportError("collector HOME path drift")

    selection = require_object(report["selection"], "selection")
    timeout = selection.get("timeout_seconds")
    if not isinstance(timeout, int) or not 1 <= timeout <= 3600:
        raise ReportError("cache harness timeout drift")
    if selection != {
        "case_ids": list(linux_probe.EXPECTED_CASE_IDS),
        "repetitions": 2,
        "timeout_seconds": timeout,
    }:
        raise ReportError("cache harness selection drift")

    try:
        first, second = baseline_validator.validate_pair(
            report["run"],
            bundle,
            "database-cache engine harness",
            "database-cache-engine/harness",
        )
    except baseline_validator.ReportError as error:
        raise ReportError(str(error)) from error
    parsed = []
    for side, raw in (("first", first), ("second", second)):
        if raw[0] != 0 or raw[2] != b"":
            raise ReportError(f"{side} harness process result drift")
        try:
            parsed.append(collector.strict_json(raw[1]))
        except collector.HarnessError as error:
            raise ReportError(str(error)) from error
    normalized = []
    for value in parsed:
        try:
            normalized.append(
                collector.normalize_observation(
                    value,
                    home_dir=parsed_paths["home_dir"],
                    linux_probe=linux_probe,
                )
            )
        except collector.HarnessError as error:
            raise ReportError(str(error)) from error
    if report["observation"] != normalized[0]:
        raise ReportError("normalized observation drift")
    relationships = linux_probe.derive_relationships(normalized[0])
    relationships["harness_runs_without_root_privileges"] = (
        normalized[0].get("effective_uid") != 0
    )
    if report["relationships"] != relationships:
        raise ReportError("relationship projection drift")
    projection_differences, size_deltas = (
        collector.compare_linux_cases(
            normalized[0],
            linux_observation,
            linux_probe=linux_probe,
        )
    )
    expected_comparison = {
        "case_projection_differences": projection_differences,
        "cache_size_deltas": size_deltas,
    }
    if report["linux_qt5_comparison"] != expected_comparison:
        raise ReportError("Linux comparison projection drift")
    differences = report["run"]["determinism_differences"]
    expected_summary = {
        "case_count": len(linux_probe.EXPECTED_CASE_IDS),
        "execution_count": 2,
        "raw_stream_count": 4,
        "raw_determinism_failures": differences,
        "normalized_outputs_equal": normalized[0] == normalized[1],
        "relationship_failures": [
            name for name, value in relationships.items() if not value
        ],
        "linux_case_projection_differences": (
            projection_differences
        ),
    }
    if report["summary"] != expected_summary:
        raise ReportError("database-cache summary drift")
    if report["normalization"] != collector.NORMALIZATION:
        raise ReportError("database-cache normalization drift")
    if report["admission"] != {
        "platform_admitted": False,
        "capability_rows_admitted": 0,
        "reason": collector.ADMISSION_REASON,
    }:
        raise ReportError("candidate must not admit capability evidence")
    if report["limitations"] != collector.LIMITATIONS:
        raise ReportError("database-cache limitations drift")
    declared_raw = {
        report["run"][side][f"{stream}_path"]
        for side in ("first", "second")
        for stream in ("stdout", "stderr")
    }
    raw_root = bundle / "raw" / "database-cache-engine"
    actual_raw = {
        path.relative_to(bundle).as_posix()
        for path in raw_root.rglob("*")
        if path.is_file()
    }
    if actual_raw != declared_raw:
        raise ReportError(
            "database-cache raw file inventory differs from report"
        )


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--oracle-report", type=Path, required=True)
    parser.add_argument("--build-report", type=Path, required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.set_defaults(root=root)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report_path = args.report.resolve(strict=True)
        oracle_path = args.oracle_report.resolve(strict=True)
        build_report_path = args.build_report.resolve(strict=True)
        binary_path = args.binary.resolve(strict=True)
        build_validator = _load(
            args.root.resolve(),
            (
                "tools/upstream/"
                "validate_macos_database_cache_harness_build.py"
            ),
            "macos_cache_build_validator_for_cache_entry",
        )
        report = build_validator.load_json(report_path)[0]
        validate_report(
            report,
            report_path=report_path,
            oracle_path=oracle_path,
            build_report_path=build_report_path,
            binary_path=binary_path,
            root=args.root.resolve(),
        )
    except (ReportError, OSError, ValueError) as error:
        print(
            f"macOS database-cache report error: {error}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
