#!/usr/bin/env python3
"""Probe pinned Qt5 CLI escaping and nested formatter ordering."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import pathlib
import subprocess
import sys
import xml.etree.ElementTree as element_tree

import compare_cli_oracles as shared


FORMAT_ARGS = {
    "json": "--json",
    "xml": "--xml",
    "csv": "--csv",
    "tsv": "--tsv",
    "plaintext": "--plaintext",
}
CASE_IDS = tuple(
    f"{scope}_{format_name}"
    for scope in ("escaping", "nested")
    for format_name in FORMAT_ARGS
)
UPSTREAM_SOURCE_PATHS = (
    "/opt/die-source/src/console/main_console.cpp",
    "/opt/die-source/XScanEngine/scanitemmodel.cpp",
    "/opt/die-source/XScanEngine/scanitemmodel.h",
    "/opt/die-source/die_script/die_scriptengine.cpp",
)
NESTED_LEAF_RECORDS = (
    {
        "type": "Unknown",
        "name": "Unknown",
        "version": "",
        "info": "",
        "string": "Unknown: Unknown",
    },
    {
        "type": "format",
        "name": "PDF",
        "version": "1.4",
        "info": "",
        "string": "Format: PDF(1.4)",
    },
    {
        "type": "complier",
        "name": "HeaderComment",
        "version": "e2e3cfd3",
        "info": "",
        "string": "Complier: HeaderComment(e2e3cfd3)",
    },
)


class ProbeError(ValueError):
    """The fixture or oracle output does not match the closed contract."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def image_identity(image: str) -> tuple[str, str]:
    result = subprocess.run(
        ["docker", "image", "inspect", image],
        check=True,
        capture_output=True,
        text=True,
    )
    document = json.loads(result.stdout)[0]
    return (
        document["Id"],
        document["Config"]["Labels"][
            "org.opencontainers.image.revision"
        ],
    )


def image_file_sha256(image: str, path: str) -> str:
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            image,
            "sha256sum",
            path,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    fields = result.stdout.split()
    if len(fields) != 2 or fields[1] != path:
        raise ProbeError(f"unexpected sha256sum output for {path}")
    return fields[0]


def reject_duplicate_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProbeError(f"duplicate manifest key: {key}")
        result[key] = value
    return result


def load_output_fixture(
    fixture_dir: pathlib.Path,
) -> tuple[dict[str, object], bytes]:
    manifest_path = fixture_dir / "manifest.json"
    raw = manifest_path.read_bytes()
    try:
        manifest = json.loads(
            raw,
            object_pairs_hook=reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProbeError(f"invalid output fixture manifest: {error}") from error
    required = {
        "schema_version",
        "generator",
        "license",
        "directories",
        "expected_records",
        "entries",
    }
    if set(manifest) != required:
        raise ProbeError("output fixture manifest fields changed")
    if (
        manifest["schema_version"] != 1
        or manifest["generator"]
        != "tools/corpus/generate_output_boundary_fixture.py"
    ):
        raise ProbeError("output fixture identity changed")
    expected_directories = {
        "database",
        "database/Binary",
        "input",
    }
    if (
        not isinstance(manifest["directories"], list)
        or set(manifest["directories"]) != expected_directories
        or len(manifest["directories"]) != len(expected_directories)
    ):
        raise ProbeError("output fixture directory inventory changed")
    for relative_name in expected_directories:
        path = fixture_dir / pathlib.PurePosixPath(relative_name)
        if not path.is_dir() or path.is_symlink():
            raise ProbeError(
                f"fixture directory mismatch: {relative_name}"
            )
    records = manifest["expected_records"]
    if not isinstance(records, list) or len(records) != 3:
        raise ProbeError("output fixture record inventory changed")
    for record in records:
        if (
            not isinstance(record, dict)
            or set(record) != {"type", "name", "version", "info"}
            or not all(isinstance(value, str) for value in record.values())
        ):
            raise ProbeError("invalid expected output record")

    expected_paths = {
        "database/Binary/output-boundary.1.sg",
        "input/plain.bin",
    }
    actual_paths = set()
    for entry in manifest["entries"]:
        if (
            not isinstance(entry, dict)
            or set(entry)
            != {"path", "purpose", "source", "size", "sha256"}
            or entry["source"] != "project-generated"
        ):
            raise ProbeError("invalid output fixture entry")
        relative = pathlib.PurePosixPath(entry["path"])
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or "\\" in entry["path"]
        ):
            raise ProbeError(f"unsafe fixture path: {entry['path']}")
        path = fixture_dir / relative
        if path.is_symlink() or not path.is_file():
            raise ProbeError(f"fixture file missing: {entry['path']}")
        data = path.read_bytes()
        if (
            len(data) != entry["size"]
            or sha256_bytes(data) != entry["sha256"]
        ):
            raise ProbeError(f"fixture identity mismatch: {entry['path']}")
        actual_paths.add(entry["path"])
    if actual_paths != expected_paths:
        raise ProbeError("output fixture file inventory changed")
    discovered = {
        path.relative_to(fixture_dir).as_posix()
        for path in fixture_dir.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    if discovered != expected_paths:
        raise ProbeError("undeclared output fixture file")
    return manifest, raw


def case_arguments(
    case_id: str,
) -> tuple[list[str], str]:
    scope, format_name = case_id.split("_", 1)
    arguments = [FORMAT_ARGS[format_name]]
    if scope == "escaping":
        arguments.extend(
            [
                "--database",
                "/outfx/database",
                "--extradatabase",
                "/outfx/missing-extra",
                "--customdatabase",
                "/outfx/missing-custom",
                "/outfx/input/plain.bin",
            ]
        )
    else:
        arguments.extend(
            [
                "--recursivescan",
                "--database",
                "/opt/die-source/Detect-It-Easy/db",
                "--extradatabase",
                "/opt/die-source/Detect-It-Easy/db_extra",
                "--customdatabase",
                "/opt/die-source/Detect-It-Easy/db_custom",
                "/nested/pe-pdf-resource.exe",
            ]
        )
    return arguments, format_name


def observe(
    image: str,
    binary: str,
    output_fixture: pathlib.Path,
    nested_fixture: pathlib.Path,
    arguments: list[str],
) -> shared.Observation:
    command = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--cpus",
        "1",
        "--memory",
        "512m",
        "--pids-limit",
        "128",
        "--mount",
        (
            f"type=bind,source={output_fixture},"
            "target=/outfx,readonly"
        ),
        "--mount",
        (
            f"type=bind,source={nested_fixture},"
            "target=/nested,readonly"
        ),
        image,
        binary,
        *arguments,
    ]
    result = subprocess.run(command, check=False, capture_output=True)
    return shared.Observation(
        result.returncode,
        result.stdout,
        result.stderr,
    )


def serialize_observation(
    observation: shared.Observation,
) -> dict[str, object]:
    result = observation.summary()
    result.update(
        {
            "stdout_base64": base64.b64encode(
                observation.stdout
            ).decode("ascii"),
            "stderr_base64": base64.b64encode(
                observation.stderr
            ).decode("ascii"),
        }
    )
    return result


def parse_json(raw: bytes) -> dict[str, object]:
    value = json.loads(
        raw,
        object_pairs_hook=reject_duplicate_keys,
    )
    if not isinstance(value, dict):
        raise ProbeError("formatter JSON root is not an object")
    return value


def escaping_facts(
    observations: dict[str, shared.Observation],
    expected_records: list[dict[str, str]],
) -> dict[str, object]:
    json_raw = observations["escaping_json"].stdout
    json_document = parse_json(json_raw)
    values = json_document["detects"][0]["values"]
    projected = [
        {
            field: value[field]
            for field in ("type", "name", "version", "info")
        }
        for value in values
    ]

    xml_raw = observations["escaping_xml"].stdout
    xml_root = element_tree.fromstring(xml_raw)
    xml_records = [
        {
            field: element.attrib[field]
            for field in ("type", "name", "version", "info")
        }
        for element in xml_root.findall("./Binary/detect")
    ]

    special_utf8 = expected_records[0]["name"].encode("utf-8")
    unicode_utf8 = "☃中😀".encode("utf-8")
    csv_raw = observations["escaping_csv"].stdout
    tsv_raw = observations["escaping_tsv"].stdout
    plaintext_raw = observations["escaping_plaintext"].stdout
    return {
        "json_record_fields_exact": projected == expected_records,
        "json_uses_valid_escaping": (
            b'\\"' in json_raw
            and b"\\n" in json_raw
            and b"\\r" in json_raw
            and b"\\t" in json_raw
            and b"\x00" not in json_raw
            and unicode_utf8 in json_raw
        ),
        "xml_record_attributes_exact": xml_records == expected_records,
        "xml_uses_entities_for_attribute_boundaries": all(
            token in xml_raw
            for token in (
                b"&quot;",
                b"&#9;",
                b"&#10;",
                b"&#13;",
                b"&lt;",
                b"&gt;",
                b"&amp;",
            )
        ),
        "csv_is_unquoted_and_delimiter_ambiguous": (
            b'"Quote""' not in csv_raw
            and len(csv_raw.splitlines()) > len(expected_records)
            and csv_raw.startswith(b'format;Quote"')
            and special_utf8 in csv_raw
        ),
        "tsv_is_unquoted_and_delimiter_ambiguous": (
            len(tsv_raw.splitlines()) > len(expected_records)
            and tsv_raw.startswith(b'format\tQuote"')
            and special_utf8 in tsv_raw
        ),
        "plaintext_preserves_raw_field_controls": (
            b"Binary\n    Format: Quote\"" in plaintext_raw
            and len(plaintext_raw.splitlines()) > 4
            and special_utf8 in plaintext_raw
        ),
        "record_order_is_format_compiler_tool": [
            record["type"] for record in projected
        ]
        == ["format", "compiler", "tool"],
    }


def nested_facts(
    observations: dict[str, shared.Observation],
) -> dict[str, object]:
    document = parse_json(observations["nested_json"].stdout)
    root = document["detects"][0]
    child = root["values"][1]
    json_order = [
        root["values"][0]["string"],
        child["values"][0]["string"],
        child["values"][1]["string"],
    ]

    xml_raw = observations["nested_xml"].stdout
    try:
        element_tree.fromstring(xml_raw)
        xml_well_formed = True
    except element_tree.ParseError:
        xml_well_formed = False
    xml_markers = (
        b"Unknown: Unknown",
        b"<Resource: PDF[",
        b"Format: PDF(1.4)",
        b"Complier: HeaderComment(e2e3cfd3)",
    )
    xml_positions = [xml_raw.find(marker) for marker in xml_markers]

    csv_lines = observations["nested_csv"].stdout.decode(
        "utf-8"
    ).strip().splitlines()
    expected_csv = [
        ";".join(record[field] for field in (
            "type",
            "name",
            "version",
            "info",
            "string",
        ))
        for record in NESTED_LEAF_RECORDS
    ]
    tsv_lines = observations["nested_tsv"].stdout.decode(
        "utf-8"
    ).strip().splitlines()
    expected_tsv = [
        "\t".join(record[field] for field in (
            "type",
            "name",
            "version",
            "info",
            "string",
        ))
        for record in NESTED_LEAF_RECORDS
    ]
    plaintext_lines = observations["nested_plaintext"].stdout.decode(
        "utf-8"
    ).strip().splitlines()
    return {
        "json_preserves_parent_child_and_leaf_order": (
            root["filetype"] == "PE32"
            and root["values"][0]["name"] == "Unknown"
            and child["filetype"] == "PDF"
            and child["parentfilepart"] == "Resource"
            and child["offset"] == "608"
            and child["size"] == "331"
            and json_order
            == [record["string"] for record in NESTED_LEAF_RECORDS]
        ),
        "xml_dynamic_nested_element_is_not_well_formed": (
            not xml_well_formed
            and all(position >= 0 for position in xml_positions)
            and xml_positions == sorted(xml_positions)
        ),
        "csv_flattens_depth_first_and_omits_parent_nodes": (
            csv_lines == expected_csv
        ),
        "tsv_flattens_depth_first_and_omits_parent_nodes": (
            tsv_lines == expected_tsv
        ),
        "plaintext_preserves_depth_first_indentation": (
            plaintext_lines
            == [
                "PE32",
                "    Unknown: Unknown",
                "    Resource: PDF[Offset=0x0260,Size=0x014b]",
                "        Format: PDF(1.4)",
                "        Complier: HeaderComment(e2e3cfd3)",
            ]
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--left-image", required=True)
    parser.add_argument("--left-binary", required=True)
    parser.add_argument("--right-image", required=True)
    parser.add_argument("--right-binary", required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument(
        "--output-fixture-dir",
        required=True,
        type=pathlib.Path,
    )
    parser.add_argument(
        "--nested-corpus-dir",
        required=True,
        type=pathlib.Path,
    )
    parser.add_argument("--output", type=pathlib.Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_fixture = args.output_fixture_dir.resolve()
    nested_fixture = args.nested_corpus_dir.resolve()
    output_manifest, output_manifest_raw = load_output_fixture(
        output_fixture
    )
    nested_samples = shared.load_nested_corpus(nested_fixture)
    nested_manifest_path = nested_fixture / "manifest.json"

    left_id, left_revision = image_identity(args.left_image)
    right_id, right_revision = image_identity(args.right_image)
    failures = []
    if left_revision != args.expected_revision:
        failures.append("left_revision")
    if right_revision != args.expected_revision:
        failures.append("right_revision")

    source_hashes = {}
    for path in UPSTREAM_SOURCE_PATHS:
        left_hash = image_file_sha256(args.left_image, path)
        right_hash = image_file_sha256(args.right_image, path)
        if left_hash != right_hash:
            failures.append(f"source_hash.{path}")
        source_hashes[path] = left_hash

    binary_hashes = {
        "left": image_file_sha256(args.left_image, args.left_binary),
        "right": image_file_sha256(
            args.right_image,
            args.right_binary,
        ),
    }
    case_records = []
    left_observations = {}
    for case_id in CASE_IDS:
        arguments, format_name = case_arguments(case_id)
        left = observe(
            args.left_image,
            args.left_binary,
            output_fixture,
            nested_fixture,
            arguments,
        )
        right = observe(
            args.right_image,
            args.right_binary,
            output_fixture,
            nested_fixture,
            arguments,
        )
        left_observations[case_id] = left
        equal = left == right
        if not equal:
            failures.append(f"case.{case_id}.oracle_difference")
        if left.exit_code != 0:
            failures.append(f"case.{case_id}.exit_code")
        if left.stderr:
            failures.append(f"case.{case_id}.stderr")
        case_records.append(
            {
                "id": case_id,
                "scope": case_id.split("_", 1)[0],
                "format": format_name,
                "arguments": arguments,
                "left": serialize_observation(left),
                "right": serialize_observation(right),
                "oracles_equal": equal,
            }
        )

    facts = {
        **escaping_facts(
            left_observations,
            output_manifest["expected_records"],
        ),
        **nested_facts(left_observations),
    }
    failures.extend(
        f"fact.{name}"
        for name, value in facts.items()
        if value is not True
    )

    root = pathlib.Path(__file__).resolve().parents[2]
    local_sources = {
        "probe": pathlib.Path(__file__).resolve(),
        "fixture_generator": (
            root
            / "tools"
            / "corpus"
            / "generate_output_boundary_fixture.py"
        ),
        "nested_generator": (
            root / "tools" / "corpus" / "generate_nested_corpus.py"
        ),
        "shared_helper": pathlib.Path(shared.__file__).resolve(),
    }
    report = {
        "schema_version": 1,
        "generator": (
            "tools/upstream/probe_cli_output_boundaries.py"
        ),
        "generator_sha256": sha256_bytes(
            pathlib.Path(__file__).read_bytes()
        ),
        "expected_revision": args.expected_revision,
        "left": {
            "image": args.left_image,
            "image_id": left_id,
            "image_revision": left_revision,
            "binary": args.left_binary,
            "binary_sha256": binary_hashes["left"],
        },
        "right": {
            "image": args.right_image,
            "image_id": right_id,
            "image_revision": right_revision,
            "binary": args.right_binary,
            "binary_sha256": binary_hashes["right"],
        },
        "resource_limits": {
            "network": "none",
            "cpus": 1,
            "memory_bytes": 536870912,
            "pids": 128,
            "fixtures": ["/outfx", "/nested"],
            "mount_mode": "read-only",
        },
        "upstream_source_hashes": source_hashes,
        "local_source_hashes": {
            name: sha256_bytes(path.read_bytes())
            for name, path in local_sources.items()
        },
        "output_fixture_manifest_sha256": sha256_bytes(
            output_manifest_raw
        ),
        "nested_fixture_manifest_sha256": sha256_bytes(
            nested_manifest_path.read_bytes()
        ),
        "nested_fixture_sample_count": len(
            nested_samples
        ),
        "cases": case_records,
        "facts": facts,
        "failures": failures,
        "passed": not failures,
    }
    serialized = (
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    if args.output is None:
        sys.stdout.buffer.write(serialized.encode("utf-8"))
    else:
        args.output.write_text(
            serialized,
            encoding="utf-8",
            newline="\n",
        )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
