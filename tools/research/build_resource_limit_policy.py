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
            "| maximum single expanded object/allocation | 128 MiB |",
            "| total expanded bytes | 512 MiB |",
            "| total source bytes read/mapped | 1 GiB |",
            "depth\n   64、total entries 100,001、single object 512 MiB、"
            "total expanded 4 GiB、",
            "total source read 8 GiB、deadline 120 s",
        ),
        SOURCES["adr_scan"],
    )

    adr_traversal = raw_by_name["adr_traversal"].decode("utf-8")
    require_text(
        adr_traversal,
        (
            "depth 64、considered/emitted files 各\n   100,000、"
            "累计 native path encoding 64 MiB、deadline 30 s",
            "depth 256、\n   considered/emitted files 各 1,000,000、"
            "累计 path encoding 1 GiB、\n   deadline 120 s",
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
            "pub max_nodes: u64",
            "pub max_diagnostics: u64",
            "pub max_archive_entries: u64",
            "pub max_depth: u32",
            "pub max_queue_items: u64",
            "`ScriptLimits` 至少控制 heap、stack、instruction/fuel 和 runtime deadline",
            "数据库 load 也有独立 `DatabaseLimits`",
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

    for name, report in (
        ("archive_limit", archive),
        ("archive_iteration", iteration),
        ("resource_count", resource),
        ("runtime_spike", runtime),
        ("include_graph", include_graph),
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

    return {
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
    }


def build_policy(root: Path) -> dict[str, Any]:
    bindings = validate_sources(root)
    observations = validate_reports(root)
    return {
        "schema_version": SCHEMA_VERSION,
        "evaluated_on": EVALUATED_ON,
        "upstream_commit": UPSTREAM_COMMIT,
        "result": "review_candidate_incomplete",
        "decision_status": {
            "admitted": False,
            "reason": (
                "ADRs 0010, 0012, and 0014 remain Proposed; several "
                "required budgets have no production candidate value; "
                "production and cross-platform limit benchmarks are missing"
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
                "scan": {
                    "wall_deadline_milliseconds": 30_000,
                    "maximum_nested_depth": 32,
                    "total_archive_entries_considered": 4096,
                    "maximum_queued_items": 4096,
                    "maximum_result_nodes": 100_000,
                    "maximum_single_expanded_object_bytes": 128 * MIB,
                    "total_expanded_bytes": 512 * MIB,
                    "total_source_bytes_read_or_mapped": GIB,
                },
                "traversal": {
                    "wall_deadline_milliseconds": 30_000,
                    "maximum_directory_depth": 64,
                    "maximum_entries_considered": 100_000,
                    "maximum_files_emitted": 100_000,
                    "maximum_total_native_path_bytes": 64 * MIB,
                },
                "include": {
                    "maximum_active_depth": 16,
                    "maximum_total_evaluations": 256,
                    "status": "review_candidate_not_admitted",
                },
            },
            "legacy_high_resource": {
                "status": "review_candidate_not_admitted",
                "default_for_any_adapter": False,
                "scan": {
                    "wall_deadline_milliseconds": 120_000,
                    "maximum_nested_depth": 64,
                    "total_archive_entries_considered": 100_001,
                    "maximum_single_expanded_object_bytes": 512 * MIB,
                    "total_expanded_bytes": 4 * GIB,
                    "total_source_bytes_read_or_mapped": 8 * GIB,
                },
                "traversal": {
                    "wall_deadline_milliseconds": 120_000,
                    "maximum_directory_depth": 256,
                    "maximum_entries_considered": 1_000_000,
                    "maximum_files_emitted": 1_000_000,
                    "maximum_total_native_path_bytes": GIB,
                },
                "include": {
                    "maximum_active_depth": 64,
                    "maximum_total_evaluations": 4096,
                    "status": "review_candidate_not_admitted",
                },
            },
        },
        "upstream_compatibility_observations": observations,
        "unresolved_required_budgets": [
            {
                "id": "scan.maximum_input_bytes",
                "required_by": "docs/design/api.md#8-scanlimits",
            },
            {
                "id": "scan.maximum_diagnostics",
                "required_by": "docs/design/api.md#8-scanlimits",
            },
            {
                "id": "scan.maximum_total_allocated_bytes",
                "required_by": "untrusted-input allocation safety",
            },
            {
                "id": "traversal.maximum_metadata_open_attempts",
                "required_by": (
                    "docs/design/decisions/"
                    "0014-bounded-path-expansion.md"
                ),
            },
            {
                "id": "script.maximum_heap_bytes",
                "required_by": "docs/design/api.md#8-scanlimits",
            },
            {
                "id": "script.maximum_stack_bytes",
                "required_by": "docs/design/api.md#8-scanlimits",
            },
            {
                "id": "script.maximum_instruction_or_fuel",
                "required_by": "docs/design/api.md#8-scanlimits",
            },
            {
                "id": "script.runtime_deadline",
                "required_by": "docs/design/api.md#8-scanlimits",
            },
            {
                "id": "database.all_load_limits",
                "required_by": "docs/design/api.md#8-scanlimits",
            },
        ],
        "acceptance_requirements": [
            "ADRs 0010, 0012, and 0014 receive explicit review disposition",
            "every unresolved required budget receives a nonzero candidate",
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
