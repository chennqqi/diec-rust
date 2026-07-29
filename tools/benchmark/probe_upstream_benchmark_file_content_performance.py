#!/usr/bin/env python3
"""Measure paired warm and file-content-nonresident upstream processes."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
import struct
import subprocess
import sys
import tempfile
from typing import Any


SCHEMA_VERSION = 1
EXPECTED_REVISION = "74eaf505c250ab47e709024e9dc41657cd8f2254"
EXPECTED_IMAGE = "diec-rust/upstream-benchmark-qt5:74eaf505"
EXPECTED_IMAGE_ID = (
    "sha256:9f1d70a8d4513404cdc457074e00dec"
    "4a9b8a6f043a572ffc17465bbe699eb09"
)
EXPECTED_PLAN_SHA256 = (
    "f93672c9603db16050047095f15d5f5e"
    "a6d9d58663b4574ed901f819f0106e1a"
)
EXPECTED_AFFINITY_SHA256 = (
    "67e6d594a5b93e1b791c11ef89bdb12"
    "e85399964cea9bee87baf591047f5d7de"
)
EXPECTED_ACCESS_SHA256 = (
    "4edfe49fc68861bbfbb04f7b3a8309b6"
    "5eb4f6eba884985b4fe08e5f5ed3f922"
)
EXPECTED_PAGE_CACHE_SHA256 = (
    "081ab455705587089a03401935c8109cd"
    "c271f426e11295b2c848f4186b933eb"
)
EXPECTED_CACHE_ENVIRONMENT_SHA256 = (
    "77ef746852a3a05fd29b8e8a8650f0fe"
    "bb22d123dd3b007451265b4597c72811"
)
EXPECTED_CPU = "0"
EXPECTED_PAGE_SIZE = 4096
PAIRS_PER_CASE = 10
WARM = "warm"
FILE_CONTENT = "file-content-nonresident-metadata-warm"
GENERATOR = (
    "tools/benchmark/"
    "probe_upstream_benchmark_file_content_performance.py"
)
MEASUREMENT_SOURCE = (
    "tools/benchmark/"
    "measure_linux_file_content_benchmark.c"
)
PAGE_CONTROLLER_SOURCE = (
    "tools/benchmark/control_linux_page_cache.c"
)


class FileContentPerformanceError(ValueError):
    """The paired cache-state measurement is not trustworthy."""


def reject_duplicate_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise FileContentPerformanceError(
                f"duplicate JSON key: {key}"
            )
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    raise FileContentPerformanceError(
        f"non-finite JSON constant: {value}"
    )


def parse_json(raw: bytes, description: str) -> dict[str, Any]:
    try:
        value = json.loads(
            raw,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise FileContentPerformanceError(
            f"invalid {description} JSON: {error}"
        ) from error
    if not isinstance(value, dict):
        raise FileContentPerformanceError(
            f"{description} root must be an object"
        )
    return value


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


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


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise FileContentPerformanceError(
            f"cannot load module: {path}"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def require_json(
    path: Path,
    expected_sha256: str,
    description: str,
) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    observed = sha256(raw)
    if observed != expected_sha256:
        raise FileContentPerformanceError(
            f"{description} SHA-256 mismatch: {observed}"
        )
    return parse_json(raw, description), raw


def resource_arguments(limits: dict[str, Any]) -> list[str]:
    return [
        "--network",
        str(limits["network"]),
        "--cpus",
        str(limits["cpus"]),
        "--cpuset-cpus",
        EXPECTED_CPU,
        "--memory",
        str(limits["memory"]),
        "--pids-limit",
        str(limits["pids"]),
    ]


def validate_static_elf(raw: bytes) -> dict[str, Any]:
    if (
        len(raw) < 64
        or raw[:4] != b"\x7fELF"
        or raw[4] != 2
        or raw[5] != 1
    ):
        raise FileContentPerformanceError(
            "measurement controller is not ELF64 little-endian"
        )
    machine = struct.unpack_from("<H", raw, 18)[0]
    program_offset = struct.unpack_from("<Q", raw, 32)[0]
    entry_size = struct.unpack_from("<H", raw, 54)[0]
    entry_count = struct.unpack_from("<H", raw, 56)[0]
    if machine != 62 or entry_size < 56 or entry_count == 0:
        raise FileContentPerformanceError(
            "measurement controller is not Linux x86_64"
        )
    end = program_offset + entry_size * entry_count
    if end > len(raw):
        raise FileContentPerformanceError(
            "measurement controller program headers are truncated"
        )
    types = [
        struct.unpack_from(
            "<I",
            raw,
            program_offset + index * entry_size,
        )[0]
        for index in range(entry_count)
    ]
    if 2 in types or 3 in types:
        raise FileContentPerformanceError(
            "measurement controller contains PT_DYNAMIC or PT_INTERP"
        )
    return {
        "elf_class": "ELF64",
        "machine": "x86_64",
        "program_header_count": entry_count,
        "pt_dynamic_present": False,
        "pt_interp_present": False,
        "statically_linked": True,
    }


def compile_controller(
    image: str,
    limits: dict[str, Any],
    measurement_source: Path,
    page_source: Path,
    exchange: Path,
) -> tuple[Path, dict[str, Any]]:
    binary = exchange / "file-content-measure"
    compile_arguments = [
        "-static",
        "-O2",
        "-std=c11",
        "-Wall",
        "-Wextra",
        "-Werror",
        "/src/measure_linux_file_content_benchmark.c",
        "-o",
        "/io/file-content-measure",
    ]
    command = [
        "docker",
        "run",
        "--rm",
        *resource_arguments(limits),
        "--mount",
        (
            f"type=bind,source={measurement_source.resolve()},"
            "target=/src/measure_linux_file_content_benchmark.c,"
            "readonly"
        ),
        "--mount",
        (
            f"type=bind,source={page_source.resolve()},"
            "target=/src/control_linux_page_cache.c,readonly"
        ),
        "--mount",
        (
            f"type=bind,source={exchange.resolve()},"
            "target=/io"
        ),
        "--entrypoint",
        "/usr/bin/cc",
        image,
        *compile_arguments,
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        timeout=120,
    )
    if (
        completed.returncode != 0
        or completed.stdout
        or completed.stderr
    ):
        raise FileContentPerformanceError(
            "measurement controller compilation failed: "
            f"{completed.stderr.decode(errors='replace')}"
        )
    raw = binary.read_bytes()
    return binary, {
        "measurement_source": MEASUREMENT_SOURCE,
        "measurement_source_sha256": sha256(
            measurement_source.read_bytes()
        ),
        "page_controller_source": PAGE_CONTROLLER_SOURCE,
        "page_controller_source_sha256": sha256(
            page_source.read_bytes()
        ),
        "compile_arguments": compile_arguments,
        "binary_bytes": len(raw),
        "binary_sha256": sha256(raw),
        "clock": "clock_gettime(CLOCK_MONOTONIC)",
        "peak_rss_method": "wait4 child rusage.ru_maxrss * 1024",
        "timeout_seconds": 120,
        "max_capture_bytes_per_stream": 64 * 1024 * 1024,
        **validate_static_elf(raw),
    }


def parse_tsv(raw: bytes) -> dict[str, str]:
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise FileContentPerformanceError(
            f"measurement output is not UTF-8: {error}"
        ) from error
    result = {}
    for line in lines:
        name, separator, value = line.partition("\t")
        if not separator or not name or name in result:
            raise FileContentPerformanceError(
                "invalid or duplicate measurement field"
            )
        result[name] = value
    expected = {
        "schema_version",
        "cache_state",
        "fadvise_executed",
        "page_size",
        "file_count",
        "logical_pages",
        "resident_pages_after_warm",
        "resident_pages_before_run",
        "before_run_page_state_verified",
        "duration_ns",
        "peak_rss_bytes",
        "exit_code",
        "timed_out",
    }
    if set(result) != expected:
        raise FileContentPerformanceError(
            "measurement fields changed"
        )
    return result


def parse_measurement(
    raw: bytes,
    cache_state: str,
    file_count: int,
    logical_pages: int,
) -> dict[str, Any]:
    fields = parse_tsv(raw)
    integers = {}
    for name, value in fields.items():
        if name == "cache_state":
            continue
        if not value.isascii() or not value.isdecimal():
            raise FileContentPerformanceError(
                f"measurement {name} is not an unsigned integer"
            )
        integers[name] = int(value)
    expected_before = (
        logical_pages if cache_state == WARM else 0
    )
    if (
        fields["cache_state"] != cache_state
        or integers["schema_version"] != 1
        or integers["fadvise_executed"]
        != (0 if cache_state == WARM else 1)
        or integers["page_size"] != EXPECTED_PAGE_SIZE
        or integers["file_count"] != file_count
        or integers["logical_pages"] != logical_pages
        or integers["resident_pages_after_warm"]
        != logical_pages
        or integers["resident_pages_before_run"]
        != expected_before
        or integers["before_run_page_state_verified"] != 1
        or integers["duration_ns"] <= 0
        or integers["peak_rss_bytes"] <= 0
        or integers["exit_code"] != 0
        or integers["timed_out"] != 0
    ):
        raise FileContentPerformanceError(
            "measurement invariant failed"
        )
    return {
        "duration_ns": integers["duration_ns"],
        "peak_rss_bytes": integers["peak_rss_bytes"],
        "exit_code": 0,
        "controller_evidence": {
            "fadvise_executed": (
                integers["fadvise_executed"] == 1
            ),
            "file_count": file_count,
            "logical_pages": logical_pages,
            "resident_pages_after_warm": logical_pages,
            "resident_pages_before_run": expected_before,
            "before_run_page_state_verified": True,
        },
    }


def run_sample(
    image: str,
    limits: dict[str, Any],
    exchange: Path,
    binary: Path,
    plan: dict[str, Any],
    cache_state: str,
    manifest: Path,
    file_count: int,
    logical_pages: int,
    baseline_case: dict[str, Any],
    prefix: str,
) -> dict[str, Any]:
    result_path = exchange / f"{prefix}.tsv"
    stdout_path = exchange / f"{prefix}.stdout"
    stderr_path = exchange / f"{prefix}.stderr"
    command = [
        "docker",
        "run",
        "--rm",
        *resource_arguments(limits),
        "--mount",
        (
            f"type=bind,source={exchange.resolve()},"
            "target=/io"
        ),
    ]
    for key in sorted(plan["environment"]):
        command.extend(
            ["--env", f"{key}={plan['environment'][key]}"]
        )
    command.extend(
        [
            "--entrypoint",
            f"/io/{binary.name}",
            image,
            "--cache-state",
            cache_state,
            "--manifest",
            f"/io/{manifest.name}",
            "--output",
            f"/io/{result_path.name}",
            "--stdout",
            f"/io/{stdout_path.name}",
            "--stderr",
            f"/io/{stderr_path.name}",
            "--",
            *plan["command"],
        ]
    )
    completed = subprocess.run(
        command,
        capture_output=True,
        timeout=180,
    )
    if completed.returncode != 0:
        raise FileContentPerformanceError(
            f"{plan['benchmark_id']} {cache_state} failed: "
            f"{completed.stderr.decode(errors='replace')}"
        )
    if completed.stdout or completed.stderr:
        raise FileContentPerformanceError(
            "measurement controller emitted output"
        )
    measurement = parse_measurement(
        result_path.read_bytes(),
        cache_state,
        file_count,
        logical_pages,
    )
    stdout_raw = stdout_path.read_bytes()
    stderr_raw = stderr_path.read_bytes()
    if (
        len(stdout_raw)
        > plan["max_stdout_bytes"]
        or len(stderr_raw)
        > plan["max_stderr_bytes"]
        or stderr_raw
        or len(stdout_raw)
        != baseline_case["runs"][0]["stdout"]["bytes"]
        or sha256(stdout_raw)
        not in baseline_case["summary"]["stdout_unique_sha256"]
    ):
        raise FileContentPerformanceError(
            f"{plan['benchmark_id']} output identity mismatch"
        )
    measurement["stdout"] = {
        "bytes": len(stdout_raw),
        "sha256": sha256(stdout_raw),
    }
    measurement["stderr"] = {
        "bytes": 0,
        "sha256": sha256(b""),
    }
    return measurement


def nearest_rank(values: list[int], percentile: float) -> int:
    rank = max(1, math.ceil(percentile * len(values)))
    return sorted(values)[rank - 1]


def summarize_values(values: list[int]) -> dict[str, int]:
    median = int(statistics.median(values))
    return {
        "min": min(values),
        "median": median,
        "p95_nearest_rank": nearest_rank(values, 0.95),
        "max": max(values),
        "mad": int(
            statistics.median(
                abs(value - median) for value in values
            )
        ),
    }


def build_case(
    *,
    image: str,
    limits: dict[str, Any],
    exchange: Path,
    binary: Path,
    plan: dict[str, Any],
    records: list[dict[str, Any]],
    baseline_case: dict[str, Any],
    page_probe: Any,
    process_runner: Any,
) -> dict[str, Any]:
    benchmark_id = plan["benchmark_id"]
    manifest = exchange / (
        benchmark_id.replace(".", "-") + ".manifest"
    )
    manifest_raw = page_probe.write_manifest(manifest, records)
    logical_pages = sum(
        math.ceil(record["bytes"] / EXPECTED_PAGE_SIZE)
        for record in records
    )
    pairs = []
    state_runs = {WARM: [], FILE_CONTENT: []}
    for pair_index in range(PAIRS_PER_CASE):
        order = (
            [WARM, FILE_CONTENT]
            if pair_index % 2 == 0
            else [FILE_CONTENT, WARM]
        )
        pair = {"pair_index": pair_index, "order": order}
        for cache_state in order:
            prefix = (
                f"{benchmark_id.replace('.', '-')}-"
                f"{pair_index}-{cache_state[:4]}"
            )
            run = run_sample(
                image,
                limits,
                exchange,
                binary,
                plan,
                cache_state,
                manifest,
                len(records),
                logical_pages,
                baseline_case,
                prefix,
            )
            state_runs[cache_state].append(run)
            pair[cache_state] = run
        warm_ns = pair[WARM]["duration_ns"]
        file_ns = pair[FILE_CONTENT]["duration_ns"]
        pair["duration_delta_ns"] = file_ns - warm_ns
        pair["duration_ratio_file_over_warm"] = (
            file_ns / warm_ns
        )
        pairs.append(pair)
    summaries = {
        state: process_runner.summarize_runs(
            runs,
            int(plan["work_bytes"]),
        )
        for state, runs in state_runs.items()
    }
    ratios_scaled = [
        round(
            pair["duration_ratio_file_over_warm"] * 1_000_000
        )
        for pair in pairs
    ]
    deltas = [pair["duration_delta_ns"] for pair in pairs]
    return {
        "benchmark_id": benchmark_id,
        "pair_count": PAIRS_PER_CASE,
        "sample_count": PAIRS_PER_CASE * 2,
        "order_policy": "ABBA alternating by pair index",
        "manifest": {
            "bytes": len(manifest_raw),
            "sha256": sha256(manifest_raw),
            "file_count": len(records),
            "file_bytes": sum(
                record["bytes"] for record in records
            ),
            "logical_pages": logical_pages,
        },
        "work_bytes": plan["work_bytes"],
        "work_definition": plan["work_definition"],
        "pairs": pairs,
        "state_summaries": summaries,
        "paired_effect": {
            "duration_delta_ns": summarize_values(deltas),
            "duration_ratio_file_over_warm_scaled_1e6": (
                summarize_values(ratios_scaled)
            ),
            "negative_delta_pair_count": sum(
                delta < 0 for delta in deltas
            ),
        },
        "outputs_identical_across_states": (
            summaries[WARM]["stdout_unique_sha256"]
            == summaries[FILE_CONTENT][
                "stdout_unique_sha256"
            ]
            and summaries[WARM]["stderr_unique_sha256"]
            == summaries[FILE_CONTENT][
                "stderr_unique_sha256"
            ]
        ),
    }


def build_report(
    repo: Path,
    image: str,
    plans_path: Path,
    affinity_path: Path,
    access_path: Path,
    page_cache_path: Path,
    cache_environment_path: Path,
) -> dict[str, Any]:
    repo = repo.resolve(strict=True)
    benchmark_probe = load_module(
        "probe_upstream_benchmark_for_file_content_performance",
        repo / "tools/benchmark/probe_upstream_benchmark.py",
    )
    process_runner = load_module(
        "run_process_benchmark_for_file_content_performance",
        repo / "tools/benchmark/run_process_benchmark.py",
    )
    page_probe = load_module(
        "probe_upstream_benchmark_page_cache_for_performance",
        repo / "tools/benchmark/probe_upstream_benchmark_page_cache.py",
    )
    plans, plans_raw = benchmark_probe.load_plans(plans_path)
    if sha256(plans_raw) != EXPECTED_PLAN_SHA256:
        raise FileContentPerformanceError(
            "benchmark plan SHA-256 mismatch"
        )
    affinity, affinity_raw = require_json(
        affinity_path,
        EXPECTED_AFFINITY_SHA256,
        "affinity baseline",
    )
    if benchmark_probe.evaluate_report(affinity):
        raise FileContentPerformanceError(
            "affinity baseline verifier failed"
        )
    access, access_raw = require_json(
        access_path,
        EXPECTED_ACCESS_SHA256,
        "file-access report",
    )
    page_cache, page_cache_raw = require_json(
        page_cache_path,
        EXPECTED_PAGE_CACHE_SHA256,
        "page-cache report",
    )
    cache_environment, cache_environment_raw = require_json(
        cache_environment_path,
        EXPECTED_CACHE_ENVIRONMENT_SHA256,
        "cache-environment report",
    )
    image_identity = benchmark_probe.docker_inspect(image)
    if (
        image_identity["id"] != EXPECTED_IMAGE_ID
        or any(
            report["environment"]["image_identity"]
            != image_identity
            for report in (
                affinity,
                access,
                page_cache,
                cache_environment,
            )
        )
    ):
        raise FileContentPerformanceError(
            "benchmark image identity mismatch"
        )
    limits = plans["container_limits"]
    cgroup = benchmark_probe.observe_cgroup(
        image,
        limits,
        cpuset_cpu=EXPECTED_CPU,
    )
    measurement_source = repo / MEASUREMENT_SOURCE
    page_source = repo / PAGE_CONTROLLER_SOURCE
    with tempfile.TemporaryDirectory() as directory:
        exchange = Path(directory)
        binary, controller = compile_controller(
            image,
            limits,
            measurement_source,
            page_source,
            exchange,
        )
        cases = {}
        for plan in plans["plans"]:
            benchmark_id = plan["benchmark_id"]
            records = page_probe.case_records(
                access,
                benchmark_id,
            )
            baseline_case = affinity["case_reports"][
                benchmark_id
            ]["report"]
            case = build_case(
                image=image,
                limits=limits,
                exchange=exchange,
                binary=binary,
                plan=plan,
                records=records,
                baseline_case=baseline_case,
                page_probe=page_probe,
                process_runner=process_runner,
            )
            if not case["outputs_identical_across_states"]:
                raise FileContentPerformanceError(
                    f"{benchmark_id} outputs differ across states"
                )
            cases[benchmark_id] = case
    relationships = {
        "all_cases_use_identical_measurement_controller": True,
        "all_cases_have_ten_abba_pairs": all(
            case["pair_count"] == PAIRS_PER_CASE
            for case in cases.values()
        ),
        "all_warm_runs_verify_every_candidate_page_resident": True,
        "all_file_content_runs_verify_every_candidate_page_nonresident": True,
        "all_outputs_match_affinity_baseline": True,
        "all_outputs_identical_across_cache_states": all(
            case["outputs_identical_across_states"]
            for case in cases.values()
        ),
        "preparation_time_is_excluded": True,
        "container_start_time_is_excluded": True,
        "regression_thresholds_are_not_frozen": True,
        "generic_cold_is_not_claimed": True,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generator": GENERATOR,
        "generator_sha256": sha256(Path(__file__).read_bytes()),
        "upstream_commit": EXPECTED_REVISION,
        "environment": {
            "network": "none",
            "image": image,
            "image_identity": image_identity,
            "container_limits": limits,
            "cgroup": cgroup,
            "cpu_affinity": {
                "requested_cpuset_cpu": EXPECTED_CPU,
                "scope": "linux_vcpu",
            },
            "page_size": EXPECTED_PAGE_SIZE,
        },
        "controller": controller,
        "inputs": {
            "plan_suite": {
                "path": plans_path.relative_to(repo).as_posix(),
                "bytes": len(plans_raw),
                "sha256": EXPECTED_PLAN_SHA256,
            },
            "affinity_baseline": {
                "path": affinity_path.relative_to(repo).as_posix(),
                "bytes": len(affinity_raw),
                "sha256": EXPECTED_AFFINITY_SHA256,
            },
            "successful_file_access": {
                "path": access_path.relative_to(repo).as_posix(),
                "bytes": len(access_raw),
                "sha256": EXPECTED_ACCESS_SHA256,
            },
            "page_cache": {
                "path": page_cache_path.relative_to(repo).as_posix(),
                "bytes": len(page_cache_raw),
                "sha256": EXPECTED_PAGE_CACHE_SHA256,
            },
            "cache_environment": {
                "path": cache_environment_path.relative_to(
                    repo
                ).as_posix(),
                "bytes": len(cache_environment_raw),
                "sha256": EXPECTED_CACHE_ENVIRONMENT_SHA256,
            },
        },
        "cache_states": {
            WARM: {
                "candidate_content_pages_before_run": "all resident",
                "metadata": "warm",
                "fadvise": False,
            },
            FILE_CONTENT: {
                "candidate_content_pages_before_run": (
                    "all nonresident"
                ),
                "metadata": "warm",
                "fadvise": True,
            },
        },
        "pairs_per_case": PAIRS_PER_CASE,
        "total_measured_processes": (
            len(cases) * PAIRS_PER_CASE * 2
        ),
        "cases": {name: cases[name] for name in sorted(cases)},
        "relationships": relationships,
        "scope": {
            "descriptive_upstream_cache_state_spike": True,
            "same_launcher_clock_and_rss_method_across_states": True,
            "direct_child_process_only": True,
            "metadata_cache_controlled": False,
            "system_cold_cache_controlled": False,
            "rust_paired_measurements_present": False,
            "long_horizon_sessions_present": False,
            "physical_core_topology_proven": False,
            "regression_thresholds_frozen": False,
        },
        "limitations": [
            "each sample starts a fresh Docker container, but container creation and cache preparation are outside the measured interval",
            "both states deliberately warm pathname, dentry and inode metadata; only candidate content-page residency differs",
            "wait4 ru_maxrss measures the direct child and is not interchangeable with the historical Python polling RSS method",
            "the ABBA order reduces monotonic drift but this is one consecutive session on one WSL2 Linux vCPU",
            "no Rust implementation exists for same-case randomized pairing and no regression threshold is frozen",
        ],
    }


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    data = root / "docs/research/data"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=root)
    parser.add_argument("--image", default=EXPECTED_IMAGE)
    parser.add_argument(
        "--plans",
        type=Path,
        default=data / "upstream-benchmark-plans.json",
    )
    parser.add_argument(
        "--affinity-baseline",
        type=Path,
        default=data / "upstream-benchmark-linux-qt5-affinity.json",
    )
    parser.add_argument(
        "--file-access",
        type=Path,
        default=data / "upstream-benchmark-linux-qt5-file-access.json",
    )
    parser.add_argument(
        "--page-cache",
        type=Path,
        default=data / "upstream-benchmark-linux-qt5-page-cache.json",
    )
    parser.add_argument(
        "--cache-environment",
        type=Path,
        default=(
            data
            / "upstream-benchmark-linux-qt5-cache-environment.json"
        ),
    )
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = build_report(
            args.repo,
            args.image,
            args.plans,
            args.affinity_baseline,
            args.file_access,
            args.page_cache,
            args.cache_environment,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(serialize(report))
    except (
        FileContentPerformanceError,
        OSError,
        subprocess.SubprocessError,
    ) as error:
        print(
            f"file-content performance probe error: {error}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
