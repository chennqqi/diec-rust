#!/usr/bin/env python3
"""Build the closed Phase 0 capability-by-platform coverage report."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
EVALUATED_ON = "2026-07-27"
TRACEABILITY_PATH = "docs/research/data/capability-traceability.json"
TARGET_PLATFORMS = (
    "linux-x86_64-qt5",
    "linux-x86_64-qt6",
    "windows-x86_64-qt5",
    "macos-x86_64-qt5",
)
VERIFICATION_TO_STATUS = {
    "observed": "runtime_observed",
    "observed_with_gaps": "runtime_observed_with_corpus_gaps",
    "source_verified": "source_only_runtime_corpus_missing",
    "source_verified_with_gaps": "source_only_with_corpus_gaps",
}


class CoverageError(ValueError):
    """The traceability input cannot produce trustworthy coverage evidence."""


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CoverageError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    try:
        value = json.loads(
            raw,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=lambda value: (_ for _ in ()).throw(
                CoverageError(f"non-finite JSON constant: {value}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CoverageError(f"invalid traceability JSON: {error}") from error
    if not isinstance(value, dict):
        raise CoverageError("traceability root must be an object")
    return value, raw


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def select(
    capability_ids: set[str],
    *,
    prefixes: tuple[str, ...] = (),
    exact: tuple[str, ...] = (),
) -> list[str]:
    selected = {
        capability_id
        for capability_id in capability_ids
        if capability_id.startswith(prefixes)
    }
    selected.update(exact)
    unknown = selected - capability_ids
    if unknown:
        raise CoverageError(
            f"gap mapping references unknown capabilities: {sorted(unknown)}"
        )
    return sorted(selected)


def build_gap_map(capability_ids: set[str]) -> dict[str, list[str]]:
    all_capabilities = sorted(capability_ids)
    return {
        "CAP-GAP-001": select(
            capability_ids,
            prefixes=("CAP-CLI-OPT-", "CAP-CLI-MODE-"),
        ),
        "CAP-GAP-002": select(
            capability_ids,
            prefixes=("CAP-CLI-DB-",),
        ),
        "CAP-GAP-003": select(
            capability_ids,
            prefixes=("CAP-CLI-IN-",),
        ),
        "CAP-GAP-004": select(
            capability_ids,
            prefixes=("CAP-CLI-OUT-",),
            exact=("CAP-NEST-008",),
        ),
        "CAP-GAP-005": select(
            capability_ids,
            exact=(
                "CAP-CLI-OPT-002",
                "CAP-CLI-OPT-005",
                "CAP-RULE-005",
                "CAP-NEST-004",
                "CAP-NEST-009",
            ),
        ),
        "CAP-GAP-006": select(
            capability_ids,
            exact=(
                "CAP-DISPATCH-004",
                "CAP-NEST-003",
                "CAP-NEST-004",
                "CAP-NEST-009",
            ),
        ),
        "CAP-GAP-007": all_capabilities,
        "CAP-GAP-008": select(
            capability_ids,
            prefixes=("CAP-CLI-IN-", "CAP-CLI-DB-"),
        ),
    }


def validate_traceability(traceability: dict[str, Any]) -> None:
    required = {
        "schema_version",
        "upstream_commit",
        "rules_commit",
        "matrix",
        "platform_scope",
        "verification_states",
        "evidence_sets",
        "capabilities",
        "coverage_gaps",
        "summary",
    }
    if set(traceability) != required:
        raise CoverageError("traceability root fields changed")
    if traceability["schema_version"] != 1:
        raise CoverageError("unsupported traceability schema")
    if traceability["platform_scope"] != ["linux-x86_64-qt5"]:
        raise CoverageError("unexpected admitted platform scope")
    capabilities = traceability["capabilities"]
    if not isinstance(capabilities, list) or not capabilities:
        raise CoverageError("capabilities must be a non-empty array")
    capability_ids = [item["id"] for item in capabilities]
    if len(capability_ids) != len(set(capability_ids)):
        raise CoverageError("capability IDs must be unique")
    if set(traceability["verification_states"]) != set(
        VERIFICATION_TO_STATUS
    ):
        raise CoverageError("verification state set changed")
    gap_ids = [gap["id"] for gap in traceability["coverage_gaps"]]
    if gap_ids != [f"CAP-GAP-{index:03d}" for index in range(1, 9)]:
        raise CoverageError("coverage gap IDs changed")


def build_report(
    traceability: dict[str, Any],
    traceability_bytes: bytes,
) -> dict[str, Any]:
    validate_traceability(traceability)
    capabilities = traceability["capabilities"]
    capability_ids = {item["id"] for item in capabilities}
    gap_map = build_gap_map(capability_ids)
    gap_records = []
    for gap in traceability["coverage_gaps"]:
        gap_id = gap["id"]
        gap_records.append(
            {
                **gap,
                "kind": (
                    "platform_missing"
                    if gap_id in {"CAP-GAP-007", "CAP-GAP-008"}
                    else "corpus_missing"
                ),
                "capability_ids": gap_map[gap_id],
            }
        )

    rows = []
    for capability in capabilities:
        capability_id = capability["id"]
        verification = capability["verification"]
        if verification not in VERIFICATION_TO_STATUS:
            raise CoverageError(
                f"unknown verification state for {capability_id}"
            )
        evidence_set = capability["evidence_set"]
        if evidence_set not in traceability["evidence_sets"]:
            raise CoverageError(f"unknown evidence set for {capability_id}")
        gap_ids = [
            gap["id"]
            for gap in gap_records
            if capability_id in gap["capability_ids"]
        ]
        rows.append(
            {
                "id": capability_id,
                "name": capability["name"],
                "evidence_set": evidence_set,
                "platform_status": {
                    "linux-x86_64-qt5": VERIFICATION_TO_STATUS[
                        verification
                    ],
                    "linux-x86_64-qt6": "platform_missing",
                    "windows-x86_64-qt5": "platform_missing",
                    "macos-x86_64-qt5": "platform_missing",
                },
                "corpus_gap_ids": [
                    gap_id
                    for gap_id in gap_ids
                    if gap_id not in {"CAP-GAP-007", "CAP-GAP-008"}
                ],
                "platform_gap_ids": [
                    gap_id
                    for gap_id in gap_ids
                    if gap_id in {"CAP-GAP-007", "CAP-GAP-008"}
                ],
            }
        )

    statuses = set(VERIFICATION_TO_STATUS.values()) | {"platform_missing"}
    status_counts = {
        platform: {
            status: sum(
                row["platform_status"][platform] == status for row in rows
            )
            for status in sorted(statuses)
        }
        for platform in TARGET_PLATFORMS
    }
    unclassified_cells = sum(
        row["platform_status"].get(platform) not in statuses
        for row in rows
        for platform in TARGET_PLATFORMS
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "evaluated_on": EVALUATED_ON,
        "result": "incomplete",
        "upstream_commit": traceability["upstream_commit"],
        "rules_commit": traceability["rules_commit"],
        "source": {
            "path": TRACEABILITY_PATH,
            "sha256": sha256_bytes(traceability_bytes),
        },
        "target_platforms": list(TARGET_PLATFORMS),
        "admitted_runtime_baseline_platforms": traceability[
            "platform_scope"
        ],
        "status_definitions": {
            "runtime_observed": (
                "pinned runtime evidence exists for the named behavior"
            ),
            "runtime_observed_with_corpus_gaps": (
                "runtime evidence exists but named boundary corpus is missing"
            ),
            "source_only_runtime_corpus_missing": (
                "pinned source evidence exists but runtime corpus is missing"
            ),
            "source_only_with_corpus_gaps": (
                "source evidence exists and additional named boundaries are open"
            ),
            "platform_missing": (
                "no complete capability baseline is admitted for this platform"
            ),
        },
        "evidence_sets": traceability["evidence_sets"],
        "coverage_gaps": gap_records,
        "rows": rows,
        "summary": {
            "capability_row_count": len(rows),
            "platform_count": len(TARGET_PLATFORMS),
            "cell_count": len(rows) * len(TARGET_PLATFORMS),
            "unclassified_capability_row_count": (
                len(capability_ids - {row["id"] for row in rows})
            ),
            "unclassified_cell_count": unclassified_cells,
            "rows_with_corpus_gaps": sum(
                bool(row["corpus_gap_ids"]) for row in rows
            ),
            "rows_with_platform_gaps": sum(
                bool(row["platform_gap_ids"]) for row in rows
            ),
            "status_counts_by_platform": status_counts,
            "phase_0_coverage_complete": False,
        },
        "limitations": [
            (
                "source-only is not runtime compatibility and must not be "
                "promoted to observed"
            ),
            (
                "linux Qt6 spot differentials are not a complete capability "
                "baseline and remain platform_missing here"
            ),
            (
                "a zero unclassified-row count means classification is "
                "complete, not that capability coverage is complete"
            ),
        ],
    }


def serialize(report: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            report,
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
    parser.add_argument(
        "--traceability",
        type=Path,
        default=root / TRACEABILITY_PATH,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            root
            / "docs"
            / "research"
            / "data"
            / "capability-coverage.json"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    traceability, raw = load_json(args.traceability)
    report = build_report(traceability, raw)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(serialize(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
