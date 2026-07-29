#!/usr/bin/env python3
"""Build the pre-execution macOS cache-state capability plan."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
EVALUATED_ON = "2026-07-30"
UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
PLATFORM = "macos-x86_64-cache-state"
XNU_COMMIT = "f6217f891ac0bb64f3d375211650a4c1ff8ca1ea"
XNU_SOURCES = {
    "bsd/sys/fcntl.h": {
        "sha256": (
            "0f93c8918a70ffafe20bfe9c72e671fd"
            "e67438cbee9f9de8c2f87b5c704c9a9e"
        ),
        "evidence": (
            "F_NOCACHE is fd-local and F_GLOBAL_NOCACHE is global "
            "for the file"
        ),
    },
    "bsd/kern/kern_descrip.c": {
        "sha256": (
            "480cfed4e987be874bd71fb6933c254ad"
            "f9fb1f36de8496dee8f351b18da13b1"
        ),
        "evidence": (
            "F_NOCACHE toggles fileglob FNOCACHE and "
            "F_GLOBAL_NOCACHE toggles vnode nocache; neither fcntl "
            "case performs an eviction or residency check"
        ),
    },
}
SOURCE_PATHS = (
    "tools/benchmark/probe_macos_file_content_cache.c",
    "tools/benchmark/collect_macos_cache_state_candidate.py",
    "tools/benchmark/validate_macos_cache_state_candidate.py",
)
OFFICIAL_MANUALS = [
    {
        "interface": "fcntl(F_NOCACHE)",
        "url": (
            "https://developer.apple.com/library/archive/documentation/"
            "System/Conceptual/ManPages_iPhoneOS/man2/fcntl.2.html"
        ),
        "contract": "turns data caching off or on for the file descriptor",
    },
    {
        "interface": "mincore",
        "url": (
            "https://developer.apple.com/library/archive/documentation/"
            "System/Conceptual/ManPages_iPhoneOS/man2/mincore.2.html"
        ),
        "contract": "returns current in-core residency per mapped page",
    },
    {
        "interface": "msync(MS_INVALIDATE)",
        "url": (
            "https://developer.apple.com/library/archive/documentation/"
            "System/Conceptual/ManPages_iPhoneOS/man2/msync.2.html"
        ),
        "contract": "invalidates cached data in the mapped range",
    },
    {
        "interface": "madvise(MADV_DONTNEED)",
        "url": (
            "https://developer.apple.com/library/archive/documentation/"
            "System/Conceptual/ManPages_iPhoneOS/man2/madvise.2.html"
        ),
        "contract": (
            "advises that the mapped range is not expected to be "
            "accessed soon; it is not an eviction proof"
        ),
    },
]


class PlanError(ValueError):
    """The macOS cache-state plan cannot be generated safely."""


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def build_plan(root: Path) -> dict[str, Any]:
    sources = {}
    for relative in SOURCE_PATHS:
        path = root / relative
        if not path.is_file():
            raise PlanError(f"source path missing: {relative}")
        sources[relative] = sha256(path.read_bytes())
    xnu_base = (
        "https://raw.githubusercontent.com/"
        f"apple-oss-distributions/xnu/{XNU_COMMIT}/"
    )
    xnu_sources = {
        relative: {
            **details,
            "url": xnu_base + relative,
        }
        for relative, details in sorted(XNU_SOURCES.items())
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "evaluated_on": EVALUATED_ON,
        "result": "infrastructure_ready_runtime_missing",
        "platform": PLATFORM,
        "upstream_commit": UPSTREAM_COMMIT,
        "sources": dict(sorted(sources.items())),
        "darwin_contract": {
            "xnu_repository": (
                "https://github.com/apple-oss-distributions/xnu"
            ),
            "xnu_commit": XNU_COMMIT,
            "xnu_sources": xnu_sources,
            "official_manuals": OFFICIAL_MANUALS,
        },
        "strategy": {
            "warm": {
                "status": "portable_name_allowed",
                "basis": "runner-defined warmup with no eviction",
            },
            "file_content_nonresident_metadata_warm": {
                "status": "runtime_candidate_not_admitted",
                "candidate": (
                    "fully warm an mmap, apply "
                    "msync(MS_SYNC|MS_INVALIDATE), then require "
                    "per-page mincore residency to be zero"
                ),
                "rejected_substitutes": [
                    "F_NOCACHE or F_GLOBAL_NOCACHE without eviction proof",
                    "MADV_DONTNEED without mincore postcondition",
                    "a successful control call without per-page evidence",
                ],
            },
            "system_cold": {
                "status": "dedicated_reboot_only_not_admitted",
                "basis": (
                    "no reviewed public per-process contract proves "
                    "system-wide file data and metadata cold; use a "
                    "disposable dedicated reboot boundary"
                ),
            },
            "generic_cold": {
                "status": "forbidden",
            },
        },
        "candidate_experiment": {
            "host": "native Darwin x86_64",
            "fixture": (
                "16 MiB deterministic regular file, unlinked before "
                "any cache operation"
            ),
            "repetitions": 2,
            "compiler_arguments": [
                "-std=c11",
                "-O2",
                "-Wall",
                "-Wextra",
                "-Werror",
            ],
            "required_observations": [
                "all fixture pages resident after explicit touch",
                "residency immediately after fd-local F_NOCACHE toggle",
                "residency after MS_SYNC|MS_INVALIDATE",
                "byte-identical structured observations across two fixtures",
            ],
            "safety": {
                "benchmark_files_touched": False,
                "system_cache_flush_executed": False,
                "temporary_fixture_unlinked_before_probe": True,
            },
            "collector": (
                "tools/benchmark/"
                "collect_macos_cache_state_candidate.py"
            ),
            "validator": (
                "tools/benchmark/"
                "validate_macos_cache_state_candidate.py"
            ),
        },
        "admission": {
            "warm_admitted": True,
            "file_content_state_admitted": False,
            "system_cold_admitted": False,
            "reason": (
                "Apple contracts identify a testable per-file candidate, "
                "but no Darwin runtime report or benchmark-closure "
                "integration exists; dedicated system-cold is also missing"
            ),
        },
    }


def serialize(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=root)
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            root
            / "docs/research/data/"
            "macos-benchmark-cache-state-plan.json"
        ),
    )
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    raw = serialize(build_plan(args.root.resolve()))
    if args.check:
        if not args.output.is_file() or args.output.read_bytes() != raw:
            raise PlanError("committed macOS cache-state plan differs")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
