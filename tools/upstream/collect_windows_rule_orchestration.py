#!/usr/bin/env python3
"""Collect native-Windows Qt5 rule orchestration behavior."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import platform
import subprocess
import sys
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[2]
BASELINE_SCRIPT = ROOT / "tools/upstream/collect_windows_cli_baseline.py"
LINUX_PROBE = ROOT / "tools/upstream/probe_rule_orchestration.py"
FIXTURE_GENERATOR = (
    ROOT / "tools/corpus/generate_rule_orchestration_fixture.py"
)
EXPECTED_BINARY_SHA256 = (
    "e8579a6ed0d2536ea14af154bcbeeaaea6967c0c7559a595"
    "fb3fe52206ac635e"
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
    "collect_windows_cli_baseline_rule_orchestration_helper",
    BASELINE_SCRIPT,
)
linux_probe = load_module(
    "probe_rule_orchestration_windows_reference",
    LINUX_PROBE,
)
HarnessError = baseline.BaselineError


@dataclass(frozen=True)
class Case:
    name: str
    arguments: tuple[str, ...]
    report_arguments: tuple[str, ...]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise HarnessError(f"JSON document is not an object: {path}")
    return value, raw


def validate_binary(binary: Path, source_dir: Path) -> dict[str, Any]:
    expected = (source_dir / "build/release/diec.exe").resolve(strict=True)
    if binary != expected:
        raise HarnessError("binary must be <source>/build/release/diec.exe")
    actual = baseline.sha256_file(binary)
    if actual != EXPECTED_BINARY_SHA256:
        raise HarnessError("fixed Windows CLI SHA-256 differs")
    return {
        "filename": binary.name,
        "size": binary.stat().st_size,
        "sha256": actual,
    }


def case_names(manifest: dict[str, Any]) -> tuple[str, ...]:
    return (
        *linux_probe.MODES,
        "priority_only",
        *manifest["ordering_cases"],
        "unknown",
    )


def validate_canonical_case(
    name: str,
    canonical: dict[str, Any],
    manifest: dict[str, Any],
) -> None:
    order = canonical.get("execution_order")
    detections = canonical.get("detections")
    if not isinstance(order, list) or not isinstance(detections, list):
        raise HarnessError(f"invalid canonical case: {name}")
    if name in linux_probe.MODES:
        linux_probe.validate_case(name, order, detections, manifest)
    elif name == "priority_only":
        linux_probe.validate_priority_only(order, detections, manifest)
    elif name == "unknown":
        linux_probe.validate_unknown(order, detections)
    else:
        linux_probe.validate_ordering_case(
            name,
            order,
            detections,
            manifest,
        )


def validate_linux_reference(
    report: dict[str, Any],
    manifest: dict[str, Any],
    manifest_sha256: str,
) -> None:
    expected_names = set(case_names(manifest))
    if (
        report.get("schema_version") != 1
        or report.get("generator")
        != "tools/upstream/probe_rule_orchestration.py"
        or report.get("generator_sha256")
        != baseline.sha256_file(LINUX_PROBE)
        or report.get("upstream_commit") != baseline.UPSTREAM_COMMIT
        or report.get("platform") != "linux-amd64-qt5"
        or report.get("normalized_outputs_equal") is not True
        or report.get("fixture_manifest", {}).get("sha256")
        != manifest_sha256
        or set(report.get("canonical_cases", {})) != expected_names
    ):
        raise HarnessError("Linux rule-orchestration reference differs")

    oracles = report.get("oracles")
    if (
        not isinstance(oracles, list)
        or len(oracles) != 2
        or any(
            oracle.get("revision") != baseline.UPSTREAM_COMMIT
            for oracle in oracles
        )
    ):
        raise HarnessError("Linux oracle identities differ")

    relationships = report.get("relationships")
    if (
        not isinstance(relationships, dict)
        or len(relationships) != 14
        or not all(value is True for value in relationships.values())
    ):
        raise HarnessError("Linux orchestration relationships differ")

    for name, canonical in report["canonical_cases"].items():
        if not isinstance(canonical, dict):
            raise HarnessError(f"invalid Linux canonical case: {name}")
        validate_canonical_case(name, canonical, manifest)


def materialize_arguments(
    arguments: Sequence[str],
    fixture_dir: Path,
) -> tuple[str, ...]:
    prefix = "/fixture"
    result = []
    for argument in arguments:
        if argument == prefix:
            result.append(str(fixture_dir))
        elif argument.startswith(prefix + "/"):
            relative = PurePosixPath(argument[len(prefix) + 1 :])
            if ".." in relative.parts:
                raise HarnessError("unsafe fixture argument")
            result.append(str(fixture_dir.joinpath(*relative.parts)))
        else:
            result.append(argument)
    return tuple(result)


def build_cases(
    fixture_dir: Path,
    manifest: dict[str, Any],
) -> tuple[Case, ...]:
    definitions: list[tuple[str, tuple[str, ...]]] = [
        (
            mode,
            linux_probe.scan_arguments(mode),
        )
        for mode in linux_probe.MODES
    ]
    definitions.append(
        ("priority_only", linux_probe.priority_arguments())
    )
    definitions.extend(
        (
            name,
            linux_probe.ordering_arguments(
                specification["database_prefix"]
            ),
        )
        for name, specification in manifest["ordering_cases"].items()
    )
    definitions.append(
        ("unknown", linux_probe.scan_arguments("default", empty=True))
    )
    return tuple(
        Case(
            name=name,
            arguments=materialize_arguments(arguments, fixture_dir),
            report_arguments=arguments,
        )
        for name, arguments in definitions
    )


def calculate_relationships(
    canonical_cases: dict[str, dict[str, Any]],
    manifest: dict[str, Any],
) -> dict[str, bool]:
    combined_order = canonical_cases["combined"]["execution_order"]
    default_order = canonical_cases["default"]["execution_order"]
    deep_order = canonical_cases["deep"]["execution_order"]
    heuristic_order = canonical_cases["heuristic"]["execution_order"]
    all_mode_orders = (
        default_order,
        deep_order,
        heuristic_order,
        combined_order,
    )
    all_mode_detections = tuple(
        canonical_cases[mode]["detections"] for mode in linux_probe.MODES
    )
    expected_init = manifest["expected_init_value"]
    return {
        "main_global_init_wins": all(
            detection["version"] == expected_init
            for detections in all_mode_detections
            for detection in detections
        ),
        "main_type_init_wins": all(
            detection["version"] == expected_init
            for detections in all_mode_detections
            for detection in detections
        ),
        "main_same_name_include_wins": all(
            detection["version"] == expected_init
            for detections in all_mode_detections
            for detection in detections
        ),
        "priority_only_beats_lexical_name": (
            canonical_cases["priority_only"]["execution_order"][0]
            == "z_priority.1.sg"
        ),
        "equal_priority_falls_back_to_name": (
            canonical_cases["equal_priority"]["execution_order"]
            == ["a_equal.2.sg", "m_equal.2.sg", "z_equal.2.sg"]
        ),
        "priority_segments_are_lexicographic": (
            canonical_cases["lexical_priority"]["execution_order"][0]
            == "z_ten.10.sg"
        ),
        "missing_priority_disables_pairwise_priority": (
            canonical_cases["missing_priority"]["execution_order"][0]
            == "a_plain.sg"
        ),
        "empty_priority_disables_pairwise_priority": (
            canonical_cases["empty_priority"]["execution_order"][0]
            == "a_empty..sg"
        ),
        "type_init_list_order_is_not_pure_priority": (
            combined_order.index("z_normal.1.sg")
            > combined_order.index("EP.entrypoint.4.sg")
        ),
        "database_layers_are_appended_main_extra_custom": (
            combined_order[-2:]
            == ["a_extra.0.sg", "a_custom.0.sg"]
        ),
        "ds_and_ep_require_deep": (
            "DS.deep.2.sg" not in default_order
            and "EP.entrypoint.4.sg" not in default_order
            and "DS.deep.2.sg" not in heuristic_order
            and "EP.entrypoint.4.sg" not in heuristic_order
            and "DS.deep.2.sg" in deep_order
            and "EP.entrypoint.4.sg" in deep_order
            and "DS.deep.2.sg" in combined_order
            and "EP.entrypoint.4.sg" in combined_order
        ),
        "heur_requires_heuristic": (
            "HEUR.heuristic.3.sg" not in default_order
            and "HEUR.heuristic.3.sg" not in deep_order
            and "HEUR.heuristic.3.sg" in heuristic_order
            and "HEUR.heuristic.3.sg" in combined_order
        ),
        "wrong_file_type_rule_never_executes": (
            all(
                "decoy.0.sg" not in order
                for order in all_mode_orders
            )
            and all(
                detection["name"] != "PE decoy"
                for detections in all_mode_detections
                for detection in detections
            )
        ),
        "empty_database_adds_unknown": (
            canonical_cases["unknown"]
            == {
                "execution_order": [],
                "detections": [
                    {
                        "type": "Unknown",
                        "name": "Unknown",
                        "version": "",
                        "info": "",
                    }
                ],
            }
        ),
    }


def observe(
    binary: Path,
    qt_dir: Path,
    working_dir: Path,
    arguments: Sequence[str],
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
        cwd=working_dir,
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


def collect_case(
    case: Case,
    binary: Path,
    qt_dir: Path,
    manifest: dict[str, Any],
    known_rule_names: set[str],
    working_dir: Path,
    raw_dir: Path,
    repetitions: int,
    timeout_seconds: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    runs = []
    canonical_runs = []
    for index in range(repetitions):
        observation = observe(
            binary,
            qt_dir,
            working_dir,
            case.arguments,
            timeout_seconds,
        )
        (raw_dir / f"{case.name}-run-{index + 1}.stdout").write_bytes(
            observation.stdout
        )
        (raw_dir / f"{case.name}-run-{index + 1}.stderr").write_bytes(
            observation.stderr
        )
        if observation.exit_code != 0:
            raise HarnessError(
                f"{case.name}/run-{index + 1} exited "
                f"{observation.exit_code}"
            )
        if observation.stderr:
            raise HarnessError(
                f"{case.name}/run-{index + 1} wrote stderr"
            )
        try:
            order, detections = linux_probe.parse_stdout(
                observation.stdout,
                known_rule_names,
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            raise HarnessError(
                f"{case.name}/run-{index + 1} output is invalid"
            ) from error
        canonical = {
            "execution_order": order,
            "detections": detections,
        }
        validate_canonical_case(case.name, canonical, manifest)
        canonical_runs.append(canonical)
        runs.append(observation.summary())

    normalized_equal = all(
        item == canonical_runs[0] for item in canonical_runs[1:]
    )
    if not normalized_equal:
        raise HarnessError(f"{case.name} semantic runs differ")
    return (
        {
            "arguments": list(case.report_arguments),
            "runs": runs,
            "raw_stdout_equal": (
                len({run["stdout_sha256"] for run in runs}) == 1
            ),
            "raw_stderr_equal": (
                len({run["stderr_sha256"] for run in runs}) == 1
            ),
            "semantic_runs_equal": normalized_equal,
            "canonical": canonical_runs[0],
        },
        canonical_runs[0],
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--qt-dir", type=Path, required=True)
    parser.add_argument("--fixture-dir", type=Path, required=True)
    parser.add_argument("--working-dir", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
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
            ROOT
            / "docs/research/data/rule-orchestration-linux-qt5.json"
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
            "native Windows rule-orchestration probe requires Windows"
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
    binary_identity = validate_binary(binary, source_dir)
    manifest_path = args.fixture_manifest.resolve(strict=True)
    manifest, manifest_sha256 = linux_probe.load_and_verify_fixture(
        fixture_dir,
        manifest_path,
    )
    fixture_copy = fixture_dir / "manifest.json"
    if (
        fixture_copy.exists()
        and fixture_copy.read_bytes() != manifest_path.read_bytes()
    ):
        raise HarnessError("fixture manifest copy differs")

    linux_path = args.linux_reference.resolve(strict=True)
    linux_reference, linux_raw = read_json(linux_path)
    validate_linux_reference(
        linux_reference,
        manifest,
        manifest_sha256,
    )

    cases = build_cases(fixture_dir, manifest)
    if len(cases) != 10:
        raise HarnessError("expected exactly ten orchestration cases")
    known_rule_names = set(
        linux_probe.detection_names_by_rule(manifest)
    )
    report_cases = {}
    canonical_cases = {}
    for case in cases:
        report_case, canonical = collect_case(
            case,
            binary,
            qt_dir,
            manifest,
            known_rule_names,
            working_dir,
            raw_dir,
            args.repetitions,
            args.timeout_seconds,
        )
        report_cases[case.name] = report_case
        canonical_cases[case.name] = canonical

    relationships = calculate_relationships(canonical_cases, manifest)
    if not all(relationships.values()):
        failed = sorted(
            name for name, value in relationships.items() if not value
        )
        raise HarnessError(f"orchestration relationships failed: {failed}")
    if relationships != linux_reference["relationships"]:
        raise HarnessError("Windows/Linux relationship maps differ")

    linux_canonical = linux_reference["canonical_cases"]
    differing_cases = [
        name
        for name in case_names(manifest)
        if canonical_cases[name] != linux_canonical[name]
    ]
    if differing_cases:
        raise HarnessError(
            "Windows/Linux canonical cases differ: "
            f"{differing_cases}"
        )

    report = {
        "schema_version": 1,
        "generator": (
            "tools/upstream/collect_windows_rule_orchestration.py"
        ),
        "generator_sha256": baseline.sha256_file(Path(__file__)),
        "platform": "windows-x86_64-qt5",
        "host": {
            "os_build": platform.version(),
            "architecture": platform.machine(),
        },
        "source": source_identity,
        "qt": qt_identity,
        "binary": binary_identity,
        "fixture": {
            "manifest": (
                "docs/research/data/rule-orchestration-fixture.json"
            ),
            "manifest_sha256": manifest_sha256,
            "generator": (
                "tools/corpus/generate_rule_orchestration_fixture.py"
            ),
            "generator_sha256": baseline.sha256_file(
                FIXTURE_GENERATOR
            ),
        },
        "linux_qt5_reference": {
            "path": (
                "docs/research/data/rule-orchestration-linux-qt5.json"
            ),
            "sha256": sha256_bytes(linux_raw),
        },
        "working_directory_role": (
            "existing controlled process context; not a fixture input"
        ),
        "repetitions": args.repetitions,
        "case_count": len(cases),
        "execution_count": len(cases) * args.repetitions,
        "cases": report_cases,
        "canonical_cases": canonical_cases,
        "relationships": relationships,
        "linux_qt5_comparison": {
            "case_differences": differing_cases,
            "canonical_cases_equal": not differing_cases,
            "relationships_equal": (
                relationships == linux_reference["relationships"]
            ),
            "platform_difference_classification": (
                "none_observed_in_semantic_projection"
            ),
        },
        "determinism": {
            "semantic_case_failures": [],
            "raw_stdout_equal_case_count": sum(
                case["raw_stdout_equal"]
                for case in report_cases.values()
            ),
            "raw_stderr_equal_case_count": sum(
                case["raw_stderr_equal"]
                for case in report_cases.values()
            ),
            "profiling_elapsed_is_nondeterministic": True,
        },
        "normalization": {
            "semantic_projection": [
                "extract exact profiling rule basenames",
                (
                    "extract type/name/version/info from every JSON "
                    "detection value"
                ),
            ],
            "not_performed": [
                "rule or detection removal/reordering",
                "profiling elapsed-time rewriting",
                "path, case, version, or field-value rewriting",
                "raw stdout/stderr hash rewriting",
            ],
        },
        "raw_artifacts": {
            "storage": (
                "untracked external directory selected by --raw-dir"
            ),
            "files": [
                f"{case.name}-run-{index}.{stream}"
                for case in cases
                for index in range(1, args.repetitions + 1)
                for stream in ("stdout", "stderr")
            ],
        },
        "limitations": [
            (
                "the fixture uses generated Binary rules and does not "
                "exercise every real database file type"
            ),
            (
                "the observed _init comparator order is fixed for this "
                "MSVC/Qt5 oracle and is not generalized to other toolchains"
            ),
            (
                "include cycles, duplicate include calls, and script "
                "exceptions remain outside this ten-case experiment"
            ),
        ],
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
