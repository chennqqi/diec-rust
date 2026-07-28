#!/usr/bin/env python3
"""Probe pinned DIE multi-record archive ordering behavior."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import sys
from typing import Any


def _load_probe_base():
    module_path = pathlib.Path(__file__).with_name(
        "probe_archive_truncation_harness.py"
    )
    spec = importlib.util.spec_from_file_location(
        "_diec_archive_multirecord_probe_base",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load archive probe base")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BASE = _load_probe_base()
UPSTREAM_COMMIT = BASE.UPSTREAM_COMMIT
FIXTURE_GENERATOR = (
    "tools/corpus/generate_archive_multirecord_fixture.py"
)
SOURCE_GENERATOR = "tools/corpus/generate_archive_format_fixture.py"
PROBE_BASE = "tools/upstream/probe_archive_truncation_harness.py"
HARNESS_SOURCE = BASE.HARNESS_SOURCE
HARNESS_DOCKERFILE = BASE.HARNESS_DOCKERFILE
IMAGE = BASE.IMAGE
HARNESS_BINARY = BASE.HARNESS_BINARY
RELEASE_BINARY = BASE.RELEASE_BINARY
DATABASE_ARGS = BASE.DATABASE_ARGS
SOURCE_PATHS = BASE.SOURCE_PATHS
FORMAT_PREFIXES = {
    "sevenzip": ("7-Zip", "Binary", "7z"),
    "rar4": ("Unknown", "RAR", "rar"),
    "cab": ("CAB", "Binary", "cab"),
    "iso9660": ("Unknown", "ISO 9660", "iso"),
}
ORDER_CASES = (
    "forward",
    "reverse",
    "duplicate-name",
    "empty-first",
)
EXPECTED_NAMES = {
    f"{prefix}-{case_name}.{extension}"
    for prefix, (_, _, extension) in FORMAT_PREFIXES.items()
    for case_name in ORDER_CASES
}
PDF_331 = {
    "detection_names": ["PDF", "HeaderComment"],
    "filetype": "PDF",
    "size": "331",
}
PDF_332 = {
    "detection_names": ["PDF", "HeaderComment"],
    "filetype": "PDF",
    "size": "332",
}
EMPTY_0 = {
    "detection_names": ["Empty file"],
    "filetype": "Binary",
    "size": "0",
}


class ProbeError(ValueError):
    """The multi-record fixture, oracle, or report is invalid."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def expected_root(sample_name: str) -> tuple[str, list[str]]:
    for prefix, (detection, filetype, _) in FORMAT_PREFIXES.items():
        if sample_name.startswith(prefix + "-"):
            return filetype, [detection]
    raise ProbeError(f"unknown expected root: {sample_name}")


def expected_streams(
    sample_name: str,
    mode: str,
) -> list[dict[str, Any]]:
    if mode in {"default", "release_default"}:
        return []
    if "-reverse." in sample_name:
        return [PDF_332, PDF_331]
    if "-empty-first." in sample_name:
        if mode == "archive_aggressive":
            return [EMPTY_0, PDF_331]
        return [PDF_331]
    return [PDF_331, PDF_332]


def load_fixture(
    fixture_dir: pathlib.Path,
    manifest_path: pathlib.Path,
) -> tuple[dict[str, Any], str]:
    manifest_bytes = manifest_path.read_bytes()
    try:
        manifest = BASE.strict_json(manifest_bytes)
    except Exception as error:
        raise ProbeError(str(error)) from error
    if not isinstance(manifest, dict) or set(manifest) != {
        "generator",
        "license",
        "samples",
        "schema_version",
        "source_generator",
    }:
        raise ProbeError("fixture manifest fields changed")
    if manifest["schema_version"] != 1:
        raise ProbeError("unsupported fixture schema")
    if manifest["generator"] != FIXTURE_GENERATOR:
        raise ProbeError("unexpected fixture generator")
    if manifest["license"] != "project-generated":
        raise ProbeError("fixture license changed")
    root = pathlib.Path(__file__).resolve().parents[2]
    source = manifest["source_generator"]
    if (
        not isinstance(source, dict)
        or set(source) != {"path", "sha256"}
        or source["path"] != SOURCE_GENERATOR
        or source["sha256"]
        != sha256((root / SOURCE_GENERATOR).read_bytes())
    ):
        raise ProbeError("fixture source generator identity changed")
    samples = manifest["samples"]
    if not isinstance(samples, list) or len(samples) != 16:
        raise ProbeError("fixture sample count changed")

    declared = set()
    for sample in samples:
        if set(sample) != {
            "archive_format",
            "entries",
            "name",
            "order_case",
            "purpose",
            "sha256",
            "size",
        }:
            raise ProbeError("fixture sample fields changed")
        name = sample["name"]
        entries = sample["entries"]
        if (
            pathlib.PurePosixPath(name).name != name
            or name in declared
            or name not in EXPECTED_NAMES
            or sample["order_case"] not in ORDER_CASES
            or not isinstance(entries, list)
            or len(entries) != 2
        ):
            raise ProbeError(
                f"unsafe, unknown, or duplicate fixture: {name}"
            )
        for entry in entries:
            if set(entry) != {"name", "sha256", "size"}:
                raise ProbeError("fixture entry fields changed")
            if (
                not isinstance(entry["name"], str)
                or not entry["name"]
                or not isinstance(entry["size"], int)
                or entry["size"] < 0
                or not isinstance(entry["sha256"], str)
                or len(entry["sha256"]) != 64
            ):
                raise ProbeError("fixture entry identity changed")
        path = fixture_dir / name
        if path.is_symlink() or not path.is_file():
            raise ProbeError(f"fixture file missing or symlinked: {name}")
        data = path.read_bytes()
        if len(data) != sample["size"] or sha256(data) != sample["sha256"]:
            raise ProbeError(f"fixture identity mismatch: {name}")
        declared.add(name)
    if declared != EXPECTED_NAMES:
        raise ProbeError("fixture expected inventory changed")
    actual = {
        path.name
        for path in fixture_dir.iterdir()
        if path.is_file() and path.name != "manifest.json"
    }
    if actual != declared:
        raise ProbeError("fixture file inventory mismatch")
    return manifest, sha256(manifest_bytes)


def validate_case(
    *,
    sample_name: str,
    mode: str,
    process: subprocess.CompletedProcess[bytes],
    summary: dict[str, Any],
) -> None:
    if process.returncode != 0:
        raise ProbeError(f"nonzero exit: {sample_name}/{mode}")
    if process.stderr:
        raise ProbeError(f"stderr changed: {sample_name}/{mode}")
    root_filetype, root_names = expected_root(sample_name)
    streams = expected_streams(sample_name, mode)
    if (
        summary["root_filetype"] != root_filetype
        or summary["root_detection_names"] != root_names
        or summary["streams"] != streams
        or summary["stream_count"] != len(streams)
    ):
        raise ProbeError(f"summary changed: {sample_name}/{mode}")


def build_report(
    fixture_dir: pathlib.Path,
    manifest_path: pathlib.Path,
) -> dict[str, Any]:
    manifest, manifest_sha256 = load_fixture(
        fixture_dir,
        manifest_path,
    )
    container_paths = (
        HARNESS_BINARY,
        RELEASE_BINARY,
        *SOURCE_PATHS.values(),
    )
    container_files = BASE.read_container_files(container_paths)
    artifacts: dict[str, dict[str, Any]] = {}
    cases: dict[str, Any] = {}

    for sample in manifest["samples"]:
        sample_name = sample["name"]
        sample_cases: dict[str, Any] = {}
        raw_modes: dict[str, tuple[bytes, bytes]] = {}
        for mode, flags in (
            ("default", ()),
            ("archive", ("--archive",)),
            (
                "archive_aggressive",
                ("--archive", "--aggressive"),
            ),
        ):
            arguments = (*flags, f"/fixture/{sample_name}")
            process = BASE.run_binary(
                binary=HARNESS_BINARY,
                fixture_dir=fixture_dir,
                arguments=arguments,
            )
            try:
                summary = BASE.summarize(
                    BASE.strict_json(process.stdout)
                )
            except Exception as error:
                raise ProbeError(
                    f"invalid JSON: {sample_name}/{mode}: {error}"
                ) from error
            validate_case(
                sample_name=sample_name,
                mode=mode,
                process=process,
                summary=summary,
            )
            raw_modes[mode] = (process.stdout, process.stderr)
            sample_cases[mode] = {
                "arguments": list(arguments),
                "exit_code": process.returncode,
                "stderr": BASE.raw_ref(process.stderr, artifacts),
                "stdout": BASE.raw_ref(process.stdout, artifacts),
                "summary": summary,
            }
        differs_aggressively = "-empty-first." in sample_name
        if (
            raw_modes["archive"]
            != raw_modes["archive_aggressive"]
        ) != differs_aggressively:
            raise ProbeError(
                f"aggressive relationship changed: {sample_name}"
            )

        release_arguments = (
            "--json",
            *DATABASE_ARGS,
            f"/fixture/{sample_name}",
        )
        release = BASE.run_binary(
            binary=RELEASE_BINARY,
            fixture_dir=fixture_dir,
            arguments=release_arguments,
        )
        try:
            release_summary = BASE.summarize(
                BASE.strict_json(release.stdout)
            )
        except Exception as error:
            raise ProbeError(
                f"invalid release JSON: {sample_name}: {error}"
            ) from error
        validate_case(
            sample_name=sample_name,
            mode="release_default",
            process=release,
            summary=release_summary,
        )
        if (release.stdout, release.stderr) != raw_modes["default"]:
            raise ProbeError(
                f"harness/release default drift: {sample_name}"
            )
        sample_cases["release_default"] = {
            "arguments": list(release_arguments),
            "exit_code": release.returncode,
            "stderr": BASE.raw_ref(release.stderr, artifacts),
            "stdout": BASE.raw_ref(release.stdout, artifacts),
            "summary": release_summary,
        }
        cases[sample_name] = sample_cases

    def archive_streams(sample: str, mode: str = "archive"):
        return cases[sample][mode]["summary"]["streams"]

    facts = {
        "all_multirecord_cases_exit_zero_without_stderr": all(
            case["exit_code"] == 0 and case["stderr"]["bytes"] == 0
            for sample_cases in cases.values()
            for case in sample_cases.values()
        ),
        "release_and_harness_default_outputs_are_equal": all(
            sample_cases["default"]["stdout"]
            == sample_cases["release_default"]["stdout"]
            and sample_cases["default"]["stderr"]
            == sample_cases["release_default"]["stderr"]
            for sample_cases in cases.values()
        ),
        "all_formats_preserve_forward_record_order": all(
            archive_streams(f"{prefix}-forward.{extension}")
            == [PDF_331, PDF_332]
            for prefix, (_, _, extension) in FORMAT_PREFIXES.items()
        ),
        "all_formats_preserve_reverse_record_order": all(
            archive_streams(f"{prefix}-reverse.{extension}")
            == [PDF_332, PDF_331]
            for prefix, (_, _, extension) in FORMAT_PREFIXES.items()
        ),
        "all_formats_keep_both_duplicate_name_records": all(
            archive_streams(
                f"{prefix}-duplicate-name.{extension}"
            )
            == [PDF_331, PDF_332]
            for prefix, (_, _, extension) in FORMAT_PREFIXES.items()
        ),
        "normal_archive_skips_empty_record_and_keeps_later_pdf": all(
            archive_streams(
                f"{prefix}-empty-first.{extension}"
            )
            == [PDF_331]
            for prefix, (_, _, extension) in FORMAT_PREFIXES.items()
        ),
        "aggressive_archive_keeps_empty_record_in_original_order": all(
            archive_streams(
                f"{prefix}-empty-first.{extension}",
                "archive_aggressive",
            )
            == [EMPTY_0, PDF_331]
            for prefix, (_, _, extension) in FORMAT_PREFIXES.items()
        ),
        "nonempty_archive_outputs_ignore_aggressive_flag": all(
            sample_cases["archive"]["stdout"]
            == sample_cases["archive_aggressive"]["stdout"]
            and sample_cases["archive"]["stderr"]
            == sample_cases["archive_aggressive"]["stderr"]
            for sample_name, sample_cases in cases.items()
            if "-empty-first." not in sample_name
        ),
    }
    root = pathlib.Path(__file__).resolve().parents[2]
    return {
        "binaries": {
            "harness": {
                "path": HARNESS_BINARY,
                "sha256": sha256(container_files[HARNESS_BINARY]),
                "size": len(container_files[HARNESS_BINARY]),
            },
            "release": {
                "path": RELEASE_BINARY,
                "sha256": sha256(container_files[RELEASE_BINARY]),
                "size": len(container_files[RELEASE_BINARY]),
            },
        },
        "cases": cases,
        "execution_count": len(cases) * 4,
        "facts": facts,
        "failures": [],
        "fixture_manifest": {
            "path": (
                "docs/research/data/archive-multirecord-corpus.json"
            ),
            "sample_count": len(manifest["samples"]),
            "sha256": manifest_sha256,
        },
        "generator": (
            "tools/upstream/probe_archive_multirecord_harness.py"
        ),
        "generator_sha256": sha256(pathlib.Path(__file__).read_bytes()),
        "image": {
            **BASE.inspect_image(),
            "name": IMAGE,
        },
        "local_sources": {
            "fixture_generator": {
                "path": FIXTURE_GENERATOR,
                "sha256": sha256(
                    (root / FIXTURE_GENERATOR).read_bytes()
                ),
            },
            "source_generator": {
                "path": SOURCE_GENERATOR,
                "sha256": sha256(
                    (root / SOURCE_GENERATOR).read_bytes()
                ),
            },
            "probe_base": {
                "path": PROBE_BASE,
                "sha256": sha256((root / PROBE_BASE).read_bytes()),
            },
            "harness_dockerfile": {
                "path": HARNESS_DOCKERFILE,
                "sha256": sha256(
                    (root / HARNESS_DOCKERFILE).read_bytes()
                ),
            },
            "harness_source": {
                "path": HARNESS_SOURCE,
                "sha256": sha256(
                    (root / HARNESS_SOURCE).read_bytes()
                ),
            },
        },
        "passed": all(facts.values()),
        "platform": "linux-x86_64-qt5",
        "raw_artifacts": artifacts,
        "remaining_gap": "CAP-GAP-006",
        "resource_limits": {
            "container_root": "read-only",
            "cpus": 1,
            "fixture_mount": "read-only",
            "memory_bytes": 512 * 1024 * 1024,
            "network": "none",
            "pids": 128,
            "timeout_seconds_per_execution": 60,
        },
        "schema_version": 1,
        "source_contract": BASE.source_contract(container_files),
        "upstream_commit": UPSTREAM_COMMIT,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    root = pathlib.Path(__file__).resolve().parents[2]
    parser.add_argument("--fixture-dir", required=True, type=pathlib.Path)
    parser.add_argument(
        "--manifest",
        type=pathlib.Path,
        default=(
            root
            / "docs"
            / "research"
            / "data"
            / "archive-multirecord-corpus.json"
        ),
    )
    parser.add_argument("--output", required=True, type=pathlib.Path)
    args = parser.parse_args()
    report = build_report(
        args.fixture_dir.resolve(),
        args.manifest.resolve(),
    )
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
