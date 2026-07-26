#!/usr/bin/env python3
"""Extract pinned non-format script globals and classify direct rule calls."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_host_api_inventory import (  # noqa: E402
    parse_slot_declaration,
    split_top_level,
    strip_comments,
)


SCHEMA_VERSION = 1
GENERATOR_VERSION = 1
UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
DIE_SCRIPT_COMMIT = "5d82316c110abf0eb863b50bc679d330e05067b6"
DIE_SCRIPT_LICENSE_SHA256 = (
    "abdeb212f229d2b93a5c315763df4d7201c7d74f580ad9dc77d77dec7cbc6c69"
)
RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
SOURCE_PATHS = (
    "LICENSE",
    "xscriptengine.cpp",
    "die_scriptengine.cpp",
    "die_scriptengine.h",
    "die_global_script.cpp",
    "die_global_script.h",
)
ECMASCRIPT_GLOBAL_FUNCTIONS = frozenset(
    {
        "Array",
        "Boolean",
        "Date",
        "Error",
        "EvalError",
        "Function",
        "Number",
        "Object",
        "RangeError",
        "ReferenceError",
        "RegExp",
        "String",
        "SyntaxError",
        "TypeError",
        "URIError",
        "decodeURI",
        "decodeURIComponent",
        "encodeURI",
        "encodeURIComponent",
        "escape",
        "eval",
        "isFinite",
        "isNaN",
        "parseFloat",
        "parseInt",
        "unescape",
    }
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def run_git(root: Path, *arguments: str) -> str:
    process = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if process.returncode != 0:
        detail = process.stderr.strip() or process.stdout.strip()
        raise ValueError(f"git {' '.join(arguments)} failed: {detail}")
    return process.stdout.strip()


def parse_global_slots(source: str, path: str) -> list[dict[str, Any]]:
    clean = strip_comments(source)
    match = re.search(
        r"(?ms)^\s*public\s+slots\s*:\s*(?P<body>.*?)^\s*signals\s*:",
        clean,
    )
    if not match:
        raise ValueError(f"{path}: public slots section not found")
    body = match.group("body")
    body_start = clean.count("\n", 0, match.start("body")) + 1
    methods = []
    offset = 0
    for declaration in split_top_level(body, ";"):
        if not declaration:
            continue
        start = body.find(declaration, offset)
        offset = start + len(declaration)
        line = body_start + body.count("\n", 0, start)
        methods.append(
            parse_slot_declaration(
                declaration, "die_global_script", path, line
            )
        )
    return methods


def parse_registrations(source: str) -> dict[str, Any]:
    qt5_pairs = re.findall(
        r'_addFunction\(\s*([A-Za-z_]\w*)\s*,\s*"([^"]+)"\s*\)\s*;',
        source,
    )
    qt6_pairs = re.findall(
        r'globalObject\(\)\.setProperty\(\s*"([^"]+)"\s*,'
        r'\s*valueGlobalScript\.property\(\s*"([^"]+)"\s*\)\s*\)\s*;',
        source,
    )
    if any(symbol != exposed for symbol, exposed in qt5_pairs):
        raise ValueError("Qt5 native symbol/exposed name mismatch")
    if any(exposed != property_name for exposed, property_name in qt6_pairs):
        raise ValueError("Qt6 exposed/property name mismatch")
    return {
        "qt5_qscriptengine": [
            {"name": exposed, "native_symbol": symbol}
            for symbol, exposed in qt5_pairs
        ],
        "qt6_qjsengine": [
            {"name": exposed, "qobject_property": property_name}
            for exposed, property_name in qt6_pairs
        ],
    }


def parse_qt5_wrappers(header: str, implementation: str) -> list[dict[str, Any]]:
    declaration_pattern = re.compile(
        r"(?m)^\s*static\s+QScriptValue\s+(?P<name>[A-Za-z_]\w*)\s*"
        r"\(\s*QScriptContext\s*\*\s*pContext\s*,\s*"
        r"QScriptEngine\s*\*\s*pEngine\s*\)\s*;"
    )
    implementation_pattern = re.compile(
        r"(?m)^QScriptValue\s+DiE_ScriptEngine::(?P<name>[A-Za-z_]\w*)\s*"
        r"\(\s*QScriptContext\s*\*\s*pContext\s*,\s*"
        r"QScriptEngine\s*\*\s*pEngine\s*\)"
    )
    declarations = {
        match.group("name"): header.count("\n", 0, match.start()) + 1
        for match in declaration_pattern.finditer(header)
    }
    implementations = {
        match.group("name"): implementation.count("\n", 0, match.start()) + 1
        for match in implementation_pattern.finditer(implementation)
    }
    if declarations.keys() != implementations.keys():
        raise ValueError("Qt5 wrapper declarations/implementations differ")
    return [
        {
            "name": name,
            "declaration_path": "die_scriptengine.h",
            "declaration_line": declarations[name],
            "implementation_path": "die_scriptengine.cpp",
            "implementation_line": implementations[name],
        }
        for name in declarations
    ]


def aggregate_direct_calls(
    direct_calls: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for call in direct_calls:
        record = result.setdefault(
            call["name"],
            {
                "name": call["name"],
                "count": 0,
                "file_count_upper_bound": 0,
                "arity_counts": {},
                "bindings": {},
                "first_location": call["first_location"],
            },
        )
        record["count"] += call["count"]
        record["file_count_upper_bound"] += call["file_count"]
        record["bindings"][call["binding"]] = call["count"]
        for arity, count in call["arity_counts"].items():
            record["arity_counts"][arity] = (
                record["arity_counts"].get(arity, 0) + count
            )
    return result


def classify_undeclared_calls(
    direct_calls: list[dict[str, Any]],
    native_names: set[str],
    rule_function_names: set[str],
) -> dict[str, Any]:
    records = []
    category_counts: dict[str, int] = {}
    category_call_counts: dict[str, int] = {}
    for call in direct_calls:
        if call["binding"] != "undeclared_global":
            continue
        name = call["name"]
        if name in native_names:
            category = "native_engine_global"
        elif name in rule_function_names:
            category = "rule_top_level_function"
        elif name in ECMASCRIPT_GLOBAL_FUNCTIONS:
            category = "ecmascript_global"
        else:
            category = "unclassified"
        category_counts[category] = category_counts.get(category, 0) + 1
        category_call_counts[category] = (
            category_call_counts.get(category, 0) + call["count"]
        )
        records.append({**call, "classification": category})
    return {
        "name_count": len(records),
        "call_count": sum(item["count"] for item in records),
        "category_name_counts": dict(sorted(category_counts.items())),
        "category_call_counts": dict(sorted(category_call_counts.items())),
        "records": records,
        "boundary": (
            "classification covers only direct calls whose callee is an "
            "undeclared identifier in its individual source file; rule "
            "top-level definitions are a repository-wide candidate union and "
            "do not prove include reachability; unclassified is not silently "
            "treated as HostApi"
        ),
    }


def build_inventory(
    die_script_root: Path,
    rule_inventory_path: Path,
    *,
    enforce_identity: bool = True,
) -> dict[str, Any]:
    if enforce_identity:
        revision = run_git(die_script_root, "rev-parse", "HEAD")
        if revision != DIE_SCRIPT_COMMIT:
            raise ValueError(
                f"die_script revision mismatch: expected {DIE_SCRIPT_COMMIT}, "
                f"got {revision}"
            )
        if run_git(die_script_root, "status", "--short"):
            raise ValueError("die_script checkout is dirty")
        if (
            sha256_bytes((die_script_root / "LICENSE").read_bytes())
            != DIE_SCRIPT_LICENSE_SHA256
        ):
            raise ValueError("die_script LICENSE hash mismatch")

    sources = []
    for relative in SOURCE_PATHS:
        data = (die_script_root / relative).read_bytes()
        sources.append(
            {
                "path": relative,
                "bytes": len(data),
                "sha256": sha256_bytes(data),
            }
        )

    header_path = die_script_root / "die_global_script.h"
    methods = parse_global_slots(
        header_path.read_text(encoding="utf-8-sig"),
        "die_global_script.h",
    )
    engine_header = (die_script_root / "die_scriptengine.h").read_text(
        encoding="utf-8-sig"
    )
    engine_implementation = (
        die_script_root / "die_scriptengine.cpp"
    ).read_text(encoding="utf-8-sig")
    registrations = parse_registrations(engine_implementation)
    qt5_wrappers = parse_qt5_wrappers(
        engine_header, engine_implementation
    )
    declared_names = {method["name"] for method in methods}
    qt5_names = {item["name"] for item in registrations["qt5_qscriptengine"]}
    qt6_names = {item["name"] for item in registrations["qt6_qjsengine"]}
    qt5_wrapper_names = {item["name"] for item in qt5_wrappers}
    if qt6_names != declared_names:
        raise ValueError("Qt6 registrations do not match declared global slots")
    if qt5_names != declared_names - {"_getQtVersion"}:
        raise ValueError("unexpected Qt5 global registration surface")
    if qt5_wrapper_names != qt5_names:
        raise ValueError("Qt5 registrations do not match custom wrappers")

    rule_bytes = rule_inventory_path.read_bytes()
    rule_inventory = json.loads(rule_bytes.decode("utf-8-sig"))
    if rule_inventory.get("rules_commit") != RULES_COMMIT:
        raise ValueError("rule syntax inventory commit mismatch")
    definitions = rule_inventory.get("top_level_function_definitions")
    if definitions is None:
        raise ValueError("rule inventory lacks top-level function definitions")
    direct_by_name = aggregate_direct_calls(rule_inventory["calls"]["direct"])
    native_usage = []
    for method in methods:
        usage = direct_by_name.get(
            method["name"],
            {
                "name": method["name"],
                "count": 0,
                "file_count_upper_bound": 0,
                "arity_counts": {},
                "bindings": {},
                "first_location": None,
            },
        )
        native_usage.append(
            {
                "name": method["name"],
                "declaration": method,
                "qt5_registered": method["name"] in qt5_names,
                "qt6_registered": method["name"] in qt6_names,
                "rule_direct_calls": usage,
            }
        )

    rule_function_names = {item["name"] for item in definitions}
    root_framework_paths = {
        "db/_init",
        "db/_debug",
        "db/_runtime_helpers",
        "db/language",
    }
    root_framework_functions = []
    for definition in definitions:
        if definition["first_location"]["path"] not in root_framework_paths:
            continue
        root_framework_functions.append(
            {
                "definition": definition,
                "rule_direct_calls": direct_by_name.get(
                    definition["name"],
                    {
                        "name": definition["name"],
                        "count": 0,
                        "file_count_upper_bound": 0,
                        "arity_counts": {},
                        "bindings": {},
                        "first_location": None,
                    },
                ),
            }
        )
    classification = classify_undeclared_calls(
        rule_inventory["calls"]["direct"],
        declared_names,
        rule_function_names,
    )
    generator_path = Path(__file__)
    return {
        "schema_version": SCHEMA_VERSION,
        "generator": {
            "path": "tools/rules/extract_global_host_api_inventory.py",
            "version": GENERATOR_VERSION,
            "sha256": sha256_bytes(generator_path.read_bytes()),
        },
        "upstream_commit": UPSTREAM_COMMIT,
        "die_script": {
            "repository": "https://github.com/horsicq/die_script",
            "commit": DIE_SCRIPT_COMMIT,
            "license": "MIT",
            "license_sha256": DIE_SCRIPT_LICENSE_SHA256,
            "sources": sources,
        },
        "native_global_api": {
            "declared_slot_count": len(methods),
            "qt5_registered_count": len(qt5_names),
            "qt6_registered_count": len(qt6_names),
            "qt5_only_omission": sorted(declared_names - qt5_names),
            "qt5_custom_wrappers": qt5_wrappers,
            "methods": native_usage,
            "registration_evidence": registrations,
        },
        "rule_inventory": {
            "path": "docs/research/data/rule-syntax-inventory.json",
            "sha256": sha256_bytes(rule_bytes),
            "rules_commit": RULES_COMMIT,
            "top_level_function_name_count": len(definitions),
            "top_level_function_definition_count": sum(
                item["definition_count"] for item in definitions
            ),
            "root_framework_functions": root_framework_functions,
            "root_framework_paths": sorted(root_framework_paths),
        },
        "undeclared_direct_call_classification": classification,
        "scope": (
            "die_global_script public slots, Qt5/Qt6 constructor registration "
            "surfaces, repository-wide rule top-level function definitions, "
            "and direct undeclared identifier calls; format QObject members, "
            "member calls, non-call global reads/writes, include reachability, "
            "native function behavior, and indirect calls are outside scope"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    repo = Path(__file__).resolve().parents[2]
    parser.add_argument("--die-script-root", type=Path, required=True)
    parser.add_argument(
        "--rule-inventory",
        type=Path,
        default=repo / "docs/research/data/rule-syntax-inventory.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=repo / "docs/research/data/global-host-api-inventory.json",
    )
    args = parser.parse_args()
    inventory = build_inventory(
        args.die_script_root.resolve(),
        args.rule_inventory.resolve(),
    )
    args.output.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
