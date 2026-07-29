#!/usr/bin/env python3
"""Freeze native Windows benchmark cache-control boundaries."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


SCHEMA_VERSION = 1
EXPECTED_REVISION = "74eaf505c250ab47e709024e9dc41657cd8f2254"
GENERATOR = (
    "tools/benchmark/probe_windows_benchmark_cache_environment.py"
)
OBSERVER = "tools/benchmark/observe_windows_cache_environment.py"
OFFICIAL_CONTRACT_SOURCES = [
    {
        "claim": (
            "GetSystemFileCacheSize observes the system-cache working-set "
            "limits and whether hard limits are enabled"
        ),
        "url": (
            "https://learn.microsoft.com/en-us/windows/win32/api/"
            "memoryapi/nf-memoryapi-getsystemfilecachesize"
        ),
    },
    {
        "claim": (
            "SetSystemFileCacheSize changes a system-global cache working "
            "set, uses -1/-1 to flush it, and requires the enabled "
            "SeIncreaseQuotaPrivilege"
        ),
        "url": (
            "https://learn.microsoft.com/en-us/windows/win32/api/"
            "memoryapi/nf-memoryapi-setsystemfilecachesize"
        ),
    },
    {
        "claim": (
            "FILE_FLAG_NO_BUFFERING selects uncached I/O for the handle "
            "and imposes sector and buffer alignment requirements"
        ),
        "url": (
            "https://learn.microsoft.com/en-us/windows/win32/fileio/"
            "file-buffering"
        ),
    },
    {
        "claim": (
            "FlushFileBuffers writes buffered file data to its target; "
            "it is not a file-page nonresidency observation"
        ),
        "url": (
            "https://learn.microsoft.com/en-us/windows/win32/api/"
            "fileapi/nf-fileapi-flushfilebuffers"
        ),
    },
    {
        "claim": (
            "EmptyWorkingSet removes as many pages as possible from one "
            "process working set, not the system file cache"
        ),
        "url": (
            "https://learn.microsoft.com/en-us/windows/win32/psapi/"
            "working-set-information"
        ),
    },
]


class ProbeError(ValueError):
    """The native Windows cache boundary is not reproducible."""


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def reject_duplicate_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProbeError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    raise ProbeError(f"non-finite JSON constant: {value}")


def parse_json(raw: bytes, description: str) -> dict[str, Any]:
    try:
        value = json.loads(
            raw,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProbeError(f"invalid {description}: {error}") from error
    if not isinstance(value, dict):
        raise ProbeError(f"{description} root must be an object")
    return value


def serialize(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def run_observer(root: Path, observer: Path) -> tuple[dict[str, Any], bytes]:
    completed = subprocess.run(
        [
            sys.executable,
            str(observer),
            "--target-root",
            str(root),
        ],
        cwd=root,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        raise ProbeError(
            "observer failed with exit "
            f"{completed.returncode}: "
            f"{completed.stderr.decode('utf-8', errors='replace')}"
        )
    raw = completed.stdout
    return parse_json(raw, "observer JSON"), raw


def validate_observation(observation: dict[str, Any]) -> None:
    if observation.get("schema_version") != 1:
        raise ProbeError("unexpected observer schema")
    scope = observation.get("scope")
    if not isinstance(scope, dict):
        raise ProbeError("observer scope is missing")
    if scope != {
        "read_only_observation": True,
        "cache_state_changed": False,
        "set_system_file_cache_size_called": False,
        "empty_working_set_called": False,
        "flush_file_buffers_called": False,
        "no_buffering_handle_opened": False,
    }:
        raise ProbeError("observer did not preserve the read-only boundary")
    privilege = (
        observation.get("process", {})
        .get("set_system_file_cache_privilege")
    )
    if (
        not isinstance(privilege, dict)
        or privilege.get("name") != "SeIncreaseQuotaPrivilege"
        or not isinstance(privilege.get("present"), bool)
        or not isinstance(privilege.get("enabled"), bool)
    ):
        raise ProbeError("cache-control privilege evidence is malformed")
    platform = observation.get("platform")
    if (
        not isinstance(platform, dict)
        or not isinstance(platform.get("page_size"), int)
        or platform["page_size"] <= 0
    ):
        raise ProbeError("Windows platform evidence is malformed")
    target = observation.get("target_volume")
    if (
        not isinstance(target, dict)
        or target.get("target_path_recorded") is not False
        or target.get("volume_identity_recorded") is not False
    ):
        raise ProbeError("target volume privacy boundary is malformed")


def build_report(root: Path) -> dict[str, Any]:
    if sys.platform != "win32":
        raise ProbeError("probe requires native Windows")
    generator = root / GENERATOR
    observer = root / OBSERVER
    if not generator.is_file() or not observer.is_file():
        raise ProbeError("generator or observer source is missing")
    first, first_raw = run_observer(root, observer)
    second, second_raw = run_observer(root, observer)
    validate_observation(first)
    validate_observation(second)
    if first_raw != second_raw or first != second:
        raise ProbeError("repeated Windows observations differ")

    privilege = first["process"]["set_system_file_cache_privilege"]
    relationships = {
        "two_native_observations_identical": True,
        "observation_was_read_only": first["scope"][
            "read_only_observation"
        ],
        "no_cache_state_changed": not first["scope"][
            "cache_state_changed"
        ],
        "global_flush_requires_named_privilege": True,
        "current_token_global_flush_authorized": privilege["enabled"],
        "no_per_file_eviction_and_residency_contract_identified": True,
        "windows_file_content_state_equivalent_to_linux_proven": False,
        "windows_system_cold_state_proven": False,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": "2026-07-30",
        "upstream_commit": EXPECTED_REVISION,
        "generator": GENERATOR,
        "generator_sha256": sha256(generator.read_bytes()),
        "observer": {
            "path": OBSERVER,
            "sha256": sha256(observer.read_bytes()),
            "repetitions": 2,
        },
        "observation": first,
        "official_contract_sources": OFFICIAL_CONTRACT_SOURCES,
        "cache_state_assessment": {
            "warm": {
                "portable_name_allowed": True,
                "basis": "runner-defined warmup and no eviction",
            },
            "file_content_nonresident_metadata_warm": {
                "portable_name_allowed": False,
                "basis": (
                    "no reviewed native Windows pair provides both "
                    "per-file eviction and pre-run residency proof; "
                    "NO_BUFFERING would alter the measured handle"
                ),
            },
            "system_cold": {
                "portable_name_allowed": False,
                "basis": (
                    "the documented flush is system-global and privileged; "
                    "dedicated-machine isolation and post-state evidence "
                    "are not established"
                ),
            },
            "generic_cold": {
                "allowed": False,
                "basis": "ADR 0015 permanently rejects the ambiguous name",
            },
        },
        "relationships": relationships,
        "scope": {
            "read_only_probe": True,
            "set_system_file_cache_size_called": False,
            "empty_working_set_called": False,
            "flush_file_buffers_called": False,
            "no_buffering_handle_opened": False,
            "benchmark_process_started": False,
            "cache_state_changed": False,
            "windows_strategy_review_input": True,
            "performance_baseline": False,
        },
        "limitations": [
            (
                "This ordinary native Windows observation does not grant "
                "permission to enable SeIncreaseQuotaPrivilege or flush "
                "the global system file cache."
            ),
            (
                "API availability does not prove an equivalent cache "
                "state; the state must also have pre-run evidence and "
                "dedicated isolation where required."
            ),
            (
                "macOS cache-state strategy and any dedicated Windows "
                "system-cold experiment remain separate work."
            ),
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            Path("docs/research/data")
            / "upstream-benchmark-windows-cache-environment.json"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[2]
    try:
        report = build_report(root)
        output = args.output
        if not output.is_absolute():
            output = root / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(serialize(report))
    except (OSError, ProbeError, ValueError) as error:
        print(
            f"Windows cache environment probe error: {error}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
