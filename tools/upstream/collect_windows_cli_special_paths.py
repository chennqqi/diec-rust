#!/usr/bin/env python3
"""Collect deterministic native-Windows Qt5 special-path behavior."""

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
    ROOT / "tools/corpus/generate_windows_special_path_fixture.py"
)
LINUX_COMMON_DIRECTORY_ORDER = (
    "leading_space",
    "leading_dash",
    "ascii",
    "upper_case",
    "emoji",
    "nfd",
    "space",
    "nfc",
    "cjk",
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
    "collect_windows_cli_baseline_special_path_helper",
    BASELINE_SCRIPT,
)
fixture_generator = load_module(
    "generate_windows_special_path_fixture_helper",
    FIXTURE_SCRIPT,
)
ProbeError = baseline.BaselineError


@dataclass(frozen=True)
class Case:
    name: str
    cwd: Path
    arguments: tuple[str, ...]
    report_cwd: str
    report_arguments: tuple[str, ...]
    expected_exit: int


def observe(
    binary: Path,
    qt_dir: Path,
    arguments: Sequence[str],
    *,
    cwd: Path,
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
        cwd=cwd,
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


def prefix_ids(
    data: bytes,
    fixture_dir: Path,
    entries: Sequence[dict[str, object]],
) -> list[str]:
    positions = []
    for entry in entries:
        relative = str(entry["path"])
        path = fixture_dir.joinpath(*relative.split("/"))
        prefix = str(path).encode("utf-8") + b":\r\n"
        start = 0
        while True:
            index = data.find(prefix, start)
            if index < 0:
                break
            positions.append((index, str(entry["id"])))
            start = index + len(prefix)
    positions.sort()
    return [case_id for _, case_id in positions]


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
    source_dir: Path,
    fixture_dir: Path,
    entries: Sequence[dict[str, object]],
    binary_dir: Path,
) -> tuple[Case, ...]:
    actual_db = database_arguments(source_dir, report=False)
    report_db = database_arguments(source_dir, report=True)
    by_id = {str(entry["id"]): entry for entry in entries}

    def actual_path(case_id: str) -> str:
        relative = str(by_id[case_id]["path"])
        return str(fixture_dir.joinpath(*relative.split("/")))

    def report_path(case_id: str) -> str:
        return "<fixture>/" + str(by_id[case_id]["path"])

    cases = []
    for entry in entries:
        case_id = str(entry["id"])
        cases.append(
            Case(
                f"single_{case_id}",
                binary_dir,
                ("--json", *actual_db, actual_path(case_id)),
                "<binary-dir>",
                ("--json", *report_db, report_path(case_id)),
                0,
            )
        )

    cases.extend(
        (
            Case(
                "directory_special",
                binary_dir,
                (
                    "--json",
                    *actual_db,
                    str(fixture_dir / "special"),
                ),
                "<binary-dir>",
                ("--json", *report_db, "<fixture>/special"),
                0,
            ),
            Case(
                "directory_unicode",
                binary_dir,
                (
                    "--json",
                    *actual_db,
                    str(fixture_dir / "目录 空格"),
                ),
                "<binary-dir>",
                ("--json", *report_db, "<fixture>/目录 空格"),
                0,
            ),
            Case(
                "explicit_order",
                binary_dir,
                (
                    "--json",
                    *actual_db,
                    actual_path("emoji"),
                    actual_path("nfc"),
                    actual_path("ascii"),
                ),
                "<binary-dir>",
                (
                    "--json",
                    *report_db,
                    report_path("emoji"),
                    report_path("nfc"),
                    report_path("ascii"),
                ),
                0,
            ),
            Case(
                "leading_dash_relative_unescaped",
                fixture_dir / "special",
                ("--json", *actual_db, "--leading-dash.pdf"),
                "<fixture>/special",
                ("--json", *report_db, "--leading-dash.pdf"),
                1,
            ),
            Case(
                "leading_dash_relative_escaped",
                fixture_dir / "special",
                ("--json", *actual_db, "--", "--leading-dash.pdf"),
                "<fixture>/special",
                ("--json", *report_db, "--", "--leading-dash.pdf"),
                0,
            ),
        )
    )
    return tuple(cases)


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
        / "docs/research/data/windows-special-path-fixture.json",
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
        raise ProbeError("special-path fixture manifest differs")
    manifest = json.loads(manifest_raw)
    fixture_generator.validate_fixture(fixture_dir, manifest)
    entries = manifest["entries"]

    baseline_path = args.windows_baseline.resolve(strict=True)
    baseline_report_raw = baseline_path.read_bytes()
    baseline_report = json.loads(baseline_report_raw)
    reference_tree = baseline_report["corpus"]["minimal.pdf"][
        "first_detect_tree"
    ]
    if baseline_report["binary"]["sha256"] != binary_sha256:
        raise ProbeError("Windows baseline binary identity differs")

    cases = build_cases(
        source_dir,
        fixture_dir,
        entries,
        binary.parent,
    )
    reports = {}
    determinism_failures = []
    expected_exit_failures = []
    reference_projection_failures = []
    for case in cases:
        first = observe(
            binary,
            qt_dir,
            case.arguments,
            cwd=case.cwd,
            timeout_seconds=args.timeout_seconds,
        )
        second = observe(
            binary,
            qt_dir,
            case.arguments,
            cwd=case.cwd,
            timeout_seconds=args.timeout_seconds,
        )
        paired = baseline.pair_report(first, second)
        first_valid_json = False
        second_valid_json = False
        try:
            json.loads(first.stdout)
            first_valid_json = True
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
        try:
            json.loads(second.stdout)
            second_valid_json = True
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
        first_tree = baseline.json_detect_tree(first.stdout)
        second_tree = baseline.json_detect_tree(second.stdout)
        projections_apply = (
            first_valid_json
            and case.name not in {"directory_special", "explicit_order"}
        )
        paired.update(
            {
                "cwd": case.report_cwd,
                "arguments": list(case.report_arguments),
                "expected_exit_code": case.expected_exit,
                "expected_exit_code_equal": (
                    first.exit_code == case.expected_exit
                ),
                "first_valid_json": first_valid_json,
                "second_valid_json": second_valid_json,
                "first_detect_tree": first_tree,
                "second_detect_tree": second_tree,
                "reference_projection_applies": projections_apply,
                "minimal_pdf_detect_tree_equal": (
                    first_tree == reference_tree
                    if projections_apply
                    else None
                ),
                "first_prefix_ids": prefix_ids(
                    first.stdout,
                    fixture_dir,
                    entries,
                ),
                "second_prefix_ids": prefix_ids(
                    second.stdout,
                    fixture_dir,
                    entries,
                ),
            }
        )
        reports[case.name] = paired
        if paired["determinism_differences"]:
            determinism_failures.append(case.name)
        if first.exit_code != case.expected_exit:
            expected_exit_failures.append(case.name)
        if projections_apply and first_tree != reference_tree:
            reference_projection_failures.append(case.name)

    directory_sequence = reports["directory_special"]["first_prefix_ids"]
    explicit_sequence = reports["explicit_order"]["first_prefix_ids"]
    expected_explicit_sequence = ["emoji", "nfc", "ascii"]
    windows_common_projection = [
        case_id
        for case_id in directory_sequence
        if case_id in LINUX_COMMON_DIRECTORY_ORDER
    ]
    findings = {
        "directory_sequence": directory_sequence,
        "directory_entry_count": len(directory_sequence),
        "linux_common_directory_order": list(
            LINUX_COMMON_DIRECTORY_ORDER
        ),
        "windows_common_directory_projection": (
            windows_common_projection
        ),
        "common_directory_order_matches_linux_qt5": (
            windows_common_projection
            == list(LINUX_COMMON_DIRECTORY_ORDER)
        ),
        "dot_file_is_enumerated": "dot_hidden" in directory_sequence,
        "hidden_attribute_file_is_excluded": (
            "attribute_hidden" not in directory_sequence
        ),
        "nfc_nfd_are_distinct_and_enumerated": (
            "nfc" in directory_sequence and "nfd" in directory_sequence
        ),
        "explicit_target_order_is_preserved": (
            explicit_sequence == expected_explicit_sequence
        ),
        "leading_dash_requires_option_terminator_when_relative": (
            reports["leading_dash_relative_unescaped"]["first"][
                "exit_code"
            ]
            == 1
            and reports["leading_dash_relative_escaped"]["first"][
                "exit_code"
            ]
            == 0
        ),
    }
    case_count = len(cases)
    report = {
        "schema_version": 1,
        "generator": (
            "tools/upstream/collect_windows_cli_special_paths.py"
        ),
        "generator_sha256": baseline.sha256_file(Path(__file__)),
        "fixture_generator": {
            "path": (
                "tools/corpus/"
                "generate_windows_special_path_fixture.py"
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
                "docs/research/data/windows-special-path-fixture.json"
            ),
            "sha256": hashlib.sha256(manifest_raw).hexdigest(),
            "directories": manifest["directories"],
            "entries": entries,
            "filesystem_observations": (
                manifest["filesystem_observations"]
            ),
            "unrepresentable_linux_controls": (
                manifest["unrepresentable_linux_controls"]
            ),
        },
        "windows_default_reference": {
            "path": (
                "docs/research/data/"
                "baseline-corpus-windows-qt5.json"
            ),
            "sha256": hashlib.sha256(
                baseline_report_raw
            ).hexdigest(),
            "sample": "minimal.pdf",
        },
        "cases": reports,
        "findings": findings,
        "summary": {
            "case_count": case_count,
            "execution_count": 2 * case_count,
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
                "the default case-insensitive Windows fixture cannot represent "
                "all Linux basename controls; each omitted class is explicit "
                "in the fixture manifest"
            ),
            (
                "this probe does not cover UNC/extended-length paths, junctions, "
                "reparse cycles, ACL denial, or alternate data streams"
            ),
            (
                "raw stdout/stderr hashes remain unnormalized platform "
                "observations; prefix parsing only identifies exact known "
                "fixture paths"
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
