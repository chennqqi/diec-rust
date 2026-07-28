#!/usr/bin/env python3
"""Collect a deterministic native-Windows Qt5 CLI baseline."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Sequence


UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
EXPECTED_SUBMODULE_COUNT = 58
EXPECTED_QT_VERSION = "5.15.2"
EXPECTED_QMAKE_SHA256 = (
    "e873ad3a689a0628c3037a6440221dcd"
    "2e426395edf14ffa6379612dede26d36"
)
EXPECTED_QTCORE_SHA256 = (
    "8d2ff4ce9096ddccc4f4cd62c2e41fc"
    "854cfd1b0d6e8d296645a7f5fd4ae565a"
)
EXPECTED_QTSCRIPT_SHA256 = (
    "0b58e5e79df13110a8258f14d7b3658d"
    "1dd0c8dddc337a164b89d4ac12a0638f"
)
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


class BaselineError(ValueError):
    """The native oracle or one of its pinned inputs is not trustworthy."""


@dataclass(frozen=True)
class Observation:
    exit_code: int
    stdout: bytes
    stderr: bytes

    def summary(self) -> dict[str, object]:
        return {
            "exit_code": self.exit_code,
            "stdout_bytes": len(self.stdout),
            "stdout_sha256": hashlib.sha256(self.stdout).hexdigest(),
            "stderr_bytes": len(self.stderr),
            "stderr_sha256": hashlib.sha256(self.stderr).hexdigest(),
        }


@dataclass(frozen=True)
class Case:
    name: str
    arguments: tuple[str, ...]
    report_arguments: tuple[str, ...]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_checked(
    arguments: Sequence[str],
    *,
    cwd: Path | None = None,
) -> str:
    result = subprocess.run(
        arguments,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
    )
    if result.returncode != 0:
        raise BaselineError(
            f"command failed ({result.returncode}): {' '.join(arguments)}"
        )
    return result.stdout.rstrip("\r\n")


def validate_source(source_dir: Path) -> dict[str, object]:
    commit = run_checked(["git", "-C", str(source_dir), "rev-parse", "HEAD"])
    if commit != UPSTREAM_COMMIT:
        raise BaselineError(
            f"DIE-engine commit mismatch: expected {UPSTREAM_COMMIT}, got {commit}"
        )

    root_status = run_checked(
        [
            "git",
            "-C",
            str(source_dir),
            "status",
            "--porcelain=v1",
            "--untracked-files=no",
            "--ignore-submodules=dirty",
        ]
    )
    if root_status:
        raise BaselineError("DIE-engine has tracked changes")

    status = run_checked(
        ["git", "-C", str(source_dir), "submodule", "status", "--recursive"]
    ).splitlines()
    if len(status) != EXPECTED_SUBMODULE_COUNT:
        raise BaselineError(
            "recursive submodule count mismatch: "
            f"expected {EXPECTED_SUBMODULE_COUNT}, got {len(status)}"
        )
    invalid = [line for line in status if not line.startswith(" ")]
    if invalid:
        raise BaselineError(f"submodule identity is not clean: {invalid}")

    tracked_submodule_status = run_checked(
        [
            "git",
            "-C",
            str(source_dir),
            "submodule",
            "foreach",
            "--quiet",
            "--recursive",
            "git status --porcelain=v1 --untracked-files=no",
        ]
    )
    if tracked_submodule_status:
        raise BaselineError("one or more submodules have tracked changes")

    rules_dir = source_dir / "Detect-It-Easy"
    rules_commit = run_checked(
        ["git", "-C", str(rules_dir), "rev-parse", "HEAD"]
    )
    if rules_commit != RULES_COMMIT:
        raise BaselineError(
            "Detect-It-Easy commit mismatch: "
            f"expected {RULES_COMMIT}, got {rules_commit}"
        )
    return {
        "repository": "https://github.com/horsicq/DIE-engine",
        "commit": commit,
        "recursive_submodule_count": len(status),
        "rules_commit": rules_commit,
    }


def validate_qt(qt_dir: Path) -> dict[str, str]:
    qmake = qt_dir / "bin" / "qmake.exe"
    qtcore = qt_dir / "bin" / "Qt5Core.dll"
    qtscript = qt_dir / "bin" / "Qt5Script.dll"
    for path in (qmake, qtcore, qtscript):
        if not path.is_file():
            raise BaselineError(f"required Qt file is missing: {path}")

    version = run_checked([str(qmake), "-query", "QT_VERSION"])
    spec = run_checked([str(qmake), "-query", "QMAKE_SPEC"])
    actual = {
        "version": version,
        "qmake_spec": spec,
        "qmake_sha256": sha256_file(qmake),
        "qt5core_sha256": sha256_file(qtcore),
        "qt5script_sha256": sha256_file(qtscript),
    }
    expected = {
        "version": EXPECTED_QT_VERSION,
        "qmake_spec": "win32-msvc",
        "qmake_sha256": EXPECTED_QMAKE_SHA256,
        "qt5core_sha256": EXPECTED_QTCORE_SHA256,
        "qt5script_sha256": EXPECTED_QTSCRIPT_SHA256,
    }
    if actual != expected:
        raise BaselineError(f"Qt identity mismatch: {actual}")
    return actual


def load_corpus(
    corpus_dir: Path,
    reference_manifest: Path,
) -> tuple[list[dict[str, object]], str]:
    generated_path = corpus_dir / "manifest.json"
    generated = generated_path.read_bytes()
    reference = reference_manifest.read_bytes()
    if generated != reference:
        raise BaselineError(
            "generated corpus manifest differs from the committed reference"
        )
    manifest = json.loads(generated)
    samples = manifest.get("samples")
    if manifest.get("schema_version") != 1 or not isinstance(samples, list):
        raise BaselineError("unsupported baseline corpus manifest")
    declared = {sample["name"] for sample in samples}
    actual = {
        path.name
        for path in corpus_dir.iterdir()
        if path.is_file() and path.name != "manifest.json"
    }
    if actual != declared:
        raise BaselineError("baseline corpus has missing or undeclared files")
    for sample in samples:
        path = corpus_dir / str(sample["name"])
        if path.stat().st_size != sample["size"]:
            raise BaselineError(f"corpus size mismatch: {path.name}")
        if sha256_file(path) != sample["sha256"]:
            raise BaselineError(f"corpus hash mismatch: {path.name}")
    return samples, hashlib.sha256(reference).hexdigest()


def json_detect_tree(data: bytes) -> object:
    """Return the stable nested-result fields used by the Linux baseline."""
    try:
        document = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(document, dict):
        return None
    detects = document.get("detects")
    if not isinstance(detects, list):
        return None

    def summarize(detect: object) -> object:
        if not isinstance(detect, dict):
            return None
        is_nested_detect = "parentfilepart" in detect
        keys = (
            ("filetype", "offset", "parentfilepart", "size")
            if is_nested_detect
            else ("name", "type", "version")
        )
        result = {key: detect[key] for key in keys if key in detect}
        values = detect.get("values")
        if isinstance(values, list):
            result["values"] = [summarize(value) for value in values]
        return result

    return [summarize(detect) for detect in detects]


def observe(
    binary: Path,
    qt_dir: Path,
    arguments: Sequence[str],
    *,
    timeout_seconds: int,
) -> Observation:
    environment = os.environ.copy()
    path_key = next(
        (key for key in environment if key.upper() == "PATH"),
        "PATH",
    )
    environment[path_key] = (
        str(qt_dir / "bin")
        + os.pathsep
        + environment.get(path_key, "")
    )
    result = subprocess.run(
        [binary.name, *arguments],
        executable=str(binary),
        cwd=binary.parent,
        env=environment,
        check=False,
        capture_output=True,
        timeout=timeout_seconds,
    )
    return Observation(result.returncode, result.stdout, result.stderr)


def pair_report(first: Observation, second: Observation) -> dict[str, object]:
    differences = []
    if first.exit_code != second.exit_code:
        differences.append("exit_code")
    if first.stdout != second.stdout:
        differences.append("stdout")
    if first.stderr != second.stderr:
        differences.append("stderr")
    return {
        "first": first.summary(),
        "second": second.summary(),
        "determinism_differences": differences,
    }


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--qt-dir", type=Path, required=True)
    parser.add_argument("--corpus-dir", type=Path, required=True)
    parser.add_argument("--expected-binary-sha256", required=True)
    parser.add_argument(
        "--reference-manifest",
        type=Path,
        default=root / "docs/research/data/baseline-corpus.json",
    )
    parser.add_argument(
        "--linux-reference",
        type=Path,
        default=root
        / "docs/research/data/baseline-corpus-linux-qt5.json",
    )
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if os.name != "nt":
        raise BaselineError("native Windows baseline requires os.name == 'nt'")
    if args.timeout_seconds < 1 or args.timeout_seconds > 3600:
        raise BaselineError("timeout-seconds must be in 1..3600")
    if (
        len(args.expected_binary_sha256) != 64
        or any(
            character not in "0123456789abcdef"
            for character in args.expected_binary_sha256
        )
    ):
        raise BaselineError("expected binary SHA-256 must be lowercase hex")

    source_dir = args.source_dir.resolve(strict=True)
    qt_dir = args.qt_dir.resolve(strict=True)
    corpus_dir = args.corpus_dir.resolve(strict=True)
    binary = args.binary.resolve(strict=True)
    expected_binary = (
        source_dir / "build" / "release" / "diec.exe"
    ).resolve(strict=True)
    if binary != expected_binary:
        raise BaselineError(
            "binary must be <source>/build/release/diec.exe"
        )
    binary_sha256 = sha256_file(binary)
    if binary_sha256 != args.expected_binary_sha256:
        raise BaselineError(
            "binary SHA-256 mismatch: "
            f"expected {args.expected_binary_sha256}, got {binary_sha256}"
        )

    source_identity = validate_source(source_dir)
    qt_identity = validate_qt(qt_dir)
    samples, manifest_sha256 = load_corpus(
        corpus_dir,
        args.reference_manifest.resolve(strict=True),
    )
    linux_reference_path = args.linux_reference.resolve(strict=True)
    linux_reference_raw = linux_reference_path.read_bytes()
    linux_reference = json.loads(linux_reference_raw)
    linux_corpus = linux_reference.get("corpus")
    if not isinstance(linux_corpus, dict):
        raise BaselineError("Linux reference has no corpus report")
    if set(linux_corpus) != {sample["name"] for sample in samples}:
        raise BaselineError("Linux reference corpus set differs")

    database_args = (
        "--database",
        str(source_dir / "Detect-It-Easy" / "db"),
        "--extradatabase",
        str(source_dir / "Detect-It-Easy" / "db_extra"),
        "--customdatabase",
        str(source_dir / "Detect-It-Easy" / "db_custom"),
    )
    database_report_args = (
        "--database",
        "<source>/Detect-It-Easy/db",
        "--extradatabase",
        "<source>/Detect-It-Easy/db_extra",
        "--customdatabase",
        "<source>/Detect-It-Easy/db_custom",
    )
    cases = (
        Case("version", ("--version",), ("--version",)),
        Case("help", ("--help",), ("--help",)),
        Case("no_args", (), ()),
        Case(
            "show_structs",
            ("--showstructs",),
            ("--showstructs",),
        ),
        Case(
            "database",
            ("--showdatabase", *database_args),
            ("--showdatabase", *database_report_args),
        ),
        Case(
            "missing",
            ("does-not-exist",),
            ("<binary-dir>/does-not-exist",),
        ),
    )

    determinism_failures: list[str] = []
    case_reports: dict[str, object] = {}
    for case in cases:
        first = observe(
            binary,
            qt_dir,
            case.arguments,
            timeout_seconds=args.timeout_seconds,
        )
        second = observe(
            binary,
            qt_dir,
            case.arguments,
            timeout_seconds=args.timeout_seconds,
        )
        paired = pair_report(first, second)
        paired["arguments"] = list(case.report_arguments)
        case_reports[case.name] = paired
        if paired["determinism_differences"]:
            determinism_failures.append(f"cases.{case.name}")

    corpus_reports: dict[str, object] = {}
    projection_failures: list[str] = []
    for sample in samples:
        name = str(sample["name"])
        arguments = (
            "--json",
            *database_args,
            str(corpus_dir / name),
        )
        first = observe(
            binary,
            qt_dir,
            arguments,
            timeout_seconds=args.timeout_seconds,
        )
        second = observe(
            binary,
            qt_dir,
            arguments,
            timeout_seconds=args.timeout_seconds,
        )
        paired = pair_report(first, second)
        first_tree = json_detect_tree(first.stdout)
        second_tree = json_detect_tree(second.stdout)
        linux = linux_corpus[name]
        linux_tree = linux["left_detect_tree"]
        paired.update(
            {
                "arguments": [
                    "--json",
                    *database_report_args,
                    f"<corpus>/{name}",
                ],
                "intended_format": sample["intended_format"],
                "sample_sha256": sample["sha256"],
                "first_detect_tree": first_tree,
                "second_detect_tree": second_tree,
                "linux_qt5_detect_tree": linux_tree,
                "linux_projection_equal": first_tree == linux_tree,
                "linux_exit_code_equal": (
                    first.exit_code == linux["left"]["exit_code"]
                ),
            }
        )
        corpus_reports[name] = paired
        if paired["determinism_differences"]:
            determinism_failures.append(f"corpus.{name}")
        if (
            first_tree != linux_tree
            or first.exit_code != linux["left"]["exit_code"]
        ):
            projection_failures.append(name)

    report = {
        "schema_version": 1,
        "generator": "tools/upstream/collect_windows_cli_baseline.py",
        "generator_sha256": sha256_file(Path(__file__)),
        "platform": "windows-x86_64-qt5",
        "source": source_identity,
        "qt": qt_identity,
        "binary": {
            "size": binary.stat().st_size,
            "sha256": binary_sha256,
            "relative_path": "build/release/diec.exe",
        },
        "corpus_manifest": {
            "path": "docs/research/data/baseline-corpus.json",
            "sha256": manifest_sha256,
            "sample_count": len(samples),
        },
        "linux_qt5_reference": {
            "path": (
                "docs/research/data/baseline-corpus-linux-qt5.json"
            ),
            "sha256": hashlib.sha256(linux_reference_raw).hexdigest(),
        },
        "cases": case_reports,
        "corpus": corpus_reports,
        "summary": {
            "case_count": len(case_reports),
            "corpus_count": len(corpus_reports),
            "execution_count": 2
            * (len(case_reports) + len(corpus_reports)),
            "determinism_failures": determinism_failures,
            "linux_projection_failures": projection_failures,
            "deterministic": not determinism_failures,
            "linux_projection_equal": not projection_failures,
        },
        "limitations": [
            (
                "this baseline covers general CLI identity, database listing, "
                "missing-path handling, and one default JSON scan per baseline "
                "corpus sample"
            ),
            (
                "output/scan/special/nested/path/database-error matrices and "
                "engine-only harnesses require separate Windows evidence"
            ),
            (
                "raw stdout hashes are platform observations; only the named "
                "detection projection and exit code are compared cross-platform"
            ),
        ],
    }
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
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(serialized)
    print(serialized.decode("utf-8"), end="")
    return 0 if not determinism_failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
