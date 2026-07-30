#!/usr/bin/env python3
"""Collect a non-admitted macOS Qt5 large-directory CLI candidate."""

from __future__ import annotations

import argparse
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
FIXTURE_GENERATOR = "tools/corpus/generate_large_path_fixture.py"
FIXTURE_MATERIALIZER = (
    "tools/corpus/materialize_large_path_fixture.py"
)
FIXTURE_MANIFEST = "docs/research/data/large-path-fixture.json"
LINUX_REFERENCE = "docs/research/data/large-path-engine-qt5.json"
VALIDATOR = "tools/upstream/validate_macos_cli_large_directory.py"
ADMISSION_REASON = (
    "large-directory CLI candidate only; macOS runtime evidence has not "
    "been reviewed or projected into the 68-row capability closure"
)
LIMITATIONS = [
    (
        "the fixture covers 0, 1, 256, flat 4096, and 16-by-256 nested "
        "4096 empty files; it does not establish an unlimited entry count"
    ),
    (
        "creation order is descending and observed output is compared "
        "with the complete ascending name-order projection"
    ),
    (
        "the release CLI still has no externally reachable cooperative "
        "cancellation channel during target expansion; each run is "
        "bounded by an external timeout"
    ),
    (
        "this is an entry-count and ordering fixture, not a long-path, "
        "large-payload, performance, TOCTOU, or memory-limit result"
    ),
]


class LargeDirectoryError(ValueError):
    """The large-directory candidate cannot be collected safely."""


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sequence_sha256(values: list[str]) -> str:
    raw = ("\n".join(values) + ("\n" if values else "")).encode()
    return sha256(raw)


def _load(root: Path, relative: str, name: str) -> Any:
    path = root / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise LargeDirectoryError(
            f"cannot load helper module: {relative}"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _generator_bindings(root: Path) -> dict[str, str]:
    paths = {
        "path": (
            "tools/upstream/collect_macos_cli_large_directory.py"
        ),
        "validator_path": VALIDATOR,
        "baseline_collector_path": BASELINE_COLLECTOR,
        "baseline_validator_path": BASELINE_VALIDATOR,
        "fixture_generator_path": FIXTURE_GENERATOR,
        "fixture_materializer_path": FIXTURE_MATERIALIZER,
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


def prefix_relatives(data: bytes, case_dir: Path) -> list[str]:
    root = os.fsencode(str(case_dir))
    result = []
    for line in data.replace(b"\r\n", b"\n").splitlines():
        if line.startswith(root + b"/") and line.endswith(b".empty:"):
            relative = line[len(root) + 1 : -1]
            result.append(os.fsdecode(relative).replace(os.sep, "/"))
    return result


def entropy_document_count(data: bytes) -> int:
    return data.count(b'"total": 0')


def expected_prefixes(
    materializer: Any, case: dict[str, Any]
) -> list[str]:
    if case["file_count"] <= 1:
        return []
    return list(materializer.relative_files(case))


def linux_projection(
    linux_reference: dict[str, Any], case_name: str
) -> dict[str, Any]:
    case = linux_reference["cases"][case_name]
    return {
        "exit_code": case["observations"]["cmake"]["exit_code"],
        "entropy_document_count": case["entropy_document_count"],
        "prefix_count": case["prefix_count"],
    }


def collect(
    *,
    root: Path,
    binary: Path,
    source_dir: Path,
    qt_dir: Path,
    fixture_dir: Path,
    oracle_path: Path,
    baseline_path: Path,
    output: Path,
    timeout_seconds: int,
) -> dict[str, Any]:
    if sys.platform != "darwin" or platform.machine() != "x86_64":
        raise LargeDirectoryError(
            "collector requires native Darwin x86_64"
        )
    if not 1 <= timeout_seconds <= 60:
        raise LargeDirectoryError(
            "timeout-seconds must be in 1..60"
        )
    source_dir = source_dir.resolve(strict=True)
    qt_dir = qt_dir.resolve(strict=True)
    fixture_dir = fixture_dir.resolve(strict=True)
    binary = binary.resolve(strict=True)
    oracle_path = oracle_path.resolve(strict=True)
    baseline_path = baseline_path.resolve(strict=True)
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    for path, name in (
        (oracle_path, "oracle-candidate.json"),
        (baseline_path, "cli-baseline-candidate.json"),
    ):
        if path != (output.parent / name).resolve(strict=True):
            raise LargeDirectoryError(
                f"input report must be bundle-local: {name}"
            )
    if output.exists():
        raise LargeDirectoryError("candidate report already exists")
    raw_dir = output.parent / "raw" / "cli-large-directory"
    raw_dir.mkdir(parents=True, exist_ok=True)
    if any(raw_dir.iterdir()):
        raise LargeDirectoryError(
            "large-directory raw directory must be empty"
        )

    baseline_collector = _load(
        root, BASELINE_COLLECTOR, "macos_baseline_for_large_directory"
    )
    baseline_validator = _load(
        root,
        BASELINE_VALIDATOR,
        "macos_baseline_validator_for_large_directory",
    )
    materializer = _load(
        root,
        FIXTURE_MATERIALIZER,
        "large_path_materializer_for_macos_cli",
    )
    common = baseline_collector.load_module(
        "windows_cli_common_for_macos_large_directory",
        root / baseline_collector.SHARED_COLLECTOR,
    )
    baseline_report = baseline_validator.load_json(baseline_path)[0]
    baseline_validator.validate_report(
        baseline_report,
        report_path=baseline_path,
        oracle_path=oracle_path,
        root=root,
    )
    oracle, oracle_raw = baseline_collector.validate_oracle_inputs(
        root, oracle_path, source_dir, qt_dir, binary
    )
    expected_binary = (
        source_dir / "build" / "release" / "diec"
    ).resolve(strict=True)
    if binary != expected_binary:
        raise LargeDirectoryError(
            "binary must be <source>/build/release/diec"
        )
    source = common.validate_source(source_dir)
    source["tracked_files_clean_before_and_after"] = True
    qt = baseline_collector.validate_qt(common, qt_dir, oracle)
    binary_sha256 = common.sha256_file(binary)
    if binary_sha256 != oracle["artifact"]["sha256"]:
        raise LargeDirectoryError("binary differs from oracle report")
    if baseline_report["source"] != source or baseline_report["qt"] != qt:
        raise LargeDirectoryError(
            "baseline source/Qt identity differs"
        )
    if baseline_report["binary"]["sha256"] != binary_sha256:
        raise LargeDirectoryError("baseline binary identity differs")

    manifest_path = root / FIXTURE_MANIFEST
    manifest, manifest_raw = materializer.load_manifest(
        root, manifest_path
    )
    live_preflight = materializer.validate_materialized(
        manifest, fixture_dir
    )
    linux_raw = (root / LINUX_REFERENCE).read_bytes()
    linux_reference = json.loads(linux_raw)
    actual_db = database_arguments(source_dir, report=False)
    report_db = database_arguments(source_dir, report=True)

    reports = {}
    determinism_failures = []
    timeout_cases = []
    linux_semantic_failures = []
    name_order_failures = []
    for case in manifest["cases"]:
        name = case["name"]
        case_dir = fixture_dir / name
        arguments = ("--entropy", "--json", *actual_db, str(case_dir))
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
            f"cli-large-directory/{name}",
            first,
            second,
        )
        first_prefixes = prefix_relatives(first.stdout, case_dir)
        second_prefixes = prefix_relatives(second.stdout, case_dir)
        expected = expected_prefixes(materializer, case)
        first_documents = entropy_document_count(first.stdout)
        second_documents = entropy_document_count(second.stdout)
        projection = linux_projection(linux_reference, name)
        linux_equal = (
            first.exit_code == projection["exit_code"]
            and first.stderr == b""
            and first_documents
            == projection["entropy_document_count"]
            and len(first_prefixes) == projection["prefix_count"]
        )
        name_order_equal = first_prefixes == expected
        entry.update(
            {
                "arguments": [
                    "--entropy",
                    "--json",
                    *report_db,
                    f"<fixture>/{name}",
                ],
                "timeout_seconds": timeout_seconds,
                "first_timed_out": first_timeout,
                "second_timed_out": second_timeout,
                "first_entropy_document_count": first_documents,
                "second_entropy_document_count": second_documents,
                "first_prefix_count": len(first_prefixes),
                "second_prefix_count": len(second_prefixes),
                "first_prefix": (
                    first_prefixes[0] if first_prefixes else None
                ),
                "last_prefix": (
                    first_prefixes[-1] if first_prefixes else None
                ),
                "first_prefixes_sha256": sequence_sha256(
                    first_prefixes
                ),
                "second_prefixes_sha256": sequence_sha256(
                    second_prefixes
                ),
                "expected_name_order_sha256": sequence_sha256(
                    expected
                ),
                "complete_name_order_equal": name_order_equal,
                "linux_qt5_projection": projection,
                "linux_qt5_semantic_equal": linux_equal,
            }
        )
        reports[name] = entry
        if entry["determinism_differences"] or (
            first_timeout != second_timeout
        ):
            determinism_failures.append(name)
        if first_timeout or second_timeout:
            timeout_cases.append(name)
        if not linux_equal:
            linux_semantic_failures.append(name)
        if not name_order_equal:
            name_order_failures.append(name)

    case_count = len(manifest["cases"])
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
        "source": source,
        "qt": qt,
        "binary": {
            "size": binary.stat().st_size,
            "sha256": binary_sha256,
            "relative_path": "build/release/diec",
        },
        "fixture": {
            "manifest": FIXTURE_MANIFEST,
            "manifest_sha256": sha256(manifest_raw),
            "materializer": FIXTURE_MATERIALIZER,
            "case_count": case_count,
            "planned_file_count": sum(
                case["file_count"] for case in manifest["cases"]
            ),
            "live_preflight": live_preflight,
        },
        "linux_qt5_reference": {
            "path": LINUX_REFERENCE,
            "sha256": sha256(linux_raw),
        },
        "local_paths": {"fixture_dir": str(fixture_dir)},
        "selection": {
            "case_names": [
                case["name"] for case in manifest["cases"]
            ],
            "minimum_repetitions_per_case": 2,
        },
        "cases": reports,
        "summary": {
            "case_count": case_count,
            "execution_count": 2 * case_count,
            "raw_stream_count": 4 * case_count,
            "determinism_failures": determinism_failures,
            "timeout_cases": timeout_cases,
            "linux_semantic_failures": linux_semantic_failures,
            "name_order_failures": name_order_failures,
            "deterministic": not determinism_failures,
            "linux_semantics_equal": not linux_semantic_failures,
            "complete_name_order_equal": not name_order_failures,
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
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=60)
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
            output=args.output,
            timeout_seconds=args.timeout_seconds,
        )
    except (LargeDirectoryError, OSError, ValueError) as error:
        print(
            f"macOS CLI large-directory error: {error}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
