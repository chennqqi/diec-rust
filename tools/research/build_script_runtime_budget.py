#!/usr/bin/env python3
"""Build the Phase 0 script runtime resource-budget candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
EVALUATED_ON = "2026-07-30"
UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
OUTPUT = "docs/design/data/script-runtime-budget-candidate.json"
SOURCES = {
    "adr_runtime": (
        "docs/design/decisions/0006-rquickjs-rule-runtime.md"
    ),
    "adr_scan": (
        "docs/design/decisions/"
        "0012-bounded-nested-scan-budget.md"
    ),
    "api": "docs/design/api.md",
    "c_abi": "docs/design/c-abi.md",
    "runtime_research": (
        "docs/research/rquickjs-rule-runtime-spike.md"
    ),
    "runtime_report": (
        "docs/research/data/rquickjs-rule-runtime.json"
    ),
    "include_sizing": (
        "docs/research/data/include-graph-sizing.json"
    ),
}

KIB = 1024
MIB = 1024 * KIB


class ScriptBudgetError(ValueError):
    """The script runtime budget candidate cannot be generated safely."""


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def reject_constant(value: str) -> None:
    raise ScriptBudgetError(f"non-finite JSON number: {value}")


def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ScriptBudgetError(f"duplicate JSON key: {key}")
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
        raise ScriptBudgetError(
            f"cannot read strict JSON {path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise ScriptBudgetError(f"JSON root must be object: {path}")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ScriptBudgetError(message)


def require_fragments(
    text: str, fragments: tuple[str, ...], source: str
) -> None:
    for fragment in fragments:
        require(fragment in text, f"{source} contract drift: {fragment}")


def next_power_of_two(value: int) -> int:
    require(value > 0, "sizing input must be positive")
    return 1 << (value - 1).bit_length()


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
        raw["adr_runtime"].decode("utf-8"),
        (
            "| live VM heap | 32 MiB | 256 MiB |",
            "| JS VM stack | 512 KiB | 2 MiB |",
            "| VM/native fuel quanta | 131,072 | 1,048,576 |",
            "| cumulative script deadline | 10 s | 60 s |",
            "每轮正常\n  runtime 共观察 28 次 interrupt callback",
            "operation anchor 不等于 VM instruction，也不能从\n"
            "  单一 Binary corpus 的 poll/checkpoint count 推导跨格式 fuel",
            "signature\n  checkpoint 也不代表所有 HostApi 已覆盖",
            "默认 allocator 的 memory checkpoint\n"
            "  不是 eval 内瞬时 heap high-water",
            "4,478,992-byte 最大瞬时\n  high-water",
            "rquickjs 的 `set_memory_limit()` 在 custom\n"
            "  allocator 下是 no-op",
        ),
        SOURCES["adr_runtime"],
    )
    require_fragments(
        raw["adr_scan"].decode("utf-8"),
        (
            "| wall deadline | 30 s |",
            "deadline 120 s",
        ),
        SOURCES["adr_scan"],
    )
    require_fragments(
        raw["api"].decode("utf-8"),
        (
            "pub struct ScriptLimits",
            "pub max_heap_bytes: u64",
            "pub max_stack_bytes: u64",
            "pub max_fuel_quanta: u64",
            "pub runtime_deadline: Duration",
            "Modern 评审候选为\n32 MiB live VM heap",
            "fuel unit 是固定 runtime/backend 版本",
            "child 或下一规则不重置",
        ),
        SOURCES["api"],
    )
    require_fragments(
        raw["c_abi"].decode("utf-8"),
        (
            "uint64_t script_heap_bytes;",
            "uint64_t script_stack_bytes;",
            "uint64_t script_fuel_quanta;",
            "uint64_t script_deadline_ms;",
            "预期 x64 size 为 88 bytes",
        ),
        SOURCES["c_abi"],
    )
    require_fragments(
        raw["runtime_research"].decode("utf-8"),
        (
            "| Files | 2235 |",
            "| Bytes | 2,902,881 |",
            "17 次 handler callback 后无限循环返回",
            "4 MiB runtime limit 拒绝 16 MiB `ArrayBuffer`",
            "默认 VM stack 为\n`256 * 1024` bytes",
            "每轮正常生命周期共触发 28 次 QuickJS-NG interrupt callback",
            "每轮固定 16,439 次，其中 compare 16,285 次、search\n154 次",
            "4,130 个 `Runtime::memory_usage()` checkpoint",
            "`verify-binary-corpus-tracked-heap` 使用包裹 pinned",
            "最大瞬时 high-water 为\n4,478,992 bytes",
            "`eval-isolated-compat-tracked-heap`",
            "瞬时 high-water 为 3,486,384 bytes",
            "`measure-rule-corpus-isolated-heap`",
            "`153,648`、maximum `3,489,576` bytes",
            "`verify-scope-lifecycles-tracked-heap`",
            "scope heap minimum/p50 为 348,080、p95 为 1,825,768，最大 4,468,192 bytes",
            "七条原样上游规则。七类代表性格式规则共\n25 个 case",
            "全矩阵最大瞬时 high-water 为 134,792 bytes",
            "不能观察 eval 内部瞬时 allocator high-water",
        ),
        SOURCES["runtime_research"],
    )

    reports = {
        name: strict_json(root / SOURCES[name])
        for name in ("runtime_report", "include_sizing")
    }
    runtime = reports["runtime_report"]
    require(
        runtime.get("upstream_commit") == UPSTREAM_COMMIT
        and runtime.get("rules_commit") == RULES_COMMIT
        and runtime.get("candidate", {}).get("version") == "0.12.1"
        and runtime.get("candidate", {}).get("engine_version")
        == "0.15.1"
        and runtime.get("candidate", {}).get("features") == ["std"],
        "runtime report identity drift",
    )
    isolated = runtime.get("isolated_eval_with_compatibility_overlay")
    corpus = runtime.get("full_binary_corpus_oracle")
    tracked_corpus = runtime.get("full_binary_corpus_tracked_heap")
    full_rule_tracked = runtime.get("full_rule_corpus_tracked_heap")
    isolated_rule_heap = runtime.get("isolated_rule_runtime_heap")
    scope_lifecycle = runtime.get("scope_lifecycle_tracked_heap")
    format_matrix = runtime.get("representative_format_runtime_matrix")
    measurement = (
        corpus.get("runtime_measurement")
        if isinstance(corpus, dict)
        else None
    )
    fixture = runtime.get("fixture")
    require(
        isolated
        == {
            "bytes": 2_902_881,
            "error_count": 0,
            "files": 2235,
            "overlay_applied_count": 1,
            "overlay_id": "nintendo-unused-var-tp-v1",
            "preserves_source_file": True,
        },
        "full rule-source sizing evidence drift",
    )
    require(
        full_rule_tracked
        == {
            "all_eval_accepted": True,
            "all_runtimes_released_to_zero": True,
            "bytes": 2_902_881,
            "compatibility_overlay_count": 1,
            "denied_allocation_count": 0,
            "files": 2235,
            "high_water_bytes": 3_486_384,
            "limit_bytes": 32 * MIB,
            "live_bytes_before_drop": 171_272,
            "projection_hash_emitted_by_spike": True,
            "projection_hash_independently_recomputed": True,
            "repeat_count": 3,
            "scope": (
                "all fixed rule programs parsed and evaluated at top level "
                "in isolated realms within one custom-allocator runtime; "
                "detect functions are not called and this is not "
                "default-allocator or cross-platform evidence"
            ),
            "set_memory_limit_used": False,
            "stable_projection_equal": True,
            "stable_projection_sha256": (
                "582d5af0995925fa9c2188a38d999e0bcb3373b91fe22510798786828cbc5f58"
            ),
            "tracking_accounting": (
                "RustAllocator allocation Layout bytes: aligned payload "
                "plus internal header"
            ),
        },
        "full rule-corpus tracked heap evidence drift",
    )
    require(
        isinstance(isolated_rule_heap, dict)
        and isolated_rule_heap.get("repeat_count") == 3
        and isolated_rule_heap.get("stable_projection_equal") is True
        and isolated_rule_heap.get("projection_hash_emitted_by_spike")
        is True
        and isolated_rule_heap.get(
            "projection_hash_independently_recomputed"
        )
        is True
        and isolated_rule_heap.get(
            "scope_maxima_hash_independently_recomputed"
        )
        is True
        and isolated_rule_heap.get(
            "top_rules_hash_independently_recomputed"
        )
        is True
        and isolated_rule_heap.get("stable_projection_sha256")
        == "cd091b6ebfe146d21c5b5f8e153bb99b283de9f709f1f95100673b4dd9990c43",
        "isolated per-rule heap repetition evidence drift",
    )
    isolated_projection = isolated_rule_heap.get("stable_projection")
    require(
        isinstance(isolated_projection, dict)
        and isolated_projection.get("upstream_commit")
        == UPSTREAM_COMMIT
        and isolated_projection.get("rules_commit") == RULES_COMMIT
        and isolated_projection.get("files") == 2235
        and isolated_projection.get("bytes") == 2_902_881
        and isolated_projection.get("eval_error_count") == 0
        and isolated_projection.get("runtime_isolation")
        == "one custom-allocator runtime and realm per rule"
        and isolated_projection.get("compatibility_overlay")
        == {
            "applied_paths": [
                "db/Binary/format_bin.Nintendo-certified-file.1.sg"
            ],
            "id": "nintendo-unused-var-tp-v1",
        }
        and isolated_projection.get("heap_distribution_bytes")
        == {
            "maximum": 3_489_576,
            "maximum_rule": "db/Binary/audio.1.sg",
            "maximum_rule_source_bytes": 603_640,
            "minimum": 118_752,
            "p50_nearest_rank": 118_752,
            "p95_nearest_rank": 127_776,
            "p99_nearest_rank": 153_648,
        }
        and isolated_projection.get("interrupt")
        == {
            "handler_call_total": 2235,
            "maximum_handler_calls_per_rule": 1,
            "maximum_rule": "db/ACE",
        }
        and isolated_projection.get("scope_maxima")
        == {
            "scope_count": 36,
            "sha256": (
                "88f8d040fcadec2d4279aebcbd34d9b5b91bd2528a3381e828a3bf0fd690591c"
            ),
        }
        and isolated_projection.get("top_rules_by_high_water")
        == {
            "rule_count": 20,
            "sha256": (
                "c17089727d805fb7dabd599d77647e3d03bcfa8dd4c938242550a468c0181db3"
            ),
        }
        and isolated_projection.get("tracking_allocator")
        == {
            "accounting": (
                "RustAllocator allocation Layout bytes: aligned payload "
                "plus internal header"
            ),
            "all_rule_runtimes_released_to_zero": True,
            "backend": (
                "rquickjs RustAllocator wrapped by TrackingLimitAllocator"
            ),
            "denied_allocation_count": 0,
            "limit_bytes_per_rule_runtime": 32 * MIB,
            "set_memory_limit_used": False,
        },
        "isolated per-rule heap stable projection drift",
    )
    require(
        isinstance(scope_lifecycle, dict)
        and scope_lifecycle.get("repeat_count") == 3
        and scope_lifecycle.get("stable_projection_equal") is True
        and scope_lifecycle.get("projection_hash_emitted_by_spike")
        is True
        and scope_lifecycle.get(
            "projection_hash_independently_recomputed"
        )
        is True
        and scope_lifecycle.get(
            "scope_results_hash_independently_recomputed"
        )
        is True
        and scope_lifecycle.get("stable_projection_sha256")
        == "7635b3cbf3a73f52a64326d7ce72fcb4808b44a1977b0cff39a1a6b3fa773296",
        "scope lifecycle repetition evidence drift",
    )
    scope_projection = scope_lifecycle.get("stable_projection")
    require(
        isinstance(scope_projection, dict)
        and scope_projection.get("upstream_commit") == UPSTREAM_COMMIT
        and scope_projection.get("rules_commit") == RULES_COMMIT
        and scope_projection.get("include_graph_sizing_sha256")
        == "b957d8d672b1cf3c746180661918e16954f3428a57941b7783d82e693f8aede1"
        and scope_projection.get("scope_count") == 30
        and scope_projection.get("program_file_count") == 2205
        and scope_projection.get("type_init_count") == 30
        and scope_projection.get("ordinary_rule_evaluation_count")
        == 2175
        and scope_projection.get("compatibility_overlay_count") == 1
        and scope_projection.get("include_evaluation_count") == 151
        and scope_projection.get("maximum_active_include_depth") == 2
        and scope_projection.get("interrupt_handler_call_total") == 31
        and scope_projection.get("layer_order")
        == "db normalized path, then db_extra normalized path"
        and scope_projection.get("layer_order_is_upstream_equivalent")
        is False
        and scope_projection.get("heap_distribution_bytes")
        == {
            "maximum": 4_468_192,
            "maximum_scope": "Binary",
            "minimum": 348_080,
            "p50_nearest_rank": 348_080,
            "p95_nearest_rank": 1_825_768,
        }
        and scope_projection.get("scope_results")
        == {
            "count": 30,
            "sha256": (
                "5034f491327f20f8850c5bc7dc46d1c624afd00cc0ac9da77abed8bfc72ed424"
            ),
        }
        and scope_projection.get("tracking_allocator")
        == {
            "accounting": (
                "RustAllocator allocation Layout bytes: aligned payload "
                "plus internal header"
            ),
            "all_scope_runtimes_released_to_zero": True,
            "backend": (
                "rquickjs RustAllocator wrapped by TrackingLimitAllocator"
            ),
            "denied_allocation_count": 0,
            "limit_bytes_per_scope_runtime": 32 * MIB,
            "set_memory_limit_used": False,
        },
        "scope lifecycle stable projection drift",
    )
    require(
        isinstance(corpus, dict)
        and corpus.get("all_match") is True
        and corpus.get("sample_count") == 14
        and corpus.get("rule_count_per_sample") == 292
        and corpus.get("attempted_detect_count") == 4088
        and corpus.get("accepted_detect_count") == 4088
        and corpus.get("detect_error_count") == 0
        and corpus.get("fallback_call_total") == 0
        and corpus.get("include_call_count_per_sample") == 30
        and corpus.get("signature_compare_call_total") == 16_285
        and corpus.get("signature_search_call_total") == 154,
        "full Binary corpus operation evidence drift",
    )
    require(
        isinstance(measurement, dict)
        and measurement.get("repeat_count") == 3
        and measurement.get("sample_runtime_count_per_repeat") == 14
        and measurement.get("stable_projection_equal") is True
        and measurement.get("projection_hash_emitted_by_spike") is True
        and measurement.get("stable_projection_sha256")
        == "286e778c3891dd3b289446526f2910601f9e25932feec25489ee74adbcc5c326"
        and measurement.get("native_checkpoint")
        == {
            "call_total": 16_439,
            "can_interrupt_single_native_call": True,
            "candidate_interval": 4096,
            "compare_call_total": 16_285,
            "search_call_total": 154,
            "semantics": (
                "one callback at each Binary signature compare/search "
                "entry and then before every 4096th searched candidate "
                "position within the same native call"
            ),
        }
        and measurement.get("interrupt")
        == {
            "detect_handler_call_sum": 9,
            "handler_call_total": 28,
            "handler_calls_outside_detects": 19,
            "handler_semantics": (
                "one QuickJS-NG interrupt callback invocation; each "
                "sample uses one monotonic runtime counter"
            ),
            "maximum_handler_calls_per_rule": 1,
        }
        and measurement.get("memory", {}).get("checkpoint_count")
        == 4130
        and measurement.get("memory", {}).get(
            "maximum_observed_malloc_size"
        )
        == {
            "bytes": 654_562,
            "sample": "ps3-type-1-elf.self",
        }
        and measurement.get("memory", {}).get(
            "maximum_observed_memory_used_size"
        )
        == {
            "bytes": 623_012,
            "sample": "ps3-type-1-elf.self",
        }
        and measurement.get("memory", {}).get(
            "transient_high_water_measured"
        )
        is False,
        "full Binary runtime measurement evidence drift",
    )
    require(
        isinstance(tracked_corpus, dict)
        and tracked_corpus.get("all_match") is True
        and tracked_corpus.get("sample_count") == 14
        and tracked_corpus.get("matched_count") == 14
        and tracked_corpus.get("attempted_detect_count") == 4088
        and tracked_corpus.get("accepted_detect_count") == 4088
        and tracked_corpus.get("detect_error_count") == 0
        and tracked_corpus.get("fallback_call_total") == 0
        and tracked_corpus.get("runtime_measurement", {}).get(
            "repeat_count"
        )
        == 3
        and tracked_corpus.get("runtime_measurement", {}).get(
            "stable_projection_equal"
        )
        is True
        and tracked_corpus.get("runtime_measurement", {}).get(
            "projection_hash_independently_recomputed"
        )
        is True
        and tracked_corpus.get("runtime_measurement", {}).get(
            "stable_projection_sha256"
        )
        == "c455f6932322ff8161a4f6c9288710b5ed792ff5486b4459e11ef27e794e45c4"
        and tracked_corpus.get("runtime_measurement", {})
        .get("memory", {})
        .get("accounting")
        == (
            "RustAllocator allocation Layout bytes: aligned payload plus "
            "internal header"
        )
        and tracked_corpus.get("runtime_measurement", {})
        .get("memory", {})
        .get("limit_bytes_per_sample_runtime")
        == 32 * MIB
        and tracked_corpus.get("runtime_measurement", {})
        .get("memory", {})
        .get("maximum_high_water_bytes")
        == 4_478_992
        and tracked_corpus.get("runtime_measurement", {})
        .get("memory", {})
        .get("denied_allocation_count")
        == 0
        and tracked_corpus.get("runtime_measurement", {})
        .get("memory", {})
        .get("all_runtimes_released_to_zero")
        is True
        and tracked_corpus.get("runtime_measurement", {})
        .get("memory", {})
        .get("set_memory_limit_used")
        is False,
        "tracked full Binary heap evidence drift",
    )
    require(
        isinstance(fixture, dict)
        and fixture.get("interrupt_handler_calls") == 17
        and fixture.get("memory_limit_bytes") == 4 * MIB
        and fixture.get("memory_limit_observed") is True
        and fixture.get("tracking_allocator", {}).get(
            "accounting"
        )
        == (
            "RustAllocator allocation Layout bytes: aligned payload plus "
            "internal header"
        )
        and fixture.get("tracking_allocator", {}).get(
            "denied_allocation_count"
        )
        == 1
        and fixture.get("tracking_allocator", {}).get(
            "live_bytes_after_drop"
        )
        == 0
        and fixture.get("tracking_allocator", {}).get(
            "same_context_recovered"
        )
        is True
        and fixture.get("stack_limit", {}).get("bytes") == 128 * KIB
        and fixture.get("stack_limit", {}).get("overflow_observed")
        is True
        and fixture.get("wall_clock_deadline", {}).get(
            "deadline_milliseconds"
        )
        == 25
        and fixture.get("wall_clock_deadline", {}).get(
            "deadline_expired"
        )
        is True,
        "runtime fault-injection evidence drift",
    )
    require(
        isinstance(format_matrix, dict)
        and format_matrix.get("all_match") is True
        and format_matrix.get("repeat_count") == 3
        and format_matrix.get("format_count") == 7
        and format_matrix.get("case_count_per_repeat") == 25
        and format_matrix.get("matched_count_per_repeat") == 25
        and format_matrix.get(
            "interrupt_handler_call_total_per_repeat"
        )
        == 25
        and format_matrix.get("memory_checkpoint_count_per_repeat")
        == 75
        and format_matrix.get("stable_canonical_reports_equal") is True
        and format_matrix.get("transient_high_water_measured") is False
        and format_matrix.get("maximum_observed_malloc_size")
        == {
            "bytes": 124_485,
            "case": "verbose_stored_zip",
            "format": "archive",
            "stage": "after_rule",
        }
        and format_matrix.get("maximum_observed_memory_used_size")
        == {
            "bytes": 113_926,
            "case": "verbose_stored_zip",
            "format": "archive",
            "stage": "after_rule",
        }
        and format_matrix.get("tracked_heap", {}).get("all_match") is True
        and format_matrix.get("tracked_heap", {}).get("accounting")
        == (
            "RustAllocator allocation Layout bytes: aligned payload plus "
            "internal header"
        )
        and format_matrix.get("tracked_heap", {}).get("repeat_count") == 3
        and format_matrix.get("tracked_heap", {}).get(
            "case_count_per_repeat"
        )
        == 25
        and format_matrix.get("tracked_heap", {}).get(
            "limit_bytes_per_case_runtime"
        )
        == 32 * MIB
        and format_matrix.get("tracked_heap", {}).get(
            "maximum_high_water_bytes"
        )
        == 134_792
        and format_matrix.get("tracked_heap", {}).get(
            "maximum_high_water_format"
        )
        == "macho"
        and format_matrix.get("tracked_heap", {}).get(
            "maximum_high_water_case"
        )
        == "rust_macho64_x86_64_entry_point_match"
        and format_matrix.get("tracked_heap", {}).get(
            "denied_allocation_count_per_repeat"
        )
        == 0
        and format_matrix.get("tracked_heap", {}).get(
            "all_runtimes_released_to_zero"
        )
        is True
        and format_matrix.get("tracked_heap", {}).get(
            "stable_canonical_reports_equal"
        )
        is True
        and format_matrix.get("tracked_heap", {}).get(
            "transient_high_water_measured"
        )
        is True,
        "representative cross-format runtime evidence drift",
    )

    include = reports["include_sizing"]
    require(
        include.get("upstream_commit") == UPSTREAM_COMMIT
        and include.get("rules_commit") == RULES_COMMIT
        and include.get("sizing", {}).get(
            "maximum_active_include_depth"
        )
        == 2
        and include.get("sizing", {}).get(
            "maximum_transitive_include_evaluations"
        )
        == 30,
        "include sizing evidence drift",
    )
    return bindings, reports


def build_candidate(root: Path) -> dict[str, Any]:
    bindings, reports = validate_sources(root)
    runtime = reports["runtime_report"]
    isolated = runtime["isolated_eval_with_compatibility_overlay"]
    corpus = runtime["full_binary_corpus_oracle"]
    tracked_corpus = runtime["full_binary_corpus_tracked_heap"]
    full_rule_tracked = runtime["full_rule_corpus_tracked_heap"]
    isolated_rule_heap = runtime["isolated_rule_runtime_heap"]
    isolated_rule_projection = isolated_rule_heap["stable_projection"]
    scope_lifecycle = runtime["scope_lifecycle_tracked_heap"]
    scope_projection = scope_lifecycle["stable_projection"]
    measurement = corpus["runtime_measurement"]
    tracked_measurement = tracked_corpus["runtime_measurement"]
    tracked_memory = tracked_measurement["memory"]
    format_matrix = runtime["representative_format_runtime_matrix"]
    tracked_format_matrix = format_matrix["tracked_heap"]
    rule_bytes = isolated["bytes"]
    operation_anchor = (
        corpus["attempted_detect_count"]
        + corpus["signature_compare_call_total"]
        + corpus["signature_search_call_total"]
        + corpus["sample_count"]
        * corpus["include_call_count_per_sample"]
    )
    require(operation_anchor == 20_947, "operation anchor drift")

    modern_heap = next_power_of_two(8 * rule_bytes)
    legacy_heap = next_power_of_two(64 * rule_bytes)
    modern_fuel = next_power_of_two(4 * operation_anchor)
    legacy_fuel = 8 * modern_fuel
    require(
        modern_heap == 32 * MIB
        and legacy_heap == 256 * MIB
        and modern_fuel == 131_072
        and legacy_fuel == 1_048_576,
        "script profile derivation drift",
    )
    profiles = {
        "modern_default": {
            "maximum_live_vm_heap_bytes": modern_heap,
            "maximum_js_vm_stack_bytes": 512 * KIB,
            "maximum_fuel_quanta": modern_fuel,
            "runtime_deadline_milliseconds": 10_000,
        },
        "legacy_high_resource": {
            "maximum_live_vm_heap_bytes": legacy_heap,
            "maximum_js_vm_stack_bytes": 2 * MIB,
            "maximum_fuel_quanta": legacy_fuel,
            "runtime_deadline_milliseconds": 60_000,
        },
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "evaluated_on": EVALUATED_ON,
        "upstream_commit": UPSTREAM_COMMIT,
        "rules_commit": RULES_COMMIT,
        "generator": "tools/research/build_script_runtime_budget.py",
        "result": "review_candidate_not_admitted",
        "runtime_identity": {
            "crate": "rquickjs",
            "crate_version": "0.12.1",
            "engine": "QuickJS-NG",
            "engine_version": "0.15.1",
            "features": ["std"],
            "default_allocator_required_for_pinned_heap_limit": True,
        },
        "units": {
            "heap": (
                "live bytes governed by the per-scan VM allocator limit"
            ),
            "stack": (
                "JS VM stack bytes; native HostApi stack is excluded"
            ),
            "fuel_quantum": (
                "one pinned-backend VM interrupt poll or one native "
                "cooperative checkpoint"
            ),
            "deadline": (
                "absolute monotonic time since first runtime work"
            ),
        },
        "sharing_and_reset": {
            "one_budget_per_scan_runtime": True,
            "global_and_type_init_count": True,
            "include_and_detect_count": True,
            "native_host_api_count": True,
            "child_work_shares_remaining_budget": True,
            "rule_include_child_or_exception_resets_forbidden": True,
            "effective_deadline_is_minimum_of_script_and_scan": True,
        },
        "candidate_derivation": {
            "profiles": profiles,
            "fixed_program_file_count": isolated["files"],
            "fixed_program_source_bytes": rule_bytes,
            "modern_heap_formula": (
                "next_power_of_two(8 * fixed_program_source_bytes)"
            ),
            "legacy_heap_formula": (
                "next_power_of_two(64 * fixed_program_source_bytes)"
            ),
            "pinned_runtime_default_stack_bytes": 256 * KIB,
            "modern_stack_multiple": 2,
            "legacy_stack_multiple": 8,
            "binary_corpus_operation_anchor": {
                "detect_calls": corpus["attempted_detect_count"],
                "signature_compare_calls": corpus[
                    "signature_compare_call_total"
                ],
                "signature_search_calls": corpus[
                    "signature_search_call_total"
                ],
                "include_calls": (
                    corpus["sample_count"]
                    * corpus["include_call_count_per_sample"]
                ),
                "total": operation_anchor,
            },
            "modern_fuel_formula": (
                "next_power_of_two(4 * operation_anchor)"
            ),
            "legacy_fuel_multiple": 8,
            "modern_deadline_fraction_of_scan": "1/3",
            "legacy_deadline_fraction_of_scan": "1/2",
            "not_observed_runtime_maxima": True,
            "modern_heap_candidate_to_tracked_high_water_ratio_floor": (
                modern_heap // tracked_memory["maximum_high_water_bytes"]
            ),
        },
        "evidence_boundary": {
            "fault_injection_only": {
                "heap_limit_bytes": 4 * MIB,
                "stack_limit_bytes": 128 * KIB,
                "deadline_milliseconds": 25,
                "infinite_loop_interrupt_polls": 17,
            },
            "maximum_active_include_depth_observed": 2,
            "maximum_include_evaluations_observed": 30,
            "real_corpus_heap_high_water_measured": False,
            "candidate_custom_allocator_real_corpus_heap_high_water_measured": True,
            "candidate_custom_allocator_accounting": tracked_memory[
                "accounting"
            ],
            "candidate_custom_allocator_limit_bytes_per_sample_runtime": (
                tracked_memory["limit_bytes_per_sample_runtime"]
            ),
            "candidate_custom_allocator_maximum_high_water_bytes": (
                tracked_memory["maximum_high_water_bytes"]
            ),
            "candidate_custom_allocator_maximum_high_water_sample": (
                tracked_memory["maximum_high_water_sample"]
            ),
            "candidate_custom_allocator_denied_allocation_count": (
                tracked_memory["denied_allocation_count"]
            ),
            "candidate_custom_allocator_all_runtimes_released_to_zero": (
                tracked_memory["all_runtimes_released_to_zero"]
            ),
            "candidate_custom_allocator_repeat_count": tracked_measurement[
                "repeat_count"
            ],
            "candidate_custom_allocator_stable_projection_sha256": (
                tracked_measurement["stable_projection_sha256"]
            ),
            "candidate_custom_allocator_full_rule_top_level_program_count": (
                full_rule_tracked["files"]
            ),
            "candidate_custom_allocator_full_rule_top_level_source_bytes": (
                full_rule_tracked["bytes"]
            ),
            "candidate_custom_allocator_full_rule_top_level_high_water_bytes": (
                full_rule_tracked["high_water_bytes"]
            ),
            "candidate_custom_allocator_full_rule_top_level_denied_allocation_count": (
                full_rule_tracked["denied_allocation_count"]
            ),
            "candidate_custom_allocator_full_rule_top_level_released_to_zero": (
                full_rule_tracked["all_runtimes_released_to_zero"]
            ),
            "candidate_custom_allocator_full_rule_top_level_repeat_count": (
                full_rule_tracked["repeat_count"]
            ),
            "candidate_custom_allocator_full_rule_top_level_stable_projection_sha256": (
                full_rule_tracked["stable_projection_sha256"]
            ),
            "candidate_custom_allocator_full_rule_top_level_detect_invoked": False,
            "candidate_custom_allocator_isolated_rule_heap_distribution_bytes": (
                isolated_rule_projection["heap_distribution_bytes"]
            ),
            "candidate_custom_allocator_isolated_rule_interrupt": (
                isolated_rule_projection["interrupt"]
            ),
            "candidate_custom_allocator_isolated_rule_scope_count": (
                isolated_rule_projection["scope_maxima"]["scope_count"]
            ),
            "candidate_custom_allocator_isolated_rule_scope_sha256": (
                isolated_rule_projection["scope_maxima"]["sha256"]
            ),
            "candidate_custom_allocator_isolated_rule_top_count": (
                isolated_rule_projection["top_rules_by_high_water"][
                    "rule_count"
                ]
            ),
            "candidate_custom_allocator_isolated_rule_top_sha256": (
                isolated_rule_projection["top_rules_by_high_water"][
                    "sha256"
                ]
            ),
            "candidate_custom_allocator_isolated_rule_repeat_count": (
                isolated_rule_heap["repeat_count"]
            ),
            "candidate_custom_allocator_isolated_rule_stable_projection_sha256": (
                isolated_rule_heap["stable_projection_sha256"]
            ),
            "candidate_custom_allocator_isolated_rule_detect_invoked": False,
            "candidate_custom_allocator_scope_lifecycle_scope_count": (
                scope_projection["scope_count"]
            ),
            "candidate_custom_allocator_scope_lifecycle_program_file_count": (
                scope_projection["program_file_count"]
            ),
            "candidate_custom_allocator_scope_lifecycle_ordinary_rule_count": (
                scope_projection["ordinary_rule_evaluation_count"]
            ),
            "candidate_custom_allocator_scope_lifecycle_include_evaluation_count": (
                scope_projection["include_evaluation_count"]
            ),
            "candidate_custom_allocator_scope_lifecycle_maximum_include_depth": (
                scope_projection["maximum_active_include_depth"]
            ),
            "candidate_custom_allocator_scope_lifecycle_heap_distribution_bytes": (
                scope_projection["heap_distribution_bytes"]
            ),
            "candidate_custom_allocator_scope_lifecycle_interrupt_total": (
                scope_projection["interrupt_handler_call_total"]
            ),
            "candidate_custom_allocator_scope_lifecycle_layer_order": (
                scope_projection["layer_order"]
            ),
            "candidate_custom_allocator_scope_lifecycle_layer_order_is_upstream_equivalent": (
                scope_projection["layer_order_is_upstream_equivalent"]
            ),
            "candidate_custom_allocator_scope_lifecycle_repeat_count": (
                scope_lifecycle["repeat_count"]
            ),
            "candidate_custom_allocator_scope_lifecycle_stable_projection_sha256": (
                scope_lifecycle["stable_projection_sha256"]
            ),
            "candidate_custom_allocator_scope_lifecycle_detect_invoked": False,
            "candidate_custom_allocator_cross_platform_measured": False,
            "candidate_custom_allocator_is_production_backend": False,
            "real_corpus_lifecycle_memory_checkpoints_measured": True,
            "real_corpus_memory_checkpoint_count": measurement[
                "memory"
            ]["checkpoint_count"],
            "real_corpus_maximum_observed_malloc_size_bytes": (
                measurement["memory"]["maximum_observed_malloc_size"][
                    "bytes"
                ]
            ),
            "real_corpus_maximum_observed_memory_used_size_bytes": (
                measurement["memory"][
                    "maximum_observed_memory_used_size"
                ]["bytes"]
            ),
            "real_corpus_interrupt_poll_count_measured": True,
            "real_corpus_interrupt_poll_repeat_count": measurement[
                "repeat_count"
            ],
            "real_corpus_interrupt_poll_total_per_repeat": measurement[
                "interrupt"
            ]["handler_call_total"],
            "real_corpus_interrupt_poll_stable_projection_equal": (
                measurement["stable_projection_equal"]
            ),
            "real_corpus_runtime_measurement_projection_sha256": (
                measurement["stable_projection_sha256"]
            ),
            "native_host_checkpoint_count_measured": True,
            "real_corpus_native_checkpoint_repeat_count": measurement[
                "repeat_count"
            ],
            "real_corpus_native_checkpoint_total_per_repeat": (
                measurement["native_checkpoint"]["call_total"]
            ),
            "real_corpus_compare_native_checkpoint_total_per_repeat": (
                measurement["native_checkpoint"]["compare_call_total"]
            ),
            "real_corpus_search_native_checkpoint_total_per_repeat": (
                measurement["native_checkpoint"]["search_call_total"]
            ),
            "real_corpus_native_checkpoint_candidate_interval": (
                measurement["native_checkpoint"]["candidate_interval"]
            ),
            "native_checkpoint_can_interrupt_single_call": (
                measurement["native_checkpoint"][
                    "can_interrupt_single_native_call"
                ]
            ),
            "representative_cross_format_rule_runtime_measured": True,
            "representative_cross_format_repeat_count": format_matrix[
                "repeat_count"
            ],
            "representative_cross_format_count": format_matrix[
                "format_count"
            ],
            "representative_cross_format_case_count_per_repeat": (
                format_matrix["case_count_per_repeat"]
            ),
            "representative_cross_format_interrupt_poll_total_per_repeat": (
                format_matrix["interrupt_handler_call_total_per_repeat"]
            ),
            "representative_cross_format_memory_checkpoint_count_per_repeat": (
                format_matrix["memory_checkpoint_count_per_repeat"]
            ),
            "representative_cross_format_stable_reports_equal": (
                format_matrix["stable_canonical_reports_equal"]
            ),
            "representative_cross_format_transient_heap_measured": True,
            "representative_cross_format_tracking_limit_bytes": (
                tracked_format_matrix["limit_bytes_per_case_runtime"]
            ),
            "representative_cross_format_maximum_high_water_bytes": (
                tracked_format_matrix["maximum_high_water_bytes"]
            ),
            "representative_cross_format_maximum_high_water_format": (
                tracked_format_matrix["maximum_high_water_format"]
            ),
            "representative_cross_format_maximum_high_water_case": (
                tracked_format_matrix["maximum_high_water_case"]
            ),
            "representative_cross_format_tracking_denied_allocation_count": (
                tracked_format_matrix["denied_allocation_count_per_repeat"]
            ),
            "representative_cross_format_tracking_all_runtimes_released_to_zero": (
                tracked_format_matrix["all_runtimes_released_to_zero"]
            ),
            "representative_cross_format_tracking_stable_reports_equal": (
                tracked_format_matrix["stable_canonical_reports_equal"]
            ),
            "representative_cross_format_maximum_observed_malloc_size_bytes": (
                format_matrix["maximum_observed_malloc_size"]["bytes"]
            ),
            "representative_cross_format_maximum_observed_memory_used_size_bytes": (
                format_matrix[
                    "maximum_observed_memory_used_size"
                ]["bytes"]
            ),
            "all_format_rule_lifecycles_measured": False,
            "does_not_prove": [
                "production heap, stack, fuel, or deadline acceptability",
                "operation-anchor to VM-poll conversion",
                "native checkpoint coverage for every HostApi",
                "all fixed rules or all supported formats runtime scaling",
                "cross-platform runtime resource equality",
                "all fixed rules on valid positive and negative inputs",
            ],
        },
        "failure_contract": {
            "fuel_exhaustion": "LimitReached(script_fuel)",
            "script_deadline": "Timeout(script_deadline)",
            "vm_heap_limit": "LimitReached(script_heap)",
            "vm_stack_limit": "LimitReached(script_stack)",
            "cancel_has_independent_typed_reason": True,
            "partial_rule_detection_is_not_published": True,
            "context_reuse_requires_explicit_recovery_state": True,
        },
        "acceptance_requirements": [
            "ADR 0006 receives explicit review disposition",
            "production backend measures real-corpus heap high-water",
            (
                "production backend extends native checkpoints to every "
                "HostApi and validates VM poll scaling across formats"
            ),
            "limit-1/exact/+1 covers all four fields without reset",
            "infinite JS and native loops stop under fuel and deadline",
            (
                "custom allocator passes sanitizer and cross-platform "
                "acceptance before production backend adoption"
            ),
            "all format lifecycles pass resource-bound differentials",
            "Windows, Linux, and macOS CPU/heap/stack evidence passes",
            "Rust, CLI, JSON, C, Go, and Python expose one failure contract",
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
            raise ScriptBudgetError(
                "committed script runtime budget candidate differs"
            )
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
