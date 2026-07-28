#!/usr/bin/env python3
"""Collect deterministic native-Windows Qt5 junction/path behavior."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Sequence


ROOT = Path(__file__).resolve().parents[2]
BASELINE_SCRIPT = ROOT / "tools/upstream/collect_windows_cli_baseline.py"
FIXTURE_SCRIPT = (
    ROOT / "tools/corpus/generate_windows_filesystem_fixture.py"
)


def load_module(name: str, path: Path) -> object:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load helper module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


baseline = load_module(
    "collect_windows_cli_baseline_filesystem_helper",
    BASELINE_SCRIPT,
)
fixture_generator = load_module(
    "generate_windows_filesystem_fixture_helper",
    FIXTURE_SCRIPT,
)
ProbeError = baseline.BaselineError


@dataclass(frozen=True)
class Case:
    name: str
    arguments: tuple[str, ...]
    report_arguments: tuple[str, ...]
    expected_exit: int = 0


def extended_path(path: Path) -> str:
    absolute = str(path.absolute())
    if absolute.startswith("\\\\"):
        return "\\\\?\\UNC\\" + absolute[2:]
    return "\\\\?\\" + absolute


def observe(
    binary: Path,
    qt_dir: Path,
    arguments: Sequence[str],
    *,
    timeout_seconds: int,
) -> object:
    environment = os.environ.copy()
    path_key = next(
        (key for key in environment if key.upper() == "PATH"),
        "PATH",
    )
    environment[path_key] = (
        str(qt_dir / "bin")
        + os.pathsep
        + environment.get(path_key, "")
    )
    result = subprocess.run(
        [binary.name, *arguments],
        executable=str(binary),
        cwd=binary.parent,
        env=environment,
        check=False,
        capture_output=True,
        timeout=timeout_seconds,
    )
    return baseline.Observation(
        result.returncode,
        result.stdout,
        result.stderr,
    )


def database_arguments(
    source_dir: Path,
    *,
    report: bool,
) -> tuple[str, ...]:
    root = "<source>" if report else str(source_dir)
    return (
        "--database",
        f"{root}/Detect-It-Easy/db",
        "--extradatabase",
        f"{root}/Detect-It-Easy/db_extra",
        "--customdatabase",
        f"{root}/Detect-It-Easy/db_custom",
    )


def build_cases(source_dir: Path, fixture_dir: Path) -> tuple[Case, ...]:
    actual_db = database_arguments(source_dir, report=False)
    report_db = database_arguments(source_dir, report=True)

    def ordinary(relative: str) -> str:
        return str(fixture_dir.joinpath(*relative.split("/")))

    def report(relative: str) -> str:
        return f"<fixture>/{relative}"

    def make(
        name: str,
        relative: str,
        *,
        extended: bool = False,
    ) -> Case:
        actual = fixture_dir.joinpath(*relative.split("/"))
        return Case(
            name,
            (
                "--json",
                *actual_db,
                extended_path(actual) if extended else str(actual),
            ),
            (
                "--json",
                *report_db,
                (
                    f"<extended-fixture>/{relative}"
                    if extended
                    else report(relative)
                ),
            ),
        )

    return (
        make("single_real_file", "single/target.pdf"),
        make(
            "single_file_through_junction",
            "direct-alias/child.pdf",
        ),
        make("directory_real", "direct-target"),
        make("directory_junction", "direct-alias"),
        make("directory_junction_chain", "chain-entry"),
        make("tree_real_and_junction", "tree"),
        make(
            "extended_single_real_file",
            "single/target.pdf",
            extended=True,
        ),
        make(
            "extended_directory_junction",
            "direct-alias",
            extended=True,
        ),
    )


def prefix_ids(data: bytes, paths: dict[str, Path]) -> list[str]:
    positions = []
    for case_id, path in paths.items():
        prefix = str(path).encode("utf-8") + b":\r\n"
        start = 0
        while True:
            index = data.find(prefix, start)
            if index < 0:
                break
            positions.append((index, case_id))
            start = index + len(prefix)
    positions.sort()
    return [case_id for _, case_id in positions]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--qt-dir", type=Path, required=True)
    parser.add_argument("--fixture-dir", type=Path, required=True)
    parser.add_argument("--expected-binary-sha256", required=True)
    parser.add_argument(
        "--fixture-manifest",
        type=Path,
        default=ROOT
        / "docs/research/data/windows-filesystem-fixture.json",
    )
    parser.add_argument(
        "--windows-baseline",
        type=Path,
        default=ROOT
        / "docs/research/data/baseline-corpus-windows-qt5.json",
    )
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if os.name != "nt":
        raise ProbeError("native Windows probe requires os.name == 'nt'")
    if args.timeout_seconds < 1 or args.timeout_seconds > 3600:
        raise ProbeError("timeout-seconds must be in 1..3600")

    source_dir = args.source_dir.resolve(strict=True)
    qt_dir = args.qt_dir.resolve(strict=True)
    fixture_dir = args.fixture_dir.resolve(strict=True)
    binary = args.binary.resolve(strict=True)
    expected_binary = (
        source_dir / "build" / "release" / "diec.exe"
    ).resolve(strict=True)
    if binary != expected_binary:
        raise ProbeError("binary must be <source>/build/release/diec.exe")
    binary_sha256 = baseline.sha256_file(binary)
    if binary_sha256 != args.expected_binary_sha256:
        raise ProbeError("binary SHA-256 mismatch")

    source_identity = baseline.validate_source(source_dir)
    qt_identity = baseline.validate_qt(qt_dir)
    manifest_path = args.fixture_manifest.resolve(strict=True)
    manifest_raw = (fixture_dir / "manifest.json").read_bytes()
    if manifest_raw != manifest_path.read_bytes():
        raise ProbeError("Windows filesystem fixture manifest differs")
    manifest = json.loads(manifest_raw)
    fixture_generator.validate_fixture(fixture_dir, manifest)

    baseline_path = args.windows_baseline.resolve(strict=True)
    baseline_raw = baseline_path.read_bytes()
    baseline_report = json.loads(baseline_raw)
    if baseline_report["binary"]["sha256"] != binary_sha256:
        raise ProbeError("Windows baseline binary identity differs")
    reference_tree = baseline_report["corpus"]["minimal.pdf"][
        "first_detect_tree"
    ]

    known_paths = {
        "tree_real": fixture_dir / "tree" / "real" / "child.pdf",
        "tree_alias": fixture_dir / "tree" / "alias" / "child.pdf",
    }
    cases = build_cases(source_dir, fixture_dir)
    reports = {}
    determinism_failures = []
    expected_exit_failures = []
    reference_projection_failures = []
    for case in cases:
        first = observe(
            binary,
            qt_dir,
            case.arguments,
            timeout_seconds=args.timeout_seconds,
        )
        second = observe(
            binary,
            qt_dir,
            case.arguments,
            timeout_seconds=args.timeout_seconds,
        )
        paired = baseline.pair_report(first, second)
        try:
            json.loads(first.stdout)
            first_valid_json = True
        except (UnicodeDecodeError, json.JSONDecodeError):
            first_valid_json = False
        try:
            json.loads(second.stdout)
            second_valid_json = True
        except (UnicodeDecodeError, json.JSONDecodeError):
            second_valid_json = False
        first_tree = baseline.json_detect_tree(first.stdout)
        second_tree = baseline.json_detect_tree(second.stdout)
        projection_applies = first_valid_json
        paired.update(
            {
                "cwd": "<binary-dir>",
                "arguments": list(case.report_arguments),
                "expected_exit_code": case.expected_exit,
                "expected_exit_code_equal": (
                    first.exit_code == case.expected_exit
                ),
                "first_valid_json": first_valid_json,
                "second_valid_json": second_valid_json,
                "first_detect_tree": first_tree,
                "second_detect_tree": second_tree,
                "reference_projection_applies": projection_applies,
                "minimal_pdf_detect_tree_equal": (
                    first_tree == reference_tree
                    if projection_applies
                    else None
                ),
                "first_prefix_ids": prefix_ids(
                    first.stdout,
                    known_paths,
                ),
                "second_prefix_ids": prefix_ids(
                    second.stdout,
                    known_paths,
                ),
            }
        )
        reports[case.name] = paired
        if paired["determinism_differences"]:
            determinism_failures.append(case.name)
        if first.exit_code != case.expected_exit:
            expected_exit_failures.append(case.name)
        if projection_applies and first_tree != reference_tree:
            reference_projection_failures.append(case.name)

    ordinary_file = reports["single_real_file"]
    extended_file = reports["extended_single_real_file"]
    ordinary_junction = reports["directory_junction"]
    extended_junction = reports["extended_directory_junction"]
    tree_case = reports["tree_real_and_junction"]
    findings = {
        "explicit_file_through_junction_is_scanned": (
            reports["single_file_through_junction"][
                "minimal_pdf_detect_tree_equal"
            ]
            is True
        ),
        "explicit_junction_directory_is_scanned": (
            ordinary_junction["minimal_pdf_detect_tree_equal"] is True
        ),
        "finite_two_junction_chain_is_scanned": (
            reports["directory_junction_chain"][
                "minimal_pdf_detect_tree_equal"
            ]
            is True
        ),
        "enumerated_tree_prefix_ids": tree_case["first_prefix_ids"],
        "enumerated_tree_is_single_valid_json": (
            tree_case["first_valid_json"]
        ),
        "extended_file_matches_ordinary_raw_stdout": (
            extended_file["first"]["stdout_sha256"]
            == ordinary_file["first"]["stdout_sha256"]
        ),
        "extended_junction_matches_ordinary_raw_stdout": (
            extended_junction["first"]["stdout_sha256"]
            == ordinary_junction["first"]["stdout_sha256"]
        ),
    }
    report = {
        "schema_version": 1,
        "generator": (
            "tools/upstream/collect_windows_cli_filesystem.py"
        ),
        "generator_sha256": baseline.sha256_file(Path(__file__)),
        "fixture_generator": {
            "path": (
                "tools/corpus/generate_windows_filesystem_fixture.py"
            ),
            "sha256": baseline.sha256_file(FIXTURE_SCRIPT),
        },
        "platform": "windows-x86_64-qt5",
        "source": source_identity,
        "qt": qt_identity,
        "binary": {
            "size": binary.stat().st_size,
            "sha256": binary_sha256,
            "relative_path": "build/release/diec.exe",
        },
        "fixture": {
            "manifest": (
                "docs/research/data/windows-filesystem-fixture.json"
            ),
            "sha256": hashlib.sha256(manifest_raw).hexdigest(),
            "files": manifest["files"],
            "junctions": manifest["junctions"],
            "extended_path_cases": manifest["extended_path_cases"],
            "explicit_gaps": manifest["explicit_gaps"],
        },
        "windows_default_reference": {
            "path": (
                "docs/research/data/baseline-corpus-windows-qt5.json"
            ),
            "sha256": hashlib.sha256(baseline_raw).hexdigest(),
            "sample": "minimal.pdf",
        },
        "cases": reports,
        "findings": findings,
        "summary": {
            "case_count": len(cases),
            "execution_count": 2 * len(cases),
            "determinism_failures": determinism_failures,
            "expected_exit_failures": expected_exit_failures,
            "reference_projection_failures": (
                reference_projection_failures
            ),
            "deterministic": not determinism_failures,
            "expected_exits_equal": not expected_exit_failures,
            "reference_projections_equal": (
                not reference_projection_failures
            ),
        },
        "limitations": [
            (
                "the fixture covers directory junctions and a finite two-hop "
                "junction chain, not privileged symbolic links"
            ),
            (
                "extended namespace cases use normal-length paths; paths over "
                "MAX_PATH remain a separate boundary"
            ),
            (
                "UNC, ACL denial, dangling reparse points, alternate data "
                "streams, and reparse cycles remain explicit gaps"
            ),
            (
                "raw stdout/stderr hashes are unnormalized; no local absolute "
                "path or raw stream bytes are committed"
            ),
        ],
    }
    serialized = (
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(serialized)
    sys.stdout.buffer.write(serialized)
    return (
        0
        if not (
            determinism_failures
            or expected_exit_failures
            or reference_projection_failures
        )
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
