#!/usr/bin/env python3
"""Collect a non-admitted macOS Qt5 CLI long-path candidate."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import os
import platform
from pathlib import Path
import subprocess
import sys
from typing import Any, Sequence


UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
PLATFORM = "macos-x86_64-qt5"
BASELINE_COLLECTOR = "tools/upstream/collect_macos_cli_baseline.py"
BASELINE_VALIDATOR = "tools/upstream/validate_macos_cli_baseline.py"
FIXTURE_GENERATOR = (
    "tools/corpus/generate_macos_long_path_fixture.py"
)
FIXTURE_VALIDATOR = (
    "tools/corpus/validate_macos_long_path_fixture.py"
)
VALIDATOR = "tools/upstream/validate_macos_cli_long_paths.py"
ADMISSION_REASON = (
    "long-path CLI candidate only; macOS runtime evidence has not been "
    "reviewed or projected into the 68-row capability closure"
)
LIMITATIONS = [
    (
        "the matrix covers explicit and short-root discovery at public "
        "PATH_MAX and kernel-private MAXLONGPATHLEN -1/exact/+1"
    ),
    (
        "component cases cover NAME_MAX -1/exact/+1 and preserve create "
        "errno when a target cannot be materialized"
    ),
    (
        "ASCII-only names isolate byte length; Unicode normalization and "
        "multi-byte name limits remain covered by the special-path matrix"
    ),
    (
        "raw streams and fixture reports retain runner-local absolute "
        "paths and remain non-admitted review artifacts"
    ),
]


class LongPathError(ValueError):
    """The long-path CLI candidate cannot be collected safely."""


@dataclass(frozen=True)
class Case:
    name: str
    target: str
    report_target: str
    fixture_case_id: str | None
    mode: str
    reference_projection_applies: bool


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _load(root: Path, relative: str, name: str) -> Any:
    path = root / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise LongPathError(f"cannot load helper module: {relative}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _generator_bindings(root: Path) -> dict[str, str]:
    paths = {
        "path": "tools/upstream/collect_macos_cli_long_paths.py",
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


def database_arguments(source_dir: Path, *, report: bool) -> tuple[str, ...]:
    root = "<source>" if report else str(source_dir)
    return (
        "--database",
        f"{root}/Detect-It-Easy/db",
        "--extradatabase",
        f"{root}/Detect-It-Easy/db_extra",
        "--customdatabase",
        f"{root}/Detect-It-Easy/db_custom",
    )


def build_cases(fixture_report: dict[str, Any]) -> tuple[Case, ...]:
    records = {
        case["id"]: case
        for case in fixture_report["fixture"]["cases"]
    }
    result = [
        Case(
            "control_explicit",
            records["control"]["absolute_path"],
            "<fixture-case:control>",
            "control",
            "explicit",
            True,
        )
    ]
    for case_id in fixture_report["fixture"]["case_ids"]:
        record = records[case_id]
        if record["kind"] != "full_path":
            continue
        result.append(
            Case(
                f"{case_id}_explicit",
                record["absolute_path"],
                f"<fixture-case:{case_id}:absolute>",
                case_id,
                "explicit",
                record["attempt"]["created"],
            )
        )
        first_component = record["relative_path"].split("/", 1)[0]
        discovery = (
            Path(fixture_report["fixture"]["local_path"])
            / first_component
        )
        result.append(
            Case(
                f"{case_id}_discovery",
                str(discovery),
                f"<fixture-case:{case_id}:discovery-root>",
                case_id,
                "discovery",
                record["attempt"]["created"],
            )
        )
    for case_id in fixture_report["fixture"]["case_ids"]:
        record = records[case_id]
        if record["kind"] != "component":
            continue
        result.append(
            Case(
                f"{case_id}_explicit",
                record["absolute_path"],
                f"<fixture-case:{case_id}:absolute>",
                case_id,
                "explicit",
                record["attempt"]["created"],
            )
        )
    result.append(
        Case(
            "component_directory",
            str(
                Path(fixture_report["fixture"]["local_path"])
                / "components"
            ),
            "<fixture>/components",
            None,
            "component_directory",
            False,
        )
    )
    return tuple(result)


def observe(
    common: Any,
    binary: Path,
    qt_dir: Path,
    arguments: Sequence[str],
    *,
    timeout_seconds: int,
) -> tuple[Any, bool]:
    environment = os.environ.copy()
    environment["PATH"] = (
        str(qt_dir / "bin")
        + os.pathsep
        + environment.get("PATH", "")
    )
    try:
        result = subprocess.run(
            [binary.name, *arguments],
            executable=str(binary),
            cwd=binary.parent,
            env=environment,
            check=False,
            capture_output=True,
            timeout=timeout_seconds,
        )
        return (
            common.Observation(
                result.returncode, result.stdout, result.stderr
            ),
            False,
        )
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout or b""
        stderr = error.stderr or b""
        if isinstance(stdout, str):
            stdout = stdout.encode("utf-8", errors="surrogateescape")
        if isinstance(stderr, str):
            stderr = stderr.encode("utf-8", errors="surrogateescape")
        return common.Observation(124, stdout, stderr), True


def valid_json(data: bytes) -> bool:
    try:
        return isinstance(json.loads(data), dict)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False


def prefix_case_ids(
    data: bytes, fixture_report: dict[str, Any]
) -> list[str]:
    positions = []
    for record in fixture_report["fixture"]["cases"]:
        if not record["attempt"]["created"]:
            continue
        prefix = record["absolute_path"].encode("ascii") + b":"
        start = 0
        while True:
            index = data.find(prefix, start)
            if index < 0:
                break
            suffix = data[index + len(prefix) :]
            if suffix.startswith((b"\n", b"\r\n")):
                positions.append((index, record["id"]))
            start = index + len(prefix)
    positions.sort()
    return [case_id for _, case_id in positions]


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
        raise LongPathError("collector requires native Darwin x86_64")
    if not 1 <= timeout_seconds <= 3600:
        raise LongPathError("timeout-seconds must be in 1..3600")
    source_dir = source_dir.resolve(strict=True)
    qt_dir = qt_dir.resolve(strict=True)
    fixture_dir = fixture_dir.resolve(strict=True)
    binary = binary.resolve(strict=True)
    oracle_path = oracle_path.resolve(strict=True)
    baseline_path = baseline_path.resolve(strict=True)
    fixture_report_path = fixture_report_path.resolve(strict=True)
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    for path, name in (
        (oracle_path, "oracle-candidate.json"),
        (baseline_path, "cli-baseline-candidate.json"),
        (
            fixture_report_path,
            "long-path-fixture-candidate.json",
        ),
    ):
        if path != (output.parent / name).resolve(strict=True):
            raise LongPathError(
                f"input report must be bundle-local: {name}"
            )
    if output.exists():
        raise LongPathError("candidate report already exists")
    raw_dir = output.parent / "raw" / "cli-long-path"
    raw_dir.mkdir(parents=True, exist_ok=True)
    if any(raw_dir.iterdir()):
        raise LongPathError("long-path raw directory must be empty")

    baseline_collector = _load(
        root, BASELINE_COLLECTOR, "macos_baseline_for_long_path"
    )
    baseline_validator = _load(
        root,
        BASELINE_VALIDATOR,
        "macos_baseline_validator_for_long_path",
    )
    fixture_validator = _load(
        root,
        FIXTURE_VALIDATOR,
        "macos_long_path_fixture_validator_for_cli",
    )
    common = baseline_collector.load_module(
        "windows_cli_common_for_macos_long_path",
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
    if Path(fixture_report["fixture"]["local_path"]) != fixture_dir:
        raise LongPathError("fixture local path differs")

    oracle, oracle_raw = baseline_collector.validate_oracle_inputs(
        root, oracle_path, source_dir, qt_dir, binary
    )
    expected_binary = (
        source_dir / "build" / "release" / "diec"
    ).resolve(strict=True)
    if binary != expected_binary:
        raise LongPathError(
            "binary must be <source>/build/release/diec"
        )
    source = common.validate_source(source_dir)
    source["tracked_files_clean_before_and_after"] = True
    qt = baseline_collector.validate_qt(common, qt_dir, oracle)
    binary_sha256 = common.sha256_file(binary)
    if binary_sha256 != oracle["artifact"]["sha256"]:
        raise LongPathError("binary differs from oracle report")
    if baseline_report["source"] != source or baseline_report["qt"] != qt:
        raise LongPathError("baseline source/Qt identity differs")
    if baseline_report["binary"]["sha256"] != binary_sha256:
        raise LongPathError("baseline binary identity differs")

    reference_tree = baseline_report["corpus"]["minimal.pdf"][
        "first_detect_tree"
    ]
    actual_db = database_arguments(source_dir, report=False)
    report_db = database_arguments(source_dir, report=True)
    cases = build_cases(fixture_report)
    reports = {}
    determinism_failures = []
    timeout_cases = []
    reference_projection_failures = []
    for case in cases:
        arguments = ("--json", *actual_db, case.target)
        first, first_timeout = observe(
            common,
            binary,
            qt_dir,
            arguments,
            timeout_seconds=timeout_seconds,
        )
        second, second_timeout = observe(
            common,
            binary,
            qt_dir,
            arguments,
            timeout_seconds=timeout_seconds,
        )
        entry = baseline_collector.pair_report(
            common,
            output.parent,
            f"cli-long-path/{case.name}",
            first,
            second,
        )
        first_tree = common.json_detect_tree(first.stdout)
        second_tree = common.json_detect_tree(second.stdout)
        reference_equal = (
            first_tree == reference_tree
            if case.reference_projection_applies
            else None
        )
        entry.update(
            {
                "arguments": [
                    "--json",
                    *report_db,
                    case.report_target,
                ],
                "mode": case.mode,
                "fixture_case_id": case.fixture_case_id,
                "reference_projection_applies": (
                    case.reference_projection_applies
                ),
                "timeout_seconds": timeout_seconds,
                "first_timed_out": first_timeout,
                "second_timed_out": second_timeout,
                "first_valid_json": valid_json(first.stdout),
                "second_valid_json": valid_json(second.stdout),
                "first_detect_tree": first_tree,
                "second_detect_tree": second_tree,
                "minimal_pdf_detect_tree_equal": reference_equal,
                "first_prefix_case_ids": prefix_case_ids(
                    first.stdout, fixture_report
                ),
                "second_prefix_case_ids": prefix_case_ids(
                    second.stdout, fixture_report
                ),
            }
        )
        reports[case.name] = entry
        if entry["determinism_differences"] or (
            first_timeout != second_timeout
        ):
            determinism_failures.append(case.name)
        if first_timeout or second_timeout:
            timeout_cases.append(case.name)
        if (
            case.reference_projection_applies
            and not reference_equal
        ):
            reference_projection_failures.append(case.name)

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
            "path": "long-path-fixture-candidate.json",
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
            "case_names": [case.name for case in cases],
            "minimum_repetitions_per_case": 2,
        },
        "cases": reports,
        "summary": {
            "case_count": case_count,
            "execution_count": 2 * case_count,
            "raw_stream_count": 4 * case_count,
            "determinism_failures": determinism_failures,
            "timeout_cases": timeout_cases,
            "reference_projection_failures": (
                reference_projection_failures
            ),
            "deterministic": not determinism_failures,
            "reference_projections_equal": (
                not reference_projection_failures
            ),
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
    except (LongPathError, OSError, ValueError) as error:
        print(f"macOS CLI long-path error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
