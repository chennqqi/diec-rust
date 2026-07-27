#!/usr/bin/env python3
"""Run and verify the pinned Qt5 PDF fixed-rule oracle harness."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
from typing import Any


UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
XPDF_COMMIT = "cdcee54dce97f566f2c023f400a457f4e6278de2"
XSCANENGINE_COMMIT = "dfe4a419e4f491bb23688ba03c5a5bf39e34da83"
RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
RULE_PATH = "/opt/die-source/Detect-It-Easy/db/PDF/format_Tools.2.sg"
RULE_SHA256 = "982869432394292415be6c3c2ef9408ac1943c4d7571e19f767ffe87314c23da"
EXPECTED_IDS = [
    "tools_string_values",
    "tools_non_string_values",
    "tools_missing_endobj",
]
EXPECTED_NATIVE = {
    "tools_string_values": {
        "object_count": 2,
        "creator": ["Tool A", "Tool)B"],
        "producer": ["Prod One"],
        "header": "e2e3cfd3",
        "detections": [
            ["tool", "Creator", "e2e3cfd3", "Tool A"],
            ["tool", "Creator", "e2e3cfd3", "Tool)B"],
            ["tool", "Producer", "e2e3cfd3", "Prod One"],
        ],
    },
    "tools_non_string_values": {
        "object_count": 1,
        "creator": [],
        "producer": [],
        "header": "4153434949",
        "detections": [],
    },
    "tools_missing_endobj": {
        "object_count": 0,
        "creator": [],
        "producer": [],
        "header": "fffe",
        "detections": [],
    },
}
EXPECTED_PARTS = {
    "tools_string_values": [
        {
            "id": 1,
            "offset": 15,
            "tokens": [
                "<<",
                "/Creator",
                "(Tool A)",
                "/Producer",
                "(Prod One)",
                ">>",
            ],
        },
        {
            "id": 2,
            "offset": 75,
            "tokens": [
                "<<",
                "/Creator",
                "(Tool A)",
                "/Creator",
                "(Tool)B)",
                "/Producer",
                "<486578>",
                ">>",
            ],
        },
    ],
    "tools_non_string_values": [
        {
            "id": 1,
            "offset": 16,
            "tokens": [
                "<<",
                "/Creator",
                "<546f6f6c>",
                "/Producer",
                "/NamedProducer",
                ">>",
            ],
        }
    ],
    "tools_missing_endobj": [],
}


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_object(path: pathlib.Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} root must be an object")
    return value


def validate(
    fixture: dict[str, Any],
    actual: dict[str, Any],
    expected_revision: str,
) -> list[str]:
    failures: list[str] = []
    metadata = {
        "schema_version": 1,
        "upstream_commit": expected_revision,
        "xpdf_commit": XPDF_COMMIT,
        "xscanengine_commit": XSCANENGINE_COMMIT,
        "rules_commit": RULES_COMMIT,
        "qt_version": "5.15.13",
        "engine": "QScriptEngine",
        "rule_path": RULE_PATH,
        "rule_sha256": RULE_SHA256,
        "case_count": len(EXPECTED_IDS),
    }
    for field, expected in metadata.items():
        if actual.get(field) != expected:
            failures.append(field)
    fixture_cases = fixture.get("cases")
    actual_cases = actual.get("cases")
    if not isinstance(fixture_cases, list) or not isinstance(actual_cases, list):
        return failures + ["cases"]
    fixture_by_id = {
        case.get("id"): case for case in fixture_cases if isinstance(case, dict)
    }
    actual_by_id = {
        case.get("id"): case for case in actual_cases if isinstance(case, dict)
    }
    if list(fixture_by_id) != EXPECTED_IDS:
        failures.append("fixture_case_ids")
    if list(actual_by_id) != EXPECTED_IDS:
        failures.append("actual_case_ids")
    for case_id in EXPECTED_IDS:
        source = fixture_by_id.get(case_id)
        case = actual_by_id.get(case_id)
        if not isinstance(source, dict) or not isinstance(case, dict):
            failures.append(f"{case_id}.missing")
            continue
        for field in ("data_hex", "data_sha256"):
            if case.get(field) != source.get(field):
                failures.append(f"{case_id}.{field}")
        data_hex = source.get("data_hex")
        if not isinstance(data_hex, str):
            failures.append(f"{case_id}.data_hex_type")
        else:
            digest = hashlib.sha256(bytes.fromhex(data_hex)).hexdigest()
            if source.get("data_sha256") != digest:
                failures.append(f"{case_id}.fixture_hash")
        expected = EXPECTED_NATIVE[case_id]
        expected_values = {
            "parser_valid": True,
            "object_count": expected["object_count"],
            "object_parts": EXPECTED_PARTS[case_id],
            "native_creator_values": expected["creator"],
            "native_producer_values": expected["producer"],
            "native_header_comment_hex": expected["header"],
            "detect_is_undefined": True,
            "detections": expected["detections"],
            "pdf_script_error": "",
        }
        for field, value in expected_values.items():
            if case.get(field) != value:
                failures.append(f"{case_id}.{field}")
        if "error" in case:
            failures.append(f"{case_id}.error")
    return failures


def docker_prefix(context: str) -> list[str]:
    command = ["docker"]
    if context:
        command.extend(["--context", context])
    return command


def run_checked(command: list[str]) -> bytes:
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(
            f"command failed with exit {result.returncode}: {message}"
        )
    return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--binary", required=True)
    parser.add_argument("--fixture", required=True, type=pathlib.Path)
    parser.add_argument("--baseline", required=True, type=pathlib.Path)
    parser.add_argument("--expected-revision", default=UPSTREAM_COMMIT)
    parser.add_argument("--docker-context", default="")
    parser.add_argument("--record-baseline", action="store_true")
    args = parser.parse_args()

    fixture_path = args.fixture.resolve()
    baseline_path = args.baseline.resolve()
    fixture = load_object(fixture_path)
    docker = docker_prefix(args.docker_context)
    revision = run_checked(
        [
            *docker,
            "image",
            "inspect",
            "--format",
            '{{ index .Config.Labels "org.opencontainers.image.revision" }}',
            args.image,
        ]
    ).decode("utf-8").strip()
    binary_hash = run_checked(
        [
            *docker,
            "run",
            "--rm",
            "--network",
            "none",
            "--entrypoint",
            "sha256sum",
            args.image,
            args.binary,
        ]
    ).decode("ascii").split()[0]
    mount = f"type=bind,src={fixture_path.parent},dst=/vectors,readonly"
    stdout = run_checked(
        [
            *docker,
            "run",
            "--rm",
            "--network",
            "none",
            "--memory",
            "512m",
            "--cpus",
            "1",
            "--pids-limit",
            "128",
            "--mount",
            mount,
            "--entrypoint",
            args.binary,
            args.image,
            f"/vectors/{fixture_path.name}",
        ]
    )
    actual = json.loads(stdout.decode("utf-8"))
    if not isinstance(actual, dict):
        raise RuntimeError("harness output root must be an object")
    if args.record_baseline:
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_bytes(stdout)
    baseline = load_object(baseline_path)
    failures = validate(fixture, actual, args.expected_revision)
    if revision != args.expected_revision:
        failures.append("image_revision")
    if actual != baseline:
        failures.append("baseline_mismatch")
    if stdout != baseline_path.read_bytes():
        failures.append("baseline_bytes_mismatch")
    report = {
        "schema_version": 1,
        "image": args.image,
        "image_revision": revision,
        "binary": args.binary,
        "binary_sha256": binary_hash,
        "fixture": str(args.fixture).replace("\\", "/"),
        "fixture_sha256": sha256(fixture_path),
        "baseline": str(args.baseline).replace("\\", "/"),
        "baseline_sha256": sha256(baseline_path),
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
        "case_count": actual.get("case_count"),
        "failures": failures,
        "passed": not failures,
    }
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
