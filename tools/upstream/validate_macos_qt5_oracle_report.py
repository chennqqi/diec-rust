#!/usr/bin/env python3
"""Validate a candidate macOS Qt5 DIE-engine CLI oracle identity report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any


UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
PLATFORM = "macos-x86_64-qt5"
EXPECTED_SOURCE_FILES = {
    ".github/workflows/builder.yml",
    "build.pri",
    "build_mac.sh",
    "console_source/console_source.pro",
    "die_source.pro",
}
SHA256_RE = re.compile(r"[0-9a-f]{64}")


class ReportError(ValueError):
    """The candidate report is incomplete or has drifted."""


def reject_duplicate_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ReportError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_report(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_bytes(),
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=lambda constant: (_ for _ in ()).throw(
                ReportError(f"non-finite JSON constant: {constant}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReportError(f"invalid JSON: {error}") from error
    if not isinstance(value, dict):
        raise ReportError("report root must be an object")
    return value


def require_sha256(value: Any, description: str) -> None:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise ReportError(f"invalid SHA-256: {description}")


def require_nonempty_strings(value: Any, description: str) -> None:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item for item in value)
    ):
        raise ReportError(f"missing string list: {description}")


def require_object(value: Any, description: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReportError(f"expected object: {description}")
    return value


def validate_report(report: dict[str, Any]) -> None:
    required_root = {
        "schema_version",
        "result",
        "platform",
        "source",
        "source_files",
        "host",
        "qt",
        "build",
        "artifact",
        "admission",
        "local_paths",
    }
    if set(report) != required_root:
        raise ReportError("report root fields changed")
    if (
        report["schema_version"] != 1
        or report["result"] != "candidate"
        or report["platform"] != PLATFORM
    ):
        raise ReportError("report identity drift")

    source = require_object(report["source"], "source")
    if (
        source.get("repository")
        != "https://github.com/horsicq/DIE-engine"
        or source.get("commit") != UPSTREAM_COMMIT
        or source.get("rules_commit") != RULES_COMMIT
        or source.get("recursive_submodule_count") != 58
        or source.get("tracked_files_clean_before_and_after") is not True
    ):
        raise ReportError("source identity drift")

    source_files = require_object(report["source_files"], "source_files")
    if set(source_files) != EXPECTED_SOURCE_FILES:
        raise ReportError("source file identity set drift")
    for path, digest in source_files.items():
        require_sha256(digest, path)

    host = require_object(report["host"], "host")
    if (
        not isinstance(host.get("uname"), str)
        or "x86_64" not in host["uname"]
        or not isinstance(host.get("cpu_brand"), str)
        or not host["cpu_brand"]
        or not isinstance(host.get("logical_cpu_count"), int)
        or host["logical_cpu_count"] < 1
        or not isinstance(host.get("cmake_version"), str)
        or not host["cmake_version"].startswith("cmake version ")
    ):
        raise ReportError("host identity incomplete")
    for field in (
        "sw_vers",
        "xcode_version",
        "clang_version",
    ):
        require_nonempty_strings(host.get(field), f"host.{field}")

    qt = require_object(report["qt"], "qt")
    if (
        qt.get("version") != "5.15.2"
        or qt.get("qmake_spec") != "macx-clang"
    ):
        raise ReportError("Qt identity drift")
    require_nonempty_strings(qt.get("qmake_version"), "qt.qmake_version")
    for field in (
        "qmake_sha256",
        "qtcore_sha256",
        "qtscript_sha256",
    ):
        require_sha256(qt.get(field), f"qt.{field}")

    build = require_object(report["build"], "build")
    if (
        build.get("system") != "qmake"
        or build.get("configuration") != "release"
        or build.get("targets")
        != [
            "sub-build_libs-make_first",
            "sub-console_source-make_first",
        ]
        or not isinstance(build.get("jobs"), int)
        or not 1 <= build["jobs"] <= 64
        or not isinstance(build.get("elapsed_seconds"), int)
        or build["elapsed_seconds"] < 0
    ):
        raise ReportError("build contract drift")

    artifact = require_object(report["artifact"], "artifact")
    if (
        not isinstance(artifact.get("size"), int)
        or artifact["size"] <= 0
        or artifact.get("architectures") != ["x86_64"]
        or not isinstance(artifact.get("file_description"), str)
        or "Mach-O" not in artifact["file_description"]
        or artifact.get("version_stdout") != "die 4.0.0"
        or artifact.get("version_exit_code") != 0
    ):
        raise ReportError("artifact identity incomplete")
    require_sha256(artifact.get("sha256"), "artifact.sha256")
    require_nonempty_strings(artifact.get("otool_l"), "artifact.otool_l")

    admission = require_object(report["admission"], "admission")
    if (
        admission.get("platform_admitted") is not False
        or not isinstance(admission.get("reason"), str)
        or not admission["reason"]
    ):
        raise ReportError("candidate must not admit the platform")

    local_paths = require_object(report["local_paths"], "local_paths")
    if set(local_paths) != {
        "source_dir",
        "qt_dir",
        "build_dir",
        "artifact",
    } or any(
        not isinstance(value, str) or not value
        for value in local_paths.values()
    ):
        raise ReportError("local path inventory incomplete")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = load_report(args.report)
    validate_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
