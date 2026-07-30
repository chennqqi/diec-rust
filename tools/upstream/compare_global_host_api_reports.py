#!/usr/bin/env python3
"""Compare pinned Qt 5 and Qt 6 global HostApi observation reports."""

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

import probe_global_host_api as probe  # noqa: E402


MISSING = object()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compare_values(
    left: Any,
    right: Any,
    path: str = "$",
) -> list[dict[str, Any]]:
    if isinstance(left, dict) and isinstance(right, dict):
        differences = []
        for key in sorted(set(left) | set(right)):
            left_value = left.get(key, MISSING)
            right_value = right.get(key, MISSING)
            child_path = f"{path}.{key}"
            if left_value is MISSING:
                differences.append(
                    {
                        "path": child_path,
                        "kind": "missing_left",
                        "right": right_value,
                    }
                )
            elif right_value is MISSING:
                differences.append(
                    {
                        "path": child_path,
                        "kind": "missing_right",
                        "left": left_value,
                    }
                )
            else:
                differences.extend(
                    compare_values(left_value, right_value, child_path)
                )
        return differences
    if isinstance(left, list) and isinstance(right, list):
        differences = []
        common = min(len(left), len(right))
        for index in range(common):
            differences.extend(
                compare_values(
                    left[index],
                    right[index],
                    f"{path}[{index}]",
                )
            )
        for index in range(common, len(left)):
            differences.append(
                {
                    "path": f"{path}[{index}]",
                    "kind": "missing_right",
                    "left": left[index],
                }
            )
        for index in range(common, len(right)):
            differences.append(
                {
                    "path": f"{path}[{index}]",
                    "kind": "missing_left",
                    "right": right[index],
                }
            )
        return differences
    if type(left) is not type(right) or left != right:
        return [
            {
                "path": path,
                "kind": "value",
                "left": left,
                "right": right,
            }
        ]
    return []


def load_report(path: pathlib.Path, runtime: str) -> tuple[dict[str, Any], str]:
    data = path.read_bytes()
    report = json.loads(data)
    if (
        report.get("schema_version") != 2
        or report.get("generator")
        != "tools/upstream/probe_global_host_api.py"
        or report.get("runtime_profile") != runtime
    ):
        raise ValueError(f"unexpected {runtime} report identity")
    probe.validate_observation(report["observation"], runtime)
    probe.validate_streams(
        report["streams"],
        report["observation"],
        runtime,
    )
    return report, sha256(data)


def relative_path(repo: pathlib.Path, path: pathlib.Path) -> str:
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError as error:
        raise ValueError("report path must be inside the repository") from error


def build_report(
    repo: pathlib.Path,
    qt5_path: pathlib.Path,
    qt6_path: pathlib.Path,
) -> dict[str, Any]:
    qt5, qt5_sha256 = load_report(qt5_path, "qt5")
    qt6, qt6_sha256 = load_report(qt6_path, "qt6")
    differences = compare_values(
        qt5["observation"],
        qt6["observation"],
    )
    source_path = repo / "tools/upstream/compare_global_host_api_reports.py"
    source = source_path.read_bytes()
    return {
        "schema_version": 2,
        "generator": (
            "tools/upstream/compare_global_host_api_reports.py"
        ),
        "upstream_commit": probe.UPSTREAM_COMMIT,
        "die_script_commit": probe.DIE_SCRIPT_COMMIT,
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
        "source": {
            "path": relative_path(repo, source_path),
            "bytes": len(source),
            "sha256": sha256(source),
        },
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
        default=repo / "docs/research/data/global-host-api-qt5.json",
    )
    parser.add_argument(
        "--qt6-report",
        type=pathlib.Path,
        default=repo / "docs/research/data/global-host-api-qt6.json",
    )
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=(
            repo / "docs/research/data/global-host-api-qt5-qt6.json"
        ),
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
