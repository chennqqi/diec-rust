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

OUTPUT_MATRIX = (
    Case("text", DATABASE_ARGS),
    Case("plaintext", ("--plaintext", *DATABASE_ARGS)),
    Case("json", ("--json", *DATABASE_ARGS)),
    Case("xml", ("--xml", *DATABASE_ARGS)),
    Case("csv", ("--csv", *DATABASE_ARGS)),
    Case("tsv", ("--tsv", *DATABASE_ARGS)),
    Case(
        "all_output_flags",
        (
            "--xml",
            "--json",
            "--csv",
            "--tsv",
            "--plaintext",
            *DATABASE_ARGS,
        ),
    ),
)

SCAN_MATRIX = (
    Case("default", ("--json", *DATABASE_ARGS)),
    Case("deep", ("--json", "--deepscan", *DATABASE_ARGS)),
    Case("heuristic", ("--json", "--heuristicscan", *DATABASE_ARGS)),
    Case("aggressive", ("--json", "--aggressivecscan", *DATABASE_ARGS)),
    Case("alltypes", ("--json", "--alltypes", *DATABASE_ARGS)),
    Case("format", ("--json", "--format", *DATABASE_ARGS)),
    Case("hideunknown", ("--json", "--hideunknown", *DATABASE_ARGS)),
    Case(
        "combined",
        (
            "--json",
            "--deepscan",
            "--heuristicscan",
            "--aggressivecscan",
            "--alltypes",
            *DATABASE_ARGS,
        ),
    ),
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
    parser.add_argument(
        "--matrix-sample",
        action="append",
        default=[],
        help="Corpus sample to include in output/scan option matrices",
    )
    parser.add_argument(
        "--matrix-all",
        action="store_true",
        help="Include every corpus sample in the selected matrices",
    )
    parser.add_argument(
        "--matrix-kind",
        choices=("both", "output", "scan"),
        default="both",
    )
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
        samples = load_corpus(corpus_dir)
        samples_by_name = {str(sample["name"]): sample for sample in samples}
        for sample in samples:
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

        matrix_names = (
            list(samples_by_name)
            if args.matrix_all
            else list(dict.fromkeys(args.matrix_sample))
        )
        if matrix_names:
            unknown_samples = sorted(
                set(matrix_names) - samples_by_name.keys()
            )
            if unknown_samples:
                raise ValueError(
                    "matrix samples are not in corpus: "
                    + ", ".join(unknown_samples)
                )

            matrix_report = {}
            report["matrix"] = matrix_report
            for name in matrix_names:
                sample_report = {}
                matrix_report[name] = sample_report
                container_path = f"/corpus/{name}"

                if args.matrix_kind in {"both", "output"}:
                    output_report = {}
                    sample_report["output"] = output_report
                    for case in OUTPUT_MATRIX:
                        arguments = (*case.arguments, container_path)
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
                        output_report[case.name] = {
                            "left": left.summary(),
                            "right": right.summary(),
                            "differences": differences,
                        }
                        failures.extend(
                            f"matrix.{name}.output.{case.name}.{item}"
                            for item in differences
                        )

                if args.matrix_kind in {"both", "scan"}:
                    scan_report = {}
                    sample_report["scan"] = scan_report
                    scan_observations = {}
                    for case in SCAN_MATRIX:
                        arguments = (*case.arguments, container_path)
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
                        scan_observations[case.name] = (left, right)
                        scan_report[case.name] = {
                            "left": left.summary(),
                            "right": right.summary(),
                            "differences": differences,
                        }
                        failures.extend(
                            f"matrix.{name}.scan.{case.name}.{item}"
                            for item in differences
                        )

                    default_left, default_right = scan_observations["default"]
                    for case_name, (left, right) in scan_observations.items():
                        entry = scan_report[case_name]
                        entry["left_changes"] = compare_observations(
                            default_left, left
                        )
                        entry["right_changes"] = compare_observations(
                            default_right, right
                        )
    elif args.matrix_sample or args.matrix_all:
        raise ValueError("matrix options require --corpus-dir")

    report["equal"] = not failures
    report["failures"] = failures
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
