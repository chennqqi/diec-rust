#!/usr/bin/env python3
"""Collect native-Windows Qt5 private signature-path behavior."""

from __future__ import annotations

import argparse
import copy
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
BASELINE_SCRIPT = ROOT / "tools/upstream/collect_windows_cli_baseline.py"
LINUX_PROBE = ROOT / "tools/upstream/probe_signature_path_harness.py"
BUILDER = (
    ROOT / "tools/upstream/build_windows_signature_path_harness.ps1"
)
HARNESS_SOURCE = ROOT / "tools/upstream/signature_path_harness_main.cpp"
FIXTURE_GENERATOR = (
    ROOT / "tools/corpus/generate_signature_path_fixture.py"
)
EXPECTED_MAKEFILE_SHA256 = (
    "e6f7710cd32be5050e10234f3282d2512b58d28170d5de14f96c30478ac03725"
)
EXPECTED_MAIN_OBJECT_SHA256 = (
    "ff736a313b4d8d53747a7b113fff5a310c31c4218555ffbf1570537af15dd6be"
)
EXPECTED_DIE_SCRIPT_OBJECT_SHA256 = (
    "f74138c8acbf6a7427c90761c7bfbf7715c3dfda6e1c4def3715d348ac159a19"
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
    "collect_windows_cli_baseline_signature_path_helper",
    BASELINE_SCRIPT,
)
linux_probe = load_module(
    "probe_signature_path_windows_reference",
    LINUX_PROBE,
)
HarnessError = baseline.BaselineError


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise HarnessError(f"JSON root must be an object: {path}")
    return value, raw


def validate_build_manifest(
    manifest: dict[str, Any],
    binary: Path,
) -> None:
    baseline_identity = manifest.get("baseline", {})
    qt = manifest.get("qt", {})
    build = manifest.get("build", {})
    source_hashes = manifest.get("source_hashes", {})
    artifact = manifest.get("artifact", {})
    alias = build.get("msvc_access_symbol_alias", {})
    if (
        manifest.get("schema_version") != 1
        or baseline_identity.get("commit") != baseline.UPSTREAM_COMMIT
        or baseline_identity.get("rules_commit") != baseline.RULES_COMMIT
        or baseline_identity.get("recursive_submodule_count") != 58
        or baseline_identity.get("cli_sha256")
        != (
            "e8579a6ed0d2536ea14af154bcbeeaaea6967c0c7559a595"
            "fb3fe52206ac635e"
        )
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
        or build.get("original_die_script_object_sha256")
        != EXPECTED_DIE_SCRIPT_OBJECT_SHA256
        or build.get("replaced_object") != "release/main_console.obj"
        or build.get("harness_object")
        != "release/signature_path_harness_main.obj"
        or source_hashes.get("builder")
        != baseline.sha256_file(BUILDER)
        or source_hashes.get("shared_harness")
        != baseline.sha256_file(HARNESS_SOURCE)
        or artifact.get("filename") != binary.name
        or artifact.get("size") != binary.stat().st_size
        or artifact.get("sha256") != baseline.sha256_file(binary)
        or not str(alias.get("from_public_declaration", "")).startswith(
            "?processDetect@DiE_Script@@QEAAX"
        )
        or not str(alias.get("to_private_definition", "")).startswith(
            "?processDetect@DiE_Script@@AEAAX"
        )
    ):
        raise HarnessError("Windows signature-path build identity differs")


def validate_linux_reference(
    report: dict[str, Any],
    fixture_sha256: str,
) -> dict[str, Any]:
    if (
        report.get("schema_version") != 1
        or report.get("generator")
        != "tools/upstream/probe_signature_path_harness.py"
        or report.get("generator_sha256")
        != baseline.sha256_file(LINUX_PROBE)
        or report.get("upstream_commit") != baseline.UPSTREAM_COMMIT
        or report.get("formats_commit") != linux_probe.FORMATS_COMMIT
        or report.get("xscanengine_commit")
        != linux_probe.XSCANENGINE_COMMIT
        or report.get("die_script_commit")
        != linux_probe.DIE_SCRIPT_COMMIT
        or report.get("platform") != "linux-amd64-qt5"
        or report.get("capability") != "CAP-RULE-007"
        or report.get("fixture", {}).get("manifest_sha256")
        != fixture_sha256
        or report.get("harness", {}).get("source_sha256")
        != baseline.sha256_file(HARNESS_SOURCE)
    ):
        raise HarnessError("Linux signature-path reference differs")
    document = copy.deepcopy(report.get("harness_output"))
    if not isinstance(document, dict):
        raise HarnessError("Linux signature-path output is missing")
    relationships = linux_probe.validate(document)
    if (
        relationships != report.get("relationships")
        or len(relationships) != 11
        or not all(relationships.values())
    ):
        raise HarnessError("Linux signature-path relationships differ")
    return document


def replace_fixture_paths(value: Any, fixture_dir: Path) -> Any:
    if isinstance(value, dict):
        return {
            key: replace_fixture_paths(item, fixture_dir)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            replace_fixture_paths(item, fixture_dir) for item in value
        ]
    if not isinstance(value, str):
        return value

    normalized = value.replace("\\", "/")
    prefix = str(fixture_dir).replace("\\", "/").rstrip("/")
    if normalized.casefold() == prefix.casefold():
        return "/fixture"
    marker = prefix + "/"
    if normalized.casefold().startswith(marker.casefold()):
        return "/fixture/" + normalized[len(marker) :]
    return value


def observe(
    binary: Path,
    qt_dir: Path,
    working_dir: Path,
    fixture_dir: Path,
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
    process = subprocess.run(
        [binary.name, str(fixture_dir)],
        executable=str(binary),
        cwd=working_dir,
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


def parse_and_normalize(
    stdout: bytes,
    fixture_dir: Path,
) -> dict[str, Any]:
    try:
        document = json.loads(stdout)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HarnessError("Windows harness stdout is not JSON") from error
    normalized = replace_fixture_paths(document, fixture_dir)
    if not isinstance(normalized, dict):
        raise HarnessError("normalized Windows output is not an object")
    linux_probe.validate(copy.deepcopy(normalized))
    return normalized


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--qt-dir", type=Path, required=True)
    parser.add_argument("--fixture-dir", type=Path, required=True)
    parser.add_argument("--working-dir", type=Path, required=True)
    parser.add_argument("--build-manifest", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument(
        "--fixture-manifest",
        type=Path,
        default=(
            ROOT / "docs/research/data/signature-path-fixture.json"
        ),
    )
    parser.add_argument(
        "--linux-reference",
        type=Path,
        default=(
            ROOT / "docs/research/data/signature-path-engine-qt5.json"
        ),
    )
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if os.name != "nt":
        raise HarnessError(
            "native Windows signature-path collector requires Windows"
        )
    if args.repetitions < 2 or args.repetitions > 20:
        raise HarnessError("repetitions must be in 2..20")
    if args.timeout_seconds < 1 or args.timeout_seconds > 3600:
        raise HarnessError("timeout-seconds must be in 1..3600")

    source_dir = args.source_dir.resolve(strict=True)
    qt_dir = args.qt_dir.resolve(strict=True)
    binary = args.binary.resolve(strict=True)
    fixture_dir = args.fixture_dir.resolve(strict=True)
    working_dir = args.working_dir.resolve(strict=True)
    raw_dir = args.raw_dir.resolve()
    raw_dir.mkdir(parents=True, exist_ok=True)

    source_identity = baseline.validate_source(source_dir)
    qt_identity = baseline.validate_qt(qt_dir)
    build_path = args.build_manifest.resolve(strict=True)
    build_manifest, build_raw = read_json(build_path)
    validate_build_manifest(build_manifest, binary)
    _, fixture_sha256 = linux_probe.verify_fixture(
        fixture_dir,
        args.fixture_manifest.resolve(strict=True),
    )
    linux_path = args.linux_reference.resolve(strict=True)
    linux_reference, linux_raw = read_json(linux_path)
    linux_document = validate_linux_reference(
        linux_reference,
        fixture_sha256,
    )

    runs = []
    normalized_runs = []
    for index in range(args.repetitions):
        observation = observe(
            binary,
            qt_dir,
            working_dir,
            fixture_dir,
            args.timeout_seconds,
        )
        (raw_dir / f"run-{index + 1}.stdout").write_bytes(
            observation.stdout
        )
        (raw_dir / f"run-{index + 1}.stderr").write_bytes(
            observation.stderr
        )
        if observation.exit_code != 0:
            raise HarnessError(
                f"Windows harness run {index + 1} exited "
                f"{observation.exit_code}"
            )
        if observation.stderr:
            raise HarnessError(
                f"Windows harness run {index + 1} wrote stderr"
            )
        runs.append(observation.summary())
        normalized_runs.append(
            parse_and_normalize(observation.stdout, fixture_dir)
        )

    raw_outputs_equal = (
        len({run["stdout_sha256"] for run in runs}) == 1
        and len({run["stderr_sha256"] for run in runs}) == 1
    )
    normalized_outputs_equal = all(
        item == normalized_runs[0] for item in normalized_runs[1:]
    )
    if not raw_outputs_equal or not normalized_outputs_equal:
        raise HarnessError("Windows signature-path runs differ")

    windows_document = normalized_runs[0]
    relationships = linux_probe.validate(copy.deepcopy(windows_document))
    semantic_equal = windows_document == linux_document
    if relationships != linux_reference["relationships"]:
        raise HarnessError("Windows/Linux relationship maps differ")
    if not semantic_equal:
        raise HarnessError("Windows/Linux normalized documents differ")

    report = {
        "schema_version": 1,
        "generator": (
            "tools/upstream/collect_windows_signature_path_harness.py"
        ),
        "generator_sha256": baseline.sha256_file(Path(__file__)),
        "platform": "windows-x86_64-qt5",
        "capability": "CAP-RULE-007",
        "host": {
            "os_build": platform.version(),
            "architecture": platform.machine(),
        },
        "source": source_identity,
        "qt": qt_identity,
        "binary": {
            "filename": binary.name,
            "size": binary.stat().st_size,
            "sha256": baseline.sha256_file(binary),
        },
        "build_manifest": {
            "sha256": sha256_bytes(build_raw),
            "identity": build_manifest,
        },
        "fixture": {
            "manifest": (
                "docs/research/data/signature-path-fixture.json"
            ),
            "manifest_sha256": fixture_sha256,
            "generator": (
                "tools/corpus/generate_signature_path_fixture.py"
            ),
            "generator_sha256": baseline.sha256_file(
                FIXTURE_GENERATOR
            ),
        },
        "linux_qt5_reference": {
            "path": (
                "docs/research/data/signature-path-engine-qt5.json"
            ),
            "sha256": sha256_bytes(linux_raw),
        },
        "repetitions": args.repetitions,
        "execution_count": args.repetitions,
        "case_observation_count": (
            args.repetitions * windows_document["case_count"]
        ),
        "runs": runs,
        "raw_outputs_equal": raw_outputs_equal,
        "normalized_outputs_equal": normalized_outputs_equal,
        "relationships": relationships,
        "harness_output": windows_document,
        "linux_qt5_comparison": {
            "semantic_document_equal": semantic_equal,
            "relationships_equal": (
                relationships == linux_reference["relationships"]
            ),
            "path_normalization_only": True,
            "platform_difference_classification": (
                "none_observed_after_verified_fixture_prefix_mapping"
            ),
        },
        "access_method": {
            "translation_unit": (
                "private-to-public macro in the shared research harness"
            ),
            "msvc_abi": (
                "linker alternatename from public access-mangled "
                "declaration to the private symbol in fixed die_script.obj"
            ),
            "engine_objects_modified": False,
        },
        "normalization": {
            "operations": [
                (
                    "replace only the verified fixture-root prefix in "
                    "structured strings with /fixture"
                ),
                (
                    "convert separators only inside a replaced "
                    "fixture-root string"
                ),
            ],
            "not_performed": [
                "case or record removal/reordering",
                "path canonicalization or dot-segment cleanup",
                "case folding or basename substitution",
                "raw stdout/stderr hash rewriting",
            ],
        },
        "raw_artifacts": {
            "storage": (
                "untracked external directory selected by --raw-dir"
            ),
            "files": [
                f"run-{index}.{stream}"
                for index in range(1, args.repetitions + 1)
                for stream in ("stdout", "stderr")
            ],
        },
        "failures": [],
        "passed": True,
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
