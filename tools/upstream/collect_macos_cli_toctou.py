#!/usr/bin/env python3
"""Collect a non-admitted macOS Qt5 enumeration/open TOCTOU candidate."""

from __future__ import annotations

import argparse
import errno
import hashlib
import importlib.util
import json
import os
import platform
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from typing import Any, Sequence


UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
PLATFORM = "macos-x86_64-qt5"
BASELINE_COLLECTOR = "tools/upstream/collect_macos_cli_baseline.py"
BASELINE_VALIDATOR = "tools/upstream/validate_macos_cli_baseline.py"
FIXTURE_GENERATOR = "tools/corpus/generate_path_toctou_fixture.py"
FIXTURE_MANIFEST = "docs/research/data/path-toctou-fixture.json"
LINUX_REFERENCE = "docs/research/data/path-toctou-engine-qt5.json"
VALIDATOR = "tools/upstream/validate_macos_cli_toctou.py"
BLOCKER_SIZE = 32 * 1024 * 1024
NEW_PAYLOAD = bytes(range(256)) * 16
ADMISSION_REASON = (
    "enumeration/open TOCTOU candidate only; macOS runtime evidence has "
    "not been reviewed or projected into the 68-row capability closure"
)
LIMITATIONS = [
    (
        "the PTY, SIGSTOP, waitpid(WUNTRACED), mutation, and SIGCONT "
        "protocol covers one ordered two-entry directory and two "
        "symlink mutations; it is not a general scheduler proof"
    ),
    (
        "the collector fails if the second logical prefix is observable "
        "before the child is confirmed stopped, rather than accepting "
        "a timing-dependent result"
    ),
    (
        "the PTY intentionally changes stdout isatty state to obtain a "
        "portable line boundary; stable controls and semantic projection "
        "detect output drift, but this is not byte-equivalent to the "
        "ordinary pipe-based CLI baseline transport"
    ),
    (
        "the candidate records legacy release-CLI behavior only; it "
        "does not approve the Rust SafeCanonical policy or waive ADR "
        "0014 post-open identity checks"
    ),
    (
        "no result is admitted until the native Darwin bundle, raw "
        "streams, filesystem identity changes, and Linux projection "
        "have been reviewed"
    ),
]


class ToctouError(ValueError):
    """The TOCTOU candidate cannot be collected safely."""


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _load(root: Path, relative: str, name: str) -> Any:
    path = root / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ToctouError(f"cannot load helper module: {relative}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _generator_bindings(root: Path) -> dict[str, str]:
    paths = {
        "path": "tools/upstream/collect_macos_cli_toctou.py",
        "validator_path": VALIDATOR,
        "baseline_collector_path": BASELINE_COLLECTOR,
        "baseline_validator_path": BASELINE_VALIDATOR,
        "fixture_generator_path": FIXTURE_GENERATOR,
    }
    result = dict(paths)
    for field, relative in paths.items():
        digest_field = (
            "sha256"
            if field == "path"
            else field.removesuffix("_path") + "_sha256"
        )
        result[digest_field] = sha256((root / relative).read_bytes())
    return result


def database_arguments(source_dir: Path, *, report: bool) -> tuple[str, ...]:
    root = "<source>" if report else str(source_dir)
    return (
        "--database",
        f"{root}/Detect-It-Easy/db",
        "--extradatabase",
        f"{root}/Detect-It-Easy/db_extra",
        "--customdatabase",
        f"{root}/Detect-It-Easy/db_custom",
    )


def _identity(path: Path, *, follow: bool) -> dict[str, int] | None:
    try:
        value = path.stat() if follow else path.lstat()
    except FileNotFoundError:
        return None
    return {
        "device": value.st_dev,
        "inode": value.st_ino,
        "mode": value.st_mode,
        "size": value.st_size,
    }


def _link_state(link: Path) -> dict[str, Any]:
    return {
        "link_identity": _identity(link, follow=False),
        "link_target": (
            os.readlink(link) if link.is_symlink() else None
        ),
        "target_identity": _identity(link, follow=True),
    }


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def materialize(
    fixture_dir: Path, case: dict[str, Any]
) -> tuple[Path, Path, dict[str, Any]]:
    case_dir = fixture_dir / "case"
    targets = fixture_dir / "targets"
    expected_files = {
        case_dir / "a-blocker.bin",
        case_dir / "z-link.bin",
        targets / "old.bin",
        targets / "new.bin",
    }
    actual_files = {
        path
        for directory in (case_dir, targets)
        if directory.is_dir()
        for path in directory.iterdir()
    }
    if actual_files - expected_files:
        raise ToctouError("unexpected path in TOCTOU fixture directory")
    for path in expected_files:
        if path.is_symlink() or path.is_file():
            path.unlink()
    for directory in (case_dir, targets):
        if directory.exists():
            directory.rmdir()
    if any(fixture_dir.iterdir()):
        raise ToctouError("unexpected TOCTOU fixture root entry")
    case_dir.mkdir(parents=True)
    targets.mkdir()
    blocker = case_dir / "a-blocker.bin"
    with blocker.open("wb") as stream:
        stream.truncate(BLOCKER_SIZE)
    old_target = targets / "old.bin"
    old_target.touch()
    new_target = targets / "new.bin"
    new_target.write_bytes(NEW_PAYLOAD)
    link = case_dir / "z-link.bin"
    link.symlink_to(case["initial_target"])
    preflight = {
        "blocker_size": blocker.stat().st_size,
        "blocker_sha256": _file_sha256(blocker),
        "old_size": old_target.stat().st_size,
        "old_sha256": _file_sha256(old_target),
        "new_size": new_target.stat().st_size,
        "new_sha256": _file_sha256(new_target),
    }
    return case_dir, link, preflight


def mutate(link: Path, action: str) -> None:
    if action == "replace_symlink_with_new_target":
        replacement = link.parent / ".replacement-link"
        replacement.symlink_to("../targets/new.bin")
        os.replace(replacement, link)
    elif action == "unlink_symlink":
        link.unlink()
    elif action != "none":
        raise ToctouError(f"unknown fixture action: {action}")


def _read_fd(fd: int) -> tuple[bytes, bool]:
    try:
        value = os.read(fd, 65536)
    except OSError as error:
        if error.errno == errno.EIO:
            return b"", True
        raise
    return value, not value


def observe(
    common: Any,
    binary: Path,
    qt_dir: Path,
    arguments: Sequence[str],
    *,
    case_dir: Path,
    link: Path,
    action: str,
    timeout_seconds: int,
) -> tuple[Any, dict[str, Any]]:
    # These modules and APIs intentionally remain lazy so synthetic report
    # validation can import this module on non-POSIX development hosts.
    import pty
    import select
    import termios

    environment = os.environ.copy()
    environment["PATH"] = (
        str(qt_dir / "bin")
        + os.pathsep
        + environment.get("PATH", "")
    )
    master, slave = pty.openpty()
    attributes = termios.tcgetattr(slave)
    attributes[1] &= ~termios.OPOST
    termios.tcsetattr(slave, termios.TCSANOW, attributes)
    process = subprocess.Popen(
        [binary.name, *arguments],
        executable=str(binary),
        cwd=binary.parent,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=slave,
        stderr=subprocess.PIPE,
        bufsize=0,
    )
    os.close(slave)
    assert process.stderr is not None
    stderr_fd = process.stderr.fileno()
    stdout = bytearray()
    stderr = bytearray()
    expected_first = os.fsencode(str(case_dir / "a-blocker.bin")) + b":\n"
    second_prefix = os.fsencode(str(case_dir / "z-link.bin")) + b":\n"
    deadline = time.monotonic() + timeout_seconds
    stopped = False
    master_eof = False
    stderr_eof = False
    before = _link_state(link)
    try:
        while b"\n" not in stdout:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ToctouError("first prefix timeout")
            ready, _, _ = select.select(
                [master, stderr_fd], [], [], min(remaining, 0.25)
            )
            if not ready and process.poll() is not None:
                raise ToctouError("child exited before first prefix")
            for fd in ready:
                data, eof = _read_fd(fd)
                if fd == master:
                    stdout.extend(data)
                    master_eof = master_eof or eof
                else:
                    stderr.extend(data)
                    stderr_eof = stderr_eof or eof
        first_line = bytes(stdout).split(b"\n", 1)[0] + b"\n"
        if first_line != expected_first:
            raise ToctouError(
                f"unexpected first logical prefix: {first_line!r}"
            )
        os.kill(process.pid, signal.SIGSTOP)
        waited_pid, wait_status = os.waitpid(process.pid, os.WUNTRACED)
        if (
            waited_pid != process.pid
            or not os.WIFSTOPPED(wait_status)
            or os.WSTOPSIG(wait_status) != signal.SIGSTOP
        ):
            raise ToctouError("child did not enter SIGSTOP state")
        stopped = True

        # Drain bytes already emitted before the confirmed stop. Seeing the
        # second prefix means the intended pre-open window was missed.
        while True:
            ready, _, _ = select.select(
                [master, stderr_fd], [], [], 0
            )
            if not ready:
                break
            for fd in ready:
                data, eof = _read_fd(fd)
                if fd == master:
                    stdout.extend(data)
                    master_eof = master_eof or eof
                else:
                    stderr.extend(data)
                    stderr_eof = stderr_eof or eof
        if second_prefix in stdout:
            raise ToctouError(
                "second prefix was emitted before confirmed mutation window"
            )

        mutate(link, action)
        after = _link_state(link)
        os.kill(process.pid, signal.SIGCONT)
        stopped = False

        while not (master_eof and stderr_eof):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ToctouError("child completion timeout")
            fds = []
            if not master_eof:
                fds.append(master)
            if not stderr_eof:
                fds.append(stderr_fd)
            ready, _, _ = select.select(
                fds, [], [], min(remaining, 0.25)
            )
            if not ready and process.poll() is not None:
                # One final nonblocking drain distinguishes EOF from a
                # scheduler gap after process exit.
                ready = fds
            for fd in ready:
                data, eof = _read_fd(fd)
                if fd == master:
                    stdout.extend(data)
                    master_eof = master_eof or eof
                else:
                    stderr.extend(data)
                    stderr_eof = stderr_eof or eof
        return_code = process.wait(
            timeout=max(0.1, deadline - time.monotonic())
        )
    finally:
        if process.poll() is None:
            if stopped:
                os.kill(process.pid, signal.SIGCONT)
            process.kill()
            process.wait()
        os.close(master)
        process.stderr.close()
    metadata = {
        "before": before,
        "after": after,
        "synchronization": {
            "transport": "pty-with-oPOST-disabled",
            "first_line": os.fsdecode(expected_first[:-1]),
            "child_confirmed_stopped": True,
            "mutation_while_stopped": True,
            "second_prefix_seen_before_mutation": False,
            "stop_signal": int(signal.SIGSTOP),
            "resume_signal": int(signal.SIGCONT),
        },
    }
    return common.Observation(return_code, bytes(stdout), bytes(stderr)), metadata


def parse_documents(stdout: bytes, case_dir: Path) -> list[dict[str, Any]]:
    # Normalizing here keeps the raw replay validator host-independent;
    # native collection is restricted to Darwin and always emits '/'.
    case_bytes = os.fsencode(str(case_dir)).replace(b"\\", b"/")
    root = re.escape(case_bytes)
    matches = list(
        re.finditer(rb"(?m)^(" + root + rb"/[^:\r\n]+):\n", stdout)
    )
    expected_paths = [
        case_bytes + b"/a-blocker.bin",
        case_bytes + b"/z-link.bin",
    ]
    if [match.group(1) for match in matches] != expected_paths:
        raise ToctouError("logical prefix sequence changed")
    documents = []
    for index, match in enumerate(matches):
        end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(stdout)
        )
        try:
            def reject_duplicates(
                pairs: list[tuple[str, Any]],
            ) -> dict[str, Any]:
                value: dict[str, Any] = {}
                for key, item in pairs:
                    if key in value:
                        raise ToctouError(
                            f"duplicate entropy JSON key: {key}"
                        )
                    value[key] = item
                return value

            value = json.loads(
                stdout[match.end() : end],
                object_pairs_hook=reject_duplicates,
                parse_constant=lambda constant: (
                    (_ for _ in ()).throw(
                        ToctouError(
                            "non-finite entropy JSON constant: "
                            f"{constant}"
                        )
                    )
                ),
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ToctouError(f"invalid entropy JSON: {error}") from error
        if not isinstance(value, dict):
            raise ToctouError("entropy document is not an object")
        documents.append(value)
    return documents


def _state_transition_valid(
    case: dict[str, Any], attempt: dict[str, Any]
) -> bool:
    before = attempt["before"]
    after = attempt["after"]
    action = case["action"]
    if (
        before["link_target"] != case["initial_target"]
        or before["link_identity"] is None
        or before["target_identity"] is None
    ):
        return False
    if action == "none":
        return before == after
    if action == "replace_symlink_with_new_target":
        return (
            after["link_target"] == "../targets/new.bin"
            and after["link_identity"] is not None
            and after["target_identity"] is not None
            and before["link_identity"]["inode"]
            != after["link_identity"]["inode"]
            and before["target_identity"]["inode"]
            != after["target_identity"]["inode"]
        )
    return action == "unlink_symlink" and after == {
        "link_identity": None,
        "link_target": None,
        "target_identity": None,
    }


def collect(
    *,
    root: Path,
    binary: Path,
    source_dir: Path,
    qt_dir: Path,
    fixture_dir: Path,
    oracle_path: Path,
    baseline_path: Path,
    output: Path,
    timeout_seconds: int,
) -> dict[str, Any]:
    if sys.platform != "darwin" or platform.machine() != "x86_64":
        raise ToctouError("collector requires native Darwin x86_64")
    if not 1 <= timeout_seconds <= 60:
        raise ToctouError("timeout-seconds must be in 1..60")
    source_dir = source_dir.resolve(strict=True)
    qt_dir = qt_dir.resolve(strict=True)
    binary = binary.resolve(strict=True)
    oracle_path = oracle_path.resolve(strict=True)
    baseline_path = baseline_path.resolve(strict=True)
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    for path, name in (
        (oracle_path, "oracle-candidate.json"),
        (baseline_path, "cli-baseline-candidate.json"),
    ):
        if path != (output.parent / name).resolve(strict=True):
            raise ToctouError(f"input report must be bundle-local: {name}")
    if output.exists():
        raise ToctouError("candidate report already exists")
    fixture_dir = fixture_dir.resolve()
    fixture_dir.mkdir(parents=True, exist_ok=True)
    if any(fixture_dir.iterdir()):
        raise ToctouError("TOCTOU fixture directory must be empty")
    raw_dir = output.parent / "raw" / "cli-toctou"
    raw_dir.mkdir(parents=True, exist_ok=True)
    if any(raw_dir.iterdir()):
        raise ToctouError("TOCTOU raw directory must be empty")

    baseline_collector = _load(
        root, BASELINE_COLLECTOR, "macos_baseline_for_toctou"
    )
    baseline_validator = _load(
        root, BASELINE_VALIDATOR, "macos_baseline_validator_for_toctou"
    )
    common = baseline_collector.load_module(
        "windows_cli_common_for_macos_toctou",
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
    if binary != (
        source_dir / "build" / "release" / "diec"
    ).resolve(strict=True):
        raise ToctouError("binary must be <source>/build/release/diec")
    source = common.validate_source(source_dir)
    source["tracked_files_clean_before_and_after"] = True
    qt = baseline_collector.validate_qt(common, qt_dir, oracle)
    binary_sha256 = common.sha256_file(binary)
    if (
        binary_sha256 != oracle["artifact"]["sha256"]
        or baseline_report["source"] != source
        or baseline_report["qt"] != qt
        or baseline_report["binary"]["sha256"] != binary_sha256
    ):
        raise ToctouError("baseline/oracle/source identity differs")

    manifest, manifest_raw = baseline_validator.load_json(
        root / FIXTURE_MANIFEST
    )
    linux, linux_raw = baseline_validator.load_json(
        root / LINUX_REFERENCE
    )
    cases = manifest.get("cases")
    if not isinstance(cases, list) or len(cases) != 4:
        raise ToctouError("TOCTOU fixture case inventory changed")
    actual_db = database_arguments(source_dir, report=False)
    report_db = database_arguments(source_dir, report=True)
    reports = {}
    determinism_failures = []
    synchronization_failures = []
    linux_semantic_failures = []
    transition_failures = []
    expected_preflight = None
    for case in cases:
        name = case["name"]
        observations = []
        attempts = []
        documents = []
        for _side in ("first", "second"):
            case_dir, link, preflight = materialize(
                fixture_dir, case
            )
            if expected_preflight is None:
                expected_preflight = preflight
            elif preflight != expected_preflight:
                raise ToctouError("fixture preflight differs across runs")
            arguments = (
                "--entropy",
                "--json",
                *actual_db,
                str(case_dir),
            )
            observation, attempt = observe(
                common,
                binary,
                qt_dir,
                arguments,
                case_dir=case_dir,
                link=link,
                action=case["action"],
                timeout_seconds=timeout_seconds,
            )
            observations.append(observation)
            attempts.append(attempt)
            documents.append(parse_documents(observation.stdout, case_dir))
        first, second = observations
        entry = baseline_collector.pair_report(
            common,
            output.parent,
            f"cli-toctou/{name}",
            first,
            second,
        )
        linux_case = linux["cases"][name]
        linux_projection = {
            "action": linux_case["action"],
            "expected_open_target": linux_case["expected_open_target"],
            "blocker_document": linux_case["blocker_document"],
            "link_document": linux_case["link_document"],
        }
        linux_equal = all(
            observation.exit_code == 0
            and observation.stderr == b""
            and parsed
            == [
                linux_projection["blocker_document"],
                linux_projection["link_document"],
            ]
            for observation, parsed in zip(observations, documents)
        )
        sync_valid = all(
            attempt["synchronization"][
                "child_confirmed_stopped"
            ]
            and attempt["synchronization"]["mutation_while_stopped"]
            and not attempt["synchronization"][
                "second_prefix_seen_before_mutation"
            ]
            for attempt in attempts
        )
        transitions_valid = all(
            _state_transition_valid(case, attempt)
            for attempt in attempts
        )
        entry.update(
            {
                "arguments": [
                    "--entropy",
                    "--json",
                    *report_db,
                    "<fixture>/case",
                ],
                "timeout_seconds": timeout_seconds,
                "initial_target": case["initial_target"],
                "action": case["action"],
                "expected_open_target": case[
                    "expected_open_target"
                ],
                "attempts": {
                    "first": attempts[0],
                    "second": attempts[1],
                },
                "first_documents": documents[0],
                "second_documents": documents[1],
                "synchronization_valid": sync_valid,
                "state_transitions_valid": transitions_valid,
                "linux_qt5_projection": linux_projection,
                "linux_qt5_semantic_equal": linux_equal,
            }
        )
        reports[name] = entry
        if entry["determinism_differences"]:
            determinism_failures.append(name)
        if not sync_valid:
            synchronization_failures.append(name)
            raise ToctouError(
                f"synchronization contract failed: {name}"
            )
        if not transitions_valid:
            transition_failures.append(name)
            raise ToctouError(
                f"filesystem state transition failed: {name}"
            )
        if not linux_equal:
            linux_semantic_failures.append(name)

    count = len(cases)
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
            "manifest": FIXTURE_MANIFEST,
            "manifest_sha256": sha256(manifest_raw),
            "case_count": count,
            "live_preflight": expected_preflight,
        },
        "linux_qt5_reference": {
            "path": LINUX_REFERENCE,
            "sha256": sha256(linux_raw),
        },
        "local_paths": {"fixture_dir": str(fixture_dir)},
        "selection": {
            "case_names": [case["name"] for case in cases],
            "minimum_repetitions_per_case": 2,
        },
        "cases": reports,
        "summary": {
            "case_count": count,
            "execution_count": 2 * count,
            "raw_stream_count": 4 * count,
            "determinism_failures": determinism_failures,
            "synchronization_failures": synchronization_failures,
            "state_transition_failures": transition_failures,
            "linux_semantic_failures": linux_semantic_failures,
            "deterministic": not determinism_failures,
            "synchronization_valid": not synchronization_failures,
            "state_transitions_valid": not transition_failures,
            "linux_semantics_equal": not linux_semantic_failures,
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
        ).encode()
    )
    return report


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--qt-dir", type=Path, required=True)
    parser.add_argument("--fixture-dir", type=Path, required=True)
    parser.add_argument("--oracle-report", type=Path, required=True)
    parser.add_argument("--cli-baseline-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=60)
    parser.set_defaults(root=root)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        collect(
            root=args.root.resolve(),
            binary=args.binary,
            source_dir=args.source_dir,
            qt_dir=args.qt_dir,
            fixture_dir=args.fixture_dir,
            oracle_path=args.oracle_report,
            baseline_path=args.cli_baseline_report,
            output=args.output,
            timeout_seconds=args.timeout_seconds,
        )
    except (ToctouError, OSError, ValueError) as error:
        print(f"macOS CLI TOCTOU error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
