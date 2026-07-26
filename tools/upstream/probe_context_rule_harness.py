#!/usr/bin/env python3
"""Run and verify the pinned Qt5 Binary context rule harness."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
from typing import Any


EXPECTED = {
    "resource_manifest": {
        "data_hex": "00",
        "file_part": "resource",
        "scan_id": "24",
        "file_name": "resource.bin",
        "rule_path": (
            "/opt/die-source/Detect-It-Easy/db/Binary/"
            "win_resources.1.sg"
        ),
        "rule_sha256": (
            "2fdad41d666d32467cabe83dae7d16625ade5935e3061c58d"
            "fefeb1fb7b99db7"
        ),
        "detect_result": True,
        "detections": [["format", "Manifest", "", "Resources"]],
    },
    "resource_unknown_id": {
        "data_hex": "00",
        "file_part": "resource",
        "scan_id": "999",
        "file_name": "resource.bin",
        "rule_path": (
            "/opt/die-source/Detect-It-Easy/db/Binary/"
            "win_resources.1.sg"
        ),
        "rule_sha256": (
            "2fdad41d666d32467cabe83dae7d16625ade5935e3061c58d"
            "fefeb1fb7b99db7"
        ),
        "detect_result": False,
        "detections": [],
    },
    "resource_header_gate": {
        "data_hex": "00",
        "file_part": "header",
        "scan_id": "24",
        "file_name": "resource.bin",
        "rule_path": (
            "/opt/die-source/Detect-It-Easy/db/Binary/"
            "win_resources.1.sg"
        ),
        "rule_sha256": (
            "2fdad41d666d32467cabe83dae7d16625ade5935e3061c58d"
            "fefeb1fb7b99db7"
        ),
        "detect_result": False,
        "detections": [],
    },
    "debug_rsds": {
        "data_hex": "52534453",
        "file_part": "debugdata",
        "scan_id": "",
        "file_name": "debug.bin",
        "rule_path": (
            "/opt/die-source/Detect-It-Easy/db/Binary/"
            "debug_data_debugData.1.sg"
        ),
        "rule_sha256": (
            "381b6259b239f2633b92fbd84fd0d99b972751e20cab12b6"
            "e09139a260f1f47d"
        ),
        "detect_result": True,
        "detections": [["debug data", "PDB file link", "7.0", ""]],
    },
    "debug_header_gate": {
        "data_hex": "52534453",
        "file_part": "header",
        "scan_id": "",
        "file_name": "debug.bin",
        "rule_path": (
            "/opt/die-source/Detect-It-Easy/db/Binary/"
            "debug_data_debugData.1.sg"
        ),
        "rule_sha256": (
            "381b6259b239f2633b92fbd84fd0d99b972751e20cab12b6"
            "e09139a260f1f47d"
        ),
        "detect_result": False,
        "detections": [],
    },
    "desktop_entry": {
        "data_hex": "5b4465736b746f7020456e7472795d0a",
        "file_part": "header",
        "scan_id": "",
        "file_name": "sample.desktop",
        "rule_path": (
            "/opt/die-source/Detect-It-Easy/db/Binary/"
            "format_DESKTOP.1.sg"
        ),
        "rule_sha256": (
            "9318de29fa4b3ea3c36f0fb286dc70fd77020cde092e1cf0"
            "78aa57dc21562ff3"
        ),
        "detect_result": True,
        "detections": [["format", "Desktop Entry (.desktop)", "", ""]],
    },
    "desktop_missing_marker": {
        "data_hex": "68656c6c6f0a",
        "file_part": "header",
        "scan_id": "",
        "file_name": "sample.desktop",
        "rule_path": (
            "/opt/die-source/Detect-It-Easy/db/Binary/"
            "format_DESKTOP.1.sg"
        ),
        "rule_sha256": (
            "9318de29fa4b3ea3c36f0fb286dc70fd77020cde092e1cf0"
            "78aa57dc21562ff3"
        ),
        "detect_result": False,
        "detections": [],
    },
    "desktop_binary_gate": {
        "data_hex": "00010203",
        "file_part": "header",
        "scan_id": "",
        "file_name": "sample.desktop",
        "rule_path": (
            "/opt/die-source/Detect-It-Easy/db/Binary/"
            "format_DESKTOP.1.sg"
        ),
        "rule_sha256": (
            "9318de29fa4b3ea3c36f0fb286dc70fd77020cde092e1cf0"
            "78aa57dc21562ff3"
        ),
        "detect_result": False,
        "detections": [],
    },
}

XSCANENGINE_COMMIT = "dfe4a419e4f491bb23688ba03c5a5bf39e34da83"
RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_object(path: pathlib.Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(document, dict):
        raise ValueError(f"{path} root must be a JSON object")
    return document


def validate(
    actual: dict[str, Any],
    expected_revision: str,
) -> list[str]:
    failures: list[str] = []
    if actual.get("schema_version") != 1:
        failures.append("schema_version")
    if actual.get("upstream_commit") != expected_revision:
        failures.append("upstream_commit")
    if actual.get("xscanengine_commit") != XSCANENGINE_COMMIT:
        failures.append("xscanengine_commit")
    if actual.get("rules_commit") != RULES_COMMIT:
        failures.append("rules_commit")
    if actual.get("qt_version") != "5.15.13":
        failures.append("qt_version")
    if actual.get("engine") != "QScriptEngine":
        failures.append("engine")
    cases = actual.get("cases")
    if not isinstance(cases, list):
        return failures + ["cases"]
    if actual.get("case_count") != len(EXPECTED) or len(cases) != len(
        EXPECTED
    ):
        failures.append("case_count")
    by_id = {
        case.get("id"): case
        for case in cases
        if isinstance(case, dict)
    }
    if set(by_id) != set(EXPECTED):
        failures.append("case_ids")
    for case_id, expected in EXPECTED.items():
        case = by_id.get(case_id)
        if not isinstance(case, dict):
            failures.append(f"{case_id}.missing")
            continue
        if case.get("detect_is_boolean") is not True:
            failures.append(f"{case_id}.detect_is_boolean")
        for field in (
            "data_hex",
            "file_part",
            "scan_id",
            "file_name",
            "rule_path",
            "rule_sha256",
        ):
            if case.get(field) != expected[field]:
                failures.append(f"{case_id}.{field}")
        if case.get("detect_result") != expected["detect_result"]:
            failures.append(f"{case_id}.detect_result")
        if case.get("detections") != expected["detections"]:
            failures.append(f"{case_id}.detections")
        if case.get("binary_script_error") != "":
            failures.append(f"{case_id}.binary_script_error")
        if "error" in case:
            failures.append(f"{case_id}.error")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--binary", required=True)
    parser.add_argument("--baseline", type=pathlib.Path, required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--docker-context", default="default")
    parser.add_argument("--record-baseline", action="store_true")
    args = parser.parse_args()

    inspect = subprocess.run(
        [
            "docker",
            f"--context={args.docker_context}",
            "image",
            "inspect",
            "--format",
            "{{index .Config.Labels "
            '"org.opencontainers.image.revision"}}',
            args.image,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    image_revision = inspect.stdout.strip()
    if image_revision != args.expected_revision:
        raise SystemExit(
            f"image revision mismatch: {image_revision!r}"
        )

    binary_hash = subprocess.run(
        [
            "docker",
            f"--context={args.docker_context}",
            "run",
            "--rm",
            "--network=none",
            "--memory=512m",
            "--cpus=1",
            "--pids-limit=128",
            "--entrypoint",
            "sha256sum",
            args.image,
            args.binary,
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()[0]
    run = subprocess.run(
        [
            "docker",
            f"--context={args.docker_context}",
            "run",
            "--rm",
            "--network=none",
            "--memory=512m",
            "--cpus=1",
            "--pids-limit=128",
            "--entrypoint",
            args.binary,
            args.image,
        ],
        check=True,
        capture_output=True,
    )
    actual = json.loads(run.stdout.decode("utf-8-sig"))
    if not isinstance(actual, dict):
        raise SystemExit("harness output root must be an object")
    failures = validate(actual, args.expected_revision)
    if failures:
        raise SystemExit("oracle validation failed: " + ", ".join(failures))

    canonical = (
        json.dumps(
            actual,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    if args.record_baseline:
        args.baseline.write_bytes(canonical)
    baseline = load_object(args.baseline)
    if baseline != actual:
        raise SystemExit("baseline content differs from harness output")

    report = {
        "schema_version": 1,
        "image": args.image,
        "image_revision": image_revision,
        "binary": args.binary,
        "binary_sha256": binary_hash,
        "baseline": str(args.baseline).replace("\\", "/"),
        "baseline_sha256": sha256_bytes(args.baseline.read_bytes()),
        "stdout_sha256": sha256_bytes(canonical),
        "case_count": len(EXPECTED),
        "failures": [],
        "passed": True,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as error:
        if error.stderr:
            sys.stderr.buffer.write(error.stderr)
        raise
