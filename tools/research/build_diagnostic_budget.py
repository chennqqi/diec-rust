#!/usr/bin/env python3
"""Build the Phase 0 scan diagnostic-count budget candidate."""

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
OUTPUT = "docs/design/data/diagnostic-budget-candidate.json"
SOURCES = {
    "adr": (
        "docs/design/decisions/"
        "0012-bounded-nested-scan-budget.md"
    ),
    "api": "docs/design/api.md",
    "database_error_research": (
        "docs/research/database-error-behavior.md"
    ),
    "windows_database": (
        "docs/research/data/windows-qt5-cli-database.json"
    ),
    "qt5_typo": (
        "docs/research/data/global-typo-errors-qt5.json"
    ),
    "qt5_qt6_typo": (
        "docs/research/data/global-typo-errors-qt5-qt6.json"
    ),
}


class DiagnosticBudgetError(ValueError):
    """The diagnostic budget candidate cannot be generated safely."""


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def reject_constant(value: str) -> None:
    raise DiagnosticBudgetError(f"non-finite JSON number: {value}")


def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DiagnosticBudgetError(f"duplicate JSON key: {key}")
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
        raise DiagnosticBudgetError(
            f"cannot read strict JSON {path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise DiagnosticBudgetError(f"JSON root must be object: {path}")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DiagnosticBudgetError(message)


def require_fragments(
    text: str, fragments: tuple[str, ...], source: str
) -> None:
    for fragment in fragments:
        require(fragment in text, f"{source} contract drift: {fragment}")


def next_power_of_two(value: int) -> int:
    if value <= 0:
        raise DiagnosticBudgetError("sizing input must be positive")
    return 1 << (value - 1).bit_length()


def candidate_profiles() -> dict[str, dict[str, int]]:
    modern_entries = 4096
    legacy_entries = 100_001
    legacy_queue = next_power_of_two(legacy_entries)
    return {
        "modern_default": {
            "maximum_archive_entries_considered": modern_entries,
            "maximum_queued_items": 4096,
            "maximum_result_nodes": 100_000,
            "maximum_diagnostics": 4096,
        },
        "legacy_high_resource": {
            "maximum_archive_entries_considered": legacy_entries,
            "maximum_queued_items": legacy_queue,
            "maximum_result_nodes": next_power_of_two(
                8 * legacy_entries
            ),
            "maximum_diagnostics": legacy_queue,
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
            "| maximum diagnostics | 4,096 |",
            "queued items 131,072、result nodes 1,048,576、",
            "diagnostics 131,072",
            "`max_diagnostics` 计数 canonical typed diagnostic facts",
            "不占 diagnostic arena slot 的 completion",
        ),
        SOURCES["adr"],
    )
    require_fragments(
        raw["api"].decode("utf-8"),
        (
            "pub max_diagnostics: u64",
            "`max_diagnostics` 计数核心产生的 typed diagnostic facts",
            "Modern 候选为 4,096，legacy-high 为\n131,072",
            "不创建第 `limit+1` 项",
        ),
        SOURCES["api"],
    )
    require_fragments(
        raw["database_error_research"].decode("utf-8"),
        (
            "`scanResult.listErrors` 也无条件追加到 stdout",
            "不依赖 `--messages`",
            "错误写 stdout 且破坏 JSON",
        ),
        SOURCES["database_error_research"],
    )

    reports = {
        name: strict_json(root / SOURCES[name])
        for name in ("windows_database", "qt5_typo", "qt5_qt6_typo")
    }
    windows = reports["windows_database"]
    summary = windows.get("summary", {})
    require(
        windows.get("source", {}).get("commit") == UPSTREAM_COMMIT
        and windows.get("source", {}).get("rules_commit") == RULES_COMMIT
        and summary.get("case_count") == 18
        and summary.get("execution_count") == 36
        and summary.get("deterministic") is True
        and summary.get("linux_exit_codes_equal") is True
        and summary.get("linux_document_validity_equal") is True
        and summary.get("linux_normalized_stdout_equal") is True,
        "windows database diagnostic evidence drift",
    )
    for name in ("qt5_typo", "qt5_qt6_typo"):
        report = reports[name]
        require(
            report.get("upstream_commit") == UPSTREAM_COMMIT
            and report.get("rules_commit") == RULES_COMMIT,
            f"{name} identity drift",
        )
    require(
        reports["qt5_typo"].get("normalized_outputs_equal") is True,
        "Qt5 typo equality drift",
    )
    require(
        reports["qt5_qt6_typo"].get(
            "normalized_detections_equal"
        )
        is True
        and reports["qt5_qt6_typo"].get("diagnostics_equal") is False,
        "Qt5/Qt6 typo diagnostic boundary drift",
    )
    return bindings, reports


def observed_diagnostics(report: dict[str, Any]) -> dict[str, int]:
    oracles = report.get("oracles")
    require(isinstance(oracles, list), "typo oracle list missing")
    scans = 0
    line_counts: list[int] = []
    for oracle in oracles:
        inputs = oracle.get("inputs")
        require(isinstance(inputs, list), "typo input list missing")
        for item in inputs:
            diagnostic = item.get("diagnostic")
            require(
                isinstance(diagnostic, str) and diagnostic,
                "typo diagnostic missing",
            )
            scans += 1
            line_counts.append(len(diagnostic.splitlines()))
    require(scans > 0, "typo scan evidence empty")
    return {
        "oracle_count": len(oracles),
        "scan_count": scans,
        "minimum_diagnostic_lines_per_scan": min(line_counts),
        "maximum_diagnostic_lines_per_scan": max(line_counts),
    }


def build_candidate(root: Path) -> dict[str, Any]:
    bindings, reports = validate_sources(root)
    qt5_observed = observed_diagnostics(reports["qt5_typo"])
    cross_observed = observed_diagnostics(reports["qt5_qt6_typo"])
    require(
        qt5_observed
        == {
            "oracle_count": 2,
            "scan_count": 4,
            "minimum_diagnostic_lines_per_scan": 1,
            "maximum_diagnostic_lines_per_scan": 1,
        },
        "Qt5 observed diagnostic count drift",
    )
    require(
        cross_observed
        == {
            "oracle_count": 3,
            "scan_count": 6,
            "minimum_diagnostic_lines_per_scan": 1,
            "maximum_diagnostic_lines_per_scan": 1,
        },
        "Qt5/Qt6 observed diagnostic count drift",
    )
    profiles = candidate_profiles()
    require(
        profiles["legacy_high_resource"]["maximum_queued_items"]
        == 131_072
        and profiles["legacy_high_resource"]["maximum_result_nodes"]
        == 1_048_576,
        "legacy profile derivation drift",
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "evaluated_on": EVALUATED_ON,
        "upstream_commit": UPSTREAM_COMMIT,
        "rules_commit": RULES_COMMIT,
        "generator": "tools/research/build_diagnostic_budget.py",
        "result": "review_candidate_not_admitted",
        "diagnostic_unit": {
            "definition": "one canonical typed diagnostic fact",
            "renderer_lines_or_views_do_not_count": True,
            "reserve_before_message_path_or_detail_copy": True,
            "child_work_shares_parent_counter": True,
            "overflow_behavior": (
                "do not create limit+1; stop new work; put LimitReached "
                "in completion outside the diagnostic arena"
            ),
            "silent_drop_or_fact_merge_forbidden": True,
        },
        "candidate_derivation": {
            "modern_default": (
                "diagnostics equals the existing 4,096 work-queue ceiling"
            ),
            "legacy_high_resource": (
                "queue and diagnostics are next_power_of_two(100,001); "
                "result nodes are next_power_of_two(8*100,001)"
            ),
            "profiles": profiles,
            "not_upstream_observed_maximum": True,
        },
        "upstream_evidence_boundary": {
            "windows_database_matrix": {
                "case_count": 18,
                "execution_count": 36,
                "deterministic": True,
                "linux_semantic_projection_equal": True,
            },
            "qt5_typo": qt5_observed,
            "qt5_qt6_typo": {
                **cross_observed,
                "normalized_detections_equal": True,
                "diagnostic_text_equal": False,
            },
            "does_not_prove": [
                "maximum diagnostics produced by arbitrary input",
                "candidate memory or latency acceptability",
                "renderer line count as a canonical diagnostic count",
            ],
        },
        "profile_closure": {
            "scan_fields_required_in_both_profiles": [
                "wall_deadline_milliseconds",
                "maximum_nested_depth",
                "total_archive_entries_considered",
                "maximum_queued_items",
                "maximum_result_nodes",
                "maximum_diagnostics",
                "maximum_single_expanded_object_bytes",
                "total_expanded_bytes",
                "total_source_bytes_read_or_mapped",
            ],
            "field_sets_must_match": True,
        },
        "acceptance_requirements": [
            "ADR 0012 receives explicit review disposition",
            "limit-1/exact/+1 proves no diagnostic allocation after overflow",
            "all parsers, rules, children, and archive backends share one counter",
            "canonical completion preserves LimitReached without a diagnostic slot",
            "modern and legacy-high CPU and peak-memory benchmarks pass",
            "Rust, CLI, JSON, C, Go, and Python expose the same fact count and usage",
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
            raise DiagnosticBudgetError(
                "committed diagnostic budget candidate differs"
            )
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
