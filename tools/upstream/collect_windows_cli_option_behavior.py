#!/usr/bin/env python3
"""Collect native-Windows Qt5 CLI option/test/profiling behavior."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[2]
BASELINE_SCRIPT = ROOT / "tools/upstream/collect_windows_cli_baseline.py"
LINUX_OPTION_PROBE = ROOT / "tools/upstream/probe_cli_option_behavior.py"
ORDER_PROBE = ROOT / "tools/upstream/probe_binary_rule_order.py"
BASELINE_GENERATOR = ROOT / "tools/corpus/generate_baseline_corpus.py"
NINTENDO_GENERATOR = (
    ROOT / "tools/corpus/generate_nintendo_certified_corpus.py"
)
EXPECTED_BINARY_SHA256 = (
    "e8579a6ed0d2536ea14af154bcbeeaaea6967c0c7559a595"
    "fb3fe52206ac635e"
)
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


def load_module(name: str, path: Path) -> object:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load helper module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


baseline = load_module(
    "collect_windows_cli_baseline_option_helper",
    BASELINE_SCRIPT,
)
linux_probe = load_module(
    "probe_cli_option_behavior_windows_reference",
    LINUX_OPTION_PROBE,
)
order_probe = load_module(
    "probe_binary_rule_order_windows_reference",
    ORDER_PROBE,
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


def validate_linux_option_reference(
    report: dict[str, Any],
) -> None:
    if (
        report.get("schema_version") != 1
        or report.get("generator")
        != "tools/upstream/probe_cli_option_behavior.py"
        or report.get("generator_sha256")
        != baseline.sha256_file(LINUX_OPTION_PROBE)
        or report.get("upstream_commit") != baseline.UPSTREAM_COMMIT
        or report.get("platform") != "linux-amd64-qt5"
        or set(report.get("cases", {}))
        != {case.name for case in linux_probe.CASES}
    ):
        raise HarnessError("Linux CLI option reference identity differs")
    relationships = report.get("relationships")
    if (
        not isinstance(relationships, dict)
        or relationships.get("test_directory_value_is_unvalidated")
        is not True
        or relationships.get(
            "createtest_complete_only_prints_announcement"
        )
        is not True
        or relationships.get(
            "profiling_without_messages_equals_default"
        )
        is not True
        or relationships.get("all_stderr_empty") is not True
    ):
        raise HarnessError("Linux CLI option relationships differ")


def validate_order_reference(
    report: dict[str, Any],
    lifecycle_sha256: str,
    sample: dict[str, Any],
) -> list[str]:
    if (
        report.get("schema_version") != 1
        or report.get("generator")
        != "tools/upstream/probe_binary_rule_order.py"
        or report.get("upstream_commit") != baseline.UPSTREAM_COMMIT
        or report.get("rules_commit") != baseline.RULES_COMMIT
        or report.get("platform") != "linux-amd64-qt5"
        or report.get("orders_equal") is not True
        or report.get("order_count") != 292
        or report.get("lifecycle_manifest", {}).get("sha256")
        != lifecycle_sha256
        or report.get("sample") != sample
    ):
        raise HarnessError("Linux profiling-order reference differs")
    order = report.get("order")
    if not isinstance(order, list):
        raise HarnessError("Linux profiling-order list is missing")
    expected_names, _ = order_probe.load_expected_names(
        ROOT / "docs/research/data/binary-rule-lifecycle.json"
    )
    order_probe.validate_order(order, expected_names)
    if report.get("order_sha256") != sha256_bytes(
        order_probe.canonical_order_bytes(order)
    ):
        raise HarnessError("Linux profiling-order hash differs")
    return order


def normalize_text(
    data: bytes,
    replacements: Sequence[tuple[str, str]],
) -> str:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise HarnessError("Windows CLI output is not UTF-8") from error
    text = text.replace("\r\n", "\n")
    for actual, marker in sorted(
        replacements,
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        variants = {
            actual,
            actual.replace("\\", "/"),
            actual.replace("/", "\\"),
        }
        for variant in variants:
            text = text.replace(variant, marker)
    return text


def parse_values(stdout: bytes) -> list[dict[str, str]]:
    document = json.loads(stdout)
    detects = document.get("detects")
    if not isinstance(detects, list) or len(detects) != 1:
        raise HarnessError("expected one top-level detect")
    values = detects[0].get("values")
    if not isinstance(values, list):
        raise HarnessError("top-level detect has no values")
    return [
        {
            key: value.get(key, "")
            for key in ("type", "name", "version", "info")
        }
        for value in values
    ]


def pair_case(
    case: Case,
    binary: Path,
    qt_dir: Path,
    timeout_seconds: int,
    raw_dir: Path,
    replacements: Sequence[tuple[str, str]],
) -> tuple[dict[str, Any], tuple[object, object]]:
    observations = tuple(
        baseline.observe(
            binary,
            qt_dir,
            case.arguments,
            timeout_seconds=timeout_seconds,
        )
        for _ in range(2)
    )
    for index, observation in enumerate(observations, 1):
        (raw_dir / f"{case.name}-run-{index}.stdout").write_bytes(
            observation.stdout
        )
        (raw_dir / f"{case.name}-run-{index}.stderr").write_bytes(
            observation.stderr
        )
    differences = baseline.pair_report(
        observations[0], observations[1]
    )["determinism_differences"]
    normalized_stdout = [
        normalize_text(observation.stdout, replacements)
        for observation in observations
    ]
    normalized_stderr = [
        normalize_text(observation.stderr, replacements)
        for observation in observations
    ]
    return (
        {
            "arguments": list(case.report_arguments),
            "runs": [item.summary() for item in observations],
            "raw_determinism_differences": differences,
            "normalized_outputs_equal": (
                normalized_stdout[0] == normalized_stdout[1]
                and normalized_stderr[0] == normalized_stderr[1]
            ),
            "canonical": {
                **observations[0].summary(),
                "normalized_stdout_utf8": normalized_stdout[0],
                "normalized_stderr_utf8": normalized_stderr[0],
            },
        },
        observations,
    )


def observe_linux_control(
    oracle: object,
    corpus_dir: Path,
    arguments: Sequence[str],
) -> object:
    process = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network=none",
            "--mount",
            f"type=bind,source={corpus_dir},target=/corpus,readonly",
            "--entrypoint",
            oracle.binary,
            oracle.image,
            *arguments,
        ],
        check=False,
        capture_output=True,
    )
    return baseline.Observation(
        process.returncode,
        process.stdout,
        process.stderr,
    )


def classify_order_difference(
    windows: list[str],
    linux: list[str],
) -> dict[str, Any]:
    differing_indices = [
        index
        for index, (windows_name, linux_name) in enumerate(
            zip(windows, linux, strict=True)
        )
        if windows_name != linux_name
    ]
    same_set = set(windows) == set(linux)
    moved_rule = "image_ICNS.sg"
    linux_index = linux.index(moved_rule)
    windows_index = windows.index(moved_rule)
    single_move_to_end = (
        same_set
        and linux_index == 248
        and windows_index == len(windows) - 1
        and windows
        == [
            *linux[:linux_index],
            *linux[linux_index + 1 :],
            moved_rule,
        ]
    )
    return {
        "orders_byte_equal": windows == linux,
        "same_rule_set": same_set,
        "differing_position_count": len(differing_indices),
        "differing_indices": differing_indices,
        "classification": (
            "single_rule_moved_to_end"
            if single_move_to_end
            else "unclassified"
        ),
        "moved_rule": moved_rule if single_move_to_end else None,
        "linux_index": linux_index if single_move_to_end else None,
        "windows_index": windows_index if single_move_to_end else None,
        "compatibility_status": (
            "platform_difference_retained_as_defect"
            if single_move_to_end
            else "unclassified_difference"
        ),
    }


def validate_option_relationships(
    observations: dict[str, object],
    normalized: dict[str, dict[str, str]],
    linux_reference: dict[str, Any],
) -> dict[str, Any]:
    empty = b""
    existing = observations["test_existing_directory"][0]
    missing = observations["test_missing_directory"][0]
    if existing != baseline.Observation(0, empty, empty):
        raise HarnessError("Windows --test existing behavior differs")
    if missing != existing:
        raise HarnessError("Windows --test validates directory")

    create_missing = observations["createtest_missing_positionals"][0]
    if (
        create_missing.exit_code != 4
        or create_missing.stderr
        or normalized["createtest_missing_positionals"]["stdout"]
        != (
            "Error: --addtest requires <filename> "
            "<detect_string> <directory>\n"
        )
    ):
        raise HarnessError("Windows --createtest missing behavior differs")

    create_complete = observations["createtest_complete"][0]
    expected_create = (
        "Adding test for file '<baseline-corpus>/minimal.elf' "
        "with detect string 'Detect String' in directory "
        "'<existing-directory>'\n"
    )
    if (
        create_complete.exit_code != 0
        or create_complete.stderr
        or normalized["createtest_complete"]["stdout"]
        != expected_create
    ):
        raise HarnessError("Windows --createtest complete behavior differs")

    default = observations["scan_default_json"][0]
    verbose = observations["scan_verbose_json"][0]
    profiling = observations[
        "scan_profiling_without_messages_json"
    ][0]
    if (
        default.exit_code != 0
        or default.stderr
        or verbose.exit_code != 0
        or verbose.stderr
        or profiling != default
    ):
        raise HarnessError("Windows scan option channel behavior differs")
    default_values = parse_values(default.stdout)
    verbose_values = parse_values(verbose.stdout)
    added = [item for item in verbose_values if item not in default_values]
    removed = [item for item in default_values if item not in verbose_values]
    expected_added = [
        {
            "type": "operation system",
            "name": "Unix",
            "version": "",
            "info": "AMD64, 64-bit",
        }
    ]
    expected_removed = [
        {
            "type": "Unknown",
            "name": "Unknown",
            "version": "",
            "info": "",
        }
    ]
    if added != expected_added or removed != expected_removed:
        raise HarnessError("Windows verbose result delta differs")

    quiet = observations["showdatabase_missing_without_messages"][0]
    messages = observations["showdatabase_missing_with_messages"][0]
    quiet_text = normalized[
        "showdatabase_missing_without_messages"
    ]["stdout"]
    messages_text = normalized[
        "showdatabase_missing_with_messages"
    ]["stdout"]
    expected_quiet = (
        "Main database: <missing-main>\n"
        "Extra database: <missing-extra>\n"
        "Custom database: <missing-custom>\n"
    )
    message = "Cannot load database: <missing-main>\n"
    if (
        quiet.exit_code != 3
        or quiet.stderr
        or quiet_text != expected_quiet
        or messages.exit_code != 3
        or messages.stderr
        or messages_text != message + expected_quiet
    ):
        raise HarnessError("Windows messages channel behavior differs")

    linux_added = linux_reference["relationships"][
        "verbose_added_values"
    ]
    if (
        len(linux_added) != 1
        or linux_added[0].get("type") != "operation system"
        or linux_reference["relationships"]["verbose_removed_values"]
        != []
    ):
        raise HarnessError("Linux verbose relationship shape differs")

    return {
        "test_directory_value_is_unvalidated": True,
        "createtest_complete_only_prints_announcement": True,
        "createtest_missing_positionals_exit_code": 4,
        "createtest_missing_positionals_uses_addtest_name": True,
        "verbose_added_values": added,
        "verbose_removed_values": removed,
        "profiling_without_messages_equals_default": True,
        "messages_added_stdout_lines": [
            message.rstrip("\n")
        ],
        "messages_change_exit_code": False,
        "all_option_case_stderr_empty": True,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--qt-dir", type=Path, required=True)
    parser.add_argument("--baseline-corpus-dir", type=Path, required=True)
    parser.add_argument("--nintendo-corpus-dir", type=Path, required=True)
    parser.add_argument("--working-dir", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument(
        "--baseline-manifest",
        type=Path,
        default=ROOT / "docs/research/data/baseline-corpus.json",
    )
    parser.add_argument(
        "--nintendo-manifest",
        type=Path,
        default=(
            ROOT / "docs/research/data/nintendo-certified-corpus.json"
        ),
    )
    parser.add_argument(
        "--linux-option-reference",
        type=Path,
        default=(
            ROOT / "docs/research/data/cli-option-behavior-linux.json"
        ),
    )
    parser.add_argument(
        "--linux-order-reference",
        type=Path,
        default=(
            ROOT
            / "docs/research/data/binary-rule-order-linux-qt5.json"
        ),
    )
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if os.name != "nt":
        raise HarnessError("native Windows CLI option probe requires Windows")
    if args.timeout_seconds < 1 or args.timeout_seconds > 3600:
        raise HarnessError("timeout-seconds must be in 1..3600")

    source_dir = args.source_dir.resolve(strict=True)
    qt_dir = args.qt_dir.resolve(strict=True)
    binary = args.binary.resolve(strict=True)
    baseline_corpus = args.baseline_corpus_dir.resolve(strict=True)
    nintendo_corpus = args.nintendo_corpus_dir.resolve(strict=True)
    working_dir = args.working_dir.resolve(strict=True)
    raw_dir = args.raw_dir.resolve()
    raw_dir.mkdir(parents=True, exist_ok=True)

    source_identity = baseline.validate_source(source_dir)
    qt_identity = baseline.validate_qt(qt_dir)
    binary_identity = validate_binary(binary, source_dir)
    samples, baseline_manifest_sha256 = baseline.load_corpus(
        baseline_corpus,
        args.baseline_manifest.resolve(strict=True),
    )
    minimal_matches = [
        item for item in samples if item["name"] == "minimal.elf"
    ]
    if len(minimal_matches) != 1:
        raise HarnessError("minimal.elf is not uniquely declared")
    minimal_sample = minimal_matches[0]
    minimal_path = baseline_corpus / "minimal.elf"

    lifecycle_path = ROOT / "docs/research/data/binary-rule-lifecycle.json"
    expected_names, lifecycle_sha256 = order_probe.load_expected_names(
        lifecycle_path
    )
    nintendo_path, nintendo_sample = order_probe.load_sample(
        nintendo_corpus,
        args.nintendo_manifest.resolve(strict=True),
        "ps3-type-1-elf.self",
    )

    linux_option_path = args.linux_option_reference.resolve(strict=True)
    linux_option, linux_option_raw = read_json(linux_option_path)
    validate_linux_option_reference(linux_option)
    linux_order_path = args.linux_order_reference.resolve(strict=True)
    linux_order, linux_order_raw = read_json(linux_order_path)
    reference_order = validate_order_reference(
        linux_order,
        lifecycle_sha256,
        nintendo_sample,
    )

    database_args = (
        "--database",
        str(source_dir / "Detect-It-Easy/db"),
        "--extradatabase",
        str(source_dir / "Detect-It-Easy/db_extra"),
        "--customdatabase",
        str(source_dir / "Detect-It-Easy/db_custom"),
    )
    database_report_args = (
        "--database",
        "<source>/Detect-It-Easy/db",
        "--extradatabase",
        "<source>/Detect-It-Easy/db_extra",
        "--customdatabase",
        "<source>/Detect-It-Easy/db_custom",
    )
    missing_dir = working_dir / "definitely-missing-test-directory"
    missing_databases = tuple(
        working_dir / name
        for name in ("missing-main", "missing-extra", "missing-custom")
    )
    forbidden_paths = [missing_dir, *missing_databases]
    if any(path.exists() for path in forbidden_paths):
        raise HarnessError("one or more negative-control paths exist")
    missing_database_args = (
        "--database",
        str(missing_databases[0]),
        "--extradatabase",
        str(missing_databases[1]),
        "--customdatabase",
        str(missing_databases[2]),
    )
    missing_database_report_args = (
        "--database",
        "<missing-main>",
        "--extradatabase",
        "<missing-extra>",
        "--customdatabase",
        "<missing-custom>",
    )
    cases = (
        Case(
            "test_existing_directory",
            ("--test", str(working_dir), *database_args),
            (
                "--test",
                "<existing-directory>",
                *database_report_args,
            ),
        ),
        Case(
            "test_missing_directory",
            ("--test", str(missing_dir), *database_args),
            ("--test", "<missing-directory>", *database_report_args),
        ),
        Case(
            "createtest_missing_positionals",
            ("--createtest", str(minimal_path), *database_args),
            (
                "--createtest",
                "<baseline-corpus>/minimal.elf",
                *database_report_args,
            ),
        ),
        Case(
            "createtest_complete",
            (
                "--createtest",
                str(minimal_path),
                *database_args,
                "Detect String",
                str(working_dir),
            ),
            (
                "--createtest",
                "<baseline-corpus>/minimal.elf",
                *database_report_args,
                "Detect String",
                "<existing-directory>",
            ),
        ),
        Case(
            "scan_default_json",
            ("--json", *database_args, str(minimal_path)),
            (
                "--json",
                *database_report_args,
                "<baseline-corpus>/minimal.elf",
            ),
        ),
        Case(
            "scan_verbose_json",
            (
                "--json",
                "--verbose",
                *database_args,
                str(minimal_path),
            ),
            (
                "--json",
                "--verbose",
                *database_report_args,
                "<baseline-corpus>/minimal.elf",
            ),
        ),
        Case(
            "scan_profiling_without_messages_json",
            (
                "--json",
                "--profiling",
                *database_args,
                str(minimal_path),
            ),
            (
                "--json",
                "--profiling",
                *database_report_args,
                "<baseline-corpus>/minimal.elf",
            ),
        ),
        Case(
            "showdatabase_missing_without_messages",
            ("--showdatabase", *missing_database_args),
            ("--showdatabase", *missing_database_report_args),
        ),
        Case(
            "showdatabase_missing_with_messages",
            (
                "--showdatabase",
                "--messages",
                *missing_database_args,
            ),
            (
                "--showdatabase",
                "--messages",
                *missing_database_report_args,
            ),
        ),
    )
    replacements = [
        (str(minimal_path), "<baseline-corpus>/minimal.elf"),
        (str(working_dir), "<existing-directory>"),
        (str(missing_dir), "<missing-directory>"),
        (
            str(source_dir / "Detect-It-Easy/db"),
            "<source>/Detect-It-Easy/db",
        ),
        (
            str(source_dir / "Detect-It-Easy/db_extra"),
            "<source>/Detect-It-Easy/db_extra",
        ),
        (
            str(source_dir / "Detect-It-Easy/db_custom"),
            "<source>/Detect-It-Easy/db_custom",
        ),
        (str(missing_databases[0]), "<missing-main>"),
        (str(missing_databases[1]), "<missing-extra>"),
        (str(missing_databases[2]), "<missing-custom>"),
    ]

    case_reports: dict[str, Any] = {}
    observations: dict[str, tuple[object, object]] = {}
    normalized: dict[str, dict[str, str]] = {}
    failures: list[str] = []
    for case in cases:
        report, pair = pair_case(
            case,
            binary,
            qt_dir,
            args.timeout_seconds,
            raw_dir,
            replacements,
        )
        case_reports[case.name] = report
        observations[case.name] = pair
        normalized[case.name] = {
            "stdout": report["canonical"]["normalized_stdout_utf8"],
            "stderr": report["canonical"]["normalized_stderr_utf8"],
        }
        if report["raw_determinism_differences"]:
            failures.append(f"{case.name}.raw_determinism")
        if not report["normalized_outputs_equal"]:
            failures.append(f"{case.name}.normalized_determinism")

    linux_oracle = linux_probe.ORACLES[0]
    linux_image_id, linux_revision = linux_probe.inspect_image(
        linux_oracle.image
    )
    linux_database_args = linux_probe.DATABASE_ARGS
    linux_control_specs = {
        "scan_default_json": (
            "--json",
            *linux_database_args,
            "/corpus/minimal.elf",
        ),
        "scan_verbose_json": (
            "--json",
            "--verbose",
            *linux_database_args,
            "/corpus/minimal.elf",
        ),
        "scan_profiling_without_messages_json": (
            "--json",
            "--profiling",
            *linux_database_args,
            "/corpus/minimal.elf",
        ),
    }
    linux_control_report = {}
    linux_control_observations = {}
    for name, arguments in linux_control_specs.items():
        observation = observe_linux_control(
            linux_oracle,
            baseline_corpus,
            arguments,
        )
        linux_control_observations[name] = observation
        (raw_dir / f"linux-control-{name}.stdout").write_bytes(
            observation.stdout
        )
        (raw_dir / f"linux-control-{name}.stderr").write_bytes(
            observation.stderr
        )
        linux_normalized_stdout = normalize_text(
            observation.stdout,
            [("/corpus/minimal.elf", "<baseline-corpus>/minimal.elf")],
        )
        windows_normalized_stdout = normalized[name]["stdout"]
        semantic_equal = (
            observation.exit_code == observations[name][0].exit_code
            and not observation.stderr
            and normalized[name]["stderr"] == ""
            and linux_normalized_stdout == windows_normalized_stdout
        )
        if not semantic_equal:
            failures.append(f"{name}.linux_same_sample")
        linux_control_report[name] = {
            "arguments": [
                *arguments[:-1],
                "<baseline-corpus>/minimal.elf",
            ],
            **observation.summary(),
            "normalized_stdout_utf8": linux_normalized_stdout,
            "windows_semantic_equal": semantic_equal,
        }
    if (
        linux_control_observations[
            "scan_profiling_without_messages_json"
        ]
        != linux_control_observations["scan_default_json"]
    ):
        failures.append("linux_control_profiling_without_messages")

    relationships: dict[str, Any] = {}
    try:
        relationships = validate_option_relationships(
            observations,
            normalized,
            linux_option,
        )
    except (HarnessError, ValueError, json.JSONDecodeError) as error:
        failures.append(f"option_relationships:{error}")

    profiling_arguments = (
        "--profiling",
        "--messages",
        "--json",
        "--deepscan",
        "--heuristicscan",
        *database_args,
        str(nintendo_path),
    )
    profiling_report_arguments = (
        "--profiling",
        "--messages",
        "--json",
        "--deepscan",
        "--heuristicscan",
        *database_report_args,
        "<nintendo-corpus>/ps3-type-1-elf.self",
    )
    profiling_runs = []
    orders = []
    for index in range(2):
        observation = baseline.observe(
            binary,
            qt_dir,
            profiling_arguments,
            timeout_seconds=args.timeout_seconds,
        )
        (raw_dir / f"profiling-order-run-{index + 1}.stdout").write_bytes(
            observation.stdout
        )
        (raw_dir / f"profiling-order-run-{index + 1}.stderr").write_bytes(
            observation.stderr
        )
        order = order_probe.extract_order(
            observation.stdout,
            expected_names,
        )
        try:
            order_probe.validate_order(order, expected_names)
        except ValueError as error:
            failures.append(f"profiling_order_run_{index + 1}:{error}")
        if observation.exit_code != 0:
            failures.append(f"profiling_order_run_{index + 1}.exit_code")
        if observation.stderr:
            failures.append(f"profiling_order_run_{index + 1}.stderr")
        profiling_runs.append(
            {
                **observation.summary(),
                "order_count": len(order),
                "order_sha256": sha256_bytes(
                    order_probe.canonical_order_bytes(order)
                ),
            }
        )
        orders.append(order)
    order_runs_equal = orders[0] == orders[1]
    order_matches_linux = orders[0] == reference_order
    order_difference = classify_order_difference(
        orders[0],
        reference_order,
    )
    if not order_runs_equal:
        failures.append("profiling_order_determinism")
    if (
        not order_matches_linux
        and order_difference["classification"]
        != "single_rule_moved_to_end"
    ):
        failures.append("profiling_order_linux_reference_unclassified")

    report = {
        "schema_version": 1,
        "generator": (
            "tools/upstream/collect_windows_cli_option_behavior.py"
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
        "fixtures": {
            "baseline_manifest": {
                "path": "docs/research/data/baseline-corpus.json",
                "sha256": baseline_manifest_sha256,
                "sample": minimal_sample,
                "generator_sha256": baseline.sha256_file(
                    BASELINE_GENERATOR
                ),
            },
            "nintendo_manifest": {
                "path": (
                    "docs/research/data/nintendo-certified-corpus.json"
                ),
                "sha256": baseline.sha256_file(
                    args.nintendo_manifest.resolve(strict=True)
                ),
                "sample": nintendo_sample,
                "generator_sha256": baseline.sha256_file(
                    NINTENDO_GENERATOR
                ),
            },
            "binary_lifecycle": {
                "path": (
                    "docs/research/data/binary-rule-lifecycle.json"
                ),
                "sha256": lifecycle_sha256,
            },
        },
        "linux_references": {
            "cli_option": {
                "path": (
                    "docs/research/data/cli-option-behavior-linux.json"
                ),
                "sha256": sha256_bytes(linux_option_raw),
            },
            "profiling_order": {
                "path": (
                    "docs/research/data/"
                    "binary-rule-order-linux-qt5.json"
                ),
                "sha256": sha256_bytes(linux_order_raw),
            },
            "same_sample_control": {
                "oracle": {
                    "name": linux_oracle.name,
                    "image": linux_oracle.image,
                    "image_id": linux_image_id,
                    "revision": linux_revision,
                    "binary": linux_oracle.binary,
                },
                "execution_count": len(linux_control_specs),
                "cases": linux_control_report,
            },
        },
        "source_hashes": {
            "baseline_helper": baseline.sha256_file(BASELINE_SCRIPT),
            "linux_option_probe": baseline.sha256_file(
                LINUX_OPTION_PROBE
            ),
            "order_probe": baseline.sha256_file(ORDER_PROBE),
        },
        "repetitions": 2,
        "cases": case_reports,
        "relationships": relationships,
        "profiling_order": {
            "arguments": list(profiling_report_arguments),
            "runs": profiling_runs,
            "raw_stdout_may_vary_only_in_elapsed_timing": True,
            "order_runs_equal": order_runs_equal,
            "order_matches_linux_qt5": order_matches_linux,
            "linux_qt5_difference": order_difference,
            "order_count": len(orders[0]),
            "order_sha256": sha256_bytes(
                order_probe.canonical_order_bytes(orders[0])
            ),
            "order": orders[0],
        },
        "normalization": {
            "operations": [
                "convert CRLF to LF in deterministic option-case text",
                "replace only exact verified fixture/database paths",
            ],
            "not_performed": [
                "exit-code, diagnostic, record, or JSON rewriting",
                "profiling rule removal, insertion, or reordering",
                "profiling elapsed-time rewriting",
                "raw stdout/stderr hash rewriting",
            ],
        },
        "raw_artifacts": {
            "storage": "untracked external directory selected by --raw-dir",
            "stdout_and_stderr_preserved_per_run": True,
        },
        "summary": {
            "case_count": len(cases) + 1,
            "deterministic_option_case_count": len(cases),
            "execution_count": (len(cases) + 1) * 2,
            "determinism_failures": len(
                [
                    failure
                    for failure in failures
                    if "determinism" in failure
                ]
            ),
            "relationship_failures": len(
                [
                    failure
                    for failure in failures
                    if "relationship" in failure
                ]
            ),
            "profiling_order_count": len(orders[0]),
            "profiling_order_matches_linux_qt5": order_matches_linux,
            "profiling_order_difference_classified": (
                order_matches_linux
                or order_difference["classification"]
                == "single_rule_moved_to_end"
            ),
            "outputs_valid": not failures,
        },
        "failures": failures,
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
