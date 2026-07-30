#!/usr/bin/env python3
"""Collect a non-admitted macOS Qt5 special-path CLI candidate."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
PLATFORM = "macos-x86_64-qt5"
BASELINE_COLLECTOR = "tools/upstream/collect_macos_cli_baseline.py"
BASELINE_VALIDATOR = "tools/upstream/validate_macos_cli_baseline.py"
FIXTURE_GENERATOR = (
    "tools/corpus/generate_macos_special_path_fixture.py"
)
FIXTURE_VALIDATOR = (
    "tools/corpus/validate_macos_special_path_fixture.py"
)
VALIDATOR = "tools/upstream/validate_macos_cli_special_paths.py"
ADMISSION_REASON = (
    "special-path CLI candidate only; macOS runtime evidence has not been "
    "reviewed or projected into the 68-row capability closure"
)
LIMITATIONS = [
    (
        "the candidate scans every logical UTF-8 spelling, including case "
        "and NFC/NFD aliases, plus three directory modes"
    ),
    (
        "invalid UTF-8 basenames are observed through directory scanning "
        "because they cannot be represented faithfully in a Unicode argv"
    ),
    (
        "symlink cycles, permissions, long paths, large directories, and "
        "TOCTOU remain separate path-profile candidates"
    ),
    (
        "raw streams and exact directory token order remain authoritative; "
        "only single-file detect trees use the macOS baseline projection"
    ),
]


class SpecialPathError(ValueError):
    """The special-path CLI candidate cannot be collected safely."""


@dataclass(frozen=True)
class Case:
    name: str
    cwd: Path
    arguments: tuple[str, ...]
    report_cwd: str
    report_arguments: tuple[str, ...]
    expected_exit: int
    reference_projection_applies: bool


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _load(root: Path, relative: str, name: str) -> Any:
    path = root / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SpecialPathError(f"cannot load helper module: {relative}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _generator_bindings(root: Path) -> dict[str, str]:
    paths = {
        "path": "tools/upstream/collect_macos_cli_special_paths.py",
        "validator_path": VALIDATOR,
        "baseline_collector_path": BASELINE_COLLECTOR,
        "baseline_validator_path": BASELINE_VALIDATOR,
        "fixture_generator_path": FIXTURE_GENERATOR,
        "fixture_validator_path": FIXTURE_VALIDATOR,
    }
    result = dict(paths)
    for field, relative in paths.items():
        digest_field = (
            "sha256"
            if field == "path"
            else field.removesuffix("_path") + "_sha256"
        )
        result[digest_field] = sha256((root / relative).read_bytes())
    return result


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


def logical_entries(
    fixture_generator: Any,
) -> tuple[tuple[str, str], ...]:
    return (
        *fixture_generator.STABLE_ENTRIES,
        fixture_generator.CASE_ALIAS[:2],
        fixture_generator.UNICODE_ALIAS[:2],
    )


def build_cases(
    *,
    source_dir: Path,
    fixture_dir: Path,
    binary_dir: Path,
    fixture_generator: Any,
) -> tuple[Case, ...]:
    actual_db = database_arguments(source_dir, report=False)
    report_db = database_arguments(source_dir, report=True)

    def actual_path(relative: str) -> str:
        return str(fixture_dir.joinpath(*relative.split("/")))

    def report_path(relative: str) -> str:
        return f"<fixture>/{relative}"

    cases = [
        Case(
            f"single_{case_id}",
            binary_dir,
            ("--json", *actual_db, actual_path(relative)),
            "<binary-dir>",
            ("--json", *report_db, report_path(relative)),
            0,
            True,
        )
        for case_id, relative in logical_entries(fixture_generator)
    ]
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
                False,
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
                True,
            ),
            Case(
                "directory_nonutf8",
                binary_dir,
                (
                    "--json",
                    *actual_db,
                    str(fixture_dir / "nonutf8"),
                ),
                "<binary-dir>",
                ("--json", *report_db, "<fixture>/nonutf8"),
                0,
                False,
            ),
            Case(
                "explicit_order",
                binary_dir,
                (
                    "--json",
                    *actual_db,
                    actual_path("special/emoji-😀.pdf"),
                    actual_path("special/é-nfc.pdf"),
                    actual_path("special/00-ascii.pdf"),
                ),
                "<binary-dir>",
                (
                    "--json",
                    *report_db,
                    "<fixture>/special/emoji-😀.pdf",
                    "<fixture>/special/é-nfc.pdf",
                    "<fixture>/special/00-ascii.pdf",
                ),
                0,
                False,
            ),
            Case(
                "leading_dash_relative_unescaped",
                fixture_dir / "special",
                ("--json", *actual_db, "--leading-dash.pdf"),
                "<fixture>/special",
                ("--json", *report_db, "--leading-dash.pdf"),
                1,
                False,
            ),
            Case(
                "leading_dash_relative_escaped",
                fixture_dir / "special",
                ("--json", *actual_db, "--", "--leading-dash.pdf"),
                "<fixture>/special",
                ("--json", *report_db, "--", "--leading-dash.pdf"),
                0,
                True,
            ),
        )
    )
    return tuple(cases)


def observe(
    common: Any,
    binary: Path,
    qt_dir: Path,
    arguments: Sequence[str],
    *,
    cwd: Path,
    timeout_seconds: int,
) -> Any:
    environment = os.environ.copy()
    environment["PATH"] = (
        str(qt_dir / "bin")
        + os.pathsep
        + environment.get("PATH", "")
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
    return common.Observation(
        result.returncode, result.stdout, result.stderr
    )


def prefix_tokens(
    data: bytes,
    *,
    fixture_dir: Path,
    fixture_report: dict[str, Any],
) -> list[str]:
    candidates = []
    entries = fixture_report["fixture"]["entries"]
    for entry in entries:
        relative = str(entry["path"])
        parent = relative.rsplit("/", 1)[0]
        parent_bytes = os.fsencode(
            fixture_dir.joinpath(*parent.split("/"))
        )
        name_bytes = bytes.fromhex(
            entry["directory_name_bytes_hex"]
        )
        candidates.append(
            (
                parent_bytes + b"/" + name_bytes,
                str(entry["id"]),
            )
        )
    raw_parent = os.fsencode(fixture_dir / "nonutf8")
    for attempt in fixture_report["fixture"]["raw_attempts"]:
        if attempt["created"]:
            name_hex = attempt["name_bytes_hex"]
            candidates.append(
                (
                    raw_parent + b"/" + bytes.fromhex(name_hex),
                    f"raw:{name_hex}",
                )
            )
    positions = []
    for prefix, token in candidates:
        start = 0
        while True:
            index = data.find(prefix + b":", start)
            if index < 0:
                break
            suffix = data[index + len(prefix) + 1 :]
            if suffix.startswith((b"\n", b"\r\n")):
                positions.append((index, token))
            start = index + len(prefix) + 1
    positions.sort()
    return [token for _, token in positions]


def valid_json(data: bytes) -> bool:
    try:
        json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    return True


def collect(
    *,
    root: Path,
    binary: Path,
    source_dir: Path,
    qt_dir: Path,
    fixture_dir: Path,
    oracle_path: Path,
    baseline_path: Path,
    fixture_report_path: Path,
    output: Path,
    timeout_seconds: int,
) -> dict[str, Any]:
    if sys.platform != "darwin" or platform.machine() != "x86_64":
        raise SpecialPathError("collector requires native Darwin x86_64")
    if not 1 <= timeout_seconds <= 3600:
        raise SpecialPathError("timeout-seconds must be in 1..3600")
    source_dir = source_dir.resolve(strict=True)
    qt_dir = qt_dir.resolve(strict=True)
    fixture_dir = fixture_dir.resolve(strict=True)
    binary = binary.resolve(strict=True)
    oracle_path = oracle_path.resolve(strict=True)
    baseline_path = baseline_path.resolve(strict=True)
    fixture_report_path = fixture_report_path.resolve(strict=True)
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    expected_inputs = {
        oracle_path: "oracle-candidate.json",
        baseline_path: "cli-baseline-candidate.json",
        fixture_report_path: "special-path-fixture-candidate.json",
    }
    for path, name in expected_inputs.items():
        if path != (output.parent / name).resolve(strict=True):
            raise SpecialPathError(
                f"input report must be bundle-local: {name}"
            )
    if output.exists():
        raise SpecialPathError("candidate report already exists")
    raw_dir = output.parent / "raw" / "cli-special-path"
    raw_dir.mkdir(parents=True, exist_ok=True)
    if any(raw_dir.iterdir()):
        raise SpecialPathError("special-path raw directory must be empty")

    baseline_collector = _load(
        root,
        BASELINE_COLLECTOR,
        "macos_cli_baseline_collector_for_special_path",
    )
    baseline_validator = _load(
        root,
        BASELINE_VALIDATOR,
        "macos_cli_baseline_validator_for_special_path",
    )
    fixture_generator = _load(
        root,
        FIXTURE_GENERATOR,
        "macos_special_path_fixture_generator_for_cli",
    )
    fixture_validator = _load(
        root,
        FIXTURE_VALIDATOR,
        "macos_special_path_fixture_validator_for_cli",
    )
    common = baseline_collector.load_module(
        "windows_cli_common_for_macos_special_path",
        root / baseline_collector.SHARED_COLLECTOR,
    )
    baseline_report = baseline_validator.load_json(baseline_path)[0]
    baseline_validator.validate_report(
        baseline_report,
        report_path=baseline_path,
        oracle_path=oracle_path,
        root=root,
    )
    fixture_report = fixture_validator.load_json(
        fixture_report_path
    )[0]
    fixture_validator.validate_report(
        fixture_report,
        report_path=fixture_report_path,
        root=root,
        live_fixture_dir=fixture_dir,
    )
    if Path(fixture_report["fixture"]["local_path"]).resolve(
        strict=True
    ) != fixture_dir:
        raise SpecialPathError("fixture local path differs")

    oracle, oracle_raw = baseline_collector.validate_oracle_inputs(
        root, oracle_path, source_dir, qt_dir, binary
    )
    expected_binary = (
        source_dir / "build" / "release" / "diec"
    ).resolve(strict=True)
    if binary != expected_binary:
        raise SpecialPathError(
            "binary must be <source>/build/release/diec"
        )
    source = common.validate_source(source_dir)
    source["tracked_files_clean_before_and_after"] = True
    qt = baseline_collector.validate_qt(common, qt_dir, oracle)
    binary_sha256 = common.sha256_file(binary)
    if binary_sha256 != oracle["artifact"]["sha256"]:
        raise SpecialPathError("binary differs from oracle report")
    for field, actual in (
        ("source", source),
        ("qt", qt),
    ):
        if baseline_report[field] != actual:
            raise SpecialPathError(
                f"baseline {field} identity differs"
            )
    if baseline_report["binary"]["sha256"] != binary_sha256:
        raise SpecialPathError("baseline binary differs")

    reference_tree = baseline_report["corpus"]["minimal.pdf"][
        "first_detect_tree"
    ]
    cases = build_cases(
        source_dir=source_dir,
        fixture_dir=fixture_dir,
        binary_dir=binary.parent,
        fixture_generator=fixture_generator,
    )
    reports = {}
    determinism_failures = []
    exit_failures = []
    projection_failures = []
    for case in cases:
        first = observe(
            common,
            binary,
            qt_dir,
            case.arguments,
            cwd=case.cwd,
            timeout_seconds=timeout_seconds,
        )
        second = observe(
            common,
            binary,
            qt_dir,
            case.arguments,
            cwd=case.cwd,
            timeout_seconds=timeout_seconds,
        )
        entry = baseline_collector.pair_report(
            common,
            output.parent,
            f"cli-special-path/{case.name}",
            first,
            second,
        )
        first_tree = common.json_detect_tree(first.stdout)
        second_tree = common.json_detect_tree(second.stdout)
        first_valid = valid_json(first.stdout)
        second_valid = valid_json(second.stdout)
        projection_equal = (
            first_tree == reference_tree
            if case.reference_projection_applies
            else None
        )
        entry.update(
            {
                "cwd": case.report_cwd,
                "arguments": list(case.report_arguments),
                "expected_exit_code": case.expected_exit,
                "expected_exit_code_equal": (
                    first.exit_code == case.expected_exit
                ),
                "first_valid_json": first_valid,
                "second_valid_json": second_valid,
                "first_detect_tree": first_tree,
                "second_detect_tree": second_tree,
                "reference_projection_applies": (
                    case.reference_projection_applies
                ),
                "minimal_pdf_detect_tree_equal": projection_equal,
                "first_prefix_tokens": prefix_tokens(
                    first.stdout,
                    fixture_dir=fixture_dir,
                    fixture_report=fixture_report,
                ),
                "second_prefix_tokens": prefix_tokens(
                    second.stdout,
                    fixture_dir=fixture_dir,
                    fixture_report=fixture_report,
                ),
            }
        )
        reports[case.name] = entry
        if entry["determinism_differences"]:
            determinism_failures.append(case.name)
        if first.exit_code != case.expected_exit:
            exit_failures.append(case.name)
        if (
            case.reference_projection_applies
            and first_tree != reference_tree
        ):
            projection_failures.append(case.name)

    findings = {
        "logical_single_case_count": len(
            logical_entries(fixture_generator)
        ),
        "directory_special_sequence": reports[
            "directory_special"
        ]["first_prefix_tokens"],
        "directory_nonutf8_sequence": reports[
            "directory_nonutf8"
        ]["first_prefix_tokens"],
        "explicit_target_sequence": reports["explicit_order"][
            "first_prefix_tokens"
        ],
        "explicit_target_order_is_preserved": (
            reports["explicit_order"]["first_prefix_tokens"]
            == ["emoji", "nfc", "ascii"]
        ),
        "case_alias_same_file": fixture_report[
            "filesystem_observations"
        ]["lowercase_alias_is_same_file"],
        "unicode_alias_same_file": fixture_report[
            "filesystem_observations"
        ]["nfd_alias_is_same_file"],
        "created_raw_name_count": sum(
            attempt["created"]
            for attempt in fixture_report["fixture"]["raw_attempts"]
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
        "result": "candidate",
        "platform": PLATFORM,
        "generator": _generator_bindings(root),
        "oracle_report": {
            "path": "oracle-candidate.json",
            "sha256": sha256(oracle_raw),
        },
        "cli_baseline_report": {
            "path": "cli-baseline-candidate.json",
            "sha256": sha256(baseline_path.read_bytes()),
        },
        "fixture_report": {
            "path": "special-path-fixture-candidate.json",
            "sha256": sha256(fixture_report_path.read_bytes()),
        },
        "source": source,
        "qt": qt,
        "binary": {
            "size": binary.stat().st_size,
            "sha256": binary_sha256,
            "relative_path": "build/release/diec",
        },
        "selection": {
            "logical_entries": [
                {"id": case_id, "path": relative}
                for case_id, relative in logical_entries(
                    fixture_generator
                )
            ],
            "case_names": [case.name for case in cases],
        },
        "cases": reports,
        "findings": findings,
        "summary": {
            "case_count": case_count,
            "execution_count": 2 * case_count,
            "raw_stream_count": 4 * case_count,
            "determinism_failures": determinism_failures,
            "expected_exit_failures": exit_failures,
            "reference_projection_failures": projection_failures,
            "deterministic": not determinism_failures,
            "expected_exits_equal": not exit_failures,
            "reference_projections_equal": not projection_failures,
        },
        "admission": {
            "platform_admitted": False,
            "capability_rows_admitted": 0,
            "reason": ADMISSION_REASON,
        },
        "limitations": LIMITATIONS,
    }
    output.write_bytes(
        (
            json.dumps(
                report,
                ensure_ascii=True,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    )
    return report


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--qt-dir", type=Path, required=True)
    parser.add_argument("--fixture-dir", type=Path, required=True)
    parser.add_argument("--oracle-report", type=Path, required=True)
    parser.add_argument("--cli-baseline-report", type=Path, required=True)
    parser.add_argument("--fixture-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.set_defaults(root=root)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        collect(
            root=args.root.resolve(),
            binary=args.binary,
            source_dir=args.source_dir,
            qt_dir=args.qt_dir,
            fixture_dir=args.fixture_dir,
            oracle_path=args.oracle_report,
            baseline_path=args.cli_baseline_report,
            fixture_report_path=args.fixture_report,
            output=args.output,
            timeout_seconds=args.timeout_seconds,
        )
    except (SpecialPathError, OSError, ValueError) as error:
        print(
            f"macOS CLI special-path error: {error}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
