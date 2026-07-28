#!/usr/bin/env python3
"""Collect deterministic native-Windows Qt5 NTFS ADS behavior."""

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
FIXTURE_SCRIPT = ROOT / "tools/corpus/generate_windows_ads_fixture.py"


def load_module(name: str, path: Path) -> object:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load helper module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


baseline = load_module(
    "collect_windows_cli_baseline_ads_helper",
    BASELINE_SCRIPT,
)
fixture_generator = load_module(
    "generate_windows_ads_fixture_helper",
    FIXTURE_SCRIPT,
)
ProbeError = baseline.BaselineError


@dataclass(frozen=True)
class Case:
    name: str
    target: str
    report_target: str
    reference_sample: str
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
    corpus_dir: Path,
) -> tuple[Case, ...]:
    carrier = fixture_dir / "ads" / "carrier.bin"
    stream = fixture_generator.ads_path(carrier)
    return (
        Case(
            "pdf_control",
            str(corpus_dir / "minimal.pdf"),
            "<corpus>/minimal.pdf",
            "minimal.pdf",
        ),
        Case(
            "carrier_default_stream",
            str(carrier),
            "<fixture>/ads/carrier.bin",
            "plain.txt",
        ),
        Case(
            "named_pdf_stream",
            str(stream),
            "<fixture>/ads/carrier.bin:payload.pdf",
            "minimal.pdf",
        ),
        Case(
            "extended_named_pdf_stream",
            fixture_generator.extended_path(stream),
            "<extended-fixture>/ads/carrier.bin:payload.pdf",
            "minimal.pdf",
        ),
        Case(
            "directory_enumeration",
            str(fixture_dir / "ads"),
            "<fixture>/ads",
            "plain.txt",
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--qt-dir", type=Path, required=True)
    parser.add_argument("--fixture-dir", type=Path, required=True)
    parser.add_argument("--corpus-dir", type=Path, required=True)
    parser.add_argument("--expected-binary-sha256", required=True)
    parser.add_argument(
        "--fixture-manifest",
        type=Path,
        default=ROOT / "docs/research/data/windows-ads-fixture.json",
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
    corpus_dir = args.corpus_dir.resolve(strict=True)
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
        raise ProbeError("Windows ADS fixture manifest differs")
    manifest = json.loads(manifest_raw)
    fixture_generator.validate_fixture(fixture_dir, manifest)

    corpus_manifest = json.loads(
        (corpus_dir / "manifest.json").read_text(encoding="utf-8")
    )
    if corpus_manifest.get("schema_version") != 1:
        raise ProbeError("unsupported Windows corpus manifest")
    for sample_name in ("minimal.pdf", "plain.txt"):
        sample = next(
            (
                item
                for item in corpus_manifest["samples"]
                if item["name"] == sample_name
            ),
            None,
        )
        if sample is None:
            raise ProbeError(f"missing corpus sample: {sample_name}")
        sample_path = corpus_dir / sample_name
        if (
            sample_path.stat().st_size != sample["size"]
            or baseline.sha256_file(sample_path) != sample["sha256"]
        ):
            raise ProbeError(f"corpus identity mismatch: {sample_name}")

    baseline_path = args.windows_baseline.resolve(strict=True)
    baseline_raw = baseline_path.read_bytes()
    baseline_report = json.loads(baseline_raw)
    if baseline_report["binary"]["sha256"] != binary_sha256:
        raise ProbeError("Windows baseline binary identity differs")
    reference_trees = {
        name: baseline_report["corpus"][name]["first_detect_tree"]
        for name in ("minimal.pdf", "plain.txt")
    }

    actual_db = database_arguments(source_dir, report=False)
    report_db = database_arguments(source_dir, report=True)
    cases = build_cases(fixture_dir, corpus_dir)
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
        reference_tree = reference_trees[case.reference_sample]
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
                "reference_sample": case.reference_sample,
                "expected_exit_code": case.expected_exit,
                "expected_exit_code_equal": (
                    first.exit_code == case.expected_exit
                ),
                "first_valid_json": first_valid_json,
                "second_valid_json": second_valid_json,
                "first_detect_tree": first_tree,
                "second_detect_tree": second_tree,
                "reference_detect_tree_equal": (
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

    pdf_hash = reports["pdf_control"]["first"]["stdout_sha256"]
    base_hash = reports["carrier_default_stream"]["first"][
        "stdout_sha256"
    ]
    findings = {
        "named_stream_is_scanned_as_pdf": (
            reports["named_pdf_stream"]["reference_detect_tree_equal"]
        ),
        "extended_named_stream_is_scanned_as_pdf": (
            reports["extended_named_pdf_stream"][
                "reference_detect_tree_equal"
            ]
        ),
        "named_stream_stdout_byte_equal_to_pdf_control": (
            reports["named_pdf_stream"]["first"]["stdout_sha256"]
            == pdf_hash
        ),
        "extended_named_stream_stdout_byte_equal_to_pdf_control": (
            reports["extended_named_pdf_stream"]["first"]["stdout_sha256"]
            == pdf_hash
        ),
        "carrier_default_stream_is_scanned_as_plain_text": (
            reports["carrier_default_stream"][
                "reference_detect_tree_equal"
            ]
        ),
        "directory_enumeration_scans_only_default_stream": (
            reports["directory_enumeration"][
                "reference_detect_tree_equal"
            ]
            and reports["directory_enumeration"]["first"]["stdout_sha256"]
            == base_hash
        ),
    }
    report = {
        "schema_version": 1,
        "generator": "tools/upstream/collect_windows_cli_ads.py",
        "generator_sha256": baseline.sha256_file(Path(__file__)),
        "fixture_generator": {
            "path": "tools/corpus/generate_windows_ads_fixture.py",
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
            "manifest": "docs/research/data/windows-ads-fixture.json",
            "sha256": hashlib.sha256(manifest_raw).hexdigest(),
            "carrier": manifest["carrier"],
            "named_stream": manifest["named_stream"],
            "filesystem_contract": manifest["filesystem_contract"],
        },
        "windows_default_reference": {
            "path": (
                "docs/research/data/baseline-corpus-windows-qt5.json"
            ),
            "sha256": hashlib.sha256(baseline_raw).hexdigest(),
            "samples": ["minimal.pdf", "plain.txt"],
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
                "the fixture covers one named $DATA stream on an ordinary "
                "file, not directory streams or other NTFS stream types"
            ),
            (
                "directory enumeration proves the named stream is not a "
                "separate CLI target; it does not enumerate streams via a "
                "native backup API"
            ),
            (
                "UNC, ACL denial, symbolic links, dangling/cyclic reparse "
                "points, case-sensitive directories, and exact path maxima "
                "remain separate gaps"
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
