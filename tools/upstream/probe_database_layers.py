#!/usr/bin/env python3
"""Run the pinned Qt5 DIE engine database-layer research harness."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import pathlib
import subprocess
import sys

import compare_cli_oracles as shared


EXPECTED_LOAD_IDS = (
    "main_only",
    "main_extra",
    "main_custom",
    "all_layers",
)
EXPECTED_SCAN_IDS = (
    "all_unsorted",
    "main_only_unsorted",
    "main_extra_unsorted",
    "main_custom_unsorted",
    "all_sorted",
)
LAYER_NAMES = {
    "main": ["MainLow", "MainShared", "MainHigh"],
    "extra": ["ExtraLow", "ExtraShared", "ExtraHigh"],
    "custom": ["CustomLow", "CustomShared", "CustomHigh"],
}


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_fixture(fixture_dir: pathlib.Path) -> dict[str, object]:
    manifest_path = fixture_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("unexpected fixture schema")
    if manifest.get("generator") != (
        "tools/corpus/generate_database_layer_fixture.py"
    ):
        raise ValueError("unexpected fixture generator")

    expected_files = {"manifest.json"}
    for entry in manifest.get("entries", []):
        if not isinstance(entry, dict):
            raise ValueError("invalid fixture entry")
        relative = pathlib.PurePosixPath(str(entry.get("path", "")))
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or not relative.parts
        ):
            raise ValueError("unsafe fixture path")
        path = fixture_dir.joinpath(*relative.parts)
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"missing fixture file: {relative}")
        if path.stat().st_size != entry.get("size"):
            raise ValueError(f"fixture size mismatch: {relative}")
        if sha256(path) != entry.get("sha256"):
            raise ValueError(f"fixture hash mismatch: {relative}")
        expected_files.add(relative.as_posix())

    actual_files = {
        path.relative_to(fixture_dir).as_posix()
        for path in fixture_dir.rglob("*")
        if path.is_file()
    }
    if actual_files != expected_files:
        raise ValueError("fixture has missing or undeclared files")
    return manifest


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
            "target=/layers,readonly"
        ),
        image,
        binary,
        "/layers",
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


def index_items(
    observation: dict[str, object],
    key: str,
    expected_ids: tuple[str, ...],
) -> dict[str, dict[str, object]]:
    items = observation.get(key)
    if not isinstance(items, list):
        raise ValueError(f"harness output is missing {key}")
    result = {}
    for item in items:
        if not isinstance(item, dict) or not isinstance(
            item.get("id"),
            str,
        ):
            raise ValueError(f"invalid {key} item")
        item_id = item["id"]
        if item_id in result:
            raise ValueError(f"duplicate {key} id: {item_id}")
        result[item_id] = item
    if tuple(result) != expected_ids:
        raise ValueError(f"unexpected {key} order or inventory")
    return result


def signature_layers(records: list[dict[str, object]]) -> list[str]:
    return [str(record["database_type"]) for record in records]


def derive_relationships(
    observation: dict[str, object],
) -> dict[str, bool]:
    loads = index_items(
        observation,
        "load_cases",
        EXPECTED_LOAD_IDS,
    )
    scans = index_items(
        observation,
        "scan_cases",
        EXPECTED_SCAN_IDS,
    )
    all_names = (
        LAYER_NAMES["main"]
        + LAYER_NAMES["extra"]
        + LAYER_NAMES["custom"]
    )
    all_records = observation["all_loaded_signatures"]
    return {
        "all_loads_report_success_without_cancellation": all(
            case["loaded"] and case["load_pd_not_canceled"]
            for case in loads.values()
        ),
        "load_flags_control_materialized_layers": (
            loads["main_only"]["signature_count"] == 3
            and signature_layers(
                loads["main_only"]["signatures"]
            ) == ["main"] * 3
            and loads["main_extra"]["signature_count"] == 6
            and signature_layers(
                loads["main_extra"]["signatures"]
            ) == ["main"] * 3 + ["extra"] * 3
            and loads["main_custom"]["signature_count"] == 6
            and signature_layers(
                loads["main_custom"]["signatures"]
            ) == ["main"] * 3 + ["custom"] * 3
            and loads["all_layers"]["signature_count"] == 9
        ),
        "successful_layers_remain_main_extra_custom_blocks": (
            signature_layers(all_records)
            == ["main"] * 3 + ["extra"] * 3 + ["custom"] * 3
        ),
        "same_named_rules_are_not_deduplicated": (
            sum(
                record["name"] == "shared.5.sg"
                for record in all_records
            )
            == 3
        ),
        "unsorted_scan_preserves_layer_then_priority_order": (
            scans["all_unsorted"]["names"] == all_names
        ),
        "runtime_flags_filter_already_loaded_layers": (
            scans["main_only_unsorted"]["names"]
            == LAYER_NAMES["main"]
            and scans["main_extra_unsorted"]["names"]
            == LAYER_NAMES["main"] + LAYER_NAMES["extra"]
            and scans["main_custom_unsorted"]["names"]
            == LAYER_NAMES["main"] + LAYER_NAMES["custom"]
        ),
        "result_sort_preserves_detection_multiset": (
            sorted(scans["all_sorted"]["names"])
            == sorted(all_names)
        ),
        "all_scan_error_lists_are_empty": all(
            case["errors"] == [] for case in scans.values()
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--binary", required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument(
        "--fixture-dir",
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

    fixture_dir = args.fixture_dir.resolve()
    fixture_manifest = fixture_dir / "manifest.json"
    load_fixture(fixture_dir)
    root = pathlib.Path(__file__).resolve().parents[2]
    source_paths = {
        "harness": (
            root / "tools" / "upstream"
            / "database_layers_harness_main.cpp"
        ),
        "dockerfile": (
            root / "tools" / "upstream"
            / "Dockerfile.database-layers-harness-qt5"
        ),
        "shared_helper": pathlib.Path(shared.__file__).resolve(),
        "fixture_generator": (
            root / "tools" / "corpus"
            / "generate_database_layer_fixture.py"
        ),
    }

    image_id, revision = image_identity(args.image)
    runs = []
    parsed_outputs = []
    failures = []
    for index in range(args.repetitions):
        observation = observe(args.image, args.binary, fixture_dir)
        runs.append(serialize_run(observation))
        if observation.exit_code != 0:
            failures.append(f"run_{index}.exit_code")
            continue
        if observation.stderr:
            failures.append(f"run_{index}.stderr")
        try:
            parsed = json.loads(observation.stdout)
            index_items(parsed, "load_cases", EXPECTED_LOAD_IDS)
            index_items(parsed, "scan_cases", EXPECTED_SCAN_IDS)
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
        "generator": "tools/upstream/probe_database_layers.py",
        "generator_sha256": sha256(pathlib.Path(__file__)),
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
        },
        "source_hashes": {
            name: sha256(path)
            for name, path in source_paths.items()
        },
        "fixture_manifest_sha256": sha256(fixture_manifest),
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
