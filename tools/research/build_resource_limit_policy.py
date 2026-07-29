#!/usr/bin/env python3
"""Build the Phase 0 resource-limit policy review candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
EVALUATED_ON = "2026-07-30"
UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
OUTPUT = "docs/design/data/resource-limit-policy-candidate.json"

SOURCES = {
    "adr_include": "docs/design/decisions/0010-bounded-include-graph.md",
    "adr_scan": "docs/design/decisions/0012-bounded-nested-scan-budget.md",
    "adr_traversal": "docs/design/decisions/0014-bounded-path-expansion.md",
    "api": "docs/design/api.md",
    "archive_limit": "docs/research/data/archive-limit-engine-qt5.json",
    "archive_iteration": (
        "docs/research/data/archive-iteration-boundary-engine-qt5.json"
    ),
    "resource_count": (
        "docs/research/data/scan-option-boundaries-linux-qt5.json"
    ),
    "runtime_spike": "docs/research/data/rquickjs-rule-runtime.json",
    "include_graph": "docs/research/data/include-graph-sizing.json",
    "database_sizing": (
        "docs/research/data/database-load-sizing.json"
    ),
    "traversal_attempt": (
        "docs/design/data/traversal-attempt-budget-candidate.json"
    ),
    "diagnostic_budget": (
        "docs/design/data/diagnostic-budget-candidate.json"
    ),
    "input_budget": (
        "docs/design/data/input-budget-candidate.json"
    ),
    "allocation_budget": (
        "docs/design/data/allocation-budget-candidate.json"
    ),
    "script_budget": (
        "docs/design/data/script-runtime-budget-candidate.json"
    ),
}

MIB = 1024 * 1024
GIB = 1024 * MIB


class PolicyError(ValueError):
    """The resource-limit policy cannot be generated safely."""


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def reject_constant(value: str) -> None:
    raise PolicyError(f"non-finite JSON number is forbidden: {value}")


def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PolicyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=reject_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PolicyError(f"cannot read strict JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PolicyError(f"JSON root must be an object: {path}")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PolicyError(message)


def require_text(text: str, fragments: tuple[str, ...], source: str) -> None:
    for fragment in fragments:
        require(fragment in text, f"{source} contract drift: {fragment}")


def validate_nested_bindings(
    root: Path,
    report: dict[str, Any],
    expected_names: set[str],
    label: str,
) -> None:
    bindings = report.get("source_bindings")
    require(isinstance(bindings, dict), f"{label} source bindings missing")
    require(
        set(bindings) == expected_names,
        f"{label} source binding set drift",
    )
    for name, binding in bindings.items():
        require(
            isinstance(binding, dict),
            f"{label} source binding invalid: {name}",
        )
        relative = binding.get("path")
        require(
            isinstance(relative, str)
            and relative
            and "\\" not in relative
            and not Path(relative).is_absolute()
            and ".." not in Path(relative).parts,
            f"{label} source path invalid: {name}",
        )
        path = root / relative
        require(path.is_file(), f"{label} nested source missing: {relative}")
        require(
            binding.get("sha256") == sha256(path.read_bytes()),
            f"{label} nested source hash drift: {name}",
        )


def validate_sources(root: Path) -> dict[str, dict[str, Any]]:
    bindings: dict[str, dict[str, Any]] = {}
    raw_by_name: dict[str, bytes] = {}
    for name, relative in SOURCES.items():
        path = root / relative
        require(path.is_file(), f"source path missing: {relative}")
        raw = path.read_bytes()
        raw_by_name[name] = raw
        bindings[name] = {
            "path": relative,
            "sha256": sha256(raw),
        }

    adr_scan = raw_by_name["adr_scan"].decode("utf-8")
    require_text(
        adr_scan,
        (
            "| wall deadline | 30 s |",
            "| maximum nested depth | 32 |",
            "| total archive entries considered | 4,096 |",
            "| maximum queued items | 4,096 |",
            "| maximum result nodes | 100,000 |",
            "| maximum diagnostics | 4,096 |",
            "| maximum root input bytes | 1 GiB |",
            "| maximum single expanded object/allocation | 128 MiB |",
            "| maximum total allocation bytes | 1 GiB |",
            "| total expanded bytes | 512 MiB |",
            "| total source bytes read/mapped | 1 GiB |",
            "depth\n   64、total entries 100,001、queued items 131,072、"
            "result nodes 1,048,576、",
            "diagnostics 131,072、root input 8 GiB、single object "
            "512 MiB、total\n   allocation 8 GiB、total expanded "
            "4 GiB、",
            "source read 8 GiB、\n   deadline 120 s",
            "root input 8 GiB",
            "根输入稳定逻辑长度",
            "queued items 131,072、result nodes 1,048,576、",
            "diagnostics 131,072",
        ),
        SOURCES["adr_scan"],
    )

    adr_traversal = raw_by_name["adr_traversal"].decode("utf-8")
    require_text(
        adr_traversal,
        (
            "depth 64、considered/emitted files 各\n   100,000、"
            "累计 native path encoding 64 MiB、metadata/open attempts\n"
            "   524,288、deadline 30 s",
            "depth 256、\n   considered/emitted files 各 1,000,000、"
            "累计 path encoding 1 GiB、\n   metadata/open attempts "
            "8,388,608、deadline 120 s",
            "metadata/open attempts",
        ),
        SOURCES["adr_traversal"],
    )

    adr_include = raw_by_name["adr_include"].decode("utf-8")
    require_text(
        adr_include,
        (
            "include depth、总 include evaluations 和 script fuel",
            "cycle detection 不能替代 hard cap",
            "include depth 16、每个 scan context 累计 include\n"
            "  evaluations 256",
            "`LegacyHighResource` 候选为 depth 64、evaluations\n  4096",
            "`limit-1/exact/+1` 覆盖 include depth 和总 evaluation budget",
        ),
        SOURCES["adr_include"],
    )

    api = raw_by_name["api"].decode("utf-8")
    require_text(
        api,
        (
            "pub max_input_bytes: u64",
            "pub max_total_read_bytes: u64",
            "pub max_total_decompressed_bytes: u64",
            "pub max_single_allocation_bytes: u64",
            "pub max_total_allocation_bytes: u64",
            "pub max_nodes: u64",
            "pub max_diagnostics: u64",
            "Modern 候选为 4,096，legacy-high 为\n131,072",
            "`max_input_bytes` 只计 root source 的稳定逻辑长度",
            "Modern 候选为 1 GiB，legacy-high 为 8 GiB",
            "pub max_archive_entries: u64",
            "pub max_depth: u32",
            "pub max_queue_items: u64",
            "`ScriptLimits` 至少控制 heap、stack、instruction/fuel 和 runtime deadline",
            "pub struct DatabaseLimits",
            "pub fn new(limits: DatabaseLimits) -> Result<Self, DatabaseError>",
            "pub max_sources: u32",
            "pub max_entries: u64",
            "pub max_single_entry_bytes: u64",
            "pub max_total_entry_bytes: u64",
            "pub max_single_container_bytes: u64",
            "pub max_total_container_bytes: u64",
            "pub max_single_logical_path_bytes: u32",
            "pub max_total_logical_path_bytes: u64",
            "pub max_cache_bytes: u64",
            "pub max_cache_records: u64",
            "数据库 load 的独立 `DatabaseLimits`",
            "pub max_metadata_open_attempts: u64",
            "Modern 候选为 524,288，legacy-high 为 8,388,608",
        ),
        SOURCES["api"],
    )
    return bindings


def validate_reports(root: Path) -> dict[str, Any]:
    archive = load_json(root / SOURCES["archive_limit"])
    iteration = load_json(root / SOURCES["archive_iteration"])
    resource = load_json(root / SOURCES["resource_count"])
    runtime = load_json(root / SOURCES["runtime_spike"])
    include_graph = load_json(root / SOURCES["include_graph"])
    database_sizing = load_json(root / SOURCES["database_sizing"])
    traversal_attempt = load_json(root / SOURCES["traversal_attempt"])
    diagnostic_budget = load_json(root / SOURCES["diagnostic_budget"])
    input_budget = load_json(root / SOURCES["input_budget"])
    allocation_budget = load_json(root / SOURCES["allocation_budget"])
    script_budget = load_json(root / SOURCES["script_budget"])

    for name, report in (
        ("archive_limit", archive),
        ("archive_iteration", iteration),
        ("resource_count", resource),
        ("runtime_spike", runtime),
        ("include_graph", include_graph),
        ("database_sizing", database_sizing),
        ("traversal_attempt", traversal_attempt),
        ("diagnostic_budget", diagnostic_budget),
        ("input_budget", input_budget),
        ("allocation_budget", allocation_budget),
        ("script_budget", script_budget),
    ):
        require(
            report.get("upstream_commit") == UPSTREAM_COMMIT,
            f"{name} upstream commit drift",
        )

    require(archive.get("passed") is True, "archive limit report did not pass")
    require(
        archive.get("assertions")
        == {
            "cancellation_retains_partial_result": True,
            "depth_reaches_maximum_tested": True,
            "expanded_bytes_reach_maximum_tested": True,
            "source_has_no_independent_depth_or_total_token": True,
        },
        "archive limit assertions drift",
    )
    corpus_samples = archive.get("corpus", {}).get("samples", [])
    require(isinstance(corpus_samples, list), "archive samples missing")
    depth_case = next(
        (item for item in corpus_samples if item.get("depth") == 64),
        None,
    )
    expanded_case = next(
        (
            item
            for item in corpus_samples
            if item.get("cumulative_expanded_bytes") == 33_554_546
        ),
        None,
    )
    require(depth_case is not None, "archive depth-64 evidence missing")
    require(
        expanded_case is not None,
        "archive 33,554,546-byte evidence missing",
    )

    require(
        iteration.get("passed") is True
        and iteration.get("assertions")
        == {
            "aggressive_member_limit_is_unreachable_before_hard_guard": True,
            "record_100000_is_reachable": True,
            "record_100001_is_not_reachable": True,
            "record_99999_is_reachable_control": True,
        },
        "archive iteration assertions drift",
    )

    facts = resource.get("facts")
    require(resource.get("passed") is True, "resource-count report did not pass")
    require(isinstance(facts, dict), "resource-count facts missing")
    require(
        facts.get("default_scanable_resource_limit_is_inclusive_21") is True,
        "default resource-count boundary drift",
    )
    require(
        facts.get("aggressive_resource_limit_is_inclusive_2001") is True,
        "aggressive resource-count boundary drift",
    )

    fixture = runtime.get("fixture")
    require(isinstance(fixture, dict), "runtime spike fixture missing")
    require(
        fixture.get("memory_limit_bytes") == 4 * MIB
        and fixture.get("memory_limit_observed") is True,
        "runtime spike memory evidence drift",
    )
    require(
        fixture.get("stack_limit")
        == {
            "bytes": 128 * 1024,
            "overflow_observed": True,
            "same_context_recovered": True,
            "same_context_recovery_result": "42",
        },
        "runtime spike stack evidence drift",
    )
    deadline = fixture.get("wall_clock_deadline")
    require(
        isinstance(deadline, dict)
        and deadline.get("deadline_milliseconds") == 25
        and deadline.get("deadline_expired") is True
        and deadline.get("interrupt_observed") is True
        and deadline.get("same_context_recovered") is True,
        "runtime spike deadline evidence drift",
    )

    require(
        include_graph.get("rules_commit")
        == "c2c17dfa5ea4e078ba31eab55d87430c96622fb6",
        "include graph rules commit drift",
    )
    graph = include_graph.get("graph")
    sizing = include_graph.get("sizing")
    require(
        isinstance(graph, dict)
        and graph.get("literal_include_call_count") == 56
        and graph.get("non_literal_include_sites") == []
        and graph.get("missing_literal_includes") == []
        and graph.get("helper_cycles") == [],
        "include graph closure drift",
    )
    require(
        isinstance(sizing, dict)
        and sizing.get("scope_count") == 30
        and sizing.get("maximum_transitive_include_evaluations") == 30
        and sizing.get("maximum_evaluation_scopes") == ["Binary", "PE"]
        and sizing.get("maximum_active_include_depth") == 2
        and sizing.get("maximum_depth_scopes")
        == ["Binary", "MSDOS", "PE"]
        and sizing.get("binary_runtime_trace_continuity", {}).get("matches")
        is True,
        "include graph sizing drift",
    )

    database_observed = database_sizing.get("observed_fixed_bundle")
    database_profiles = database_sizing.get("profiles")
    require(
        database_sizing.get("rules_commit")
        == "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
        and database_sizing.get("result")
        == "review_candidate_not_admitted"
        and isinstance(database_observed, dict)
        and database_observed.get("source_count") == 3
        and database_observed.get("entry_count") == 2268
        and database_observed.get("total_entry_bytes") == 2_909_316
        and database_observed.get("maximum_single_entry_bytes") == 603_640
        and database_observed.get("total_container_bytes") == 3_201_508,
        "database sizing observations drift",
    )
    require(
        isinstance(database_profiles, dict)
        and database_profiles.get("modern_default")
        == {
            "status": "review_candidate_not_admitted",
            "maximum_sources": 32,
            "maximum_entries": 32_768,
            "maximum_single_entry_bytes": 8 * MIB,
            "maximum_total_entry_bytes": 32 * MIB,
            "maximum_single_container_bytes": 32 * MIB,
            "maximum_total_container_bytes": 32 * MIB,
            "maximum_single_logical_path_bytes": 512,
            "maximum_total_logical_path_bytes": 512 * 1024,
            "maximum_cache_bytes": 64 * MIB,
            "maximum_cache_records": 32_768,
        }
        and database_profiles.get("legacy_high_resource")
        == {
            "status": "review_candidate_not_admitted",
            "default_for_any_adapter": False,
            "maximum_sources": 256,
            "maximum_entries": 262_144,
            "maximum_single_entry_bytes": 64 * MIB,
            "maximum_total_entry_bytes": 256 * MIB,
            "maximum_single_container_bytes": 256 * MIB,
            "maximum_total_container_bytes": 256 * MIB,
            "maximum_single_logical_path_bytes": 4096,
            "maximum_total_logical_path_bytes": 4 * MIB,
            "maximum_cache_bytes": 512 * MIB,
            "maximum_cache_records": 262_144,
        },
        "database sizing profiles drift",
    )
    attempt_derivation = traversal_attempt.get("derivation")
    attempt_evidence = traversal_attempt.get(
        "upstream_evidence_boundary"
    )
    require(
        traversal_attempt.get("result")
        == "review_candidate_not_admitted"
        and isinstance(attempt_derivation, dict)
        and attempt_derivation.get("modern_default", {}).get(
            "maximum_metadata_open_attempts"
        )
        == 524_288
        and attempt_derivation.get("legacy_high_resource", {}).get(
            "maximum_metadata_open_attempts"
        )
        == 8_388_608
        and attempt_derivation.get("modern_default", {}).get(
            "raw_structural_allowance"
        )
        == 500_004
        and attempt_derivation.get("legacy_high_resource", {}).get(
            "raw_structural_allowance"
        )
        == 5_000_004,
        "traversal attempt candidate drift",
    )
    validate_nested_bindings(
        root,
        traversal_attempt,
        {
            "adr",
            "api",
            "linux_path",
            "linux_large",
            "linux_toctou",
            "windows_closure",
        },
        "traversal attempt",
    )
    require(
        isinstance(attempt_evidence, dict)
        and attempt_evidence.get("filesystem_attempt_count_measured")
        is False
        and attempt_evidence.get("linux_complete_flat_entries") == 4096
        and attempt_evidence.get("windows_complete_flat_entries") == 4096
        and attempt_evidence.get(
            "enumerate_then_reopen_toctou_observed"
        )
        is True,
        "traversal attempt evidence boundary drift",
    )
    diagnostic_profiles = diagnostic_budget.get(
        "candidate_derivation", {}
    ).get("profiles")
    diagnostic_evidence = diagnostic_budget.get(
        "upstream_evidence_boundary"
    )
    diagnostic_closure = diagnostic_budget.get("profile_closure")
    require(
        diagnostic_budget.get("rules_commit")
        == "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
        and diagnostic_budget.get("result")
        == "review_candidate_not_admitted"
        and diagnostic_profiles
        == {
            "modern_default": {
                "maximum_archive_entries_considered": 4096,
                "maximum_queued_items": 4096,
                "maximum_result_nodes": 100_000,
                "maximum_diagnostics": 4096,
            },
            "legacy_high_resource": {
                "maximum_archive_entries_considered": 100_001,
                "maximum_queued_items": 131_072,
                "maximum_result_nodes": 1_048_576,
                "maximum_diagnostics": 131_072,
            },
        },
        "diagnostic budget profile drift",
    )
    require(
        isinstance(diagnostic_evidence, dict)
        and diagnostic_evidence.get("qt5_typo", {}).get("scan_count") == 4
        and diagnostic_evidence.get("qt5_qt6_typo", {}).get(
            "scan_count"
        )
        == 6
        and diagnostic_evidence.get("qt5_qt6_typo", {}).get(
            "diagnostic_text_equal"
        )
        is False
        and isinstance(diagnostic_closure, dict)
        and diagnostic_closure.get("field_sets_must_match") is True,
        "diagnostic budget evidence boundary drift",
    )
    validate_nested_bindings(
        root,
        diagnostic_budget,
        {
            "adr",
            "api",
            "database_error_research",
            "windows_database",
            "qt5_typo",
            "qt5_qt6_typo",
        },
        "diagnostic budget",
    )
    input_profiles = input_budget.get(
        "candidate_derivation", {}
    ).get("profiles")
    input_evidence = input_budget.get("upstream_evidence_boundary")
    require(
        input_budget.get("result") == "review_candidate_not_admitted"
        and input_profiles
        == {
            "modern_default": {
                "maximum_root_input_bytes": GIB,
                "total_source_bytes_read_or_mapped": GIB,
            },
            "legacy_high_resource": {
                "maximum_root_input_bytes": 8 * GIB,
                "total_source_bytes_read_or_mapped": 8 * GIB,
            },
        },
        "input budget profile drift",
    )
    require(
        isinstance(input_evidence, dict)
        and input_evidence.get("engine_contract_case_count") == 37
        and input_evidence.get("maximum_observed_root_archive_bytes")
        == 16_777_452
        and input_evidence.get(
            "maximum_observed_cumulative_expanded_bytes"
        )
        == 33_554_546
        and input_budget.get("counter_relationships", {}).get(
            "root_length_does_not_authorize_equal_allocation"
        )
        is True,
        "input budget evidence boundary drift",
    )
    validate_nested_bindings(
        root,
        input_budget,
        {
            "adr_scan",
            "adr_input",
            "api",
            "engine_contract",
            "archive_limit",
        },
        "input budget",
    )
    allocation_profiles = allocation_budget.get(
        "candidate_derivation", {}
    ).get("profiles")
    allocation_evidence = allocation_budget.get(
        "upstream_evidence_boundary"
    )
    require(
        allocation_budget.get("result")
        == "review_candidate_not_admitted"
        and allocation_profiles
        == {
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
        },
        "allocation budget profile drift",
    )
    require(
        isinstance(allocation_evidence, dict)
        and allocation_evidence.get(
            "archive_maximum_process_peak_rss_kib"
        )
        == 56_472
        and allocation_evidence.get(
            "repeated_product_maximum_process_peak_rss_bytes"
        )
        == 80_953_344
        and allocation_evidence.get(
            "measurements_are_not_scan_owned_allocations"
        )
        is True
        and allocation_budget.get("allocation_unit", {}).get(
            "deallocation_refunds"
        )
        is False
        and allocation_budget.get("allocation_unit", {}).get(
            "cross_target_compile_time_size_assertion_required"
        )
        is True,
        "allocation budget evidence boundary drift",
    )
    validate_nested_bindings(
        root,
        allocation_budget,
        {
            "adr",
            "api",
            "c_abi",
            "archive_limit",
            "repeated_benchmark",
        },
        "allocation budget",
    )
    script_profiles = script_budget.get(
        "candidate_derivation", {}
    ).get("profiles")
    script_evidence = script_budget.get("evidence_boundary")
    require(
        script_budget.get("rules_commit")
        == "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
        and script_budget.get("result")
        == "review_candidate_not_admitted"
        and script_profiles
        == {
            "modern_default": {
                "maximum_fuel_quanta": 131_072,
                "maximum_js_vm_stack_bytes": 512 * 1024,
                "maximum_live_vm_heap_bytes": 32 * MIB,
                "runtime_deadline_milliseconds": 10_000,
            },
            "legacy_high_resource": {
                "maximum_fuel_quanta": 1_048_576,
                "maximum_js_vm_stack_bytes": 2 * MIB,
                "maximum_live_vm_heap_bytes": 256 * MIB,
                "runtime_deadline_milliseconds": 60_000,
            },
        },
        "script runtime budget profile drift",
    )
    require(
        isinstance(script_evidence, dict)
        and script_evidence.get("real_corpus_heap_high_water_measured")
        is False
        and script_evidence.get(
            "real_corpus_interrupt_poll_count_measured"
        )
        is True
        and script_evidence.get(
            "real_corpus_interrupt_poll_repeat_count"
        )
        == 3
        and script_evidence.get(
            "real_corpus_interrupt_poll_total_per_repeat"
        )
        == 28
        and script_evidence.get(
            "real_corpus_runtime_measurement_projection_sha256"
        )
        == "286e778c3891dd3b289446526f2910601f9e25932feec25489ee74adbcc5c326"
        and script_evidence.get(
            "real_corpus_lifecycle_memory_checkpoints_measured"
        )
        is True
        and script_evidence.get(
            "real_corpus_memory_checkpoint_count"
        )
        == 4130
        and script_evidence.get(
            "real_corpus_maximum_observed_malloc_size_bytes"
        )
        == 654_562
        and script_evidence.get(
            "real_corpus_maximum_observed_memory_used_size_bytes"
        )
        == 623_012
        and script_evidence.get(
            "native_host_checkpoint_count_measured"
        )
        is True
        and script_evidence.get(
            "real_corpus_native_checkpoint_repeat_count"
        )
        == 3
        and script_evidence.get(
            "real_corpus_native_checkpoint_total_per_repeat"
        )
        == 16_439
        and script_evidence.get(
            "real_corpus_compare_native_checkpoint_total_per_repeat"
        )
        == 16_285
        and script_evidence.get(
            "real_corpus_search_native_checkpoint_total_per_repeat"
        )
        == 154
        and script_evidence.get(
            "real_corpus_native_checkpoint_candidate_interval"
        )
        == 4096
        and script_evidence.get(
            "native_checkpoint_can_interrupt_single_call"
        )
        is True
        and script_evidence.get(
            "representative_cross_format_rule_runtime_measured"
        )
        is True
        and script_evidence.get(
            "representative_cross_format_repeat_count"
        )
        == 3
        and script_evidence.get(
            "representative_cross_format_count"
        )
        == 7
        and script_evidence.get(
            "representative_cross_format_case_count_per_repeat"
        )
        == 25
        and script_evidence.get(
            "representative_cross_format_interrupt_poll_total_per_repeat"
        )
        == 25
        and script_evidence.get(
            "representative_cross_format_memory_checkpoint_count_per_repeat"
        )
        == 75
        and script_evidence.get(
            "representative_cross_format_stable_reports_equal"
        )
        is True
        and script_evidence.get(
            "representative_cross_format_maximum_observed_malloc_size_bytes"
        )
        == 124_485
        and script_evidence.get(
            "representative_cross_format_maximum_observed_memory_used_size_bytes"
        )
        == 113_926
        and script_evidence.get(
            "representative_cross_format_transient_heap_measured"
        )
        is True
        and script_evidence.get(
            "representative_cross_format_tracking_limit_bytes"
        )
        == 32 * MIB
        and script_evidence.get(
            "representative_cross_format_maximum_high_water_bytes"
        )
        == 124_080
        and script_evidence.get(
            "representative_cross_format_maximum_high_water_format"
        )
        == "macho"
        and script_evidence.get(
            "representative_cross_format_tracking_denied_allocation_count"
        )
        == 0
        and script_evidence.get(
            "representative_cross_format_tracking_all_runtimes_released_to_zero"
        )
        is True
        and script_evidence.get(
            "representative_cross_format_tracking_stable_reports_equal"
        )
        is True
        and script_evidence.get(
            "all_format_rule_lifecycles_measured"
        )
        is False
        and script_budget.get("sharing_and_reset", {}).get(
            "rule_include_child_or_exception_resets_forbidden"
        )
        is True,
        "script runtime budget evidence boundary drift",
    )
    validate_nested_bindings(
        root,
        script_budget,
        {
            "adr_runtime",
            "adr_scan",
            "api",
            "c_abi",
            "runtime_research",
            "runtime_report",
            "include_sizing",
        },
        "script runtime budget",
    )

    return {
        "observations": {
            "archive_depth_maximum_tested": 64,
            "archive_expanded_bytes_maximum_tested": 33_554_546,
            "archive_has_no_independent_depth_or_total_limit": True,
            "legacy_default_resource_children_inclusive": 21,
            "legacy_aggressive_resource_children_inclusive": 2001,
            "legacy_aggressive_archive_record_reachable": 100_000,
            "legacy_aggressive_archive_record_not_reachable": 100_001,
            "runtime_spike_only": {
                "memory_limit_bytes": 4 * MIB,
                "stack_limit_bytes": 128 * 1024,
                "deadline_milliseconds": 25,
                "production_default_candidate": False,
            },
            "fixed_rule_include_graph": {
                "program_file_count": 2235,
                "literal_call_count": 56,
                "maximum_transitive_evaluations": 30,
                "maximum_active_depth": 2,
                "non_literal_or_unresolved_or_cyclic_count": 0,
                "binary_dynamic_trace_matches": True,
            },
            "fixed_database_bundle": {
                "source_count": database_observed["source_count"],
                "entry_count": database_observed["entry_count"],
                "total_entry_bytes": database_observed[
                    "total_entry_bytes"
                ],
                "maximum_single_entry_bytes": database_observed[
                    "maximum_single_entry_bytes"
                ],
                "total_container_bytes": database_observed[
                    "total_container_bytes"
                ],
            },
            "path_traversal_attempt_boundary": {
                "filesystem_attempt_count_measured": False,
                "linux_complete_flat_entries": 4096,
                "windows_complete_flat_entries": 4096,
                "enumerate_then_reopen_toctou_observed": True,
            },
            "diagnostic_evidence_boundary": {
                "qt5_typo_scan_count": 4,
                "qt5_qt6_typo_scan_count": 6,
                "maximum_observed_lines_per_scan": 1,
                "diagnostic_text_equal_across_qt5_qt6": False,
                "observed_maximum_is_candidate_basis": False,
            },
            "root_input_evidence_boundary": {
                "engine_contract_case_count": 37,
                "maximum_observed_root_archive_bytes": 16_777_452,
                "maximum_observed_cumulative_expanded_bytes": 33_554_546,
                "observed_maximum_is_candidate_basis": False,
            },
            "allocation_evidence_boundary": {
                "archive_maximum_process_peak_rss_kib": 56_472,
                "repeated_product_maximum_process_peak_rss_bytes": 80_953_344,
                "measurements_are_scan_owned_allocations": False,
                "observed_maximum_is_candidate_basis": False,
            },
            "script_runtime_evidence_boundary": {
                "real_corpus_heap_high_water_measured": False,
                "real_corpus_interrupt_poll_count_measured": True,
                "real_corpus_interrupt_poll_repeat_count": 3,
                "real_corpus_interrupt_poll_total_per_repeat": 28,
                "real_corpus_runtime_measurement_projection_sha256": (
                    "286e778c3891dd3b289446526f2910601f9e25932feec254"
                    "89ee74adbcc5c326"
                ),
                "real_corpus_lifecycle_memory_checkpoints_measured": True,
                "real_corpus_memory_checkpoint_count": 4130,
                "real_corpus_maximum_observed_malloc_size_bytes": 654_562,
                "real_corpus_maximum_observed_memory_used_size_bytes": 623_012,
                "native_host_checkpoint_count_measured": True,
                "real_corpus_native_checkpoint_repeat_count": 3,
                "real_corpus_native_checkpoint_total_per_repeat": 16_439,
                "real_corpus_compare_native_checkpoint_total_per_repeat": (
                    16_285
                ),
                "real_corpus_search_native_checkpoint_total_per_repeat": 154,
                "real_corpus_native_checkpoint_candidate_interval": 4096,
                "native_checkpoint_can_interrupt_single_call": True,
                "representative_cross_format_rule_runtime_measured": True,
                "representative_cross_format_repeat_count": 3,
                "representative_cross_format_count": 7,
                "representative_cross_format_case_count_per_repeat": 25,
                "representative_cross_format_interrupt_poll_total_per_repeat": (
                    25
                ),
                "representative_cross_format_memory_checkpoint_count_per_repeat": (
                    75
                ),
                "representative_cross_format_stable_reports_equal": True,
                "representative_cross_format_maximum_observed_malloc_size_bytes": (
                    124_485
                ),
                "representative_cross_format_maximum_observed_memory_used_size_bytes": (
                    113_926
                ),
                "representative_cross_format_transient_heap_measured": True,
                "representative_cross_format_tracking_limit_bytes": 32
                * MIB,
                "representative_cross_format_maximum_high_water_bytes": (
                    124_080
                ),
                "representative_cross_format_maximum_high_water_format": (
                    "macho"
                ),
                "representative_cross_format_tracking_denied_allocation_count": (
                    0
                ),
                "representative_cross_format_tracking_all_runtimes_released_to_zero": (
                    True
                ),
                "representative_cross_format_tracking_stable_reports_equal": (
                    True
                ),
                "all_format_rule_lifecycles_measured": False,
                "fault_injection_values_are_candidate_basis": False,
            },
        },
        "database_profiles": database_profiles,
        "diagnostic_profiles": diagnostic_profiles,
        "input_profiles": input_profiles,
        "allocation_profiles": allocation_profiles,
        "script_profiles": script_profiles,
        "required_scan_fields": diagnostic_closure[
            "scan_fields_required_in_both_profiles"
        ],
    }


def build_policy(root: Path) -> dict[str, Any]:
    bindings = validate_sources(root)
    validated = validate_reports(root)
    observations = validated["observations"]
    database_profiles = validated["database_profiles"]
    diagnostic_profiles = validated["diagnostic_profiles"]
    input_profiles = validated["input_profiles"]
    allocation_profiles = validated["allocation_profiles"]
    script_profiles = validated["script_profiles"]
    required_scan_fields = set(validated["required_scan_fields"])
    modern_diagnostic = diagnostic_profiles["modern_default"]
    legacy_diagnostic = diagnostic_profiles["legacy_high_resource"]
    modern_input = input_profiles["modern_default"]
    legacy_input = input_profiles["legacy_high_resource"]
    modern_allocation = allocation_profiles["modern_default"]
    legacy_allocation = allocation_profiles["legacy_high_resource"]
    modern_scan = {
        "wall_deadline_milliseconds": 30_000,
        "maximum_nested_depth": 32,
        "total_archive_entries_considered": 4096,
        "maximum_queued_items": modern_diagnostic[
            "maximum_queued_items"
        ],
        "maximum_result_nodes": modern_diagnostic[
            "maximum_result_nodes"
        ],
        "maximum_diagnostics": modern_diagnostic[
            "maximum_diagnostics"
        ],
        "maximum_root_input_bytes": modern_input[
            "maximum_root_input_bytes"
        ],
        "maximum_total_allocation_bytes": modern_allocation[
            "maximum_total_allocation_bytes"
        ],
        "maximum_single_expanded_object_bytes": 128 * MIB,
        "total_expanded_bytes": 512 * MIB,
        "total_source_bytes_read_or_mapped": GIB,
    }
    legacy_scan = {
        "wall_deadline_milliseconds": 120_000,
        "maximum_nested_depth": 64,
        "total_archive_entries_considered": 100_001,
        "maximum_queued_items": legacy_diagnostic[
            "maximum_queued_items"
        ],
        "maximum_result_nodes": legacy_diagnostic[
            "maximum_result_nodes"
        ],
        "maximum_diagnostics": legacy_diagnostic[
            "maximum_diagnostics"
        ],
        "maximum_root_input_bytes": legacy_input[
            "maximum_root_input_bytes"
        ],
        "maximum_total_allocation_bytes": legacy_allocation[
            "maximum_total_allocation_bytes"
        ],
        "maximum_single_expanded_object_bytes": 512 * MIB,
        "total_expanded_bytes": 4 * GIB,
        "total_source_bytes_read_or_mapped": 8 * GIB,
    }
    require(
        set(modern_scan) == required_scan_fields
        and set(legacy_scan) == required_scan_fields,
        "modern and legacy-high scan field sets differ",
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "evaluated_on": EVALUATED_ON,
        "upstream_commit": UPSTREAM_COMMIT,
        "result": "review_candidate_complete_unadmitted",
        "decision_status": {
            "admitted": False,
            "reason": (
                "ADRs 0006, 0010, 0012, and 0014 remain Proposed; all "
                "required budgets have candidate values, but production "
                "and cross-platform limit benchmarks are missing"
            ),
        },
        "invariants": {
            "all_numeric_limits_nonzero": True,
            "caller_may_lower_but_not_disable_hard_limits": True,
            "child_work_shares_parent_budget": True,
            "reserve_before_read_allocate_decompress_or_enqueue": True,
            "legacy_high_resource_requires_explicit_opt_in": True,
            "limit_difference_requires_safety_deviation_waiver": True,
        },
        "profiles": {
            "modern_default": {
                "status": "review_candidate_not_admitted",
                "scan": modern_scan,
                "traversal": {
                    "wall_deadline_milliseconds": 30_000,
                    "maximum_directory_depth": 64,
                    "maximum_entries_considered": 100_000,
                    "maximum_files_emitted": 100_000,
                    "maximum_total_native_path_bytes": 64 * MIB,
                    "maximum_metadata_open_attempts": 524_288,
                },
                "include": {
                    "maximum_active_depth": 16,
                    "maximum_total_evaluations": 256,
                    "status": "review_candidate_not_admitted",
                },
                "database": database_profiles["modern_default"],
                "script": script_profiles["modern_default"],
            },
            "legacy_high_resource": {
                "status": "review_candidate_not_admitted",
                "default_for_any_adapter": False,
                "scan": legacy_scan,
                "traversal": {
                    "wall_deadline_milliseconds": 120_000,
                    "maximum_directory_depth": 256,
                    "maximum_entries_considered": 1_000_000,
                    "maximum_files_emitted": 1_000_000,
                    "maximum_total_native_path_bytes": GIB,
                    "maximum_metadata_open_attempts": 8_388_608,
                },
                "include": {
                    "maximum_active_depth": 64,
                    "maximum_total_evaluations": 4096,
                    "status": "review_candidate_not_admitted",
                },
                "database": database_profiles["legacy_high_resource"],
                "script": script_profiles["legacy_high_resource"],
            },
        },
        "upstream_compatibility_observations": observations,
        "unresolved_required_budgets": [],
        "acceptance_requirements": [
            "ADRs 0010, 0012, and 0014 receive explicit review disposition",
            "every required budget candidate receives explicit review",
            "limit-1/exact/+1 tests cover every production counter",
            "all archive backends reserve through one shared budget",
            "modern and legacy-high CPU and peak-memory benchmarks pass",
            "Rust, CLI, JSON, C, Go, and Python observe one limit contract",
            "cross-platform path and runtime limit evidence is recorded",
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


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=root)
    parser.add_argument(
        "--output",
        type=Path,
        default=root / OUTPUT,
    )
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    raw = serialize(build_policy(args.root.resolve()))
    if args.check:
        if not args.output.is_file() or args.output.read_bytes() != raw:
            raise PolicyError("committed resource-limit policy differs")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
