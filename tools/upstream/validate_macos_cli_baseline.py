#!/usr/bin/env python3
"""Validate a raw-output macOS Qt5 CLI baseline candidate bundle."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
PLATFORM = "macos-x86_64-qt5"
COLLECTOR = "tools/upstream/collect_macos_cli_baseline.py"
SHARED_COLLECTOR = "tools/upstream/collect_windows_cli_baseline.py"
ORACLE_VALIDATOR = (
    "tools/upstream/validate_macos_qt5_oracle_report.py"
)
BASELINE_MANIFEST = "docs/research/data/baseline-corpus.json"
LINUX_REFERENCE = (
    "docs/research/data/baseline-corpus-linux-qt5.json"
)
SHA256_RE = re.compile(r"[0-9a-f]{64}")
EXPECTED_ADMISSION_REASON = (
    "general CLI and baseline corpus candidate only; "
    "the complete 68-row macOS closure is missing"
)
EXPECTED_LIMITATIONS = [
    (
        "the bundle covers general CLI identity, database listing, "
        "missing-path handling, and one default JSON scan per "
        "generated baseline sample"
    ),
    (
        "option, output, special, nested, filesystem, database error, "
        "and engine-only matrices require separate macOS evidence"
    ),
    (
        "every raw stdout and stderr stream is retained; only the "
        "named detection projection and exit code are compared with "
        "Linux Qt5"
    ),
]


class ReportError(ValueError):
    """The candidate bundle is incomplete, unsafe, or inconsistent."""


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ReportError(f"cannot load helper module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def reject_duplicates(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ReportError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    try:
        value = json.loads(
            raw,
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda constant: (_ for _ in ()).throw(
                ReportError(
                    f"non-finite JSON constant: {constant}"
                )
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReportError(f"invalid JSON: {path}: {error}") from error
    if not isinstance(value, dict):
        raise ReportError(f"JSON root must be an object: {path}")
    return value, raw


def require_object(value: Any, description: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReportError(f"{description} must be an object")
    return value


def require_sha256(value: Any, description: str) -> None:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise ReportError(f"invalid SHA-256: {description}")


def read_raw(
    bundle_dir: Path,
    relative: Any,
    description: str,
) -> bytes:
    if not isinstance(relative, str):
        raise ReportError(f"raw path missing: {description}")
    relative_path = Path(relative)
    if (
        relative_path.is_absolute()
        or ".." in relative_path.parts
        or not relative_path.parts
        or relative_path.parts[0] != "raw"
    ):
        raise ReportError(f"unsafe raw path: {description}")
    path = bundle_dir / relative_path
    if path.is_symlink() or not path.is_file():
        raise ReportError(f"raw file missing or symbolic: {description}")
    resolved = path.resolve()
    raw_root = (bundle_dir / "raw").resolve()
    if raw_root not in resolved.parents:
        raise ReportError(f"raw path escaped bundle: {description}")
    return path.read_bytes()


def validate_observation(
    value: Any,
    bundle_dir: Path,
    description: str,
    raw_stem: str,
) -> tuple[int, bytes, bytes]:
    observation = require_object(value, description)
    expected = {
        "exit_code",
        "stdout_bytes",
        "stdout_sha256",
        "stderr_bytes",
        "stderr_sha256",
        "stdout_path",
        "stderr_path",
    }
    if set(observation) != expected:
        raise ReportError(f"observation field drift: {description}")
    exit_code = observation["exit_code"]
    if not isinstance(exit_code, int) or isinstance(exit_code, bool):
        raise ReportError(f"exit code missing: {description}")
    streams = []
    for stream in ("stdout", "stderr"):
        expected_path = f"raw/{raw_stem}.{stream}"
        if observation[f"{stream}_path"] != expected_path:
            raise ReportError(
                f"raw path identity drift: {description}.{stream}"
            )
        raw = read_raw(
            bundle_dir,
            observation[f"{stream}_path"],
            f"{description}.{stream}",
        )
        require_sha256(
            observation[f"{stream}_sha256"],
            f"{description}.{stream}",
        )
        if (
            observation[f"{stream}_bytes"] != len(raw)
            or observation[f"{stream}_sha256"] != sha256(raw)
        ):
            raise ReportError(
                f"raw stream identity mismatch: {description}.{stream}"
            )
        streams.append(raw)
    return exit_code, streams[0], streams[1]


def validate_pair(
    value: Any,
    bundle_dir: Path,
    description: str,
    raw_stem: str,
) -> tuple[tuple[int, bytes, bytes], tuple[int, bytes, bytes]]:
    pair = require_object(value, description)
    first = validate_observation(
        pair.get("first"),
        bundle_dir,
        f"{description}.first",
        f"{raw_stem}.first",
    )
    second = validate_observation(
        pair.get("second"),
        bundle_dir,
        f"{description}.second",
        f"{raw_stem}.second",
    )
    differences = []
    if first[0] != second[0]:
        differences.append("exit_code")
    if first[1] != second[1]:
        differences.append("stdout")
    if first[2] != second[2]:
        differences.append("stderr")
    if pair.get("determinism_differences") != differences:
        raise ReportError(f"determinism projection drift: {description}")
    return first, second


def validate_report(
    report: dict[str, Any],
    *,
    report_path: Path,
    oracle_path: Path,
    root: Path,
) -> None:
    expected_oracle_path = report_path.parent / "oracle-candidate.json"
    if oracle_path != expected_oracle_path.resolve(strict=True):
        raise ReportError(
            "oracle report must be the bundle-local oracle-candidate.json"
        )
    expected_root = {
        "schema_version",
        "result",
        "platform",
        "generator",
        "oracle_report",
        "source",
        "qt",
        "binary",
        "corpus_manifest",
        "linux_qt5_reference",
        "cases",
        "corpus",
        "summary",
        "admission",
        "limitations",
    }
    if set(report) != expected_root:
        raise ReportError("report root fields changed")
    if (
        report["schema_version"] != 1
        or report["result"] != "candidate"
        or report["platform"] != PLATFORM
    ):
        raise ReportError("report identity drift")

    generator = require_object(report["generator"], "generator")
    expected_generator = {
        "path": COLLECTOR,
        "sha256": sha256((root / COLLECTOR).read_bytes()),
        "shared_collector_path": SHARED_COLLECTOR,
        "shared_collector_sha256": sha256(
            (root / SHARED_COLLECTOR).read_bytes()
        ),
        "validator_path": (
            "tools/upstream/validate_macos_cli_baseline.py"
        ),
        "validator_sha256": sha256(Path(__file__).read_bytes()),
    }
    if generator != expected_generator:
        raise ReportError("generator identity drift")

    oracle_validator = load_module(
        "macos_oracle_validator_for_cli_bundle_validation",
        root / ORACLE_VALIDATOR,
    )
    oracle = oracle_validator.load_report(oracle_path)
    oracle_validator.validate_report(oracle)
    oracle_raw = oracle_path.read_bytes()
    if report["oracle_report"] != {
        "path": "oracle-candidate.json",
        "sha256": sha256(oracle_raw),
    }:
        raise ReportError("oracle report binding drift")

    source = require_object(report["source"], "source")
    if source != {
        "repository": "https://github.com/horsicq/DIE-engine",
        "commit": UPSTREAM_COMMIT,
        "recursive_submodule_count": 58,
        "rules_commit": RULES_COMMIT,
        "tracked_files_clean_before_and_after": True,
    }:
        raise ReportError("source identity drift")
    qt = require_object(report["qt"], "qt")
    if qt != {
        "version": oracle["qt"]["version"],
        "qmake_spec": oracle["qt"]["qmake_spec"],
        "qmake_sha256": oracle["qt"]["qmake_sha256"],
        "qtcore_sha256": oracle["qt"]["qtcore_sha256"],
        "qtscript_sha256": oracle["qt"]["qtscript_sha256"],
    }:
        raise ReportError("Qt identity drift")
    binary = require_object(report["binary"], "binary")
    if (
        binary.get("relative_path") != "build/release/diec"
        or binary.get("size") != oracle["artifact"]["size"]
        or binary.get("sha256") != oracle["artifact"]["sha256"]
    ):
        raise ReportError("binary identity drift")

    manifest, manifest_raw = load_json(root / BASELINE_MANIFEST)
    samples = manifest.get("samples")
    if not isinstance(samples, list):
        raise ReportError("baseline manifest samples missing")
    if report["corpus_manifest"] != {
        "path": BASELINE_MANIFEST,
        "sha256": sha256(manifest_raw),
        "sample_count": len(samples),
    }:
        raise ReportError("corpus manifest binding drift")
    linux, linux_raw = load_json(root / LINUX_REFERENCE)
    if report["linux_qt5_reference"] != {
        "path": LINUX_REFERENCE,
        "sha256": sha256(linux_raw),
    }:
        raise ReportError("Linux reference binding drift")
    linux_corpus = require_object(linux.get("corpus"), "Linux corpus")

    collector = load_module(
        "macos_cli_collector_for_bundle_validation",
        root / COLLECTOR,
    )
    common = load_module(
        "windows_cli_common_for_bundle_validation",
        root / SHARED_COLLECTOR,
    )
    cases = require_object(report["cases"], "cases")
    expected_cases = collector.expected_cases(common)
    if set(cases) != {case.name for case in expected_cases}:
        raise ReportError("case set drift")

    determinism_failures: list[str] = []
    for case in expected_cases:
        value = require_object(cases[case.name], f"cases.{case.name}")
        if set(value) != {
            "first",
            "second",
            "determinism_differences",
            "arguments",
        }:
            raise ReportError(f"case field set drift: {case.name}")
        if value.get("arguments") != list(case.report_arguments):
            raise ReportError(f"case arguments drift: {case.name}")
        first, second = validate_pair(
            value,
            report_path.parent,
            f"cases.{case.name}",
            f"cli-baseline/cases/{case.name}",
        )
        if first != second:
            determinism_failures.append(f"cases.{case.name}")

    corpus = require_object(report["corpus"], "corpus")
    sample_names = [str(sample["name"]) for sample in samples]
    if set(corpus) != set(sample_names):
        raise ReportError("corpus result set drift")
    projection_failures: list[str] = []
    database_args = [
        "--database",
        "<source>/Detect-It-Easy/db",
        "--extradatabase",
        "<source>/Detect-It-Easy/db_extra",
        "--customdatabase",
        "<source>/Detect-It-Easy/db_custom",
    ]
    for sample in samples:
        name = str(sample["name"])
        value = require_object(corpus[name], f"corpus.{name}")
        if set(value) != {
            "first",
            "second",
            "determinism_differences",
            "arguments",
            "intended_format",
            "sample_sha256",
            "first_detect_tree",
            "second_detect_tree",
            "linux_qt5_detect_tree",
            "linux_projection_equal",
            "linux_exit_code_equal",
        }:
            raise ReportError(f"corpus field set drift: {name}")
        expected_arguments = [
            "--json",
            *database_args,
            f"<corpus>/{name}",
        ]
        if (
            value.get("arguments") != expected_arguments
            or value.get("intended_format") != sample["intended_format"]
            or value.get("sample_sha256") != sample["sha256"]
        ):
            raise ReportError(f"corpus metadata drift: {name}")
        first, second = validate_pair(
            value,
            report_path.parent,
            f"corpus.{name}",
            f"cli-baseline/corpus/{name}",
        )
        first_tree = common.json_detect_tree(first[1])
        second_tree = common.json_detect_tree(second[1])
        linux_item = require_object(
            linux_corpus.get(name), f"Linux corpus.{name}"
        )
        linux_tree = linux_item["left_detect_tree"]
        linux_exit = linux_item["left"]["exit_code"]
        expected_projection = {
            "first_detect_tree": first_tree,
            "second_detect_tree": second_tree,
            "linux_qt5_detect_tree": linux_tree,
            "linux_projection_equal": first_tree == linux_tree,
            "linux_exit_code_equal": first[0] == linux_exit,
        }
        for field, expected in expected_projection.items():
            if value.get(field) != expected:
                raise ReportError(
                    f"corpus projection drift: {name}.{field}"
                )
        if first != second:
            determinism_failures.append(f"corpus.{name}")
        if first_tree != linux_tree or first[0] != linux_exit:
            projection_failures.append(name)

    summary = require_object(report["summary"], "summary")
    expected_summary = {
        "case_count": len(expected_cases),
        "corpus_count": len(samples),
        "execution_count": 2 * (len(expected_cases) + len(samples)),
        "determinism_failures": determinism_failures,
        "linux_projection_failures": projection_failures,
        "deterministic": not determinism_failures,
        "linux_projection_equal": not projection_failures,
    }
    if summary != expected_summary:
        raise ReportError("summary drift")

    admission = require_object(report["admission"], "admission")
    if (
        admission
        != {
            "platform_admitted": False,
            "capability_rows_admitted": 0,
            "reason": EXPECTED_ADMISSION_REASON,
        }
    ):
        raise ReportError("candidate must not admit capability evidence")
    limitations = report["limitations"]
    if limitations != EXPECTED_LIMITATIONS:
        raise ReportError("limitations are incomplete")

    declared_raw_paths = {
        observation[f"{stream}_path"]
        for collection in (cases, corpus)
        for pair in collection.values()
        for observation_name in ("first", "second")
        for observation in [
            require_object(
                require_object(pair, "result pair").get(
                    observation_name
                ),
                "result observation",
            )
        ]
        for stream in ("stdout", "stderr")
    }
    raw_root = report_path.parent / "raw" / "cli-baseline"
    actual_raw_paths = {
        path.relative_to(report_path.parent).as_posix()
        for path in raw_root.rglob("*")
        if path.is_file()
    }
    if actual_raw_paths != declared_raw_paths:
        raise ReportError("raw file inventory differs from report")


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--oracle-report", type=Path, required=True)
    parser.set_defaults(root=root)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report_path = args.report.resolve(strict=True)
        oracle_path = args.oracle_report.resolve(strict=True)
        report, _ = load_json(report_path)
        validate_report(
            report,
            report_path=report_path,
            oracle_path=oracle_path,
            root=args.root.resolve(),
        )
    except (ReportError, OSError, ValueError) as error:
        print(
            f"macOS CLI baseline validation error: {error}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
