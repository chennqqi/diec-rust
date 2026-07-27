#!/usr/bin/env python3
"""Build the Phase 0 closure manifest for Linux Qt5 source-only abilities."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
EVALUATED_ON = "2026-07-27"
COVERAGE_PATH = "docs/research/data/capability-coverage.json"
PLATFORM = "linux-x86_64-qt5"

CATALOG: dict[str, dict[str, Any]] = {
    "CAP-RULE-007": {
        "closure_kind": "scope_review_or_private_harness",
        "missing_evidence": [
            "the public scan API cannot pass a non-empty signature path",
            "no runtime case observes the private path comparator",
        ],
        "fixture": "two same-name rules in distinct directories",
        "harness": "private DiE_Script processDetect path-filter harness",
        "assertions": [
            "exact path selects only the addressed rule",
            "empty, missing, case-mismatched, and normalized paths are distinct",
            "an ADR either keeps the private behavior in scope or excludes it",
        ],
    },
    "CAP-DISPATCH-002": {
        "closure_kind": "generated_format_oracle",
        "missing_evidence": [
            "MS-DOS, NE, LE, LX, DOS16M, DOS4G, BW DOS16M, and COM lack runtime cases"
        ],
        "fixture": "deterministic minimal DOS/COM family corpus",
        "harness": "pinned qmake/CMake CLI oracle comparator",
        "assertions": [
            "each family member reaches its exact upstream filetype",
            "truncated and near-magic controls do not borrow adjacent dispatch",
            "raw stdout, stderr, exit code, size, and SHA-256 are retained",
        ],
    },
    "CAP-DISPATCH-003": {
        "closure_kind": "generated_format_oracle",
        "missing_evidence": [
            "Amiga Hunk and Atari ST have source dispatch only"
        ],
        "fixture": "deterministic minimal Amiga Hunk and Atari ST corpus",
        "harness": "pinned qmake/CMake CLI oracle comparator",
        "assertions": [
            "both formats reach their exact upstream filetype",
            "truncated and wrong-endian controls are included",
            "raw stdout, stderr, exit code, size, and SHA-256 are retained",
        ],
    },
    "CAP-NEST-007": {
        "closure_kind": "paired_negative_nested_oracle",
        "missing_evidence": [
            "source proves debug-data enumeration exists but scanner dispatch omits it",
            "no paired runtime case distinguishes direct debug context from recursive scanning",
        ],
        "fixture": "PE with both RT_MANIFEST resource and valid debug-data records",
        "harness": "engine recursive scan plus direct debug-context harness",
        "assertions": [
            "resource is recursively dispatched as the positive control",
            "debug data is detectable when invoked directly",
            "the same debug data produces no recursive scanner child",
        ],
    },
    "CAP-NEST-009": {
        "closure_kind": "bounded_escalation_and_adr",
        "missing_evidence": [
            "absence of an independent depth or total-extraction limit is source-only",
            "resource exhaustion boundaries have no escalating runtime corpus",
        ],
        "fixture": "generated nested archives with monotonic depth and expanded bytes",
        "harness": "resource-limited upstream engine oracle",
        "assertions": [
            "per-level count behavior is separated from depth and total bytes",
            "timeout, peak memory, partial results, and cancellation are retained",
            "an ADR records the bounded Rust default and legacy compatibility policy",
        ],
    },
    "CAP-RESULT-001": {
        "closure_kind": "engine_result_harness_extension",
        "missing_evidence": [
            "runtime output currently retains nSize but not nScanTime, sFileName, or ftInit"
        ],
        "fixture": "file, memory, device, and subdevice scans over identical bytes",
        "harness": "extended engine-contract result serializer",
        "assertions": [
            "nScanTime, sFileName, nSize, and ftInit are emitted",
            "entry-point-specific filename semantics are compared",
            "nondeterministic scan time is typed and not exact-normalized away",
        ],
    },
    "CAP-RESULT-002": {
        "closure_kind": "engine_result_harness_extension",
        "missing_evidence": [
            "records and errors are observed but debug-record and handler lists are not"
        ],
        "fixture": "success, parse error, runtime error, debug record, and handler cases",
        "harness": "extended engine-contract result serializer",
        "assertions": [
            "record, error, debug-record, and handler lists are emitted separately",
            "empty and non-empty cases preserve order and duplicates",
            "no list is inferred from CLI stderr or another list",
        ],
    },
    "CAP-RESULT-003": {
        "closure_kind": "engine_result_harness_extension",
        "missing_evidence": [
            "unknown true/false is observed but heuristic flags are only false"
        ],
        "fixture": "normal, heuristic, advanced-heuristic, and unknown rules",
        "harness": "extended engine-contract rule fixture",
        "assertions": [
            "heuristic and advanced-heuristic each have true and false cases",
            "unknown has true and false cases",
            "flags are asserted independently from display type strings",
        ],
    },
    "CAP-RESULT-004": {
        "closure_kind": "nested_result_harness_extension",
        "missing_evidence": [
            "record and parent identifiers are not emitted by current harnesses"
        ],
        "fixture": "root scan with resource and overlay children",
        "harness": "extended nested engine result serializer",
        "assertions": [
            "root and child record identifiers are retained",
            "each child parent identifier equals the actual parent identifier",
            "identifier stability and uniqueness are tested without hard-coding randomness",
        ],
    },
    "CAP-RESULT-005": {
        "closure_kind": "engine_result_harness_extension",
        "missing_evidence": [
            "string type/name values are observed but enum representations are not"
        ],
        "fixture": "known, unknown, heuristic, and custom result records",
        "harness": "extended engine-contract result serializer",
        "assertions": [
            "numeric enums and string type/name projections are emitted together",
            "unknown and out-of-range representations are explicit",
            "case and alias behavior is retained",
        ],
    },
}


class ClosureError(ValueError):
    """The source-only closure manifest cannot be generated safely."""


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ClosureError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw, object_pairs_hook=reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ClosureError(f"invalid coverage JSON: {error}") from error
    if not isinstance(value, dict):
        raise ClosureError("coverage root must be an object")
    return value, raw


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def build_manifest(
    coverage: dict[str, Any],
    coverage_bytes: bytes,
) -> dict[str, Any]:
    if coverage.get("schema_version") != 1:
        raise ClosureError("unsupported coverage schema")
    rows = coverage.get("rows")
    if not isinstance(rows, list):
        raise ClosureError("coverage rows must be an array")
    source_only = [
        row
        for row in rows
        if str(row["platform_status"][PLATFORM]).startswith("source_only")
    ]
    source_ids = {row["id"] for row in source_only}
    if source_ids != set(CATALOG):
        missing = sorted(source_ids - set(CATALOG))
        stale = sorted(set(CATALOG) - source_ids)
        raise ClosureError(
            f"closure catalog drift: missing={missing}, stale={stale}"
        )

    items = []
    for row in source_only:
        capability_id = row["id"]
        plan = CATALOG[capability_id]
        for field in (
            "closure_kind",
            "missing_evidence",
            "fixture",
            "harness",
            "assertions",
        ):
            if not plan[field]:
                raise ClosureError(f"{capability_id} has empty {field}")
        items.append(
            {
                "id": capability_id,
                "name": row["name"],
                "current_status": row["platform_status"][PLATFORM],
                "evidence_set": row["evidence_set"],
                "closure_kind": plan["closure_kind"],
                "missing_evidence": plan["missing_evidence"],
                "proposed_experiment": {
                    "fixture": plan["fixture"],
                    "harness": plan["harness"],
                    "platform": PLATFORM,
                    "assertions": plan["assertions"],
                },
                "acceptance": (
                    "all assertions pass against the pinned upstream "
                    "identity and the capability becomes runtime-observed "
                    "or receives an explicit reviewed scope disposition"
                ),
            }
        )

    kind_counts: dict[str, int] = {}
    for item in items:
        kind = item["closure_kind"]
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
    return {
        "schema_version": SCHEMA_VERSION,
        "evaluated_on": EVALUATED_ON,
        "result": "incomplete",
        "upstream_commit": coverage["upstream_commit"],
        "rules_commit": coverage["rules_commit"],
        "platform": PLATFORM,
        "source": {
            "path": COVERAGE_PATH,
            "sha256": sha256(coverage_bytes),
        },
        "items": items,
        "summary": {
            "source_only_capability_count": len(items),
            "closure_kind_counts": dict(sorted(kind_counts.items())),
            "all_items_have_missing_evidence": all(
                item["missing_evidence"] for item in items
            ),
            "all_items_have_executable_assertions": all(
                item["proposed_experiment"]["assertions"] for item in items
            ),
            "phase_0_source_only_closed": False,
        },
        "limitations": [
            "this manifest specifies closure evidence but does not execute the experiments",
            "source-only negative claims require paired controls or a reviewed scope decision",
            "a catalog entry cannot by itself promote a capability status",
        ],
    }


def serialize(value: dict[str, Any]) -> bytes:
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
    parser.add_argument(
        "--coverage",
        type=Path,
        default=root / COVERAGE_PATH,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            root
            / "docs"
            / "research"
            / "data"
            / "source-only-closure.json"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    coverage, raw = load_json(args.coverage)
    manifest = build_manifest(coverage, raw)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(serialize(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
