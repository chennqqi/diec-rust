#!/usr/bin/env python3
"""Compare pinned Qt 5 and Qt 6 format HostApi arity reports."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from typing import Any


SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import compare_global_host_api_reports as json_diff  # noqa: E402
import probe_host_api_arity as probe  # noqa: E402


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_report(path: pathlib.Path, runtime: str) -> tuple[dict[str, Any], str]:
    data = path.read_bytes()
    report = json.loads(data)
    if (
        report.get("schema_version") != 1
        or report.get("generator")
        != "tools/upstream/probe_host_api_arity.py"
        or report.get("runtime_profile") != runtime
    ):
        raise ValueError(f"unexpected {runtime} report identity")
    probe.validate_observation(report["observation"], runtime)
    stderr = b"" if runtime == "qt5" else probe.QT6_STDERR
    if report.get("stderr") != {
        "bytes": len(stderr),
        "sha256": sha256(stderr),
        "utf8_lines": stderr.decode("utf-8").splitlines(),
    }:
        raise ValueError(f"unexpected {runtime} stderr record")
    return report, sha256(data)


def relative_path(repo: pathlib.Path, path: pathlib.Path) -> str:
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError as error:
        raise ValueError("report path must be inside the repository") from error


def source_identities(repo: pathlib.Path) -> dict[str, dict[str, Any]]:
    result = {}
    for relative in (
        "tools/upstream/compare_host_api_arity_reports.py",
        "tools/upstream/compare_global_host_api_reports.py",
        "tools/upstream/probe_host_api_arity.py",
    ):
        data = (repo / relative).read_bytes()
        result[relative] = {
            "bytes": len(data),
            "sha256": sha256(data),
        }
    return result


def build_report(
    repo: pathlib.Path,
    qt5_path: pathlib.Path,
    qt6_path: pathlib.Path,
) -> dict[str, Any]:
    qt5, qt5_sha256 = load_report(qt5_path, "qt5")
    qt6, qt6_sha256 = load_report(qt6_path, "qt6")
    left = {
        "observation": qt5["observation"],
        "stderr": qt5["stderr"],
    }
    right = {
        "observation": qt6["observation"],
        "stderr": qt6["stderr"],
    }
    differences = json_diff.compare_values(left, right)
    return {
        "schema_version": 1,
        "generator": (
            "tools/upstream/compare_host_api_arity_reports.py"
        ),
        "upstream_commit": probe.UPSTREAM_COMMIT,
        "xscanengine_commit": probe.XSCANENGINE_COMMIT,
        "rules_commit": probe.RULES_COMMIT,
        "inputs": {
            "qt5": {
                "path": relative_path(repo, qt5_path),
                "sha256": qt5_sha256,
                "image": qt5["image"],
                "binary": qt5["binary"],
            },
            "qt6": {
                "path": relative_path(repo, qt6_path),
                "sha256": qt6_sha256,
                "image": qt6["image"],
                "binary": qt6["binary"],
            },
        },
        "sources": source_identities(repo),
        "equal": not differences,
        "difference_count": len(differences),
        "differences": differences,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    repo = pathlib.Path(__file__).resolve().parents[2]
    parser.add_argument(
        "--qt5-report",
        type=pathlib.Path,
        default=repo / "docs/research/data/host-api-arity-qt5.json",
    )
    parser.add_argument(
        "--qt6-report",
        type=pathlib.Path,
        default=repo / "docs/research/data/host-api-arity-qt6.json",
    )
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=repo / "docs/research/data/host-api-arity-qt5-qt6.json",
    )
    args = parser.parse_args()
    report = build_report(
        repo,
        args.qt5_report.resolve(),
        args.qt6_report.resolve(),
    )
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
