#!/usr/bin/env python3
"""Collect native-Windows Qt5 archive depth and expansion-limit evidence."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
UPSTREAM_DIR = ROOT / "tools/upstream"
DATA_DIR = ROOT / "docs/research/data"
BUILDER = UPSTREAM_DIR / "build_windows_archive_limits_harness.ps1"
HARNESS_SOURCE = UPSTREAM_DIR / "archive_limits_harness_main.cpp"
CORPUS_MANIFEST = DATA_DIR / "archive-limit-corpus.json"
LINUX_REPORT = DATA_DIR / "archive-limit-engine-qt5.json"
EXPECTED_HARNESS_SOURCE_SHA256 = (
    "9bba1c21cf01b93a1ac80ab5cea4145330e1b2621d9f2b6e4275ab04723a68a4"
)
EXPECTED_ADAPTED_SOURCE_SHA256 = (
    "b33630b803679d3fe29244e85d996d120ce4b95e894b5e9110a8ac34bd10d24c"
)
EXPECTED_MAKEFILE_SHA256 = (
    "e6f7710cd32be5050e10234f3282d2512b58d28170d5de14f96c30478ac03725"
)
EXPECTED_MAIN_OBJECT_SHA256 = (
    "ff736a313b4d8d53747a7b113fff5a310c31c4218555ffbf1570537af15dd6be"
)
EXPECTED_CLI_SHA256 = (
    "e8579a6ed0d2536ea14af154bcbeeaaea6967c0c7559a595"
    "fb3fe52206ac635e"
)
EXPECTED_REPLACEMENTS = {
    "/opt/die-source/Detect-It-Easy/db_custom": (
        "Detect-It-Easy/db_custom",
        1,
    ),
    "/opt/die-source/Detect-It-Easy/db_extra": (
        "Detect-It-Easy/db_extra",
        1,
    ),
    "/opt/die-source/Detect-It-Easy/db": (
        "Detect-It-Easy/db",
        1,
    ),
}
SEMANTIC_FIELDS = (
    "cancel_after_callbacks",
    "cyclic_node_count",
    "debug_record_count",
    "deepest_pdf_depth",
    "error_count",
    "handler_count",
    "max_depth",
    "max_stream_depth",
    "node_count",
    "pdf_node_count",
    "pd_stopped",
    "record_count",
    "stream_node_count",
)
METRIC_FIELDS = (
    "callback_calls",
    "elapsed_ms",
    "peak_rss_after_kib",
    "peak_rss_before_kib",
    "scan_result_time_ms",
)


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load helper module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


baseline = load_module(
    "collect_windows_archive_limits_baseline",
    UPSTREAM_DIR / "collect_windows_cli_baseline.py",
)
probe = load_module(
    "collect_windows_archive_limits_probe",
    UPSTREAM_DIR / "probe_archive_limits_harness.py",
)
HarnessError = baseline.BaselineError


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    return probe.parse_json(raw, str(path)), raw


def validate_build_manifest(
    manifest: dict[str, Any],
    harness: Path,
) -> None:
    identity = manifest.get("baseline", {})
    qt = manifest.get("qt", {})
    build = manifest.get("build", {})
    adaptation = build.get("platform_adaptation", {})
    sources = manifest.get("source_hashes", {})
    harness_source = sources.get("harness", {})
    artifact = manifest.get("artifact", {})
    replacements = harness_source.get("database_path_replacements", [])
    observed_replacements = {
        item.get("from"): (item.get("to"), item.get("count"))
        for item in replacements
        if isinstance(item, dict)
    }
    if (
        manifest.get("schema_version") != 1
        or identity.get("commit") != baseline.UPSTREAM_COMMIT
        or identity.get("rules_commit") != baseline.RULES_COMMIT
        or identity.get("recursive_submodule_count") != 58
        or identity.get("cli_sha256") != EXPECTED_CLI_SHA256
        or qt.get("version") != "5.15.2"
        or qt.get("qmake_spec") != "win32-msvc"
        or build.get("system") != "patched-qmake-release-makefile"
        or build.get("tool") != "nmake"
        or build.get("target_architecture") != "amd64"
        or build.get("host_architecture") != "amd64"
        or build.get("original_makefile_sha256")
        != EXPECTED_MAKEFILE_SHA256
        or build.get("original_main_object_sha256")
        != EXPECTED_MAIN_OBJECT_SHA256
        or build.get("replaced_object") != "release/main_console.obj"
        or build.get("engine_objects_modified") is not False
        or build.get("database_root")
        != "<working-directory>/Detect-It-Easy"
        or build.get("runtime_working_directory_contract")
        != "verified-source-root"
        or adaptation
        != {
            "kind": "harness-only-peak-rss",
            "unix_api": "getrusage(RUSAGE_SELF)",
            "windows_api": "GetProcessMemoryInfo",
            "engine_semantics_changed": False,
        }
        or sources.get("builder") != baseline.sha256_file(BUILDER)
        or harness_source.get("path")
        != "tools/upstream/archive_limits_harness_main.cpp"
        or harness_source.get("original_sha256")
        != EXPECTED_HARNESS_SOURCE_SHA256
        or harness_source.get("original_sha256")
        != baseline.sha256_file(HARNESS_SOURCE)
        or harness_source.get("adapted_sha256")
        != EXPECTED_ADAPTED_SOURCE_SHA256
        or observed_replacements != EXPECTED_REPLACEMENTS
        or artifact.get("filename") != harness.name
        or artifact.get("size") != harness.stat().st_size
        or artifact.get("sha256") != baseline.sha256_file(harness)
    ):
        raise HarnessError("Windows archive-limit build identity differs")


def observe_source(source_dir: Path) -> dict[str, Any]:
    path = source_dir / "XScanEngine/xscanengine.cpp"
    raw = path.read_bytes()
    source_hash = sha256_bytes(raw)
    if source_hash != probe.EXPECTED_SOURCE_SHA256:
        raise HarnessError("Windows XScanEngine source differs")
    text = raw.decode("utf-8")
    counts = {
        name: text.count(pattern)
        for name, pattern in probe.SOURCE_PATTERNS.items()
    }
    if any(count < 1 for count in counts.values()):
        raise HarnessError("Windows archive-limit source token differs")
    start = text.index(probe.SOURCE_PATTERNS["archive_option_guard"])
    end = text.index("QList<XBinary::FPART> listFileParts;", start)
    archive_block = text[start:end].lower()
    negative = {
        token: archive_block.count(token)
        for token in (
            "depth",
            "cumulative",
            "totalextracted",
            "totaldecompressed",
        )
    }
    if any(negative.values()):
        raise HarnessError("independent archive-limit token appeared")
    return {
        "path": "<source>/XScanEngine/xscanengine.cpp",
        "sha256": source_hash,
        "component_commit": probe.EXPECTED_XSCANENGINE_COMMIT,
        "archive_block_start_line": text[:start].count("\n") + 1,
        "archive_block_end_line": text[:end].count("\n") + 1,
        "required_pattern_counts": counts,
        "negative_token_counts": negative,
    }


def semantic_projection(document: dict[str, Any]) -> dict[str, Any]:
    missing = [
        field
        for field in (*SEMANTIC_FIELDS, *METRIC_FIELDS)
        if field not in document
    ]
    if missing:
        raise HarnessError(f"harness fields missing: {missing}")
    for field in METRIC_FIELDS:
        value = document[field]
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or value < 0
        ):
            raise HarnessError(f"invalid harness metric: {field}")
    if (
        document["callback_calls"] < 1
        or document["peak_rss_before_kib"] <= 0
        or document["peak_rss_after_kib"]
        < document["peak_rss_before_kib"]
    ):
        raise HarnessError("invalid callback or peak RSS observation")
    return {field: document[field] for field in SEMANTIC_FIELDS}


def observe(
    harness: Path,
    arguments: list[str],
    *,
    source_dir: Path,
    qt_dir: Path,
    timeout_seconds: int,
) -> Any:
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
    process = subprocess.run(
        [harness.name, *arguments],
        executable=str(harness),
        cwd=source_dir,
        env=environment,
        check=False,
        capture_output=True,
        timeout=timeout_seconds,
    )
    return baseline.Observation(
        process.returncode,
        process.stdout,
        process.stderr,
    )


def run_case(
    *,
    name: str,
    arguments: list[str],
    harness: Path,
    source_dir: Path,
    qt_dir: Path,
    raw_dir: Path,
    repetitions: int,
    timeout_seconds: int,
    reference: dict[str, Any],
) -> dict[str, Any]:
    reference_projection = semantic_projection(reference)
    runs = []
    projections = []
    for repetition in range(1, repetitions + 1):
        observation = observe(
            harness,
            arguments,
            source_dir=source_dir,
            qt_dir=qt_dir,
            timeout_seconds=timeout_seconds,
        )
        stem = f"{name}.run-{repetition}"
        stdout_name = stem + ".stdout"
        stderr_name = stem + ".stderr"
        (raw_dir / stdout_name).write_bytes(observation.stdout)
        (raw_dir / stderr_name).write_bytes(observation.stderr)
        if observation.exit_code != 0 or observation.stderr:
            raise HarnessError(f"Windows archive-limit run failed: {stem}")
        document = probe.parse_json(observation.stdout, stem)
        projection = semantic_projection(document)
        if projection != reference_projection:
            raise HarnessError(
                f"Windows archive-limit semantics differ: {stem}"
            )
        projections.append(projection)
        runs.append(
            {
                **observation.summary(),
                "raw_stdout": stdout_name,
                "raw_stderr": stderr_name,
                "semantic_projection": projection,
                "metrics": {
                    field: document[field] for field in METRIC_FIELDS
                },
                "linux_qt5_semantic_equal": True,
            }
        )
    return {
        "runs": runs,
        "semantic_deterministic": all(
            projection == projections[0]
            for projection in projections[1:]
        ),
        "linux_qt5_semantic_projection": reference_projection,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--harness", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--qt-dir", type=Path, required=True)
    parser.add_argument("--fixture-dir", type=Path, required=True)
    parser.add_argument("--build-manifest", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if os.name != "nt":
        raise HarnessError(
            "native Windows archive-limit collector requires Windows"
        )
    if args.repetitions < 2 or args.repetitions > 10:
        raise HarnessError("repetitions must be in 2..10")
    if args.timeout_seconds < 1 or args.timeout_seconds > 3600:
        raise HarnessError("timeout must be in 1..3600")

    harness = args.harness.resolve(strict=True)
    source_dir = args.source_dir.resolve(strict=True)
    qt_dir = args.qt_dir.resolve(strict=True)
    fixture_dir = args.fixture_dir.resolve(strict=True)
    raw_dir = args.raw_dir.resolve()
    raw_dir.mkdir(parents=True, exist_ok=True)

    source_identity = baseline.validate_source(source_dir)
    qt_identity = baseline.validate_qt(qt_dir)
    build_manifest, build_raw = read_json(
        args.build_manifest.resolve(strict=True)
    )
    validate_build_manifest(build_manifest, harness)
    source_contract = observe_source(source_dir)
    corpus, corpus_raw = probe.load_and_verify_corpus(
        fixture_dir,
        CORPUS_MANIFEST,
    )
    linux, linux_raw = read_json(LINUX_REPORT)
    if (
        linux.get("schema_version") != 1
        or linux.get("passed") is not True
        or linux.get("failures") != []
        or linux.get("upstream_commit") != baseline.UPSTREAM_COMMIT
        or linux.get("corpus") != corpus
        or linux.get("corpus_manifest_sha256")
        != sha256_bytes(corpus_raw)
        or linux.get("source_contract", {}).get("sha256")
        != source_contract["sha256"]
        or len(linux.get("normal_cases", [])) != len(corpus["samples"])
        or not all(linux.get("assertions", {}).values())
    ):
        raise HarnessError("Linux Qt5 archive-limit reference differs")
    linux_normal = {
        case["sample"]: case["harness"]
        for case in linux["normal_cases"]
    }
    if set(linux_normal) != {
        sample["name"] for sample in corpus["samples"]
    }:
        raise HarnessError("Linux archive-limit cases differ")

    normal_cases = {}
    for sample in corpus["samples"]:
        sample_name = sample["name"]
        normal_cases[sample_name] = {
            "series": sample["series"],
            "depth": sample["depth"],
            "cumulative_expanded_bytes": sample[
                "cumulative_expanded_bytes"
            ],
            **run_case(
                name=f"normal.{sample_name}",
                arguments=[str(fixture_dir / sample_name)],
                harness=harness,
                source_dir=source_dir,
                qt_dir=qt_dir,
                raw_dir=raw_dir,
                repetitions=args.repetitions,
                timeout_seconds=args.timeout_seconds,
                reference=linux_normal[sample_name],
            ),
        }

    cancellation_reference = linux["cancellation_case"]
    cancellation_sample = cancellation_reference["sample"]
    cancellation_case = {
        "sample": cancellation_sample,
        **run_case(
            name="cancel.depth-64",
            arguments=[
                "--cancel-after-callbacks",
                "1",
                str(fixture_dir / cancellation_sample),
            ],
            harness=harness,
            source_dir=source_dir,
            qt_dir=qt_dir,
            raw_dir=raw_dir,
            repetitions=args.repetitions,
            timeout_seconds=args.timeout_seconds,
            reference=cancellation_reference["harness"],
        ),
    }

    depth_cases = [
        case
        for case in normal_cases.values()
        if case["series"] == "depth"
    ]
    expanded_cases = [
        case
        for case in normal_cases.values()
        if case["series"] == "expanded_bytes"
    ]
    cancel_projection = cancellation_case["runs"][0][
        "semantic_projection"
    ]
    relationships = {
        "all_normal_runs_exit_zero_without_stderr": all(
            run["exit_code"] == 0 and run["stderr_bytes"] == 0
            for case in normal_cases.values()
            for run in case["runs"]
        ),
        "all_normal_semantics_are_deterministic": all(
            case["semantic_deterministic"]
            for case in normal_cases.values()
        ),
        "all_normal_semantics_match_linux_qt5": all(
            run["linux_qt5_semantic_equal"]
            for case in normal_cases.values()
            for run in case["runs"]
        ),
        "depth_series_reaches_64": (
            max(
                case["runs"][0]["semantic_projection"][
                    "max_stream_depth"
                ]
                for case in depth_cases
            )
            == 64
        ),
        "depth_series_reaches_deepest_pdf": all(
            case["runs"][0]["semantic_projection"][
                "deepest_pdf_depth"
            ]
            == case["depth"]
            for case in depth_cases
        ),
        "expanded_series_reaches_33554546_bytes": (
            max(
                case["cumulative_expanded_bytes"]
                for case in expanded_cases
            )
            == 33554546
        ),
        "expanded_series_reaches_depth_2_pdf": all(
            case["runs"][0]["semantic_projection"][
                "deepest_pdf_depth"
            ]
            == 2
            for case in expanded_cases
        ),
        "cancellation_is_deterministic": cancellation_case[
            "semantic_deterministic"
        ],
        "cancellation_matches_linux_qt5": all(
            run["linux_qt5_semantic_equal"]
            for run in cancellation_case["runs"]
        ),
        "cancellation_retains_root_only_prefix": (
            cancel_projection["pd_stopped"] is True
            and cancel_projection["record_count"] == 1
            and cancel_projection["stream_node_count"] == 0
            and cancel_projection["pdf_node_count"] == 0
        ),
        "source_has_required_recursive_archive_contract": all(
            count >= 1
            for count in source_contract[
                "required_pattern_counts"
            ].values()
        ),
        "source_has_no_independent_depth_or_total_token": not any(
            source_contract["negative_token_counts"].values()
        ),
    }
    if len(relationships) != 12 or not all(relationships.values()):
        raise HarnessError("Windows archive-limit relationships differ")

    execution_count = (
        len(normal_cases) + 1
    ) * args.repetitions
    report = {
        "schema_version": 1,
        "generator": (
            "tools/upstream/collect_windows_archive_limits.py"
        ),
        "generator_sha256": baseline.sha256_file(Path(__file__)),
        "platform": "windows-x86_64-qt5",
        "capability": probe.CAPABILITY,
        "host": {
            "os_build": platform.version(),
            "architecture": platform.machine(),
        },
        "source": source_identity,
        "qt": qt_identity,
        "build_manifest": {
            "sha256": sha256_bytes(build_raw),
            "identity": build_manifest,
        },
        "source_contract": source_contract,
        "fixture": {
            "path": "docs/research/data/archive-limit-corpus.json",
            "sha256": sha256_bytes(corpus_raw),
            "sample_count": len(corpus["samples"]),
        },
        "linux_qt5_reference": {
            "path": (
                "docs/research/data/archive-limit-engine-qt5.json"
            ),
            "sha256": sha256_bytes(linux_raw),
        },
        "repetitions": args.repetitions,
        "normal_case_count": len(normal_cases),
        "cancellation_case_count": 1,
        "execution_count": execution_count,
        "case_observation_count": execution_count,
        "normal_cases": normal_cases,
        "cancellation_case": cancellation_case,
        "relationships": relationships,
        "failures": [],
        "passed": True,
        "raw_artifacts": {
            "retained_externally": True,
            "directory_role": (
                "native harness stdout/stderr, excluded from repository"
            ),
            "file_count": execution_count * 2,
        },
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "execution_count": execution_count,
                "output": str(output),
                "passed": True,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
