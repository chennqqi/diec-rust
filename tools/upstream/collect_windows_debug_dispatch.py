#!/usr/bin/env python3
"""Collect the native-Windows Qt5 debug-data dispatch boundary."""

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
UPSTREAM_DIR = ROOT / "tools/upstream"
DATA_DIR = ROOT / "docs/research/data"
BUILDER = UPSTREAM_DIR / "build_windows_debug_dispatch_harness.ps1"
HARNESS_SOURCE = UPSTREAM_DIR / "debug_dispatch_harness_main.cpp"
LINUX_REPORT = DATA_DIR / "debug-dispatch-engine-qt5.json"
FIXTURE_MANIFEST = DATA_DIR / "debug-dispatch-fixture.json"
EXPECTED_MAKEFILE_SHA256 = (
    "e6f7710cd32be5050e10234f3282d2512b58d28170d5de14f96c30478ac03725"
)
EXPECTED_MAIN_OBJECT_SHA256 = (
    "ff736a313b4d8d53747a7b113fff5a310c31c4218555ffbf1570537af15dd6be"
)
EXPECTED_DIE_SCRIPT_OBJECT_SHA256 = (
    "f74138c8acbf6a7427c90761c7bfbf7715c3dfda6e1c4def3715d348ac159a19"
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
        3,
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
    "collect_windows_debug_dispatch_baseline",
    UPSTREAM_DIR / "collect_windows_cli_baseline.py",
)
linux_probe = load_module(
    "collect_windows_debug_dispatch_linux_probe",
    UPSTREAM_DIR / "probe_debug_dispatch_harness.py",
)
HarnessError = baseline.BaselineError


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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
            raise HarnessError("invalid debug source replacement record")
        source = replacement["from"]
        target = replacement["to"]
        count = replacement["count"]
        expected = EXPECTED_REPLACEMENTS.get(source)
        if (
            expected != (target, count)
            or text.count(source) != count
            or source in observed
        ):
            raise HarnessError("debug source replacement differs")
        text = text.replace(source, target)
        observed[source] = (target, count)
    if observed != EXPECTED_REPLACEMENTS:
        raise HarnessError("debug source replacement inventory differs")
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
    bridge = build.get("access_bridge", {})
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
        or build.get("original_die_script_object_sha256")
        != EXPECTED_DIE_SCRIPT_OBJECT_SHA256
        or build.get("replaced_object") != "release/main_console.obj"
        or build.get("engine_objects_modified") is not False
        or build.get("database_root")
        != "<working-directory>/Detect-It-Easy"
        or build.get("runtime_working_directory_contract")
        != "verified-source-root"
        or bridge.get("kind") != "msvc-alternatename"
        or not str(bridge.get("from_public_declaration", "")).startswith(
            "?processDetect@DiE_Script@@QEAAX"
        )
        or not str(bridge.get("to_private_definition", "")).startswith(
            "?processDetect@DiE_Script@@AEAAX"
        )
        or sources.get("builder") != baseline.sha256_file(BUILDER)
        or harness.get("path")
        != "tools/upstream/debug_dispatch_harness_main.cpp"
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
        raise HarnessError("Windows debug-dispatch build identity differs")


def validate_linux_reference(
    report: dict[str, Any],
    fixture_sha256: str,
) -> tuple[dict[str, Any], dict[str, bool]]:
    document = report.get("harness_output")
    relationships = report.get("relationships")
    if (
        report.get("schema_version") != 1
        or report.get("generator")
        != "tools/upstream/probe_debug_dispatch_harness.py"
        or report.get("generator_sha256")
        != baseline.sha256_file(
            UPSTREAM_DIR / "probe_debug_dispatch_harness.py"
        )
        or report.get("upstream_commit") != baseline.UPSTREAM_COMMIT
        or report.get("rules_commit") != baseline.RULES_COMMIT
        or report.get("platform") != "linux-amd64-qt5"
        or report.get("capability") != "CAP-NEST-007"
        or report.get("fixture", {}).get("manifest_sha256")
        != fixture_sha256
        or not isinstance(document, dict)
        or not isinstance(relationships, dict)
        or len(relationships) != 9
        or not all(relationships.values())
    ):
        raise HarnessError("Linux debug-dispatch reference differs")
    observed = linux_probe.validate(copy.deepcopy(document))
    if observed != relationships:
        raise HarnessError("Linux debug-dispatch relationships differ")
    return document, relationships


def observe(
    binary: Path,
    qt_dir: Path,
    source_dir: Path,
    fixture_dir: Path,
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
        [binary.name, fixture_dir.as_posix()],
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


def normalize_signature_paths(
    document: dict[str, Any],
    source_dir: Path,
) -> dict[str, Any]:
    result = copy.deepcopy(document)
    windows_prefix = (source_dir / "Detect-It-Easy").as_posix()
    linux_prefix = "/opt/die-source/Detect-It-Easy"
    path_count = 0
    for scan_name in ("public_recursive_scan", "direct_debug_scan"):
        records = result.get(scan_name, {}).get("records", [])
        if not isinstance(records, list):
            raise HarnessError(f"invalid records: {scan_name}")
        for record in records:
            value = record.get("signature_path")
            if not isinstance(value, str):
                raise HarnessError("debug signature path is not a string")
            normalized = value.replace("\\", "/")
            marker = windows_prefix + "/"
            if not normalized.casefold().startswith(marker.casefold()):
                raise HarnessError("debug signature path escaped source root")
            record["signature_path"] = (
                linux_prefix + normalized[len(windows_prefix) :]
            )
            path_count += 1
    if path_count != 3:
        raise HarnessError("debug signature-path count differs")
    return result


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
            "native Windows debug-dispatch collector requires Windows"
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
    _, fixture_sha256 = linux_probe.verify_fixture(
        fixture_dir,
        FIXTURE_MANIFEST,
    )
    linux_report, linux_raw = read_json(LINUX_REPORT)
    linux_document, linux_relationships = validate_linux_reference(
        linux_report,
        fixture_sha256,
    )

    runs = []
    normalized_documents = []
    relationship_runs = []
    for index in range(args.repetitions):
        observation = observe(
            binary,
            qt_dir,
            source_dir,
            fixture_dir,
            args.timeout_seconds,
        )
        stdout_name = f"run-{index + 1}.stdout"
        stderr_name = f"run-{index + 1}.stderr"
        (raw_dir / stdout_name).write_bytes(observation.stdout)
        (raw_dir / stderr_name).write_bytes(observation.stderr)
        if observation.exit_code != 0 or observation.stderr:
            raise HarnessError(
                f"Windows debug-dispatch run {index + 1} failed"
            )
        try:
            document = json.loads(observation.stdout)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise HarnessError(
                "Windows debug-dispatch stdout is not JSON"
            ) from error
        if not isinstance(document, dict):
            raise HarnessError("Windows debug output is not an object")
        relationships = linux_probe.validate(copy.deepcopy(document))
        normalized = normalize_signature_paths(document, source_dir)
        runs.append(
            {
                **observation.summary(),
                "raw_stdout": stdout_name,
                "raw_stderr": stderr_name,
            }
        )
        normalized_documents.append(normalized)
        relationship_runs.append(relationships)

    normalized_equal = all(
        item == normalized_documents[0]
        for item in normalized_documents[1:]
    )
    relationships_equal = all(
        item == linux_relationships for item in relationship_runs
    )
    linux_equal = normalized_documents[0] == linux_document
    raw_equal = (
        len({run["stdout_sha256"] for run in runs}) == 1
        and len({run["stderr_sha256"] for run in runs}) == 1
    )
    if not normalized_equal or not relationships_equal or not linux_equal:
        raise HarnessError("Windows debug-dispatch semantics differ")

    report = {
        "schema_version": 1,
        "generator": (
            "tools/upstream/collect_windows_debug_dispatch.py"
        ),
        "generator_sha256": baseline.sha256_file(Path(__file__)),
        "platform": "windows-x86_64-qt5",
        "capability": "CAP-NEST-007",
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
            "path": "docs/research/data/debug-dispatch-fixture.json",
            "sha256": fixture_sha256,
        },
        "linux_qt5_reference": {
            "path": "docs/research/data/debug-dispatch-engine-qt5.json",
            "sha256": sha256_bytes(linux_raw),
        },
        "repetitions": args.repetitions,
        "execution_count": args.repetitions,
        "semantic_case_count_per_execution": 3,
        "case_observation_count": 3 * args.repetitions,
        "runs": runs,
        "raw_outputs_equal": raw_equal,
        "normalized_outputs_equal": normalized_equal,
        "relationships": linux_relationships,
        "relationships_equal": relationships_equal,
        "harness_output": normalized_documents[0],
        "linux_qt5_semantic_document_equal": linux_equal,
        "normalization": {
            "operation": (
                "replace only three verified signature_path prefixes "
                "under the fixed source/Detect-It-Easy root with the "
                "Linux reference root"
            ),
            "not_performed": [
                "record or field removal/reordering",
                "filetype, rule, result, or error text rewriting",
                "raw stdout/stderr hash rewriting",
            ],
        },
        "raw_artifacts": {
            "storage": "untracked external directory selected by --raw-dir",
            "stdout_and_stderr_retained_for_every_execution": True,
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
