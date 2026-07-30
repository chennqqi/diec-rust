#!/usr/bin/env python3
"""Validate a non-admitted macOS Qt5 database-cache harness build."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import sys
from typing import Any


PLATFORM = "macos-x86_64-qt5"
BUILDER = "tools/upstream/build_macos_database_cache_harness.py"
ORACLE_VALIDATOR = "tools/upstream/validate_macos_qt5_oracle_report.py"


class ReportError(ValueError):
    """The harness build candidate is incomplete or inconsistent."""


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _load(root: Path, relative: str, name: str) -> Any:
    path = root / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ReportError(f"cannot load helper module: {relative}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def require_object(value: Any, description: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReportError(f"{description} must be an object")
    return value


def load_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()

    def reject_duplicates(
        pairs: list[tuple[str, Any]],
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
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
                ReportError(f"non-finite JSON constant: {constant}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReportError(f"invalid JSON: {path}: {error}") from error
    if not isinstance(value, dict):
        raise ReportError("report root must be an object")
    return value, raw


def _absolute_posix(value: Any, description: str) -> PurePosixPath:
    if (
        not isinstance(value, str)
        or not PurePosixPath(value).is_absolute()
        or "\\" in value
    ):
        raise ReportError(f"{description} is not absolute POSIX")
    return PurePosixPath(value)


def _raw_reference(
    value: Any,
    *,
    bundle: Path,
    expected_path: str,
    description: str,
) -> str:
    record = require_object(value, description)
    if set(record) != {"path", "bytes", "sha256"}:
        raise ReportError(f"{description} fields changed")
    if record["path"] != expected_path:
        raise ReportError(f"{description} path drift")
    path = (bundle / expected_path).resolve(strict=True)
    try:
        path.relative_to(bundle.resolve(strict=True))
    except ValueError as error:
        raise ReportError(f"{description} path escaped bundle") from error
    raw = path.read_bytes()
    if (
        record["bytes"] != len(raw)
        or record["sha256"] != sha256(raw)
    ):
        raise ReportError(f"{description} identity drift")
    return expected_path


def validate_macho_x86_64_executable(raw: bytes) -> None:
    if len(raw) < 32 or raw[:4] != b"\xcf\xfa\xed\xfe":
        raise ReportError("artifact is not a thin little-endian Mach-O 64")
    cpu_type = int.from_bytes(raw[4:8], "little")
    file_type = int.from_bytes(raw[12:16], "little")
    if cpu_type != 0x01000007 or file_type != 2:
        raise ReportError("artifact is not an x86_64 Mach-O executable")


def validate_report(
    report: dict[str, Any],
    *,
    report_path: Path,
    oracle_path: Path,
    artifact_path: Path,
    root: Path,
) -> None:
    bundle = report_path.parent
    builder = _load(
        root, BUILDER, "macos_database_cache_builder_validation"
    )
    if report_path != (
        bundle / builder.REPORT_NAME
    ).resolve(strict=True):
        raise ReportError(
            f"report must be bundle-local: {builder.REPORT_NAME}"
        )
    if oracle_path != (
        bundle / "oracle-candidate.json"
    ).resolve(strict=True):
        raise ReportError(
            "oracle report must be bundle-local: oracle-candidate.json"
        )
    if artifact_path != (
        bundle / builder.BINARY_NAME
    ).resolve(strict=True):
        raise ReportError(
            f"artifact must be bundle-local: {builder.BINARY_NAME}"
        )
    if set(report) != {
        "schema_version",
        "result",
        "platform",
        "generator",
        "oracle_report",
        "source",
        "qt",
        "cli",
        "build",
        "artifact",
        "local_paths",
        "admission",
        "limitations",
    }:
        raise ReportError("report root fields changed")
    if (
        report["schema_version"] != 1
        or report["result"] != "candidate"
        or report["platform"] != PLATFORM
    ):
        raise ReportError("report identity drift")
    if report["generator"] != builder.generator_bindings(root):
        raise ReportError("generator identity drift")

    oracle_validator = _load(
        root,
        ORACLE_VALIDATOR,
        "macos_oracle_validator_for_cache_build",
    )
    oracle = oracle_validator.load_report(oracle_path)
    oracle_validator.validate_report(oracle)
    if report["oracle_report"] != {
        "path": "oracle-candidate.json",
        "sha256": sha256(oracle_path.read_bytes()),
    }:
        raise ReportError("oracle report binding drift")
    if report["source"] != oracle["source"]:
        raise ReportError("source identity drift")
    expected_qt = {
        field: oracle["qt"][field]
        for field in (
            "version",
            "qmake_spec",
            "qmake_sha256",
            "qtcore_sha256",
            "qtscript_sha256",
        )
    }
    if report["qt"] != expected_qt:
        raise ReportError("Qt identity drift")
    if report["cli"] != {
        "relative_path": "build/release/diec",
        "size": oracle["artifact"]["size"],
        "sha256": oracle["artifact"]["sha256"],
    }:
        raise ReportError("CLI identity drift")

    local_paths = require_object(report["local_paths"], "local_paths")
    if set(local_paths) != {
        "source_dir",
        "qt_dir",
        "build_dir",
        "console_build_dir",
        "original_makefile",
        "patched_makefile",
        "local_artifact",
    }:
        raise ReportError("local path fields changed")
    parsed_paths = {
        field: _absolute_posix(value, f"local_paths.{field}")
        for field, value in local_paths.items()
    }
    for field in ("source_dir", "qt_dir", "build_dir"):
        if str(parsed_paths[field]) != oracle["local_paths"][field]:
            raise ReportError(f"oracle local path drift: {field}")
    build_dir = parsed_paths["build_dir"]
    console = build_dir / "console_source"
    if parsed_paths["console_build_dir"] != console:
        raise ReportError("console build path drift")
    if parsed_paths["original_makefile"] != console / "Makefile":
        raise ReportError("original makefile path drift")
    if parsed_paths["patched_makefile"] != (
        console / builder.PATCHED_MAKEFILE_NAME
    ):
        raise ReportError("patched makefile path drift")
    if parsed_paths["local_artifact"] != (
        console / builder.BINARY_NAME
    ):
        raise ReportError("local artifact path drift")

    build = require_object(report["build"], "build")
    if set(build) != {
        "system",
        "tool",
        "jobs",
        "elapsed_milliseconds",
        "console_makefile_sha256",
        "patched_makefile_sha256",
        "replacements",
        "inputs",
        "exit_code",
        "stdout",
        "stderr",
    }:
        raise ReportError("build fields changed")
    if (
        build["system"] != "patched-qmake-makefile"
        or build["tool"] != "make"
        or not isinstance(build["jobs"], int)
        or not 1 <= build["jobs"] <= 16
        or not isinstance(build["elapsed_milliseconds"], int)
        or build["elapsed_milliseconds"] < 0
        or build["exit_code"] != 0
    ):
        raise ReportError("build contract drift")
    inputs = require_object(build["inputs"], "build.inputs")
    expected_input_paths = {
        "console_makefile": (
            "build-input/database-cache-console.Makefile"
        ),
        "patched_makefile": (
            "build-input/database-cache-harness.Makefile"
        ),
        "shared_harness": (
            "build-input/database_cache_harness_main.cpp"
        ),
        "macos_adapter": (
            "build-input/database_cache_harness_macos_adapter.cpp"
        ),
    }
    if set(inputs) != set(expected_input_paths):
        raise ReportError("build input inventory drift")
    declared_inputs = set()
    input_raw = {}
    for field, relative in expected_input_paths.items():
        declared_inputs.add(
            _raw_reference(
                inputs[field],
                bundle=bundle,
                expected_path=relative,
                description=f"build.inputs.{field}",
            )
        )
        input_raw[field] = (bundle / relative).read_bytes()
    actual_inputs = {
        path.relative_to(bundle).as_posix()
        for path in (bundle / "build-input").rglob("*")
        if path.is_file()
    }
    if actual_inputs != declared_inputs:
        raise ReportError("build input file inventory differs from report")
    original_raw = input_raw["console_makefile"]
    expected_patched, replacements = builder.patch_qmake_makefile(
        original_raw, target=parsed_paths["local_artifact"]
    )
    if (
        build["console_makefile_sha256"] != sha256(original_raw)
        or build["patched_makefile_sha256"]
        != sha256(expected_patched)
        or build["replacements"] != replacements
        or input_raw["patched_makefile"] != expected_patched
    ):
        raise ReportError("patched qmake makefile identity drift")
    if input_raw["shared_harness"] != (
        root / builder.SHARED_HARNESS
    ).read_bytes():
        raise ReportError("shared harness input drift")
    if input_raw["macos_adapter"] != (
        root / builder.MACOS_ADAPTER
    ).read_bytes():
        raise ReportError("macOS adapter input drift")

    declared_raw = {
        _raw_reference(
            build["stdout"],
            bundle=bundle,
            expected_path=(
                "raw/database-cache-harness-build.stdout"
            ),
            description="build.stdout",
        ),
        _raw_reference(
            build["stderr"],
            bundle=bundle,
            expected_path=(
                "raw/database-cache-harness-build.stderr"
            ),
            description="build.stderr",
        ),
    }
    raw_root = bundle / "raw"
    actual_raw = {
        path.relative_to(bundle).as_posix()
        for path in raw_root.glob("database-cache-harness-build.*")
        if path.is_file()
    }
    if actual_raw != declared_raw:
        raise ReportError("build raw file inventory differs from report")

    artifact = require_object(report["artifact"], "artifact")
    artifact_raw = artifact_path.read_bytes()
    validate_macho_x86_64_executable(artifact_raw)
    if set(artifact) != {
        "path",
        "size",
        "sha256",
        "architectures",
        "file_description",
        "otool_l",
    }:
        raise ReportError("artifact fields changed")
    if (
        artifact["path"] != builder.BINARY_NAME
        or artifact["size"] != len(artifact_raw)
        or artifact["sha256"] != sha256(artifact_raw)
        or artifact["architectures"] != ["x86_64"]
        or not isinstance(artifact["file_description"], str)
        or "Mach-O" not in artifact["file_description"]
        or "x86_64" not in artifact["file_description"]
    ):
        raise ReportError("artifact identity drift")
    otool = artifact["otool_l"]
    if (
        not isinstance(otool, list)
        or not otool
        or otool[0] != f"{builder.BINARY_NAME}:"
        or not all(isinstance(line, str) for line in otool)
    ):
        raise ReportError("otool projection drift")
    dependencies = "\n".join(otool)
    for framework in ("QtCore.framework", "QtScript.framework"):
        if framework not in dependencies:
            raise ReportError(f"artifact dependency missing: {framework}")
    if report["admission"] != {
        "platform_admitted": False,
        "capability_rows_admitted": 0,
        "reason": builder.ADMISSION_REASON,
    }:
        raise ReportError("candidate must not admit capability evidence")
    if report["limitations"] != builder.LIMITATIONS:
        raise ReportError("build limitations drift")


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--oracle-report", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.set_defaults(root=root)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report_path = args.report.resolve(strict=True)
        oracle_path = args.oracle_report.resolve(strict=True)
        artifact_path = args.artifact.resolve(strict=True)
        report = load_json(report_path)[0]
        validate_report(
            report,
            report_path=report_path,
            oracle_path=oracle_path,
            artifact_path=artifact_path,
            root=args.root.resolve(),
        )
    except (ReportError, OSError, ValueError) as error:
        print(
            f"macOS database-cache harness build report error: {error}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
