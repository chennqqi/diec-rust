#!/usr/bin/env python3
"""Validate a non-admitted macOS Qt5 CLI filesystem-path candidate."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import sys
from pathlib import Path, PurePosixPath
from typing import Any


UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
PLATFORM = "macos-x86_64-qt5"
COLLECTOR = "tools/upstream/collect_macos_cli_filesystem.py"
BASELINE_COLLECTOR = "tools/upstream/collect_macos_cli_baseline.py"
BASELINE_VALIDATOR = "tools/upstream/validate_macos_cli_baseline.py"
ORACLE_VALIDATOR = "tools/upstream/validate_macos_qt5_oracle_report.py"


class ReportError(ValueError):
    """The filesystem-path candidate is incomplete or inconsistent."""


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
        bundle / "cli-filesystem-candidate.json"
    ).resolve(strict=True):
        raise ReportError(
            "report must be bundle-local: cli-filesystem-candidate.json"
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
        root, COLLECTOR, "macos_cli_filesystem_collector_validation"
    )
    baseline_collector = _load(
        root,
        BASELINE_COLLECTOR,
        "macos_cli_baseline_collector_filesystem_validation",
    )
    baseline_validator = _load(
        root,
        BASELINE_VALIDATOR,
        "macos_cli_baseline_validator_filesystem_validation",
    )
    oracle_validator = _load(
        root,
        ORACLE_VALIDATOR,
        "macos_oracle_validator_filesystem_validation",
    )
    common = baseline_collector.load_module(
        "windows_cli_common_filesystem_validation",
        root / baseline_collector.SHARED_COLLECTOR,
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

    manifest, manifest_raw = baseline_validator.load_json(
        root / collector.FIXTURE_MANIFEST
    )
    fixture = require_object(report["fixture"], "fixture")
    live = require_object(fixture.get("live_preflight"), "live_preflight")
    if fixture != {
        "manifest": collector.FIXTURE_MANIFEST,
        "manifest_sha256": sha256(manifest_raw),
        "archive_sha256": manifest["archive"]["sha256"],
        "archive_size": manifest["archive"]["size"],
        "entry_count": len(manifest["entries"]),
        "live_preflight": live,
    }:
        raise ReportError("filesystem fixture binding drift")
    if set(live) != {
        "effective_uid",
        "effective_gid",
        "denied_mode",
        "denied_read_execute_access",
        "deep_component_count",
        "symlink_targets",
    }:
        raise ReportError("live fixture preflight fields changed")
    if (
        not isinstance(live["effective_uid"], int)
        or live["effective_uid"] <= 0
        or not isinstance(live["effective_gid"], int)
        or live["effective_gid"] < 0
        or live["denied_mode"] != 0
        or live["denied_read_execute_access"] is not False
        or live["deep_component_count"] != 64
        or live["symlink_targets"]
        != {
            "file_link": "target.pdf",
            "directory_link": "dir-target",
            "dangling_link": "missing.pdf",
            "cycle_link": ".",
        }
    ):
        raise ReportError("live fixture preflight drift")

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

    expected_selection = {
        "case_names": [case.name for case in collector.CASES],
        "minimum_repetitions_per_case": 2,
    }
    if report["selection"] != expected_selection:
        raise ReportError("filesystem case selection drift")
    cases = require_object(report["cases"], "cases")
    if set(cases) != set(expected_selection["case_names"]):
        raise ReportError("filesystem case inventory drift")

    reference_tree = baseline_report["corpus"]["minimal.pdf"][
        "first_detect_tree"
    ]
    report_db = collector.database_arguments(
        Path("<source>"), report=True
    )
    declared_raw: set[str] = set()
    determinism_failures = []
    timeout_cases = []
    linux_semantic_failures = []
    reference_projection_failures = []
    for case in collector.CASES:
        entry = require_object(cases[case.name], f"case {case.name}")
        expected_arguments = [
            "--json",
            *report_db,
            f"<fixture>/{case.relative}",
        ]
        if entry.get("arguments") != expected_arguments:
            raise ReportError(f"case arguments drift: {case.name}")
        maximum_timeout = case.timeout_cap_seconds or 3600
        timeout = entry.get("timeout_seconds")
        if (
            not isinstance(timeout, int)
            or timeout < 1
            or timeout > maximum_timeout
        ):
            raise ReportError(f"case timeout drift: {case.name}")
        try:
            first, second = baseline_validator.validate_pair(
                entry,
                bundle,
                f"filesystem case {case.name}",
                f"cli-filesystem/{case.name}",
            )
        except baseline_validator.ReportError as error:
            raise ReportError(str(error)) from error
        for side in ("first", "second"):
            raw = require_object(entry[side], f"{case.name}.{side}")
            declared_raw.update(
                {raw["stdout_path"], raw["stderr_path"]}
            )
        first_timeout = entry.get("first_timed_out")
        second_timeout = entry.get("second_timed_out")
        if not isinstance(first_timeout, bool) or not isinstance(
            second_timeout, bool
        ):
            raise ReportError(f"timeout flag drift: {case.name}")
        if (first_timeout and first[0] != 124) or (
            second_timeout and second[0] != 124
        ):
            raise ReportError(f"timeout exit drift: {case.name}")
        first_summary = collector.stdout_summary(first[1])
        second_summary = collector.stdout_summary(second[1])
        first_tree = common.json_detect_tree(first[1])
        second_tree = common.json_detect_tree(second[1])
        linux_projection = collector._linux_projection(
            linux_reference, case.linux_case
        )
        linux_equal = (
            first[0] == linux_projection["exit_code"]
            and first_summary == linux_projection["stdout_summary"]
        )
        reference_equal = (
            first_tree == reference_tree
            if case.reference_tree_applies
            else None
        )
        expected_fields = {
            "first_stdout_summary": first_summary,
            "second_stdout_summary": second_summary,
            "first_prefix_paths": collector.prefix_paths(
                first[1], fixture_dir
            ),
            "second_prefix_paths": collector.prefix_paths(
                second[1], fixture_dir
            ),
            "first_detect_tree": first_tree,
            "second_detect_tree": second_tree,
            "reference_tree_applies": case.reference_tree_applies,
            "minimal_pdf_detect_tree_equal": reference_equal,
            "linux_case": case.linux_case,
            "linux_qt5_projection": linux_projection,
            "linux_qt5_semantic_equal": linux_equal,
        }
        for field, expected in expected_fields.items():
            if entry.get(field) != expected:
                raise ReportError(
                    f"filesystem projection drift: {case.name}.{field}"
                )
        if entry["determinism_differences"] or (
            first_timeout != second_timeout
        ):
            determinism_failures.append(case.name)
        if first_timeout or second_timeout:
            timeout_cases.append(case.name)
        if not linux_equal:
            linux_semantic_failures.append(case.name)
        if case.reference_tree_applies and not reference_equal:
            reference_projection_failures.append(case.name)

    count = len(collector.CASES)
    expected_summary = {
        "case_count": count,
        "execution_count": 2 * count,
        "raw_stream_count": 4 * count,
        "determinism_failures": determinism_failures,
        "timeout_cases": timeout_cases,
        "linux_semantic_failures": linux_semantic_failures,
        "reference_projection_failures": reference_projection_failures,
        "deterministic": not determinism_failures,
        "linux_semantics_equal": not linux_semantic_failures,
        "reference_projections_equal": (
            not reference_projection_failures
        ),
    }
    if report["summary"] != expected_summary:
        raise ReportError("filesystem summary drift")
    if report["admission"] != {
        "platform_admitted": False,
        "capability_rows_admitted": 0,
        "reason": collector.ADMISSION_REASON,
    }:
        raise ReportError("candidate must not admit capability evidence")
    if report["limitations"] != collector.LIMITATIONS:
        raise ReportError("filesystem limitations drift")
    raw_root = bundle / "raw" / "cli-filesystem"
    actual_raw = {
        path.relative_to(bundle).as_posix()
        for path in raw_root.rglob("*")
        if path.is_file()
    }
    if actual_raw != declared_raw:
        raise ReportError(
            "filesystem raw file inventory differs from report"
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
            "macos_cli_baseline_validator_filesystem_entry",
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
            f"macOS CLI filesystem report error: {error}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
