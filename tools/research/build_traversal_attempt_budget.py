#!/usr/bin/env python3
"""Build the Phase 0 traversal metadata/open attempt candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
EVALUATED_ON = "2026-07-30"
UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
OUTPUT = "docs/design/data/traversal-attempt-budget-candidate.json"
SOURCES = {
    "adr": (
        "docs/design/decisions/0014-bounded-path-expansion.md"
    ),
    "api": "docs/design/api.md",
    "linux_path": (
        "docs/research/data/path-filesystem-engine-qt5.json"
    ),
    "linux_large": (
        "docs/research/data/large-path-engine-qt5.json"
    ),
    "linux_toctou": (
        "docs/research/data/path-toctou-engine-qt5.json"
    ),
    "windows_closure": (
        "docs/research/data/windows-path-closure-qt5.json"
    ),
}


class AttemptBudgetError(ValueError):
    """The traversal attempt candidate cannot be generated safely."""


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def reject_constant(value: str) -> None:
    raise AttemptBudgetError(f"non-finite JSON number: {value}")


def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AttemptBudgetError(f"duplicate JSON key: {key}")
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
        raise AttemptBudgetError(
            f"cannot read strict JSON {path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise AttemptBudgetError(f"JSON root must be object: {path}")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AttemptBudgetError(message)


def require_fragments(
    text: str, fragments: tuple[str, ...], source: str
) -> None:
    for fragment in fragments:
        require(fragment in text, f"{source} contract drift: {fragment}")


def next_power_of_two(value: int) -> int:
    if value <= 0:
        raise AttemptBudgetError("attempt sizing input must be positive")
    return 1 << (value - 1).bit_length()


def derive_attempt_limit(
    entries_considered: int, files_emitted: int
) -> dict[str, int]:
    require(entries_considered > 0, "entries candidate must be positive")
    require(files_emitted > 0, "files candidate must be positive")
    require(
        files_emitted <= entries_considered,
        "files candidate cannot exceed entries candidate",
    )
    root_allowance = 4
    per_entry_allowance = 4
    per_emitted_file_allowance = 1
    raw = (
        root_allowance
        + per_entry_allowance * entries_considered
        + per_emitted_file_allowance * files_emitted
    )
    return {
        "maximum_entries_considered": entries_considered,
        "maximum_files_emitted": files_emitted,
        "root_attempt_allowance": root_allowance,
        "per_considered_entry_attempt_allowance": per_entry_allowance,
        "per_emitted_file_handoff_allowance": (
            per_emitted_file_allowance
        ),
        "raw_structural_allowance": raw,
        "maximum_metadata_open_attempts": next_power_of_two(raw),
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

    adr = raw["adr"].decode("utf-8")
    require_fragments(
        adr,
        (
            "metadata/open attempts\n   524,288",
            "metadata/open attempts 8,388,608",
            "`4 + 4*entries_considered + files_emitted`",
            "失败调用也计数，内部重试必须再次 reserve",
            "mock adapter 证明 exact/+1 不发生越界调用",
        ),
        SOURCES["adr"],
    )
    api = raw["api"].decode("utf-8")
    require_fragments(
        api,
        (
            "pub struct TraversalLimits",
            "pub max_metadata_open_attempts: u64",
            "Modern 候选为 524,288，legacy-high 为 8,388,608",
            "失败和 retry 也计数",
        ),
        SOURCES["api"],
    )

    reports = {
        name: strict_json(root / SOURCES[name])
        for name in (
            "linux_path",
            "linux_large",
            "linux_toctou",
            "windows_closure",
        )
    }
    for name in ("linux_path", "linux_large", "linux_toctou"):
        report = reports[name]
        require(
            report.get("upstream_commit") == UPSTREAM_COMMIT
            and report.get("passed") is True
            and report.get("failures") == [],
            f"{name} evidence drift",
        )
    windows = reports["windows_closure"]
    require(
        windows.get("source", {}).get("commit") == UPSTREAM_COMMIT
        and windows.get("passed") is True
        and windows.get("failures") == []
        and windows.get("case_count") == 23
        and windows.get("execution_count") == 46,
        "windows closure evidence drift",
    )
    return bindings, reports


def build_candidate(root: Path) -> dict[str, Any]:
    bindings, reports = validate_sources(root)
    path_facts = reports["linux_path"]["facts"]
    large_facts = reports["linux_large"]["facts"]
    toctou_facts = reports["linux_toctou"]["facts"]
    windows = reports["windows_closure"]["relationships"]
    require(
        path_facts.get("deep_64_directory_reaches_leaf") is True
        and path_facts.get(
            "self_cycle_duplicates_pdf_at_depths_40_through_0"
        )
        is True,
        "linux path facts drift",
    )
    require(
        large_facts.get("all_4096_flat_files_are_emitted") is True
        and large_facts.get("all_4096_nested_files_are_emitted")
        is True
        and large_facts.get(
            "cli_target_expansion_has_no_wired_cooperative_cancel"
        )
        is True,
        "linux large-directory facts drift",
    )
    require(
        toctou_facts.get(
            "swap_happens_after_full_enumeration_sync_point"
        )
        is True
        and toctou_facts.get("swap_old_to_new_matches_stable_new")
        is True
        and toctou_facts.get(
            "unlink_result_matches_observed_missing_open"
        )
        is True,
        "linux TOCTOU facts drift",
    )
    require(
        windows.get("large_flat_4096_is_complete_and_ordered") is True
        and windows.get("large_nested_4096_is_complete_and_ordered")
        is True
        and windows.get("source_freezes_list_before_open") is True
        and windows.get("toctou_swap_opens_new_target") is True
        and windows.get("reparse_cycle_is_bounded_and_repeats_without_deduplication")
        is True,
        "windows traversal relationships drift",
    )

    modern = derive_attempt_limit(100_000, 100_000)
    legacy = derive_attempt_limit(1_000_000, 1_000_000)
    require(
        modern["maximum_metadata_open_attempts"] == 524_288,
        "modern attempt candidate drift",
    )
    require(
        legacy["maximum_metadata_open_attempts"] == 8_388_608,
        "legacy attempt candidate drift",
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "evaluated_on": EVALUATED_ON,
        "upstream_commit": UPSTREAM_COMMIT,
        "generator": (
            "tools/research/build_traversal_attempt_budget.py"
        ),
        "result": "review_candidate_not_admitted",
        "attempt_unit": {
            "definition": (
                "one project-issued filesystem adapter request for "
                "metadata, type, identity, read-link, or file/directory/"
                "reparse handle acquire or reacquire"
            ),
            "failed_attempts_count": True,
            "automatic_retries_count_again": True,
            "cached_facts_without_refresh_count": False,
            "reserve_before_adapter_call": True,
        },
        "derivation": {
            "formula": (
                "next_power_of_two(4 + 4*maximum_entries_considered "
                "+ maximum_files_emitted)"
            ),
            "interpretation": (
                "structural sizing allowance, not an upstream syscall "
                "measurement or a guarantee that all counters reach max"
            ),
            "modern_default": modern,
            "legacy_high_resource": legacy,
        },
        "upstream_evidence_boundary": {
            "filesystem_attempt_count_measured": False,
            "linux_complete_flat_entries": 4096,
            "linux_complete_nested_files": 4096,
            "windows_complete_flat_entries": 4096,
            "windows_complete_nested_files": 4096,
            "enumerate_then_reopen_toctou_observed": True,
            "symlink_or_reparse_cycle_without_identity_dedup_observed": True,
            "does_not_prove": [
                "production adapter call count per entry",
                "macOS handle-relative traversal behavior",
                "candidate CPU or latency acceptability",
            ],
        },
        "acceptance_requirements": [
            "ADR 0014 receives explicit review disposition",
            "every adapter attempt reserves before touching the filesystem",
            "success, failure, retry, link, reparse, and TOCTOU paths have limit-1/exact/+1 tests",
            "modern and legacy-high traversal benchmarks pass on supported platforms",
            "Rust, CLI, JSON, C, Go, and Python expose the same limit and consumed usage",
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
            raise AttemptBudgetError(
                "committed traversal attempt candidate differs"
            )
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
