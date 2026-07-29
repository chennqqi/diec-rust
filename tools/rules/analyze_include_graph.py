#!/usr/bin/env python3
"""Analyze the complete fixed rule include graph and sizing envelope."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
DATABASES = ("db", "db_extra", "db_custom")
RULE_ASSETS_REPORT = (
    "docs/research/data/runtime-rule-assets-license.json"
)
INCLUDE_RE = re.compile(
    r"""\bincludeScript\s*\(\s*(["'])([^"'\\]+)\1\s*\)"""
)
INCLUDE_SITE_RE = re.compile(r"\bincludeScript\s*\(")


class IncludeGraphError(ValueError):
    """The fixed include graph cannot be analyzed safely."""


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def is_program(path: Path) -> bool:
    return path.is_file() and (
        path.suffix.casefold() == ".sg" or path.suffix == ""
    )


def include_sites(path: Path) -> tuple[list[str], int]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise IncludeGraphError(f"cannot read rule {path}: {exc}") from exc
    return (
        [match.group(2) for match in INCLUDE_RE.finditer(text)],
        len(INCLUDE_SITE_RE.findall(text)),
    )


def record(path: Path, rules_root: Path, database: str) -> dict[str, Any]:
    relative = path.relative_to(rules_root)
    under_database = path.relative_to(rules_root / database)
    parts = under_database.parts
    return {
        "database": database,
        "name": path.name,
        "path": relative.as_posix(),
        "scope": "global" if len(parts) == 1 else parts[0],
        "sha256": sha256(path.read_bytes()),
        "size": path.stat().st_size,
    }


def scan_records(rules_root: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for database in DATABASES:
        base = rules_root / database
        if not base.is_dir():
            raise IncludeGraphError(f"database directory missing: {database}")
        for path in sorted(
            (item for item in base.rglob("*") if is_program(item)),
            key=lambda item: item.relative_to(base).as_posix(),
        ):
            result.append(record(path, rules_root, database))
    return result


def first_named(
    records: list[dict[str, Any]],
    name: str,
    *,
    scope: str,
) -> dict[str, Any] | None:
    expected = name.casefold()
    for database in DATABASES:
        for item in records:
            if (
                item["database"] == database
                and item["scope"] == scope
                and item["name"].casefold() == expected
            ):
                return item
    return None


def find_cycles(
    adjacency: dict[str, list[str]],
) -> list[list[str]]:
    cycles: set[tuple[str, ...]] = set()
    active: list[str] = []
    active_index: dict[str, int] = {}
    visited: set[str] = set()

    def canonical_cycle(nodes: list[str]) -> tuple[str, ...]:
        body = nodes[:-1]
        rotations = [
            tuple(body[index:] + body[:index])
            for index in range(len(body))
        ]
        chosen = min(rotations)
        return chosen + (chosen[0],)

    def visit(node: str) -> None:
        if node in active_index:
            start = active_index[node]
            cycles.add(canonical_cycle(active[start:] + [node]))
            return
        if node in visited:
            return
        active_index[node] = len(active)
        active.append(node)
        for target in adjacency.get(node, []):
            visit(target)
        active.pop()
        active_index.pop(node)
        visited.add(node)

    for node in sorted(adjacency):
        visit(node)
    return [list(cycle) for cycle in sorted(cycles)]


def expansion_metrics(
    caller: str,
    calls_by_caller: dict[str, list[str]],
    *,
    active: tuple[str, ...] = (),
) -> tuple[int, int]:
    if caller in active:
        chain = " -> ".join(active + (caller,))
        raise IncludeGraphError(f"include cycle prevents sizing: {chain}")
    evaluations = 0
    maximum_depth = 0
    next_active = active + (caller,)
    for target in calls_by_caller.get(caller, []):
        child_evaluations, child_depth = expansion_metrics(
            target,
            calls_by_caller,
            active=next_active,
        )
        evaluations += 1 + child_evaluations
        maximum_depth = max(maximum_depth, 1 + child_depth)
    return evaluations, maximum_depth


def strict_json(path: Path) -> dict[str, Any]:
    def reject_duplicate(
        pairs: list[tuple[str, Any]],
    ) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise IncludeGraphError(f"duplicate JSON key: {key}")
            value[key] = item
        return value

    def reject_constant(value: str) -> None:
        raise IncludeGraphError(f"non-finite JSON number: {value}")

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicate,
            parse_constant=reject_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise IncludeGraphError(f"cannot read strict JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise IncludeGraphError(f"JSON root must be object: {path}")
    return value


def build_report(repo: Path) -> dict[str, Any]:
    rules_root = repo / "upstream" / "Detect-It-Easy"
    records = scan_records(rules_root)
    by_path = {item["path"]: item for item in records}
    if len(by_path) != len(records):
        raise IncludeGraphError("duplicate rule path")

    assets_path = repo / RULE_ASSETS_REPORT
    assets = strict_json(assets_path)
    identity = assets.get("identity", {})
    inventory = assets.get("inventory", {})
    if (
        identity.get("combined_tree_sha256")
        != "20f2b74effc2bdaf069e3b2e13060432"
        "b8890d38364511f5cde56a337348bfda"
        or inventory.get("program_file_count") != 2235
        or inventory.get("program_byte_count") != 2_902_881
    ):
        raise IncludeGraphError("fixed rule asset identity drift")
    if len(records) != inventory["program_file_count"]:
        raise IncludeGraphError("program inventory count drift")
    if sum(item["size"] for item in records) != inventory["program_byte_count"]:
        raise IncludeGraphError("program inventory byte count drift")

    calls: list[dict[str, Any]] = []
    non_literal: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    calls_by_caller: dict[str, list[str]] = {}
    for caller in records:
        targets, site_count = include_sites(rules_root / caller["path"])
        if site_count != len(targets):
            non_literal.append(
                {
                    "caller": caller["path"],
                    "literal_count": len(targets),
                    "site_count": site_count,
                }
            )
        resolved_paths: list[str] = []
        for ordinal, target_name in enumerate(targets):
            target = first_named(records, target_name, scope="global")
            resolved = target["path"] if target is not None else None
            item = {
                "caller": caller["path"],
                "ordinal": ordinal,
                "target": target_name,
                "resolved_path": resolved,
            }
            calls.append(item)
            if resolved is None:
                missing.append(item)
            else:
                resolved_paths.append(resolved)
        calls_by_caller[caller["path"]] = resolved_paths

    helper_paths = sorted(
        item["path"] for item in records if item["scope"] == "global"
    )
    helper_adjacency = {
        path: calls_by_caller[path] for path in helper_paths
    }
    cycles = find_cycles(helper_adjacency)
    if non_literal:
        raise IncludeGraphError("non-literal include sites prevent closed graph")
    if missing:
        raise IncludeGraphError("missing literal include target")
    if cycles:
        raise IncludeGraphError("fixed helper include graph contains a cycle")

    global_init = first_named(records, "_init", scope="global")
    if global_init is None:
        raise IncludeGraphError("global _init missing")

    scopes = sorted(
        {item["scope"] for item in records if item["scope"] != "global"}
    )
    scope_metrics: list[dict[str, Any]] = []
    for scope in scopes:
        scope_records = [item for item in records if item["scope"] == scope]
        selected_init = first_named(records, "_init", scope=scope)
        roots = [global_init]
        if selected_init is not None:
            roots.append(selected_init)
        roots.extend(
            item
            for item in scope_records
            if selected_init is None or item["path"] != selected_init["path"]
        )
        evaluations = 0
        maximum_depth = 0
        direct_calls = 0
        for root in roots:
            direct_calls += len(calls_by_caller[root["path"]])
            root_evaluations, root_depth = expansion_metrics(
                root["path"],
                calls_by_caller,
            )
            evaluations += root_evaluations
            maximum_depth = max(maximum_depth, root_depth)
        scope_metrics.append(
            {
                "scope": scope,
                "program_file_count": len(scope_records),
                "selected_init": (
                    selected_init["path"]
                    if selected_init is not None
                    else None
                ),
                "direct_include_call_count": direct_calls,
                "transitive_include_evaluation_count": evaluations,
                "maximum_active_include_depth": maximum_depth,
            }
        )

    maximum_evaluations = max(
        item["transitive_include_evaluation_count"]
        for item in scope_metrics
    )
    maximum_depth = max(
        item["maximum_active_include_depth"] for item in scope_metrics
    )
    maximum_evaluation_scopes = [
        item["scope"]
        for item in scope_metrics
        if item["transitive_include_evaluation_count"]
        == maximum_evaluations
    ]
    maximum_depth_scopes = [
        item["scope"]
        for item in scope_metrics
        if item["maximum_active_include_depth"] == maximum_depth
    ]

    binary = next(item for item in scope_metrics if item["scope"] == "Binary")
    if (
        binary["direct_include_call_count"] != 23
        or binary["transitive_include_evaluation_count"] != 30
    ):
        raise IncludeGraphError("Binary dynamic include trace continuity drift")

    return {
        "schema_version": SCHEMA_VERSION,
        "upstream_commit": UPSTREAM_COMMIT,
        "rules_commit": RULES_COMMIT,
        "generator": "tools/rules/analyze_include_graph.py",
        "rule_assets": {
            "report": RULE_ASSETS_REPORT,
            "report_sha256": sha256(assets_path.read_bytes()),
            "combined_tree_sha256": identity["combined_tree_sha256"],
            "program_file_count": len(records),
            "program_byte_count": sum(item["size"] for item in records),
        },
        "resolution_contract": {
            "database_order": list(DATABASES),
            "target_scope": "global program records only",
            "name_matching": "case-insensitive",
            "duplicate_policy": "first matching database-layer record",
            "duplicate_include_policy": "evaluate every call; no include-once cache",
        },
        "graph": {
            "literal_include_call_count": len(calls),
            "unique_calling_file_count": len(
                {item["caller"] for item in calls}
            ),
            "unique_resolved_helper_count": len(
                {item["resolved_path"] for item in calls}
            ),
            "non_literal_include_sites": non_literal,
            "missing_literal_includes": missing,
            "helper_cycles": cycles,
            "calls": calls,
        },
        "sizing": {
            "scope_count": len(scope_metrics),
            "scopes": scope_metrics,
            "maximum_transitive_include_evaluations": maximum_evaluations,
            "maximum_evaluation_scopes": maximum_evaluation_scopes,
            "maximum_active_include_depth": maximum_depth,
            "maximum_depth_scopes": maximum_depth_scopes,
            "binary_runtime_trace_continuity": {
                "direct_calls": binary["direct_include_call_count"],
                "transitive_evaluations": (
                    binary["transitive_include_evaluation_count"]
                ),
                "expected_dynamic_trace_evaluations": 30,
                "matches": True,
            },
        },
        "scope": {
            "covers": (
                "all fixed db/db_extra/db_custom program files and literal "
                "includeScript calls"
            ),
            "does_not_prove": [
                "production runtime memory or instruction limits",
                "future or user-supplied database include shape",
                "runtime behavior for dynamically computed include names",
            ],
        },
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
    repo = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=repo)
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            repo
            / "docs/research/data/"
            "include-graph-sizing.json"
        ),
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raw = serialize(build_report(args.repo.resolve()))
    if args.check:
        if not args.output.is_file() or args.output.read_bytes() != raw:
            raise IncludeGraphError("committed include graph report differs")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
