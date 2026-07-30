#!/usr/bin/env python3
"""Validate a non-admitted macOS Qt5 enumeration/open TOCTOU candidate."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import sys
from typing import Any


PLATFORM = "macos-x86_64-qt5"
COLLECTOR = "tools/upstream/collect_macos_cli_toctou.py"
BASELINE_COLLECTOR = "tools/upstream/collect_macos_cli_baseline.py"
BASELINE_VALIDATOR = "tools/upstream/validate_macos_cli_baseline.py"
ORACLE_VALIDATOR = "tools/upstream/validate_macos_qt5_oracle_report.py"
DARWIN_SIGSTOP = 17
DARWIN_SIGCONT = 19


class ReportError(ValueError):
    """The TOCTOU candidate is incomplete or inconsistent."""


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


def _identity(value: Any, description: str) -> None:
    identity = require_object(value, description)
    if set(identity) != {"device", "inode", "mode", "size"}:
        raise ReportError(f"{description} fields changed")
    if any(
        not isinstance(identity[field], int) or identity[field] < 0
        for field in identity
    ):
        raise ReportError(f"{description} values are invalid")


def _state(value: Any, description: str) -> dict[str, Any]:
    state = require_object(value, description)
    if set(state) != {
        "link_identity",
        "link_target",
        "target_identity",
    }:
        raise ReportError(f"{description} fields changed")
    for field in ("link_identity", "target_identity"):
        if state[field] is not None:
            _identity(state[field], f"{description}.{field}")
    if state["link_target"] is not None and not isinstance(
        state["link_target"], str
    ):
        raise ReportError(f"{description}.link_target is invalid")
    return state


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
        bundle / "cli-toctou-candidate.json"
    ).resolve(strict=True):
        raise ReportError(
            "report must be bundle-local: cli-toctou-candidate.json"
        )
    for path, name in (
        (oracle_path, "oracle-candidate.json"),
        (baseline_path, "cli-baseline-candidate.json"),
    ):
        if path != (bundle / name).resolve(strict=True):
            raise ReportError(f"input report must be bundle-local: {name}")
    if set(report) != {
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
    }:
        raise ReportError("report root fields changed")
    if (
        report["schema_version"] != 1
        or report["result"] != "candidate"
        or report["platform"] != PLATFORM
    ):
        raise ReportError("report identity drift")

    collector = _load(
        root, COLLECTOR, "macos_cli_toctou_collector_validation"
    )
    baseline_validator = _load(
        root,
        BASELINE_VALIDATOR,
        "macos_baseline_validator_toctou_validation",
    )
    oracle_validator = _load(
        root,
        ORACLE_VALIDATOR,
        "macos_oracle_validator_toctou_validation",
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
    baseline, baseline_raw = baseline_validator.load_json(baseline_path)
    baseline_validator.validate_report(
        baseline,
        report_path=baseline_path,
        oracle_path=oracle_path,
        root=root,
    )
    if report["cli_baseline_report"] != {
        "path": "cli-baseline-candidate.json",
        "sha256": sha256(baseline_raw),
    }:
        raise ReportError("CLI baseline binding drift")
    for field in ("source", "qt", "binary"):
        if report[field] != baseline[field]:
            raise ReportError(f"{field} identity drift")

    manifest, manifest_raw = baseline_validator.load_json(
        root / collector.FIXTURE_MANIFEST
    )
    cases_manifest = manifest.get("cases")
    if not isinstance(cases_manifest, list) or len(cases_manifest) != 4:
        raise ReportError("TOCTOU fixture case inventory changed")
    materialization = require_object(
        manifest.get("materialization"), "fixture materialization"
    )
    expected_preflight = {
        "blocker_size": materialization["blocker"]["size"],
        "blocker_sha256": materialization["blocker"]["sha256"],
        "old_size": materialization["old_target"]["size"],
        "old_sha256": materialization["old_target"]["sha256"],
        "new_size": materialization["new_target"]["size"],
        "new_sha256": materialization["new_target"]["sha256"],
    }
    if report["fixture"] != {
        "manifest": collector.FIXTURE_MANIFEST,
        "manifest_sha256": sha256(manifest_raw),
        "case_count": len(cases_manifest),
        "live_preflight": expected_preflight,
    }:
        raise ReportError("TOCTOU fixture binding drift")
    linux, linux_raw = baseline_validator.load_json(
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
    names = [case["name"] for case in cases_manifest]
    if report["selection"] != {
        "case_names": names,
        "minimum_repetitions_per_case": 2,
    }:
        raise ReportError("TOCTOU case selection drift")
    cases = require_object(report["cases"], "cases")
    if set(cases) != set(names):
        raise ReportError("TOCTOU case inventory drift")

    report_db = collector.database_arguments(
        Path("<source>"), report=True
    )
    declared_raw: set[str] = set()
    determinism_failures = []
    synchronization_failures = []
    transition_failures = []
    linux_semantic_failures = []
    for case in cases_manifest:
        name = case["name"]
        entry = require_object(cases[name], f"case {name}")
        if entry.get("arguments") != [
            "--entropy",
            "--json",
            *report_db,
            "<fixture>/case",
        ]:
            raise ReportError(f"case arguments drift: {name}")
        timeout = entry.get("timeout_seconds")
        if not isinstance(timeout, int) or not 1 <= timeout <= 60:
            raise ReportError(f"case timeout drift: {name}")
        for field in (
            "initial_target",
            "action",
            "expected_open_target",
        ):
            if entry.get(field) != case[field]:
                raise ReportError(f"fixture projection drift: {name}.{field}")
        try:
            first, second = baseline_validator.validate_pair(
                entry,
                bundle,
                f"TOCTOU case {name}",
                f"cli-toctou/{name}",
            )
        except baseline_validator.ReportError as error:
            raise ReportError(str(error)) from error
        for side in ("first", "second"):
            raw = require_object(entry[side], f"{name}.{side}")
            declared_raw.update(
                {raw["stdout_path"], raw["stderr_path"]}
            )

        parsed = [
            collector.parse_documents(raw[1], Path(str(fixture_dir / "case")))
            for raw in (first, second)
        ]
        if entry.get("first_documents") != parsed[0]:
            raise ReportError(f"first document projection drift: {name}")
        if entry.get("second_documents") != parsed[1]:
            raise ReportError(f"second document projection drift: {name}")

        attempts = require_object(entry.get("attempts"), f"{name}.attempts")
        if set(attempts) != {"first", "second"}:
            raise ReportError(f"attempt inventory drift: {name}")
        transitions_valid = True
        sync_valid = True
        expected_line = str(fixture_dir / "case" / "a-blocker.bin") + ":"
        for side in ("first", "second"):
            attempt = require_object(
                attempts[side], f"{name}.attempts.{side}"
            )
            if set(attempt) != {"before", "after", "synchronization"}:
                raise ReportError(f"attempt fields changed: {name}.{side}")
            _state(attempt["before"], f"{name}.{side}.before")
            _state(attempt["after"], f"{name}.{side}.after")
            synchronization = require_object(
                attempt["synchronization"],
                f"{name}.{side}.synchronization",
            )
            expected_sync = {
                "transport": "pty-with-oPOST-disabled",
                "first_line": expected_line,
                "child_confirmed_stopped": True,
                "mutation_while_stopped": True,
                "second_prefix_seen_before_mutation": False,
                "stop_signal": DARWIN_SIGSTOP,
                "resume_signal": DARWIN_SIGCONT,
            }
            if synchronization != expected_sync:
                sync_valid = False
            if not collector._state_transition_valid(case, attempt):
                transitions_valid = False
        if entry.get("synchronization_valid") is not sync_valid:
            raise ReportError(f"synchronization projection drift: {name}")
        if entry.get("state_transitions_valid") is not transitions_valid:
            raise ReportError(f"state transition projection drift: {name}")

        linux_case = linux["cases"][name]
        projection = {
            "action": linux_case["action"],
            "expected_open_target": linux_case["expected_open_target"],
            "blocker_document": linux_case["blocker_document"],
            "link_document": linux_case["link_document"],
        }
        if entry.get("linux_qt5_projection") != projection:
            raise ReportError(f"Linux projection drift: {name}")
        linux_equal = all(
            raw[0] == 0
            and raw[2] == b""
            and documents
            == [
                projection["blocker_document"],
                projection["link_document"],
            ]
            for raw, documents in zip((first, second), parsed)
        )
        if entry.get("linux_qt5_semantic_equal") is not linux_equal:
            raise ReportError(f"Linux semantic projection drift: {name}")
        if entry["determinism_differences"]:
            determinism_failures.append(name)
        if not sync_valid:
            synchronization_failures.append(name)
        if not transitions_valid:
            transition_failures.append(name)
        if not linux_equal:
            linux_semantic_failures.append(name)

    count = len(cases_manifest)
    expected_summary = {
        "case_count": count,
        "execution_count": 2 * count,
        "raw_stream_count": 4 * count,
        "determinism_failures": determinism_failures,
        "synchronization_failures": synchronization_failures,
        "state_transition_failures": transition_failures,
        "linux_semantic_failures": linux_semantic_failures,
        "deterministic": not determinism_failures,
        "synchronization_valid": not synchronization_failures,
        "state_transitions_valid": not transition_failures,
        "linux_semantics_equal": not linux_semantic_failures,
    }
    if report["summary"] != expected_summary:
        raise ReportError("TOCTOU summary drift")
    if synchronization_failures or transition_failures:
        raise ReportError(
            "TOCTOU synchronization/state transition must fail closed"
        )
    if report["admission"] != {
        "platform_admitted": False,
        "capability_rows_admitted": 0,
        "reason": collector.ADMISSION_REASON,
    }:
        raise ReportError("candidate must not admit capability evidence")
    if report["limitations"] != collector.LIMITATIONS:
        raise ReportError("TOCTOU limitations drift")
    raw_root = bundle / "raw" / "cli-toctou"
    actual_raw = {
        path.relative_to(bundle).as_posix()
        for path in raw_root.rglob("*")
        if path.is_file()
    }
    if actual_raw != declared_raw:
        raise ReportError("TOCTOU raw file inventory differs from report")


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
            "macos_baseline_validator_toctou_entry",
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
        print(f"macOS CLI TOCTOU report error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
