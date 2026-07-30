#!/usr/bin/env python3
"""Validate a macOS root, ACL, and ownership CLI candidate report."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import sys
from typing import Any

PLATFORM = "macos-x86_64-qt5"
COLLECTOR = "tools/upstream/collect_macos_cli_privilege_paths.py"
BASELINE_COLLECTOR = "tools/upstream/collect_macos_cli_baseline.py"
BASELINE_VALIDATOR = "tools/upstream/validate_macos_cli_baseline.py"
ORACLE_VALIDATOR = "tools/upstream/validate_macos_qt5_oracle_report.py"


class ReportError(ValueError):
    """The privilege-path report is incomplete or inconsistent."""


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load(root: Path, relative: str, name: str):
    path = root / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ReportError(f"cannot load helper: {relative}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReportError(f"expected object: {label}")
    return value


def require_command_record(
    value: Any,
    label: str,
    *,
    require_success: bool = True,
) -> dict[str, Any]:
    record = require_object(value, label)
    if set(record) != {"exit_code", "stdout", "stderr"}:
        raise ReportError(f"command record fields changed: {label}")
    if (
        not isinstance(record["exit_code"], int)
        or not isinstance(record["stdout"], str)
        or not isinstance(record["stderr"], str)
    ):
        raise ReportError(f"command record types changed: {label}")
    if require_success and record["exit_code"] != 0:
        raise ReportError(f"command record did not succeed: {label}")
    return record


def validate_snapshot(
    snapshot: Any,
    target: Any,
    *,
    runner_uid: int,
    runner_gid: int,
    username: str,
    payload_size: int,
) -> dict[str, Any]:
    value = require_object(snapshot, f"snapshot {target.name}")
    expected_fields = {
        "relative_path",
        "kind",
        "owner",
        "uid",
        "gid",
        "mode",
        "size",
        "acl_kind",
        "acl_listing",
    }
    if set(value) != expected_fields:
        raise ReportError(f"snapshot fields changed: {target.name}")
    expected_uid = 0 if target.owner == "root" else runner_uid
    expected_gid = 0 if target.owner == "root" else runner_gid
    if (
        value["relative_path"] != target.relative
        or value["kind"] != target.kind
        or value["owner"] != target.owner
        or value["uid"] != expected_uid
        or value["gid"] != expected_gid
        or value["mode"] != f"{target.mode:04o}"
        or value["acl_kind"] != target.acl_kind
        or not isinstance(value["size"], int)
        or not isinstance(value["acl_listing"], str)
    ):
        raise ReportError(f"snapshot identity drift: {target.name}")
    if target.kind == "file":
        if value["size"] != payload_size:
            raise ReportError(f"snapshot payload size drift: {target.name}")
    elif value["size"] <= 0:
        raise ReportError(f"directory snapshot size drift: {target.name}")
    if target.acl_kind is not None:
        rights = (
            "read"
            if target.acl_kind == "deny_read"
            else "list,search"
        )
        if username not in value["acl_listing"] or (
            f"deny {rights}" not in value["acl_listing"]
        ):
            raise ReportError(f"ACL listing drift: {target.name}")
    return value


def validate_report(
    report: dict[str, Any],
    *,
    report_path: Path,
    oracle_path: Path,
    baseline_path: Path,
    root: Path,
) -> None:
    bundle = report_path.parent
    if report_path != (
        bundle / "cli-privilege-path-candidate.json"
    ).resolve(strict=True):
        raise ReportError(
            "report must be bundle-local: "
            "cli-privilege-path-candidate.json"
        )
    for path, name in (
        (oracle_path, "oracle-candidate.json"),
        (baseline_path, "cli-baseline-candidate.json"),
    ):
        if path != (bundle / name).resolve(strict=True):
            raise ReportError(f"input report must be bundle-local: {name}")
    expected_root = {
        "schema_version",
        "result",
        "platform",
        "generator",
        "oracle_report",
        "cli_baseline_report",
        "source",
        "qt",
        "binary",
        "fixture",
        "local_paths",
        "selection",
        "cases",
        "relationships",
        "summary",
        "admission",
        "limitations",
    }
    if set(report) != expected_root:
        raise ReportError("report root fields changed")
    if (
        report["schema_version"] != 1
        or report["result"] != "candidate"
        or report["platform"] != PLATFORM
    ):
        raise ReportError("report identity drift")

    collector = _load(
        root, COLLECTOR, "macos_privilege_path_collector_validation"
    )
    baseline_collector = _load(
        root,
        BASELINE_COLLECTOR,
        "macos_baseline_collector_privilege_path_validation",
    )
    baseline_validator = _load(
        root,
        BASELINE_VALIDATOR,
        "macos_baseline_validator_privilege_path_validation",
    )
    oracle_validator = _load(
        root,
        ORACLE_VALIDATOR,
        "macos_oracle_validator_privilege_path_validation",
    )
    common = baseline_collector.load_module(
        "windows_cli_common_privilege_path_validation",
        root / baseline_collector.SHARED_COLLECTOR,
    )
    if report["generator"] != collector._generator_bindings(root):
        raise ReportError("generator identity drift")

    oracle = oracle_validator.load_report(oracle_path)
    oracle_validator.validate_report(oracle)
    if report["oracle_report"] != {
        "path": "oracle-candidate.json",
        "sha256": sha256(oracle_path.read_bytes()),
    }:
        raise ReportError("oracle report binding drift")
    baseline_report = baseline_validator.load_json(baseline_path)[0]
    baseline_validator.validate_report(
        baseline_report,
        report_path=baseline_path,
        oracle_path=oracle_path,
        root=root,
    )
    if report["cli_baseline_report"] != {
        "path": "cli-baseline-candidate.json",
        "sha256": sha256(baseline_path.read_bytes()),
    }:
        raise ReportError("CLI baseline binding drift")
    if report["source"] != baseline_report["source"]:
        raise ReportError("source identity drift")
    if report["qt"] != baseline_report["qt"]:
        raise ReportError("Qt identity drift")
    if report["binary"] != baseline_report["binary"]:
        raise ReportError("binary identity drift")

    manifest, manifest_raw = baseline_validator.load_json(
        root / collector.BASELINE_MANIFEST
    )
    records = {
        record["name"]: record for record in manifest["samples"]
    }
    payload = records[collector.MINIMAL_PDF]
    fixture = require_object(report["fixture"], "fixture")
    expected_fixture_fields = {
        "manifest",
        "manifest_sha256",
        "payload",
        "runner",
        "tool_paths",
        "sudo_probe",
        "mutations",
        "targets",
        "database_archives",
        "runtime_directories",
        "runtime_artifacts",
        "cleanup",
    }
    if set(fixture) != expected_fixture_fields:
        raise ReportError("fixture fields changed")
    if (
        fixture["manifest"] != collector.BASELINE_MANIFEST
        or fixture["manifest_sha256"] != sha256(manifest_raw)
        or fixture["payload"] != payload
    ):
        raise ReportError("fixture payload binding drift")
    runner = require_object(fixture["runner"], "fixture.runner")
    if set(runner) != {"uid", "gid", "username"}:
        raise ReportError("runner identity fields changed")
    if (
        not isinstance(runner["uid"], int)
        or runner["uid"] <= 0
        or not isinstance(runner["gid"], int)
        or runner["gid"] < 0
        or not isinstance(runner["username"], str)
        or not runner["username"]
        or "\n" in runner["username"]
    ):
        raise ReportError("runner identity drift")
    tool_paths = require_object(
        fixture["tool_paths"], "fixture.tool_paths"
    )
    expected_static_tools = {
        "sudo": str(collector.SUDO),
        "id": str(collector.ID),
        "chmod": str(collector.CHMOD),
        "chown": str(collector.CHOWN),
        "ls": str(collector.LS),
        "root_exec_helper": collector.ROOT_EXEC_HELPER,
    }
    if set(tool_paths) != {*expected_static_tools, "python"}:
        raise ReportError("Darwin tool paths drift")
    for field, expected in expected_static_tools.items():
        if tool_paths[field] != expected:
            raise ReportError(f"Darwin tool path drift: {field}")
    python_path = tool_paths["python"]
    if (
        not isinstance(python_path, str)
        or not PurePosixPath(python_path).is_absolute()
        or not PurePosixPath(python_path).name.startswith("python3")
    ):
        raise ReportError("Darwin Python path drift")
    sudo_probe = require_command_record(
        fixture["sudo_probe"], "sudo probe"
    )
    if sudo_probe["stdout"].strip() != "0":
        raise ReportError("sudo probe did not observe uid 0")

    targets = require_object(fixture["targets"], "fixture.targets")
    if set(targets) != {target.name for target in collector.TARGETS}:
        raise ReportError("fixture target inventory drift")
    validated_targets = {}
    for target in collector.TARGETS:
        validated_targets[target.name] = validate_snapshot(
            targets[target.name],
            target,
            runner_uid=runner["uid"],
            runner_gid=runner["gid"],
            username=runner["username"],
            payload_size=payload["size"],
        )
    database_archives = fixture["database_archives"]
    if not isinstance(database_archives, list):
        raise ReportError("database archive inventory is not a list")
    if [item.get("name") for item in database_archives] != list(
        collector.DATABASE_DIRECTORIES
    ):
        raise ReportError("database archive inventory drift")
    for item in database_archives:
        if set(item) != {
            "name",
            "path",
            "member_count",
            "size",
            "sha256",
            "format",
        }:
            raise ReportError("database archive fields changed")
        expected_path = (
            f"{collector.DATABASE_ARCHIVE_DIRECTORY}/{item['name']}.zip"
        )
        if (
            item["path"] != expected_path
            or not isinstance(item["member_count"], int)
            or item["member_count"] < 0
            or not isinstance(item["size"], int)
            or item["size"] < 22
            or not isinstance(item["sha256"], str)
            or len(item["sha256"]) != 64
            or any(character not in "0123456789abcdef"
                   for character in item["sha256"])
            or item["format"]
            != (
                "ZIP_STORED; lexicographic POSIX member order; "
                "1980-01-01T00:00:00; mode 0100644"
            )
        ):
            raise ReportError("database archive identity drift")
    if fixture["runtime_directories"] != collector.RUNTIME_DIRECTORIES:
        raise ReportError("runtime directory contract drift")
    runtime_artifacts = fixture["runtime_artifacts"]
    if not isinstance(runtime_artifacts, list):
        raise ReportError("runtime artifact inventory is not a list")
    runtime_paths = []
    for index, artifact in enumerate(runtime_artifacts):
        item = require_object(artifact, f"runtime artifact {index}")
        if set(item) != {
            "path",
            "kind",
            "uid",
            "gid",
            "mode",
            "size",
        }:
            raise ReportError("runtime artifact fields changed")
        relative = item["path"]
        if (
            not isinstance(relative, str)
            or not relative.startswith(".runtime/")
            or PurePosixPath(relative).is_absolute()
            or ".." in PurePosixPath(relative).parts
        ):
            raise ReportError("runtime artifact path escaped fixture")
        if (
            item["kind"] not in {"directory", "file", "other"}
            or item["uid"] not in {0, runner["uid"]}
            or not isinstance(item["gid"], int)
            or item["gid"] < 0
            or not isinstance(item["mode"], str)
            or len(item["mode"]) != 4
            or any(character not in "01234567" for character in item["mode"])
            or not isinstance(item["size"], int)
            or item["size"] < 0
        ):
            raise ReportError("runtime artifact identity drift")
        runtime_paths.append(relative)
    if runtime_paths != sorted(set(runtime_paths)):
        raise ReportError("runtime artifact inventory is not unique/sorted")
    expected_runtime_roots = {
        relative
        for identity in collector.IDENTITIES
        for relative in collector.RUNTIME_DIRECTORIES[identity].values()
    }
    if not expected_runtime_roots.issubset(set(runtime_paths)):
        raise ReportError("runtime directory inventory is incomplete")

    mutations = fixture["mutations"]
    if not isinstance(mutations, list) or len(mutations) != 4:
        raise ReportError("fixture mutation inventory drift")
    expected_mutations = [
        ("root_public_file", "chown_root", False),
        ("root_private_file", "chown_root", False),
        ("acl_deny_read_file", "add_acl", True),
        ("acl_deny_search_directory", "add_acl", True),
    ]
    for record, (target_name, operation, has_entry) in zip(
        mutations, expected_mutations, strict=True
    ):
        item = require_object(record, f"mutation {target_name}")
        expected = {
            "target",
            "operation",
            "exit_code",
            "stdout",
            "stderr",
        }
        if has_entry:
            expected.add("entry")
        if set(item) != expected:
            raise ReportError(f"mutation fields changed: {target_name}")
        if (
            item["target"] != target_name
            or item["operation"] != operation
        ):
            raise ReportError(f"mutation identity drift: {target_name}")
        require_command_record(
            {
                key: item[key]
                for key in ("exit_code", "stdout", "stderr")
            },
            f"mutation command {target_name}",
        )
        if has_entry:
            target = next(
                value
                for value in collector.TARGETS
                if value.name == target_name
            )
            if item["entry"] != collector.acl_entry(
                runner["username"], target.acl_kind
            ):
                raise ReportError(f"mutation ACL entry drift: {target_name}")

    cleanup = require_object(fixture["cleanup"], "fixture.cleanup")
    if set(cleanup) != {"fixture_removed", "operations"}:
        raise ReportError("cleanup fields changed")
    if cleanup["fixture_removed"] is not True:
        raise ReportError("fixture was not removed")
    operations = cleanup["operations"]
    acl_targets = [
        target for target in collector.TARGETS
        if target.acl_kind is not None
    ]
    if not isinstance(operations, list) or len(operations) != len(
        acl_targets
    ):
        raise ReportError("cleanup operation inventory drift")
    for operation, target in zip(operations, acl_targets, strict=True):
        item = require_object(operation, f"cleanup {target.name}")
        if set(item) != {
            "target",
            "operation",
            "exit_code",
            "stdout",
            "stderr",
        }:
            raise ReportError(f"cleanup fields changed: {target.name}")
        if (
            item["target"] != target.name
            or item["operation"] != "remove_acl"
        ):
            raise ReportError(f"cleanup identity drift: {target.name}")
        require_command_record(
            {
                key: item[key]
                for key in ("exit_code", "stdout", "stderr")
            },
            f"cleanup command {target.name}",
        )

    local_paths = require_object(report["local_paths"], "local_paths")
    if set(local_paths) != {"fixture_dir"}:
        raise ReportError("local path fields changed")
    fixture_text = local_paths["fixture_dir"]
    if (
        not isinstance(fixture_text, str)
        or not PurePosixPath(fixture_text).is_absolute()
        or "\\" in fixture_text
    ):
        raise ReportError("fixture local path is not absolute POSIX")
    fixture_dir = PurePosixPath(fixture_text)

    expected_selection = {
        "target_names": [target.name for target in collector.TARGETS],
        "execution_identities": list(collector.IDENTITIES),
        "minimum_repetitions_per_case": 2,
    }
    if report["selection"] != expected_selection:
        raise ReportError("privilege-path selection drift")
    cases = require_object(report["cases"], "cases")
    expected_case_names = {
        collector._case_name(target, identity)
        for target in collector.TARGETS
        for identity in collector.IDENTITIES
    }
    if set(cases) != expected_case_names:
        raise ReportError("privilege-path case inventory drift")

    report_db = collector.database_arguments(Path("."), report=True)
    reference_tree = baseline_report["corpus"][collector.MINIMAL_PDF][
        "first_detect_tree"
    ]
    declared_raw: set[str] = set()
    determinism_failures = []
    timeout_cases = []
    expected_reference_failures = []
    for target in collector.TARGETS:
        for identity in collector.IDENTITIES:
            name = collector._case_name(target, identity)
            entry = require_object(cases[name], f"case {name}")
            if entry.get("target") != target.name:
                raise ReportError(f"case target drift: {name}")
            if entry.get("execution_identity") != identity:
                raise ReportError(f"case identity drift: {name}")
            expected_prefix = (
                []
                if identity == "runner"
                else [
                    "sudo",
                    "-n",
                    "--",
                    "python3",
                    "-I",
                    "-S",
                    "root-exec-helper",
                ]
            )
            if entry.get("command_prefix") != expected_prefix:
                raise ReportError(f"case command prefix drift: {name}")
            expected_runtime_environment = {
                "HOME": (
                    "<fixture>/"
                    + collector.RUNTIME_DIRECTORIES[identity]["home"]
                ),
                "TMPDIR": (
                    "<fixture>/"
                    + collector.RUNTIME_DIRECTORIES[identity]["tmp"]
                ),
                "root_umask": (
                    "0000" if identity == "root" else None
                ),
            }
            if (
                entry.get("runtime_environment")
                != expected_runtime_environment
            ):
                raise ReportError(
                    f"case runtime environment drift: {name}"
                )
            if entry.get("arguments") != [
                "--json",
                *report_db,
                f"<fixture>/{target.relative}",
            ]:
                raise ReportError(f"case arguments drift: {name}")
            timeout = entry.get("timeout_seconds")
            if not isinstance(timeout, int) or not 1 <= timeout <= 3600:
                raise ReportError(f"case timeout drift: {name}")
            try:
                first, second = baseline_validator.validate_pair(
                    entry,
                    bundle,
                    f"privilege-path case {name}",
                    f"{collector.RAW_SUBDIR}/{name}",
                )
            except baseline_validator.ReportError as error:
                raise ReportError(str(error)) from error
            for side in ("first", "second"):
                raw = require_object(entry[side], f"{name}.{side}")
                declared_raw.update(
                    {raw["stdout_path"], raw["stderr_path"]}
                )
            first_timeout = entry.get("first_timed_out")
            second_timeout = entry.get("second_timed_out")
            if not isinstance(first_timeout, bool) or not isinstance(
                second_timeout, bool
            ):
                raise ReportError(f"timeout flag drift: {name}")
            if (first_timeout and first[0] != 124) or (
                second_timeout and second[0] != 124
            ):
                raise ReportError(f"timeout exit drift: {name}")
            if (
                entry.get("first_fixture_snapshot")
                != validated_targets[target.name]
                or entry.get("second_fixture_snapshot")
                != validated_targets[target.name]
            ):
                raise ReportError(f"case fixture snapshot drift: {name}")
            first_tree = common.json_detect_tree(first[1])
            second_tree = common.json_detect_tree(second[1])
            reference_expected = (
                identity in target.expected_reference_identities
            )
            expected_fields = {
                "first_stdout_summary": collector.stdout_summary(first[1]),
                "second_stdout_summary": collector.stdout_summary(second[1]),
                "first_prefix_paths": collector._prefix_paths(
                    first[1], Path(str(fixture_dir))
                ),
                "second_prefix_paths": collector._prefix_paths(
                    second[1], Path(str(fixture_dir))
                ),
                "first_detect_tree": first_tree,
                "second_detect_tree": second_tree,
                "reference_tree_expected": reference_expected,
                "minimal_pdf_detect_tree_equal": (
                    first_tree == reference_tree
                    if target.kind == "file"
                    else None
                ),
            }
            for field, expected in expected_fields.items():
                if entry.get(field) != expected:
                    raise ReportError(
                        f"privilege-path projection drift: {name}.{field}"
                    )
            if entry["determinism_differences"] or (
                first_timeout != second_timeout
            ):
                determinism_failures.append(name)
            if first_timeout or second_timeout:
                timeout_cases.append(name)
            if reference_expected and first_tree != reference_tree:
                expected_reference_failures.append(name)

    relationships = collector.derive_relationships(cases)
    if report["relationships"] != relationships:
        raise ReportError("privilege-path relationships drift")
    count = len(expected_case_names)
    expected_summary = {
        "case_count": count,
        "execution_count": 2 * count,
        "raw_stream_count": 4 * count,
        "determinism_failures": determinism_failures,
        "timeout_cases": timeout_cases,
        "expected_reference_failures": expected_reference_failures,
        "deterministic": not determinism_failures,
        "expected_references_equal": not expected_reference_failures,
    }
    if report["summary"] != expected_summary:
        raise ReportError("privilege-path summary drift")
    if report["admission"] != {
        "platform_admitted": False,
        "capability_rows_admitted": 0,
        "reason": collector.ADMISSION_REASON,
    }:
        raise ReportError("candidate must not admit capability evidence")
    if report["limitations"] != collector.LIMITATIONS:
        raise ReportError("privilege-path limitations drift")
    raw_root = bundle / "raw" / collector.RAW_SUBDIR
    actual_raw = {
        path.relative_to(bundle).as_posix()
        for path in raw_root.rglob("*")
        if path.is_file()
    }
    if actual_raw != declared_raw:
        raise ReportError(
            "privilege-path raw file inventory differs from report"
        )


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--oracle-report", type=Path, required=True)
    parser.add_argument("--cli-baseline-report", type=Path, required=True)
    parser.set_defaults(root=root)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report_path = args.report.resolve(strict=True)
        oracle_path = args.oracle_report.resolve(strict=True)
        baseline_path = args.cli_baseline_report.resolve(strict=True)
        baseline_validator = _load(
            args.root.resolve(),
            BASELINE_VALIDATOR,
            "macos_baseline_validator_privilege_path_entry",
        )
        report = baseline_validator.load_json(report_path)[0]
        validate_report(
            report,
            report_path=report_path,
            oracle_path=oracle_path,
            baseline_path=baseline_path,
            root=args.root.resolve(),
        )
    except (OSError, ReportError, ValueError) as error:
        print(
            f"macOS CLI privilege-path report error: {error}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
