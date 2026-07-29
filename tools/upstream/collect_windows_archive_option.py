#!/usr/bin/env python3
"""Collect the native-Windows Qt5 engine-only archive option matrix."""

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
BUILDER = UPSTREAM_DIR / "build_windows_archive_option_harness.ps1"
HARNESS_SOURCE = UPSTREAM_DIR / "archive_harness_main.cpp"
LINUX_REPORT = DATA_DIR / "archive-option-engine-qt5-qt6.json"
WINDOWS_RELEASE_REPORT = DATA_DIR / "windows-qt5-cli-path-nested.json"
FIXTURE_MANIFEST = DATA_DIR / "nested-corpus.json"
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
ARCHIVE_SAMPLES = {
    "pdf-member.zip",
    "nested-zip.zip",
    "many-pdf-members.zip",
}


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load helper module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


baseline = load_module(
    "collect_windows_archive_option_baseline",
    UPSTREAM_DIR / "collect_windows_cli_baseline.py",
)
archive_probe = load_module(
    "collect_windows_archive_option_probe",
    UPSTREAM_DIR / "probe_archive_harness.py",
)
HarnessError = baseline.BaselineError


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def read_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HarnessError(f"invalid JSON: {path}") from error
    if not isinstance(value, dict):
        raise HarnessError(f"JSON root must be an object: {path}")
    return value, raw


def expected_adapted_source(
    replacements: list[dict[str, Any]],
) -> str:
    text = HARNESS_SOURCE.read_text(encoding="utf-8")
    observed = {}
    for replacement in replacements:
        if set(replacement) != {"from", "to", "count"}:
            raise HarnessError("invalid archive source replacement record")
        source = replacement["from"]
        target = replacement["to"]
        count = replacement["count"]
        expected = EXPECTED_REPLACEMENTS.get(source)
        if (
            expected != (target, count)
            or text.count(source) != count
            or source in observed
        ):
            raise HarnessError("archive source replacement differs")
        text = text.replace(source, target)
        observed[source] = (target, count)
    if observed != EXPECTED_REPLACEMENTS:
        raise HarnessError("archive source replacement inventory differs")
    return sha256_bytes(text.encode("utf-8"))


def validate_build_manifest(
    manifest: dict[str, Any],
    binary: Path,
) -> None:
    identity = manifest.get("baseline", {})
    qt = manifest.get("qt", {})
    build = manifest.get("build", {})
    sources = manifest.get("source_hashes", {})
    harness = sources.get("harness", {})
    artifact = manifest.get("artifact", {})
    replacements = harness.get("database_path_replacements")
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
        or sources.get("builder") != baseline.sha256_file(BUILDER)
        or harness.get("path")
        != "tools/upstream/archive_harness_main.cpp"
        or harness.get("original_sha256")
        != baseline.sha256_file(HARNESS_SOURCE)
        or not isinstance(replacements, list)
        or harness.get("adapted_sha256")
        != expected_adapted_source(replacements)
        or not binary.is_file()
        or artifact.get("filename") != binary.name
        or artifact.get("size") != binary.stat().st_size
        or artifact.get("sha256") != baseline.sha256_file(binary)
    ):
        raise HarnessError("Windows archive-option build identity differs")


def validate_fixture(
    fixture_dir: Path,
) -> tuple[list[dict[str, Any]], str]:
    committed, committed_raw = read_json(FIXTURE_MANIFEST)
    generated_path = fixture_dir / "manifest.json"
    generated, generated_raw = read_json(generated_path)
    if generated != committed or generated_raw != committed_raw:
        raise HarnessError("nested fixture manifest differs")
    samples = committed.get("samples")
    if (
        committed.get("schema_version") != 1
        or committed.get("generator")
        != "tools/corpus/generate_nested_corpus.py"
        or not isinstance(samples, list)
        or len(samples) != 8
    ):
        raise HarnessError("nested fixture catalog differs")
    for sample in samples:
        path = fixture_dir / str(sample.get("name", ""))
        if (
            not path.is_file()
            or path.stat().st_size != sample.get("size")
            or baseline.sha256_file(path) != sample.get("sha256")
        ):
            raise HarnessError(f"nested fixture differs: {path.name}")
    return samples, sha256_bytes(committed_raw)


def validate_linux_reference(
    report: dict[str, Any],
    fixture_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    trees = report.get("detection_trees")
    cases = report.get("cases")
    if (
        report.get("schema_version") != 1
        or report.get("generator")
        != "tools/upstream/probe_qt6_archive_option_harness.py"
        or report.get("generator_sha256")
        != baseline.sha256_file(
            UPSTREAM_DIR / "probe_qt6_archive_option_harness.py"
        )
        or report.get("underlying_probe", {}).get("sha256")
        != baseline.sha256_file(
            UPSTREAM_DIR / "probe_archive_harness.py"
        )
        or report.get("upstream_commit") != baseline.UPSTREAM_COMMIT
        or report.get("rules_commit") != baseline.RULES_COMMIT
        or report.get("capability") != "CAP-NEST-003"
        or report.get("case_count") != 64
        or report.get("release_control_count") != 32
        or report.get("fixture", {}).get("manifest_sha256")
        != fixture_sha256
        or not isinstance(trees, dict)
        or not isinstance(cases, dict)
        or len(cases) != 8
        or len(report.get("relationships", {})) != 11
        or not all(report.get("relationships", {}).values())
    ):
        raise HarnessError("Linux archive-option reference differs")
    for tree_hash, tree in trees.items():
        if sha256_bytes(canonical_bytes(tree)) != tree_hash:
            raise HarnessError("Linux archive-option tree hash differs")
    return cases, trees


def validate_windows_release(
    report: dict[str, Any],
    fixture_sha256: str,
) -> dict[str, Any]:
    nested = report.get("nested", {}).get("cases")
    if (
        report.get("schema_version") != 1
        or report.get("platform") != "windows-x86_64-qt5"
        or report.get("source", {}).get("commit")
        != baseline.UPSTREAM_COMMIT
        or report.get("source", {}).get("rules_commit")
        != baseline.RULES_COMMIT
        or report.get("fixtures", {}).get("nested", {}).get("sha256")
        != fixture_sha256
        or not isinstance(nested, dict)
        or len(nested) != 8
    ):
        raise HarnessError("Windows release nested reference differs")
    return nested


def observe(
    binary: Path,
    qt_dir: Path,
    source_dir: Path,
    arguments: list[str],
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
        [binary.name, *arguments],
        executable=str(binary),
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--qt-dir", type=Path, required=True)
    parser.add_argument("--fixture-dir", type=Path, required=True)
    parser.add_argument("--build-manifest", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if os.name != "nt":
        raise HarnessError(
            "native Windows archive-option collector requires Windows"
        )
    if args.repetitions < 2 or args.repetitions > 20:
        raise HarnessError("repetitions must be in 2..20")
    if args.timeout_seconds < 1 or args.timeout_seconds > 3600:
        raise HarnessError("timeout-seconds must be in 1..3600")

    binary = args.binary.resolve(strict=True)
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
    validate_build_manifest(build_manifest, binary)
    samples, fixture_sha256 = validate_fixture(fixture_dir)
    linux_report, linux_raw = read_json(LINUX_REPORT)
    linux_cases, linux_trees = validate_linux_reference(
        linux_report,
        fixture_sha256,
    )
    windows_release_report, windows_release_raw = read_json(
        WINDOWS_RELEASE_REPORT
    )
    windows_release = validate_windows_release(
        windows_release_report,
        fixture_sha256,
    )

    cases: dict[str, Any] = {}
    detection_trees: dict[str, Any] = {}
    raw_stdout_hashes = set()
    raw_stderr_hashes = set()
    without_archive = {
        case.name
        for case in archive_probe.HARNESS_MATRIX
        if "--archive" not in case.arguments
    }
    for sample in samples:
        sample_name = str(sample["name"])
        sample_cases: dict[str, Any] = {}
        cases[sample_name] = sample_cases
        for case in archive_probe.HARNESS_MATRIX:
            arguments = [
                *case.arguments,
                str(fixture_dir / sample_name),
            ]
            observations = []
            trees = []
            for repetition in range(args.repetitions):
                observation = observe(
                    binary,
                    qt_dir,
                    source_dir,
                    arguments,
                    args.timeout_seconds,
                )
                raw_base = (
                    f"{sample_name}.{case.name}.run-{repetition + 1}"
                )
                stdout_name = raw_base + ".stdout"
                stderr_name = raw_base + ".stderr"
                (raw_dir / stdout_name).write_bytes(observation.stdout)
                (raw_dir / stderr_name).write_bytes(observation.stderr)
                if observation.exit_code != 0 or observation.stderr:
                    raise HarnessError(
                        f"archive-option run failed: "
                        f"{sample_name}.{case.name}.{repetition + 1}"
                    )
                tree = archive_probe.SHARED.json_detect_tree(
                    observation.stdout
                )
                if tree is None:
                    raise HarnessError("archive-option stdout is not JSON")
                tree_hash = sha256_bytes(canonical_bytes(tree))
                existing = detection_trees.setdefault(tree_hash, tree)
                if existing != tree:
                    raise HarnessError(
                        "Windows archive-option tree hash collision"
                    )
                observations.append(
                    {
                        **observation.summary(),
                        "raw_stdout": stdout_name,
                        "raw_stderr": stderr_name,
                        "detect_tree_sha256": tree_hash,
                    }
                )
                trees.append(tree)
                raw_stdout_hashes.add(
                    observations[-1]["stdout_sha256"]
                )
                raw_stderr_hashes.add(
                    observations[-1]["stderr_sha256"]
                )

            linux_entry = linux_cases[sample_name][case.name]
            linux_tree_hash = linux_entry["observations"]["qt5"][
                "detect_tree_sha256"
            ]
            if (
                not all(tree == trees[0] for tree in trees[1:])
                or linux_tree_hash not in linux_trees
                or trees[0] != linux_trees[linux_tree_hash]
            ):
                raise HarnessError(
                    f"archive-option semantic drift: "
                    f"{sample_name}.{case.name}"
                )
            release_equal = None
            if case.name in without_archive:
                release_tree = windows_release[sample_name][case.name][
                    "first_detect_tree"
                ]
                release_equal = trees[0] == release_tree
                if not release_equal:
                    raise HarnessError(
                        f"archive-option release control drift: "
                        f"{sample_name}.{case.name}"
                    )
            sample_cases[case.name] = {
                "arguments": [
                    *case.arguments,
                    f"<fixture>/{sample_name}",
                ],
                "observations": observations,
                "deterministic": True,
                "linux_qt5_detect_tree_sha256": linux_tree_hash,
                "linux_qt5_semantic_equal": True,
                "windows_release_semantic_equal": release_equal,
                "stream_count": archive_probe.count_file_parts(
                    trees[0], "Stream"
                ),
                "resource_count": archive_probe.count_file_parts(
                    trees[0], "Resource"
                ),
                "overlay_count": archive_probe.count_file_parts(
                    trees[0], "Overlay"
                ),
            }

    with_archive = {
        case.name
        for case in archive_probe.HARNESS_MATRIX
        if "--archive" in case.arguments
    }
    relationships = {
        "all_64_cases_are_deterministic": all(
            case["deterministic"]
            for sample_cases in cases.values()
            for case in sample_cases.values()
        ),
        "all_64_cases_match_linux_qt5": all(
            case["linux_qt5_semantic_equal"]
            for sample_cases in cases.values()
            for case in sample_cases.values()
        ),
        "all_32_no_archive_cases_match_windows_release": all(
            case["windows_release_semantic_equal"] is True
            for sample_cases in cases.values()
            for name, case in sample_cases.items()
            if name in without_archive
        ),
        "archive_samples_have_no_stream_without_archive_option": all(
            cases[sample][name]["stream_count"] == 0
            for sample in ARCHIVE_SAMPLES
            for name in without_archive
        ),
        "archive_samples_have_streams_with_archive_option": all(
            cases[sample][name]["stream_count"] > 0
            for sample in ARCHIVE_SAMPLES
            for name in with_archive
        ),
        "nested_archive_option_propagates_to_inner_zip": (
            cases["nested-zip.zip"]["archive"]["stream_count"] == 2
        ),
        "default_archive_member_control_stops_at_21": (
            cases["many-pdf-members.zip"]["archive"]["stream_count"]
            == 21
        ),
        "aggressive_archive_member_control_reaches_22": (
            cases["many-pdf-members.zip"]["archive_aggressive"][
                "stream_count"
            ]
            == 22
        ),
        "default_resource_control_stops_at_21": (
            cases["pe-many-pdf-resources.exe"]["recursive"][
                "resource_count"
            ]
            == 21
        ),
        "aggressive_resource_control_reaches_22": (
            cases["pe-many-pdf-resources.exe"][
                "recursive_aggressive"
            ]["resource_count"]
            == 22
        ),
        "archive_option_is_independent_of_aggressive": all(
            cases[sample]["archive"]["stream_count"] > 0
            and cases[sample]["aggressive"]["stream_count"] == 0
            for sample in ARCHIVE_SAMPLES
        ),
    }
    if len(relationships) != 11 or not all(relationships.values()):
        raise HarnessError("Windows archive-option relationships differ")

    report = {
        "schema_version": 1,
        "generator": (
            "tools/upstream/collect_windows_archive_option.py"
        ),
        "generator_sha256": baseline.sha256_file(Path(__file__)),
        "platform": "windows-x86_64-qt5",
        "capability": "CAP-NEST-003",
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
        "fixture": {
            "path": "docs/research/data/nested-corpus.json",
            "sha256": fixture_sha256,
            "sample_count": len(samples),
        },
        "linux_qt5_reference": {
            "path": "docs/research/data/archive-option-engine-qt5-qt6.json",
            "sha256": sha256_bytes(linux_raw),
        },
        "windows_release_reference": {
            "path": (
                "docs/research/data/windows-qt5-cli-path-nested.json"
            ),
            "sha256": sha256_bytes(windows_release_raw),
        },
        "repetitions": args.repetitions,
        "case_count": sum(len(value) for value in cases.values()),
        "execution_count": (
            sum(len(value) for value in cases.values())
            * args.repetitions
        ),
        "case_observation_count": (
            sum(len(value) for value in cases.values())
            * args.repetitions
        ),
        "release_control_count": sum(
            case["windows_release_semantic_equal"] is not None
            for sample_cases in cases.values()
            for case in sample_cases.values()
        ),
        "unique_raw_stdout_count": len(raw_stdout_hashes),
        "unique_raw_stderr_count": len(raw_stderr_hashes),
        "detection_trees": detection_trees,
        "cases": cases,
        "relationships": relationships,
        "failures": [],
        "passed": True,
        "raw_artifacts": {
            "storage": "untracked external directory selected by --raw-dir",
            "stdout_and_stderr_retained_for_every_execution": True,
        },
        "limitations": [
            "the matrix covers the eight project-generated nested fixtures",
            "count observations stop at 22 and do not close the 100000 iteration boundary",
            "depth and cumulative expanded-byte limits require the separate limit harness",
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
    print(serialized.decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
