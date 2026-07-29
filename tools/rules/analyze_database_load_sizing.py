#!/usr/bin/env python3
"""Size the fixed rule database load envelope and review candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
EVALUATED_ON = "2026-07-30"
UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
DATABASES = ("db", "db_extra", "db_custom")
OUTPUT = "docs/research/data/database-load-sizing.json"

SOURCES = {
    "rule_assets": (
        "docs/research/data/runtime-rule-assets-license.json"
    ),
    "archive_behavior": (
        "docs/research/data/database-archive-linux-qt5.json"
    ),
    "layer_behavior": (
        "docs/research/data/database-layers-engine-qt5.json"
    ),
    "cache_behavior": (
        "docs/research/data/database-cache-engine-qt5.json"
    ),
}

MIB = 1024 * 1024


class DatabaseSizingError(ValueError):
    """The database sizing report cannot be generated safely."""


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def reject_constant(value: str) -> None:
    raise DatabaseSizingError(f"non-finite JSON number: {value}")


def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DatabaseSizingError(f"duplicate JSON key: {key}")
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
        raise DatabaseSizingError(
            f"cannot read strict JSON {path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise DatabaseSizingError(f"JSON root must be object: {path}")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DatabaseSizingError(message)


def next_power_of_two(value: int) -> int:
    if value <= 0:
        raise DatabaseSizingError("sizing input must be positive")
    return 1 << (value - 1).bit_length()


def headroom(value: int, multiplier: int = 8) -> int:
    return next_power_of_two(value * multiplier)


def is_program(path: Path) -> bool:
    return path.suffix.casefold() == ".sg" or path.suffix == ""


def scan_layer(rules_root: Path, database: str) -> dict[str, Any]:
    base = rules_root / database
    require(base.is_dir(), f"database directory missing: {database}")
    descendants = sorted(
        base.rglob("*"),
        key=lambda item: item.relative_to(base).as_posix(),
    )
    for path in descendants:
        require(
            not path.is_symlink(),
            f"symlink is forbidden in fixed database: {path}",
        )

    files = [path for path in descendants if path.is_file()]
    require(files, f"database layer has no files: {database}")
    records: list[dict[str, Any]] = []
    for path in files:
        relative = path.relative_to(base).as_posix()
        bundle_relative = f"{database}/{relative}"
        raw = path.read_bytes()
        records.append(
            {
                "path": relative,
                "bundle_path": bundle_relative,
                "path_bytes": len(relative.encode("utf-8")),
                "bundle_path_bytes": len(bundle_relative.encode("utf-8")),
                "components": len(Path(relative).parts),
                "size": len(raw),
                "program": is_program(path),
            }
        )

    # ZIP_STORED with no extra fields/comments has 30-byte local headers,
    # 46-byte central records, two filename copies, and one 22-byte EOCD.
    stored_zip_bytes = (
        sum(
            item["size"] + 76 + 2 * item["path_bytes"]
            for item in records
        )
        + 22
    )
    largest = max(records, key=lambda item: (item["size"], item["path"]))
    longest = max(
        records,
        key=lambda item: (item["path_bytes"], item["path"]),
    )
    return {
        "database": database,
        "file_count": len(records),
        "byte_count": sum(item["size"] for item in records),
        "program_file_count": sum(item["program"] for item in records),
        "program_byte_count": sum(
            item["size"] for item in records if item["program"]
        ),
        "total_path_bytes": sum(
            item["path_bytes"] for item in records
        ),
        "canonical_stored_zip_bytes": stored_zip_bytes,
        "maximum_components": max(
            item["components"] for item in records
        ),
        "largest_file": {
            "path": largest["path"],
            "bytes": largest["size"],
            "program": largest["program"],
        },
        "longest_path": {
            "path": longest["path"],
            "utf8_bytes": longest["path_bytes"],
        },
        "extension_counts": dict(
            sorted(
                Counter(
                    Path(item["path"]).suffix.casefold() or "<none>"
                    for item in records
                ).items()
            )
        ),
        "_records": records,
    }


def validate_sources(root: Path) -> tuple[
    dict[str, dict[str, str]], dict[str, dict[str, Any]]
]:
    bindings: dict[str, dict[str, str]] = {}
    reports: dict[str, dict[str, Any]] = {}
    for name, relative in SOURCES.items():
        path = root / relative
        require(path.is_file(), f"source missing: {relative}")
        raw = path.read_bytes()
        bindings[name] = {"path": relative, "sha256": sha256(raw)}
        reports[name] = strict_json(path)

    assets = reports["rule_assets"]
    require(
        assets.get("identity", {}).get("combined_tree_sha256")
        == "20f2b74effc2bdaf069e3b2e13060432"
        "b8890d38364511f5cde56a337348bfda",
        "rule asset identity drift",
    )
    inventory = assets.get("inventory", {})
    require(
        inventory.get("file_count") == 2268
        and inventory.get("byte_count") == 2_909_316
        and inventory.get("program_file_count") == 2235
        and inventory.get("program_byte_count") == 2_902_881,
        "rule asset inventory drift",
    )

    archive = reports["archive_behavior"]
    require(
        archive.get("expected_revision") == UPSTREAM_COMMIT
        and archive.get("left_revision") == UPSTREAM_COMMIT
        and archive.get("right_revision") == UPSTREAM_COMMIT
        and archive.get("equal") is True
        and archive.get("failures") == [],
        "archive behavior evidence drift",
    )
    for name in ("layer_behavior", "cache_behavior"):
        report = reports[name]
        require(
            report.get("expected_revision") == UPSTREAM_COMMIT
            and report.get("image_revision") == UPSTREAM_COMMIT
            and report.get("passed") is True
            and report.get("raw_outputs_equal") is True
            and report.get("failures") == [],
            f"{name} evidence drift",
        )

    layer_relationships = reports["layer_behavior"].get("relationships", {})
    require(
        layer_relationships.get(
            "same_named_rules_are_not_deduplicated"
        )
        is True
        and layer_relationships.get(
            "successful_layers_remain_main_extra_custom_blocks"
        )
        is True,
        "layer behavior relationships drift",
    )
    cache_relationships = reports["cache_behavior"].get(
        "relationships", {}
    )
    require(
        cache_relationships.get(
            "record_truncation_injects_partial_record_before_fallback"
        )
        is True
        and cache_relationships.get(
            "tail_truncation_injects_partial_record_before_fallback"
        )
        is True
        and cache_relationships.get(
            "canceled_miss_saves_empty_cache"
        )
        is True,
        "cache behavior relationships drift",
    )
    return bindings, reports


def profile(observed: dict[str, int], multiplier: int) -> dict[str, Any]:
    total_entry_limit = headroom(
        observed["total_entry_bytes"], multiplier
    )
    values = {
        "maximum_sources": headroom(
            observed["source_count"], multiplier
        ),
        "maximum_entries": headroom(
            observed["entry_count"], multiplier
        ),
        "maximum_single_entry_bytes": headroom(
            observed["maximum_single_entry_bytes"], multiplier
        ),
        "maximum_total_entry_bytes": total_entry_limit,
        "maximum_single_container_bytes": headroom(
            observed["maximum_single_container_bytes"], multiplier
        ),
        "maximum_total_container_bytes": headroom(
            observed["total_container_bytes"], multiplier
        ),
        "maximum_single_logical_path_bytes": headroom(
            observed["maximum_single_logical_path_bytes"], multiplier
        ),
        "maximum_total_logical_path_bytes": headroom(
            observed["total_logical_path_bytes"], multiplier
        ),
        "maximum_cache_bytes": total_entry_limit * 2,
        "maximum_cache_records": headroom(
            observed["entry_count"], multiplier
        ),
    }
    require(all(value > 0 for value in values.values()), "zero limit")
    return {
        "status": "review_candidate_not_admitted",
        **values,
    }


def build_report(root: Path) -> dict[str, Any]:
    bindings, _ = validate_sources(root)
    rules_root = root / "upstream" / "Detect-It-Easy"
    layers = [scan_layer(rules_root, name) for name in DATABASES]
    all_records = [
        record for layer in layers for record in layer.pop("_records")
    ]
    observed = {
        "source_count": len(layers),
        "entry_count": sum(layer["file_count"] for layer in layers),
        "total_entry_bytes": sum(
            layer["byte_count"] for layer in layers
        ),
        "program_entry_count": sum(
            layer["program_file_count"] for layer in layers
        ),
        "program_entry_bytes": sum(
            layer["program_byte_count"] for layer in layers
        ),
        "maximum_single_entry_bytes": max(
            item["size"] for item in all_records
        ),
        "maximum_single_logical_path_bytes": max(
            item["path_bytes"] for item in all_records
        ),
        "maximum_bundle_relative_path_bytes": max(
            item["bundle_path_bytes"] for item in all_records
        ),
        "maximum_path_components": max(
            item["components"] for item in all_records
        ),
        "total_logical_path_bytes": sum(
            item["path_bytes"] for item in all_records
        ),
        "maximum_single_container_bytes": max(
            layer["canonical_stored_zip_bytes"] for layer in layers
        ),
        "total_container_bytes": sum(
            layer["canonical_stored_zip_bytes"] for layer in layers
        ),
    }
    require(
        (
            observed["entry_count"],
            observed["total_entry_bytes"],
            observed["program_entry_count"],
            observed["program_entry_bytes"],
        )
        == (2268, 2_909_316, 2235, 2_902_881),
        "enumerated inventory differs from bound asset report",
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "evaluated_on": EVALUATED_ON,
        "upstream_commit": UPSTREAM_COMMIT,
        "rules_commit": RULES_COMMIT,
        "generator": "tools/rules/analyze_database_load_sizing.py",
        "result": "review_candidate_not_admitted",
        "measurement_contract": {
            "database_order": list(DATABASES),
            "logical_path": "UTF-8 path relative to one database source",
            "program_file": "case-insensitive .sg suffix or no suffix",
            "symlinks": "rejected",
            "canonical_archive": (
                "ZIP_STORED; one local and central record per file; "
                "no extra fields, comments, data descriptors, or ZIP64"
            ),
            "canonical_archive_size_formula": (
                "sum(file_bytes + 76 + 2*utf8_path_bytes) + 22"
            ),
        },
        "observed_fixed_bundle": {
            **observed,
            "layers": layers,
        },
        "candidate_derivation": {
            "modern_default": (
                "next_power_of_two(observed * 8); cache bytes are twice "
                "the resulting total-entry ceiling for record metadata"
            ),
            "legacy_high_resource": (
                "next_power_of_two(observed * 64); cache bytes are twice "
                "the resulting total-entry ceiling"
            ),
            "not_proven": [
                "production CPU or peak-memory acceptability",
                "maximum future upstream or user database size",
                "ZIP extra fields, comments, ZIP64, or compression ratio",
                "serialized cache overhead for the complete fixed bundle",
            ],
        },
        "profiles": {
            "modern_default": profile(observed, 8),
            "legacy_high_resource": {
                "default_for_any_adapter": False,
                **profile(observed, 64),
            },
        },
        "required_loader_invariants": [
            "reserve container bytes before reading an archive or cache",
            "reserve entry count and logical path bytes before materializing",
            "reserve declared and actual entry bytes before allocation",
            "directory, archive, embedded, cache-hit, and fallback paths share limits",
            "decode, database build, and cache publish are transactional",
            "unknown syntax and malformed data produce explicit diagnostics",
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
    raw = serialize(build_report(args.root.resolve()))
    if args.check:
        if not args.output.is_file() or args.output.read_bytes() != raw:
            raise DatabaseSizingError(
                "committed database sizing report differs"
            )
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
