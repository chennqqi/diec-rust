#!/usr/bin/env python3
"""Compare observable CLI behavior from two pinned DIE-engine Docker images."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from typing import Sequence


DATABASE_ARGS = (
    "--database",
    "/opt/die-source/Detect-It-Easy/db",
    "--extradatabase",
    "/opt/die-source/Detect-It-Easy/db_extra",
    "--customdatabase",
    "/opt/die-source/Detect-It-Easy/db_custom",
)


@dataclass(frozen=True)
class Observation:
    exit_code: int
    stdout: bytes
    stderr: bytes

    def summary(self) -> dict[str, object]:
        return {
            "exit_code": self.exit_code,
            "stdout_sha256": hashlib.sha256(self.stdout).hexdigest(),
            "stderr_sha256": hashlib.sha256(self.stderr).hexdigest(),
        }


@dataclass(frozen=True)
class Case:
    name: str
    arguments: tuple[str, ...]


CASES = (
    Case("version", ("--version",)),
    Case("help", ("--help",)),
    Case("database", ("--showdatabase", *DATABASE_ARGS)),
    Case("true_json", ("--json", *DATABASE_ARGS, "/usr/bin/true")),
    Case("no_args", ()),
    Case("missing", ("/does-not-exist",)),
)


def observe(image: str, binary: str, arguments: Sequence[str]) -> Observation:
    # The symlink gives both programs the same argv[0], making the Usage line
    # comparable even though their build-tree paths differ.
    command = [
        "docker",
        "run",
        "--rm",
        image,
        "sh",
        "-c",
        'ln -sf "$1" /tmp/diec && shift && exec /tmp/diec "$@"',
        "sh",
        binary,
        *arguments,
    ]
    result = subprocess.run(command, check=False, capture_output=True)
    return Observation(result.returncode, result.stdout, result.stderr)


def image_revision(image: str) -> str:
    result = subprocess.run(
        ["docker", "image", "inspect", image],
        check=True,
        capture_output=True,
        text=True,
    )
    document = json.loads(result.stdout)
    return document[0]["Config"]["Labels"]["org.opencontainers.image.revision"]


def sample_sha256(image: str) -> str:
    result = subprocess.run(
        ["docker", "run", "--rm", image, "sha256sum", "/usr/bin/true"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.split()[0]


def compare_observations(
    left: Observation, right: Observation
) -> list[str]:
    differences = []
    if left.exit_code != right.exit_code:
        differences.append("exit_code")
    if left.stdout != right.stdout:
        differences.append("stdout")
    if left.stderr != right.stderr:
        differences.append("stderr")
    return differences


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--left-image", required=True)
    parser.add_argument("--left-binary", required=True)
    parser.add_argument("--right-image", required=True)
    parser.add_argument("--right-binary", required=True)
    parser.add_argument("--expected-revision", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report: dict[str, object] = {
        "expected_revision": args.expected_revision,
        "left_image": args.left_image,
        "right_image": args.right_image,
        "cases": {},
    }
    failures = []

    for side, image in (
        ("left", args.left_image),
        ("right", args.right_image),
    ):
        revision = image_revision(image)
        report[f"{side}_revision"] = revision
        if revision != args.expected_revision:
            failures.append(f"{side}_revision")

    left_sample = sample_sha256(args.left_image)
    right_sample = sample_sha256(args.right_image)
    report["sample"] = {
        "path": "/usr/bin/true",
        "left_sha256": left_sample,
        "right_sha256": right_sample,
    }
    if left_sample != right_sample:
        failures.append("sample_sha256")

    case_report = report["cases"]
    assert isinstance(case_report, dict)
    for case in CASES:
        left = observe(args.left_image, args.left_binary, case.arguments)
        right = observe(args.right_image, args.right_binary, case.arguments)
        differences = compare_observations(left, right)
        case_report[case.name] = {
            "arguments": list(case.arguments),
            "left": left.summary(),
            "right": right.summary(),
            "differences": differences,
        }
        failures.extend(f"{case.name}.{item}" for item in differences)

    report["equal"] = not failures
    report["failures"] = failures
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
