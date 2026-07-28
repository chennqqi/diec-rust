#!/usr/bin/env python3
"""Probe pinned DIE ISO9660 dual-endian conflict behavior."""

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
        "_diec_iso9660_endian_probe_base",
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
    "tools/corpus/generate_iso9660_endian_fixture.py"
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
FIELD_NAMES = {
    "pvd-volume-space-size",
    "pvd-volume-set-size",
    "pvd-volume-sequence-number",
    "pvd-logical-block-size",
    "pvd-path-table-size",
    "pvd-root-extent",
    "pvd-root-size",
    "pvd-root-volume-sequence",
    "dot-extent",
    "dot-size",
    "dot-volume-sequence",
    "dotdot-extent",
    "dotdot-size",
    "dotdot-volume-sequence",
    "payload-extent",
    "payload-size",
    "payload-volume-sequence",
}
SIDES = {"little", "big"}
EXPECTED_NAMES = {
    "iso9660-control.iso",
    *{
        f"iso9660-{field}-{side}-alternate.iso"
        for field in FIELD_NAMES
        for side in SIDES
    },
}
LITTLE_SUPPRESSED_FIELDS = {
    "pvd-logical-block-size",
    "pvd-root-extent",
    "payload-extent",
}
LITTLE_SIZE_FIELD = "payload-size"
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


class ProbeError(ValueError):
    """The ISO9660 endian fixture, oracle, or report is invalid."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def expected_streams(
    sample_name: str,
    mode: str,
) -> list[dict[str, Any]]:
    if mode in {"default", "release_default"}:
        return []
    for field in LITTLE_SUPPRESSED_FIELDS:
        if sample_name == (
            f"iso9660-{field}-little-alternate.iso"
        ):
            return []
    if sample_name == (
        f"iso9660-{LITTLE_SIZE_FIELD}-little-alternate.iso"
    ):
        return [PDF_332]
    return [PDF_331]


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
    if not isinstance(samples, list) or len(samples) != 35:
        raise ProbeError("fixture sample count changed")

    declared = set()
    pairs = set()
    sample_fields = {
        "alternate_value",
        "changed_byte_count",
        "changed_offset_max",
        "changed_offset_min",
        "control_sha256",
        "control_value",
        "field",
        "field_offset",
        "field_width",
        "mutated_side",
        "name",
        "purpose",
        "sha256",
        "size",
    }
    for sample in samples:
        if not isinstance(sample, dict) or set(sample) != sample_fields:
            raise ProbeError("fixture sample fields changed")
        name = sample["name"]
        if (
            not isinstance(name, str)
            or pathlib.PurePosixPath(name).name != name
            or name in declared
            or name not in EXPECTED_NAMES
        ):
            raise ProbeError(
                f"unsafe, unknown, or duplicate fixture: {name}"
            )
        if name == "iso9660-control.iso":
            if (
                sample["field"] != "control"
                or sample["mutated_side"] is not None
                or sample["changed_byte_count"] != 0
            ):
                raise ProbeError("fixture control identity changed")
        else:
            field = sample["field"]
            side = sample["mutated_side"]
            if (
                field not in FIELD_NAMES
                or side not in SIDES
                or sample["field_width"] not in {2, 4}
                or not isinstance(sample["field_offset"], int)
                or sample["changed_byte_count"] < 1
            ):
                raise ProbeError(
                    f"fixture conflict identity changed: {name}"
                )
            pairs.add((field, side))
        path = fixture_dir / name
        if path.is_symlink() or not path.is_file():
            raise ProbeError(f"fixture file missing or symlinked: {name}")
        data = path.read_bytes()
        if len(data) != sample["size"] or sha256(data) != sample["sha256"]:
            raise ProbeError(f"fixture identity mismatch: {name}")
        declared.add(name)
    if declared != EXPECTED_NAMES:
        raise ProbeError("fixture expected inventory changed")
    if pairs != {
        (field, side)
        for field in FIELD_NAMES
        for side in SIDES
    }:
        raise ProbeError("fixture field/side product changed")
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
    streams = expected_streams(sample_name, mode)
    if (
        summary["root_filetype"] != "ISO 9660"
        or summary["root_detection_names"] != ["Unknown"]
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
        if raw_modes["archive"] != raw_modes["archive_aggressive"]:
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

    def streams(sample: str) -> list[dict[str, Any]]:
        return cases[sample]["archive"]["summary"]["streams"]

    big_samples = [
        f"iso9660-{field}-big-alternate.iso"
        for field in sorted(FIELD_NAMES)
    ]
    inert_little_fields = (
        FIELD_NAMES
        - LITTLE_SUPPRESSED_FIELDS
        - {LITTLE_SIZE_FIELD}
    )
    facts = {
        "all_endian_conflict_cases_exit_zero_without_stderr": all(
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
        "all_conflicts_keep_iso9660_root_detection": all(
            case["summary"]["root_filetype"] == "ISO 9660"
            and case["summary"]["root_detection_names"] == ["Unknown"]
            for sample_cases in cases.values()
            for case in sample_cases.values()
        ),
        "all_big_endian_alternates_keep_control_child_projection": all(
            streams(sample) == [PDF_331]
            for sample in big_samples
        ),
        "little_endian_offsets_and_block_size_control_child_reachability": all(
            streams(
                f"iso9660-{field}-little-alternate.iso"
            )
            == []
            for field in LITTLE_SUPPRESSED_FIELDS
        ),
        "little_endian_payload_size_controls_declared_child_size": (
            streams(
                "iso9660-payload-size-little-alternate.iso"
            )
            == [PDF_332]
        ),
        "other_little_endian_alternates_keep_control_child_projection": all(
            streams(
                f"iso9660-{field}-little-alternate.iso"
            )
            == [PDF_331]
            for field in inert_little_fields
        ),
        "archive_and_aggressive_outputs_are_equal": all(
            sample_cases["archive"]["stdout"]
            == sample_cases["archive_aggressive"]["stdout"]
            and sample_cases["archive"]["stderr"]
            == sample_cases["archive_aggressive"]["stderr"]
            for sample_cases in cases.values()
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
                "docs/research/data/iso9660-endian-corpus.json"
            ),
            "sample_count": len(manifest["samples"]),
            "sha256": manifest_sha256,
        },
        "generator": (
            "tools/upstream/probe_iso9660_endian_harness.py"
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
            / "iso9660-endian-corpus.json"
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
