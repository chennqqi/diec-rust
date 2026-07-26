#!/usr/bin/env python3
"""Probe fixed DIE engine filtering, sorting, cancellation, and entry points."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import subprocess
from typing import Any

from probe_rule_orchestration import load_and_verify_fixture


UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
IMAGE = "diec-rust/engine-contract-harness-qt5:74eaf505"
BINARY = "/opt/die-build/src/console/diec-engine-contract-harness"
SOURCE_PATHS = (
    "/opt/die-source/XScanEngine/xscanengine.h",
    "/opt/die-source/die_script/die_script.h",
    "/opt/die-source/die_script/die_script.cpp",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def docker_bytes(entrypoint: str, *arguments: str) -> bytes:
    process = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network=none",
            "--entrypoint",
            entrypoint,
            IMAGE,
            *arguments,
        ],
        check=True,
        capture_output=True,
    )
    if process.stderr:
        raise ValueError(f"{entrypoint} wrote stderr")
    return process.stdout


def inspect_image() -> tuple[str, str]:
    process = subprocess.run(
        ["docker", "image", "inspect", IMAGE],
        check=True,
        capture_output=True,
    )
    document = json.loads(process.stdout)[0]
    revision = document["Config"]["Labels"].get(
        "org.opencontainers.image.revision", ""
    )
    if revision != UPSTREAM_COMMIT:
        raise ValueError("harness image revision mismatch")
    return document["Id"], revision


def audit_signature_file_path() -> dict[str, Any]:
    sources = {
        path: docker_bytes("/bin/cat", path) for path in SOURCE_PATHS
    }
    header = sources[SOURCE_PATHS[0]].decode("utf-8")
    script_header = sources[SOURCE_PATHS[1]].decode("utf-8")
    implementation = sources[SOURCE_PATHS[2]].decode("utf-8")

    options_match = re.search(
        r"struct\s+SCAN_OPTIONS\s*\{(?P<body>.*?)\n\s*\};",
        header,
        re.DOTALL,
    )
    if options_match is None:
        raise ValueError("SCAN_OPTIONS definition not found")
    options_body = options_match.group("body")
    public_option_absent = "sSignatureFilePath" not in options_body
    name_option_present = "sSignatureName" in options_body
    private_parameter_present = (
        "const QString &sSignatureFilePath" in script_header
    )
    protected_passes_empty = bool(
        re.search(
            r"DiE_Script::_processDetect\(.*?\)\s*\{\s*"
            r"processDetect\(.*?,\s*\"\",\s*bAddUnknown,\s*"
            r"pPdStruct\);\s*\}",
            implementation,
            re.DOTALL,
        )
    )
    call_argument_count = len(
        re.findall(r"\bprocessDetect\s*\(", implementation)
    )
    reachable = not (
        public_option_absent
        and private_parameter_present
        and protected_passes_empty
        and call_argument_count == 2
    )
    if not name_option_present or reachable:
        raise ValueError("signature file-path reachability assumptions changed")

    return {
        "public_scan_options_has_signature_name": name_option_present,
        "public_scan_options_has_signature_file_path": (
            not public_option_absent
        ),
        "private_process_detect_has_signature_file_path": (
            private_parameter_present
        ),
        "protected_process_detect_passes_empty_path": protected_passes_empty,
        "implementation_process_detect_occurrences": call_argument_count,
        "public_runtime_filter_reachable": reachable,
        "sources": {
            path: {
                "bytes": len(data),
                "sha256": sha256(data),
            }
            for path, data in sources.items()
        },
    }


def case_map(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    cases = document["cases"]
    if document["case_count"] != len(cases):
        raise ValueError("harness case count mismatch")
    result = {case["id"]: case for case in cases}
    if len(result) != len(cases):
        raise ValueError("duplicate harness case id")
    return result


def names(case: dict[str, Any]) -> list[str]:
    return [record["name"] for record in case["records"]]


def validate(document: dict[str, Any]) -> dict[str, bool]:
    if document["upstream_commit"] != UPSTREAM_COMMIT:
        raise ValueError("harness upstream commit mismatch")
    cases = case_map(document)
    expected_ids = {
        "filter_all",
        "filter_exact_extra",
        "filter_missing",
        "filter_case_mismatch",
        "filter_deep_disabled",
        "filter_deep_enabled",
        "sort_disabled",
        "sort_enabled",
        "callback_continue",
        "callback_stop_first",
        "break_scan",
        "pre_stopped",
        "entry_file",
        "entry_memory",
        "entry_device",
        "entry_subdevice",
    }
    if set(cases) != expected_ids:
        raise ValueError("unexpected harness case inventory")

    relationships = {
        "signature_name_exact_match_selects_one_rule": (
            names(cases["filter_exact_extra"]) == ["Extra normal"]
        ),
        "signature_name_is_case_sensitive": (
            names(cases["filter_case_mismatch"]) == ["Unknown"]
        ),
        "missing_signature_adds_unknown": (
            names(cases["filter_missing"]) == ["Unknown"]
        ),
        "deep_filter_still_applies_to_exact_name": (
            names(cases["filter_deep_disabled"]) == ["Unknown"]
            and names(cases["filter_deep_enabled"]) == ["Main deep"]
        ),
        "sort_disabled_preserves_insertion_order": (
            names(cases["sort_disabled"])
            == ["Packer last", "Format first", "Compiler middle"]
        ),
        "sort_enabled_orders_by_type_priority": (
            names(cases["sort_enabled"])
            == ["Format first", "Compiler middle", "Packer last"]
        ),
        "callback_false_keeps_current_then_stops": (
            names(cases["callback_stop_first"]) == ["Priority one"]
            and len(cases["callback_stop_first"]["callback_events"]) == 1
            and cases["callback_stop_first"]["pd_stopped"]
            and not cases["callback_stop_first"]["pd_success"]
        ),
        "break_scan_keeps_current_then_stops": (
            names(cases["break_scan"]) == ["Break first"]
            and cases["break_scan"]["pd_stopped"]
            and not cases["break_scan"]["pd_success"]
        ),
        "pre_stopped_adds_unknown": (
            names(cases["pre_stopped"]) == ["Unknown"]
            and cases["pre_stopped"]["pd_stopped"]
        ),
        "entry_points_are_semantically_equal": (
            cases["entry_file"]["records"]
            == cases["entry_memory"]["records"]
            == cases["entry_device"]["records"]
            == cases["entry_subdevice"]["records"]
        ),
    }
    failed = [name for name, value in relationships.items() if not value]
    if failed:
        raise ValueError(f"engine contract relationships failed: {failed}")
    return relationships


def build_report(
    fixture_dir: pathlib.Path,
    manifest_path: pathlib.Path,
    raw_dir: pathlib.Path,
) -> dict[str, Any]:
    _, manifest_sha256 = load_and_verify_fixture(
        fixture_dir, manifest_path
    )
    image_id, revision = inspect_image()
    binary_digest = docker_bytes("/usr/bin/sha256sum", BINARY).split()[0]

    process = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network=none",
            "--mount",
            f"type=bind,source={fixture_dir},target=/fixture,readonly",
            "--entrypoint",
            BINARY,
            IMAGE,
            "/fixture",
        ],
        check=False,
        capture_output=True,
    )
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "engine-contract.stdout").write_bytes(process.stdout)
    (raw_dir / "engine-contract.stderr").write_bytes(process.stderr)
    if process.returncode != 0 or process.stderr:
        raise ValueError("engine contract harness failed")
    document = json.loads(process.stdout)
    relationships = validate(document)
    source_audit = audit_signature_file_path()

    return {
        "schema_version": 1,
        "generator": "tools/upstream/probe_engine_contract.py",
        "generator_sha256": sha256(pathlib.Path(__file__).read_bytes()),
        "upstream_commit": UPSTREAM_COMMIT,
        "platform": "linux-amd64-qt5",
        "fixture_manifest": {
            "path": (
                "docs/research/data/"
                "rule-orchestration-fixture.json"
            ),
            "sha256": manifest_sha256,
        },
        "oracle": {
            "image": IMAGE,
            "image_id": image_id,
            "revision": revision,
            "binary": BINARY,
            "binary_sha256": binary_digest.decode("ascii"),
            "exit_code": process.returncode,
            "raw_stdout_bytes": len(process.stdout),
            "raw_stdout_sha256": sha256(process.stdout),
            "raw_stderr_bytes": len(process.stderr),
            "raw_stderr_sha256": sha256(process.stderr),
        },
        "raw_artifacts": {
            "storage": "untracked external directory selected by --raw-dir"
        },
        "relationships": relationships,
        "source_audit": source_audit,
        "harness_output": document,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    repo = pathlib.Path(__file__).resolve().parents[2]
    parser.add_argument("--fixture-dir", type=pathlib.Path, required=True)
    parser.add_argument(
        "--manifest",
        type=pathlib.Path,
        default=(
            repo
            / "docs/research/data/rule-orchestration-fixture.json"
        ),
    )
    parser.add_argument("--raw-dir", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()
    report = build_report(
        args.fixture_dir.resolve(),
        args.manifest.resolve(),
        args.raw_dir.resolve(),
    )
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
