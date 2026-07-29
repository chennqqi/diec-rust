#!/usr/bin/env python3
"""Build the 68-row Windows Qt5 capability closure plan."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
EVALUATED_ON = "2026-07-29"
UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
PLATFORM = "windows-x86_64-qt5"
TRACEABILITY_PATH = "docs/research/data/capability-traceability.json"
WINDOWS_BUILD_PATH = (
    "docs/research/data/windows-qt5-build-baseline.json"
)
REPORT_KEYS = {
    "docs/research/data/baseline-corpus-windows-qt5.json": (
        "windows_cli_baseline"
    ),
    "docs/research/data/windows-qt5-cli-matrix.json": (
        "windows_cli_matrix"
    ),
    "docs/research/data/windows-qt5-cli-path-nested.json": (
        "windows_cli_path_nested"
    ),
    "docs/research/data/windows-qt5-cli-database.json": (
        "windows_cli_database"
    ),
    "docs/research/data/windows-qt5-cli-database-archive.json": (
        "windows_cli_database_archive"
    ),
    "docs/research/data/database-cache-engine-windows-qt5.json": (
        "windows_engine_database_cache"
    ),
    "docs/research/data/windows-qt5-cli-special-paths.json": (
        "windows_cli_special_paths"
    ),
    "docs/research/data/windows-qt5-cli-filesystem.json": (
        "windows_cli_filesystem"
    ),
    "docs/research/data/windows-qt5-cli-long-paths.json": (
        "windows_cli_long_paths"
    ),
    "docs/research/data/windows-qt5-cli-ads.json": (
        "windows_cli_ads"
    ),
    "docs/research/data/windows-qt5-cli-output-remaining.json": (
        "windows_cli_output_remaining"
    ),
    "docs/research/data/windows-qt5-cli-special-remaining.json": (
        "windows_cli_special_remaining"
    ),
}


class ClosurePlanError(ValueError):
    """The Windows closure plan cannot be generated safely."""


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ClosurePlanError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw, object_pairs_hook=reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ClosurePlanError(f"invalid JSON in {path}: {error}") from error
    if not isinstance(value, dict):
        raise ClosurePlanError(f"JSON root must be an object: {path}")
    return value, raw


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


COMPLETE: dict[str, str] = {
    "CAP-CLI-IN-001": "26 hash-bound corpus files exercise one positional target with deterministic Linux-equal detection projections",
    "CAP-CLI-IN-002": "ordered multi-target, duplicate, missing-plus-valid, and directory-plus-file cases are fixed",
    "CAP-CLI-IN-004": "single-file directory and empty-directory behavior is fixed",
    "CAP-CLI-OPT-001": "eight nested fixtures have stable recursive-scan detection trees equal to Linux Qt5",
    "CAP-CLI-OPT-002": "all 26 baseline samples execute the deep-scan option twice",
    "CAP-CLI-OPT-003": "all 26 baseline samples execute the heuristic option twice",
    "CAP-CLI-OPT-005": "all 26 baseline samples execute the aggressive option twice",
    "CAP-CLI-OPT-006": "all 26 baseline samples execute all-types twice",
    "CAP-CLI-OPT-007": "all 26 baseline samples execute formatted-result mode twice",
    "CAP-CLI-OPT-009": "database messages and structured-output contamination match Linux Qt5",
    "CAP-CLI-OPT-010": "all 26 baseline samples execute hide-unknown twice",
    "CAP-CLI-MODE-001": "entropy covers all 26 samples and six formatters with stable priority",
    "CAP-CLI-MODE-002": "info covers all 26 samples and six formatters with stable priority",
    "CAP-CLI-MODE-003": "generic Hash/MD5/unknown struct cases cover all 26 samples",
    "CAP-CLI-MODE-004": "show-structs is fixed as a control case",
    "CAP-CLI-MODE-005": "help and no-argument help are fixed controls",
    "CAP-CLI-MODE-006": "version is a fixed control",
    "CAP-CLI-OUT-001": "XML runs across all 26 samples with the four stable invalid-document cases retained",
    "CAP-CLI-OUT-002": "JSON detection projections cover all 26 samples",
    "CAP-CLI-OUT-003": "CSV covers all 26 samples and all-output precedence remains CSV-first",
    "CAP-CLI-OUT-004": "TSV covers all 26 samples",
    "CAP-CLI-OUT-005": "plain text covers all 26 samples",
    "CAP-CLI-DB-001": "main database success, missing, invalid ZIP, malformed, throwing, and ZIP boundaries are fixed",
    "CAP-CLI-DB-002": "extra database missing/success behavior is fixed",
    "CAP-CLI-DB-003": "custom database missing/success behavior is fixed",
    "CAP-CLI-DB-004": "show-database directory and 17 ZIP boundary cases are fixed",
    "CAP-RULE-008": "empty database and ordinary unknown inputs produce stable Unknown fallback",
    "CAP-RULE-010": "malformed and throwing database rules retain exact diagnostic visibility and JSON invalidity",
    "CAP-DISPATCH-001": "PE32/64, ELF32/64, and Mach-O 32/64/FAT projections are fixed",
    "CAP-DISPATCH-005": "DEX, Java Class, and PYC projections are fixed",
    "CAP-DISPATCH-006": "PDF and CFBF projections are fixed",
    "CAP-DISPATCH-007": "JPEG, PNG, and BMP/Image projections are fixed",
    "CAP-DISPATCH-008": "empty and plain binary fallback projections are fixed",
    "CAP-NEST-001": "directory traversal and internal recursive-scan controls are both fixed",
    "CAP-NEST-002": "resource and overlay recursive-scan projections are fixed",
    "CAP-NEST-005": "overlay and resource recursive/aggressive gate projections are fixed",
    "CAP-NEST-008": "nested result trees are fixed across 32 CLI cases",
}


PARTIAL: dict[str, tuple[str, str, str]] = {
    "CAP-CLI-IN-003": (
        "special names, Junction aliases/chains, ADS, and 324/325-code-unit paths are fixed",
        "UNC, reparse cycles, 4096-entry ordering, TOCTOU, and domain/network ACL profiles",
        "run a Windows path closure harness covering the named filesystem profiles with raw order and resource retention",
    ),
    "CAP-RULE-001": (
        "CLI main/extra/custom path acceptance and missing-layer behavior are fixed",
        "engine append order and same-name records across all three database layers",
        "port the database-layer engine harness to the fixed Windows object set",
    ),
    "CAP-RULE-002": (
        "formatter precedence and stable public detection order are fixed",
        "priority, lexical, missing, empty, and type-init rule ordering",
        "port the rule-orchestration ordering harness to Windows",
    ),
    "CAP-RULE-004": (
        "26 public format projections establish ordinary type dispatch",
        "wrong-file-type custom rules under all four scan modes",
        "run the fixed scan-option boundary fixture through a Windows engine harness",
    ),
    "CAP-RULE-005": (
        "deep and heuristic public CLI options execute across 26 samples",
        "independent deep, entry-point, and heuristic custom-rule gates",
        "run the fixed scan-option boundary fixture through a Windows engine harness",
    ),
    "CAP-DISPATCH-004": (
        "APK, IPA, JAR, ZIP, RAR, ISO9660, TAR, and GZip public projections are fixed",
        "NPM auto/forced dispatch and direct Archive property-only controls",
        "run the fixed archive-dispatch corpus and direct property harness on Windows",
    ),
    "CAP-RESULT-001": (
        "CLI filetype, offset, size, parent part, and detection strings are fixed",
        "engine scalar fields across memory/device entry points including scan time treatment",
        "port the result-model scalar harness to Windows",
    ),
    "CAP-RESULT-002": (
        "CLI detection records and database error framing are fixed",
        "engine record/error/debug/handler list inventory",
        "port the result-list harness to Windows",
    ),
    "CAP-RESULT-003": (
        "public heuristic and Unknown projections are fixed",
        "engine heuristic, advanced-heuristic, and unknown flag truth table",
        "port the result-flag harness to Windows",
    ),
    "CAP-RESULT-004": (
        "nested CLI parent/child tree shape is fixed",
        "record and parent identifier invariants modulo UUID values",
        "port the result-ID harness to Windows",
    ),
    "CAP-RESULT-005": (
        "canonical CLI type/name strings across 26 samples are fixed",
        "raw, numeric, reserved, and fallback enum mapping",
        "port the result-enum harness to Windows",
    ),
    "CAP-RESULT-006": (
        "normal CLI record strings and priority outcomes are fixed",
        "engine version/info/rule-name/rule-path/priority fields",
        "port the result-model field harness to Windows",
    ),
}


MISSING: dict[str, tuple[str, str]] = {
    "CAP-ENG-IN-001": (
        "public engine memory/file/device entry-point equivalence",
        "port the four-entry engine-contract harness to Windows",
    ),
    "CAP-ENG-IN-002": (
        "device/subdevice short-read, seek, range, and failure boundaries",
        "port the device/subdevice engine-contract harness to Windows",
    ),
    "CAP-CLI-OPT-004": (
        "Windows verbose OS-record channel behavior",
        "run the fixed CLI option harness on the Windows oracle",
    ),
    "CAP-CLI-OPT-008": (
        "Windows profiling channel and complete rule announcement order",
        "run the fixed CLI option/profiling harness on the Windows oracle",
    ),
    "CAP-CLI-TEST-001": (
        "Windows --test complete/missing argument behavior",
        "run the fixed CLI test-entry matrix on the Windows oracle",
    ),
    "CAP-CLI-TEST-002": (
        "Windows --createtest complete/missing argument behavior",
        "run the fixed CLI test-entry matrix on the Windows oracle",
    ),
    "CAP-RULE-003": (
        "global init, type init, and same-name include precedence",
        "port the rule-orchestration engine harness to Windows",
    ),
    "CAP-RULE-006": (
        "exact signature-name filter, case, deep, and missing controls",
        "port the signature-path/name engine harness to Windows",
    ),
    "CAP-RULE-007": (
        "private signature-path filter boundaries",
        "port the signature-path engine harness to Windows",
    ),
    "CAP-RULE-009": (
        "sort enabled/disabled engine record ordering",
        "port the engine-contract ordering harness to Windows",
    ),
    "CAP-RULE-011": (
        "complete Windows script profiling order",
        "run the fixed CLI option/profiling harness on Windows",
    ),
    "CAP-RULE-012": (
        "callback break, pre-stop, and synchronized cancellation",
        "port the engine-contract cancellation harness to Windows",
    ),
    "CAP-DISPATCH-002": (
        "DOS/COM public dispatch and BW property-only branch",
        "run the fixed DOS/COM/BW dispatch corpus on Windows",
    ),
    "CAP-DISPATCH-003": (
        "Amiga Hunk public dispatch and Atari ST detector-only fallback",
        "run the fixed Amiga/Atari dispatch corpus on Windows",
    ),
    "CAP-NEST-003": (
        "direct engine archive option independent of aggressive",
        "port the 64-case archive-option harness to Windows",
    ),
    "CAP-NEST-004": (
        "99999/100000/100001 archive and 21/2001 resource count boundaries",
        "port the archive/resource iteration harnesses to Windows",
    ),
    "CAP-NEST-006": (
        "recursive/aggressive resource context propagation",
        "port the resource-context chain harness to Windows",
    ),
    "CAP-NEST-007": (
        "public debug-data omission plus direct positive control",
        "port the debug-dispatch harness to Windows",
    ),
    "CAP-NEST-009": (
        "depth-64 and 33,554,546-byte cumulative expansion behavior",
        "run the fixed archive-limit corpus through a Windows engine harness",
    ),
}


EVIDENCE_PATHS = {
    "cli_scan_baseline": (
        "docs/research/data/baseline-corpus-windows-qt5.json",
        "docs/research/data/windows-qt5-cli-matrix.json",
    ),
    "cli_path": (
        "docs/research/data/windows-qt5-cli-path-nested.json",
        "docs/research/data/windows-qt5-cli-special-paths.json",
        "docs/research/data/windows-qt5-cli-filesystem.json",
        "docs/research/data/windows-qt5-cli-long-paths.json",
        "docs/research/data/windows-qt5-cli-ads.json",
    ),
    "cli_options": (
        "docs/research/data/baseline-corpus-windows-qt5.json",
        "docs/research/data/windows-qt5-cli-matrix.json",
        "docs/research/data/windows-qt5-cli-database.json",
    ),
    "cli_special": (
        "docs/research/data/windows-qt5-cli-matrix.json",
        "docs/research/data/windows-qt5-cli-special-remaining.json",
    ),
    "cli_control": (
        "docs/research/data/baseline-corpus-windows-qt5.json",
    ),
    "cli_output": (
        "docs/research/data/windows-qt5-cli-matrix.json",
        "docs/research/data/windows-qt5-cli-output-remaining.json",
    ),
    "database": (
        "docs/research/data/windows-qt5-cli-database.json",
        "docs/research/data/windows-qt5-cli-database-archive.json",
        "docs/research/data/database-cache-engine-windows-qt5.json",
    ),
    "rule_orchestration": (
        "docs/research/data/windows-qt5-cli-matrix.json",
        "docs/research/data/windows-qt5-cli-database.json",
    ),
    "dispatch_source": (
        "docs/research/data/baseline-corpus-windows-qt5.json",
        "docs/research/data/windows-qt5-cli-matrix.json",
    ),
    "nested_scan": (
        "docs/research/data/windows-qt5-cli-path-nested.json",
    ),
    "result_model": (
        "docs/research/data/baseline-corpus-windows-qt5.json",
        "docs/research/data/windows-qt5-cli-matrix.json",
        "docs/research/data/windows-qt5-cli-path-nested.json",
        "docs/research/data/windows-qt5-cli-database.json",
    ),
    "engine_contract": (),
    "signature_path_filter": (),
    "debug_data_dispatch": (),
}


EXPERIMENTS: dict[str, dict[str, Any]] = {
    "windows_path": {
        "fixture": (
            "extend the committed Windows path fixtures with UNC, reparse "
            "cycle, 4096-entry, TOCTOU, and ACL profiles"
        ),
        "harness": (
            "native Windows CLI/path collector using the pinned qmake oracle"
        ),
        "assertions": [
            "two raw observations per case are deterministic",
            "complete enumeration order and alias multiplicity are retained",
            "platform errors, resource use, and unsupported profiles are explicitly classified",
        ],
    },
    "engine_contract": {
        "fixture": "docs/research/data/engine-contract-linux-qt5.json",
        "harness": "tools/upstream/engine_contract_harness_main.cpp",
        "assertions": [
            "all public engine entry points retain the Linux row projection",
            "short-read, seek, range, and failure cases preserve exact error/list behavior",
            "signature filter, sorting, and cancellation controls are deterministic",
        ],
    },
    "cli_options": {
        "fixture": "docs/research/data/cli-option-behavior-linux.json",
        "harness": "tools/upstream/probe_cli_option_behavior.py",
        "assertions": [
            "verbose/messages/profiling channels retain raw stdout and stderr",
            "the complete profiling announcement order is compared",
            "test and createtest complete/missing argument exit and text behavior are fixed",
        ],
    },
    "rule_orchestration": {
        "fixture": "tools/corpus/generate_rule_orchestration_fixture.py",
        "harness": "tools/upstream/probe_rule_orchestration.py",
        "assertions": [
            "three-layer append and same-name records are retained",
            "global/type init, priority, lexical, and include precedence are fixed",
            "wrong-type, deep, entry-point, and heuristic gates are independently exercised",
        ],
    },
    "signature_path": {
        "fixture": "tools/corpus/generate_signature_path_fixture.py",
        "harness": "tools/upstream/signature_path_harness_main.cpp",
        "assertions": [
            "exact, empty, missing, case, dot-dot, deep, and disabled cases execute",
            "raw rule-path values are retained without platform rewriting",
            "two runs preserve record and error projections",
        ],
    },
    "legacy_dispatch": {
        "fixture": "tools/corpus/generate_legacy_dispatch_corpus.py",
        "harness": "tools/upstream/probe_legacy_dispatch.py",
        "assertions": [
            "DOS/COM and Amiga/Atari positive and negative cases execute",
            "public dispatch and detector/property-only branches are distinguished",
            "raw and structured Windows/Linux differences are classified",
        ],
    },
    "archive_dispatch": {
        "fixture": "tools/corpus/generate_generic_archive_dispatch_fixture.py",
        "harness": "tools/upstream/probe_generic_archive_dispatch_harness.py",
        "assertions": [
            "NPM auto and forced paths execute",
            "direct Archive property-only controls execute",
            "dispatch names, child trees, and errors are compared to Linux Qt5",
        ],
    },
    "nested_engine": {
        "fixture": "docs/research/data/nested-corpus.json",
        "harness": (
            "port the archive-option, iteration, resource-context, debug, "
            "and archive-limit probes under tools/upstream/"
        ),
        "assertions": [
            "direct engine options are separated from release CLI flags",
            "count, depth, and cumulative-byte sentinel boundaries execute",
            "context propagation, debug omission, cancellation, and resource projections are retained",
        ],
    },
    "result_model": {
        "fixture": (
            "docs/research/data/result-list-fixture.json, "
            "docs/research/data/result-flag-fixture.json, and "
            "docs/research/data/result-enum-fixture.json; metadata and ID "
            "harnesses are self-contained"
        ),
        "harness": (
            "port result_metadata/result_lists/result_ids/result_flags/"
            "result_enums harnesses under tools/upstream/"
        ),
        "assertions": [
            "scalar fields and all result lists are captured",
            "flags, identifiers, and enum raw/canonical forms are retained",
            "version, info, rule path/name, priority, and nondeterministic fields are classified",
        ],
    },
}

EXPERIMENT_GROUPS: dict[str, str] = {
    "CAP-CLI-IN-003": "windows_path",
    **{
        capability_id: "engine_contract"
        for capability_id in (
            "CAP-ENG-IN-001",
            "CAP-ENG-IN-002",
            "CAP-RULE-006",
            "CAP-RULE-009",
            "CAP-RULE-012",
        )
    },
    **{
        capability_id: "cli_options"
        for capability_id in (
            "CAP-CLI-OPT-004",
            "CAP-CLI-OPT-008",
            "CAP-CLI-TEST-001",
            "CAP-CLI-TEST-002",
            "CAP-RULE-011",
        )
    },
    **{
        capability_id: "rule_orchestration"
        for capability_id in (
            "CAP-RULE-001",
            "CAP-RULE-002",
            "CAP-RULE-003",
            "CAP-RULE-004",
            "CAP-RULE-005",
        )
    },
    "CAP-RULE-007": "signature_path",
    "CAP-DISPATCH-002": "legacy_dispatch",
    "CAP-DISPATCH-003": "legacy_dispatch",
    "CAP-DISPATCH-004": "archive_dispatch",
    **{
        capability_id: "nested_engine"
        for capability_id in (
            "CAP-NEST-003",
            "CAP-NEST-004",
            "CAP-NEST-006",
            "CAP-NEST-007",
            "CAP-NEST-009",
        )
    },
    **{
        capability_id: "result_model"
        for capability_id in (
            "CAP-RESULT-001",
            "CAP-RESULT-002",
            "CAP-RESULT-003",
            "CAP-RESULT-004",
            "CAP-RESULT-005",
            "CAP-RESULT-006",
        )
    },
}


EXPECTED_REPORT_FACTS: dict[str, dict[str, Any]] = {
    "windows_cli_baseline": {
        "corpus_count": 26,
        "execution_count": 64,
        "deterministic": True,
        "linux_projection_equal": True,
    },
    "windows_cli_matrix": {
        "case_count": 338,
        "execution_count": 676,
        "deterministic": True,
        "linux_exit_codes_equal": True,
    },
    "windows_cli_path_nested": {
        "case_count": 46,
        "execution_count": 92,
        "deterministic": True,
        "nested_projections_equal": True,
        "path_prefixes_equal": True,
    },
    "windows_cli_database": {
        "case_count": 18,
        "execution_count": 36,
        "deterministic": True,
        "linux_normalized_stdout_equal": True,
    },
    "windows_cli_database_archive": {
        "case_count": 17,
        "execution_count": 34,
        "deterministic": True,
        "linux_normalized_stdout_equal": True,
    },
    "windows_cli_special_paths": {
        "case_count": 17,
        "execution_count": 34,
        "deterministic": True,
        "reference_projections_equal": True,
    },
    "windows_cli_filesystem": {
        "case_count": 8,
        "execution_count": 16,
        "deterministic": True,
        "reference_projections_equal": True,
    },
    "windows_cli_long_paths": {
        "case_count": 7,
        "execution_count": 14,
        "deterministic": True,
        "reference_projections_equal": True,
    },
    "windows_cli_ads": {
        "case_count": 5,
        "execution_count": 10,
        "deterministic": True,
        "reference_projections_equal": True,
    },
    "windows_cli_output_remaining": {
        "sample_count": 21,
        "execution_count": 294,
        "deterministic": True,
        "json_default_references_equal": True,
    },
    "windows_cli_special_remaining": {
        "sample_count": 21,
        "execution_count": 798,
        "deterministic": True,
        "outputs_valid": True,
    },
}


def validate_inputs(
    root: Path,
    traceability: dict[str, Any],
    build: dict[str, Any],
    reports: dict[str, dict[str, Any]],
    report_raw: dict[str, bytes],
) -> None:
    if traceability.get("schema_version") != 1:
        raise ClosurePlanError("traceability schema drift")
    if traceability.get("upstream_commit") != UPSTREAM_COMMIT:
        raise ClosurePlanError("traceability upstream drift")
    if traceability.get("rules_commit") != RULES_COMMIT:
        raise ClosurePlanError("traceability rules drift")
    if build.get("upstream", {}).get("commit") != UPSTREAM_COMMIT:
        raise ClosurePlanError("Windows build upstream drift")
    if build.get("upstream", {}).get("rules_commit") != RULES_COMMIT:
        raise ClosurePlanError("Windows build rules drift")

    for path, key in REPORT_KEYS.items():
        identity = build.get(key)
        if not isinstance(identity, dict):
            raise ClosurePlanError(f"Windows build identity missing: {key}")
        if identity.get("path") != path:
            raise ClosurePlanError(f"Windows build path drift: {key}")
        if identity.get("sha256") != sha256(report_raw[path]):
            raise ClosurePlanError(f"Windows report hash drift: {path}")
        report = reports[path]
        if report.get("schema_version") != 1:
            raise ClosurePlanError(f"Windows report schema drift: {path}")
        if report.get("platform") != PLATFORM:
            raise ClosurePlanError(f"Windows report platform drift: {path}")
        if report.get("source", {}).get("commit") != UPSTREAM_COMMIT:
            raise ClosurePlanError(f"Windows report source drift: {path}")

    for key, expected in EXPECTED_REPORT_FACTS.items():
        path = next(path for path, value in REPORT_KEYS.items() if value == key)
        summary = reports[path].get("summary")
        if not isinstance(summary, dict):
            raise ClosurePlanError(f"Windows summary missing: {path}")
        for fact, value in expected.items():
            if summary.get(fact) != value:
                raise ClosurePlanError(
                    f"Windows summary fact drift: {key}.{fact}"
                )

    cache = reports[
        "docs/research/data/database-cache-engine-windows-qt5.json"
    ]
    if (
        cache.get("passed") is not True
        or cache.get("failures") != []
        or cache.get("raw_outputs_equal") is not True
        or cache.get("normalized_outputs_equal") is not True
        or cache.get("linux_qt5_comparison", {}).get(
            "case_projection_differences"
        )
        != []
        or cache.get("linux_qt5_comparison", {}).get(
            "all_named_relationships_hold"
        )
        is not True
    ):
        raise ClosurePlanError("Windows cache harness facts drift")

    for evidence_set, paths in EVIDENCE_PATHS.items():
        for path in paths:
            if path not in reports:
                raise ClosurePlanError(
                    f"unknown {evidence_set} evidence path: {path}"
                )
            if not (root / path).is_file():
                raise ClosurePlanError(f"evidence path missing: {path}")


def build_plan(root: Path) -> dict[str, Any]:
    traceability, traceability_raw = load_json(root / TRACEABILITY_PATH)
    build, build_raw = load_json(root / WINDOWS_BUILD_PATH)
    reports = {}
    report_raw = {}
    for path in REPORT_KEYS:
        report, raw = load_json(root / path)
        reports[path] = report
        report_raw[path] = raw
    validate_inputs(root, traceability, build, reports, report_raw)

    capabilities = traceability.get("capabilities")
    if not isinstance(capabilities, list) or len(capabilities) != 68:
        raise ClosurePlanError("traceability must contain 68 capabilities")
    expected_ids = {row.get("id") for row in capabilities}
    classified_ids = set(COMPLETE) | set(PARTIAL) | set(MISSING)
    if expected_ids != classified_ids:
        missing = sorted(expected_ids - classified_ids)
        unknown = sorted(classified_ids - expected_ids)
        raise ClosurePlanError(
            f"closure classification drift: missing={missing}, unknown={unknown}"
        )
    if (
        set(COMPLETE) & set(PARTIAL)
        or set(COMPLETE) & set(MISSING)
        or set(PARTIAL) & set(MISSING)
    ):
        raise ClosurePlanError("closure status maps overlap")

    rows = []
    for capability in capabilities:
        capability_id = capability["id"]
        evidence_set = capability["evidence_set"]
        if evidence_set not in EVIDENCE_PATHS:
            raise ClosurePlanError(
                f"unknown evidence set for {capability_id}: {evidence_set}"
            )
        if capability_id in COMPLETE:
            status = "evidence_complete"
            observed_scope = COMPLETE[capability_id]
            missing_scope = None
            experiment = None
        elif capability_id in PARTIAL:
            status = "partial"
            observed_scope, missing_scope, _experiment_hint = PARTIAL[
                capability_id
            ]
        else:
            status = "missing"
            observed_scope = None
            missing_scope, _experiment_hint = MISSING[capability_id]
        if status == "evidence_complete":
            experiment = None
        else:
            group = EXPERIMENT_GROUPS.get(capability_id)
            if group is None or group not in EXPERIMENTS:
                raise ClosurePlanError(
                    f"missing experiment contract: {capability_id}"
                )
            experiment = EXPERIMENTS[group]
        rows.append(
            {
                "id": capability_id,
                "name": capability["name"],
                "evidence_set": evidence_set,
                "evidence_paths": list(EVIDENCE_PATHS[evidence_set]),
                "status": status,
                "observed_scope": observed_scope,
                "missing_scope": missing_scope,
                "proposed_experiment": experiment,
                "acceptance": (
                    "the complete Linux Qt5 row boundary is executed on "
                    "the pinned Windows Qt5 oracle with raw/structured "
                    "evidence and every platform difference classified"
                ),
            }
        )

    sources = {
        TRACEABILITY_PATH: sha256(traceability_raw),
        WINDOWS_BUILD_PATH: sha256(build_raw),
        **{path: sha256(raw) for path, raw in report_raw.items()},
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "evaluated_on": EVALUATED_ON,
        "platform": PLATFORM,
        "upstream_commit": UPSTREAM_COMMIT,
        "rules_commit": RULES_COMMIT,
        "sources": dict(sorted(sources.items())),
        "capabilities": rows,
        "summary": {
            "capability_count": len(rows),
            "evidence_complete": len(COMPLETE),
            "partial": len(PARTIAL),
            "missing": len(MISSING),
            "closure_required": len(PARTIAL) + len(MISSING),
            "all_capabilities_accounted_for": True,
            "windows_baseline_admitted": (
                not PARTIAL and not MISSING
            ),
            "windows_process_execution_count": 2070,
            "windows_report_count": len(REPORT_KEYS),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    report = build_plan(root)
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
    if args.output is None:
        print(serialized.decode("utf-8"), end="")
        return 0
    output = args.output if args.output.is_absolute() else root / args.output
    if args.check:
        if not output.is_file() or output.read_bytes() != serialized:
            raise ClosurePlanError(
                f"committed Windows closure plan is stale: {output}"
            )
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
