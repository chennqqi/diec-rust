#!/usr/bin/env python3
"""Collect the native-Windows Qt5 DIE engine-contract matrix."""

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
SHARED_HELPER = ROOT / "tools/upstream/compare_cli_oracles.py"
FIXTURE_PROBE = ROOT / "tools/upstream/probe_rule_orchestration.py"
LINUX_PROBE = ROOT / "tools/upstream/probe_engine_contract.py"
SHARED_HARNESS = ROOT / "tools/upstream/engine_contract_harness_main.cpp"
WINDOWS_BUILDER = (
    ROOT / "tools/upstream/build_windows_engine_contract_harness.ps1"
)
FIXTURE_GENERATOR = (
    ROOT / "tools/corpus/generate_rule_orchestration_fixture.py"
)
SOURCE_PATHS = (
    "XScanEngine/xscanengine.h",
    "XScanEngine/xscanengine.cpp",
    "die_script/die_script.h",
    "die_script/die_script.cpp",
    "Formats/xbinary.cpp",
    "Formats/subdevice.cpp",
    "Formats/xbinary.h",
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
    "collect_windows_cli_baseline_engine_contract_helper",
    BASELINE_SCRIPT,
)
shared = load_module(
    "compare_cli_oracles_windows_engine_contract_helper",
    SHARED_HELPER,
)
fixture_probe = load_module("probe_rule_orchestration", FIXTURE_PROBE)
linux_probe = load_module(
    "probe_engine_contract_windows_reference",
    LINUX_PROBE,
)
HarnessError = baseline.BaselineError


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise HarnessError(f"JSON document is not an object: {path}")
    return value, raw


def validate_build_manifest(
    build: dict[str, Any],
    binary: Path,
) -> None:
    expected_baseline = {
        "repository": "https://github.com/horsicq/DIE-engine",
        "commit": baseline.UPSTREAM_COMMIT,
        "recursive_submodule_count": baseline.EXPECTED_SUBMODULE_COUNT,
        "rules_commit": baseline.RULES_COMMIT,
        "cli_sha256": (
            "e8579a6ed0d2536ea14af154bcbeeaaea6967c0c7559a595"
            "fb3fe52206ac635e"
        ),
    }
    expected_sources = {
        "builder": baseline.sha256_file(WINDOWS_BUILDER),
        "shared_harness": baseline.sha256_file(SHARED_HARNESS),
    }
    if build.get("schema_version") != 1:
        raise HarnessError("unsupported Windows harness build manifest")
    if build.get("baseline") != expected_baseline:
        raise HarnessError("Windows harness build baseline differs")
    if build.get("source_hashes") != expected_sources:
        raise HarnessError("Windows harness source hashes differ")
    build_identity = build.get("build")
    if not isinstance(build_identity, dict):
        raise HarnessError("Windows harness build identity is missing")
    if (
        build_identity.get("target_architecture") != "amd64"
        or build_identity.get("host_architecture") != "amd64"
        or build_identity.get("replaced_object")
        != "release/main_console.obj"
        or build_identity.get("harness_object")
        != "release/engine_contract_harness_main.obj"
    ):
        raise HarnessError("Windows harness build architecture differs")
    artifact = build.get("artifact")
    if not isinstance(artifact, dict):
        raise HarnessError("Windows harness build has no artifact")
    if artifact.get("filename") != binary.name:
        raise HarnessError("Windows harness artifact filename differs")
    if artifact.get("size") != binary.stat().st_size:
        raise HarnessError("Windows harness artifact size differs")
    if artifact.get("sha256") != baseline.sha256_file(binary):
        raise HarnessError("Windows harness artifact hash differs")


def validate_linux_reference(
    report: dict[str, Any],
    fixture_sha256: str,
) -> dict[str, Any]:
    expected = {
        "schema_version": 1,
        "generator": "tools/upstream/probe_engine_contract.py",
        "generator_sha256": baseline.sha256_file(LINUX_PROBE),
        "upstream_commit": baseline.UPSTREAM_COMMIT,
        "platform": "linux-amd64-qt5",
        "fixture_manifest": {
            "path": (
                "docs/research/data/rule-orchestration-fixture.json"
            ),
            "sha256": fixture_sha256,
        },
    }
    for key, value in expected.items():
        if report.get(key) != value:
            raise HarnessError(
                f"Linux engine-contract reference {key!r} differs"
            )
    harness_inputs = report.get("harness_inputs")
    if not isinstance(harness_inputs, dict):
        raise HarnessError("Linux reference has no harness inputs")
    source = harness_inputs.get("source")
    if not isinstance(source, dict) or source.get("sha256") != (
        baseline.sha256_file(SHARED_HARNESS)
    ):
        raise HarnessError("Linux reference harness hash differs")
    document = report.get("harness_output")
    if not isinstance(document, dict):
        raise HarnessError("Linux reference has no harness output")
    relationships = linux_probe.validate(copy.deepcopy(document))
    if report.get("relationships") != relationships:
        raise HarnessError("Linux reference relationships differ")
    return document


def validate_source_audit(
    source_dir: Path,
    linux_report: dict[str, Any],
) -> dict[str, Any]:
    source_audit = linux_report.get("source_audit")
    if not isinstance(source_audit, dict):
        raise HarnessError("Linux reference has no source audit")
    linux_sources = source_audit.get("sources")
    if not isinstance(linux_sources, dict):
        raise HarnessError("Linux reference has no source hashes")

    verified: dict[str, Any] = {}
    for relative in SOURCE_PATHS:
        local_path = source_dir / Path(relative)
        raw = local_path.read_bytes()
        linux_key = f"/opt/die-source/{relative}"
        expected = linux_sources.get(linux_key)
        actual = {"bytes": len(raw), "sha256": sha256_bytes(raw)}
        if expected != actual:
            raise HarnessError(
                f"Windows source differs from Linux audit: {relative}"
            )
        verified[relative] = actual

    contracts = {
        key: copy.deepcopy(value)
        for key, value in source_audit.items()
        if key != "sources"
    }
    if (
        contracts.get("public_runtime_filter_reachable") is not False
        or contracts.get(
            "public_scan_options_has_signature_file_path"
        )
        is not False
        or not all(contracts.get("device_contracts", {}).values())
        or not all(contracts.get("cancellation_contracts", {}).values())
    ):
        raise HarnessError("Linux source contract assumptions differ")
    return {
        "method": (
            "byte-identical Windows source files reuse the fixed Linux "
            "structural audit"
        ),
        "contracts": contracts,
        "sources": verified,
    }


def observe(
    binary: Path,
    qt_dir: Path,
    fixture_dir: Path,
    working_dir: Path,
    timeout_seconds: int,
) -> object:
    environment = os.environ.copy()
    environment["PATH"] = (
        str(qt_dir / "bin")
        + os.pathsep
        + environment.get("PATH", "")
    )
    result = subprocess.run(
        [str(binary), str(fixture_dir)],
        cwd=working_dir,
        env=environment,
        check=False,
        capture_output=True,
        timeout=timeout_seconds,
    )
    return shared.Observation(
        result.returncode,
        result.stdout,
        result.stderr,
    )


def replace_fixture_paths(
    value: Any,
    fixture_prefix: str,
) -> Any:
    if isinstance(value, dict):
        return {
            key: replace_fixture_paths(item, fixture_prefix)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            replace_fixture_paths(item, fixture_prefix) for item in value
        ]
    if not isinstance(value, str):
        return value

    normalized = value.replace("\\", "/")
    prefix = fixture_prefix.replace("\\", "/").rstrip("/")
    if normalized.casefold() == prefix.casefold():
        return "<fixture>"
    marker = prefix + "/"
    if normalized.casefold().startswith(marker.casefold()):
        return "<fixture>/" + normalized[len(marker) :]
    return value


def normalize_observation(
    document: dict[str, Any],
    fixture_dir: Path,
) -> dict[str, Any]:
    normalized = replace_fixture_paths(document, str(fixture_dir))
    if not isinstance(normalized, dict):
        raise HarnessError("normalized harness output is not an object")
    if normalized.get("upstream_commit") != baseline.UPSTREAM_COMMIT:
        raise HarnessError("harness upstream commit differs")
    if normalized.get("xscanengine_commit") != (
        "dfe4a419e4f491bb23688ba03c5a5bf39e34da83"
    ):
        raise HarnessError("harness XScanEngine commit differs")
    if normalized.get("die_script_commit") != (
        "5d82316c110abf0eb863b50bc679d330e05067b6"
    ):
        raise HarnessError("harness die_script commit differs")
    if normalized.get("qt_version") != "5.15.2":
        raise HarnessError("harness Qt version differs")
    return normalized


def linux_semantic_document(document: dict[str, Any]) -> dict[str, Any]:
    normalized = replace_fixture_paths(copy.deepcopy(document), "/fixture")
    if not isinstance(normalized, dict):
        raise HarnessError("Linux harness output is not an object")
    normalized.pop("qt_version", None)
    return normalized


def windows_semantic_document(
    document: dict[str, Any],
) -> dict[str, Any]:
    result = copy.deepcopy(document)
    result.pop("qt_version", None)
    return result


def compare_cases(
    windows: dict[str, Any],
    linux: dict[str, Any],
) -> list[str]:
    windows_cases = linux_probe.case_map(windows)
    linux_cases = linux_probe.case_map(linux)
    return [
        case_id
        for case_id in sorted(linux_cases)
        if windows_cases.get(case_id) != linux_cases[case_id]
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--qt-dir", type=Path, required=True)
    parser.add_argument("--fixture-dir", type=Path, required=True)
    parser.add_argument("--build-manifest", type=Path, required=True)
    parser.add_argument("--working-dir", type=Path, required=True)
    parser.add_argument(
        "--fixture-manifest",
        type=Path,
        default=(
            ROOT
            / "docs/research/data/rule-orchestration-fixture.json"
        ),
    )
    parser.add_argument(
        "--linux-reference",
        type=Path,
        default=(
            ROOT / "docs/research/data/engine-contract-linux-qt5.json"
        ),
    )
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if os.name != "nt":
        raise HarnessError("native Windows engine harness requires Windows")
    if args.repetitions < 2 or args.repetitions > 20:
        raise HarnessError("repetitions must be in 2..20")
    if args.timeout_seconds < 1 or args.timeout_seconds > 3600:
        raise HarnessError("timeout-seconds must be in 1..3600")

    binary = args.binary.resolve(strict=True)
    source_dir = args.source_dir.resolve(strict=True)
    qt_dir = args.qt_dir.resolve(strict=True)
    fixture_dir = args.fixture_dir.resolve(strict=True)
    working_dir = args.working_dir.resolve(strict=True)
    raw_dir = args.raw_dir.resolve()
    raw_dir.mkdir(parents=True, exist_ok=True)
    source_identity = baseline.validate_source(source_dir)
    qt_identity = baseline.validate_qt(qt_dir)

    build_path = args.build_manifest.resolve(strict=True)
    build_manifest, build_raw = read_json(build_path)
    validate_build_manifest(build_manifest, binary)

    fixture_manifest_path = args.fixture_manifest.resolve(strict=True)
    _, fixture_sha256 = fixture_probe.load_and_verify_fixture(
        fixture_dir,
        fixture_manifest_path,
    )
    fixture_copy = fixture_dir / "manifest.json"
    if (
        fixture_copy.exists()
        and fixture_copy.read_bytes() != fixture_manifest_path.read_bytes()
    ):
        raise HarnessError("fixture manifest copy differs")

    linux_path = args.linux_reference.resolve(strict=True)
    linux_report, linux_raw = read_json(linux_path)
    linux_document = validate_linux_reference(
        linux_report,
        fixture_sha256,
    )
    source_audit = validate_source_audit(source_dir, linux_report)
    normalized_linux = replace_fixture_paths(
        copy.deepcopy(linux_document),
        "/fixture",
    )
    if not isinstance(normalized_linux, dict):
        raise HarnessError("normalized Linux output is not an object")

    runs = []
    observations: list[dict[str, Any]] = []
    failures: list[str] = []
    for index in range(args.repetitions):
        observation = observe(
            binary,
            qt_dir,
            fixture_dir,
            working_dir,
            args.timeout_seconds,
        )
        runs.append(observation.summary())
        (raw_dir / f"run-{index + 1}.stdout").write_bytes(
            observation.stdout
        )
        (raw_dir / f"run-{index + 1}.stderr").write_bytes(
            observation.stderr
        )
        if observation.exit_code != 0:
            failures.append(f"run_{index + 1}.exit_code")
            continue
        if observation.stderr:
            failures.append(f"run_{index + 1}.stderr")
        try:
            parsed = json.loads(observation.stdout)
            if not isinstance(parsed, dict):
                raise HarnessError("harness output is not an object")
            observations.append(
                normalize_observation(parsed, fixture_dir)
            )
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
            ValueError,
        ):
            failures.append(f"run_{index + 1}.stdout")

    raw_outputs_equal = (
        len(runs) == args.repetitions
        and len({run["stdout_sha256"] for run in runs}) == 1
        and len({run["stderr_sha256"] for run in runs}) == 1
    )
    normalized_outputs_equal = (
        len(observations) == args.repetitions
        and all(item == observations[0] for item in observations[1:])
    )
    if not raw_outputs_equal:
        failures.append("raw_outputs_equal")
    if not normalized_outputs_equal:
        failures.append("normalized_outputs_equal")

    document = observations[0] if observations else None
    relationships: dict[str, bool] = {}
    case_differences: list[str] = []
    semantic_equal = False
    if document is not None:
        relationships = linux_probe.validate(copy.deepcopy(document))
        normalized_relationships = linux_report.get("relationships")
        if relationships != normalized_relationships:
            failures.append("linux_relationships")
        case_differences = compare_cases(document, normalized_linux)
        semantic_equal = (
            windows_semantic_document(document)
            == linux_semantic_document(linux_document)
        )
        if case_differences:
            failures.append("linux_case_projection")
        if not semantic_equal:
            failures.append("linux_semantic_document")

    report = {
        "schema_version": 1,
        "generator": (
            "tools/upstream/collect_windows_engine_contract_harness.py"
        ),
        "generator_sha256": baseline.sha256_file(Path(__file__)),
        "platform": "windows-x86_64-qt5",
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
                "docs/research/data/rule-orchestration-fixture.json"
            ),
            "sha256": fixture_sha256,
        },
        "linux_qt5_reference": {
            "path": (
                "docs/research/data/engine-contract-linux-qt5.json"
            ),
            "sha256": sha256_bytes(linux_raw),
        },
        "source_hashes": {
            "shared_helper": baseline.sha256_file(SHARED_HELPER),
            "linux_probe": baseline.sha256_file(LINUX_PROBE),
            "fixture_probe": baseline.sha256_file(FIXTURE_PROBE),
            "fixture_generator": baseline.sha256_file(
                FIXTURE_GENERATOR
            ),
        },
        "source_audit": source_audit,
        "repetitions": args.repetitions,
        "execution_count": args.repetitions,
        "case_observation_count": (
            args.repetitions * document["case_count"]
            if document is not None
            else 0
        ),
        "runs": runs,
        "raw_outputs_equal": raw_outputs_equal,
        "normalized_outputs_equal": normalized_outputs_equal,
        "observation": document,
        "relationships": relationships,
        "linux_qt5_comparison": {
            "windows_qt_version": (
                document.get("qt_version")
                if document is not None
                else None
            ),
            "linux_qt_version": linux_document.get("qt_version"),
            "excluded_identity_fields": ["qt_version"],
            "case_differences": case_differences,
            "semantic_document_equal": semantic_equal,
            "all_named_relationships_equal": (
                bool(relationships)
                and relationships == linux_report.get("relationships")
            ),
        },
        "normalization": {
            "operations": [
                (
                    "replace only verified fixture-root prefixes in "
                    "structured path strings with <fixture>"
                ),
                "convert backslashes inside replaced fixture paths",
            ],
            "not_performed": [
                "case or record removal/reordering",
                "result, error, callback, I/O, or cancellation rewriting",
                "raw stdout/stderr hash rewriting",
                "Qt version rewriting",
            ],
        },
        "raw_artifacts": {
            "storage": "untracked external directory selected by --raw-dir",
            "files": [
                f"run-{index + 1}.{stream}"
                for index in range(args.repetitions)
                for stream in ("stdout", "stderr")
            ],
        },
        "limitations": [
            (
                "the synchronized cross-thread stop case uses join-based "
                "happens-before and does not execute upstream's unsafe "
                "unsynchronized data-race path"
            ),
            (
                "callback exceptions, unknown-size devices, null devices, "
                "concurrent mutation, and signed-overflow paths remain "
                "outside the fixed 37-case contract"
            ),
            (
                "the harness isolates entry/I/O semantics with generated "
                "Binary rules and does not preserve uninitialized short-read "
                "tail bytes as compatibility data"
            ),
        ],
        "failures": sorted(set(failures)),
        "passed": not failures,
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
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
