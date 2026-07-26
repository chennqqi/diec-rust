#!/usr/bin/env python3
"""Run and verify the pinned XBinary signature oracle harness."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
from typing import Any


EXPECTED_OBSERVATIONS = {
    "find_at_window_end": {
        "compare": True,
        "find_offset": -1,
    },
    "decimal_class_rejects_letter": {
        "compare": False,
        "find_offset": 0,
    },
    "ansi_del_compare_find_divergence": {
        "compare": True,
        "find_offset": -1,
    },
    "not_ansi_del_compare_find_divergence": {
        "compare": False,
        "find_offset": 0,
    },
    "invalid_suffix_partially_compares": {
        "valid": False,
        "compare": True,
        "find_offset": 0,
    },
    "percent_only_has_no_records": {
        "valid": True,
        "compare": False,
        "find_offset": -1,
    },
    "relative_offset_little_endian": {
        "compare": True,
        "find_offset": 0,
    },
    "absolute_address_identity_map": {
        "compare": True,
        "find_offset": 0,
    },
}


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_object(path: pathlib.Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(document, dict):
        raise ValueError(f"{path} root must be a JSON object")
    return document


def validate_baseline(
    vectors: dict[str, Any],
    baseline: dict[str, Any],
    expected_revision: str,
) -> list[str]:
    failures: list[str] = []
    vector_cases = vectors.get("cases")
    baseline_cases = baseline.get("cases")
    if not isinstance(vector_cases, list) or not isinstance(
        baseline_cases, list
    ):
        return ["case_list"]
    if baseline.get("upstream_commit") != expected_revision:
        failures.append("upstream_commit")
    if baseline.get("formats_commit") != vectors.get("formats_commit"):
        failures.append("formats_commit")
    if baseline.get("case_count") != len(vector_cases):
        failures.append("case_count")
    if len(baseline_cases) != len(vector_cases):
        failures.append("case_output_count")

    baseline_by_id = {
        case.get("id"): case
        for case in baseline_cases
        if isinstance(case, dict)
    }
    for vector in vector_cases:
        if not isinstance(vector, dict):
            failures.append("invalid_vector")
            continue
        case_id = vector.get("id")
        actual = baseline_by_id.get(case_id)
        if not isinstance(actual, dict):
            failures.append(f"{case_id}.missing")
            continue
        for field in ("id", "pattern", "data_hex"):
            expected = vector.get(field)
            if actual.get(field) != expected:
                failures.append(f"{case_id}.{field}")
        if actual.get("offset") != vector.get("offset", 0):
            failures.append(f"{case_id}.offset")

    for case_id, expected in EXPECTED_OBSERVATIONS.items():
        actual = baseline_by_id.get(case_id)
        if not isinstance(actual, dict):
            failures.append(f"{case_id}.missing_observation")
            continue
        for field, value in expected.items():
            if actual.get(field) != value:
                failures.append(f"{case_id}.{field}")
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--binary", required=True)
    parser.add_argument("--vectors", required=True, type=pathlib.Path)
    parser.add_argument("--baseline", required=True, type=pathlib.Path)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--docker-context", default="")
    parser.add_argument("--record-baseline", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    vectors_path = args.vectors.resolve()
    baseline_path = args.baseline.resolve()
    vectors = load_object(vectors_path)
    failures: list[str] = []

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
    if revision != args.expected_revision:
        failures.append("image_revision")

    binary_hash_output = run_checked(
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
    ).decode("ascii")
    binary_sha256 = binary_hash_output.split()[0]

    mount = (
        f"type=bind,src={vectors_path.parent},dst=/vectors,readonly"
    )
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
            f"/vectors/{vectors_path.name}",
        ]
    )
    actual = json.loads(stdout.decode("utf-8"))
    if args.record_baseline:
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_bytes(stdout)
    baseline = load_object(baseline_path)
    failures.extend(
        validate_baseline(
            vectors,
            baseline,
            args.expected_revision,
        )
    )
    if actual != baseline:
        failures.append("baseline_mismatch")
    if stdout != baseline_path.read_bytes():
        failures.append("baseline_bytes_mismatch")

    report = {
        "schema_version": 1,
        "image": args.image,
        "image_revision": revision,
        "binary": args.binary,
        "binary_sha256": binary_sha256,
        "vectors": str(args.vectors).replace("\\", "/"),
        "vectors_sha256": sha256(vectors_path),
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
