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
    "binary_script_fast_path_invalid_suffix": {
        "compare": True,
        "binary_script_compare_result": False,
    },
    "binary_script_fast_path_before_strict_boundary": {
        "compare": True,
        "binary_script_compare_result": False,
    },
    "binary_script_generic_at_strict_boundary": {
        "compare": True,
        "binary_script_compare_result": True,
    },
    "binary_script_literal_before_strict_boundary": {
        "compare": True,
        "binary_script_compare_result": True,
    },
    "binary_script_literal_at_strict_boundary": {
        "compare": True,
        "binary_script_compare_result": True,
    },
    "binary_script_negative_offset_clamps_to_header_start": {
        "compare": False,
        "binary_script_compare_result": True,
    },
    "binary_script_negative_offset_clamp_can_mismatch": {
        "compare": False,
        "binary_script_compare_result": False,
    },
    "binary_script_ep_fast_path_invalid_suffix": {
        "binary_script_parser_valid": True,
        "binary_script_entry_point_offset": 512,
        "binary_compare_ep_result": True,
        "binary_script_compare_ep_result": False,
    },
    "binary_script_ep_cache_overrun_fast_path": {
        "binary_compare_ep_result": True,
        "binary_script_compare_ep_result": False,
    },
    "binary_script_ep_original_length_selects_generic": {
        "binary_compare_ep_result": True,
        "binary_script_compare_ep_result": True,
    },
    "binary_script_ep_before_strict_boundary": {
        "binary_compare_ep_result": True,
        "binary_script_compare_ep_result": False,
    },
    "binary_script_ep_at_strict_boundary": {
        "binary_compare_ep_result": True,
        "binary_script_compare_ep_result": True,
    },
    "binary_script_overlay_fast_path_invalid_suffix": {
        "binary_script_parser_valid": True,
        "binary_script_overlay_offset": 1536,
        "binary_script_overlay_size": 512,
        "binary_compare_overlay_result": True,
        "binary_script_compare_overlay_result": False,
    },
    "binary_script_overlay_cache_overrun_fast_path": {
        "binary_compare_overlay_result": True,
        "binary_script_compare_overlay_result": False,
    },
    "binary_script_overlay_original_length_selects_generic": {
        "binary_compare_overlay_result": True,
        "binary_script_compare_overlay_result": True,
    },
    "binary_script_overlay_before_strict_boundary": {
        "binary_compare_overlay_result": True,
        "binary_script_compare_overlay_result": False,
    },
    "binary_script_overlay_at_strict_boundary": {
        "binary_compare_overlay_result": True,
        "binary_script_compare_overlay_result": True,
    },
    "plain_find_clamps_oversized_range": {
        "compare": False,
        "find_offset": 1,
        "binary_script_find_signature_result": 1,
        "binary_script_f_sig_result": 1,
        "binary_script_is_signature_present_result": True,
    },
    "binary_script_find_size_minus_one": {
        "find_offset": 1,
        "binary_script_find_signature_result": 1,
        "binary_script_f_sig_result": 1,
        "binary_script_is_signature_present_result": True,
    },
    "sigbyte_fixed_anchor_rechecks_record_classes": {
        "compare": False,
        "find_offset": -1,
    },
    "find_at_window_end": {
        "compare": True,
        "find_offset": -1,
        "binary_script_find_signature_result": -1,
        "binary_script_f_sig_result": -1,
        "binary_script_is_signature_present_result": False,
    },
    "control_longest_literal_anchor": {
        "compare": True,
        "find_offset": 0,
    },
    "control_class_first_anchor": {
        "compare": True,
        "find_offset": 0,
    },
    "control_relative_first_fallback": {
        "compare": True,
        "find_offset": 0,
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
    "literal_mismatch": {
        "compare": False,
        "find_offset": -1,
        "binary_script_find_signature_result": -1,
        "binary_script_f_sig_result": -1,
        "binary_script_is_signature_present_result": False,
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
    "pe_relative_crosses_raw_gap": {
        "compare": True,
    },
    "elf_big_endian_relative_crosses_raw_gap": {
        "compare": True,
    },
    "macho_64_absolute_crosses_raw_gap": {
        "compare": True,
    },
    "com_relative_ignores_nonidentity_map": {
        "compare": True,
    },
    "msdos_absolute_word_adds_code_base": {
        "compare": True,
    },
    "msdos_far_pointer_uses_segment_address": {
        "compare": True,
    },
    "amigahunk_relative_word_omits_width_increment": {
        "compare": True,
    },
    "pe32_parser_memory_map_relative_jump": {
        "format_valid": True,
        "compare": True,
    },
    "pe64_parser_memory_map_relative_jump": {
        "format_valid": True,
        "compare": True,
    },
    "elf64_parser_memory_map_relative_jump": {
        "format_valid": True,
        "compare": True,
    },
    "elf32_parser_memory_map_relative_jump": {
        "format_valid": True,
        "compare": True,
    },
    "macho64_parser_memory_map_absolute_jump": {
        "format_valid": True,
        "compare": True,
    },
    "macho32_parser_memory_map_absolute_jump": {
        "format_valid": True,
        "compare": True,
    },
    "com_parser_memory_map_relative_jump": {
        "format_valid": True,
        "compare": True,
    },
    "msdos_parser_memory_map_far_pointer": {
        "format_valid": True,
        "compare": True,
    },
    "amigahunk_parser_memory_map_relative_jump": {
        "format_valid": True,
        "compare": True,
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
    if baseline.get("schema_version") != vectors.get("schema_version"):
        failures.append("schema_version")
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
        if actual.get("search_offset") != vector.get("find_offset", 0):
            failures.append(f"{case_id}.search_offset")
        expected_search_size = vector.get(
            "find_size",
            len(vector.get("data_hex", "")) // 2
            - vector.get("find_offset", 0),
        )
        if actual.get("search_size") != expected_search_size:
            failures.append(f"{case_id}.search_size")
        for field in ("base_signature", "memory_map", "format_parser"):
            if field in vector and actual.get(field) != vector.get(field):
                failures.append(f"{case_id}.{field}")
        for field in (
            "binary_script_compare",
            "binary_script_compare_ep",
            "binary_script_compare_overlay",
            "binary_script_find_signature",
            "binary_script_f_sig",
            "binary_script_is_signature_present",
            "binary_script_parser",
        ):
            if field in vector and actual.get(field) != vector.get(field):
                failures.append(f"{case_id}.{field}")
        if "format_parser" in vector and not isinstance(
            actual.get("derived_memory_map"), dict
        ):
            failures.append(f"{case_id}.derived_memory_map")

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
