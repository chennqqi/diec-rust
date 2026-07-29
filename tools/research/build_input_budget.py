#!/usr/bin/env python3
"""Build the Phase 0 root-input byte budget candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
EVALUATED_ON = "2026-07-30"
UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
OUTPUT = "docs/design/data/input-budget-candidate.json"
SOURCES = {
    "adr_scan": (
        "docs/design/decisions/"
        "0012-bounded-nested-scan-budget.md"
    ),
    "adr_input": (
        "docs/design/decisions/"
        "0013-fail-closed-incomplete-input.md"
    ),
    "api": "docs/design/api.md",
    "engine_contract": (
        "docs/research/data/engine-contract-linux-qt5.json"
    ),
    "archive_limit": (
        "docs/research/data/archive-limit-engine-qt5.json"
    ),
}

MIB = 1024 * 1024
GIB = 1024 * MIB


class InputBudgetError(ValueError):
    """The root-input budget candidate cannot be generated safely."""


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def reject_constant(value: str) -> None:
    raise InputBudgetError(f"non-finite JSON number: {value}")


def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InputBudgetError(f"duplicate JSON key: {key}")
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
        raise InputBudgetError(
            f"cannot read strict JSON {path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise InputBudgetError(f"JSON root must be object: {path}")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise InputBudgetError(message)


def require_fragments(
    text: str, fragments: tuple[str, ...], source: str
) -> None:
    for fragment in fragments:
        require(fragment in text, f"{source} contract drift: {fragment}")


def candidate_profiles() -> dict[str, dict[str, int]]:
    return {
        "modern_default": {
            "maximum_root_input_bytes": GIB,
            "total_source_bytes_read_or_mapped": GIB,
        },
        "legacy_high_resource": {
            "maximum_root_input_bytes": 8 * GIB,
            "total_source_bytes_read_or_mapped": 8 * GIB,
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
        raw["adr_scan"].decode("utf-8"),
        (
            "| maximum root input bytes | 1 GiB |",
            "root input 8 GiB",
            "根输入稳定逻辑长度",
            "不授权等量分配",
        ),
        SOURCES["adr_scan"],
    )
    require_fragments(
        raw["adr_input"].decode("utf-8"),
        (
            "具有稳定长度和受控随机访问语义的 `ByteSource`",
            "不满足随机访问契约的 sequential/non-seekable source",
            "自动把 sequential source 全部缓存",
        ),
        SOURCES["adr_input"],
    )
    require_fragments(
        raw["api"].decode("utf-8"),
        (
            "pub max_input_bytes: u64",
            "`max_input_bytes` 只计 root source 的稳定逻辑长度",
            "Modern 候选为 1 GiB，legacy-high 为 8 GiB",
            "不能授权等量 allocation",
        ),
        SOURCES["api"],
    )

    reports = {
        name: strict_json(root / SOURCES[name])
        for name in ("engine_contract", "archive_limit")
    }
    engine = reports["engine_contract"]
    require(
        engine.get("upstream_commit") == UPSTREAM_COMMIT,
        "engine contract upstream identity drift",
    )
    relationships = engine.get("relationships")
    source_audit = engine.get("source_audit")
    harness_output = engine.get("harness_output")
    require(
        isinstance(harness_output, dict)
        and harness_output.get("case_count") == 37
        and isinstance(harness_output.get("cases"), list)
        and len(harness_output["cases"]) == 37
        and isinstance(relationships, dict)
        and relationships.get("chunked_direct_read_completes") is True
        and relationships.get("incomplete_device_reads_are_silent_success")
        is True
        and relationships.get(
            "chunked_subdevice_parent_overreads_one_buffered_byte"
        )
        is True
        and isinstance(source_audit, dict)
        and source_audit.get("device_contracts", {}).get(
            "small_device_copy_ignores_read_count"
        )
        is True,
        "engine input/read evidence drift",
    )

    archive = reports["archive_limit"]
    require(
        archive.get("upstream_commit") == UPSTREAM_COMMIT
        and archive.get("passed") is True
        and archive.get("assertions")
        == {
            "cancellation_retains_partial_result": True,
            "depth_reaches_maximum_tested": True,
            "expanded_bytes_reach_maximum_tested": True,
            "source_has_no_independent_depth_or_total_token": True,
        },
        "archive limit evidence drift",
    )
    samples = archive.get("corpus", {}).get("samples")
    require(isinstance(samples, list), "archive corpus samples missing")
    require(
        max(item.get("size", -1) for item in samples) == 16_777_452
        and max(
            item.get("cumulative_expanded_bytes", -1)
            for item in samples
        )
        == 33_554_546,
        "archive observed byte boundary drift",
    )
    return bindings, reports


def build_candidate(root: Path) -> dict[str, Any]:
    bindings, _reports = validate_sources(root)
    profiles = candidate_profiles()
    require(
        profiles["modern_default"]["maximum_root_input_bytes"]
        == profiles["modern_default"][
            "total_source_bytes_read_or_mapped"
        ]
        and profiles["legacy_high_resource"][
            "maximum_root_input_bytes"
        ]
        == profiles["legacy_high_resource"][
            "total_source_bytes_read_or_mapped"
        ],
        "root/read profile relationship drift",
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "evaluated_on": EVALUATED_ON,
        "upstream_commit": UPSTREAM_COMMIT,
        "generator": "tools/research/build_input_budget.py",
        "result": "review_candidate_not_admitted",
        "root_input_unit": {
            "definition": (
                "stable logical byte length of the root ScanSource"
            ),
            "bytes_source_measurement": "borrowed slice length",
            "byte_source_measurement": (
                "declared stable length after source validation"
            ),
            "path_measurement": (
                "length from the opened stable file handle, before parsing"
            ),
            "root_only": True,
            "child_or_expanded_objects_do_not_count_again": True,
            "unknown_length_streaming_supported": False,
        },
        "enforcement": {
            "reserve_stage": (
                "after source identity/open validation and before parser, "
                "rule, mapping, bulk read, or input-sized allocation"
            ),
            "exact_limit_is_allowed": True,
            "over_limit_behavior": (
                "reject before parser/rule work with LimitReached; "
                "return no partial scan report"
            ),
            "length_check_uses_checked_u64": True,
            "concurrent_length_change_fails_closed_under_adr_0013": True,
        },
        "counter_relationships": {
            "root_length_is_not_cumulative_io": True,
            "total_read_or_mapped_is_charged_independently": True,
            "re_reads_can_exhaust_total_read_or_mapped": True,
            "mapping_charges_exposed_mapped_range": True,
            "root_length_does_not_authorize_equal_allocation": True,
            "single_and_total_allocation_limits_remain_independent": True,
        },
        "candidate_derivation": {
            "profiles": profiles,
            "relationship": (
                "each profile's root-length ceiling equals its existing "
                "total read/mapped ceiling; a root at that ceiling has "
                "budget for at most one full-size pass, while smaller "
                "roots may be reread only until cumulative I/O is exhausted"
            ),
            "not_upstream_observed_maximum": True,
            "not_a_memory_allocation_target": True,
        },
        "upstream_evidence_boundary": {
            "engine_contract_case_count": 37,
            "chunked_positive_progress_completes": True,
            "short_or_failed_reads_can_silently_succeed_upstream": True,
            "qt_subdevice_can_overread_one_parent_byte": True,
            "maximum_observed_root_archive_bytes": 16_777_452,
            "maximum_observed_cumulative_expanded_bytes": 33_554_546,
            "does_not_prove": [
                "maximum root input accepted by arbitrary upstream paths",
                "1 GiB or 8 GiB memory or latency acceptability",
                "whole-input allocation is required or permitted",
            ],
        },
        "acceptance_requirements": [
            "ADR 0012 receives explicit review disposition",
            "Bytes, ByteSource, Path, and FFI use one root-length gate",
            "limit-1/exact/+1 runs before parser, rule, map, and allocation",
            "rereads and mappings independently charge cumulative I/O",
            "concurrent truncate/grow and unknown-length sources fail closed",
            "modern and legacy-high CPU and peak-memory benchmarks pass",
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
            raise InputBudgetError(
                "committed input budget candidate differs"
            )
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
