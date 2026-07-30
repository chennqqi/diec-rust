#!/usr/bin/env python3
"""Collect a non-admitted macOS Qt5 CLI filesystem-path candidate."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import os
import platform
from pathlib import Path
import stat
import subprocess
import sys
from typing import Any, Sequence


UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
PLATFORM = "macos-x86_64-qt5"
BASELINE_COLLECTOR = "tools/upstream/collect_macos_cli_baseline.py"
BASELINE_VALIDATOR = "tools/upstream/validate_macos_cli_baseline.py"
FIXTURE_GENERATOR = "tools/corpus/generate_path_filesystem_fixture.py"
FIXTURE_MANIFEST = "docs/research/data/path-filesystem-fixture.json"
LINUX_REFERENCE = (
    "docs/research/data/path-filesystem-engine-qt5.json"
)
VALIDATOR = "tools/upstream/validate_macos_cli_filesystem.py"
ADMISSION_REASON = (
    "filesystem-path CLI candidate only; macOS runtime evidence has not "
    "been reviewed or projected into the 68-row capability closure"
)
LIMITATIONS = [
    (
        "the deterministic fixture covers file and directory symbolic "
        "links, a dangling link, a self-cycle, a mode-000 directory, and "
        "a 64-component directory chain"
    ),
    (
        "permission behavior is observed as the non-root GitHub runner "
        "user; root, ACL, sandbox, SIP, network-volume, and ownership "
        "variants remain open"
    ),
    (
        "self-cycle execution is bounded to ten seconds; a timeout and "
        "its partial raw streams are retained as observations"
    ),
    (
        "Linux comparison uses named exit/count/detection projections; "
        "absolute paths and raw streams are intentionally not normalized"
    ),
]


class FilesystemError(ValueError):
    """The filesystem-path candidate cannot be collected safely."""


@dataclass(frozen=True)
class Case:
    name: str
    relative: str
    linux_case: str
    reference_tree_applies: bool
    timeout_cap_seconds: int | None = None


CASES = (
    Case("direct_control", "paths/symlink/target.pdf", "direct_control", True),
    Case("file_symlink", "paths/symlink/file-link.pdf", "file_symlink", True),
    Case(
        "directory_symlink",
        "paths/symlink/dir-link",
        "directory_symlink",
        True,
    ),
    Case("symlink_tree", "paths/symlink", "symlink_tree", False),
    Case(
        "dangling_symlink",
        "paths/symlink/dangling.pdf",
        "dangling_symlink",
        False,
    ),
    Case("deep_64", "paths/deep", "deep_64", True),
    Case(
        "denied_as_runner",
        "paths/denied",
        "denied_as_nobody",
        False,
    ),
    Case(
        "self_cycle",
        "paths/cycle",
        "self_cycle",
        False,
        10,
    ),
)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _load(root: Path, relative: str, name: str) -> Any:
    path = root / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise FilesystemError(f"cannot load helper module: {relative}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _generator_bindings(root: Path) -> dict[str, str]:
    paths = {
        "path": "tools/upstream/collect_macos_cli_filesystem.py",
        "validator_path": VALIDATOR,
        "baseline_collector_path": BASELINE_COLLECTOR,
        "baseline_validator_path": BASELINE_VALIDATOR,
        "fixture_generator_path": FIXTURE_GENERATOR,
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


def validate_fixture(
    root: Path, fixture_dir: Path
) -> tuple[dict[str, Any], bytes, dict[str, Any]]:
    committed_raw = (root / FIXTURE_MANIFEST).read_bytes()
    generated_raw = (fixture_dir / "manifest.json").read_bytes()
    if generated_raw != committed_raw:
        raise FilesystemError("generated filesystem manifest differs")
    manifest = json.loads(committed_raw)
    archive_record = manifest["archive"]
    archive = fixture_dir / archive_record["name"]
    archive_raw = archive.read_bytes()
    if (
        len(archive_raw) != archive_record["size"]
        or sha256(archive_raw) != archive_record["sha256"]
    ):
        raise FilesystemError("filesystem fixture archive identity differs")

    paths = fixture_dir / "paths"
    links = {
        "file_link": paths / "symlink" / "file-link.pdf",
        "directory_link": paths / "symlink" / "dir-link",
        "dangling_link": paths / "symlink" / "dangling.pdf",
        "cycle_link": paths / "cycle" / "loop",
    }
    expected_targets = {
        "file_link": "target.pdf",
        "directory_link": "dir-target",
        "dangling_link": "missing.pdf",
        "cycle_link": ".",
    }
    actual_targets = {}
    for name, path in links.items():
        if not path.is_symlink():
            raise FilesystemError(f"fixture symlink missing: {name}")
        actual_targets[name] = os.readlink(path)
    if actual_targets != expected_targets:
        raise FilesystemError("fixture symlink targets differ")

    denied = paths / "denied"
    denied_mode = stat.S_IMODE(os.lstat(denied).st_mode)
    if denied_mode != 0:
        raise FilesystemError("denied fixture mode differs")
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        raise FilesystemError("filesystem collector must run as non-root")
    denied_accessible = os.access(denied, os.R_OK | os.X_OK)
    if denied_accessible:
        raise FilesystemError("mode-000 fixture is accessible to runner")

    leaves = list((paths / "deep").rglob("leaf.pdf"))
    if len(leaves) != 1:
        raise FilesystemError("deep fixture leaf inventory differs")
    leaf = leaves[0]
    deep_count = sum(part.startswith("level-") for part in leaf.parts)
    if deep_count != 64:
        raise FilesystemError("deep fixture component count differs")
    payload = manifest["payload"]
    for path in (
        paths / "symlink" / "target.pdf",
        paths / "symlink" / "dir-target" / "child.pdf",
        paths / "cycle" / "root.pdf",
        leaf,
    ):
        raw = path.read_bytes()
        if len(raw) != payload["size"] or sha256(raw) != payload["sha256"]:
            raise FilesystemError(f"fixture payload differs: {path}")
    live = {
        "effective_uid": os.geteuid(),
        "effective_gid": os.getegid(),
        "denied_mode": denied_mode,
        "denied_read_execute_access": denied_accessible,
        "deep_component_count": deep_count,
        "symlink_targets": actual_targets,
    }
    return manifest, committed_raw, live


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


def stdout_summary(data: bytes) -> dict[str, int]:
    return {
        "cannot_find_count": data.count(b"Cannot find:"),
        "filename_prefix_count": (
            data.count(b".pdf:\n") + data.count(b".pdf:\r\n")
        ),
        "pdf_root_count": (
            data.count(b'"filetype":"PDF"')
            + data.count(b'"filetype": "PDF"')
        ),
    }


def prefix_paths(data: bytes, fixture_dir: Path) -> list[str]:
    root = os.fsencode(str(fixture_dir))
    result = []
    for line in data.replace(b"\r\n", b"\n").splitlines():
        if line.startswith(root + b"/") and line.endswith(b".pdf:"):
            relative = line[len(root) + 1 : -1]
            result.append(
                "<fixture>/"
                + os.fsdecode(relative).replace(os.sep, "/")
            )
    return result


def _linux_projection(
    linux_reference: dict[str, Any], linux_case: str
) -> dict[str, Any]:
    case = linux_reference["cases"][linux_case]
    observation = case["observations"]["cmake"]
    return {
        "exit_code": observation["exit_code"],
        "stdout_summary": case["summary"],
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
        raise FilesystemError("collector requires native Darwin x86_64")
    if not 1 <= timeout_seconds <= 3600:
        raise FilesystemError("timeout-seconds must be in 1..3600")
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
            raise FilesystemError(f"input report must be bundle-local: {name}")
    if output.exists():
        raise FilesystemError("candidate report already exists")
    raw_dir = output.parent / "raw" / "cli-filesystem"
    raw_dir.mkdir(parents=True, exist_ok=True)
    if any(raw_dir.iterdir()):
        raise FilesystemError("filesystem raw directory must be empty")

    baseline_collector = _load(
        root, BASELINE_COLLECTOR, "macos_baseline_for_filesystem"
    )
    baseline_validator = _load(
        root, BASELINE_VALIDATOR, "macos_baseline_validator_for_filesystem"
    )
    common = baseline_collector.load_module(
        "windows_cli_common_for_macos_filesystem",
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
        raise FilesystemError("binary must be <source>/build/release/diec")
    source = common.validate_source(source_dir)
    source["tracked_files_clean_before_and_after"] = True
    qt = baseline_collector.validate_qt(common, qt_dir, oracle)
    binary_sha256 = common.sha256_file(binary)
    if binary_sha256 != oracle["artifact"]["sha256"]:
        raise FilesystemError("binary differs from oracle report")
    if baseline_report["source"] != source or baseline_report["qt"] != qt:
        raise FilesystemError("baseline source/Qt identity differs")
    if baseline_report["binary"]["sha256"] != binary_sha256:
        raise FilesystemError("baseline binary identity differs")

    manifest, manifest_raw, live_fixture = validate_fixture(
        root, fixture_dir
    )
    linux_raw = (root / LINUX_REFERENCE).read_bytes()
    linux_reference = json.loads(linux_raw)
    reference_tree = baseline_report["corpus"]["minimal.pdf"][
        "first_detect_tree"
    ]
    actual_db = database_arguments(source_dir, report=False)
    report_db = database_arguments(source_dir, report=True)

    reports = {}
    determinism_failures = []
    timeout_cases = []
    linux_semantic_failures = []
    reference_projection_failures = []
    for case in CASES:
        actual_path = fixture_dir.joinpath(*case.relative.split("/"))
        cap = case.timeout_cap_seconds or timeout_seconds
        effective_timeout = min(timeout_seconds, cap)
        arguments = ("--json", *actual_db, str(actual_path))
        report_arguments = (
            "--json",
            *report_db,
            f"<fixture>/{case.relative}",
        )
        first, first_timeout = observe(
            common,
            binary,
            qt_dir,
            arguments,
            timeout_seconds=effective_timeout,
        )
        second, second_timeout = observe(
            common,
            binary,
            qt_dir,
            arguments,
            timeout_seconds=effective_timeout,
        )
        entry = baseline_collector.pair_report(
            common,
            output.parent,
            f"cli-filesystem/{case.name}",
            first,
            second,
        )
        first_tree = common.json_detect_tree(first.stdout)
        second_tree = common.json_detect_tree(second.stdout)
        first_summary = stdout_summary(first.stdout)
        second_summary = stdout_summary(second.stdout)
        linux_projection = _linux_projection(
            linux_reference, case.linux_case
        )
        linux_equal = (
            first.exit_code == linux_projection["exit_code"]
            and first_summary == linux_projection["stdout_summary"]
        )
        reference_equal = (
            first_tree == reference_tree
            if case.reference_tree_applies
            else None
        )
        entry.update(
            {
                "arguments": list(report_arguments),
                "timeout_seconds": effective_timeout,
                "first_timed_out": first_timeout,
                "second_timed_out": second_timeout,
                "first_stdout_summary": first_summary,
                "second_stdout_summary": second_summary,
                "first_prefix_paths": prefix_paths(
                    first.stdout, fixture_dir
                ),
                "second_prefix_paths": prefix_paths(
                    second.stdout, fixture_dir
                ),
                "first_detect_tree": first_tree,
                "second_detect_tree": second_tree,
                "reference_tree_applies": case.reference_tree_applies,
                "minimal_pdf_detect_tree_equal": reference_equal,
                "linux_case": case.linux_case,
                "linux_qt5_projection": linux_projection,
                "linux_qt5_semantic_equal": linux_equal,
            }
        )
        reports[case.name] = entry
        if entry["determinism_differences"] or (
            first_timeout != second_timeout
        ):
            determinism_failures.append(case.name)
        if first_timeout or second_timeout:
            timeout_cases.append(case.name)
        if not linux_equal:
            linux_semantic_failures.append(case.name)
        if case.reference_tree_applies and not reference_equal:
            reference_projection_failures.append(case.name)

    case_count = len(CASES)
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
            "archive_sha256": manifest["archive"]["sha256"],
            "archive_size": manifest["archive"]["size"],
            "entry_count": len(manifest["entries"]),
            "live_preflight": live_fixture,
        },
        "linux_qt5_reference": {
            "path": LINUX_REFERENCE,
            "sha256": sha256(linux_raw),
        },
        "local_paths": {"fixture_dir": str(fixture_dir)},
        "selection": {
            "case_names": [case.name for case in CASES],
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
            "reference_projection_failures": (
                reference_projection_failures
            ),
            "deterministic": not determinism_failures,
            "linux_semantics_equal": not linux_semantic_failures,
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
            output=args.output,
            timeout_seconds=args.timeout_seconds,
        )
    except (FilesystemError, OSError, ValueError) as error:
        print(f"macOS CLI filesystem error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
