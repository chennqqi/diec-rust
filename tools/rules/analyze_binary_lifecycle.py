#!/usr/bin/env python3
"""Generate deterministic evidence for the fixed upstream Binary rule lifecycle."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable


UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
DATABASES = ("db", "db_extra", "db_custom")
INCLUDE_RE = re.compile(
    r"""\bincludeScript\s*\(\s*(["'])([^"'\\]+)\1\s*\)"""
)
INCLUDE_SITE_RE = re.compile(r"\bincludeScript\s*\(")
SOURCE_EVIDENCE = {
    "die_script.cpp": {
        "commit": "5d82316c110abf0eb863b50bc679d330e05067b6",
        "sha256": (
            "588da8f383725795c600bfe2a91a9649bdd5cefb9bfa294379752bfa132dab67"
        ),
        "url": (
            "https://github.com/horsicq/die_script/blob/"
            "5d82316c110abf0eb863b50bc679d330e05067b6/die_script.cpp"
        ),
    },
    "die_scriptengine.cpp": {
        "commit": "5d82316c110abf0eb863b50bc679d330e05067b6",
        "sha256": (
            "f9b9d69a17dc930556c7308fce46d3287d18dd9f927c91d6733ce994594fcb72"
        ),
        "url": (
            "https://github.com/horsicq/die_script/blob/"
            "5d82316c110abf0eb863b50bc679d330e05067b6/die_scriptengine.cpp"
        ),
    },
    "xscanengine.cpp": {
        "commit": "dfe4a419e4f491bb23688ba03c5a5bf39e34da83",
        "sha256": (
            "e088bebb7c8345ce5832cc51de712c05a8b239873d7f092db3ae5566a761b498"
        ),
        "url": (
            "https://github.com/horsicq/XScanEngine/blob/"
            "dfe4a419e4f491bb23688ba03c5a5bf39e34da83/xscanengine.cpp"
        ),
    },
}


def is_signature(path: Path) -> bool:
    return path.is_file() and (path.suffix.lower() == ".sg" or not path.suffix)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def priority_candidate(name: str) -> str | None:
    if name.count(".") <= 1:
        return None
    return name.split(".")[-2]


def precedes(left: str, right: str) -> bool:
    """Mirror sort_signature_prio for records with the same file type."""
    left_priority = priority_candidate(left)
    right_priority = priority_candidate(right)
    if (
        left_priority is not None
        and right_priority is not None
        and left_priority
        and right_priority
        and left_priority != right_priority
    ):
        return left_priority < right_priority
    return left < right


def find_cycle_witnesses(names: list[str], limit: int = 10) -> list[list[str]]:
    irregular = [name for name in names if priority_candidate(name) is None]
    irregular.sort(key=lambda name: (name == "_init", name))
    regular = [name for name in names if priority_candidate(name) is not None]
    witnesses: list[list[str]] = []
    for first in irregular:
        for second in regular:
            if not precedes(first, second):
                continue
            for third in regular:
                if (
                    precedes(second, third)
                    and precedes(third, first)
                    and len({first, second, third}) == 3
                ):
                    witnesses.append([first, second, third])
                    if len(witnesses) == limit:
                        return witnesses
    return witnesses


def records(root: Path, database: str, directory: str) -> list[dict[str, Any]]:
    base = root / database
    target = base / directory if directory else base
    if not target.is_dir():
        return []
    result = []
    for path in sorted(target.iterdir(), key=lambda item: item.name):
        if not is_signature(path):
            continue
        result.append(
            {
                "database": database,
                "name": path.name,
                "path": path.relative_to(root).as_posix(),
                "priority_candidate": priority_candidate(path.name),
                "sha256": sha256(path),
                "size": path.stat().st_size,
            }
        )
    return result


def first_named(
    layered_records: Iterable[list[dict[str, Any]]],
    name: str,
    *,
    case_insensitive: bool = False,
) -> dict[str, Any] | None:
    expected = name.casefold() if case_insensitive else name
    for layer in layered_records:
        for record in layer:
            actual = (
                record["name"].casefold()
                if case_insensitive
                else record["name"]
            )
            if actual == expected:
                return record
    return None


def include_sites(path: Path) -> tuple[list[str], int]:
    text = path.read_text(encoding="utf-8")
    return (
        [match.group(2) for match in INCLUDE_RE.finditer(text)],
        len(INCLUDE_SITE_RE.findall(text)),
    )


def build_manifest(repo: Path) -> dict[str, Any]:
    rules_root = repo / "upstream" / "Detect-It-Easy"
    root_layers = [records(rules_root, database, "") for database in DATABASES]
    binary_layers = [
        records(rules_root, database, "Binary") for database in DATABASES
    ]

    global_init = first_named(root_layers, "_init")
    type_init = first_named(binary_layers, "_init")
    if global_init is None or type_init is None:
        raise RuntimeError("fixed rules must contain global and Binary _init")

    include_calls: list[dict[str, Any]] = []
    non_literal_include_sites: list[dict[str, Any]] = []
    scanned = [global_init, type_init]
    scanned.extend(
        record
        for layer in binary_layers
        for record in layer
        if record["name"] != "_init"
    )
    for caller in scanned:
        targets, site_count = include_sites(rules_root / caller["path"])
        if site_count != len(targets):
            non_literal_include_sites.append(
                {
                    "caller": caller["path"],
                    "literal_count": len(targets),
                    "site_count": site_count,
                }
            )
        for target in targets:
            resolved = first_named(
                root_layers, target, case_insensitive=True
            )
            include_calls.append(
                {
                    "caller": caller["path"],
                    "target": target,
                    "resolved_path": (
                        resolved["path"] if resolved is not None else None
                    ),
                }
            )

    main_names = [record["name"] for record in binary_layers[0]]
    witnesses = find_cycle_witnesses(main_names)
    return {
        "schema_version": 1,
        "generator": "tools/rules/analyze_binary_lifecycle.py",
        "upstream_commit": UPSTREAM_COMMIT,
        "rules_commit": RULES_COMMIT,
        "source_evidence": SOURCE_EVIDENCE,
        "load_protocol": {
            "database_append_order": list(DATABASES),
            "sort_scope": "each database independently before append",
            "signature_filter": "regular file with .sg or no extension",
            "include_lookup": (
                "first case-insensitive name match among FT_UNKNOWN records"
            ),
            "engine_scope": "one shared script engine per processDetect call",
        },
        "binary": {
            "records_by_database": {
                database: layer
                for database, layer in zip(DATABASES, binary_layers)
            },
            "executable_count_by_database": {
                database: sum(
                    record["name"] != "_init" for record in layer
                )
                for database, layer in zip(DATABASES, binary_layers)
            },
            "selected_global_init": global_init,
            "selected_type_init": type_init,
            "literal_include_calls": include_calls,
            "literal_include_call_count": len(include_calls),
            "non_literal_include_sites": non_literal_include_sites,
            "missing_literal_includes": [
                call for call in include_calls if call["resolved_path"] is None
            ],
        },
        "ordering_risk": {
            "default_priority": "9",
            "priority_is_compared_only_when_both_names_have_more_than_one_dot": True,
            "comparison_is_lexicographic": True,
            "strict_weak_ordering_satisfied": not witnesses,
            "cycle_witnesses": witnesses,
            "consequence": (
                "std::sort ordering is not portable when cycle witnesses exist"
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    document = json.dumps(
        build_manifest(args.repo.resolve()),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    if args.output:
        args.output.write_text(document, encoding="utf-8", newline="\n")
    else:
        print(document, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
