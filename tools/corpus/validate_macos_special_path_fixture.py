#!/usr/bin/env python3
"""Validate a non-admitted macOS special-path fixture candidate."""

from __future__ import annotations

import argparse
import errno
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path, PurePosixPath
from typing import Any

GENERATOR = "tools/corpus/generate_macos_special_path_fixture.py"
BASELINE_MANIFEST = "docs/research/data/baseline-corpus.json"


class ReportError(ValueError):
    """The special-path fixture candidate is inconsistent."""


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def require_object(value: Any, description: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReportError(f"{description} must be an object")
    return value


def load_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()

    def reject_duplicates(
        pairs: list[tuple[str, Any]],
    ) -> dict[str, Any]:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ReportError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw,
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda constant: (_ for _ in ()).throw(
                ReportError(
                    f"non-finite JSON constant: {constant}"
                )
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReportError(f"invalid JSON: {path}: {error}") from error
    if not isinstance(value, dict):
        raise ReportError("JSON root must be an object")
    return value, raw


def load_generator(root: Path) -> Any:
    path = root / GENERATOR
    spec = importlib.util.spec_from_file_location(
        "macos_special_path_fixture_generator_validation", path
    )
    if spec is None or spec.loader is None:
        raise ReportError("cannot load fixture generator")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _entry_map(
    entries: Any,
    generator: Any,
    source: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    if not isinstance(entries, list):
        raise ReportError("fixture entries must be an array")
    result = {}
    allowed = {
        case_id: relative
        for case_id, relative in generator.STABLE_ENTRIES
    }
    allowed[generator.CASE_ALIAS[0]] = generator.CASE_ALIAS[1]
    allowed[generator.UNICODE_ALIAS[0]] = generator.UNICODE_ALIAS[1]
    for entry in entries:
        item = require_object(entry, "fixture entry")
        if set(item) != {
            "id",
            "path",
            "directory_name_bytes_hex",
            "size",
            "sha256",
        }:
            raise ReportError("fixture entry fields changed")
        case_id = item["id"]
        if (
            not isinstance(case_id, str)
            or case_id in result
            or allowed.get(case_id) != item["path"]
            or not isinstance(item["directory_name_bytes_hex"], str)
            or len(item["directory_name_bytes_hex"]) % 2
            or item["size"] != source["size"]
            or item["sha256"] != source["sha256"]
        ):
            raise ReportError(f"fixture entry drift: {case_id!r}")
        try:
            bytes.fromhex(item["directory_name_bytes_hex"])
        except ValueError as error:
            raise ReportError(
                f"fixture entry name hex is invalid: {case_id}"
            ) from error
        result[case_id] = item
    return result


def _expected_inventory(
    entries: dict[str, dict[str, Any]],
    raw_attempts: list[dict[str, Any]],
    directories: tuple[str, ...],
) -> dict[str, set[str]]:
    result = {directory: set() for directory in directories}
    for entry in entries.values():
        relative = str(entry["path"])
        parent, _ = relative.rsplit("/", 1)
        result[parent].add(entry["directory_name_bytes_hex"])
    for attempt in raw_attempts:
        if attempt["created"]:
            result["nonutf8"].add(attempt["name_bytes_hex"])
    return result


def _validate_live_fixture(
    fixture_dir: Path,
    *,
    entries: dict[str, dict[str, Any]],
    raw_attempts: list[dict[str, Any]],
    observations: dict[str, Any],
    directory_inventory: dict[str, list[str]],
    generator: Any,
) -> None:
    for entry in entries.values():
        path = fixture_dir.joinpath(*str(entry["path"]).split("/"))
        raw = path.read_bytes()
        if (
            len(raw) != entry["size"]
            or sha256(raw) != entry["sha256"]
        ):
            raise ReportError(
                f"live fixture entry differs: {entry['id']}"
            )
    stable_paths = dict(generator.STABLE_ENTRIES)
    upper = fixture_dir.joinpath(
        *stable_paths[generator.CASE_ALIAS[2]].split("/")
    )
    lower = fixture_dir.joinpath(*generator.CASE_ALIAS[1].split("/"))
    lower_exists = lower.exists()
    lower_same = lower_exists and os.path.samefile(upper, lower)
    if (
        lower_exists is not True
        or lower_same
        is not observations["lowercase_alias_is_same_file"]
    ):
        raise ReportError("live final case-alias state drift")
    nfc = fixture_dir.joinpath(
        *stable_paths[generator.UNICODE_ALIAS[2]].split("/")
    )
    nfd = fixture_dir.joinpath(
        *generator.UNICODE_ALIAS[1].split("/")
    )
    nfd_exists = nfd.exists()
    nfd_same = nfd_exists and os.path.samefile(nfc, nfd)
    if (
        nfd_exists is not True
        or nfd_same
        is not observations["nfd_alias_is_same_file"]
    ):
        raise ReportError("live final Unicode-alias state drift")
    raw_root = os.fsencode(fixture_dir / "nonutf8")
    for attempt in raw_attempts:
        raw_path = (
            raw_root
            + b"/"
            + bytes.fromhex(attempt["name_bytes_hex"])
        )
        if os.path.exists(raw_path) is not attempt["created"]:
            raise ReportError("live raw-name observation drift")
    for directory in generator.DIRECTORIES:
        actual = generator._directory_inventory(
            fixture_dir.joinpath(*directory.split("/"))
        )
        if actual != directory_inventory[directory]:
            raise ReportError(
                f"live directory order drift: {directory}"
            )


def validate_report(
    report: dict[str, Any],
    *,
    report_path: Path,
    root: Path,
    live_fixture_dir: Path | None = None,
) -> None:
    if report_path != (
        report_path.parent / "special-path-fixture-candidate.json"
    ).resolve(strict=True):
        raise ReportError(
            "report must be bundle-local: "
            "special-path-fixture-candidate.json"
        )
    expected_root = {
        "schema_version",
        "result",
        "platform",
        "generator",
        "source",
        "fixture",
        "filesystem_observations",
        "admission",
        "limitations",
    }
    if set(report) != expected_root:
        raise ReportError("report root fields changed")
    generator = load_generator(root)
    if (
        report["schema_version"] != generator.SCHEMA_VERSION
        or report["result"] != "candidate"
        or report["platform"] != generator.PLATFORM
    ):
        raise ReportError("report identity drift")
    if report["generator"] != {
        "path": GENERATOR,
        "sha256": sha256((root / GENERATOR).read_bytes()),
        "validator_path": generator.VALIDATOR,
        "validator_sha256": sha256(Path(__file__).read_bytes()),
    }:
        raise ReportError("generator identity drift")

    manifest, manifest_raw = load_json(root / BASELINE_MANIFEST)
    matches = [
        sample
        for sample in manifest.get("samples", [])
        if sample.get("name") == generator.SOURCE_NAME
    ]
    if len(matches) != 1:
        raise ReportError("baseline minimal.pdf identity drift")
    sample = matches[0]
    expected_source = {
        "manifest": BASELINE_MANIFEST,
        "manifest_sha256": sha256(manifest_raw),
        "sample": generator.SOURCE_NAME,
        "size": sample["size"],
        "sha256": sample["sha256"],
    }
    if report["source"] != expected_source:
        raise ReportError("source identity drift")

    fixture = require_object(report["fixture"], "fixture")
    if set(fixture) != {
        "local_path",
        "directories",
        "entries",
        "raw_attempts",
        "directory_inventory_name_bytes_hex",
    }:
        raise ReportError("fixture fields changed")
    local_path = fixture["local_path"]
    if (
        not isinstance(local_path, str)
        or not PurePosixPath(local_path).is_absolute()
    ):
        raise ReportError("fixture local path must be absolute")
    if fixture["directories"] != list(generator.DIRECTORIES):
        raise ReportError("fixture directory set drift")
    observations = require_object(
        report["filesystem_observations"],
        "filesystem_observations",
    )
    expected_observation_fields = {
        "lowercase_alias_exists_after_upper_create",
        "lowercase_alias_is_same_file",
        "case_distinct_names_materialized",
        "nfd_alias_exists_after_nfc_create",
        "nfd_alias_is_same_file",
        "nfc_nfd_distinct_names_materialized",
    }
    if set(observations) != expected_observation_fields or not all(
        isinstance(value, bool) for value in observations.values()
    ):
        raise ReportError("filesystem observation fields changed")
    if (
        observations[
            "lowercase_alias_exists_after_upper_create"
        ]
        is not observations["lowercase_alias_is_same_file"]
        or observations["case_distinct_names_materialized"]
        is observations["lowercase_alias_is_same_file"]
        or observations["nfd_alias_exists_after_nfc_create"]
        is not observations["nfd_alias_is_same_file"]
        or observations["nfc_nfd_distinct_names_materialized"]
        is observations["nfd_alias_is_same_file"]
    ):
        raise ReportError("filesystem alias projection drift")

    entries = _entry_map(fixture["entries"], generator, expected_source)
    expected_ids = {
        case_id for case_id, _ in generator.STABLE_ENTRIES
    }
    if observations["case_distinct_names_materialized"]:
        expected_ids.add(generator.CASE_ALIAS[0])
    if observations["nfc_nfd_distinct_names_materialized"]:
        expected_ids.add(generator.UNICODE_ALIAS[0])
    if set(entries) != expected_ids:
        raise ReportError("fixture materialized entry set drift")

    raw_attempts = fixture["raw_attempts"]
    if not isinstance(raw_attempts, list) or len(raw_attempts) != len(
        generator.RAW_NAMES
    ):
        raise ReportError("raw-name attempt set drift")
    for attempt, expected_name in zip(
        raw_attempts, generator.RAW_NAMES, strict=True
    ):
        item = require_object(attempt, "raw-name attempt")
        if set(item) != {
            "name_bytes_hex",
            "created",
            "errno",
            "size",
            "sha256",
        } or item["name_bytes_hex"] != expected_name.hex():
            raise ReportError("raw-name attempt identity drift")
        if item["created"] is True:
            if (
                item["errno"] is not None
                or item["size"] != expected_source["size"]
                or item["sha256"] != expected_source["sha256"]
            ):
                raise ReportError("created raw-name projection drift")
        elif item["created"] is False:
            if (
                item["errno"]
                not in {
                    errno.EILSEQ,
                    errno.EINVAL,
                    errno.ENOTSUP,
                }
                or item["size"] is not None
                or item["sha256"] is not None
            ):
                raise ReportError("rejected raw-name projection drift")
        else:
            raise ReportError("raw-name created flag must be boolean")

    inventory = require_object(
        fixture["directory_inventory_name_bytes_hex"],
        "directory inventory",
    )
    if set(inventory) != set(generator.DIRECTORIES):
        raise ReportError("directory inventory roots drift")
    expected_inventory = _expected_inventory(
        entries, raw_attempts, generator.DIRECTORIES
    )
    for directory, expected_names in expected_inventory.items():
        names = inventory[directory]
        if (
            not isinstance(names, list)
            or not all(isinstance(name, str) for name in names)
            or len(names) != len(set(names))
            or set(names) != expected_names
        ):
            raise ReportError(
                f"directory inventory drift: {directory}"
            )

    if report["admission"] != {
        "fixture_admitted": False,
        "capability_rows_admitted": 0,
        "reason": generator.ADMISSION_REASON,
    }:
        raise ReportError("candidate must not admit capability evidence")
    if report["limitations"] != generator.LIMITATIONS:
        raise ReportError("limitations drift")
    if live_fixture_dir is not None:
        _validate_live_fixture(
            live_fixture_dir.resolve(strict=True),
            entries=entries,
            raw_attempts=raw_attempts,
            observations=observations,
            directory_inventory=inventory,
            generator=generator,
        )


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--fixture-dir", type=Path)
    parser.set_defaults(root=root)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report_path = args.report.resolve(strict=True)
        report = load_json(report_path)[0]
        validate_report(
            report,
            report_path=report_path,
            root=args.root.resolve(),
            live_fixture_dir=args.fixture_dir,
        )
    except (ReportError, OSError, ValueError) as error:
        print(
            f"macOS special-path fixture validation error: {error}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
