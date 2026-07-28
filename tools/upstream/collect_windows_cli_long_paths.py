#!/usr/bin/env python3
"""Collect deterministic native-Windows Qt5 paths over MAX_PATH."""

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
    ROOT / "tools/corpus/generate_windows_long_path_fixture.py"
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
    "collect_windows_cli_baseline_long_path_helper",
    BASELINE_SCRIPT,
)
fixture_generator = load_module(
    "generate_windows_long_path_fixture_helper",
    FIXTURE_SCRIPT,
)
ProbeError = baseline.BaselineError


@dataclass(frozen=True)
class Case:
    name: str
    target: str
    report_target: str
    expected_exit: int = 0


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


def build_cases(
    fixture_dir: Path,
    files: Sequence[dict[str, object]],
) -> tuple[Case, ...]:
    by_id = {str(entry["id"]): entry for entry in files}

    def path(case_id: str) -> Path:
        relative = str(by_id[case_id]["path"])
        return fixture_dir.joinpath(*relative.split("/"))

    explicit = path("explicit")
    discovery = path("discovery")
    return (
        Case(
            "control_file",
            str(path("control")),
            "<fixture>/control/target.pdf",
        ),
        Case(
            "long_file_ordinary",
            str(explicit),
            "<fixture>/<long-explicit-file>",
        ),
        Case(
            "long_file_extended",
            fixture_generator.extended_path(explicit),
            "<extended-fixture>/<long-explicit-file>",
        ),
        Case(
            "long_directory_ordinary",
            str(explicit.parent),
            "<fixture>/<long-explicit-directory>",
        ),
        Case(
            "long_directory_extended",
            fixture_generator.extended_path(explicit.parent),
            "<extended-fixture>/<long-explicit-directory>",
        ),
        Case(
            "short_discovery_root",
            str(fixture_dir / "discovery-root"),
            "<fixture>/discovery-root",
        ),
        Case(
            "extended_discovery_root",
            fixture_generator.extended_path(
                discovery.parents[len(fixture_generator.SEGMENTS)]
            ),
            "<extended-fixture>/discovery-root",
        ),
    )


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
        / "docs/research/data/windows-long-path-fixture.json",
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
        raise ProbeError("Windows long-path fixture manifest differs")
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

    actual_db = database_arguments(source_dir, report=False)
    report_db = database_arguments(source_dir, report=True)
    cases = build_cases(fixture_dir, manifest["files"])
    reports = {}
    determinism_failures = []
    expected_exit_failures = []
    json_failures = []
    reference_projection_failures = []
    for case in cases:
        arguments = ("--json", *actual_db, case.target)
        first = observe(
            binary,
            qt_dir,
            arguments,
            timeout_seconds=args.timeout_seconds,
        )
        second = observe(
            binary,
            qt_dir,
            arguments,
            timeout_seconds=args.timeout_seconds,
        )
        paired = baseline.pair_report(first, second)
        first_tree = baseline.json_detect_tree(first.stdout)
        second_tree = baseline.json_detect_tree(second.stdout)
        first_valid_json = first_tree is not None
        second_valid_json = second_tree is not None
        paired.update(
            {
                "cwd": "<binary-dir>",
                "arguments": [
                    "--json",
                    *report_db,
                    case.report_target,
                ],
                "expected_exit_code": case.expected_exit,
                "expected_exit_code_equal": (
                    first.exit_code == case.expected_exit
                ),
                "first_valid_json": first_valid_json,
                "second_valid_json": second_valid_json,
                "first_detect_tree": first_tree,
                "second_detect_tree": second_tree,
                "minimal_pdf_detect_tree_equal": (
                    first_tree == reference_tree
                ),
            }
        )
        reports[case.name] = paired
        if paired["determinism_differences"]:
            determinism_failures.append(case.name)
        if first.exit_code != case.expected_exit:
            expected_exit_failures.append(case.name)
        if not first_valid_json or not second_valid_json:
            json_failures.append(case.name)
        if first_tree != reference_tree:
            reference_projection_failures.append(case.name)

    control_hash = reports["control_file"]["first"]["stdout_sha256"]
    findings = {
        "ordinary_long_file_is_scanned": (
            reports["long_file_ordinary"][
                "minimal_pdf_detect_tree_equal"
            ]
        ),
        "extended_long_file_is_scanned": (
            reports["long_file_extended"][
                "minimal_pdf_detect_tree_equal"
            ]
        ),
        "ordinary_long_directory_is_scanned": (
            reports["long_directory_ordinary"][
                "minimal_pdf_detect_tree_equal"
            ]
        ),
        "extended_long_directory_is_scanned": (
            reports["long_directory_extended"][
                "minimal_pdf_detect_tree_equal"
            ]
        ),
        "short_root_discovers_long_leaf": (
            reports["short_discovery_root"][
                "minimal_pdf_detect_tree_equal"
            ]
        ),
        "extended_short_root_discovers_long_leaf": (
            reports["extended_discovery_root"][
                "minimal_pdf_detect_tree_equal"
            ]
        ),
        "all_stdout_byte_equal_to_control": all(
            record["first"]["stdout_sha256"] == control_hash
            for record in reports.values()
        ),
    }
    report = {
        "schema_version": 1,
        "generator": (
            "tools/upstream/collect_windows_cli_long_paths.py"
        ),
        "generator_sha256": baseline.sha256_file(Path(__file__)),
        "fixture_generator": {
            "path": (
                "tools/corpus/generate_windows_long_path_fixture.py"
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
                "docs/research/data/windows-long-path-fixture.json"
            ),
            "sha256": hashlib.sha256(manifest_raw).hexdigest(),
            "max_path_reference": manifest["max_path_reference"],
            "files": manifest["files"],
            "guarantee": manifest["guarantee"],
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
            "json_failures": json_failures,
            "reference_projection_failures": (
                reference_projection_failures
            ),
            "deterministic": not determinism_failures,
            "expected_exits_equal": not expected_exit_failures,
            "all_json_valid": not json_failures,
            "reference_projections_equal": (
                not reference_projection_failures
            ),
        },
        "limitations": [
            (
                "the fixed paths are 324 and 325 relative UTF-16 code units; "
                "the exact Win32 and NT namespace maxima remain unprobed"
            ),
            (
                "the ASCII-only components isolate length from Unicode "
                "normalization and surrogate-pair counting"
            ),
            (
                "UNC, ACL denial, symbolic links, dangling/cyclic reparse "
                "points, and alternate data streams remain separate gaps"
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
            or json_failures
            or reference_projection_failures
        )
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
