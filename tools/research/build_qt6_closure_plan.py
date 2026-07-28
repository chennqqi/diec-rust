#!/usr/bin/env python3
"""Build the 68-row Linux Qt6 capability closure plan."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
EVALUATED_ON = "2026-07-28"
UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
PLATFORM = "linux-x86_64-qt6"
TRACEABILITY_PATH = "docs/research/data/capability-traceability.json"
REPORT_PATHS = (
    "docs/research/data/qt5-qt6-cli.json",
    "docs/research/data/global-host-api-qt5-qt6.json",
    "docs/research/data/host-api-arity-qt5-qt6.json",
    "docs/research/data/global-typo-errors-qt5-qt6.json",
    "docs/research/data/cli-output-boundaries-linux-qt5-qt6.json",
    "docs/research/data/cli-output-matrix-linux-qt5-qt6.json",
    "docs/research/data/cli-scan-nested-matrix-linux-qt5-qt6.json",
    "docs/research/data/qt6-alltypes-diagnostics.json",
    "docs/research/data/cli-special-matrix-linux-qt5-qt6.json",
    "docs/research/data/cli-special-boundaries-linux-qt5-qt6.json",
    "docs/research/data/cli-path-matrix-linux-qt5-qt6.json",
    "docs/research/data/cli-database-matrix-linux-qt5-qt6.json",
    "docs/research/data/qt6-database-diagnostics.json",
)
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
QT6_UNIMPLEMENTED_SHA256 = (
    "b303e6913e76b70a6f0d6a4d3ccd389bc342589e45e1615873a37334dea8c51b"
)


class ClosurePlanError(ValueError):
    """The Qt6 closure plan cannot be generated safely."""


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


# These are deliberately narrow. A capability is complete only when the existing
# Qt6 comparison exercises the entire behavior named by the matrix row.
COMPLETE: dict[str, str] = {
    "CAP-CLI-IN-001": "15 hash-bound corpus files exercise one positional target",
    "CAP-CLI-IN-002": "ordered, duplicate, missing-plus-valid, and directory-plus-file targets are equal",
    "CAP-CLI-IN-004": "single-file directory and empty-directory behavior is equal",
    "CAP-CLI-OPT-001": "all eight nested fixtures have equal recursive-scan detection trees",
    "CAP-CLI-OPT-002": "the five-sample deep-scan matrix has equal stdout and exit codes",
    "CAP-CLI-OPT-003": "the five-sample heuristic matrix has equal detection semantics",
    "CAP-CLI-OPT-005": "the five-sample aggressive matrix has equal stdout and exit codes",
    "CAP-CLI-OPT-006": "alltypes detections are equal; the complete Qt6 diagnostic difference is retained",
    "CAP-CLI-OPT-007": "the five-sample format-result matrix has equal stdout and exit codes",
    "CAP-CLI-OPT-009": "database load messages and structured-output contamination are equal",
    "CAP-CLI-OPT-010": "the five-sample hide-unknown matrix has equal stdout and exit codes",
    "CAP-CLI-MODE-001": "five-sample formatter and exact 6.5 entropy boundaries are equal",
    "CAP-CLI-MODE-002": "five-sample formatter, priority, and multi-target info boundaries are equal",
    "CAP-CLI-MODE-003": "generic and 11 format-specific struct method boundaries are equal",
    "CAP-CLI-MODE-004": "--showstructs is equal both with and without a target",
    "CAP-CLI-MODE-005": "--help and no-argument help are byte-identical",
    "CAP-CLI-MODE-006": "--version is byte-identical",
    "CAP-CLI-OUT-001": "the five-sample XML matrix has equal stdout and exit codes",
    "CAP-CLI-OUT-002": "all 15 normal scans have equal JSON detection trees",
    "CAP-CLI-OUT-003": "the five-sample CSV matrix and all-flags precedence are equal",
    "CAP-CLI-OUT-004": "the five-sample TSV matrix has equal stdout and exit codes",
    "CAP-CLI-OUT-005": "the five-sample plain-text matrix has equal stdout and exit codes",
    "CAP-CLI-DB-001": "the main database argument and reported path are equal",
    "CAP-CLI-DB-002": "the extra database argument and reported path are equal",
    "CAP-CLI-DB-003": "the custom database argument and reported path are equal",
    "CAP-CLI-DB-004": "--showdatabase output is byte-identical",
    "CAP-DISPATCH-001": "PE32/64, ELF32/64, Mach-O 32/64/FAT detection trees are equal",
    "CAP-DISPATCH-005": "DEX, Java Class, and PYC detection trees are equal",
    "CAP-DISPATCH-006": "the PDF and CFBF fixtures have equal detection trees",
    "CAP-DISPATCH-007": "JPEG, PNG, and generic Image/BMP detection trees are equal",
    "CAP-DISPATCH-008": "empty and plain binary fallback fixtures are equal",
    "CAP-NEST-001": "directory traversal and internal recursive-scan controls are both equal",
    "CAP-NEST-002": "resource and overlay recursive-scan gates have equal detection trees",
    "CAP-NEST-005": "overlay and resource subdevice gate controls have equal detection trees",
    "CAP-NEST-008": "all five nested formatter stdout streams, including the JSON tree, are equal",
    "CAP-RULE-008": "an empty valid database produces the same sole Unknown fallback",
    "CAP-RULE-010": "parse/runtime errors are collected with exact runtime-specific diagnostics",
}

PARTIAL: dict[str, str] = {
    "CAP-CLI-IN-003": "basic depth-first tree is covered; filesystem/locale/TOCTOU/large-directory boundaries remain",
    "CAP-DISPATCH-004": "TAR, gzip, and ZIP only; full archive family remains",
    "CAP-NEST-003": "CLI non-extraction is covered; the Qt6 engine archive option remains",
    "CAP-RULE-005": "five-sample deep/heuristic effects are covered; independent rule-gate controls remain",
    "CAP-RESULT-001": "CLI JSON exposes only a projection of scalar engine metadata",
    "CAP-RESULT-002": "rule probes expose errors, but not all four engine lists",
    "CAP-RESULT-003": "baseline JSON includes Unknown; heuristic flag combinations remain",
    "CAP-RESULT-004": "CLI trees expose parent structure, not the full engine identifier contract",
    "CAP-RESULT-005": "CLI JSON exposes string representations, not numeric enums",
    "CAP-RESULT-006": "HostApi probes cover rule metadata only partially",
}


def _same_stdout_and_exit(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return (
        left.get("exit_code") == right.get("exit_code")
        and left.get("stdout_sha256") == right.get("stdout_sha256")
        and left.get("stdout_bytes") == right.get("stdout_bytes")
    )


def _is_known_qt6_warning(
    left: dict[str, Any], right: dict[str, Any]
) -> bool:
    return (
        left.get("stderr_sha256") == EMPTY_SHA256
        and left.get("stderr_bytes") == 0
        and right.get("stderr_sha256") == QT6_UNIMPLEMENTED_SHA256
        and right.get("stderr_bytes") == 80
    )


def _validate_output_boundary_report(report: dict[str, Any]) -> None:
    if report.get("expected_revision") != UPSTREAM_COMMIT:
        raise ClosurePlanError("output-boundary revision drift")
    for side in ("left", "right"):
        if report.get(side, {}).get("image_revision") != UPSTREAM_COMMIT:
            raise ClosurePlanError(f"output-boundary {side} revision drift")
    cases = report.get("cases")
    if not isinstance(cases, list):
        raise ClosurePlanError("output-boundary cases must be an array")
    expected_ids = {
        f"{scope}_{formatter}"
        for scope in ("escaping", "nested")
        for formatter in ("json", "xml", "csv", "tsv", "plaintext")
    }
    if {case.get("id") for case in cases} != expected_ids:
        raise ClosurePlanError("output-boundary case catalog drift")
    expected_failures = {
        f"case.nested_{formatter}.oracle_difference"
        for formatter in ("json", "xml", "csv", "tsv", "plaintext")
    }
    if set(report.get("failures", [])) != expected_failures:
        raise ClosurePlanError("output-boundary failure catalog drift")
    if report.get("passed") is not False:
        raise ClosurePlanError("output-boundary must retain raw Qt6 warnings")
    facts = report.get("facts")
    if not isinstance(facts, dict) or not facts or not all(
        value is True for value in facts.values()
    ):
        raise ClosurePlanError("output-boundary semantic facts changed")
    for case in cases:
        left = case.get("left", {})
        right = case.get("right", {})
        if not _same_stdout_and_exit(left, right):
            raise ClosurePlanError(
                f"output-boundary semantic difference: {case.get('id')}"
            )
        if case["scope"] == "escaping":
            if case.get("oracles_equal") is not True:
                raise ClosurePlanError("escaping formatter difference")
        elif not (
            case.get("oracles_equal") is False
            and _is_known_qt6_warning(left, right)
        ):
            raise ClosurePlanError("unexpected nested formatter difference")


def _validate_paired_observation(
    record: dict[str, Any],
    expected_differences: set[tuple[str, ...]],
    label: str,
) -> tuple[str, ...]:
    left = record.get("left", {})
    right = record.get("right", {})
    if not _same_stdout_and_exit(left, right):
        raise ClosurePlanError(f"CLI matrix semantic difference: {label}")
    differences = tuple(record.get("differences", []))
    if differences not in expected_differences:
        raise ClosurePlanError(f"unexpected CLI matrix difference: {label}")
    if differences == ("stderr",) and not _is_known_qt6_warning(left, right):
        raise ClosurePlanError(f"unexpected CLI matrix stderr: {label}")
    return differences


def _validate_output_matrix_report(report: dict[str, Any]) -> None:
    if (
        report.get("expected_revision") != UPSTREAM_COMMIT
        or report.get("left_revision") != UPSTREAM_COMMIT
        or report.get("right_revision") != UPSTREAM_COMMIT
    ):
        raise ClosurePlanError("CLI output matrix revision drift")
    if report.get("equal") is not False:
        raise ClosurePlanError("CLI output matrix must retain raw Qt6 warnings")

    failures = {
        "corpus.minimal.exe.stderr",
        "corpus.minimal-pe64.exe.stderr",
        *{
            f"matrix.minimal.exe.output.{case}.stderr"
            for case in (
                "text",
                "plaintext",
                "json",
                "xml",
                "csv",
                "tsv",
                "all_output_flags",
            )
        },
    }
    if set(report.get("failures", [])) != failures:
        raise ClosurePlanError("CLI output matrix failure catalog drift")

    cases = report.get("cases")
    unreadable = report.get("unreadable_input")
    corpus = report.get("corpus")
    matrix = report.get("matrix")
    if not all(
        isinstance(value, dict)
        for value in (cases, unreadable, corpus, matrix)
    ):
        raise ClosurePlanError("CLI output matrix sections are missing")
    if len(corpus) != 26:
        raise ClosurePlanError("CLI output matrix corpus drift")
    expected_samples = {
        "empty.bin",
        "minimal.exe",
        "minimal.pdf",
        "payload.zip",
        "plain.txt",
    }
    if set(matrix) != expected_samples:
        raise ClosurePlanError("CLI output matrix sample catalog drift")
    expected_formatters = {
        "text",
        "plaintext",
        "json",
        "xml",
        "csv",
        "tsv",
        "all_output_flags",
    }

    observed_failures = set()
    for name, record in cases.items():
        differences = _validate_paired_observation(
            record, {()}, f"cases.{name}"
        )
        if differences:
            observed_failures.add(f"{name}.{differences[0]}")
    for name, record in unreadable.items():
        differences = _validate_paired_observation(
            record, {()}, f"unreadable_input.{name}"
        )
        if differences:
            observed_failures.add(
                f"unreadable_input.{name}.{differences[0]}"
            )
    for name, record in corpus.items():
        differences = _validate_paired_observation(
            record, {(), ("stderr",)}, f"corpus.{name}"
        )
        if differences:
            observed_failures.add(f"corpus.{name}.{differences[0]}")
        if record.get("left_detect_tree") != record.get("right_detect_tree"):
            raise ClosurePlanError(f"corpus detection tree difference: {name}")
    for sample, sample_record in matrix.items():
        output = sample_record.get("output")
        if not isinstance(output, dict) or set(output) != expected_formatters:
            raise ClosurePlanError(
                f"CLI output formatter catalog drift: {sample}"
            )
        for name, record in output.items():
            differences = _validate_paired_observation(
                record,
                {(), ("stderr",)},
                f"matrix.{sample}.output.{name}",
            )
            if differences:
                observed_failures.add(
                    f"matrix.{sample}.output.{name}.{differences[0]}"
                )
    if observed_failures != failures:
        raise ClosurePlanError("CLI output matrix derived failures drift")


def _validate_scan_nested_report(report: dict[str, Any]) -> None:
    if (
        report.get("expected_revision") != UPSTREAM_COMMIT
        or report.get("left_revision") != UPSTREAM_COMMIT
        or report.get("right_revision") != UPSTREAM_COMMIT
    ):
        raise ClosurePlanError("CLI scan/nested matrix revision drift")
    if report.get("equal") is not False:
        raise ClosurePlanError(
            "CLI scan/nested matrix must retain Qt6 differences"
        )
    cases = report.get("cases")
    unreadable = report.get("unreadable_input")
    corpus = report.get("corpus")
    matrix = report.get("matrix")
    nested = report.get("nested_corpus", {}).get("cases")
    if not all(
        isinstance(value, dict)
        for value in (cases, unreadable, corpus, matrix, nested)
    ):
        raise ClosurePlanError("CLI scan/nested matrix sections are missing")
    if len(corpus) != 26:
        raise ClosurePlanError("CLI scan/nested corpus drift")
    expected_samples = {
        "empty.bin",
        "minimal.exe",
        "minimal.pdf",
        "payload.zip",
        "plain.txt",
    }
    if set(matrix) != expected_samples:
        raise ClosurePlanError("CLI scan matrix sample catalog drift")
    expected_scan_cases = {
        "default",
        "deep",
        "heuristic",
        "aggressive",
        "alltypes",
        "format",
        "hideunknown",
        "combined",
    }
    expected_nested_samples = {
        "pdf-member.zip",
        "nested-zip.zip",
        "many-pdf-members.zip",
        "pe-pdf-overlay.exe",
        "pe-pdf-resource.exe",
        "pe-many-pdf-resources.exe",
        "pe-manifest-resource.exe",
        "pe-zip-overlay.exe",
    }
    if set(nested) != expected_nested_samples:
        raise ClosurePlanError("CLI nested sample catalog drift")
    expected_nested_cases = {
        "default",
        "recursive",
        "aggressive",
        "recursive_aggressive",
    }

    observed_failures = set()
    for name, record in cases.items():
        _validate_paired_observation(record, {()}, f"cases.{name}")
    for name, record in unreadable.items():
        _validate_paired_observation(
            record, {()}, f"unreadable_input.{name}"
        )
    for name, record in corpus.items():
        differences = _validate_paired_observation(
            record, {(), ("stderr",)}, f"corpus.{name}"
        )
        if differences:
            observed_failures.add(f"corpus.{name}.{differences[0]}")
        if record.get("left_detect_tree") != record.get("right_detect_tree"):
            raise ClosurePlanError(f"corpus detection tree difference: {name}")

    for sample, sample_record in matrix.items():
        scan = sample_record.get("scan")
        if not isinstance(scan, dict) or set(scan) != expected_scan_cases:
            raise ClosurePlanError(f"CLI scan case catalog drift: {sample}")
        for name, record in scan.items():
            label = f"matrix.{sample}.scan.{name}"
            differences = tuple(record.get("differences", []))
            if sample == "minimal.exe" and name in {
                "alltypes",
                "combined",
            }:
                if differences != ("stdout", "stderr"):
                    raise ClosurePlanError(
                        f"alltypes diagnostic difference drift: {label}"
                    )
                if not _is_known_qt6_warning(
                    record.get("left", {}), record.get("right", {})
                ):
                    raise ClosurePlanError(
                        f"alltypes stderr difference drift: {label}"
                    )
                if (
                    tuple(record.get("left_changes", []))
                    != ("stdout",)
                    or tuple(record.get("right_changes", []))
                    != ("stdout",)
                ):
                    raise ClosurePlanError(
                        f"alltypes relative effect drift: {label}"
                    )
            else:
                differences = _validate_paired_observation(
                    record, {(), ("stderr",)}, label
                )
                if record.get("left_changes") != record.get("right_changes"):
                    raise ClosurePlanError(
                        f"scan relative effect difference: {label}"
                    )
            for difference in differences:
                observed_failures.add(f"{label}.{difference}")

    for sample, sample_record in nested.items():
        if set(sample_record) != expected_nested_cases:
            raise ClosurePlanError(
                f"CLI nested case catalog drift: {sample}"
            )
        for name, record in sample_record.items():
            label = f"nested_corpus.{sample}.{name}"
            differences = _validate_paired_observation(
                record, {(), ("stderr",)}, label
            )
            if record.get("left_detect_tree") != record.get(
                "right_detect_tree"
            ):
                raise ClosurePlanError(
                    f"nested detection tree difference: {label}"
                )
            if record.get("left_changes") != record.get("right_changes"):
                raise ClosurePlanError(
                    f"nested relative effect difference: {label}"
                )
            for difference in differences:
                observed_failures.add(f"{label}.{difference}")
    if observed_failures != set(report.get("failures", [])):
        raise ClosurePlanError("CLI scan/nested derived failures drift")


def _validate_alltypes_diagnostics(report: dict[str, Any]) -> None:
    if report.get("upstream_commit") != UPSTREAM_COMMIT:
        raise ClosurePlanError("alltypes diagnostic revision drift")
    if report.get("passed") is not True:
        raise ClosurePlanError("alltypes diagnostic probe did not pass")
    facts = report.get("facts")
    if not isinstance(facts, dict) or not facts or not all(
        value is True for value in facts.values()
    ):
        raise ClosurePlanError("alltypes diagnostic facts changed")
    repetitions = report.get("repetitions")
    if not isinstance(repetitions, int) or repetitions < 2:
        raise ClosurePlanError("alltypes diagnostic repetitions drift")
    cases = report.get("cases")
    if not isinstance(cases, dict) or set(cases) != {
        "alltypes",
        "combined",
    }:
        raise ClosurePlanError("alltypes diagnostic case catalog drift")
    expected = report.get("expected_normalized_diagnostics")
    if not isinstance(expected, str) or "MSDOS_Script(<address>)" not in expected:
        raise ClosurePlanError("alltypes normalized diagnostic drift")
    for case_name, case in cases.items():
        observations = case.get("observations")
        if not isinstance(observations, dict) or set(observations) != {
            "qt5",
            "qt6",
        }:
            raise ClosurePlanError(
                f"alltypes oracle catalog drift: {case_name}"
            )
        qt5 = observations["qt5"]
        qt6 = observations["qt6"]
        if len(qt5) != repetitions or len(qt6) != repetitions:
            raise ClosurePlanError(
                f"alltypes repetition count drift: {case_name}"
            )
        baseline_document = qt5[0].get("json_document")
        for oracle_name, items in observations.items():
            for index, item in enumerate(items):
                label = f"{case_name}.{oracle_name}.{index}"
                try:
                    stdout = base64.b64decode(
                        item["stdout_base64"], validate=True
                    )
                    stderr = base64.b64decode(
                        item["stderr_base64"], validate=True
                    )
                except (KeyError, ValueError) as error:
                    raise ClosurePlanError(
                        f"invalid alltypes raw stream: {label}"
                    ) from error
                if (
                    len(stdout) != item.get("stdout_bytes")
                    or sha256(stdout) != item.get("stdout_sha256")
                    or len(stderr) != item.get("stderr_bytes")
                    or sha256(stderr) != item.get("stderr_sha256")
                ):
                    raise ClosurePlanError(
                        f"alltypes raw stream identity drift: {label}"
                    )
                if item.get("json_document") != baseline_document:
                    raise ClosurePlanError(
                        f"alltypes JSON difference: {label}"
                    )
                if oracle_name == "qt5":
                    if item.get("diagnostics") != "" or stderr != b"":
                        raise ClosurePlanError(
                            f"unexpected Qt5 alltypes diagnostic: {label}"
                        )
                elif (
                    item.get("normalized_diagnostics") != expected
                    or "0x" not in item.get("diagnostics", "")
                    or stderr != b"Unimplemented code.\n" * 4
                ):
                    raise ClosurePlanError(
                        f"unexpected Qt6 alltypes diagnostic: {label}"
                    )


def _validate_special_matrix_report(report: dict[str, Any]) -> None:
    if (
        report.get("expected_revision") != UPSTREAM_COMMIT
        or report.get("left_revision") != UPSTREAM_COMMIT
        or report.get("right_revision") != UPSTREAM_COMMIT
    ):
        raise ClosurePlanError("CLI special matrix revision drift")
    if report.get("equal") is not False:
        raise ClosurePlanError(
            "CLI special matrix must retain corpus Qt6 warnings"
        )
    cases = report.get("cases")
    unreadable = report.get("unreadable_input")
    corpus = report.get("corpus")
    matrix = report.get("matrix")
    if not all(
        isinstance(value, dict)
        for value in (cases, unreadable, corpus, matrix)
    ):
        raise ClosurePlanError("CLI special matrix sections are missing")
    if len(corpus) != 26:
        raise ClosurePlanError("CLI special matrix corpus drift")
    expected_samples = {
        "empty.bin",
        "minimal.exe",
        "minimal.pdf",
        "payload.zip",
        "plain.txt",
    }
    if set(matrix) != expected_samples:
        raise ClosurePlanError("CLI special matrix sample catalog drift")
    expected_cases = {
        "entropy_text",
        "entropy_plaintext",
        "entropy_json",
        "entropy_xml",
        "entropy_csv",
        "entropy_tsv",
        "entropy_all_output_flags",
        "info_text",
        "info_plaintext",
        "info_json",
        "info_xml",
        "info_csv",
        "info_tsv",
        "info_all_output_flags",
        "struct_hash_json",
        "struct_hash_md5_json",
        "struct_unknown_json",
        "entropy_over_info_struct_json",
        "struct_over_info_json",
    }
    observed_failures = set()
    for name, record in cases.items():
        _validate_paired_observation(record, {()}, f"cases.{name}")
    for name, record in unreadable.items():
        _validate_paired_observation(
            record, {()}, f"unreadable_input.{name}"
        )
    for name, record in corpus.items():
        differences = _validate_paired_observation(
            record, {(), ("stderr",)}, f"corpus.{name}"
        )
        if differences:
            observed_failures.add(f"corpus.{name}.{differences[0]}")
        if record.get("left_detect_tree") != record.get("right_detect_tree"):
            raise ClosurePlanError(f"corpus detection tree difference: {name}")
    for sample, sample_record in matrix.items():
        special = sample_record.get("special")
        if not isinstance(special, dict) or set(special) != expected_cases:
            raise ClosurePlanError(
                f"CLI special case catalog drift: {sample}"
            )
        for name, record in special.items():
            _validate_paired_observation(
                record, {()}, f"matrix.{sample}.special.{name}"
            )
    if observed_failures != set(report.get("failures", [])):
        raise ClosurePlanError("CLI special matrix derived failures drift")


def _validate_special_boundary_report(report: dict[str, Any]) -> None:
    if report.get("upstream_commit") != UPSTREAM_COMMIT:
        raise ClosurePlanError("CLI special boundary revision drift")
    if report.get("result") != "equal":
        raise ClosurePlanError("CLI special boundary result changed")
    cases = report.get("cases")
    expected_cases = {
        "dex_header_json",
        "elf_ehdr_json",
        "elf_entry_point_json",
        "entropy_above_json",
        "entropy_below_json",
        "entropy_exact_json",
        "entropy_exact_text",
        "entropy_over_struct_json",
        "entropy_two_json",
        "info_struct_empty_json",
        "info_two_json",
        "macho_entry_point_json",
        "macho_header_json",
        "pe_dos_header_json",
        "pe_entry_point_json",
        "pe_export_directory_json",
        "pe_nt_headers_json",
        "pe_resource_directory_json",
        "pe_section_header_json",
        "struct_check_format_json",
        "struct_empty_json",
        "struct_entropy_json",
        "struct_hash_empty_segment_json",
        "struct_hash_md5_casefold_json",
        "struct_hash_md5_trailing_json",
        "struct_hash_md5_two_json",
        "struct_hash_unknown_child_json",
        "struct_unknown_nested_json",
    }
    if (
        not isinstance(cases, dict)
        or set(cases) != expected_cases
        or report.get("case_count") != len(expected_cases)
    ):
        raise ClosurePlanError("CLI special boundary case catalog drift")
    if not all(
        case.get("all_oracles_equal") is True for case in cases.values()
    ):
        raise ClosurePlanError("CLI special boundary oracle difference")
    oracles = report.get("oracles")
    if (
        not isinstance(oracles, list)
        or [oracle.get("name") for oracle in oracles]
        != ["linux-qt5-cmake", "linux-qt6-cmake"]
        or any(
            oracle.get("revision") != UPSTREAM_COMMIT
            for oracle in oracles
        )
    ):
        raise ClosurePlanError("CLI special boundary oracle identity drift")
    relationships = report.get("relationships")
    if not isinstance(relationships, dict):
        raise ClosurePlanError("CLI special boundary relationships missing")
    if relationships.get("runtime_entropy_statuses") != {
        "below": "not packed",
        "exact": "not packed",
        "above": "packed",
    }:
        raise ClosurePlanError("CLI entropy boundary drift")
    required_true = (
        "struct_filter_is_case_insensitive",
        "struct_trailing_segments_are_ignored",
        "empty_struct_value_falls_back_to_normal_scan",
        "entropy_precedes_struct",
    )
    if not all(relationships.get(name) is True for name in required_true):
        raise ClosurePlanError("CLI struct/priority boundary drift")
    if len(relationships.get("format_struct_methods", {})) != 11:
        raise ClosurePlanError("CLI format struct method catalog drift")
    if set(relationships.get("multi_target_structured_outputs", {})) != {
        "entropy_two_json",
        "info_two_json",
        "struct_hash_md5_two_json",
    }:
        raise ClosurePlanError("CLI special multi-target catalog drift")
    source_audit = report.get("source_audit", {}).get("assumptions")
    if not isinstance(source_audit, dict) or not all(
        value is True for value in source_audit.values()
    ):
        raise ClosurePlanError("CLI special source audit drift")


def _validate_path_matrix_report(report: dict[str, Any]) -> None:
    if (
        report.get("expected_revision") != UPSTREAM_COMMIT
        or report.get("left_revision") != UPSTREAM_COMMIT
        or report.get("right_revision") != UPSTREAM_COMMIT
    ):
        raise ClosurePlanError("CLI path matrix revision drift")
    if report.get("equal") is not False:
        raise ClosurePlanError("CLI path matrix must retain Qt6 warnings")
    cases = report.get("cases")
    unreadable = report.get("unreadable_input")
    path_corpus = report.get("path_corpus")
    path_cases = (
        path_corpus.get("cases")
        if isinstance(path_corpus, dict)
        else None
    )
    if not all(
        isinstance(value, dict)
        for value in (cases, unreadable, path_corpus, path_cases)
    ):
        raise ClosurePlanError("CLI path matrix sections are missing")
    expected_cases = {
        "single_file_json",
        "two_files_json",
        "duplicate_file_json",
        "tree_json",
        "tree_recursive_json",
        "tree_xml",
        "tree_csv",
        "tree_plaintext",
        "tree_entropy_json",
        "tree_info_json",
        "single_directory_json",
        "empty_directory_json",
        "missing_and_existing_json",
        "directory_plus_duplicate_json",
    }
    if set(path_cases) != expected_cases:
        raise ClosurePlanError("CLI path case catalog drift")
    expected_failures = {
        f"path_corpus.{name}.stderr"
        for name in (
            "tree_json",
            "tree_recursive_json",
            "tree_xml",
            "tree_csv",
            "tree_plaintext",
            "directory_plus_duplicate_json",
        )
    }
    observed_failures = set()
    for name, record in cases.items():
        _validate_paired_observation(record, {()}, f"cases.{name}")
    for name, record in unreadable.items():
        _validate_paired_observation(
            record, {()}, f"unreadable_input.{name}"
        )
    for name, record in path_cases.items():
        label = f"path_corpus.{name}"
        differences = _validate_paired_observation(
            record, {(), ("stderr",)}, label
        )
        if differences:
            observed_failures.add(f"{label}.{differences[0]}")
        if record.get("left_filename_prefixes") != record.get(
            "right_filename_prefixes"
        ):
            raise ClosurePlanError(f"CLI path prefix difference: {name}")
        for format_name in ("json", "xml"):
            left_key = f"left_valid_{format_name}"
            right_key = f"right_valid_{format_name}"
            if left_key in record and record.get(left_key) != record.get(
                right_key
            ):
                raise ClosurePlanError(
                    f"CLI path {format_name} validity difference: {name}"
                )
        if "left_changes" in record and record.get(
            "left_changes"
        ) != record.get("right_changes"):
            raise ClosurePlanError(
                f"CLI path recursive effect difference: {name}"
            )
    if observed_failures != expected_failures or set(
        report.get("failures", [])
    ) != expected_failures:
        raise ClosurePlanError("CLI path failure catalog drift")
    if (
        path_corpus.get("generator")
        != "tools/corpus/generate_path_corpus.py"
        or len(path_corpus.get("directories", [])) != 5
        or len(path_corpus.get("entries", [])) != 5
    ):
        raise ClosurePlanError("CLI path fixture catalog drift")


def _validate_database_matrix_report(report: dict[str, Any]) -> None:
    if (
        report.get("expected_revision") != UPSTREAM_COMMIT
        or report.get("left_revision") != UPSTREAM_COMMIT
        or report.get("right_revision") != UPSTREAM_COMMIT
    ):
        raise ClosurePlanError("CLI database matrix revision drift")
    if report.get("equal") is not False:
        raise ClosurePlanError(
            "CLI database matrix must retain parse diagnostic difference"
        )
    cases = report.get("cases")
    unreadable = report.get("unreadable_input")
    fixture = report.get("database_fixture")
    database_cases = (
        fixture.get("cases") if isinstance(fixture, dict) else None
    )
    if not all(
        isinstance(value, dict)
        for value in (cases, unreadable, fixture, database_cases)
    ):
        raise ClosurePlanError("CLI database matrix sections are missing")
    expected_cases = {
        "show_database_missing_main",
        "show_database_missing_main_messages",
        "show_database_empty_main",
        "show_database_invalid_archive",
        "show_database_invalid_archive_messages",
        "show_database_malformed_main",
        "scan_missing_main_json",
        "scan_missing_main_messages_json",
        "scan_empty_main_json",
        "scan_invalid_archive_json",
        "scan_invalid_archive_messages_json",
        "scan_malformed_main_json",
        "scan_throwing_main_json",
        "scan_valid_main_json",
        "entropy_missing_main_messages_json",
        "info_missing_main_messages_json",
        "scan_valid_main_missing_extra_json",
        "show_database_valid_main_missing_extra",
    }
    if set(database_cases) != expected_cases:
        raise ClosurePlanError("CLI database case catalog drift")
    expected_failures = {
        "database_fixture.scan_malformed_main_json.stdout"
    }
    for name, record in cases.items():
        _validate_paired_observation(record, {()}, f"cases.{name}")
    for name, record in unreadable.items():
        _validate_paired_observation(
            record, {()}, f"unreadable_input.{name}"
        )
    for name, record in database_cases.items():
        label = f"database_fixture.{name}"
        differences = tuple(record.get("differences", []))
        if name == "scan_malformed_main_json":
            if (
                differences != ("stdout",)
                or record.get("left", {}).get("exit_code")
                != record.get("right", {}).get("exit_code")
                or record.get("left", {}).get("stderr_sha256")
                != record.get("right", {}).get("stderr_sha256")
            ):
                raise ClosurePlanError(
                    "CLI malformed database difference drift"
                )
        else:
            _validate_paired_observation(record, {()}, label)
        if record.get("left_reports_load_error") != record.get(
            "right_reports_load_error"
        ):
            raise ClosurePlanError(
                f"CLI database load-error difference: {name}"
            )
        if "left_valid_json" in record and record.get(
            "left_valid_json"
        ) != record.get("right_valid_json"):
            raise ClosurePlanError(
                f"CLI database JSON framing difference: {name}"
            )
    for name in (
        "show_database_missing_main_messages",
        "scan_missing_main_messages_json",
        "entropy_missing_main_messages_json",
        "info_missing_main_messages_json",
    ):
        if database_cases[name].get("left_reports_load_error") is not True:
            raise ClosurePlanError(
                f"CLI database message channel drift: {name}"
            )
    empty = database_cases["scan_empty_main_json"]
    if (
        empty["left"].get("stdout_sha256")
        != "83cbe006c9b24c93260312b75a213904e76b75b7fcdb17612c6640f37a20c78c"
        or empty["right"].get("stdout_sha256")
        != empty["left"].get("stdout_sha256")
    ):
        raise ClosurePlanError("CLI empty database fallback drift")
    if set(report.get("failures", [])) != expected_failures:
        raise ClosurePlanError("CLI database failure catalog drift")
    if (
        fixture.get("generator")
        != "tools/corpus/generate_database_fixture.py"
        or len(fixture.get("directories", [])) != 10
        or len(fixture.get("entries", [])) != 15
    ):
        raise ClosurePlanError("CLI database fixture catalog drift")


def _validate_database_diagnostics(report: dict[str, Any]) -> None:
    if report.get("upstream_commit") != UPSTREAM_COMMIT:
        raise ClosurePlanError("database diagnostic revision drift")
    if report.get("passed") is not True:
        raise ClosurePlanError("database diagnostic probe did not pass")
    facts = report.get("facts")
    if not isinstance(facts, dict) or not facts or not all(
        value is True for value in facts.values()
    ):
        raise ClosurePlanError("database diagnostic facts changed")
    repetitions = report.get("repetitions")
    if not isinstance(repetitions, int) or repetitions < 2:
        raise ClosurePlanError("database diagnostic repetitions drift")
    expected = {
        "malformed": {
            "qt5": (
                "broken.1.sg: Binary/broken.1.sg: 1: "
                "SyntaxError: Parse error\n\n"
            ),
            "qt6": (
                "broken.1.sg: Binary/broken.1.sg: 2: "
                "SyntaxError: Expected token `}'\n\n"
            ),
        },
        "throwing": {
            "qt5": (
                "throw.1.sg: Binary/throw.1.sg: 2: "
                "Error: database fixture\n\n"
            ),
            "qt6": (
                "throw.1.sg: Binary/throw.1.sg: 2: "
                "Error: database fixture\n\n"
            ),
        },
    }
    if report.get("expected_diagnostics") != expected:
        raise ClosurePlanError("database expected diagnostics drift")
    cases = report.get("cases")
    if not isinstance(cases, dict) or set(cases) != set(expected):
        raise ClosurePlanError("database diagnostic case catalog drift")
    for case_name, case in cases.items():
        observations = case.get("observations")
        if not isinstance(observations, dict) or set(observations) != {
            "qt5",
            "qt6",
        }:
            raise ClosurePlanError(
                f"database diagnostic oracle drift: {case_name}"
            )
        baseline = observations["qt5"][0].get("json_document")
        for oracle_name, items in observations.items():
            if len(items) != repetitions:
                raise ClosurePlanError(
                    f"database diagnostic repetition drift: {case_name}"
                )
            for index, item in enumerate(items):
                label = f"{case_name}.{oracle_name}.{index}"
                try:
                    stdout = base64.b64decode(
                        item["stdout_base64"], validate=True
                    )
                    stderr = base64.b64decode(
                        item["stderr_base64"], validate=True
                    )
                except (KeyError, ValueError) as error:
                    raise ClosurePlanError(
                        f"invalid database raw stream: {label}"
                    ) from error
                if (
                    len(stdout) != item.get("stdout_bytes")
                    or sha256(stdout) != item.get("stdout_sha256")
                    or len(stderr) != item.get("stderr_bytes")
                    or sha256(stderr) != item.get("stderr_sha256")
                ):
                    raise ClosurePlanError(
                        f"database raw stream identity drift: {label}"
                    )
                if (
                    item.get("json_document") != baseline
                    or item.get("diagnostics")
                    != expected[case_name][oracle_name]
                    or stderr != b""
                    or item.get("exit_code") != 0
                ):
                    raise ClosurePlanError(
                        f"database diagnostic semantic drift: {label}"
                    )


CAMPAIGNS: dict[str, dict[str, Any]] = {
    "cli_scan_baseline": {
        "fixture": "reuse baseline-corpus and scan-option-boundary fixtures",
        "harness": "run the pinned Qt5 and Qt6 CLI images with every scan-option vector",
        "assertions": [
            "exit code and normalized detection tree are equal",
            "raw stdout and stderr hashes are retained",
            "each documented option boundary has a named paired control",
        ],
    },
    "cli_path": {
        "fixture": "reuse path, special-path, filesystem, large-directory, TOCTOU, and locale fixtures",
        "harness": "port the fixed Linux Qt5 path probes to the pinned Qt6 CLI image",
        "assertions": [
            "target order, duplicate handling, and directory traversal are equal",
            "exit code and raw per-target framing are retained",
            "links, permissions, TOCTOU, locale, and large-directory controls are all executed",
        ],
    },
    "engine_contract": {
        "fixture": "reuse the 37-case engine-contract fixture and controls",
        "harness": "build and run an equivalent XScanEngine Qt6 harness",
        "assertions": [
            "memory, file, device, and subdevice result projections are equal",
            "read, seek, EOF, sequential, and invalid-range cases are equal",
            "sort, signature filter, cancellation, and fresh-state cases are equal",
        ],
    },
    "cli_options": {
        "fixture": "reuse CLI option and binary rule-order fixtures",
        "harness": "execute every short/long option and paired control on Qt5 and Qt6",
        "assertions": [
            "exit code and normalized detection output are equal",
            "message and profiling channels retain raw output before normalization",
            "no-op and malformed test-mode behaviors are exercised",
        ],
    },
    "cli_special": {
        "fixture": "reuse special-mode and boundary fixtures",
        "harness": "run entropy, info, struct, and showstructs matrices on Qt5 and Qt6",
        "assertions": [
            "all formatter and multi-target framing cases are equal",
            "floating-point and invalid/deep struct boundaries are equal",
            "format-specific PE/ELF/Mach-O/DEX struct methods are exercised",
        ],
    },
    "cli_control": {
        "fixture": "reuse control-mode arguments and no-target controls",
        "harness": "run help, version, missing-target, and no-argument cases",
        "assertions": [
            "exit codes are equal",
            "stdout and stderr hashes are equal",
            "target-independent control modes are tested with and without a target",
        ],
    },
    "cli_output": {
        "fixture": "reuse output-boundary fixture and five representative formats",
        "harness": "run XML, JSON, CSV, TSV, and plain output matrices",
        "assertions": [
            "raw bytes and parsed semantic projections are retained",
            "formatter precedence and multi-target framing are equal",
            "messages contamination and special-mode output are exercised",
        ],
    },
    "database": {
        "fixture": "reuse database layer, error, archive, and cache fixtures",
        "harness": "build Qt6 database-layer and cache harnesses plus CLI controls",
        "assertions": [
            "main, extra, and custom layer ordering is equal",
            "missing, malformed, archive, and cache behavior is equal",
            "showdatabase counts, paths, exit code, and raw streams are equal",
        ],
    },
    "rule_orchestration": {
        "fixture": "reuse rule-orchestration and scan-option fixtures",
        "harness": "run the full rule gate/order/init/error matrix under both script engines",
        "assertions": [
            "layer, priority, init, type, deep, heuristic, and fallback behavior is equal",
            "detections and diagnostics are compared separately",
            "each known Qt5/Qt6 diagnostic difference is explicit and reviewable",
        ],
    },
    "signature_path_filter": {
        "fixture": "reuse signature-path fixture",
        "harness": "build and run an equivalent private-path Qt6 harness",
        "assertions": [
            "absolute exact match and mismatch controls are equal",
            "case, dot-dot, basename, and empty public-entry behavior is equal",
            "raw records and errors are retained",
        ],
    },
    "debug_data_dispatch": {
        "fixture": "reuse debug-dispatch fixture and source-audit identity",
        "harness": "build and run an equivalent Qt6 debug-dispatch harness",
        "assertions": [
            "resource and debug enumerations are equal",
            "only resource candidates are scanner-dispatched",
            "positive resource and negative debug controls retain raw records",
        ],
    },
    "dispatch_source": {
        "fixture": "reuse every dispatch fixture named by the Qt5 evidence set",
        "harness": "build Qt6 variants of all public and private dispatch probes",
        "assertions": [
            "every format family and property-only or detector-only branch is exercised",
            "normalized detection records and raw diagnostics are compared",
            "archive adapters include positive, malformed, compressed, and boundary controls",
        ],
    },
    "nested_scan": {
        "fixture": "reuse nested, resource, archive-limit, iteration, adversarial, and structure fixtures",
        "harness": "build Qt6 nested/resource/archive harness variants",
        "assertions": [
            "CLI recursion and internal recursion gates are distinguished",
            "record-count, iteration, depth, and expanded-byte observations are equal",
            "parent tree, context propagation, subdevice gates, and raw errors are compared",
        ],
    },
    "result_model": {
        "fixture": "reuse engine result metadata/list/flag/id/enum fixtures",
        "harness": "build and run equivalent Qt6 result-model harnesses",
        "assertions": [
            "all scalar fields, lists, flags, IDs, enums, and rule metadata are projected",
            "stable fields are compared exactly and random IDs by declared invariants",
            "script-engine diagnostic differences remain separate from detection semantics",
        ],
    },
}


def _validate_inputs(
    traceability: dict[str, Any], reports: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    if traceability.get("schema_version") != 1:
        raise ClosurePlanError("unsupported traceability schema")
    if traceability.get("upstream_commit") != UPSTREAM_COMMIT:
        raise ClosurePlanError("traceability upstream commit drift")
    if traceability.get("rules_commit") != RULES_COMMIT:
        raise ClosurePlanError("traceability rules commit drift")
    capabilities = traceability.get("capabilities")
    if not isinstance(capabilities, list) or len(capabilities) != 68:
        raise ClosurePlanError("traceability must contain exactly 68 capabilities")
    ids = [item.get("id") for item in capabilities]
    if len(set(ids)) != len(ids):
        raise ClosurePlanError("duplicate capability id")
    evidence_sets = {item.get("evidence_set") for item in capabilities}
    if evidence_sets != set(CAMPAIGNS):
        raise ClosurePlanError(
            "Qt6 campaign catalog does not exactly match evidence sets"
        )
    known = set(COMPLETE) | set(PARTIAL)
    if not known <= set(ids):
        raise ClosurePlanError("Qt6 evidence catalog contains stale capability ids")

    cli = reports[REPORT_PATHS[0]]
    if (
        cli.get("expected_revision") != UPSTREAM_COMMIT
        or cli.get("left_revision") != UPSTREAM_COMMIT
        or cli.get("right_revision") != UPSTREAM_COMMIT
    ):
        raise ClosurePlanError("CLI comparison revision drift")
    for path in REPORT_PATHS[1:4]:
        report = reports[path]
        if report.get("upstream_commit") != UPSTREAM_COMMIT:
            raise ClosurePlanError(f"report upstream commit drift: {path}")
        if report.get("rules_commit") != RULES_COMMIT:
            raise ClosurePlanError(f"report rules commit drift: {path}")
    _validate_output_boundary_report(reports[REPORT_PATHS[4]])
    _validate_output_matrix_report(reports[REPORT_PATHS[5]])
    _validate_scan_nested_report(reports[REPORT_PATHS[6]])
    _validate_alltypes_diagnostics(reports[REPORT_PATHS[7]])
    _validate_special_matrix_report(reports[REPORT_PATHS[8]])
    _validate_special_boundary_report(reports[REPORT_PATHS[9]])
    _validate_path_matrix_report(reports[REPORT_PATHS[10]])
    _validate_database_matrix_report(reports[REPORT_PATHS[11]])
    _validate_database_diagnostics(reports[REPORT_PATHS[12]])
    return capabilities


def build_plan(
    traceability: dict[str, Any],
    traceability_bytes: bytes,
    reports: dict[str, dict[str, Any]],
    report_bytes: dict[str, bytes],
) -> dict[str, Any]:
    capabilities = _validate_inputs(traceability, reports)
    rows = []
    for capability in capabilities:
        capability_id = capability["id"]
        evidence_set = capability["evidence_set"]
        if capability_id in COMPLETE:
            status = "evidence_complete"
            observed_scope = COMPLETE[capability_id]
            missing_scope = None
            experiment = None
        elif capability_id in PARTIAL:
            status = "partial"
            observed_scope = PARTIAL[capability_id]
            missing_scope = (
                "execute the remaining Qt5 capability boundary under the "
                "pinned Qt6 oracle"
            )
            experiment = CAMPAIGNS[evidence_set]
        else:
            status = "missing"
            observed_scope = None
            missing_scope = (
                "no row-complete Qt6 runtime evidence is currently admitted"
            )
            experiment = CAMPAIGNS[evidence_set]
        rows.append(
            {
                "id": capability_id,
                "name": capability["name"],
                "evidence_set": evidence_set,
                "status": status,
                "observed_scope": observed_scope,
                "missing_scope": missing_scope,
                "proposed_experiment": experiment,
                "acceptance": (
                    "the full Linux Qt5 row boundary is executed against the "
                    "pinned Qt6 oracle; raw and normalized outputs are retained; "
                    "every difference is either zero or explicitly classified"
                ),
            }
        )

    counts = {
        state: sum(row["status"] == state for row in rows)
        for state in ("evidence_complete", "partial", "missing")
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "evaluated_on": EVALUATED_ON,
        "result": (
            "complete"
            if counts["partial"] == 0 and counts["missing"] == 0
            else "incomplete"
        ),
        "platform": PLATFORM,
        "upstream_commit": UPSTREAM_COMMIT,
        "rules_commit": RULES_COMMIT,
        "sources": {
            TRACEABILITY_PATH: sha256(traceability_bytes),
            **{path: sha256(report_bytes[path]) for path in REPORT_PATHS},
        },
        "known_differences": [
            {
                "source": REPORT_PATHS[0],
                "scope": "minimal.exe stderr",
                "semantic_detection_equal": True,
            },
            {
                "source": REPORT_PATHS[1],
                "scope": "global HostApi runtime",
                "difference_count": reports[REPORT_PATHS[1]][
                    "difference_count"
                ],
            },
            {
                "source": REPORT_PATHS[2],
                "scope": "HostApi arity diagnostics",
                "difference_count": reports[REPORT_PATHS[2]][
                    "difference_count"
                ],
            },
            {
                "source": REPORT_PATHS[3],
                "scope": "global typo diagnostics",
                "semantic_detection_equal": reports[REPORT_PATHS[3]][
                    "normalized_detections_equal"
                ],
            },
            {
                "source": REPORT_PATHS[4],
                "scope": "five nested formatter stderr streams",
                "difference_count": len(
                    reports[REPORT_PATHS[4]]["failures"]
                ),
                "stdout_and_exit_equal": True,
                "right_stderr_sha256": QT6_UNIMPLEMENTED_SHA256,
            },
            {
                "source": REPORT_PATHS[5],
                "scope": "PE32/PE64 baseline and PE32 seven-formatter stderr streams",
                "difference_count": len(
                    reports[REPORT_PATHS[5]]["failures"]
                ),
                "stdout_and_exit_equal": True,
                "right_stderr_sha256": QT6_UNIMPLEMENTED_SHA256,
            },
            {
                "source": REPORT_PATHS[6],
                "scope": "scan-option and nested gate raw streams",
                "difference_count": len(
                    reports[REPORT_PATHS[6]]["failures"]
                ),
                "detection_semantics_equal_except_trailing_diagnostics": True,
            },
            {
                "source": REPORT_PATHS[7],
                "scope": "alltypes and combined trailing diagnostics",
                "repetitions": reports[REPORT_PATHS[7]]["repetitions"],
                "json_documents_equal": True,
                "raw_streams_retained_before_address_normalization": True,
            },
            {
                "source": REPORT_PATHS[8],
                "scope": "five-sample special formatter and priority matrix",
                "special_case_difference_count": 0,
                "corpus_warning_difference_count": len(
                    reports[REPORT_PATHS[8]]["failures"]
                ),
            },
            {
                "source": REPORT_PATHS[9],
                "scope": "28-case special-mode exact boundary matrix",
                "difference_count": 0,
                "all_raw_streams_equal": True,
            },
            {
                "source": REPORT_PATHS[10],
                "scope": "14-case basic path and directory matrix",
                "difference_count": len(
                    reports[REPORT_PATHS[10]]["failures"]
                ),
                "stdout_exit_prefix_and_framing_equal": True,
            },
            {
                "source": REPORT_PATHS[11],
                "scope": "18-case database load/error/messages matrix",
                "difference_count": len(
                    reports[REPORT_PATHS[11]]["failures"]
                ),
                "only_malformed_parse_diagnostic_differs": True,
            },
            {
                "source": REPORT_PATHS[12],
                "scope": "malformed parse and runtime error diagnostics",
                "repetitions": reports[REPORT_PATHS[12]]["repetitions"],
                "json_documents_equal": True,
                "raw_streams_retained": True,
            },
        ],
        "rows": rows,
        "summary": {
            "capability_count": len(rows),
            **counts,
            "closure_required": counts["partial"] + counts["missing"],
            "all_capabilities_accounted_for": len(rows) == 68,
            "cap_gap_007_closed": counts["partial"] == counts["missing"] == 0,
        },
        "limitations": [
            "the plan classifies existing evidence; it does not promote Linux Qt6 platform coverage",
            "partial evidence cannot satisfy a capability row",
            "diagnostic differences are not normalized away from compatibility review",
            "the current Qt6 image and reports remain pinned to exact identities",
        ],
    }


def serialize(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--traceability",
        type=Path,
        default=root / TRACEABILITY_PATH,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root
        / "docs"
        / "research"
        / "data"
        / "qt6-capability-closure-plan.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[2]
    traceability, traceability_raw = load_json(args.traceability)
    reports: dict[str, dict[str, Any]] = {}
    raw_reports: dict[str, bytes] = {}
    for relative_path in REPORT_PATHS:
        reports[relative_path], raw_reports[relative_path] = load_json(
            root / relative_path
        )
    plan = build_plan(
        traceability,
        traceability_raw,
        reports,
        raw_reports,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(serialize(plan))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
