#!/usr/bin/env python3
"""Summarize comparable pinned upstream benchmark probe sessions."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import sys
from typing import Any


SCHEMA_VERSION = 1
SESSION_COUNT = 3
EXPECTED_REVISION = "74eaf505c250ab47e709024e9dc41657cd8f2254"
EXPECTED_IMAGE_ID = (
    "sha256:9f1d70a8d4513404cdc457074e00dec"
    "4a9b8a6f043a572ffc17465bbe699eb09"
)
EXPECTED_PLAN_SHA256 = (
    "f93672c9603db16050047095f15d5f5e"
    "a6d9d58663b4574ed901f819f0106e1a"
)
EXPECTED_CPU = "0"
CONTROL_ID = "upstream.qt-process-control.v1"
GENERATOR = (
    "tools/benchmark/summarize_upstream_benchmark_sessions.py"
)


class SummaryError(ValueError):
    """The repeated-session evidence is incomplete or incomparable."""


def reject_duplicate_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SummaryError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    raise SummaryError(f"non-finite JSON constant: {value}")


def parse_json(raw: bytes, description: str) -> dict[str, Any]:
    try:
        value = json.loads(
            raw,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SummaryError(
            f"invalid {description} JSON: {error}"
        ) from error
    if not isinstance(value, dict):
        raise SummaryError(f"{description} root must be an object")
    return value


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def serialize(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def load_probe_module() -> Any:
    path = Path(__file__).with_name("probe_upstream_benchmark.py")
    spec = importlib.util.spec_from_file_location(
        "probe_upstream_benchmark_for_session_summary",
        path,
    )
    if spec is None or spec.loader is None:
        raise SummaryError("cannot load upstream benchmark probe")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def repo_file(repo_root: Path, path: Path) -> tuple[Path, str]:
    root = repo_root.resolve(strict=True)
    resolved = path.resolve(strict=True)
    try:
        relative = resolved.relative_to(root).as_posix()
    except ValueError as error:
        raise SummaryError(
            f"session report is outside repository: {path}"
        ) from error
    current = root
    for part in Path(relative).parts:
        current /= part
        if current.is_symlink():
            raise SummaryError(
                f"session report path contains symlink: {relative}"
            )
    if not resolved.is_file():
        raise SummaryError(
            f"session report is not a file: {relative}"
        )
    return resolved, relative


def session_identity(
    repo_root: Path,
    path: Path,
    probe: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    resolved, relative = repo_file(repo_root, path)
    raw = resolved.read_bytes()
    report = parse_json(raw, relative)
    if report.get("passed") is not True:
        raise SummaryError(f"session did not pass: {relative}")
    if report.get("failures") != []:
        raise SummaryError(f"session has failures: {relative}")
    try:
        failures = probe.evaluate_report(report)
    except (KeyError, TypeError, ValueError) as error:
        raise SummaryError(
            f"session verifier crashed: {relative}: {error}"
        ) from error
    if failures:
        raise SummaryError(
            f"session verifier failed: {relative}: {failures}"
        )
    environment = report["environment"]
    if (
        report.get("baseline_scope")
        != "descriptive_upstream_only"
        or report.get("targets_frozen") is not False
        or report.get("plan_suite_sha256") != EXPECTED_PLAN_SHA256
        or environment["image_identity"]["id"] != EXPECTED_IMAGE_ID
        or environment["image_identity"]["revision"]
        != EXPECTED_REVISION
        or environment.get("cpu_affinity")
        != {
            "requested_cpuset_cpu": EXPECTED_CPU,
            "scope": "linux_vcpu",
        }
        or environment["cgroup"]["cpuset_effective"]
        != EXPECTED_CPU
    ):
        raise SummaryError(f"session identity mismatch: {relative}")
    return report, {
        "path": relative,
        "bytes": len(raw),
        "sha256": sha256(raw),
    }


def ratio(maximum: int, minimum: int) -> float:
    if minimum <= 0:
        raise SummaryError("session statistic must be positive")
    return maximum / minimum


def summarize_case(
    benchmark_id: str,
    reports: list[dict[str, Any]],
) -> dict[str, Any]:
    items = [
        report["case_reports"][benchmark_id]["report"]
        for report in reports
    ]
    medians = [
        item["summary"]["duration_ns"]["median"] for item in items
    ]
    p95s = [
        item["summary"]["duration_ns"]["p95_nearest_rank"]
        for item in items
    ]
    mads = [
        item["summary"]["duration_ns"]["mad"] for item in items
    ]
    rss_medians = [
        item["summary"]["peak_rss_bytes"]["median"]
        for item in items
    ]
    rss_maxima = [
        item["summary"]["peak_rss_bytes"]["max"]
        for item in items
    ]
    rss_samples = [
        item["summary"]["peak_rss_bytes"]["sample_count"]
        for item in items
    ]
    stdout_hashes = [
        item["summary"]["stdout_unique_sha256"] for item in items
    ]
    stderr_hashes = [
        item["summary"]["stderr_unique_sha256"] for item in items
    ]
    return {
        "session_duration_median_ns": medians,
        "session_duration_p95_nearest_rank_ns": p95s,
        "session_duration_mad_ns": mads,
        "duration_median_across_sessions_ns": int(
            statistics.median(medians)
        ),
        "duration_median_max_over_min": ratio(
            max(medians),
            min(medians),
        ),
        "duration_p95_max_over_min": ratio(
            max(p95s),
            min(p95s),
        ),
        "session_peak_rss_median_bytes": rss_medians,
        "session_peak_rss_max_bytes": rss_maxima,
        "session_peak_rss_sample_count": rss_samples,
        "peak_rss_median_max_over_min": ratio(
            max(rss_medians),
            min(rss_medians),
        ),
        "stdout_hashes_identical_across_sessions": (
            stdout_hashes[1:] == stdout_hashes[:-1]
        ),
        "stderr_hashes_identical_across_sessions": (
            stderr_hashes[1:] == stderr_hashes[:-1]
        ),
    }


def build_report(
    repo_root: Path,
    session_paths: list[Path],
) -> dict[str, Any]:
    if len(session_paths) != SESSION_COUNT:
        raise SummaryError(
            f"exactly {SESSION_COUNT} sessions are required"
        )
    probe = load_probe_module()
    loaded = [
        session_identity(repo_root, path, probe)
        for path in session_paths
    ]
    reports = [item[0] for item in loaded]
    identities = [item[1] for item in loaded]
    hashes = [item["sha256"] for item in identities]
    if len(set(hashes)) != SESSION_COUNT:
        raise SummaryError("session reports must have unique hashes")
    first = reports[0]
    for report in reports[1:]:
        if report["plan_suite"] != first["plan_suite"]:
            raise SummaryError("session plan suites differ")
        if report["environment"] != first["environment"]:
            raise SummaryError("session environments differ")
    case_ids = sorted(first["case_reports"])
    if any(sorted(report["case_reports"]) != case_ids for report in reports):
        raise SummaryError("session case sets differ")
    cases = {
        benchmark_id: summarize_case(benchmark_id, reports)
        for benchmark_id in case_ids
    }
    output_hashes_stable = all(
        case["stdout_hashes_identical_across_sessions"]
        and case["stderr_hashes_identical_across_sessions"]
        for case in cases.values()
    )
    product_rss_complete = all(
        all(
            count
            == reports[index]["case_reports"][benchmark_id][
                "report"
            ]["execution"]["measured_runs"]
            for index, count in enumerate(
                cases[benchmark_id][
                    "session_peak_rss_sample_count"
                ]
            )
        )
        for benchmark_id in case_ids
        if benchmark_id != CONTROL_ID
    )
    control_counts = cases[CONTROL_ID][
        "session_peak_rss_sample_count"
    ]
    control_measured = [
        report["case_reports"][CONTROL_ID]["report"][
            "execution"
        ]["measured_runs"]
        for report in reports
    ]
    control_partial_rss_preserved = all(
        3 <= count < measured
        for count, measured in zip(
            control_counts,
            control_measured,
            strict=True,
        )
    )
    relationships = {
        "all_sessions_pass_probe_verifier": True,
        "all_sessions_use_exact_image_plan_environment_and_cpuset": True,
        "session_reports_are_distinct": True,
        "case_sets_are_identical": True,
        "outputs_are_deterministic_across_sessions": (
            output_hashes_stable
        ),
        "all_product_cases_have_complete_rss_samples": (
            product_rss_complete
        ),
        "partial_control_rss_is_preserved_not_imputed": (
            control_partial_rss_preserved
        ),
        "targets_remain_unfrozen": all(
            report["targets_frozen"] is False for report in reports
        ),
    }
    if not all(relationships.values()):
        failed = sorted(
            name for name, value in relationships.items() if not value
        )
        raise SummaryError(
            f"session relationships failed: {failed}"
        )
    total_warmups = sum(
        wrapped["report"]["execution"]["warmup_runs"]
        for report in reports
        for wrapped in report["case_reports"].values()
    )
    total_measured = sum(
        wrapped["report"]["execution"]["measured_runs"]
        for report in reports
        for wrapped in report["case_reports"].values()
    )
    generator_raw = Path(__file__).read_bytes()
    return {
        "schema_version": SCHEMA_VERSION,
        "generator": GENERATOR,
        "generator_sha256": sha256(generator_raw),
        "upstream_commit": EXPECTED_REVISION,
        "baseline_scope": "descriptive_upstream_only",
        "targets_frozen": False,
        "session_count": SESSION_COUNT,
        "total_warmup_runs": total_warmups,
        "total_measured_runs": total_measured,
        "source_reports": identities,
        "fixed_environment": first["environment"],
        "plan_suite_sha256": EXPECTED_PLAN_SHA256,
        "cases": cases,
        "relationships": relationships,
        "scope": {
            "platform": "Linux x86_64 under Docker Desktop/WSL2",
            "cpu_affinity": "single Linux vCPU 0",
            "sessions_are_separate_probe_invocations": True,
            "sessions_are_same_host_and_consecutive": True,
            "physical_core_topology_proven": False,
            "cold_cache_controlled": False,
            "power_and_frequency_controlled": False,
            "long_horizon_variability_measured": False,
            "regression_thresholds_approved": False,
        },
        "limitations": [
            "the three sessions are consecutive invocations on one Docker Desktop/WSL2 host, not independent machines, reboots, days, or randomized implementation pairs",
            "cpuset.cpus.effective=0 proves a Linux vCPU constraint but not physical-core, SMT-sibling, power, frequency, or host-load control",
            "the plans declare warm cache and do not forcibly control the OS page cache",
            "the short process control retains partial RSS samples and is not product RSS evidence",
            "cross-session ratios are descriptive observations and are not approved regression thresholds",
        ],
    }


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--session",
        action="append",
        required=True,
        type=Path,
        help="one committed affinity probe report; repeat exactly three times",
    )
    parser.add_argument("--repo-root", type=Path, default=root)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = build_report(args.repo_root, args.session)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(serialize(report))
    except (OSError, SummaryError) as error:
        print(f"session summary error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
