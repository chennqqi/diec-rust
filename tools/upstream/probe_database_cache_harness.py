#!/usr/bin/env python3
"""Run the pinned Qt5 DIE engine database-cache research harness."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import pathlib
import subprocess
import sys

import compare_cli_oracles as shared


EXPECTED_CASE_IDS = (
    "initial_miss",
    "unchanged_hit",
    "same_stats_stale_hit",
    "stats_changed_rebuild",
    "bad_magic_fallback",
    "truncated_cache_fallback",
    "canceled_cache_hit",
    "canceled_cache_miss",
    "poisoned_empty_cache_hit",
)


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


def observe(
    image: str,
    binary: str,
    fixture_dir: pathlib.Path,
) -> shared.Observation:
    command = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--cpus",
        "2",
        "--memory",
        "1g",
        "--pids-limit",
        "256",
        "--mount",
        (
            f"type=bind,source={fixture_dir},"
            "target=/dbfx,readonly"
        ),
        "--env",
        "XDG_DATA_HOME=/tmp/xdg",
        image,
        binary,
        "/dbfx",
    ]
    result = subprocess.run(command, check=False, capture_output=True)
    return shared.Observation(
        result.returncode,
        result.stdout,
        result.stderr,
    )


def serialize_run(observation: shared.Observation) -> dict[str, object]:
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


def index_cases(
    observation: dict[str, object],
) -> dict[str, dict[str, object]]:
    cases = observation.get("cases")
    if not isinstance(cases, list):
        raise ValueError("harness output is missing cases")
    result = {}
    for case in cases:
        if not isinstance(case, dict) or not isinstance(
            case.get("id"),
            str,
        ):
            raise ValueError("invalid harness case")
        case_id = case["id"]
        if case_id in result:
            raise ValueError(f"duplicate harness case: {case_id}")
        result[case_id] = case
    if tuple(result) != EXPECTED_CASE_IDS:
        raise ValueError("unexpected harness case order or inventory")
    return result


def derive_relationships(
    observation: dict[str, object],
) -> dict[str, bool]:
    cases = index_cases(observation)
    initial = cases["initial_miss"]
    unchanged = cases["unchanged_hit"]
    stale = cases["same_stats_stale_hit"]
    rebuilt = cases["stats_changed_rebuild"]
    bad_magic = cases["bad_magic_fallback"]
    truncated = cases["truncated_cache_fallback"]
    canceled_hit = cases["canceled_cache_hit"]
    canceled_miss = cases["canceled_cache_miss"]
    poisoned = cases["poisoned_empty_cache_hit"]

    initial_hash = initial["cache"]["sha256"]
    rebuilt_hash = rebuilt["cache"]["sha256"]
    poisoned_hash = canceled_miss["cache"]["sha256"]
    return {
        "initial_load_creates_one_record_cache": (
            initial["loaded"]
            and initial["binary_signature_count"] == 1
            and initial["scan_names"] == ["Fixture"]
            and initial["cache"]["exists"]
        ),
        "unchanged_load_reuses_identical_cache": (
            unchanged["cache"]["sha256"] == initial_hash
            and unchanged["scan_names"] == ["Fixture"]
        ),
        "same_size_mtime_content_change_is_stale_hit": (
            stale["cache"]["sha256"] == initial_hash
            and stale["scan_names"] == ["Fixture"]
        ),
        "mtime_change_rebuilds_changed_rule": (
            rebuilt_hash != initial_hash
            and rebuilt["binary_signature_count"] == 1
            and rebuilt["scan_names"] == ["Changed"]
        ),
        "bad_magic_falls_back_and_rewrites": (
            bad_magic["cache"]["sha256"] == rebuilt_hash
            and bad_magic["binary_signature_count"] == 1
            and bad_magic["scan_names"] == ["Changed"]
        ),
        "truncated_cache_injects_partial_record_before_fallback": (
            truncated["cache"]["sha256"] == rebuilt_hash
            and truncated["binary_signature_count"] == 2
            and truncated["scan_names"] == ["Changed"]
        ),
        "canceled_cache_hit_reports_success_with_zero_records": (
            canceled_hit["loaded"]
            and not canceled_hit["load_pd_not_canceled"]
            and canceled_hit["binary_signature_count"] == 0
            and canceled_hit["scan_names"] == ["Unknown"]
            and canceled_hit["cache"]["sha256"] == rebuilt_hash
        ),
        "canceled_miss_saves_empty_cache": (
            canceled_miss["loaded"]
            and not canceled_miss["load_pd_not_canceled"]
            and canceled_miss["binary_signature_count"] == 0
            and canceled_miss["cache"]["size"] < rebuilt["cache"]["size"]
        ),
        "uncanceled_load_reuses_poisoned_empty_cache": (
            poisoned["loaded"]
            and poisoned["load_pd_not_canceled"]
            and poisoned["binary_signature_count"] == 0
            and poisoned["scan_names"] == ["Unknown"]
            and poisoned["cache"]["sha256"] == poisoned_hash
        ),
        "all_scan_error_lists_are_empty": all(
            case["scan_errors"] == [] for case in cases.values()
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--binary", required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument(
        "--database-fixture-dir",
        required=True,
        type=pathlib.Path,
    )
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--output", type=pathlib.Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.repetitions < 2:
        raise ValueError("at least two repetitions are required")

    fixture_dir = args.database_fixture_dir.resolve()
    shared.load_database_fixture(fixture_dir)
    fixture_manifest = fixture_dir / "manifest.json"
    root = pathlib.Path(__file__).resolve().parents[2]
    source_paths = {
        "harness": (
            root / "tools" / "upstream"
            / "database_cache_harness_main.cpp"
        ),
        "dockerfile": (
            root / "tools" / "upstream"
            / "Dockerfile.database-cache-harness-qt5"
        ),
        "shared_helper": pathlib.Path(shared.__file__).resolve(),
        "fixture_generator": (
            root / "tools" / "corpus"
            / "generate_database_fixture.py"
        ),
    }

    image_id, revision = image_identity(args.image)
    runs = []
    parsed_outputs = []
    failures = []
    for index in range(args.repetitions):
        observation = observe(
            args.image,
            args.binary,
            fixture_dir,
        )
        runs.append(serialize_run(observation))
        if observation.exit_code != 0:
            failures.append(f"run_{index}.exit_code")
            continue
        if observation.stderr:
            failures.append(f"run_{index}.stderr")
        try:
            parsed = json.loads(observation.stdout)
            index_cases(parsed)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            failures.append(f"run_{index}.stdout")
            continue
        parsed_outputs.append(parsed)

    raw_outputs_equal = len(
        {run["stdout_sha256"] for run in runs}
    ) == 1 and len(
        {run["stderr_sha256"] for run in runs}
    ) == 1
    if not raw_outputs_equal:
        failures.append("raw_outputs_equal")
    if revision != args.expected_revision:
        failures.append("revision")

    relationships = (
        derive_relationships(parsed_outputs[0])
        if parsed_outputs
        else {}
    )
    failures.extend(
        f"relationship.{name}"
        for name, value in relationships.items()
        if not value
    )

    report = {
        "schema_version": 1,
        "generator": (
            "tools/upstream/probe_database_cache_harness.py"
        ),
        "generator_sha256": hashlib.sha256(
            pathlib.Path(__file__).read_bytes()
        ).hexdigest(),
        "expected_revision": args.expected_revision,
        "image": args.image,
        "image_id": image_id,
        "image_revision": revision,
        "binary": args.binary,
        "resource_limits": {
            "network": "none",
            "cpus": 2,
            "memory_bytes": 1073741824,
            "pids": 256,
            "fixture_mount": "read-only",
            "xdg_data_home": "/tmp/xdg",
        },
        "source_hashes": {
            name: hashlib.sha256(path.read_bytes()).hexdigest()
            for name, path in source_paths.items()
        },
        "fixture_manifest_sha256": hashlib.sha256(
            fixture_manifest.read_bytes()
        ).hexdigest(),
        "repetitions": args.repetitions,
        "runs": runs,
        "raw_outputs_equal": raw_outputs_equal,
        "observation": (
            parsed_outputs[0] if parsed_outputs else None
        ),
        "relationships": relationships,
        "failures": failures,
        "passed": not failures,
    }
    serialized = (
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    )
    if args.output is None:
        sys.stdout.write(serialized)
    else:
        args.output.write_text(
            serialized,
            encoding="utf-8",
            newline="\n",
        )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
