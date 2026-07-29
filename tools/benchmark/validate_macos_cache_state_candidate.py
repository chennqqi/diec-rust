#!/usr/bin/env python3
"""Validate a candidate macOS cache-state capability report."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any


PLATFORM = "macos-x86_64-cache-state"
XNU_COMMIT = "f6217f891ac0bb64f3d375211650a4c1ff8ca1ea"
XNU_FCNTL_SHA256 = (
    "0f93c8918a70ffafe20bfe9c72e671fde67438cbee9f9de8c2f87b5c704c9a9e"
)
XNU_KERN_DESCRIP_SHA256 = (
    "480cfed4e987be874bd71fb6933c254adf9fb1f36de8496dee8f351b18da13b1"
)
SHA256_RE = re.compile(r"[0-9a-f]{64}")


class ReportError(ValueError):
    """The candidate cache-state report is incomplete or ambiguous."""


def reject_duplicate_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ReportError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    raise ReportError(f"non-finite JSON constant: {value}")


def load_report(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_bytes(),
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReportError(f"invalid JSON: {error}") from error
    if not isinstance(value, dict):
        raise ReportError("report root must be an object")
    return value


def require_object(value: Any, description: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReportError(f"{description} must be an object")
    return value


def require_sha256(value: Any, description: str) -> None:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise ReportError(f"invalid SHA-256: {description}")


def validate_observation(value: Any, index: int) -> None:
    observation = require_object(value, f"observations[{index}]")
    required = {
        "schema_version",
        "page_size",
        "fixture_bytes",
        "logical_pages",
        "warm_resident_pages",
        "after_f_nocache_resident_pages",
        "msync_flags",
        "after_msync_invalidate_resident_pages",
        "checksum",
        "temporary_fixture_unlinked_before_probe",
        "benchmark_files_touched",
        "system_cache_flush_executed",
    }
    if set(observation) != required:
        raise ReportError("observation field set drift")
    if observation["schema_version"] != 1:
        raise ReportError("observation schema drift")
    for field in required - {"schema_version"}:
        if not isinstance(observation[field], int):
            raise ReportError(f"observation integer missing: {field}")
    page_size = observation["page_size"]
    fixture_bytes = observation["fixture_bytes"]
    logical_pages = observation["logical_pages"]
    if (
        page_size <= 0
        or fixture_bytes != 16 * 1024 * 1024
        or logical_pages != fixture_bytes // page_size
        or logical_pages <= 0
        or observation["msync_flags"] != 18
    ):
        raise ReportError("observation page geometry drift")
    if observation["warm_resident_pages"] != logical_pages:
        raise ReportError("fixture was not fully warm")
    for field in (
        "after_f_nocache_resident_pages",
        "after_msync_invalidate_resident_pages",
    ):
        if not 0 <= observation[field] <= logical_pages:
            raise ReportError(f"residency count out of range: {field}")
    if (
        observation["temporary_fixture_unlinked_before_probe"] != 1
        or observation["benchmark_files_touched"] != 0
        or observation["system_cache_flush_executed"] != 0
    ):
        raise ReportError("temporary-fixture safety boundary failed")


def validate_report(report: dict[str, Any]) -> None:
    required_root = {
        "schema_version",
        "result",
        "platform",
        "generated_at",
        "upstream_commit",
        "darwin_source",
        "probe",
        "host",
        "observations",
        "relationships",
        "admission",
        "scope",
    }
    if set(report) != required_root:
        raise ReportError("report root fields changed")
    if (
        report["schema_version"] != 1
        or report["result"] != "candidate"
        or report["platform"] != PLATFORM
        or report["upstream_commit"]
        != "74eaf505c250ab47e709024e9dc41657cd8f2254"
    ):
        raise ReportError("report identity drift")
    if (
        not isinstance(report["generated_at"], str)
        or not report["generated_at"]
    ):
        raise ReportError("generated_at is missing")

    darwin = require_object(report["darwin_source"], "darwin_source")
    if darwin.get("xnu_commit") != XNU_COMMIT:
        raise ReportError("XNU identity drift")
    if (
        darwin.get("fcntl_header_sha256") != XNU_FCNTL_SHA256
        or darwin.get("kern_descrip_sha256")
        != XNU_KERN_DESCRIP_SHA256
    ):
        raise ReportError("XNU source hash drift")

    probe = require_object(report["probe"], "probe")
    if set(probe) != {
        "source_sha256",
        "binary_sha256",
        "collector_sha256",
        "validator_sha256",
        "compiler_arguments",
    }:
        raise ReportError("probe identity field set drift")
    for field in (
        "source_sha256",
        "binary_sha256",
        "collector_sha256",
        "validator_sha256",
    ):
        require_sha256(probe.get(field), f"probe.{field}")
    root = Path(__file__).resolve().parents[2]
    identities = {
        "source_sha256": (
            root / "tools/benchmark/probe_macos_file_content_cache.c"
        ),
        "collector_sha256": (
            root
            / "tools/benchmark/"
            "collect_macos_cache_state_candidate.py"
        ),
        "validator_sha256": Path(__file__).resolve(),
    }
    for field, path in identities.items():
        if probe[field] != hashlib.sha256(path.read_bytes()).hexdigest():
            raise ReportError(f"local source identity drift: {field}")
    if probe.get("compiler_arguments") != [
        "-std=c11",
        "-O2",
        "-Wall",
        "-Wextra",
        "-Werror",
    ]:
        raise ReportError("compiler arguments drift")

    host = require_object(report["host"], "host")
    if set(host) != {
        "machine",
        "macos_product_version",
        "macos_build_version",
        "darwin_release",
        "temporary_filesystem",
        "clang_version",
    } or (
        host.get("machine") != "x86_64"
        or not isinstance(host.get("macos_product_version"), str)
        or not host["macos_product_version"]
        or not isinstance(host.get("macos_build_version"), str)
        or not host["macos_build_version"]
        or not isinstance(host.get("darwin_release"), str)
        or not host["darwin_release"]
        or not isinstance(host.get("temporary_filesystem"), str)
        or not host["temporary_filesystem"]
        or not isinstance(host.get("clang_version"), list)
        or not host["clang_version"]
        or any(
            not isinstance(line, str) or not line
            for line in host["clang_version"]
        )
    ):
        raise ReportError("host identity is incomplete")

    observations = report["observations"]
    if not isinstance(observations, list) or len(observations) != 2:
        raise ReportError("exactly two observations are required")
    for index, observation in enumerate(observations):
        validate_observation(observation, index)
    if observations[0] != observations[1]:
        raise ReportError("repeated observations differ")

    relationships = require_object(
        report["relationships"], "relationships"
    )
    expected_equivalence = all(
        item["after_msync_invalidate_resident_pages"] == 0
        for item in observations
    )
    if relationships != {
        "two_observations_identical": True,
        "all_pages_warm_before_control": True,
        "f_nocache_toggle_alone_evicted_all_pages": all(
            item["after_f_nocache_resident_pages"] == 0
            for item in observations
        ),
        "msync_invalidate_produced_zero_resident_pages": (
            expected_equivalence
        ),
        "linux_file_content_semantic_candidate": expected_equivalence,
    }:
        raise ReportError("derived relationships drift")

    admission = require_object(report["admission"], "admission")
    if (
        admission.get("cache_state_admitted") is not False
        or not isinstance(admission.get("reason"), str)
        or not admission["reason"]
    ):
        raise ReportError("candidate must not admit a cache state")
    scope = require_object(report["scope"], "scope")
    if scope != {
        "temporary_unlinked_fixture_only": True,
        "benchmark_files_touched": False,
        "system_cache_flush_executed": False,
        "performance_baseline": False,
        "runtime_candidate_only": True,
    }:
        raise ReportError("report scope drift")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    return parser.parse_args()


def main() -> int:
    report = load_report(parse_args().report)
    validate_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
