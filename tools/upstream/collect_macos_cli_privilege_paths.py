#!/usr/bin/env python3
"""Collect non-admitted macOS root, ACL, and ownership CLI evidence."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import stat
import subprocess
import sys
from typing import Any, NamedTuple, Sequence
import zipfile

UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
PLATFORM = "macos-x86_64-qt5"
REPORT_NAME = "cli-privilege-path-candidate.json"
RAW_SUBDIR = "cli-privilege-path"
COLLECTOR = "tools/upstream/collect_macos_cli_privilege_paths.py"
BASELINE_COLLECTOR = "tools/upstream/collect_macos_cli_baseline.py"
BASELINE_VALIDATOR = "tools/upstream/validate_macos_cli_baseline.py"
VALIDATOR = "tools/upstream/validate_macos_cli_privilege_paths.py"
ROOT_EXEC_HELPER = "tools/upstream/exec_macos_privilege_root.py"
BASELINE_MANIFEST = "docs/research/data/baseline-corpus.json"
MINIMAL_PDF = "minimal.pdf"
SUDO = Path("/usr/bin/sudo")
ID = Path("/usr/bin/id")
CHMOD = Path("/bin/chmod")
CHOWN = Path("/usr/sbin/chown")
LS = Path("/bin/ls")
ADMISSION_REASON = (
    "candidate infrastructure and observations require reviewed native "
    "Darwin evidence before any capability row can be admitted"
)
LIMITATIONS = [
    (
        "the fixture is confined to one collector-owned runner temporary "
        "directory and does not model SIP, sandbox profiles, TCC, network "
        "volumes, immutable flags, or multi-user group membership"
    ),
    (
        "passwordless sudo and Darwin ACL support are mandatory capability "
        "preconditions; their presence does not imply production callers "
        "run with root privileges"
    ),
    (
        "ACL cases are observations rather than Linux equivalence claims; "
        "the validator recomputes raw CLI projections without assuming "
        "whether uid 0 bypasses a deny ACE"
    ),
    (
        "the report contains runner uid, gid, user name, and temporary "
        "absolute paths and therefore remains external candidate evidence "
        "until sanitized and reviewed"
    ),
]


class PrivilegePathError(ValueError):
    """The privilege-path candidate cannot be collected safely."""


class Target(NamedTuple):
    name: str
    relative: str
    kind: str
    owner: str
    mode: int
    acl_kind: str | None
    expected_reference_identities: tuple[str, ...]


TARGETS = (
    Target(
        "owner_public_file",
        "owner-public.pdf",
        "file",
        "runner",
        0o644,
        None,
        ("runner", "root"),
    ),
    Target(
        "root_public_file",
        "root-public.pdf",
        "file",
        "root",
        0o644,
        None,
        ("runner", "root"),
    ),
    Target(
        "root_private_file",
        "root-private.pdf",
        "file",
        "root",
        0o600,
        None,
        ("root",),
    ),
    Target(
        "mode_000_file",
        "mode-000.pdf",
        "file",
        "runner",
        0o000,
        None,
        ("root",),
    ),
    Target(
        "acl_deny_read_file",
        "acl-deny.pdf",
        "file",
        "runner",
        0o644,
        "deny_read",
        (),
    ),
    Target(
        "acl_deny_search_directory",
        "acl-deny-directory",
        "directory",
        "runner",
        0o755,
        "deny_search",
        (),
    ),
)
IDENTITIES = ("runner", "root")
RUNTIME_DIRECTORIES = {
    "runner": {
        "home": ".runtime/runner-home",
        "tmp": ".runtime/runner-tmp",
    },
    "root": {
        "home": ".runtime/root-home",
        "tmp": ".runtime/root-tmp",
    },
}
DATABASE_DIRECTORIES = ("db", "db_extra", "db_custom")
DATABASE_ARCHIVE_DIRECTORY = ".database"


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load(root: Path, relative: str, name: str):
    path = root / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise PrivilegePathError(f"cannot load helper: {relative}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _generator_bindings(root: Path) -> dict[str, str]:
    paths = (
        COLLECTOR,
        ROOT_EXEC_HELPER,
        BASELINE_COLLECTOR,
        BASELINE_VALIDATOR,
        VALIDATOR,
        BASELINE_MANIFEST,
    )
    return {relative: sha256((root / relative).read_bytes()) for relative in paths}


def database_arguments(database_dir: Path, *, report: bool) -> tuple[str, ...]:
    root = (
        f"<fixture>/{DATABASE_ARCHIVE_DIRECTORY}"
        if report
        else str(database_dir)
    )
    return (
        "--database",
        f"{root}/db.zip",
        "--extradatabase",
        f"{root}/db_extra.zip",
        "--customdatabase",
        f"{root}/db_custom.zip",
    )


def materialize_database_archives(
    source_dir: Path,
    fixture_dir: Path,
) -> list[dict[str, Any]]:
    archive_dir = fixture_dir / DATABASE_ARCHIVE_DIRECTORY
    archive_dir.mkdir(mode=0o700)
    records: list[dict[str, Any]] = []
    for name in DATABASE_DIRECTORIES:
        source = (source_dir / "Detect-It-Easy" / name).resolve(strict=True)
        if not source.is_dir():
            raise PrivilegePathError(f"database source is not a directory: {name}")
        destination = archive_dir / f"{name}.zip"
        members: list[Path] = []
        for candidate in source.rglob("*"):
            if candidate.is_symlink() or not candidate.is_file():
                if candidate.is_dir():
                    continue
                raise PrivilegePathError(
                    f"unsupported database entry: {candidate}"
                )
            members.append(candidate)
        members.sort(key=lambda path: path.relative_to(source).as_posix())
        with zipfile.ZipFile(
            destination,
            mode="x",
            compression=zipfile.ZIP_STORED,
        ) as archive:
            for member in members:
                relative = member.relative_to(source).as_posix()
                info = zipfile.ZipInfo(
                    relative,
                    date_time=(1980, 1, 1, 0, 0, 0),
                )
                info.compress_type = zipfile.ZIP_STORED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                archive.writestr(info, member.read_bytes())
        destination.chmod(0o444)
        records.append(
            {
                "name": name,
                "path": f"{DATABASE_ARCHIVE_DIRECTORY}/{name}.zip",
                "member_count": len(members),
                "size": destination.stat().st_size,
                "sha256": sha256(destination.read_bytes()),
                "format": (
                    "ZIP_STORED; lexicographic POSIX member order; "
                    "1980-01-01T00:00:00; mode 0100644"
                ),
            }
        )
    return records


def command_record(result: subprocess.CompletedProcess[bytes]) -> dict[str, Any]:
    return {
        "exit_code": result.returncode,
        "stdout": result.stdout.decode("utf-8", errors="backslashreplace"),
        "stderr": result.stderr.decode("utf-8", errors="backslashreplace"),
    }


def run_checked(arguments: Sequence[str], *, label: str) -> dict[str, Any]:
    result = subprocess.run(
        [str(value) for value in arguments],
        check=False,
        capture_output=True,
    )
    record = command_record(result)
    if result.returncode != 0:
        raise PrivilegePathError(f"{label} failed: {record}")
    return record


def validate_fixture_path(path: Path) -> Path:
    if path.exists():
        raise PrivilegePathError("fixture directory must not already exist")
    parent = path.parent.resolve(strict=True)
    resolved = path.resolve()
    if resolved.parent != parent or resolved == parent:
        raise PrivilegePathError("fixture must be one direct child of its parent")
    if resolved == Path(resolved.anchor):
        raise PrivilegePathError("fixture cannot be a filesystem root")
    return resolved


def load_payload(root: Path, corpus_dir: Path) -> tuple[bytes, dict[str, Any], bytes]:
    manifest_raw = (root / BASELINE_MANIFEST).read_bytes()
    manifest = json.loads(manifest_raw)
    records = {
        record["name"]: record for record in manifest["samples"]
    }
    record = records[MINIMAL_PDF]
    payload = (corpus_dir / MINIMAL_PDF).read_bytes()
    if len(payload) != record["size"] or sha256(payload) != record["sha256"]:
        raise PrivilegePathError("minimal PDF corpus identity differs")
    return payload, record, manifest_raw


def acl_entry(username: str, kind: str) -> str:
    if kind == "deny_read":
        rights = "read"
    elif kind == "deny_search":
        rights = "list,search"
    else:
        raise PrivilegePathError(f"unknown ACL kind: {kind}")
    return f"user:{username} deny {rights}"


def inspect_target(
    target: Target,
    path: Path,
    *,
    runner_uid: int,
    runner_gid: int,
) -> dict[str, Any]:
    value = os.lstat(path)
    listing = subprocess.run(
        [str(LS), "-lde", str(path)],
        check=False,
        capture_output=True,
    )
    if listing.returncode != 0:
        raise PrivilegePathError(
            f"cannot inspect target {target.name}: {command_record(listing)}"
        )
    expected_uid = 0 if target.owner == "root" else runner_uid
    expected_gid = 0 if target.owner == "root" else runner_gid
    actual_mode = stat.S_IMODE(value.st_mode)
    if (
        value.st_uid != expected_uid
        or value.st_gid != expected_gid
        or actual_mode != target.mode
    ):
        raise PrivilegePathError(f"target identity differs: {target.name}")
    return {
        "relative_path": target.relative,
        "kind": target.kind,
        "owner": target.owner,
        "uid": value.st_uid,
        "gid": value.st_gid,
        "mode": f"{actual_mode:04o}",
        "size": value.st_size,
        "acl_kind": target.acl_kind,
        "acl_listing": listing.stdout.decode(
            "utf-8", errors="backslashreplace"
        ),
    }


def materialize_fixture(
    fixture_dir: Path,
    payload: bytes,
    *,
    username: str,
    runner_uid: int,
    runner_gid: int,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    fixture_dir.mkdir(mode=0o700)
    for identity in IDENTITIES:
        for relative in RUNTIME_DIRECTORIES[identity].values():
            path = fixture_dir / relative
            path.mkdir(parents=True, mode=0o700)
    mutation_records = []
    for target in TARGETS:
        path = fixture_dir / target.relative
        if target.kind == "directory":
            path.mkdir(mode=0o755)
            (path / MINIMAL_PDF).write_bytes(payload)
            os.chmod(path / MINIMAL_PDF, 0o644)
        else:
            path.write_bytes(payload)
        os.chmod(path, target.mode)
        if target.owner == "root":
            record = run_checked(
                (
                    SUDO,
                    "-n",
                    "--",
                    CHOWN,
                    "0:0",
                    path,
                ),
                label=f"root ownership mutation for {target.name}",
            )
            mutation_records.append(
                {
                    "target": target.name,
                    "operation": "chown_root",
                    **record,
                }
            )
        if target.acl_kind is not None:
            entry = acl_entry(username, target.acl_kind)
            record = run_checked(
                (CHMOD, "+a", entry, path),
                label=f"ACL mutation for {target.name}",
            )
            mutation_records.append(
                {
                    "target": target.name,
                    "operation": "add_acl",
                    "entry": entry,
                    **record,
                }
            )
    snapshots = {
        target.name: inspect_target(
            target,
            fixture_dir / target.relative,
            runner_uid=runner_uid,
            runner_gid=runner_gid,
        )
        for target in TARGETS
    }
    for target in TARGETS:
        snapshot = snapshots[target.name]
        if target.acl_kind is not None:
            entry = acl_entry(username, target.acl_kind)
            rights = entry.split(" deny ", 1)[1]
            if username not in snapshot["acl_listing"] or (
                f"deny {rights}" not in snapshot["acl_listing"]
            ):
                raise PrivilegePathError(
                    f"ACL listing does not show deny entry: {target.name}"
                )
    return snapshots, mutation_records


def runtime_artifact_inventory(fixture_dir: Path) -> list[dict[str, Any]]:
    runtime_root = fixture_dir / ".runtime"
    result = []
    for path in sorted(runtime_root.rglob("*")):
        value = os.lstat(path)
        result.append(
            {
                "path": path.relative_to(fixture_dir).as_posix(),
                "kind": (
                    "directory"
                    if stat.S_ISDIR(value.st_mode)
                    else "file"
                    if stat.S_ISREG(value.st_mode)
                    else "other"
                ),
                "uid": value.st_uid,
                "gid": value.st_gid,
                "mode": f"{stat.S_IMODE(value.st_mode):04o}",
                "size": value.st_size,
            }
        )
    return result


def cleanup_fixture(fixture_dir: Path) -> dict[str, Any]:
    records = []
    for target in TARGETS:
        path = fixture_dir / target.relative
        if not path.exists() and not path.is_symlink():
            continue
        if target.acl_kind is not None:
            result = subprocess.run(
                [str(CHMOD), "-N", str(path)],
                check=False,
                capture_output=True,
            )
            records.append(
                {
                    "target": target.name,
                    "operation": "remove_acl",
                    **command_record(result),
                }
            )
            if result.returncode != 0:
                raise PrivilegePathError(
                    f"ACL cleanup failed for {target.name}"
                )
        if target.mode == 0:
            os.chmod(path, 0o600)
    shutil.rmtree(fixture_dir)
    return {"fixture_removed": not fixture_dir.exists(), "operations": records}


def observe(
    common: Any,
    binary: Path,
    qt_dir: Path,
    arguments: Sequence[str],
    identity: str,
    runtime_home: Path,
    runtime_tmp: Path,
    root_exec_helper: Path,
    python_executable: Path,
    *,
    timeout_seconds: int,
) -> tuple[Any, bool]:
    environment = os.environ.copy()
    path_value = (
        str(qt_dir / "bin")
        + os.pathsep
        + environment.get("PATH", "")
    )
    if identity == "runner":
        command = [binary.name, *arguments]
        executable = str(binary)
    elif identity == "root":
        command = [
            str(SUDO),
            "-n",
            "--",
            str(python_executable),
            "-I",
            "-S",
            str(root_exec_helper),
            "--home",
            str(runtime_home),
            "--tmp",
            str(runtime_tmp),
            "--path",
            path_value,
            "--",
            str(binary),
            *arguments,
        ]
        executable = None
    else:
        raise PrivilegePathError(f"unknown execution identity: {identity}")
    environment["PATH"] = path_value
    environment["HOME"] = str(runtime_home)
    environment["TMPDIR"] = str(runtime_tmp)
    try:
        result = subprocess.run(
            command,
            executable=executable,
            cwd=binary.parent,
            env=environment,
            check=False,
            capture_output=True,
            timeout=timeout_seconds,
        )
        return common.Observation(
            result.returncode, result.stdout, result.stderr
        ), False
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout or b""
        stderr = error.stderr or b""
        if isinstance(stdout, str):
            stdout = stdout.encode("utf-8", errors="surrogateescape")
        if isinstance(stderr, str):
            stderr = stderr.encode("utf-8", errors="surrogateescape")
        return common.Observation(124, stdout, stderr), True


def stdout_summary(data: bytes) -> dict[str, int]:
    normalized = data.replace(b"\r\n", b"\n")
    return {
        "cannot_find_count": normalized.count(b"Cannot find:"),
        "filename_prefix_count": normalized.count(b".pdf:\n"),
        "pdf_root_count": (
            normalized.count(b'"filetype":"PDF"')
            + normalized.count(b'"filetype": "PDF"')
        ),
    }


def _case_name(target: Target, identity: str) -> str:
    return f"{target.name}__as_{identity}"


def _prefix_paths(data: bytes, fixture_dir: Path) -> list[str]:
    root = os.fsencode(str(fixture_dir))
    result = []
    for line in data.replace(b"\r\n", b"\n").splitlines():
        if line.startswith(root + b"/") and line.endswith(b".pdf:"):
            relative = line[len(root) + 1 : -1]
            result.append(
                "<fixture>/"
                + os.fsdecode(relative).replace(os.sep, "/")
            )
    return result


def derive_relationships(cases: dict[str, Any]) -> dict[str, Any]:
    result = {}
    for target in TARGETS:
        runner = cases[_case_name(target, "runner")]
        root = cases[_case_name(target, "root")]
        result[target.name] = {
            "runner_exit_code": runner["first"]["exit_code"],
            "root_exit_code": root["first"]["exit_code"],
            "runner_matches_minimal_pdf": runner[
                "minimal_pdf_detect_tree_equal"
            ],
            "root_matches_minimal_pdf": root[
                "minimal_pdf_detect_tree_equal"
            ],
            "runner_root_detect_trees_equal": (
                runner["first_detect_tree"] == root["first_detect_tree"]
            ),
            "runner_root_stdout_summaries_equal": (
                runner["first_stdout_summary"]
                == root["first_stdout_summary"]
            ),
        }
    return result


def collect(
    *,
    root: Path,
    binary: Path,
    source_dir: Path,
    qt_dir: Path,
    corpus_dir: Path,
    fixture_dir: Path,
    oracle_path: Path,
    baseline_path: Path,
    output: Path,
    timeout_seconds: int,
) -> dict[str, Any]:
    if sys.platform != "darwin" or platform.machine() != "x86_64":
        raise PrivilegePathError("collector requires native Darwin x86_64")
    if not 1 <= timeout_seconds <= 3600:
        raise PrivilegePathError("timeout-seconds must be in 1..3600")
    if os.geteuid() == 0:
        raise PrivilegePathError("collector must start as a non-root user")
    for tool in (SUDO, ID, CHMOD, CHOWN, LS):
        if not tool.is_file():
            raise PrivilegePathError(f"required Darwin tool missing: {tool}")
    python_executable = Path(sys.executable).resolve(strict=True)

    root = root.resolve(strict=True)
    source_dir = source_dir.resolve(strict=True)
    qt_dir = qt_dir.resolve(strict=True)
    corpus_dir = corpus_dir.resolve(strict=True)
    binary = binary.resolve(strict=True)
    oracle_path = oracle_path.resolve(strict=True)
    baseline_path = baseline_path.resolve(strict=True)
    fixture_dir = validate_fixture_path(fixture_dir)
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    for path, name in (
        (oracle_path, "oracle-candidate.json"),
        (baseline_path, "cli-baseline-candidate.json"),
    ):
        if path != (output.parent / name).resolve(strict=True):
            raise PrivilegePathError(
                f"input report must be bundle-local: {name}"
            )
    if output != (output.parent / REPORT_NAME).resolve():
        raise PrivilegePathError(f"output must be bundle-local: {REPORT_NAME}")
    if output.exists():
        raise PrivilegePathError("candidate report already exists")
    raw_dir = output.parent / "raw" / RAW_SUBDIR
    raw_dir.mkdir(parents=True, exist_ok=True)
    if any(raw_dir.iterdir()):
        raise PrivilegePathError("privilege-path raw directory must be empty")

    baseline_collector = _load(
        root, BASELINE_COLLECTOR, "macos_baseline_for_privilege_path"
    )
    baseline_validator = _load(
        root,
        BASELINE_VALIDATOR,
        "macos_baseline_validator_for_privilege_path",
    )
    common = baseline_collector.load_module(
        "windows_cli_common_for_macos_privilege_path",
        root / baseline_collector.SHARED_COLLECTOR,
    )
    baseline_report = baseline_validator.load_json(baseline_path)[0]
    baseline_validator.validate_report(
        baseline_report,
        report_path=baseline_path,
        oracle_path=oracle_path,
        root=root,
    )
    oracle, oracle_raw = baseline_collector.validate_oracle_inputs(
        root, oracle_path, source_dir, qt_dir, binary
    )
    expected_binary = (
        source_dir / "build" / "release" / "diec"
    ).resolve(strict=True)
    if binary != expected_binary:
        raise PrivilegePathError(
            "binary must be <source>/build/release/diec"
        )
    source = common.validate_source(source_dir)
    source["tracked_files_clean_before_and_after"] = True
    qt = baseline_collector.validate_qt(common, qt_dir, oracle)
    binary_sha256 = common.sha256_file(binary)
    if binary_sha256 != oracle["artifact"]["sha256"]:
        raise PrivilegePathError("binary differs from oracle report")
    if baseline_report["source"] != source or baseline_report["qt"] != qt:
        raise PrivilegePathError("baseline source/Qt identity differs")
    if baseline_report["binary"]["sha256"] != binary_sha256:
        raise PrivilegePathError("baseline binary identity differs")

    payload, payload_record, manifest_raw = load_payload(
        root, corpus_dir
    )
    root_exec_helper = (root / ROOT_EXEC_HELPER).resolve(strict=True)
    import pwd

    runner_uid = os.geteuid()
    runner_gid = os.getegid()
    username = pwd.getpwuid(runner_uid).pw_name
    sudo_probe = run_checked(
        (SUDO, "-n", "--", ID, "-u"),
        label="passwordless sudo probe",
    )
    if sudo_probe["stdout"].strip() != "0":
        raise PrivilegePathError("sudo probe did not execute as uid 0")

    snapshots: dict[str, dict[str, Any]] = {}
    mutations: list[dict[str, Any]] = []
    cases: dict[str, Any] = {}
    runtime_artifacts: list[dict[str, Any]] = []
    database_archives: list[dict[str, Any]] = []
    cleanup: dict[str, Any] | None = None
    try:
        snapshots, mutations = materialize_fixture(
            fixture_dir,
            payload,
            username=username,
            runner_uid=runner_uid,
            runner_gid=runner_gid,
        )
        database_archives = materialize_database_archives(
            source_dir,
            fixture_dir,
        )
        database_dir = fixture_dir / DATABASE_ARCHIVE_DIRECTORY
        actual_db = database_arguments(database_dir, report=False)
        report_db = database_arguments(database_dir, report=True)
        reference_tree = baseline_report["corpus"][MINIMAL_PDF][
            "first_detect_tree"
        ]
        for target in TARGETS:
            actual_path = fixture_dir / target.relative
            for identity in IDENTITIES:
                name = _case_name(target, identity)
                runtime_home = (
                    fixture_dir
                    / RUNTIME_DIRECTORIES[identity]["home"]
                )
                runtime_tmp = (
                    fixture_dir
                    / RUNTIME_DIRECTORIES[identity]["tmp"]
                )
                arguments = ("--json", *actual_db, str(actual_path))
                first_snapshot = inspect_target(
                    target,
                    actual_path,
                    runner_uid=runner_uid,
                    runner_gid=runner_gid,
                )
                first, first_timeout = observe(
                    common,
                    binary,
                    qt_dir,
                    arguments,
                    identity,
                    runtime_home,
                    runtime_tmp,
                    root_exec_helper,
                    python_executable,
                    timeout_seconds=timeout_seconds,
                )
                second_snapshot = inspect_target(
                    target,
                    actual_path,
                    runner_uid=runner_uid,
                    runner_gid=runner_gid,
                )
                second, second_timeout = observe(
                    common,
                    binary,
                    qt_dir,
                    arguments,
                    identity,
                    runtime_home,
                    runtime_tmp,
                    root_exec_helper,
                    python_executable,
                    timeout_seconds=timeout_seconds,
                )
                entry = baseline_collector.pair_report(
                    common,
                    output.parent,
                    f"{RAW_SUBDIR}/{name}",
                    first,
                    second,
                )
                first_tree = common.json_detect_tree(first.stdout)
                second_tree = common.json_detect_tree(second.stdout)
                entry.update(
                    {
                        "target": target.name,
                        "execution_identity": identity,
                        "command_prefix": (
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
                        ),
                        "runtime_environment": {
                            "HOME": (
                                "<fixture>/"
                                + RUNTIME_DIRECTORIES[identity]["home"]
                            ),
                            "TMPDIR": (
                                "<fixture>/"
                                + RUNTIME_DIRECTORIES[identity]["tmp"]
                            ),
                            "root_umask": (
                                "0000" if identity == "root" else None
                            ),
                        },
                        "arguments": [
                            "--json",
                            *report_db,
                            f"<fixture>/{target.relative}",
                        ],
                        "timeout_seconds": timeout_seconds,
                        "first_timed_out": first_timeout,
                        "second_timed_out": second_timeout,
                        "first_fixture_snapshot": first_snapshot,
                        "second_fixture_snapshot": second_snapshot,
                        "first_stdout_summary": stdout_summary(
                            first.stdout
                        ),
                        "second_stdout_summary": stdout_summary(
                            second.stdout
                        ),
                        "first_prefix_paths": _prefix_paths(
                            first.stdout, fixture_dir
                        ),
                        "second_prefix_paths": _prefix_paths(
                            second.stdout, fixture_dir
                        ),
                        "first_detect_tree": first_tree,
                        "second_detect_tree": second_tree,
                        "reference_tree_expected": (
                            identity
                            in target.expected_reference_identities
                        ),
                        "minimal_pdf_detect_tree_equal": (
                            first_tree == reference_tree
                            if target.kind == "file"
                            else None
                        ),
                    }
                )
                cases[name] = entry
        runtime_artifacts = runtime_artifact_inventory(fixture_dir)
    finally:
        if fixture_dir.exists():
            cleanup = cleanup_fixture(fixture_dir)
    if cleanup is None or not cleanup["fixture_removed"]:
        raise PrivilegePathError("fixture cleanup was not completed")

    determinism_failures = []
    timeout_cases = []
    expected_reference_failures = []
    for target in TARGETS:
        for identity in IDENTITIES:
            name = _case_name(target, identity)
            entry = cases[name]
            if entry["determinism_differences"]:
                determinism_failures.append(name)
            if entry["first_timed_out"] or entry["second_timed_out"]:
                timeout_cases.append(name)
            if (
                entry["reference_tree_expected"]
                and not entry["minimal_pdf_detect_tree_equal"]
            ):
                expected_reference_failures.append(name)
    case_count = len(TARGETS) * len(IDENTITIES)
    report = {
        "schema_version": 1,
        "result": "candidate",
        "platform": PLATFORM,
        "generator": _generator_bindings(root),
        "oracle_report": {
            "path": "oracle-candidate.json",
            "sha256": sha256(oracle_raw),
        },
        "cli_baseline_report": {
            "path": "cli-baseline-candidate.json",
            "sha256": sha256(baseline_path.read_bytes()),
        },
        "source": source,
        "qt": qt,
        "binary": {
            "size": binary.stat().st_size,
            "sha256": binary_sha256,
            "relative_path": "build/release/diec",
        },
        "fixture": {
            "manifest": BASELINE_MANIFEST,
            "manifest_sha256": sha256(manifest_raw),
            "payload": payload_record,
            "runner": {
                "uid": runner_uid,
                "gid": runner_gid,
                "username": username,
            },
            "tool_paths": {
                "sudo": str(SUDO),
                "id": str(ID),
                "chmod": str(CHMOD),
                "chown": str(CHOWN),
                "ls": str(LS),
                "python": str(python_executable),
                "root_exec_helper": ROOT_EXEC_HELPER,
            },
            "sudo_probe": sudo_probe,
            "mutations": mutations,
            "targets": snapshots,
            "database_archives": database_archives,
            "runtime_directories": RUNTIME_DIRECTORIES,
            "runtime_artifacts": runtime_artifacts,
            "cleanup": cleanup,
        },
        "local_paths": {"fixture_dir": str(fixture_dir)},
        "selection": {
            "target_names": [target.name for target in TARGETS],
            "execution_identities": list(IDENTITIES),
            "minimum_repetitions_per_case": 2,
        },
        "cases": cases,
        "relationships": derive_relationships(cases),
        "summary": {
            "case_count": case_count,
            "execution_count": 2 * case_count,
            "raw_stream_count": 4 * case_count,
            "determinism_failures": determinism_failures,
            "timeout_cases": timeout_cases,
            "expected_reference_failures": expected_reference_failures,
            "deterministic": not determinism_failures,
            "expected_references_equal": (
                not expected_reference_failures
            ),
        },
        "admission": {
            "platform_admitted": False,
            "capability_rows_admitted": 0,
            "reason": ADMISSION_REASON,
        },
        "limitations": LIMITATIONS,
    }
    output.write_bytes(
        (
            json.dumps(
                report,
                ensure_ascii=True,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    )
    return report


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--qt-dir", type=Path, required=True)
    parser.add_argument("--corpus-dir", type=Path, required=True)
    parser.add_argument("--fixture-dir", type=Path, required=True)
    parser.add_argument("--oracle-report", type=Path, required=True)
    parser.add_argument("--cli-baseline-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.set_defaults(root=root)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        collect(
            root=args.root,
            binary=args.binary,
            source_dir=args.source_dir,
            qt_dir=args.qt_dir,
            corpus_dir=args.corpus_dir,
            fixture_dir=args.fixture_dir,
            oracle_path=args.oracle_report,
            baseline_path=args.cli_baseline_report,
            output=args.output,
            timeout_seconds=args.timeout_seconds,
        )
    except (OSError, PrivilegePathError, ValueError) as error:
        print(f"macOS CLI privilege-path error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
