#!/usr/bin/env python3
"""Validate and audit exact, evidence-bound compatibility waivers."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import sys
from typing import Any


AUDIT_SCHEMA_VERSION = 1
REGISTRY_SCHEMA_VERSION = 1
REPORT_SCHEMA_VERSION = 1

CLASSIFICATIONS = {
    "Semantic",
    "SafetyDeviation",
    "Unsupported",
}
WAIVABLE_FAILURE_KINDS = {
    "semantic_mismatch",
    "platform_behavior",
    "safety_limit",
    "unsupported_feature",
}
FORBIDDEN_FAILURE_KINDS = {
    "abi_ub",
    "crash",
    "data_race",
    "hang",
    "memory_safety",
    "panic",
    "silent_unknown_syntax",
    "unbounded_allocation",
}
GLOB_TOKENS = {"*", "?", "[", "]"}
HEX_40 = re.compile(r"^[0-9a-f]{40}$")
HEX_64 = re.compile(r"^[0-9a-f]{64}$")
ID_PATTERN = re.compile(r"^DIFF-[0-9]{4,}$")
DIFFERENCE_ID_PATTERN = re.compile(r"^D-[0-9]{4,}$")
CASE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
PLATFORM_PATTERN = re.compile(
    r"^[a-z0-9]+-[a-z0-9][a-z0-9_]*$"
)


class ValidationError(ValueError):
    """The registry or report is not structurally trustworthy."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(value: object) -> bytes:
    try:
        serialized = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise ValidationError(
            "difference values must be finite JSON values"
        ) from error
    return serialized.encode("utf-8")


def difference_fingerprint(difference: dict[str, object]) -> str:
    payload = {
        "case_id": difference["case_id"],
        "json_pointer": difference["json_pointer"],
        "classification": difference["classification"],
        "failure_kind": difference["failure_kind"],
        "left_raw_sha256": difference["left_raw_sha256"],
        "right_raw_sha256": difference["right_raw_sha256"],
        "upstream_value": difference["upstream_value"],
        "rust_value": difference["rust_value"],
    }
    return sha256_bytes(canonical_json(payload))


def require_object(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError(f"{field} must be an object")
    return value


def require_list(value: object, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValidationError(f"{field} must be an array")
    return value


def require_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} must be a non-empty string")
    return value


def require_positive_int(value: object, field: str) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 1
    ):
        raise ValidationError(f"{field} must be a positive integer")
    return value


def require_exact_keys(
    value: dict[str, Any],
    required: set[str],
    optional: set[str],
    field: str,
) -> None:
    missing = sorted(required - value.keys())
    extra = sorted(value.keys() - required - optional)
    if missing:
        raise ValidationError(
            f"{field} is missing fields: {', '.join(missing)}"
        )
    if extra:
        raise ValidationError(
            f"{field} has unknown fields: {', '.join(extra)}"
        )


def parse_date(value: object, field: str) -> dt.date:
    text = require_string(value, field)
    try:
        parsed = dt.date.fromisoformat(text)
    except ValueError as error:
        raise ValidationError(
            f"{field} must use YYYY-MM-DD"
        ) from error
    if parsed.isoformat() != text:
        raise ValidationError(f"{field} must use canonical YYYY-MM-DD")
    return parsed


def validate_sha256(value: object, field: str) -> str:
    text = require_string(value, field)
    if not HEX_64.fullmatch(text):
        raise ValidationError(
            f"{field} must be a lowercase SHA-256"
        )
    return text


def validate_case_id(value: object, field: str) -> str:
    text = require_string(value, field)
    if (
        not CASE_ID_PATTERN.fullmatch(text)
        or any(token in text for token in GLOB_TOKENS)
    ):
        raise ValidationError(
            f"{field} must be one exact case ID without wildcards"
        )
    return text


def validate_json_pointer(value: object, field: str) -> str:
    pointer = require_string(value, field)
    if (
        pointer == "/"
        or not pointer.startswith("/")
        or any(token in pointer for token in GLOB_TOKENS)
    ):
        raise ValidationError(
            f"{field} must be one non-root JSON Pointer without wildcards"
        )
    index = 0
    while index < len(pointer):
        if pointer[index] != "~":
            index += 1
            continue
        if (
            index + 1 >= len(pointer)
            or pointer[index + 1] not in {"0", "1"}
        ):
            raise ValidationError(
                f"{field} has an invalid JSON Pointer escape"
            )
        index += 2
    return pointer


def validate_reference(
    value: object,
    field: str,
    repo_root: pathlib.Path,
    prefix: str | None = None,
) -> str:
    reference = require_string(value, field)
    if "\\" in reference:
        raise ValidationError(f"{field} must use repository '/' paths")
    relative = pathlib.PurePosixPath(reference)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or not relative.parts
    ):
        raise ValidationError(f"{field} must be a safe repository path")
    if prefix is not None and not reference.startswith(prefix):
        raise ValidationError(f"{field} must start with {prefix}")
    resolved = repo_root.joinpath(*relative.parts).resolve()
    try:
        resolved.relative_to(repo_root)
    except ValueError as error:
        raise ValidationError(
            f"{field} escapes the repository"
        ) from error
    if not resolved.is_file():
        raise ValidationError(
            f"{field} does not exist: {reference}"
        )
    return reference


def validate_identity(
    value: object,
    field: str,
) -> dict[str, object]:
    identity = require_object(value, field)
    require_exact_keys(
        identity,
        {"platform", "upstream_commit", "rust_schema"},
        set(),
        field,
    )
    platform = require_string(
        identity["platform"],
        f"{field}.platform",
    )
    if (
        not PLATFORM_PATTERN.fullmatch(platform)
        or any(token in platform for token in GLOB_TOKENS)
    ):
        raise ValidationError(
            f"{field}.platform must name one exact platform"
        )
    upstream_commit = require_string(
        identity["upstream_commit"],
        f"{field}.upstream_commit",
    )
    if not HEX_40.fullmatch(upstream_commit):
        raise ValidationError(
            f"{field}.upstream_commit must be a lowercase 40-hex SHA"
        )
    rust_schema = require_positive_int(
        identity["rust_schema"],
        f"{field}.rust_schema",
    )
    return {
        "platform": platform,
        "upstream_commit": upstream_commit,
        "rust_schema": rust_schema,
    }


def validate_waiver(
    value: object,
    index: int,
    repo_root: pathlib.Path,
    as_of: dt.date,
) -> dict[str, object]:
    field = f"waivers[{index}]"
    waiver = require_object(value, field)
    base_required = {
        "id",
        "status",
        "case_id",
        "json_pointer",
        "classification",
        "failure_kind",
        "left_raw_sha256",
        "right_raw_sha256",
        "diff_fingerprint",
        "evidence",
        "decision",
        "owner",
        "reviewed_by",
        "reviewed_on",
        "expires",
        "removal_condition",
    }
    conditional = {
        "threat_analysis",
        "regression_test",
        "roadmap_phase",
        "exit_condition",
    }
    require_exact_keys(waiver, base_required, conditional, field)

    waiver_id = require_string(waiver["id"], f"{field}.id")
    if not ID_PATTERN.fullmatch(waiver_id):
        raise ValidationError(
            f"{field}.id must match DIFF- followed by at least 4 digits"
        )
    if waiver["status"] != "approved":
        raise ValidationError(
            f"{field}.status must be approved"
        )
    case_id = validate_case_id(
        waiver["case_id"],
        f"{field}.case_id",
    )
    json_pointer = validate_json_pointer(
        waiver["json_pointer"],
        f"{field}.json_pointer",
    )
    classification = require_string(
        waiver["classification"],
        f"{field}.classification",
    )
    if classification not in CLASSIFICATIONS:
        raise ValidationError(
            f"{field}.classification is not waivable"
        )
    failure_kind = require_string(
        waiver["failure_kind"],
        f"{field}.failure_kind",
    )
    if failure_kind in FORBIDDEN_FAILURE_KINDS:
        raise ValidationError(
            f"{field} attempts to waive forbidden {failure_kind}"
        )
    if failure_kind not in WAIVABLE_FAILURE_KINDS:
        raise ValidationError(
            f"{field}.failure_kind is unknown"
        )

    left_hash = validate_sha256(
        waiver["left_raw_sha256"],
        f"{field}.left_raw_sha256",
    )
    right_hash = validate_sha256(
        waiver["right_raw_sha256"],
        f"{field}.right_raw_sha256",
    )
    fingerprint = validate_sha256(
        waiver["diff_fingerprint"],
        f"{field}.diff_fingerprint",
    )
    evidence = validate_reference(
        waiver["evidence"],
        f"{field}.evidence",
        repo_root,
        "docs/research/",
    )
    decision = validate_reference(
        waiver["decision"],
        f"{field}.decision",
        repo_root,
        "docs/design/decisions/",
    )
    owner = require_string(waiver["owner"], f"{field}.owner")
    reviewed_by = require_string(
        waiver["reviewed_by"],
        f"{field}.reviewed_by",
    )
    reviewed_on = parse_date(
        waiver["reviewed_on"],
        f"{field}.reviewed_on",
    )
    expires = parse_date(
        waiver["expires"],
        f"{field}.expires",
    )
    if reviewed_on > as_of:
        raise ValidationError(
            f"{field}.reviewed_on is after the audit date"
        )
    if expires <= reviewed_on:
        raise ValidationError(
            f"{field}.expires must be after reviewed_on"
        )
    removal_condition = require_string(
        waiver["removal_condition"],
        f"{field}.removal_condition",
    )

    result = {
        "id": waiver_id,
        "status": "approved",
        "case_id": case_id,
        "json_pointer": json_pointer,
        "classification": classification,
        "failure_kind": failure_kind,
        "left_raw_sha256": left_hash,
        "right_raw_sha256": right_hash,
        "diff_fingerprint": fingerprint,
        "evidence": evidence,
        "decision": decision,
        "owner": owner,
        "reviewed_by": reviewed_by,
        "reviewed_on": reviewed_on.isoformat(),
        "expires": expires.isoformat(),
        "removal_condition": removal_condition,
    }

    if classification == "SafetyDeviation":
        for required_field, prefix in (
            ("threat_analysis", "docs/"),
            ("regression_test", "tools/tests/"),
        ):
            if required_field not in waiver:
                raise ValidationError(
                    f"{field}.{required_field} is required"
                )
            result[required_field] = validate_reference(
                waiver[required_field],
                f"{field}.{required_field}",
                repo_root,
                prefix,
            )
        if "roadmap_phase" in waiver or "exit_condition" in waiver:
            raise ValidationError(
                f"{field} has Unsupported-only fields"
            )
    elif classification == "Unsupported":
        for required_field in ("roadmap_phase", "exit_condition"):
            if required_field not in waiver:
                raise ValidationError(
                    f"{field}.{required_field} is required"
                )
        roadmap_phase = require_string(
            waiver["roadmap_phase"],
            f"{field}.roadmap_phase",
        )
        if not re.fullmatch(r"Phase [1-6]", roadmap_phase):
            raise ValidationError(
                f"{field}.roadmap_phase must be Phase 1 through Phase 6"
            )
        result["roadmap_phase"] = roadmap_phase
        result["exit_condition"] = require_string(
            waiver["exit_condition"],
            f"{field}.exit_condition",
        )
        if "threat_analysis" in waiver or "regression_test" in waiver:
            raise ValidationError(
                f"{field} has SafetyDeviation-only fields"
            )
    else:
        if conditional & waiver.keys():
            raise ValidationError(
                f"{field} has fields not allowed for Semantic"
            )
    return result


def validate_registry(
    value: object,
    repo_root: pathlib.Path,
    as_of: dt.date,
) -> dict[str, object]:
    registry = require_object(value, "registry")
    require_exact_keys(
        registry,
        {"schema_version", "registry_identity", "waivers"},
        set(),
        "registry",
    )
    if registry["schema_version"] != REGISTRY_SCHEMA_VERSION:
        raise ValidationError("unsupported registry schema_version")
    identity = validate_identity(
        registry["registry_identity"],
        "registry.registry_identity",
    )
    raw_waivers = require_list(registry["waivers"], "registry.waivers")
    waivers = [
        validate_waiver(item, index, repo_root, as_of)
        for index, item in enumerate(raw_waivers)
    ]
    ids = [str(item["id"]) for item in waivers]
    if len(ids) != len(set(ids)):
        raise ValidationError("waiver IDs must be unique")
    targets = [
        (item["case_id"], item["json_pointer"])
        for item in waivers
    ]
    if len(targets) != len(set(targets)):
        raise ValidationError(
            "each case_id/json_pointer target may have only one waiver"
        )
    return {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "registry_identity": identity,
        "waivers": waivers,
    }


def validate_difference(
    value: object,
    index: int,
    executed_cases: set[str],
) -> dict[str, object]:
    field = f"differences[{index}]"
    difference = require_object(value, field)
    required = {
        "id",
        "case_id",
        "json_pointer",
        "classification",
        "failure_kind",
        "left_raw_sha256",
        "right_raw_sha256",
        "upstream_value",
        "rust_value",
        "diff_fingerprint",
    }
    require_exact_keys(difference, required, set(), field)
    difference_id = require_string(difference["id"], f"{field}.id")
    if not DIFFERENCE_ID_PATTERN.fullmatch(difference_id):
        raise ValidationError(
            f"{field}.id must match D- followed by at least 4 digits"
        )
    case_id = validate_case_id(
        difference["case_id"],
        f"{field}.case_id",
    )
    if case_id not in executed_cases:
        raise ValidationError(
            f"{field}.case_id was not executed"
        )
    json_pointer = validate_json_pointer(
        difference["json_pointer"],
        f"{field}.json_pointer",
    )
    classification = require_string(
        difference["classification"],
        f"{field}.classification",
    )
    if classification not in CLASSIFICATIONS:
        raise ValidationError(
            f"{field}.classification is invalid"
        )
    failure_kind = require_string(
        difference["failure_kind"],
        f"{field}.failure_kind",
    )
    if failure_kind not in (
        WAIVABLE_FAILURE_KINDS | FORBIDDEN_FAILURE_KINDS
    ):
        raise ValidationError(f"{field}.failure_kind is unknown")
    normalized = {
        "id": difference_id,
        "case_id": case_id,
        "json_pointer": json_pointer,
        "classification": classification,
        "failure_kind": failure_kind,
        "left_raw_sha256": validate_sha256(
            difference["left_raw_sha256"],
            f"{field}.left_raw_sha256",
        ),
        "right_raw_sha256": validate_sha256(
            difference["right_raw_sha256"],
            f"{field}.right_raw_sha256",
        ),
        "upstream_value": difference["upstream_value"],
        "rust_value": difference["rust_value"],
    }
    claimed_fingerprint = validate_sha256(
        difference["diff_fingerprint"],
        f"{field}.diff_fingerprint",
    )
    computed_fingerprint = difference_fingerprint(normalized)
    if claimed_fingerprint != computed_fingerprint:
        raise ValidationError(
            f"{field}.diff_fingerprint does not match canonical content"
        )
    normalized["diff_fingerprint"] = computed_fingerprint
    return normalized


def validate_report(value: object) -> dict[str, object]:
    report = require_object(value, "report")
    require_exact_keys(
        report,
        {
            "report_schema",
            "run_identity",
            "executed_case_ids",
            "differences",
        },
        set(),
        "report",
    )
    if report["report_schema"] != REPORT_SCHEMA_VERSION:
        raise ValidationError("unsupported report_schema")
    identity = validate_identity(
        report["run_identity"],
        "report.run_identity",
    )
    raw_case_ids = require_list(
        report["executed_case_ids"],
        "report.executed_case_ids",
    )
    case_ids = [
        validate_case_id(
            case_id,
            f"report.executed_case_ids[{index}]",
        )
        for index, case_id in enumerate(raw_case_ids)
    ]
    if not case_ids:
        raise ValidationError("report must contain an executed case")
    if len(case_ids) != len(set(case_ids)):
        raise ValidationError("executed_case_ids must be unique")
    executed_cases = set(case_ids)
    raw_differences = require_list(
        report["differences"],
        "report.differences",
    )
    differences = [
        validate_difference(item, index, executed_cases)
        for index, item in enumerate(raw_differences)
    ]
    difference_ids = [str(item["id"]) for item in differences]
    if len(difference_ids) != len(set(difference_ids)):
        raise ValidationError("difference IDs must be unique")
    targets = [
        (item["case_id"], item["json_pointer"])
        for item in differences
    ]
    if len(targets) != len(set(targets)):
        raise ValidationError(
            "each case_id/json_pointer may have only one difference"
        )
    return {
        "report_schema": REPORT_SCHEMA_VERSION,
        "run_identity": identity,
        "executed_case_ids": case_ids,
        "differences": differences,
    }


def waiver_matches(
    waiver: dict[str, object],
    difference: dict[str, object],
) -> bool:
    fields = (
        "case_id",
        "json_pointer",
        "classification",
        "failure_kind",
        "left_raw_sha256",
        "right_raw_sha256",
        "diff_fingerprint",
    )
    return all(
        waiver[field] == difference[field]
        for field in fields
    )


def audit_waivers(
    registry: dict[str, object],
    report: dict[str, object],
    as_of: dt.date,
    registry_sha256: str,
    report_sha256: str,
    input_files_unchanged: bool = True,
) -> dict[str, object]:
    if registry["registry_identity"] != report["run_identity"]:
        raise ValidationError(
            "registry_identity does not match report.run_identity"
        )

    differences = report["differences"]
    waivers = registry["waivers"]
    assert isinstance(differences, list)
    assert isinstance(waivers, list)
    executed_cases = set(report["executed_case_ids"])

    applied = []
    applied_difference_ids = set()
    expired_waivers = []
    stale_waivers = []
    unmatched_waivers = []
    forbidden_waiver_attempts = []

    for waiver in waivers:
        assert isinstance(waiver, dict)
        waiver_id = str(waiver["id"])
        if as_of >= dt.date.fromisoformat(str(waiver["expires"])):
            expired_waivers.append(waiver_id)
            continue
        if waiver["case_id"] not in executed_cases:
            unmatched_waivers.append(waiver_id)
            continue
        matches = [
            difference
            for difference in differences
            if waiver_matches(waiver, difference)
        ]
        if not matches:
            stale_waivers.append(waiver_id)
            continue
        if len(matches) != 1:
            raise ValidationError(
                f"{waiver_id} matched more than one difference"
            )
        difference = matches[0]
        assert isinstance(difference, dict)
        if difference["failure_kind"] in FORBIDDEN_FAILURE_KINDS:
            forbidden_waiver_attempts.append(waiver_id)
            continue
        difference_id = str(difference["id"])
        applied.append(
            {
                "waiver_id": waiver_id,
                "difference_id": difference_id,
            }
        )
        applied_difference_ids.add(difference_id)

    unmatched_differences = [
        str(difference["id"])
        for difference in differences
        if str(difference["id"]) not in applied_difference_ids
    ]
    failures = []
    for name, values in (
        ("unmatched_differences", unmatched_differences),
        ("expired_waivers", expired_waivers),
        ("stale_waivers", stale_waivers),
        ("unmatched_waivers", unmatched_waivers),
        ("forbidden_waiver_attempts", forbidden_waiver_attempts),
    ):
        if values:
            failures.append(name)
    if not input_files_unchanged:
        failures.append("input_files_changed")

    return {
        "audit_schema": AUDIT_SCHEMA_VERSION,
        "as_of": as_of.isoformat(),
        "run_identity": report["run_identity"],
        "input_sha256": {
            "registry": registry_sha256,
            "report": report_sha256,
        },
        "input_files_unchanged": input_files_unchanged,
        "applied": applied,
        "unmatched_differences": unmatched_differences,
        "expired_waivers": expired_waivers,
        "stale_waivers": stale_waivers,
        "unmatched_waivers": unmatched_waivers,
        "forbidden_waiver_attempts": forbidden_waiver_attempts,
        "failures": failures,
        "result": "pass" if not failures else "fail",
    }


def load_json_bytes(
    path: pathlib.Path,
    field: str,
) -> tuple[object, bytes]:
    try:
        data = path.read_bytes()
    except OSError as error:
        raise ValidationError(f"cannot read {field}: {error}") from error
    try:
        def reject_duplicates(
            pairs: list[tuple[str, object]],
        ) -> dict[str, object]:
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValidationError(
                        f"{field} contains duplicate key: {key}"
                    )
                result[key] = value
            return result

        def reject_constant(constant: str) -> object:
            raise ValidationError(
                f"{field} contains non-finite number: {constant}"
            )

        return (
            json.loads(
                data,
                object_pairs_hook=reject_duplicates,
                parse_constant=reject_constant,
            ),
            data,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError(f"{field} is not valid UTF-8 JSON") from error


def serialize_audit(audit: dict[str, object]) -> str:
    return (
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True, type=pathlib.Path)
    parser.add_argument("--report", required=True, type=pathlib.Path)
    parser.add_argument(
        "--as-of",
        required=True,
        help="Deterministic audit date in YYYY-MM-DD form",
    )
    parser.add_argument(
        "--repo-root",
        type=pathlib.Path,
        default=pathlib.Path(__file__).resolve().parents[2],
    )
    parser.add_argument("--output", type=pathlib.Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    registry_path = args.registry.resolve()
    report_path = args.report.resolve()
    output_path = args.output.resolve() if args.output else None
    if output_path in {registry_path, report_path}:
        raise SystemExit("output must not overwrite an input")

    as_of = None
    try:
        as_of = parse_date(args.as_of, "--as-of")
        repo_root = args.repo_root.resolve()
        registry_value, registry_bytes = load_json_bytes(
            registry_path,
            "registry",
        )
        report_value, report_bytes = load_json_bytes(
            report_path,
            "report",
        )
        registry_hash = sha256_bytes(registry_bytes)
        report_hash = sha256_bytes(report_bytes)
        registry = validate_registry(
            registry_value,
            repo_root,
            as_of,
        )
        report = validate_report(report_value)
        input_files_unchanged = (
            registry_path.read_bytes() == registry_bytes
            and report_path.read_bytes() == report_bytes
        )
        audit = audit_waivers(
            registry,
            report,
            as_of,
            registry_hash,
            report_hash,
            input_files_unchanged,
        )
        exit_code = 0 if audit["result"] == "pass" else 1
    except (OSError, ValidationError) as error:
        audit = {
            "audit_schema": AUDIT_SCHEMA_VERSION,
            "as_of": None if as_of is None else as_of.isoformat(),
            "errors": [str(error)],
            "result": "infrastructure_error",
        }
        exit_code = 2

    serialized = serialize_audit(audit)
    if output_path is None:
        sys.stdout.write(serialized)
    else:
        output_path.write_text(
            serialized,
            encoding="utf-8",
            newline="\n",
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
