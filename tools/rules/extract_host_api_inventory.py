#!/usr/bin/env python3
"""Extract the pinned XScanEngine script HostApi and compare rule call shapes."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
GENERATOR_VERSION = 1
UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
XSCANENGINE_COMMIT = "dfe4a419e4f491bb23688ba03c5a5bf39e34da83"
XSCANENGINE_LICENSE_SHA256 = (
    "ac4f868b0034a4047dd1394409e412a25b03013a42f75f20fb0a4f9b4692a827"
)
RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"


@dataclass(frozen=True)
class ClassBlock:
    name: str
    parent: str
    body: str
    body_start_line: int


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def normalize_space(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"\s*([*&])\s*", r" \1", value)
    return value


def strip_comments(source: str) -> str:
    result: list[str] = []
    index = 0
    state = "code"
    quote = ""
    while index < len(source):
        current = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""
        if state == "code":
            if current == "/" and following == "/":
                result.extend((" ", " "))
                index += 2
                state = "line_comment"
                continue
            if current == "/" and following == "*":
                result.extend((" ", " "))
                index += 2
                state = "block_comment"
                continue
            if current in {'"', "'"}:
                quote = current
                state = "string"
            result.append(current)
            index += 1
            continue
        if state == "line_comment":
            if current == "\n":
                result.append("\n")
                state = "code"
            else:
                result.append(" ")
            index += 1
            continue
        if state == "block_comment":
            if current == "*" and following == "/":
                result.extend((" ", " "))
                index += 2
                state = "code"
            else:
                result.append("\n" if current == "\n" else " ")
                index += 1
            continue
        result.append(current)
        if current == "\\" and following:
            result.append(following)
            index += 2
            continue
        if current == quote:
            state = "code"
        index += 1
    return "".join(result)


def find_matching_brace(source: str, opening: int) -> int:
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    raise ValueError("unterminated class body")


def find_class(source: str, path: str) -> ClassBlock:
    clean = strip_comments(source)
    matches = list(
        re.finditer(
            r"\bclass\s+(?:[A-Za-z_]\w*\s+)?"
            r"(?P<name>[A-Za-z_]\w*_Script)\s*"
            r":\s*public\s+(?P<parent>[A-Za-z_:]\w*)\s*\{",
            clean,
        )
    )
    if len(matches) != 1:
        raise ValueError(f"{path}: expected one *_Script class, found {len(matches)}")
    match = matches[0]
    opening = clean.find("{", match.start(), match.end())
    closing = find_matching_brace(clean, opening)
    return ClassBlock(
        name=match.group("name"),
        parent=match.group("parent"),
        body=clean[opening + 1 : closing],
        body_start_line=clean.count("\n", 0, opening + 1) + 1,
    )


def split_top_level(value: str, delimiter: str) -> list[str]:
    result: list[str] = []
    start = 0
    round_depth = 0
    angle_depth = 0
    square_depth = 0
    brace_depth = 0
    quote: str | None = None
    index = 0
    while index < len(value):
        current = value[index]
        if quote:
            if current == "\\":
                index += 2
                continue
            if current == quote:
                quote = None
            index += 1
            continue
        if current in {'"', "'"}:
            quote = current
        elif current == "(":
            round_depth += 1
        elif current == ")":
            round_depth -= 1
        elif current == "<":
            angle_depth += 1
        elif current == ">" and angle_depth:
            angle_depth -= 1
        elif current == "[":
            square_depth += 1
        elif current == "]":
            square_depth -= 1
        elif current == "{":
            brace_depth += 1
        elif current == "}":
            brace_depth -= 1
        elif (
            current == delimiter
            and round_depth == 0
            and angle_depth == 0
            and square_depth == 0
            and brace_depth == 0
        ):
            result.append(value[start:index].strip())
            start = index + 1
        index += 1
    result.append(value[start:].strip())
    return result


def split_default(parameter: str) -> tuple[str, str | None]:
    parts = split_top_level(parameter, "=")
    if len(parts) == 1:
        return parts[0], None
    if len(parts) != 2:
        raise ValueError(f"unsupported parameter default: {parameter}")
    return parts[0], parts[1]


def parse_parameter(parameter: str) -> dict[str, Any]:
    declaration, default = split_default(parameter)
    match = re.match(r"^(?P<type>.+?)(?P<name>[A-Za-z_]\w*)$", declaration.strip())
    if not match:
        raise ValueError(f"cannot parse parameter: {parameter}")
    type_name = normalize_space(match.group("type"))
    if not type_name:
        raise ValueError(f"missing parameter type: {parameter}")
    return {
        "name": match.group("name"),
        "type": type_name,
        "default": normalize_space(default) if default is not None else None,
    }


def slot_sections(class_block: ClassBlock) -> list[tuple[str, int]]:
    body = class_block.body
    section_pattern = re.compile(
        r"(?m)^\s*(public|protected|private)(?:\s+slots)?\s*:"
    )
    labels = list(section_pattern.finditer(body))
    sections: list[tuple[str, int]] = []
    for index, label in enumerate(labels):
        if normalize_space(label.group(0)).replace(" ", "") != "publicslots:":
            continue
        start = label.end()
        end = labels[index + 1].start() if index + 1 < len(labels) else len(body)
        line = class_block.body_start_line + body.count("\n", 0, start)
        sections.append((body[start:end], line))
    return sections


def parse_slot_declaration(
    declaration: str, class_name: str, path: str, line: int
) -> dict[str, Any]:
    declaration = normalize_space(declaration)
    declaration = re.sub(r"^Q_INVOKABLE\s+", "", declaration)
    match = re.match(
        r"^(?P<return>.+?)\s+(?P<name>[A-Za-z_]\w*)\s*"
        r"\((?P<parameters>.*)\)\s*(?P<const>const\b)?"
        r"\s*(?:=\s*0)?$",
        declaration,
    )
    if not match:
        raise ValueError(f"{path}:{line}: cannot parse slot: {declaration}")
    return_text = normalize_space(match.group("return"))
    is_virtual = bool(re.search(r"\bvirtual\b", return_text))
    return_type = normalize_space(re.sub(r"\bvirtual\b", "", return_text))
    raw_parameters = match.group("parameters").strip()
    parameters = (
        []
        if not raw_parameters or raw_parameters == "void"
        else [
            parse_parameter(item)
            for item in split_top_level(raw_parameters, ",")
        ]
    )
    seen_default = False
    for parameter in parameters:
        if parameter["default"] is not None:
            seen_default = True
        elif seen_default:
            raise ValueError(
                f"{path}:{line}: non-default parameter follows default"
            )
    minimum_arity = sum(
        parameter["default"] is None for parameter in parameters
    )
    return {
        "class": class_name,
        "name": match.group("name"),
        "return_type": return_type,
        "virtual": is_virtual,
        "const": bool(match.group("const")),
        "parameters": parameters,
        "minimum_arity": minimum_arity,
        "maximum_arity": len(parameters),
        "declaration": declaration,
        "path": path,
        "line": line,
    }


def parse_header(source: str, path: str) -> dict[str, Any]:
    class_block = find_class(source, path)
    methods: list[dict[str, Any]] = []
    for section, section_line in slot_sections(class_block):
        offset = 0
        for declaration in split_top_level(section, ";"):
            if not declaration:
                continue
            declaration_start = section.find(declaration, offset)
            offset = declaration_start + len(declaration)
            line = section_line + section.count("\n", 0, declaration_start)
            methods.append(
                parse_slot_declaration(
                    declaration, class_block.name, path, line
                )
            )
    properties = [
        normalize_space(match.group(1))
        for match in re.finditer(r"\bQ_PROPERTY\s*\((.*?)\)", class_block.body)
    ]
    return {
        "name": class_block.name,
        "parent": class_block.parent,
        "path": path,
        "direct_method_count": len(methods),
        "methods": methods,
        "properties": properties,
    }


def validate_inheritance(classes: dict[str, dict[str, Any]]) -> None:
    for class_name in classes:
        seen: set[str] = set()
        current = class_name
        while current in classes:
            if current in seen:
                raise ValueError(f"inheritance cycle at {class_name}")
            seen.add(current)
            current = classes[current]["parent"]
        if current != "QObject":
            raise ValueError(f"{class_name}: unknown parent {current}")


def inherited_methods(
    class_name: str, classes: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    lineage: list[str] = []
    current = class_name
    while current in classes:
        lineage.append(current)
        current = classes[current]["parent"]
    result: list[dict[str, Any]] = []
    for name in reversed(lineage):
        result.extend(classes[name]["methods"])
    return result


def class_receiver(class_name: str) -> str:
    value = class_name.removesuffix("_Script")
    return "JPEG" if value == "Jpeg" else value


def method_covers_arity(method: dict[str, Any], arity: int) -> bool:
    return method["minimum_arity"] <= arity <= method["maximum_arity"]


def compare_rule_calls(
    classes: dict[str, dict[str, Any]], rule_inventory: dict[str, Any]
) -> dict[str, Any]:
    receiver_classes = {
        class_receiver(name): name for name in sorted(classes)
    }
    all_class_names = sorted(classes)
    observations = rule_inventory["calls"]["known_host"]
    script_extensions = rule_inventory.get(
        "known_receiver_script_extensions", []
    )
    extensions_by_receiver_method = {
        (item["receiver_root"], item["member"]): item
        for item in script_extensions
    }
    records: list[dict[str, Any]] = []
    missing_methods = 0
    uncovered_arities = 0
    covered_arities = 0
    cpp_covered_arities = 0
    script_covered_arities = 0
    for observation in observations:
        receiver = observation["receiver_root"]
        if receiver in {"File", "X"}:
            candidate_classes = all_class_names
            mapping = "all_format_classes_alias_union"
        elif receiver in receiver_classes:
            candidate_classes = [receiver_classes[receiver]]
            mapping = "exact_receiver_class"
        else:
            candidate_classes = []
            mapping = "unmapped_receiver"
        candidates = [
            method
            for candidate_class in candidate_classes
            for method in inherited_methods(candidate_class, classes)
            if method["name"] == observation["method"]
        ]
        arities = sorted(int(value) for value in observation["arity_counts"])
        if receiver in {"File", "X"}:
            extension_candidates = [
                item
                for (extension_receiver, member), item in (
                    extensions_by_receiver_method.items()
                )
                if member == observation["method"]
            ]
        else:
            extension = extensions_by_receiver_method.get(
                (receiver, observation["method"])
            )
            extension_candidates = [extension] if extension else []
        arity_resolutions = {}
        uncovered = []
        for arity in arities:
            if extension_candidates:
                arity_resolutions[str(arity)] = "script_extension"
                script_covered_arities += 1
            elif any(
                method_covers_arity(method, arity)
                for method in candidates
            ):
                arity_resolutions[str(arity)] = "cpp_declared_range"
                cpp_covered_arities += 1
            else:
                arity_resolutions[str(arity)] = "uncovered"
                uncovered.append(arity)
        if not candidates and not extension_candidates:
            missing_methods += 1
        uncovered_arities += len(uncovered)
        covered_arities += len(arities) - len(uncovered)
        records.append(
            {
                "receiver_root": receiver,
                "method": observation["method"],
                "mapping": mapping,
                "candidate_classes": candidate_classes,
                "observed_arity_counts": observation["arity_counts"],
                "declared_candidate_count": len(candidates),
                "declared_ranges": sorted(
                    {
                        (
                            method["class"],
                            method["minimum_arity"],
                            method["maximum_arity"],
                        )
                        for method in candidates
                    }
                ),
                "script_extension_candidate_count": len(
                    extension_candidates
                ),
                "script_extensions": extension_candidates,
                "arity_resolutions": arity_resolutions,
                "uncovered_arities": uncovered,
                "first_location": observation["first_location"],
            }
        )
    return {
        "observed_receiver_method_count": len(observations),
        "observed_arity_shape_count": sum(
            len(item["arity_counts"]) for item in observations
        ),
        "covered_arity_shape_count": covered_arities,
        "cpp_covered_arity_shape_count": cpp_covered_arities,
        "script_extension_covered_arity_shape_count":
            script_covered_arities,
        "uncovered_arity_shape_count": uncovered_arities,
        "missing_method_record_count": missing_methods,
        "records": records,
        "mapping_boundary": (
            "named format receivers map to their exact *_Script class with "
            "inheritance; File and X are runtime aliases and are conservatively "
            "compared against the union of all format classes; first-level "
            "JavaScript function extensions are an independent coverage layer "
            "and shadow same-name C++ slots after init while using normal "
            "JavaScript permissive call arity"
        ),
    }


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


def build_inventory(
    xscanengine_root: Path,
    rule_inventory_path: Path,
    *,
    enforce_identity: bool = True,
) -> dict[str, Any]:
    if enforce_identity:
        revision = run_git(xscanengine_root, "rev-parse", "HEAD")
        if revision != XSCANENGINE_COMMIT:
            raise ValueError(
                f"XScanEngine revision mismatch: expected {XSCANENGINE_COMMIT}, "
                f"got {revision}"
            )
        license_hash = sha256_bytes(
            (xscanengine_root / "LICENSE").read_bytes()
        )
        if license_hash != XSCANENGINE_LICENSE_SHA256:
            raise ValueError("XScanEngine LICENSE hash mismatch")
    headers = sorted(
        (xscanengine_root / "modules").glob("*_script.h"),
        key=lambda item: item.name,
    )
    if not headers:
        raise ValueError("no *_script.h headers found")
    header_manifest = []
    classes: dict[str, dict[str, Any]] = {}
    for header in headers:
        relative_path = header.relative_to(xscanengine_root).as_posix()
        content = header.read_bytes()
        parsed = parse_header(content.decode("utf-8-sig"), relative_path)
        if parsed["name"] in classes:
            raise ValueError(f"duplicate class {parsed['name']}")
        classes[parsed["name"]] = parsed
        header_manifest.append(
            {
                "path": relative_path,
                "bytes": len(content),
                "sha256": sha256_bytes(content),
            }
        )
    validate_inheritance(classes)
    rule_bytes = rule_inventory_path.read_bytes()
    rule_inventory = json.loads(rule_bytes.decode("utf-8-sig"))
    if rule_inventory.get("rules_commit") != RULES_COMMIT:
        raise ValueError("rule syntax inventory commit mismatch")
    comparison = compare_rule_calls(classes, rule_inventory)
    manifest_bytes = "\n".join(
        f"{item['path']}\0{item['bytes']}\0{item['sha256']}"
        for item in header_manifest
    ).encode()
    class_records = []
    for name in sorted(classes):
        record = classes[name]
        effective = inherited_methods(name, classes)
        class_records.append(
            {
                **record,
                "effective_method_count": len(effective),
                "lineage": [
                    method_class
                    for method_class in _lineage(name, classes)
                ],
            }
        )
    generator_path = Path(__file__)
    return {
        "schema_version": SCHEMA_VERSION,
        "generator": {
            "path": "tools/rules/extract_host_api_inventory.py",
            "version": GENERATOR_VERSION,
            "sha256": sha256_bytes(generator_path.read_bytes()),
        },
        "upstream_commit": UPSTREAM_COMMIT,
        "xscanengine": {
            "repository": "https://github.com/horsicq/XScanEngine",
            "commit": XSCANENGINE_COMMIT,
            "license": "MIT",
            "license_sha256": XSCANENGINE_LICENSE_SHA256,
            "header_count": len(header_manifest),
            "header_manifest_sha256": sha256_bytes(manifest_bytes),
            "header_manifest_hash_contract": (
                "UTF-8 path NUL byte-count NUL sha256 records joined by LF "
                "without trailing LF, ordinal filename order"
            ),
            "headers": header_manifest,
        },
        "declarations": {
            "class_count": len(classes),
            "direct_slot_method_count": sum(
                len(record["methods"]) for record in classes.values()
            ),
            "property_count": sum(
                len(record["properties"]) for record in classes.values()
            ),
            "classes": class_records,
        },
        "rule_inventory": {
            "path": "docs/research/data/rule-syntax-inventory.json",
            "sha256": sha256_bytes(rule_bytes),
            "rules_commit": RULES_COMMIT,
        },
        "observed_call_coverage": comparison,
        "scope": (
            "public slots and Q_PROPERTY declarations in 30 XScanEngine "
            "*_Script classes, inheritance expansion, and static rule-call "
            "arity coverage; runtime conversion, overload selection, return "
            "semantics, exceptions, and dynamic File/X alias identity are not "
            "proved"
        ),
    }


def _lineage(
    class_name: str, classes: dict[str, dict[str, Any]]
) -> list[str]:
    result = []
    current = class_name
    while current in classes:
        result.append(current)
        current = classes[current]["parent"]
    result.append(current)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--xscanengine-root", required=True, type=Path)
    parser.add_argument("--rule-inventory", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    inventory = build_inventory(
        arguments.xscanengine_root.resolve(),
        arguments.rule_inventory.resolve(),
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
