#!/usr/bin/env python3
"""Offline verification for pinned upstream components and Git subtrees."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SHA1_RE = re.compile(r"^[0-9a-f]{40}$")


class VerificationError(RuntimeError):
    """Raised when Git data required for verification cannot be read."""


@dataclass(frozen=True)
class SubtreeRecord:
    commit: str
    directory: str
    split: str


class Reporter:
    def __init__(self) -> None:
        self.failures = 0
        self.warnings = 0

    def pass_(self, message: str) -> None:
        print(f"PASS  {message}")

    def fail(self, message: str) -> None:
        self.failures += 1
        print(f"FAIL  {message}")

    def warn(self, message: str) -> None:
        self.warnings += 1
        print(f"WARN  {message}")


def run_git(repo: Path, *args: str) -> str:
    process = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if process.returncode != 0:
        detail = process.stderr.strip() or process.stdout.strip()
        raise VerificationError(f"git {' '.join(args)} failed: {detail}")
    return process.stdout.strip()


def rev_parse(repo: Path, revision: str) -> str:
    return run_git(repo, "rev-parse", "--verify", revision)


def parse_subtree_records(output: str) -> list[SubtreeRecord]:
    records: list[SubtreeRecord] = []
    for raw_record in output.split("\x1e"):
        raw_record = raw_record.strip()
        if not raw_record or "\x00" not in raw_record:
            continue
        commit, body = raw_record.split("\x00", 1)
        directory = ""
        split = ""
        for line in body.splitlines():
            if line.startswith("git-subtree-dir: "):
                directory = line.removeprefix("git-subtree-dir: ").strip()
            elif line.startswith("git-subtree-split: "):
                split = line.removeprefix("git-subtree-split: ").strip()
        if directory and split:
            records.append(SubtreeRecord(commit=commit.strip(), directory=directory, split=split))
    return records


def find_subtree_record(repo: Path, local_path: str) -> SubtreeRecord | None:
    output = run_git(
        repo,
        "log",
        "--all",
        "--format=%H%x00%B%x1e",
        f"--grep=git-subtree-dir: {local_path}",
    )
    for record in parse_subtree_records(output):
        if record.directory == local_path:
            return record
    return None


def validate_lock_data(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("schema") != 1:
        errors.append("schema must be 1")

    baseline = data.get("baseline")
    if not isinstance(baseline, dict):
        errors.append("baseline table is required")
        baseline = {}

    for field in ("name", "repository", "commit", "local_path", "materialization"):
        if not baseline.get(field):
            errors.append(f"baseline.{field} is required")
    if baseline.get("commit") and not SHA1_RE.fullmatch(str(baseline["commit"])):
        errors.append("baseline.commit must be a lowercase 40-character SHA-1")

    components = data.get("component")
    if not isinstance(components, list) or not components:
        errors.append("at least one [[component]] is required")
        return errors

    seen_names: set[str] = set()
    seen_local_paths: set[str] = set()
    for index, component in enumerate(components):
        prefix = f"component[{index}]"
        if not isinstance(component, dict):
            errors.append(f"{prefix} must be a table")
            continue
        for field in ("name", "repository", "commit", "gitlink_path", "materialization"):
            if not component.get(field):
                errors.append(f"{prefix}.{field} is required")

        name = str(component.get("name", ""))
        if name in seen_names:
            errors.append(f"duplicate component name: {name}")
        seen_names.add(name)

        commit = str(component.get("commit", ""))
        if commit and not SHA1_RE.fullmatch(commit):
            errors.append(f"{prefix}.commit must be a lowercase 40-character SHA-1")

        materialization = component.get("materialization")
        local_path = component.get("local_path")
        if materialization == "subtree-squash" and not local_path:
            errors.append(f"{prefix}.local_path is required for subtree-squash")
        if local_path:
            local_path = str(local_path)
            if local_path in seen_local_paths:
                errors.append(f"duplicate component local_path: {local_path}")
            seen_local_paths.add(local_path)

    return errors


def load_lock(lock_path: Path) -> dict[str, Any]:
    try:
        with lock_path.open("rb") as lock_file:
            return tomllib.load(lock_file)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise VerificationError(f"cannot read {lock_path}: {error}") from error


def verify_subtree(
    repo: Path,
    reporter: Reporter,
    *,
    label: str,
    commit: str,
    local_path: str,
) -> None:
    try:
        upstream_tree = rev_parse(repo, f"{commit}^{{tree}}")
        local_tree = rev_parse(repo, f"HEAD:{local_path}")
    except VerificationError as error:
        reporter.fail(f"{label}: {error}")
        return

    if upstream_tree == local_tree:
        reporter.pass_(f"{label}: subtree tree matches {commit}")
    else:
        reporter.fail(
            f"{label}: subtree tree mismatch "
            f"(upstream={upstream_tree}, local={local_tree})"
        )

    try:
        record = find_subtree_record(repo, local_path)
    except VerificationError as error:
        reporter.fail(f"{label}: cannot inspect subtree metadata: {error}")
        return

    if record is None:
        reporter.fail(f"{label}: no git-subtree metadata for {local_path}")
    elif record.split != commit:
        reporter.fail(
            f"{label}: git-subtree-split is {record.split}, expected {commit}"
        )
    else:
        reporter.pass_(
            f"{label}: subtree metadata commit {record.commit[:12]} "
            f"pins {record.split}"
        )


def verify_repository(repo: Path, lock_path: Path, data: dict[str, Any]) -> Reporter:
    reporter = Reporter()
    errors = validate_lock_data(data)
    for error in errors:
        reporter.fail(f"lock: {error}")
    if errors:
        return reporter

    try:
        top_level = Path(run_git(repo, "rev-parse", "--show-toplevel")).resolve()
    except VerificationError as error:
        reporter.fail(str(error))
        return reporter
    if top_level != repo.resolve():
        reporter.fail(f"repo path is not the Git top level: {repo}")
        return reporter
    reporter.pass_(f"repository root: {top_level}")
    reporter.pass_(f"lock parsed: {lock_path.relative_to(repo)}")

    baseline = data["baseline"]
    baseline_commit = str(baseline["commit"])
    verify_subtree(
        repo,
        reporter,
        label=str(baseline["name"]),
        commit=baseline_commit,
        local_path=str(baseline["local_path"]),
    )

    for component in data["component"]:
        name = str(component["name"])
        commit = str(component["commit"])
        gitlink_path = str(component["gitlink_path"])
        try:
            gitlink = rev_parse(repo, f"{baseline_commit}:{gitlink_path}")
        except VerificationError as error:
            reporter.fail(f"{name}: cannot resolve baseline gitlink: {error}")
            continue

        if gitlink == commit:
            reporter.pass_(f"{name}: baseline gitlink matches {commit}")
        else:
            reporter.fail(
                f"{name}: baseline gitlink is {gitlink}, lock expects {commit}"
            )

        if component["materialization"] != "subtree-squash":
            reporter.warn(f"{name}: content is not materialized in this repository")
            continue

        local_path = str(component["local_path"])
        verify_subtree(
            repo,
            reporter,
            label=name,
            commit=commit,
            local_path=local_path,
        )

        for tracked_path in component.get("tracked_content", []):
            tracked_path = str(tracked_path)
            try:
                upstream_tree = rev_parse(repo, f"{commit}:{tracked_path}")
                local_tree = rev_parse(repo, f"HEAD:{local_path}/{tracked_path}")
            except VerificationError as error:
                reporter.fail(f"{name}/{tracked_path}: {error}")
                continue
            if upstream_tree == local_tree:
                reporter.pass_(f"{name}/{tracked_path}: tree matches")
            else:
                reporter.fail(
                    f"{name}/{tracked_path}: tree mismatch "
                    f"(upstream={upstream_tree}, local={local_tree})"
                )

    return reporter


def parse_args() -> argparse.Namespace:
    default_repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Verify pinned upstream gitlinks and squash subtrees without network access."
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=default_repo,
        help="repository root (default: inferred from this script)",
    )
    parser.add_argument(
        "--lock",
        type=Path,
        default=None,
        help="component lock path (default: upstream/components.lock.toml)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = args.repo.resolve()
    lock_path = (
        args.lock.resolve()
        if args.lock is not None
        else repo / "upstream" / "components.lock.toml"
    )

    try:
        data = load_lock(lock_path)
    except VerificationError as error:
        print(f"FAIL  {error}")
        return 2

    reporter = verify_repository(repo, lock_path, data)
    print(
        f"\nsummary: failures={reporter.failures} "
        f"warnings={reporter.warnings}"
    )
    return 1 if reporter.failures else 0


if __name__ == "__main__":
    sys.exit(main())
