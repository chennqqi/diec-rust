#!/usr/bin/env python3
"""Validate a non-admitted macOS long-path filesystem fixture."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import sys
from typing import Any


GENERATOR = "tools/corpus/generate_macos_long_path_fixture.py"


class ReportError(ValueError):
    """The long-path fixture report is incomplete or inconsistent."""


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def reject_duplicate_keys(
    pairs: list[tuple[str, Any]]
) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ReportError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=lambda constant: (_ for _ in ()).throw(
                ReportError(
                    f"non-finite JSON constant: {constant}"
                )
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReportError(f"invalid JSON: {error}") from error
    if not isinstance(value, dict):
        raise ReportError("report root must be an object")
    return value, raw


def load_generator(root: Path) -> Any:
    path = root / GENERATOR
    spec = importlib.util.spec_from_file_location(
        "macos_long_path_fixture_generator_validation", path
    )
    if spec is None or spec.loader is None:
        raise ReportError("cannot load long-path fixture generator")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _expected_cases(
    generator: Any, fixture_path: PurePosixPath
) -> list[tuple[str, str, str, int]]:
    result = [
        (
            "control",
            "control",
            "control/target.pdf",
            len(f"{fixture_path}/control/target.pdf".encode("ascii")),
        )
    ]
    for boundary, value in (
        ("path_max", generator.XNU_PATH_MAX),
        ("max_long_path", generator.XNU_MAXLONGPATHLEN),
    ):
        for delta in generator.FULL_PATH_DELTAS:
            target = value + delta
            result.append(
                (
                    f"{boundary}_{delta:+d}",
                    "full_path",
                    generator.build_full_relative_path(
                        fixture_path, target
                    ),
                    target,
                )
            )
    for delta in generator.COMPONENT_DELTAS:
        target = generator.XNU_NAME_MAX + delta
        result.append(
            (
                f"name_max_{delta:+d}",
                "component",
                (
                    "components/"
                    + generator.build_component_name(target)
                ),
                target,
            )
        )
    return result


def validate_report(
    report: dict[str, Any],
    *,
    report_path: Path,
    root: Path,
    live_fixture_dir: Path | None = None,
) -> None:
    if report_path != (
        report_path.parent / "long-path-fixture-candidate.json"
    ).resolve(strict=True):
        raise ReportError(
            "report must be named long-path-fixture-candidate.json"
        )
    expected_root = {
        "schema_version",
        "result",
        "platform",
        "generator",
        "xnu_reference",
        "baseline",
        "filesystem_limits",
        "fixture",
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
        raise ReportError("fixture report identity drift")
    if report["generator"] != generator.generator_binding(root):
        raise ReportError("generator identity drift")
    if report["xnu_reference"] != {
        "repository": (
            "https://github.com/apple-oss-distributions/xnu"
        ),
        "commit": generator.XNU_COMMIT,
        "source": generator.XNU_SOURCE,
        "source_url": generator.XNU_SOURCE_URL,
        "source_sha256": generator.XNU_SOURCE_SHA256,
        "name_max": generator.XNU_NAME_MAX,
        "path_max": generator.XNU_PATH_MAX,
        "kernel_private_max_long_path": (
            generator.XNU_MAXLONGPATHLEN
        ),
    }:
        raise ReportError("XNU source binding drift")

    baseline_raw = (root / generator.BASELINE_MANIFEST).read_bytes()
    baseline_manifest = json.loads(baseline_raw)
    matches = [
        sample
        for sample in baseline_manifest["samples"]
        if sample["name"] == generator.SOURCE_NAME
    ]
    if len(matches) != 1:
        raise ReportError("baseline sample inventory drift")
    sample = matches[0]
    if report["baseline"] != {
        "manifest": generator.BASELINE_MANIFEST,
        "manifest_sha256": sha256(baseline_raw),
        "sample": generator.SOURCE_NAME,
        "payload_size": sample["size"],
        "payload_sha256": sample["sha256"],
    }:
        raise ReportError("baseline fixture binding drift")
    if report["filesystem_limits"] != {
        "pathconf_name_max": generator.XNU_NAME_MAX,
        "pathconf_path_max": generator.XNU_PATH_MAX,
    }:
        raise ReportError("runtime filesystem limit drift")

    fixture = report["fixture"]
    if not isinstance(fixture, dict) or set(fixture) != {
        "local_path",
        "local_path_bytes",
        "case_ids",
        "cases",
    }:
        raise ReportError("fixture fields changed")
    local_text = fixture["local_path"]
    if (
        not isinstance(local_text, str)
        or not PurePosixPath(local_text).is_absolute()
        or "\\" in local_text
    ):
        raise ReportError("fixture local path is not absolute POSIX")
    try:
        local_bytes = local_text.encode("ascii")
    except UnicodeEncodeError as error:
        raise ReportError("fixture local path is not ASCII") from error
    if fixture["local_path_bytes"] != len(local_bytes):
        raise ReportError("fixture local path byte count drift")
    expected = _expected_cases(
        generator, PurePosixPath(local_text)
    )
    expected_ids = [record[0] for record in expected]
    if fixture["case_ids"] != expected_ids:
        raise ReportError("fixture case ID order drift")
    cases = fixture["cases"]
    if not isinstance(cases, list) or len(cases) != len(expected):
        raise ReportError("fixture case inventory drift")
    for case, (case_id, kind, relative, target) in zip(
        cases, expected, strict=True
    ):
        if not isinstance(case, dict) or set(case) != {
            "id",
            "kind",
            "relative_path",
            "relative_bytes",
            "absolute_path",
            "absolute_bytes",
            "basename_bytes",
            "target_boundary",
            "target_bytes",
            "attempt",
            "payload_size",
            "payload_sha256",
        }:
            raise ReportError(f"fixture case fields changed: {case_id}")
        absolute = f"{local_text}/{relative}"
        basename_bytes = len(
            relative.rsplit("/", 1)[-1].encode("ascii")
        )
        boundary = (
            "control"
            if kind == "control"
            else (
                "name_max"
                if kind == "component"
                else case_id.rsplit("_", 1)[0]
            )
        )
        fixed = {
            "id": case_id,
            "kind": kind,
            "relative_path": relative,
            "relative_bytes": len(relative.encode("ascii")),
            "absolute_path": absolute,
            "absolute_bytes": len(absolute.encode("ascii")),
            "basename_bytes": basename_bytes,
            "target_boundary": boundary,
            "target_bytes": target,
        }
        for field, value in fixed.items():
            if case[field] != value:
                raise ReportError(
                    f"fixture case projection drift: {case_id}.{field}"
                )
        if kind == "full_path" and case["absolute_bytes"] != target:
            raise ReportError(f"full path length drift: {case_id}")
        if kind == "component" and basename_bytes != target:
            raise ReportError(f"component length drift: {case_id}")
        attempt = case["attempt"]
        if not isinstance(attempt, dict) or set(attempt) != {
            "created",
            "errno",
            "errno_name",
        }:
            raise ReportError(f"attempt fields changed: {case_id}")
        if not isinstance(attempt["created"], bool):
            raise ReportError(f"attempt created flag drift: {case_id}")
        if attempt["created"]:
            if attempt["errno"] is not None or (
                attempt["errno_name"] is not None
            ):
                raise ReportError(f"successful attempt errno: {case_id}")
            if (
                case["payload_size"] != sample["size"]
                or case["payload_sha256"] != sample["sha256"]
            ):
                raise ReportError(
                    f"successful attempt payload drift: {case_id}"
                )
        else:
            number = attempt["errno"]
            if (
                not isinstance(number, int)
                or number <= 0
                or not isinstance(attempt["errno_name"], str)
                or not attempt["errno_name"].startswith("E")
                or not attempt["errno_name"].replace("_", "").isalnum()
                or case["payload_size"] is not None
                or case["payload_sha256"] is not None
            ):
                raise ReportError(f"failed attempt drift: {case_id}")
    if not cases[0]["attempt"]["created"]:
        raise ReportError("control fixture must be created")
    if report["admission"] != {
        "platform_admitted": False,
        "capability_rows_admitted": 0,
        "reason": generator.ADMISSION_REASON,
    }:
        raise ReportError("fixture candidate must not admit evidence")
    if report["limitations"] != generator.LIMITATIONS:
        raise ReportError("fixture limitations drift")
    if live_fixture_dir is not None:
        try:
            generator.validate_live(report, live_fixture_dir)
        except generator.FixtureError as error:
            raise ReportError(str(error)) from error


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
        live = (
            args.fixture_dir.resolve(strict=True)
            if args.fixture_dir is not None
            else None
        )
        validate_report(
            report,
            report_path=report_path,
            root=args.root.resolve(),
            live_fixture_dir=live,
        )
    except (ReportError, OSError, ValueError) as error:
        print(
            f"macOS long-path fixture report error: {error}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
