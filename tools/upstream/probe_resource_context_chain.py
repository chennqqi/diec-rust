#!/usr/bin/env python3
"""Verify the pinned CLI resource-to-Binary-rule context chain."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import sys
from typing import Any


def _load_shared_module():
    module_path = pathlib.Path(__file__).with_name(
        "compare_cli_oracles.py"
    )
    spec = importlib.util.spec_from_file_location(
        "_diec_compare_cli_oracles_resource_context",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load shared oracle helpers")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SHARED = _load_shared_module()

SAMPLE_NAME = "pe-manifest-resource.exe"
SAMPLE_SIZE = 1024
SAMPLE_SHA256 = (
    "0a973cbde2f520bdbd6e1b75304e4a412462113d4de9a8139cdf997af16641ee"
)
CASES = (
    SHARED.Case("default", ("--json", *SHARED.DATABASE_ARGS)),
    SHARED.Case(
        "recursive",
        ("--json", "--recursivescan", *SHARED.DATABASE_ARGS),
    ),
    SHARED.Case(
        "aggressive",
        ("--json", "--aggressivecscan", *SHARED.DATABASE_ARGS),
    ),
    SHARED.Case(
        "recursive_aggressive",
        (
            "--json",
            "--recursivescan",
            "--aggressivecscan",
            *SHARED.DATABASE_ARGS,
        ),
    ),
)

ROOT_TREE = [
    {
        "filetype": "PE32",
        "offset": "0",
        "parentfilepart": "Header",
        "size": "1024",
        "values": [
            {
                "name": "Unknown",
                "type": "Unknown",
                "version": "",
            }
        ],
    }
]
RESOURCE_TREE = [
    {
        "filetype": "PE32",
        "offset": "0",
        "parentfilepart": "Header",
        "size": "1024",
        "values": [
            {
                "name": "Unknown",
                "type": "Unknown",
                "version": "",
            },
            {
                "filetype": "Binary",
                "offset": "608",
                "parentfilepart": "Resource",
                "size": "20",
                "values": [
                    {
                        "name": "Manifest",
                        "type": "format",
                        "version": "",
                    }
                ],
            },
        ],
    }
]
EXPECTED_TREES = {
    "default": ROOT_TREE,
    "recursive": ROOT_TREE,
    "aggressive": ROOT_TREE,
    "recursive_aggressive": RESOURCE_TREE,
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_case(
    case_name: str,
    observation: Any,
) -> list[str]:
    failures: list[str] = []
    if observation.exit_code != 0:
        failures.append(f"{case_name}.exit_code")
    if observation.stderr:
        failures.append(f"{case_name}.stderr")
    tree = SHARED.json_detect_tree(observation.stdout)
    if tree != EXPECTED_TREES[case_name]:
        failures.append(f"{case_name}.detect_tree")
    return failures


def inspect_revision(image: str, docker_context: str) -> str:
    process = subprocess.run(
        [
            "docker",
            f"--context={docker_context}",
            "image",
            "inspect",
            "--format",
            (
                "{{index .Config.Labels "
                '"org.opencontainers.image.revision"}}'
            ),
            image,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return process.stdout.strip()


def binary_sha256(
    image: str,
    binary: str,
    docker_context: str,
) -> str:
    process = subprocess.run(
        [
            "docker",
            f"--context={docker_context}",
            "run",
            "--rm",
            "--network=none",
            "--memory=512m",
            "--cpus=1",
            "--pids-limit=128",
            "--entrypoint",
            "sha256sum",
            image,
            binary,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return process.stdout.split()[0]


def observe(
    image: str,
    binary: str,
    arguments: tuple[str, ...],
    corpus_dir: pathlib.Path,
    docker_context: str,
) -> Any:
    command = [
        "docker",
        f"--context={docker_context}",
        "run",
        "--rm",
        "--network=none",
        "--memory=512m",
        "--cpus=1",
        "--pids-limit=128",
        "--mount",
        f"type=bind,source={corpus_dir},target=/corpus,readonly",
        "--entrypoint",
        binary,
        image,
        *arguments,
        f"/corpus/{SAMPLE_NAME}",
    ]
    process = subprocess.run(command, check=False, capture_output=True)
    return SHARED.Observation(
        process.returncode,
        process.stdout,
        process.stderr,
    )


def load_sample(corpus_dir: pathlib.Path) -> dict[str, object]:
    samples = SHARED.load_nested_corpus(corpus_dir)
    by_name = {sample["name"]: sample for sample in samples}
    sample = by_name.get(SAMPLE_NAME)
    if sample is None:
        raise ValueError(f"nested corpus is missing {SAMPLE_NAME}")
    if sample.get("size") != SAMPLE_SIZE:
        raise ValueError("Manifest resource sample size differs")
    if sample.get("sha256") != SAMPLE_SHA256:
        raise ValueError("Manifest resource sample SHA-256 differs")
    return sample


def canonical_baseline(
    expected_revision: str,
    image: str,
    binary: str,
    binary_hash: str,
    sample: dict[str, object],
    observations: dict[str, Any],
) -> dict[str, object]:
    cases = {}
    for case in CASES:
        observation = observations[case.name]
        cases[case.name] = {
            "arguments": [
                *case.arguments,
                f"/corpus/{SAMPLE_NAME}",
            ],
            "exit_code": observation.exit_code,
            "raw_stdout": observation.stdout.decode("utf-8"),
            "raw_stdout_sha256": sha256_bytes(observation.stdout),
            "raw_stderr_hex": observation.stderr.hex(),
            "raw_stderr_sha256": sha256_bytes(observation.stderr),
            "normalized_detect_tree": SHARED.json_detect_tree(
                observation.stdout
            ),
        }
    return {
        "schema_version": 1,
        "upstream_commit": expected_revision,
        "image": image,
        "binary": {
            "path": binary,
            "sha256": binary_hash,
        },
        "sample": sample,
        "cases": cases,
    }


def load_object(path: pathlib.Path) -> dict[str, object]:
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(document, dict):
        raise ValueError(f"{path} root must be a JSON object")
    return document


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--binary", required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--nested-corpus-dir", required=True, type=pathlib.Path)
    parser.add_argument("--baseline", required=True, type=pathlib.Path)
    parser.add_argument("--docker-context", default="default")
    parser.add_argument("--record-baseline", action="store_true")
    args = parser.parse_args()

    revision = inspect_revision(args.image, args.docker_context)
    if revision != args.expected_revision:
        raise SystemExit(f"image revision mismatch: {revision!r}")

    corpus_dir = args.nested_corpus_dir.resolve()
    sample = load_sample(corpus_dir)
    observations = {}
    failures = []
    for case in CASES:
        observation = observe(
            args.image,
            args.binary,
            case.arguments,
            corpus_dir,
            args.docker_context,
        )
        observations[case.name] = observation
        failures.extend(validate_case(case.name, observation))
    if failures:
        raise SystemExit(
            "resource context validation failed: " + ", ".join(failures)
        )

    binary_hash = binary_sha256(
        args.image,
        args.binary,
        args.docker_context,
    )
    actual = canonical_baseline(
        args.expected_revision,
        args.image,
        args.binary,
        binary_hash,
        sample,
        observations,
    )
    canonical = (
        json.dumps(actual, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")
    if args.record_baseline:
        args.baseline.write_bytes(canonical)
    if load_object(args.baseline) != actual:
        raise SystemExit("baseline content differs from current observation")

    report = {
        "schema_version": 1,
        "image": args.image,
        "image_revision": revision,
        "binary": args.binary,
        "binary_sha256": binary_hash,
        "sample": SAMPLE_NAME,
        "sample_sha256": SAMPLE_SHA256,
        "baseline": str(args.baseline).replace("\\", "/"),
        "baseline_sha256": sha256_bytes(args.baseline.read_bytes()),
        "case_count": len(CASES),
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
            sys.stderr.write(str(error.stderr))
        raise
