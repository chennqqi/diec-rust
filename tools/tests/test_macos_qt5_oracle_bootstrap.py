import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD_SCRIPT = ROOT / "tools/upstream/build_macos_qt5_oracle.sh"
VALIDATOR_PATH = (
    ROOT / "tools/upstream/validate_macos_qt5_oracle_report.py"
)
PLAN_SCRIPT = ROOT / "tools/research/build_macos_qt5_oracle_plan.py"
PLAN_PATH = ROOT / "docs/research/data/macos-qt5-oracle-plan.json"
WORKFLOW_PATH = (
    ROOT / ".github/workflows/macos-qt5-oracle-candidate.yml"
)
CLI_COLLECTOR_PATH = (
    ROOT / "tools/upstream/collect_macos_cli_baseline.py"
)
CLI_VALIDATOR_PATH = (
    ROOT / "tools/upstream/validate_macos_cli_baseline.py"
)
MATRIX_COLLECTOR_PATH = (
    ROOT / "tools/upstream/collect_macos_cli_matrix.py"
)
MATRIX_VALIDATOR_PATH = (
    ROOT / "tools/upstream/validate_macos_cli_matrix.py"
)
REMAINING_COLLECTOR_PATH = (
    ROOT / "tools/upstream/collect_macos_cli_remaining.py"
)
REMAINING_VALIDATOR_PATH = (
    ROOT / "tools/upstream/validate_macos_cli_remaining.py"
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


VALIDATOR = load_module("validate_macos_qt5_oracle_report", VALIDATOR_PATH)
PLAN = load_module("build_macos_qt5_oracle_plan", PLAN_SCRIPT)
CLI_COLLECTOR = load_module(
    "collect_macos_cli_baseline", CLI_COLLECTOR_PATH
)
CLI_VALIDATOR = load_module(
    "validate_macos_cli_baseline", CLI_VALIDATOR_PATH
)
CLI_COMMON = load_module(
    "collect_windows_cli_baseline_for_macos_test",
    ROOT / "tools/upstream/collect_windows_cli_baseline.py",
)
MATRIX_COLLECTOR = load_module(
    "collect_macos_cli_matrix", MATRIX_COLLECTOR_PATH
)
MATRIX_VALIDATOR = load_module(
    "validate_macos_cli_matrix", MATRIX_VALIDATOR_PATH
)
MATRIX_HELPER = load_module(
    "collect_windows_cli_matrix_for_macos_test",
    ROOT / "tools/upstream/collect_windows_cli_matrix.py",
)
MATRIX_DEFINITIONS = load_module(
    "compare_cli_oracles_for_macos_test",
    ROOT / "tools/upstream/compare_cli_oracles.py",
)
REMAINING_COLLECTOR = load_module(
    "collect_macos_cli_remaining", REMAINING_COLLECTOR_PATH
)
REMAINING_VALIDATOR = load_module(
    "validate_macos_cli_remaining", REMAINING_VALIDATOR_PATH
)
REMAINING_OUTPUT_HELPER = load_module(
    "collect_windows_cli_output_remaining_for_macos_test",
    ROOT / "tools/upstream/collect_windows_cli_output_remaining.py",
)
REMAINING_SPECIAL_HELPER = load_module(
    "collect_windows_cli_special_remaining_for_macos_test",
    ROOT / "tools/upstream/collect_windows_cli_special_remaining.py",
)


def candidate_report() -> dict:
    digest = "0" * 64
    return {
        "schema_version": 1,
        "result": "candidate",
        "platform": "macos-x86_64-qt5",
        "source": {
            "repository": "https://github.com/horsicq/DIE-engine",
            "commit": VALIDATOR.UPSTREAM_COMMIT,
            "rules_commit": VALIDATOR.RULES_COMMIT,
            "recursive_submodule_count": 58,
            "tracked_files_clean_before_and_after": True,
        },
        "source_files": {
            path: digest for path in VALIDATOR.EXPECTED_SOURCE_FILES
        },
        "host": {
            "sw_vers": ["ProductName:\tmacOS", "ProductVersion:\t15.0"],
            "uname": "Darwin host 24.0.0 x86_64",
            "cpu_brand": "Intel test CPU",
            "logical_cpu_count": 4,
            "xcode_version": ["Xcode 16.0", "Build version 16A1"],
            "clang_version": ["Apple clang version 16.0.0"],
            "cmake_version": "cmake version 3.30.0",
        },
        "qt": {
            "version": "5.15.2",
            "qmake_spec": "macx-clang",
            "qmake_version": [
                "QMake version 3.1",
                "Using Qt version 5.15.2",
            ],
            "qmake_sha256": digest,
            "qtcore_sha256": digest,
            "qtscript_sha256": digest,
        },
        "build": {
            "system": "qmake",
            "configuration": "release",
            "jobs": 4,
            "targets": [
                "sub-build_libs-make_first",
                "sub-console_source-make_first",
            ],
            "elapsed_seconds": 60,
        },
        "artifact": {
            "size": 1,
            "sha256": digest,
            "architectures": ["x86_64"],
            "file_description": "Mach-O 64-bit executable x86_64",
            "otool_l": [
                "diec:",
                "\tQtCore.framework/Versions/5/QtCore",
            ],
            "version_stdout": "die 4.0.0",
            "version_exit_code": 0,
        },
        "admission": {
            "platform_admitted": False,
            "reason": "runtime capability evidence is missing",
        },
        "local_paths": {
            "source_dir": "/private/tmp/source",
            "qt_dir": "/Users/runner/Qt/5.15.2/clang_64",
            "build_dir": "/private/tmp/build",
            "artifact": "/private/tmp/source/build/release/diec",
        },
    }


def write_cli_candidate_bundle(directory: Path) -> Path:
    oracle = candidate_report()
    oracle_path = directory / "oracle-candidate.json"
    oracle_path.write_text(
        json.dumps(oracle, sort_keys=True), encoding="utf-8"
    )
    manifest_raw = (
        ROOT / "docs/research/data/baseline-corpus.json"
    ).read_bytes()
    manifest = json.loads(manifest_raw)
    linux_raw = (
        ROOT / "docs/research/data/baseline-corpus-linux-qt5.json"
    ).read_bytes()
    linux = json.loads(linux_raw)

    cases = {}
    for case in CLI_COLLECTOR.expected_cases(CLI_COMMON):
        observation = CLI_COMMON.Observation(0, b"stable", b"")
        pair = CLI_COLLECTOR.pair_report(
            CLI_COMMON,
            directory,
            f"cli-baseline/cases/{case.name}",
            observation,
            observation,
        )
        pair["arguments"] = list(case.report_arguments)
        cases[case.name] = pair

    database_args = [
        "--database",
        "<source>/Detect-It-Easy/db",
        "--extradatabase",
        "<source>/Detect-It-Easy/db_extra",
        "--customdatabase",
        "<source>/Detect-It-Easy/db_custom",
    ]
    corpus = {}
    for sample in manifest["samples"]:
        name = sample["name"]
        linux_item = linux["corpus"][name]
        linux_tree = linux_item["left_detect_tree"]
        stdout = (
            b""
            if linux_tree is None
            else json.dumps(
                {"detects": linux_tree},
                separators=(",", ":"),
            ).encode("utf-8")
        )
        observation = CLI_COMMON.Observation(
            linux_item["left"]["exit_code"], stdout, b""
        )
        pair = CLI_COLLECTOR.pair_report(
            CLI_COMMON,
            directory,
            f"cli-baseline/corpus/{name}",
            observation,
            observation,
        )
        projected = CLI_COMMON.json_detect_tree(stdout)
        pair.update(
            {
                "arguments": [
                    "--json",
                    *database_args,
                    f"<corpus>/{name}",
                ],
                "intended_format": sample["intended_format"],
                "sample_sha256": sample["sha256"],
                "first_detect_tree": projected,
                "second_detect_tree": projected,
                "linux_qt5_detect_tree": linux_tree,
                "linux_projection_equal": projected == linux_tree,
                "linux_exit_code_equal": True,
            }
        )
        corpus[name] = pair

    report = {
        "schema_version": 1,
        "result": "candidate",
        "platform": CLI_VALIDATOR.PLATFORM,
        "generator": {
            "path": CLI_VALIDATOR.COLLECTOR,
            "sha256": hashlib.sha256(
                CLI_COLLECTOR_PATH.read_bytes()
            ).hexdigest(),
            "shared_collector_path": (
                CLI_VALIDATOR.SHARED_COLLECTOR
            ),
            "shared_collector_sha256": hashlib.sha256(
                (
                    ROOT
                    / CLI_VALIDATOR.SHARED_COLLECTOR
                ).read_bytes()
            ).hexdigest(),
            "validator_path": (
                "tools/upstream/validate_macos_cli_baseline.py"
            ),
            "validator_sha256": hashlib.sha256(
                CLI_VALIDATOR_PATH.read_bytes()
            ).hexdigest(),
        },
        "oracle_report": {
            "path": "oracle-candidate.json",
            "sha256": hashlib.sha256(
                oracle_path.read_bytes()
            ).hexdigest(),
        },
        "source": {
            "repository": "https://github.com/horsicq/DIE-engine",
            "commit": VALIDATOR.UPSTREAM_COMMIT,
            "recursive_submodule_count": 58,
            "rules_commit": VALIDATOR.RULES_COMMIT,
            "tracked_files_clean_before_and_after": True,
        },
        "qt": {
            "version": oracle["qt"]["version"],
            "qmake_spec": oracle["qt"]["qmake_spec"],
            "qmake_sha256": oracle["qt"]["qmake_sha256"],
            "qtcore_sha256": oracle["qt"]["qtcore_sha256"],
            "qtscript_sha256": oracle["qt"]["qtscript_sha256"],
        },
        "binary": {
            "size": oracle["artifact"]["size"],
            "sha256": oracle["artifact"]["sha256"],
            "relative_path": "build/release/diec",
        },
        "corpus_manifest": {
            "path": CLI_VALIDATOR.BASELINE_MANIFEST,
            "sha256": hashlib.sha256(manifest_raw).hexdigest(),
            "sample_count": len(manifest["samples"]),
        },
        "linux_qt5_reference": {
            "path": CLI_VALIDATOR.LINUX_REFERENCE,
            "sha256": hashlib.sha256(linux_raw).hexdigest(),
        },
        "cases": cases,
        "corpus": corpus,
        "summary": {
            "case_count": len(cases),
            "corpus_count": len(corpus),
            "execution_count": 2 * (len(cases) + len(corpus)),
            "determinism_failures": [],
            "linux_projection_failures": [],
            "deterministic": True,
            "linux_projection_equal": True,
        },
        "admission": {
            "platform_admitted": False,
            "capability_rows_admitted": 0,
            "reason": CLI_VALIDATOR.EXPECTED_ADMISSION_REASON,
        },
        "limitations": CLI_VALIDATOR.EXPECTED_LIMITATIONS,
    }
    report_path = directory / "cli-baseline-candidate.json"
    report_path.write_text(
        json.dumps(report, sort_keys=True), encoding="utf-8"
    )
    return report_path


def write_cli_matrix_candidate_bundle(
    directory: Path,
    baseline_path: Path,
) -> Path:
    baseline = CLI_VALIDATOR.load_json(baseline_path)[0]
    oracle_path = directory / "oracle-candidate.json"
    manifest = json.loads(
        (
            ROOT / "docs/research/data/baseline-corpus.json"
        ).read_bytes()
    )
    sample_names = [sample["name"] for sample in manifest["samples"]]
    cases_by_kind = {
        "output": MATRIX_DEFINITIONS.OUTPUT_MATRIX,
        "scan": MATRIX_DEFINITIONS.SCAN_MATRIX,
        "special": MATRIX_DEFINITIONS.SPECIAL_MATRIX,
    }
    selection = {
        "output": list(MATRIX_COLLECTOR.OUTPUT_SAMPLES),
        "scan": sample_names,
        "special": list(MATRIX_COLLECTOR.SPECIAL_SAMPLES),
    }
    linux_reports = {}
    linux_bindings = {}
    for kind, relative in MATRIX_COLLECTOR.LINUX_REFERENCES.items():
        raw = (ROOT / relative).read_bytes()
        linux_reports[kind] = json.loads(raw)
        linux_bindings[kind] = {
            "path": relative,
            "sha256": hashlib.sha256(raw).hexdigest(),
        }

    matrix = {}
    for kind in ("output", "scan", "special"):
        for sample_name in selection[kind]:
            kind_report = matrix.setdefault(sample_name, {}).setdefault(
                kind, {}
            )
            baseline_entry = baseline["corpus"][sample_name]
            baseline_observations = {}
            for side in ("first", "second"):
                item = baseline_entry[side]
                baseline_observations[side] = CLI_COMMON.Observation(
                    item["exit_code"],
                    (directory / item["stdout_path"]).read_bytes(),
                    (directory / item["stderr_path"]).read_bytes(),
                )
            observations = {}
            for case in cases_by_kind[kind]:
                if kind == "scan":
                    stdout = baseline_observations["first"].stdout
                    stderr = baseline_observations["first"].stderr
                    exit_code = baseline_observations["first"].exit_code
                else:
                    stdout = b"stable"
                    stderr = b""
                    exit_code = 0
                if sample_name in MATRIX_COLLECTOR.OUTPUT_SAMPLES:
                    exit_code = linux_reports[kind]["matrix"][
                        sample_name
                    ][kind][case.name]["left"]["exit_code"]
                observation = CLI_COMMON.Observation(
                    exit_code, stdout, stderr
                )
                observations[case.name] = (
                    observation,
                    observation,
                )
                pair = CLI_COLLECTOR.pair_report(
                    CLI_COMMON,
                    directory,
                    (
                        "cli-matrix/"
                        f"{sample_name}/{kind}/{case.name}"
                    ),
                    observation,
                    observation,
                )
                pair["arguments"] = [
                    *MATRIX_HELPER.translate_arguments(
                        case.arguments,
                        Path("<source>"),
                        report=True,
                    ),
                    f"<corpus>/{sample_name}",
                ]
                if kind == "scan":
                    tree = CLI_COMMON.json_detect_tree(stdout)
                    pair["first_detect_tree"] = tree
                    pair["second_detect_tree"] = tree
                if sample_name in MATRIX_COLLECTOR.OUTPUT_SAMPLES:
                    pair["linux_qt5_exit_code"] = exit_code
                    pair["linux_qt5_exit_code_equal"] = True
                kind_report[case.name] = pair

            if kind == "scan":
                default_first, default_second = observations["default"]
                default = kind_report["default"]
                reference_equal = (
                    default_first.summary()
                    == MATRIX_COLLECTOR.observation_identity(
                        baseline_entry["first"]
                    )
                    and default_second.summary()
                    == MATRIX_COLLECTOR.observation_identity(
                        baseline_entry["second"]
                    )
                    and default["first_detect_tree"]
                    == baseline_entry["first_detect_tree"]
                    and default["second_detect_tree"]
                    == baseline_entry["second_detect_tree"]
                )
                default["cli_baseline_reference_equal"] = reference_equal
                for case_name, (first, second) in observations.items():
                    entry = kind_report[case_name]
                    entry["first_changes_from_default"] = (
                        MATRIX_HELPER.observation_differences(
                            default_first, first
                        )
                    )
                    entry["second_changes_from_default"] = (
                        MATRIX_HELPER.observation_differences(
                            default_second, second
                        )
                    )

    case_counts = {
        kind: len(selection[kind]) * len(cases_by_kind[kind])
        for kind in selection
    }
    case_count = sum(case_counts.values())
    report = {
        "schema_version": 1,
        "result": "candidate",
        "platform": MATRIX_COLLECTOR.PLATFORM,
        "generator": {
            "path": MATRIX_VALIDATOR.COLLECTOR,
            "sha256": hashlib.sha256(
                MATRIX_COLLECTOR_PATH.read_bytes()
            ).hexdigest(),
            "validator_path": (
                "tools/upstream/validate_macos_cli_matrix.py"
            ),
            "validator_sha256": hashlib.sha256(
                MATRIX_VALIDATOR_PATH.read_bytes()
            ).hexdigest(),
            "baseline_collector_path": (
                MATRIX_VALIDATOR.BASELINE_COLLECTOR
            ),
            "baseline_collector_sha256": hashlib.sha256(
                CLI_COLLECTOR_PATH.read_bytes()
            ).hexdigest(),
            "baseline_validator_path": (
                MATRIX_VALIDATOR.BASELINE_VALIDATOR
            ),
            "baseline_validator_sha256": hashlib.sha256(
                CLI_VALIDATOR_PATH.read_bytes()
            ).hexdigest(),
            "windows_matrix_helper_path": (
                MATRIX_VALIDATOR.WINDOWS_MATRIX_HELPER
            ),
            "windows_matrix_helper_sha256": hashlib.sha256(
                (
                    ROOT
                    / MATRIX_VALIDATOR.WINDOWS_MATRIX_HELPER
                ).read_bytes()
            ).hexdigest(),
            "matrix_definitions_path": (
                MATRIX_VALIDATOR.MATRIX_DEFINITIONS
            ),
            "matrix_definitions_sha256": hashlib.sha256(
                (
                    ROOT / MATRIX_VALIDATOR.MATRIX_DEFINITIONS
                ).read_bytes()
            ).hexdigest(),
        },
        "oracle_report": {
            "path": "oracle-candidate.json",
            "sha256": hashlib.sha256(
                oracle_path.read_bytes()
            ).hexdigest(),
        },
        "cli_baseline_report": {
            "path": "cli-baseline-candidate.json",
            "sha256": hashlib.sha256(
                baseline_path.read_bytes()
            ).hexdigest(),
        },
        "source": baseline["source"],
        "qt": baseline["qt"],
        "binary": baseline["binary"],
        "corpus_manifest": baseline["corpus_manifest"],
        "linux_qt5_references": linux_bindings,
        "selection": selection,
        "matrix": matrix,
        "summary": {
            "sample_count": len(sample_names),
            "case_counts": case_counts,
            "case_count": case_count,
            "execution_count": 2 * case_count,
            "raw_stream_count": 4 * case_count,
            "determinism_failures": [],
            "default_reference_failures": [],
            "linux_exit_code_failures": [],
            "deterministic": True,
            "default_reference_equal": True,
            "linux_exit_codes_equal": True,
        },
        "admission": {
            "platform_admitted": False,
            "capability_rows_admitted": 0,
            "reason": MATRIX_COLLECTOR.ADMISSION_REASON,
        },
        "limitations": MATRIX_COLLECTOR.LIMITATIONS,
    }
    report_path = directory / "cli-matrix-candidate.json"
    report_path.write_text(
        json.dumps(report, sort_keys=True), encoding="utf-8"
    )
    return report_path


def write_cli_remaining_candidate_bundle(
    directory: Path,
    baseline_path: Path,
    primary_path: Path,
) -> Path:
    baseline = CLI_VALIDATOR.load_json(baseline_path)[0]
    manifest = json.loads(
        (
            ROOT / "docs/research/data/baseline-corpus.json"
        ).read_bytes()
    )
    covered = set(
        REMAINING_OUTPUT_HELPER.ALREADY_COVERED
    )
    selection = [
        sample["name"]
        for sample in manifest["samples"]
        if sample["name"] not in covered
    ]
    cases_by_kind = {
        "output": MATRIX_DEFINITIONS.OUTPUT_MATRIX,
        "special": MATRIX_DEFINITIONS.SPECIAL_MATRIX,
    }
    matrix = {}
    for sample_name in selection:
        sample_report = matrix.setdefault(sample_name, {})
        for kind in ("output", "special"):
            kind_report = sample_report.setdefault(kind, {})
            observations = {}
            for case in cases_by_kind[kind]:
                if kind == "output" and case.name == "json":
                    baseline_entry = baseline["corpus"][sample_name]
                    pair_observations = tuple(
                        CLI_COMMON.Observation(
                            baseline_entry[side]["exit_code"],
                            (
                                directory
                                / baseline_entry[side]["stdout_path"]
                            ).read_bytes(),
                            (
                                directory
                                / baseline_entry[side]["stderr_path"]
                            ).read_bytes(),
                        )
                        for side in ("first", "second")
                    )
                else:
                    if kind == "output":
                        stdout = (
                            b"<invalid"
                            if (
                                case.name == "xml"
                                and sample_name
                                in REMAINING_OUTPUT_HELPER.EXPECTED_INVALID_XML
                            )
                            else (
                                b"<root/>"
                                if case.name == "xml"
                                else b"text"
                            )
                        )
                    elif case.name in {
                        "info_json",
                        "info_all_output_flags",
                    }:
                        stdout = json.dumps(
                            {
                                "data": {
                                    "Info": {
                                        "File name": (
                                            "/tmp/corpus/"
                                            f"{sample_name}"
                                        )
                                    }
                                }
                            },
                            separators=(",", ":"),
                        ).encode("utf-8")
                    elif (
                        case.name
                        in REMAINING_SPECIAL_HELPER.JSON_CASES
                    ):
                        stdout = b"{}"
                    elif (
                        case.name
                        in REMAINING_SPECIAL_HELPER.XML_CASES
                    ):
                        stdout = b"<root/>"
                    else:
                        stdout = b"text"
                    observation = CLI_COMMON.Observation(
                        0, stdout, b""
                    )
                    pair_observations = (
                        observation,
                        observation,
                    )
                first, second = pair_observations
                observations[case.name] = pair_observations
                entry = CLI_COLLECTOR.pair_report(
                    CLI_COMMON,
                    directory,
                    (
                        "cli-remaining/"
                        f"{sample_name}/{kind}/{case.name}"
                    ),
                    first,
                    second,
                )
                entry.update(
                    {
                        "arguments": [
                            *MATRIX_HELPER.translate_arguments(
                                case.arguments,
                                Path("<source>"),
                                report=True,
                            ),
                            f"<corpus>/{sample_name}",
                        ],
                        "expected_exit_code": 0,
                        "expected_exit_code_equal": True,
                        "expected_empty_stderr": True,
                        "first_stderr_empty": True,
                        "second_stderr_empty": True,
                    }
                )
                if kind == "output":
                    expected_valid = not (
                        case.name == "xml"
                        and sample_name
                        in REMAINING_OUTPUT_HELPER.EXPECTED_INVALID_XML
                    )
                    first_valid = (
                        REMAINING_OUTPUT_HELPER.output_validity(
                            case.name, first.stdout
                        )
                    )
                    second_valid = (
                        REMAINING_OUTPUT_HELPER.output_validity(
                            case.name, second.stdout
                        )
                    )
                    entry.update(
                        {
                            "first_output_valid": first_valid,
                            "second_output_valid": second_valid,
                            "expected_output_valid": expected_valid,
                            "output_validity_expected_equal": True,
                        }
                    )
                    if case.name == "json":
                        first_tree = CLI_COMMON.json_detect_tree(
                            first.stdout
                        )
                        second_tree = CLI_COMMON.json_detect_tree(
                            second.stdout
                        )
                        entry.update(
                            {
                                "first_detect_tree": first_tree,
                                "second_detect_tree": second_tree,
                                "cli_baseline_reference_equal": True,
                            }
                        )
                else:
                    first_valid, first_projection = (
                        REMAINING_SPECIAL_HELPER.parse_output(
                            case.name, first.stdout
                        )
                    )
                    second_valid, second_projection = (
                        REMAINING_SPECIAL_HELPER.parse_output(
                            case.name, second.stdout
                        )
                    )
                    first_projection = (
                        REMAINING_SPECIAL_HELPER.normalize_projection(
                            case.name,
                            first_projection,
                            sample_name,
                        )
                    )
                    second_projection = (
                        REMAINING_SPECIAL_HELPER.normalize_projection(
                            case.name,
                            second_projection,
                            sample_name,
                        )
                    )
                    entry.update(
                        {
                            "first_output_valid": first_valid,
                            "second_output_valid": second_valid,
                        }
                    )
                    if (
                        case.name
                        in REMAINING_SPECIAL_HELPER.JSON_CASES
                        or case.name
                        in REMAINING_SPECIAL_HELPER.XML_CASES
                    ):
                        entry.update(
                            {
                                "first_projection": first_projection,
                                "second_projection": second_projection,
                            }
                        )
                kind_report[case.name] = entry

            if kind == "output":
                kind_report["all_output_flags"][
                    "csv_priority_reference_equal"
                ] = (
                    observations["all_output_flags"]
                    == observations["csv"]
                )
            else:
                for case_name, reference_name in (
                    REMAINING_SPECIAL_HELPER.PRIORITY_REFERENCES.items()
                ):
                    entry = kind_report[case_name]
                    entry["priority_reference_case"] = reference_name
                    entry["priority_reference_equal"] = (
                        observations[case_name]
                        == observations[reference_name]
                    )

    case_counts = {
        kind: len(selection) * len(cases)
        for kind, cases in cases_by_kind.items()
    }
    case_count = sum(case_counts.values())
    report = {
        "schema_version": 1,
        "result": "candidate",
        "platform": REMAINING_COLLECTOR.PLATFORM,
        "generator": REMAINING_COLLECTOR._generator_bindings(ROOT),
        "oracle_report": {
            "path": "oracle-candidate.json",
            "sha256": hashlib.sha256(
                (directory / "oracle-candidate.json").read_bytes()
            ).hexdigest(),
        },
        "cli_baseline_report": {
            "path": "cli-baseline-candidate.json",
            "sha256": hashlib.sha256(
                baseline_path.read_bytes()
            ).hexdigest(),
        },
        "cli_primary_matrix_report": {
            "path": "cli-matrix-candidate.json",
            "sha256": hashlib.sha256(
                primary_path.read_bytes()
            ).hexdigest(),
        },
        "source": baseline["source"],
        "qt": baseline["qt"],
        "binary": baseline["binary"],
        "corpus_manifest": baseline["corpus_manifest"],
        "selection": selection,
        "cases": {
            kind: [case.name for case in cases]
            for kind, cases in cases_by_kind.items()
        },
        "output_classification": {
            "expected_invalid_xml_samples": list(
                REMAINING_OUTPUT_HELPER.EXPECTED_INVALID_XML
            ),
            "special_json": list(
                REMAINING_SPECIAL_HELPER.JSON_CASES
            ),
            "special_xml": list(
                REMAINING_SPECIAL_HELPER.XML_CASES
            ),
        },
        "priority_references": {
            "output_all_flags": "csv",
            "special": (
                REMAINING_SPECIAL_HELPER.PRIORITY_REFERENCES
            ),
        },
        "matrix": matrix,
        "summary": {
            "sample_count": len(selection),
            "case_counts": case_counts,
            "case_count": case_count,
            "execution_count": 2 * case_count,
            "raw_stream_count": 4 * case_count,
            "determinism_failures": [],
            "expected_exit_failures": [],
            "stderr_failures": [],
            "validity_failures": [],
            "json_reference_failures": [],
            "priority_failures": [],
            "deterministic": True,
            "expected_exits_equal": True,
            "stderr_empty": True,
            "outputs_valid_as_expected": True,
            "json_baseline_references_equal": True,
            "priority_references_equal": True,
        },
        "admission": {
            "platform_admitted": False,
            "capability_rows_admitted": 0,
            "reason": REMAINING_COLLECTOR.ADMISSION_REASON,
        },
        "limitations": REMAINING_COLLECTOR.LIMITATIONS,
    }
    report_path = directory / "cli-remaining-candidate.json"
    report_path.write_text(
        json.dumps(report, sort_keys=True), encoding="utf-8"
    )
    return report_path


class MacosQt5OracleBootstrapTests(unittest.TestCase):
    def test_plan_is_exact_generator_output_and_source_bound(self):
        report = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
        expected = PLAN.build_plan(ROOT)
        self.assertEqual(report, expected)
        self.assertEqual(PLAN_PATH.read_bytes(), PLAN.serialize(expected))
        for relative, digest in report["sources"].items():
            with self.subTest(path=relative):
                self.assertEqual(
                    hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(),
                    digest,
                )

    def test_plan_keeps_runtime_and_platform_admission_open(self):
        report = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            report["result"],
            "infrastructure_ready_runtime_missing",
        )
        self.assertFalse(report["admission"]["platform_admitted"])
        self.assertEqual(
            report["admission"]["coverage_status"],
            "platform_missing",
        )
        self.assertEqual(
            report["runtime_closure"]["required_capability_count"],
            68,
        )
        self.assertEqual(
            report["runtime_closure"]["minimum_repetitions_per_case"],
            2,
        )

    def test_shell_builder_is_fail_closed_and_cli_only(self):
        text = BUILD_SCRIPT.read_text(encoding="utf-8")
        for required in (
            VALIDATOR.UPSTREAM_COMMIT,
            VALIDATOR.RULES_COMMIT,
            'EXPECTED_SUBMODULE_COUNT=58',
            'EXPECTED_QT_VERSION="5.15.2"',
            'EXPECTED_QMAKE_SPEC="macx-clang"',
            'EXPECTED_ARCH="x86_64"',
            'git -C "$source_dir" submodule status --recursive',
            'build directory must be empty',
            'sub-build_libs-make_first',
            'sub-console_source-make_first',
            'tracked_files_clean_before_and_after',
            'platform_admitted": False',
            'validate_macos_qt5_oracle_report.py',
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)
        self.assertNotIn("rm -rf", text)
        self.assertNotIn("gui_source", text)
        self.assertNotIn("lite_source", text)

    def test_dispatch_workflow_is_manual_pinned_and_non_admitting(self):
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        for required in (
            "workflow_dispatch:",
            "runs-on: macos-15-intel",
            "contents: read",
            "persist-credentials: false",
            "aqtinstall==${AQTINSTALL_VERSION}",
            "mac desktop 5.15.2 clang_64",
            "--modules qtscript",
            VALIDATOR.UPSTREAM_COMMIT,
            "submodule update",
            "--init --recursive --depth=1 --jobs 4",
            "build_macos_qt5_oracle.sh",
            "validate_macos_qt5_oracle_report.py",
            "collect_macos_cache_state_candidate.py",
            "validate_macos_cache_state_candidate.py",
            "generate_baseline_corpus.py",
            "collect_macos_cli_baseline.py",
            "validate_macos_cli_baseline.py",
            "collect_macos_cli_matrix.py",
            "validate_macos_cli_matrix.py",
            "collect_macos_cli_remaining.py",
            "validate_macos_cli_remaining.py",
            "cli-baseline-candidate.json",
            "cli-matrix-candidate.json",
            "cli-remaining-candidate.json",
            "diec-macos-candidate-evidence/raw",
            (
                "actions/checkout@"
                "de0fac2e4500dabe0009e67214ff5f5447ce83dd"
            ),
            (
                "actions/upload-artifact@"
                "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
            ),
            "retention-days: 14",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)
        for forbidden in (
            "macos-latest",
            "pull_request:",
            "push:",
            "@v4",
            "@v5",
            "@v6",
            "@v7",
            "platform_admitted",
            "cache_state_admitted",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)

        report = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
        workflow = report["dispatch_workflow"]
        self.assertEqual(workflow["trigger"], "workflow_dispatch")
        self.assertEqual(workflow["runner"], "macos-15-intel")
        self.assertFalse(workflow["automatically_admits_evidence"])
        self.assertTrue(workflow["raw_cli_streams_retained"])
        self.assertEqual(
            workflow["candidate_reports"],
            [
                "oracle-candidate.json",
                "cache-state-candidate.json",
                "cli-baseline-candidate.json",
                "cli-matrix-candidate.json",
                "cli-remaining-candidate.json",
            ],
        )
        self.assertEqual(
            workflow["remaining_cli_execution_count"], 1092
        )
        self.assertEqual(
            workflow["general_cli_execution_count"], 1832
        )
        self.assertEqual(
            workflow["general_cli_raw_stream_count"], 3664
        )

    def test_cli_candidate_tools_are_bound_and_fail_closed(self):
        collector = CLI_COLLECTOR_PATH.read_text(encoding="utf-8")
        validator = CLI_VALIDATOR_PATH.read_text(encoding="utf-8")
        for required in (
            "native Darwin x86_64",
            "oracle-candidate.json",
            "baseline-corpus-linux-qt5.json",
            "platform_admitted",
            "capability_rows_admitted",
            "write_observation",
            "determinism_failures",
            "linux_projection_failures",
        ):
            with self.subTest(required=required):
                self.assertIn(required, collector)
        for required in (
            "bundle-local oracle-candidate.json",
            "raw file inventory differs from report",
            "raw path escaped bundle",
            "candidate must not admit capability evidence",
            "determinism projection drift",
            "corpus projection drift",
        ):
            with self.subTest(required=required):
                self.assertIn(required, validator)
        self.assertEqual(
            CLI_COLLECTOR.ADMISSION_REASON,
            CLI_VALIDATOR.EXPECTED_ADMISSION_REASON,
        )
        self.assertEqual(
            CLI_COLLECTOR.LIMITATIONS,
            CLI_VALIDATOR.EXPECTED_LIMITATIONS,
        )

    def test_cli_candidate_validator_recomputes_raw_bundle(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            report_path = write_cli_candidate_bundle(directory)
            report = CLI_VALIDATOR.load_json(report_path)[0]
            oracle_path = directory / "oracle-candidate.json"
            CLI_VALIDATOR.validate_report(
                report,
                report_path=report_path,
                oracle_path=oracle_path,
                root=ROOT,
            )

            raw_path = directory / report["cases"]["help"]["first"][
                "stdout_path"
            ]
            raw_path.write_bytes(b"tampered")
            with self.assertRaisesRegex(
                CLI_VALIDATOR.ReportError,
                "raw stream identity mismatch",
            ):
                CLI_VALIDATOR.validate_report(
                    report,
                    report_path=report_path,
                    oracle_path=oracle_path,
                    root=ROOT,
                )

    def test_cli_candidate_validator_rejects_admission_and_extra_raw(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            report_path = write_cli_candidate_bundle(directory)
            report = CLI_VALIDATOR.load_json(report_path)[0]
            oracle_path = directory / "oracle-candidate.json"

            report["admission"]["platform_admitted"] = True
            with self.assertRaisesRegex(
                CLI_VALIDATOR.ReportError,
                "must not admit",
            ):
                CLI_VALIDATOR.validate_report(
                    report,
                    report_path=report_path,
                    oracle_path=oracle_path,
                    root=ROOT,
                )
            report["admission"]["platform_admitted"] = False
            (
                directory
                / "raw"
                / "cli-baseline"
                / "undeclared"
            ).write_bytes(b"x")
            with self.assertRaisesRegex(
                CLI_VALIDATOR.ReportError,
                "raw file inventory",
            ):
                CLI_VALIDATOR.validate_report(
                    report,
                    report_path=report_path,
                    oracle_path=oracle_path,
                    root=ROOT,
                )

    def test_cli_matrix_validator_recomputes_full_raw_matrix(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            baseline_path = write_cli_candidate_bundle(directory)
            matrix_path = write_cli_matrix_candidate_bundle(
                directory, baseline_path
            )
            report = CLI_VALIDATOR.load_json(matrix_path)[0]
            oracle_path = directory / "oracle-candidate.json"
            MATRIX_VALIDATOR.validate_report(
                report,
                report_path=matrix_path,
                oracle_path=oracle_path,
                baseline_path=baseline_path,
                root=ROOT,
            )
            self.assertEqual(report["summary"]["case_count"], 338)
            self.assertEqual(
                report["summary"]["execution_count"], 676
            )
            self.assertEqual(
                report["summary"]["raw_stream_count"], 1352
            )

            first = report["matrix"]["empty.bin"]["output"][
                "json"
            ]["first"]
            raw_path = directory / first["stdout_path"]
            original = raw_path.read_bytes()
            raw_path.write_bytes(b"tampered")
            with self.assertRaisesRegex(
                MATRIX_VALIDATOR.ReportError,
                "raw stream identity mismatch",
            ):
                MATRIX_VALIDATOR.validate_report(
                    report,
                    report_path=matrix_path,
                    oracle_path=oracle_path,
                    baseline_path=baseline_path,
                    root=ROOT,
                )
            raw_path.write_bytes(original)

            report["admission"]["platform_admitted"] = True
            with self.assertRaisesRegex(
                MATRIX_VALIDATOR.ReportError,
                "must not admit",
            ):
                MATRIX_VALIDATOR.validate_report(
                    report,
                    report_path=matrix_path,
                    oracle_path=oracle_path,
                    baseline_path=baseline_path,
                    root=ROOT,
                )
            report["admission"]["platform_admitted"] = False

            extra = (
                directory
                / "raw"
                / "cli-matrix"
                / "undeclared"
            )
            extra.write_bytes(b"x")
            with self.assertRaisesRegex(
                MATRIX_VALIDATOR.ReportError,
                "raw file inventory",
            ):
                MATRIX_VALIDATOR.validate_report(
                    report,
                    report_path=matrix_path,
                    oracle_path=oracle_path,
                    baseline_path=baseline_path,
                    root=ROOT,
                )

    def test_cli_remaining_validator_recomputes_full_raw_matrix(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            baseline_path = write_cli_candidate_bundle(directory)
            primary_path = write_cli_matrix_candidate_bundle(
                directory, baseline_path
            )
            report_path = write_cli_remaining_candidate_bundle(
                directory, baseline_path, primary_path
            )
            report = CLI_VALIDATOR.load_json(report_path)[0]
            oracle_path = directory / "oracle-candidate.json"
            REMAINING_VALIDATOR.validate_report(
                report,
                report_path=report_path,
                oracle_path=oracle_path,
                baseline_path=baseline_path,
                primary_path=primary_path,
                root=ROOT,
            )
            self.assertEqual(report["summary"]["case_count"], 546)
            self.assertEqual(
                report["summary"]["execution_count"], 1092
            )
            self.assertEqual(
                report["summary"]["raw_stream_count"], 2184
            )

            first = report["matrix"]["Minimal.class"]["output"][
                "json"
            ]["first"]
            raw_path = directory / first["stdout_path"]
            original = raw_path.read_bytes()
            raw_path.write_bytes(b"tampered")
            with self.assertRaisesRegex(
                REMAINING_VALIDATOR.ReportError,
                "raw stream identity mismatch",
            ):
                REMAINING_VALIDATOR.validate_report(
                    report,
                    report_path=report_path,
                    oracle_path=oracle_path,
                    baseline_path=baseline_path,
                    primary_path=primary_path,
                    root=ROOT,
                )
            raw_path.write_bytes(original)

            report["admission"]["platform_admitted"] = True
            with self.assertRaisesRegex(
                REMAINING_VALIDATOR.ReportError,
                "must not admit",
            ):
                REMAINING_VALIDATOR.validate_report(
                    report,
                    report_path=report_path,
                    oracle_path=oracle_path,
                    baseline_path=baseline_path,
                    primary_path=primary_path,
                    root=ROOT,
                )
            report["admission"]["platform_admitted"] = False

            extra = (
                directory
                / "raw"
                / "cli-remaining"
                / "undeclared"
            )
            extra.write_bytes(b"x")
            with self.assertRaisesRegex(
                REMAINING_VALIDATOR.ReportError,
                "raw file inventory",
            ):
                REMAINING_VALIDATOR.validate_report(
                    report,
                    report_path=report_path,
                    oracle_path=oracle_path,
                    baseline_path=baseline_path,
                    primary_path=primary_path,
                    root=ROOT,
                )

    def test_candidate_validator_accepts_complete_report(self):
        VALIDATOR.validate_report(candidate_report())

    def test_candidate_validator_rejects_identity_and_admission_drift(self):
        changed = candidate_report()
        changed["source"]["commit"] = "f" * 40
        with self.assertRaisesRegex(
            VALIDATOR.ReportError,
            "source identity",
        ):
            VALIDATOR.validate_report(changed)

        changed = candidate_report()
        changed["admission"]["platform_admitted"] = True
        with self.assertRaisesRegex(
            VALIDATOR.ReportError,
            "must not admit",
        ):
            VALIDATOR.validate_report(changed)

        changed = candidate_report()
        changed["artifact"]["architectures"] = ["arm64"]
        with self.assertRaisesRegex(
            VALIDATOR.ReportError,
            "artifact identity",
        ):
            VALIDATOR.validate_report(changed)

        changed = candidate_report()
        changed["qt"] = []
        with self.assertRaisesRegex(
            VALIDATOR.ReportError,
            "expected object: qt",
        ):
            VALIDATOR.validate_report(changed)

    def test_loader_rejects_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"schema_version":1,"schema_version":1}')
            with self.assertRaisesRegex(
                VALIDATOR.ReportError,
                "duplicate JSON key",
            ):
                VALIDATOR.load_report(path)


if __name__ == "__main__":
    unittest.main()
