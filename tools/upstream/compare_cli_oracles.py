#!/usr/bin/env python3
"""Compare observable CLI behavior from two pinned DIE-engine Docker images."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
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


def observe(
    image: str,
    binary: str,
    arguments: Sequence[str],
    corpus_dir: pathlib.Path | None = None,
) -> Observation:
    # The symlink gives both programs the same argv[0], making the Usage line
    # comparable even though their build-tree paths differ.
    command = [
        "docker",
        "run",
        "--rm",
    ]
    if corpus_dir is not None:
        command.extend(
            [
                "--mount",
                f"type=bind,source={corpus_dir},target=/corpus,readonly",
            ]
        )
    command.extend(
        [
            image,
            "sh",
            "-c",
            'ln -sf "$1" /tmp/diec && shift && exec /tmp/diec "$@"',
            "sh",
            binary,
            *arguments,
        ]
    )
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


def load_corpus(corpus_dir: pathlib.Path) -> list[dict[str, object]]:
    manifest_path = corpus_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported corpus manifest schema")
    samples = manifest.get("samples")
    if not isinstance(samples, list) or not samples:
        raise ValueError("corpus manifest has no samples")

    validated = []
    names = set()
    for sample in samples:
        if not isinstance(sample, dict):
            raise ValueError("corpus sample must be an object")
        name = sample.get("name")
        expected_size = sample.get("size")
        expected_sha256 = sample.get("sha256")
        if (
            not isinstance(name, str)
            or pathlib.PurePath(name).name != name
            or name in {".", ".."}
        ):
            raise ValueError(f"unsafe corpus sample name: {name!r}")
        if not isinstance(expected_size, int) or expected_size < 0:
            raise ValueError(f"invalid size for corpus sample: {name}")
        if (
            not isinstance(expected_sha256, str)
            or len(expected_sha256) != 64
            or any(character not in "0123456789abcdef" for character in expected_sha256)
        ):
            raise ValueError(f"invalid SHA-256 for corpus sample: {name}")
        if name in names:
            raise ValueError(f"duplicate corpus sample name: {name}")
        names.add(name)

        data = (corpus_dir / name).read_bytes()
        actual_sha256 = hashlib.sha256(data).hexdigest()
        if len(data) != expected_size or actual_sha256 != expected_sha256:
            raise ValueError(f"corpus sample does not match manifest: {name}")
        validated.append(sample)
    return validated


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--left-image", required=True)
    parser.add_argument("--left-binary", required=True)
    parser.add_argument("--right-image", required=True)
    parser.add_argument("--right-binary", required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--corpus-dir", type=pathlib.Path)
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
    corpus_dir = args.corpus_dir.resolve() if args.corpus_dir else None

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

    if corpus_dir is not None:
        corpus_report = {}
        report["corpus"] = corpus_report
        for sample in load_corpus(corpus_dir):
            name = str(sample["name"])
            arguments = ("--json", *DATABASE_ARGS, f"/corpus/{name}")
            left = observe(
                args.left_image,
                args.left_binary,
                arguments,
                corpus_dir,
            )
            right = observe(
                args.right_image,
                args.right_binary,
                arguments,
                corpus_dir,
            )
            differences = compare_observations(left, right)
            corpus_report[name] = {
                "intended_format": sample.get("intended_format"),
                "size": sample["size"],
                "sha256": sample["sha256"],
                "left": left.summary(),
                "right": right.summary(),
                "differences": differences,
            }
            failures.extend(f"corpus.{name}.{item}" for item in differences)

    report["equal"] = not failures
    report["failures"] = failures
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
