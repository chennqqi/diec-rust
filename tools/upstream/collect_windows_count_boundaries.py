#!/usr/bin/env python3
"""Collect Windows Qt5 archive/resource exact count boundaries."""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any
import zlib


ROOT = Path(__file__).resolve().parents[2]
UPSTREAM_DIR = ROOT / "tools/upstream"
DATA_DIR = ROOT / "docs/research/data"
BUILDER = UPSTREAM_DIR / "build_windows_archive_iteration_harness.ps1"
HARNESS_SOURCE = (
    UPSTREAM_DIR / "archive_iteration_boundary_harness_main.cpp"
)
ARCHIVE_MANIFEST = (
    DATA_DIR / "archive-iteration-boundary-corpus.json"
)
RESOURCE_MANIFEST = (
    DATA_DIR / "scan-option-boundary-fixture.json"
)
LINUX_ARCHIVE_REPORT = (
    DATA_DIR / "archive-iteration-boundary-engine-qt5.json"
)
LINUX_RESOURCE_REPORT = (
    DATA_DIR / "scan-option-boundaries-linux-qt5.json"
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
EXPECTED_HARNESS_SOURCE_SHA256 = (
    "b8f35799ddda9e61fcff70081e7cdb6550ca2b9e9442a340"
    "a8b4ff31d2170e41"
)
EXPECTED_ADAPTED_SOURCE_SHA256 = (
    "7f6beffdd46844ee039812c16cd3a4dc7e304e01e9c0040f"
    "a25cdba5d2205743"
)
EXPECTED_XSCANENGINE_SHA256 = (
    "e088bebb7c8345ce5832cc51de712c05a8b239873d7f092db3ae5566a761b498"
)
EXPECTED_ISO_SOURCE_SHA256 = (
    "d6e97c4ff2395b812b65da5ab480e937c6b365e6e6e8b0288ddf48b8fd398fb1"
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


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load helper module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


baseline = load_module(
    "collect_windows_count_baseline",
    UPSTREAM_DIR / "collect_windows_cli_baseline.py",
)
archive_probe = load_module(
    "collect_windows_count_archive_probe",
    UPSTREAM_DIR / "probe_archive_iteration_boundary_harness.py",
)
resource_probe = load_module(
    "collect_windows_count_resource_probe",
    UPSTREAM_DIR / "probe_scan_option_boundaries.py",
)
HarnessError = baseline.BaselineError


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_hash(value: Any) -> str:
    return sha256_bytes(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    )


def read_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HarnessError(f"invalid JSON: {path}") from error
    if not isinstance(value, dict):
        raise HarnessError(f"JSON root must be an object: {path}")
    return value, raw


def validate_build_manifest(
    manifest: dict[str, Any],
    binary: Path,
) -> None:
    identity = manifest.get("baseline", {})
    qt = manifest.get("qt", {})
    build = manifest.get("build", {})
    adaptation = build.get("platform_adaptation", {})
    sources = manifest.get("source_hashes", {})
    harness = sources.get("harness", {})
    artifact = manifest.get("artifact", {})
    replacements = harness.get("database_path_replacements")
    observed_replacements = {}
    if isinstance(replacements, list):
        for replacement in replacements:
            if not isinstance(replacement, dict):
                continue
            observed_replacements[replacement.get("from")] = (
                replacement.get("to"),
                replacement.get("count"),
            )
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
        or harness.get("path")
        != (
            "tools/upstream/"
            "archive_iteration_boundary_harness_main.cpp"
        )
        or harness.get("original_sha256")
        != EXPECTED_HARNESS_SOURCE_SHA256
        or harness.get("original_sha256")
        != baseline.sha256_file(HARNESS_SOURCE)
        or harness.get("adapted_sha256")
        != EXPECTED_ADAPTED_SOURCE_SHA256
        or observed_replacements != EXPECTED_REPLACEMENTS
        or not binary.is_file()
        or artifact.get("filename") != binary.name
        or artifact.get("size") != binary.stat().st_size
        or artifact.get("sha256") != baseline.sha256_file(binary)
    ):
        raise HarnessError(
            "Windows archive-iteration build identity differs"
        )


def validate_source_contracts(
    source_dir: Path,
    resource_report: dict[str, Any],
) -> dict[str, Any]:
    paths = {
        "xscanengine": source_dir / "XScanEngine/xscanengine.cpp",
        "iso9660": source_dir / "XArchive/xiso9660.cpp",
        "console": source_dir / "src/console/main_console.cpp",
        "pe": source_dir / "Formats/exec/xpe.cpp",
    }
    hashes = {
        name: baseline.sha256_file(path)
        for name, path in paths.items()
    }
    qmake = resource_report.get("observations", {}).get(
        "linux-qt5-qmake", {}
    )
    if (
        hashes["xscanengine"] != EXPECTED_XSCANENGINE_SHA256
        or hashes["iso9660"] != EXPECTED_ISO_SOURCE_SHA256
        or hashes["xscanengine"]
        != qmake.get("resource_source_sha256")
        or hashes["console"] != qmake.get("console_source_sha256")
        or hashes["pe"] != qmake.get("pe_source_sha256")
    ):
        raise HarnessError("Windows count-boundary source differs")
    text = paths["xscanengine"].read_text(encoding="utf-8")
    required = {
        "aggressive_archive_limit": "nLimit = 100000;",
        "archive_hard_guard": "(i < 100000)",
        "archive_post_increment_check": (
            "if (nCurrentIndex > nLimit) {"
        ),
        "default_resource_limit": "qint32 nLimit = 20;",
        "aggressive_resource_limit": "nLimit = 2000;",
        "inclusive_resource_limit": (
            "if (nCurrentIndex <= nLimit)"
        ),
    }
    counts = {
        name: text.count(token) for name, token in required.items()
    }
    if any(count < 1 for count in counts.values()):
        raise HarnessError("Windows count-boundary source token differs")
    return {
        "paths": {
            name: path.relative_to(source_dir).as_posix()
            for name, path in paths.items()
        },
        "sha256": hashes,
        "required_pattern_counts": counts,
    }


def validate_archive_reference(
    report: dict[str, Any],
    manifest_sha256: str,
) -> dict[str, dict[str, Any]]:
    if (
        report.get("schema_version") != 1
        or report.get("passed") is not True
        or report.get("failures") != []
        or report.get("upstream_commit") != baseline.UPSTREAM_COMMIT
        or report.get("xscanengine_commit")
        != archive_probe.EXPECTED_XSCANENGINE_COMMIT
        or report.get("corpus_manifest_sha256")
        != manifest_sha256
        or report.get("source_contract", {}).get("sha256")
        != EXPECTED_XSCANENGINE_SHA256
        or len(report.get("cases", [])) != 3
        or not all(report.get("assertions", {}).values())
    ):
        raise HarnessError("Linux archive count reference differs")
    return {
        case["sample"]: case["harness"]
        for case in report["cases"]
    }


def decode_resource_reference(
    report: dict[str, Any],
    manifest_sha256: str,
) -> dict[str, dict[str, Any]]:
    observations = report.get("observations", {}).get(
        "linux-qt5-qmake", {}
    )
    cases = observations.get("cases")
    artifacts = report.get("raw_artifacts")
    if (
        report.get("schema_version") != 1
        or report.get("passed") is not True
        or report.get("failures") != []
        or report.get("upstream_commit") != baseline.UPSTREAM_COMMIT
        or report.get("generator")
        != "tools/upstream/probe_scan_option_boundaries.py"
        or report.get("generator_sha256")
        != baseline.sha256_file(
            UPSTREAM_DIR / "probe_scan_option_boundaries.py"
        )
        or report.get("fixture_manifest", {}).get("sha256")
        != manifest_sha256
        or not isinstance(cases, dict)
        or len(cases) != 8
        or not isinstance(artifacts, dict)
        or not all(report.get("facts", {}).values())
    ):
        raise HarnessError("Linux resource count reference differs")
    result = {}
    for name, case in cases.items():
        stream_hash = case["stdout"]["artifact_sha256"]
        artifact = artifacts.get(stream_hash, {})
        if artifact.get("encoding") != "zlib+base64":
            raise HarnessError("resource reference encoding differs")
        try:
            raw = zlib.decompress(
                base64.b64decode(artifact["base64"], validate=True)
            )
            document = resource_probe.strict_json(raw)
        except (KeyError, ValueError, zlib.error) as error:
            raise HarnessError(
                "resource reference artifact differs"
            ) from error
        if (
            sha256_bytes(raw) != stream_hash
            or len(raw) != artifact.get("bytes")
            or resource_probe.summarize_document(document)
            != case.get("summary")
        ):
            raise HarnessError("resource reference content differs")
        result[name] = {
            "document": document,
            "document_sha256": canonical_hash(document),
            "raw_sha256": stream_hash,
            "summary": case["summary"],
        }
    return result


def observe(
    executable: Path,
    arguments: list[str],
    *,
    source_dir: Path,
    qt_dir: Path,
    timeout_seconds: int,
    extra_environment: dict[str, str] | None = None,
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
    if extra_environment:
        environment.update(extra_environment)
    process = subprocess.run(
        [executable.name, *arguments],
        executable=str(executable),
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


def archive_projection(document: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "aggressive_scan",
        "debug_record_count",
        "error_count",
        "handler_count",
        "node_count",
        "pdf_node_count",
        "pd_stopped",
        "record_count",
        "stream_node_count",
    )
    projection = {field: document.get(field) for field in fields}
    for timing in (
        "elapsed_ms",
        "scan_result_time_ms",
        "peak_rss_before_kib",
        "peak_rss_after_kib",
    ):
        value = document.get(timing)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or value < 0
        ):
            raise HarnessError(f"invalid archive metric: {timing}")
    if (
        document["peak_rss_before_kib"] <= 0
        or document["peak_rss_after_kib"]
        < document["peak_rss_before_kib"]
    ):
        raise HarnessError("invalid Windows archive peak RSS")
    return projection


def resource_arguments(
    case: Any,
    fixture_dir: Path,
) -> list[str]:
    return [
        "--json",
        *case.flags,
        "--database",
        str(fixture_dir / "database"),
        "--extradatabase",
        str(fixture_dir / "extra"),
        "--customdatabase",
        str(fixture_dir / "custom"),
        str(fixture_dir / "input" / case.sample),
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--harness", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--qt-dir", type=Path, required=True)
    parser.add_argument("--archive-fixture-dir", type=Path, required=True)
    parser.add_argument("--resource-fixture-dir", type=Path, required=True)
    parser.add_argument("--build-manifest", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--archive-timeout-seconds", type=int, default=30)
    parser.add_argument("--resource-timeout-seconds", type=int, default=180)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if os.name != "nt":
        raise HarnessError(
            "native Windows count-boundary collector requires Windows"
        )
    if args.repetitions < 2 or args.repetitions > 10:
        raise HarnessError("repetitions must be in 2..10")
    if (
        args.archive_timeout_seconds < 1
        or args.archive_timeout_seconds > 3600
        or args.resource_timeout_seconds < 1
        or args.resource_timeout_seconds > 3600
    ):
        raise HarnessError("timeout must be in 1..3600")

    harness = args.harness.resolve(strict=True)
    source_dir = args.source_dir.resolve(strict=True)
    qt_dir = args.qt_dir.resolve(strict=True)
    archive_fixture_dir = args.archive_fixture_dir.resolve(strict=True)
    resource_fixture_dir = args.resource_fixture_dir.resolve(strict=True)
    raw_dir = args.raw_dir.resolve()
    raw_dir.mkdir(parents=True, exist_ok=True)
    temp_block = raw_dir / "qtemporaryfile-failure-path"
    temp_block.write_bytes(b"not a directory\n")
    if not temp_block.is_file():
        raise HarnessError("temporary failure path is not a file")

    source_identity = baseline.validate_source(source_dir)
    qt_identity = baseline.validate_qt(qt_dir)
    cli = source_dir / "build/release/diec.exe"
    if baseline.sha256_file(cli) != EXPECTED_CLI_SHA256:
        raise HarnessError("Windows release CLI differs")
    build_manifest, build_raw = read_json(
        args.build_manifest.resolve(strict=True)
    )
    validate_build_manifest(build_manifest, harness)

    archive_corpus, archive_manifest_raw = (
        archive_probe.load_and_verify_corpus(
            archive_fixture_dir,
            ARCHIVE_MANIFEST,
        )
    )
    archive_manifest_sha256 = sha256_bytes(archive_manifest_raw)
    resource_manifest, resource_manifest_sha256 = (
        resource_probe.load_fixture(
            resource_fixture_dir,
            RESOURCE_MANIFEST,
        )
    )
    linux_archive, linux_archive_raw = read_json(
        LINUX_ARCHIVE_REPORT
    )
    archive_reference = validate_archive_reference(
        linux_archive,
        archive_manifest_sha256,
    )
    linux_resource, linux_resource_raw = read_json(
        LINUX_RESOURCE_REPORT
    )
    resource_reference = decode_resource_reference(
        linux_resource,
        resource_manifest_sha256,
    )
    source_contract = validate_source_contracts(
        source_dir,
        linux_resource,
    )

    archive_cases = {}
    for sample in archive_corpus["samples"]:
        sample_name = sample["name"]
        reference_projection = archive_projection(
            archive_reference[sample_name]
        )
        runs = []
        projections = []
        for repetition in range(args.repetitions):
            observation = observe(
                harness,
                [str(archive_fixture_dir / sample_name)],
                source_dir=source_dir,
                qt_dir=qt_dir,
                timeout_seconds=args.archive_timeout_seconds,
                extra_environment={
                    "TEMP": str(temp_block),
                    "TMP": str(temp_block),
                },
            )
            base = f"archive.{sample_name}.run-{repetition + 1}"
            stdout_name = base + ".stdout"
            stderr_name = base + ".stderr"
            (raw_dir / stdout_name).write_bytes(observation.stdout)
            (raw_dir / stderr_name).write_bytes(observation.stderr)
            if observation.exit_code != 0 or observation.stderr:
                raise HarnessError(
                    f"Windows archive boundary failed: "
                    f"{sample_name}.{repetition + 1}"
                )
            document = archive_probe.parse_json(
                observation.stdout,
                f"Windows {sample_name}",
            )
            projection = archive_projection(document)
            if projection != reference_projection:
                raise HarnessError(
                    f"Windows archive boundary differs: {sample_name}"
                )
            projections.append(projection)
            runs.append(
                {
                    **observation.summary(),
                    "raw_stdout": stdout_name,
                    "raw_stderr": stderr_name,
                    "semantic_projection": projection,
                    "metrics": {
                        field: document[field]
                        for field in (
                            "elapsed_ms",
                            "scan_result_time_ms",
                            "peak_rss_before_kib",
                            "peak_rss_after_kib",
                        )
                    },
                }
            )
        archive_cases[sample_name] = {
            "sentinel_ordinal": sample["sentinel_ordinal"],
            "runs": runs,
            "semantic_deterministic": all(
                item == projections[0] for item in projections[1:]
            ),
            "linux_qt5_semantic_equal": True,
        }

    resource_cases = {}
    for case in resource_probe.CASES:
        reference = resource_reference[case.name]
        runs = []
        for repetition in range(args.repetitions):
            observation = observe(
                cli,
                resource_arguments(case, resource_fixture_dir),
                source_dir=source_dir,
                qt_dir=qt_dir,
                timeout_seconds=args.resource_timeout_seconds,
            )
            base = f"resource.{case.name}.run-{repetition + 1}"
            stdout_name = base + ".stdout"
            stderr_name = base + ".stderr"
            (raw_dir / stdout_name).write_bytes(observation.stdout)
            (raw_dir / stderr_name).write_bytes(observation.stderr)
            if observation.exit_code != 0 or observation.stderr:
                raise HarnessError(
                    f"Windows resource boundary failed: "
                    f"{case.name}.{repetition + 1}"
                )
            document = resource_probe.strict_json(observation.stdout)
            summary = resource_probe.summarize_document(document)
            if (
                document != reference["document"]
                or summary != reference["summary"]
            ):
                raise HarnessError(
                    f"Windows resource boundary differs: {case.name}"
                )
            runs.append(
                {
                    **observation.summary(),
                    "raw_stdout": stdout_name,
                    "raw_stderr": stderr_name,
                    "document_sha256": canonical_hash(document),
                    "summary": summary,
                    "linux_qt5_document_equal": True,
                }
            )
        resource_cases[case.name] = {
            "sample": case.sample,
            "arguments": [
                "--json",
                *case.flags,
                "--database",
                "<fixture>/database",
                "--extradatabase",
                "<fixture>/extra",
                "--customdatabase",
                "<fixture>/custom",
                f"<fixture>/input/{case.sample}",
            ],
            "runs": runs,
            "raw_deterministic": (
                len({run["stdout_sha256"] for run in runs}) == 1
                and len({run["stderr_sha256"] for run in runs}) == 1
            ),
            "linux_qt5_document_sha256": reference[
                "document_sha256"
            ],
        }

    relationships = {
        "archive_all_six_runs_complete_without_errors": all(
            run["exit_code"] == 0
            and run["stderr_bytes"] == 0
            for case in archive_cases.values()
            for run in case["runs"]
        ),
        "archive_all_three_semantic_projections_are_deterministic": all(
            case["semantic_deterministic"]
            for case in archive_cases.values()
        ),
        "archive_all_three_match_linux_qt5": all(
            case["linux_qt5_semantic_equal"]
            for case in archive_cases.values()
        ),
        "archive_record_99999_is_reachable": (
            archive_cases["sentinel-099999.iso"]["runs"][0][
                "semantic_projection"
            ]["pdf_node_count"]
            == 1
        ),
        "archive_record_100000_is_reachable": (
            archive_cases["sentinel-100000.iso"]["runs"][0][
                "semantic_projection"
            ]["pdf_node_count"]
            == 1
        ),
        "archive_record_100001_is_not_reachable": (
            archive_cases["sentinel-100001.iso"]["runs"][0][
                "semantic_projection"
            ]["pdf_node_count"]
            == 0
        ),
        "resource_all_sixteen_runs_are_raw_deterministic": all(
            case["raw_deterministic"]
            for case in resource_cases.values()
        ),
        "resource_all_sixteen_documents_match_linux_qt5": all(
            run["linux_qt5_document_equal"]
            for case in resource_cases.values()
            for run in case["runs"]
        ),
        "resource_default_limit_is_inclusive_21": (
            resource_cases["recursive_pdf_22"]["runs"][0][
                "summary"
            ]["resource_count"]
            == 21
        ),
        "resource_aggressive_control_reaches_22": (
            resource_cases["recursive_aggressive_pdf_22"]["runs"][0][
                "summary"
            ]["resource_count"]
            == 22
        ),
        "resource_aggressive_limit_is_inclusive_2001": (
            resource_cases[
                "recursive_aggressive_unclassified_2002"
            ]["runs"][0]["summary"]["resource_count"]
            == 2001
        ),
        "resource_children_preserve_enumeration_order": all(
            run["summary"]["resource_offsets_strictly_increasing"]
            for name, case in resource_cases.items()
            if name
            in {
                "recursive_pdf_22",
                "recursive_aggressive_pdf_22",
                "recursive_aggressive_unclassified_2002",
            }
            for run in case["runs"]
        ),
        "fault_injection_uses_regular_file_as_temp_root": (
            temp_block.is_file() and not temp_block.is_dir()
        ),
        "source_contracts_match_fixed_linux_qt5": (
            source_contract["sha256"]["xscanengine"]
            == EXPECTED_XSCANENGINE_SHA256
            and source_contract["sha256"]["iso9660"]
            == EXPECTED_ISO_SOURCE_SHA256
        ),
    }
    if len(relationships) != 14 or not all(relationships.values()):
        raise HarnessError("Windows count-boundary relationships differ")

    execution_count = (
        len(archive_cases) + len(resource_cases)
    ) * args.repetitions
    report = {
        "schema_version": 1,
        "generator": (
            "tools/upstream/collect_windows_count_boundaries.py"
        ),
        "generator_sha256": baseline.sha256_file(Path(__file__)),
        "platform": "windows-x86_64-qt5",
        "capability": "CAP-NEST-004",
        "host": {
            "os_build": platform.version(),
            "architecture": platform.machine(),
        },
        "source": source_identity,
        "qt": qt_identity,
        "cli": {
            "path": "<source>/build/release/diec.exe",
            "sha256": EXPECTED_CLI_SHA256,
        },
        "build_manifest": {
            "sha256": sha256_bytes(build_raw),
            "identity": build_manifest,
        },
        "source_contract": source_contract,
        "archive_fixture": {
            "path": (
                "docs/research/data/"
                "archive-iteration-boundary-corpus.json"
            ),
            "sha256": archive_manifest_sha256,
            "sample_count": len(archive_corpus["samples"]),
        },
        "resource_fixture": {
            "path": (
                "docs/research/data/"
                "scan-option-boundary-fixture.json"
            ),
            "sha256": resource_manifest_sha256,
            "entry_count": len(resource_manifest["entries"]),
        },
        "linux_qt5_references": {
            "archive": {
                "path": (
                    "docs/research/data/"
                    "archive-iteration-boundary-engine-qt5.json"
                ),
                "sha256": sha256_bytes(linux_archive_raw),
            },
            "resource": {
                "path": (
                    "docs/research/data/"
                    "scan-option-boundaries-linux-qt5.json"
                ),
                "sha256": sha256_bytes(linux_resource_raw),
            },
        },
        "fault_injection": {
            "placeholder_declared_size": 0x1000000,
            "temporary_path_kind": "regular-file-not-directory",
            "environment_variables": ["TEMP", "TMP"],
            "purpose": (
                "force placeholder QTemporaryFile creation to fail "
                "before unpack/child scan while preserving archive "
                "record iteration"
            ),
        },
        "repetitions": args.repetitions,
        "archive_case_count": len(archive_cases),
        "resource_case_count": len(resource_cases),
        "execution_count": execution_count,
        "case_observation_count": execution_count,
        "archive_cases": archive_cases,
        "resource_cases": resource_cases,
        "relationships": relationships,
        "failures": [],
        "passed": True,
        "raw_artifacts": {
            "storage": "untracked external directory selected by --raw-dir",
            "stdout_and_stderr_retained_for_every_execution": True,
            "temporary_failure_file_retained": True,
        },
        "limitations": [
            "archive timing and peak RSS are descriptive host observations rather than cross-platform goldens",
            "the regular-file temp root is controlled fault injection and not a normal writable-temp performance profile",
            "depth and cumulative expanded-byte limits require the separate CAP-NEST-009 harness",
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
