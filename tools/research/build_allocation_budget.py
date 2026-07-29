#!/usr/bin/env python3
"""Build the Phase 0 cumulative scan-allocation budget candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
EVALUATED_ON = "2026-07-30"
UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
OUTPUT = "docs/design/data/allocation-budget-candidate.json"
SOURCES = {
    "adr": (
        "docs/design/decisions/"
        "0012-bounded-nested-scan-budget.md"
    ),
    "api": "docs/design/api.md",
    "c_abi": "docs/design/c-abi.md",
    "archive_limit": (
        "docs/research/data/archive-limit-engine-qt5.json"
    ),
    "repeated_benchmark": (
        "docs/research/data/"
        "upstream-benchmark-linux-qt5-affinity-repeated.json"
    ),
}

MIB = 1024 * 1024
GIB = 1024 * MIB


class AllocationBudgetError(ValueError):
    """The allocation budget candidate cannot be generated safely."""


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def reject_constant(value: str) -> None:
    raise AllocationBudgetError(f"non-finite JSON number: {value}")


def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AllocationBudgetError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=reject_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AllocationBudgetError(
            f"cannot read strict JSON {path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise AllocationBudgetError(
            f"JSON root must be object: {path}"
        )
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AllocationBudgetError(message)


def require_fragments(
    text: str, fragments: tuple[str, ...], source: str
) -> None:
    for fragment in fragments:
        require(fragment in text, f"{source} contract drift: {fragment}")


def candidate_profiles() -> dict[str, dict[str, int]]:
    return {
        "modern_default": {
            "maximum_single_allocation_bytes": 128 * MIB,
            "maximum_total_allocation_bytes": GIB,
            "total_expanded_bytes": 512 * MIB,
        },
        "legacy_high_resource": {
            "maximum_single_allocation_bytes": 512 * MIB,
            "maximum_total_allocation_bytes": 8 * GIB,
            "total_expanded_bytes": 4 * GIB,
        },
    }


def validate_sources(root: Path) -> tuple[
    dict[str, dict[str, str]], dict[str, dict[str, Any]]
]:
    bindings: dict[str, dict[str, str]] = {}
    raw: dict[str, bytes] = {}
    for name, relative in SOURCES.items():
        path = root / relative
        require(path.is_file(), f"source missing: {relative}")
        content = path.read_bytes()
        raw[name] = content
        bindings[name] = {
            "path": relative,
            "sha256": sha256(content),
        }

    require_fragments(
        raw["adr"].decode("utf-8"),
        (
            "| maximum total allocation bytes | 1 GiB |",
            "total\n   allocation 8 GiB",
            "`max_total_allocation_bytes` 是全 scan 单调累计",
            "释放不退款",
            "portable element charge",
            "不是\n    上游 RSS 最大值",
        ),
        SOURCES["adr"],
    )
    require_fragments(
        raw["api"].decode("utf-8"),
        (
            "pub max_total_allocation_bytes: u64",
            "`max_total_allocation_bytes` 计全 scan 单调累计",
            "Modern 候选为 1 GiB，\nlegacy-high 为 8 GiB",
            "释放不退款",
            "portable element charge",
        ),
        SOURCES["api"],
    )
    require_fragments(
        raw["c_abi"].decode("utf-8"),
        (
            "uint64_t max_total_allocation_bytes;",
            "| `max_total_allocation_bytes` | 48 |",
            "全 scan 单调累计 allocation capacity",
        ),
        SOURCES["c_abi"],
    )

    reports = {
        name: strict_json(root / SOURCES[name])
        for name in ("archive_limit", "repeated_benchmark")
    }
    archive = reports["archive_limit"]
    require(
        archive.get("upstream_commit") == UPSTREAM_COMMIT
        and archive.get("passed") is True,
        "archive allocation evidence identity drift",
    )
    normal_cases = archive.get("normal_cases")
    require(
        isinstance(normal_cases, list) and len(normal_cases) == 14,
        "archive normal-case set drift",
    )
    harness_rows = [item.get("harness") for item in normal_cases]
    require(
        all(isinstance(item, dict) for item in harness_rows),
        "archive RSS observations missing",
    )

    repeated = reports["repeated_benchmark"]
    require(
        repeated.get("upstream_commit") == UPSTREAM_COMMIT
        and repeated.get("session_count") == 3
        and repeated.get("total_warmup_runs") == 51
        and repeated.get("total_measured_runs") == 270
        and repeated.get("targets_frozen") is False,
        "repeated benchmark identity drift",
    )
    relationships = repeated.get("relationships")
    require(
        isinstance(relationships, dict)
        and relationships.get(
            "all_product_cases_have_complete_rss_samples"
        )
        is True
        and relationships.get(
            "all_sessions_use_exact_image_plan_environment_and_cpuset"
        )
        is True
        and relationships.get(
            "outputs_are_deterministic_across_sessions"
        )
        is True
        and relationships.get("targets_remain_unfrozen") is True,
        "repeated benchmark relationship drift",
    )
    cases = repeated.get("cases")
    require(
        isinstance(cases, dict)
        and set(cases)
        == {
            "upstream.archive-depth16.v1",
            "upstream.cli-baseline-batch-json.v1",
            "upstream.cli-pe32-json.v1",
            "upstream.database-load.v1",
            "upstream.qt-process-control.v1",
        },
        "repeated benchmark case set drift",
    )
    for name, case in cases.items():
        require(
            isinstance(case, dict)
            and isinstance(
                case.get("session_peak_rss_max_bytes"), list
            )
            and len(case["session_peak_rss_max_bytes"]) == 3
            and all(
                isinstance(value, int) and value > 0
                for value in case["session_peak_rss_max_bytes"]
            ),
            f"repeated benchmark RSS maxima drift: {name}",
        )
        expected_counts = (
            [9, 12, 12]
            if name == "upstream.qt-process-control.v1"
            else [15, 15, 15]
        )
        require(
            case.get("session_peak_rss_sample_count")
            == expected_counts,
            f"repeated benchmark RSS sample count drift: {name}",
        )
    return bindings, reports


def observed_boundaries(
    reports: dict[str, dict[str, Any]]
) -> dict[str, int]:
    archive = reports["archive_limit"]
    rows = [item["harness"] for item in archive["normal_cases"]]
    archive_peak = max(item["peak_rss_after_kib"] for item in rows)
    archive_delta = max(
        item["peak_rss_after_kib"] - item["peak_rss_before_kib"]
        for item in rows
    )
    repeated = reports["repeated_benchmark"]
    product_cases = {
        key: value
        for key, value in repeated["cases"].items()
        if key != "upstream.qt-process-control.v1"
    }
    product_peak = max(
        max(item["session_peak_rss_max_bytes"])
        for item in product_cases.values()
    )
    product_rss_samples = sum(
        sum(item["session_peak_rss_sample_count"])
        for item in product_cases.values()
    )
    result = {
        "archive_normal_case_count": len(rows),
        "archive_maximum_process_peak_rss_kib": archive_peak,
        "archive_maximum_process_peak_rss_delta_kib": archive_delta,
        "repeated_session_count": repeated["session_count"],
        "repeated_product_measured_run_count": product_rss_samples,
        "repeated_product_maximum_process_peak_rss_bytes": product_peak,
    }
    require(
        result
        == {
            "archive_normal_case_count": 14,
            "archive_maximum_process_peak_rss_kib": 56_472,
            "archive_maximum_process_peak_rss_delta_kib": 37_572,
            "repeated_session_count": 3,
            "repeated_product_measured_run_count": 180,
            "repeated_product_maximum_process_peak_rss_bytes": 80_953_344,
        },
        "observed allocation evidence boundary drift",
    )
    return result


def build_candidate(root: Path) -> dict[str, Any]:
    bindings, reports = validate_sources(root)
    observed = observed_boundaries(reports)
    profiles = candidate_profiles()
    for profile in profiles.values():
        require(
            profile["maximum_total_allocation_bytes"]
            == 2 * profile["total_expanded_bytes"],
            "total-allocation derivation drift",
        )
        require(
            profile["maximum_total_allocation_bytes"]
            >= 8 * profile["maximum_single_allocation_bytes"],
            "single-allocation headroom drift",
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "evaluated_on": EVALUATED_ON,
        "upstream_commit": UPSTREAM_COMMIT,
        "generator": "tools/research/build_allocation_budget.py",
        "result": "review_candidate_not_admitted",
        "allocation_unit": {
            "definition": (
                "monotonic sum of successful scan-owned allocation "
                "capacity commitments"
            ),
            "byte_storage_charge": "requested capacity bytes",
            "typed_storage_charge": (
                "versioned portable element charge not smaller than "
                "checked Layout::array payload bytes on admitted targets"
            ),
            "cross_target_compile_time_size_assertion_required": True,
            "new_clone_or_arena_chunk_charges_full_capacity": True,
            "moving_grow_or_replacement_charges_full_new_capacity": True,
            "reuse_within_committed_capacity_charges_zero": True,
            "deallocation_refunds": False,
            "failed_allocator_attempt_commits_charge": False,
        },
        "reservation_protocol": {
            "order": [
                "checked logical size, portable charge, and Layout conversion",
                "hold budget reservation before allocator call",
                "try allocator operation",
                "commit charge only after allocator success",
                "publish capacity to scan work",
            ],
            "budget_rejection_allocates": False,
            "allocator_failure": (
                "release tentative hold and return AllocationFailed"
            ),
            "counter_overflow": "fail closed before allocator call",
            "exact_limit_can_reuse_existing_capacity": True,
            "first_positive_increment_after_exact_limit": "LimitReached",
        },
        "scope": {
            "included": [
                "core byte buffers and owned strings",
                "parser and extractor typed storage",
                "work queue, result arena, and diagnostic arena capacity",
                "scan-owned decompressor output capacity",
            ],
            "excluded": {
                "allocator_metadata_or_fragmentation": "benchmark/RSS",
                "stack": "script and native stack policies",
                "mmap_and_page_cache": "total read/mapped budget",
                "database_owned_memory": "DatabaseLimits",
                "script_heap": "ScriptLimits",
                "caller_and_adapter_memory": "outside ScanBudget",
            },
            "not_an_os_or_process_rss_cap": True,
        },
        "candidate_derivation": {
            "profiles": profiles,
            "formula": (
                "maximum total allocation = 2 * total expanded bytes"
            ),
            "modern_single_allocation_multiple": 8,
            "legacy_single_allocation_minimum_multiple": 16,
            "not_upstream_observed_maximum": True,
            "not_production_memory_target": True,
        },
        "upstream_evidence_boundary": {
            **observed,
            "measurements_are_whole_process_rss": True,
            "measurements_are_not_scan_owned_allocations": True,
            "benchmark_targets_frozen": False,
            "does_not_prove": [
                "cumulative allocation capacity used by upstream",
                "1 GiB or 8 GiB production memory acceptability",
                "allocator metadata, fragmentation, or transient peak bounds",
                "Rust implementation allocation behavior",
            ],
        },
        "acceptance_requirements": [
            "ADR 0012 receives explicit review disposition",
            "all input-dependent scan-owned allocations use one protocol",
            "all admitted targets prove portable charges cover actual layouts",
            "limit-1/exact/+1 covers allocate, clone, grow, free, and reuse",
            "mock allocator proves no call after budget rejection",
            "decompressors cannot bypass budgeted output sinks",
            "script/database/adapter scopes have independent enforced limits",
            "modern and legacy-high CPU, allocation, and peak-RSS reports pass",
            "Rust, CLI, JSON, C, Go, and Python expose the same limit result",
        ],
        "source_bindings": bindings,
    }


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


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=root)
    parser.add_argument("--output", type=Path, default=root / OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raw = serialize(build_candidate(args.root.resolve()))
    if args.check:
        if not args.output.is_file() or args.output.read_bytes() != raw:
            raise AllocationBudgetError(
                "committed allocation budget candidate differs"
            )
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
