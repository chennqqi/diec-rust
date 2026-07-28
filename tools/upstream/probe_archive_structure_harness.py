#!/usr/bin/env python3
"""Probe pinned DIE structural archive mutation behavior."""

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
        "_diec_archive_structure_probe_base",
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
    "tools/corpus/generate_archive_structure_fixture.py"
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

EXPECTED_NAMES = {
    "sevenzip-control-none.7z",
    "sevenzip-start-header-crc-bit-flip.7z",
    "sevenzip-next-header-offset-past-eof.7z",
    "sevenzip-next-header-size-past-eof.7z",
    "sevenzip-next-header-offset-zero.7z",
    "sevenzip-next-header-offset-max-u64.7z",
    "sevenzip-next-header-size-zero.7z",
    "sevenzip-next-header-size-max-u64.7z",
    "sevenzip-next-header-crc-bit-flip.7z",
    "sevenzip-packed-crc-bit-flip.7z",
    "sevenzip-unpacked-size-plus-one.7z",
    "rar4-control-none.rar",
    "rar4-main-header-crc-bit-flip.rar",
    "rar4-file-header-crc-bit-flip.rar",
    "rar4-packed-size-plus-one.rar",
    "rar4-unpacked-size-plus-one.rar",
    "rar4-data-crc-bit-flip.rar",
    "rar4-method-unknown-0x7f.rar",
    "rar4-name-size-plus-one.rar",
    "rar4-packed-size-zero.rar",
    "rar4-packed-size-max-u32.rar",
    "rar4-unpacked-size-zero.rar",
    "rar4-unpacked-size-max-u32.rar",
    "rar4-name-size-zero.rar",
    "rar4-name-size-max-u16.rar",
    "cab-control-none.cab",
    "cab-cabinet-size-minus-one.cab",
    "cab-files-offset-plus-one.cab",
    "cab-data-offset-plus-one.cab",
    "cab-method-unknown-0xffff.cab",
    "cab-file-size-plus-one.cab",
    "cab-folder-offset-plus-one.cab",
    "cab-compressed-size-plus-one.cab",
    "cab-uncompressed-size-plus-one.cab",
    "cab-cabinet-size-zero.cab",
    "cab-cabinet-size-max-u32.cab",
    "cab-file-size-zero.cab",
    "cab-file-size-max-u32.cab",
    "cab-compressed-size-zero.cab",
    "cab-compressed-size-max-u16.cab",
    "iso9660-control-none.iso",
    "iso9660-descriptor-id-bit-flip.iso",
    "iso9660-volume-size-minus-one-block.iso",
    "iso9660-logical-block-size-set-1024.iso",
    "iso9660-root-extent-plus-one-block.iso",
    "iso9660-root-size-minus-one.iso",
    "iso9660-payload-record-length-zero.iso",
    "iso9660-payload-extent-plus-one-block.iso",
    "iso9660-payload-size-plus-one.iso",
    "iso9660-logical-block-size-zero.iso",
    "iso9660-logical-block-size-max-u16.iso",
    "iso9660-payload-record-length-max-u8.iso",
    "iso9660-payload-extent-zero.iso",
    "iso9660-payload-extent-max-u32.iso",
    "iso9660-payload-size-zero.iso",
    "iso9660-payload-size-max-u32.iso",
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
BINARY_1 = {
    "detection_names": ["Unknown"],
    "filetype": "Binary",
    "size": "1",
}
BINARY_331 = {
    "detection_names": ["Unknown"],
    "filetype": "Binary",
    "size": "331",
}
EMPTY_0 = {
    "detection_names": ["Empty file"],
    "filetype": "Binary",
    "size": "0",
}
NORMAL_CHILDREN = {
    "sevenzip-control-none.7z": [PDF_331],
    "sevenzip-start-header-crc-bit-flip.7z": [PDF_331],
    "sevenzip-next-header-crc-bit-flip.7z": [PDF_331],
    "sevenzip-packed-crc-bit-flip.7z": [PDF_331],
    "rar4-control-none.rar": [PDF_331],
    "rar4-main-header-crc-bit-flip.rar": [PDF_331],
    "rar4-file-header-crc-bit-flip.rar": [PDF_331],
    "rar4-packed-size-plus-one.rar": [PDF_331],
    "rar4-name-size-plus-one.rar": [PDF_331],
    "rar4-packed-size-max-u32.rar": [PDF_331],
    "rar4-name-size-zero.rar": [PDF_331],
    "rar4-name-size-max-u16.rar": [PDF_331],
    "cab-control-none.cab": [PDF_331],
    "cab-cabinet-size-minus-one.cab": [PDF_331],
    "cab-uncompressed-size-plus-one.cab": [PDF_331],
    "cab-cabinet-size-zero.cab": [PDF_331],
    "cab-cabinet-size-max-u32.cab": [PDF_331],
    "iso9660-control-none.iso": [PDF_331],
    "iso9660-volume-size-minus-one-block.iso": [PDF_331],
    "iso9660-root-size-minus-one.iso": [PDF_331],
    "iso9660-payload-size-plus-one.iso": [PDF_332],
    "iso9660-payload-record-length-max-u8.iso": [PDF_331],
}
AGGRESSIVE_ONLY_CHILDREN = {
    "cab-files-offset-plus-one.cab": [BINARY_1],
    "cab-method-unknown-0xffff.cab": [BINARY_331],
    "rar4-unpacked-size-zero.rar": [EMPTY_0],
    "cab-file-size-zero.cab": [EMPTY_0],
    "iso9660-payload-extent-zero.iso": [BINARY_331],
    "iso9660-payload-extent-max-u32.iso": [BINARY_331],
    "iso9660-payload-size-zero.iso": [EMPTY_0],
}
ISO_MAX_EXTENT_STDERR = (
    b"QBuffer::seek: Invalid pos: 8796093020160\n"
    b"QBuffer::seek: Invalid pos: 8796093020160\n"
)


class ProbeError(ValueError):
    """The archive structure fixture, oracle, or report is invalid."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def expected_root(sample_name: str) -> tuple[str, list[str]]:
    if sample_name.startswith("sevenzip-"):
        return "Binary", ["7-Zip"]
    if sample_name.startswith("rar4-"):
        return "RAR", ["Unknown"]
    if sample_name.startswith("cab-"):
        return "Binary", ["CAB"]
    if sample_name == "iso9660-descriptor-id-bit-flip.iso":
        return "Binary", ["Unknown"]
    if sample_name.startswith("iso9660-"):
        return "ISO 9660", ["Unknown"]
    raise ProbeError(f"unknown expected root: {sample_name}")


def expected_streams(
    sample_name: str,
    mode: str,
) -> list[dict[str, Any]]:
    if mode in {"default", "release_default"}:
        return []
    if (
        mode == "archive_aggressive"
        and sample_name in AGGRESSIVE_ONLY_CHILDREN
    ):
        return AGGRESSIVE_ONLY_CHILDREN[sample_name]
    return NORMAL_CHILDREN.get(sample_name, [])


def expected_stderr(sample_name: str, mode: str) -> bytes:
    if (
        sample_name == "iso9660-payload-extent-max-u32.iso"
        and mode in {"archive", "archive_aggressive"}
    ):
        return ISO_MAX_EXTENT_STDERR
    return b""


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
    if not isinstance(manifest["source_generator"], dict) or set(
        manifest["source_generator"]
    ) != {"path", "sha256"}:
        raise ProbeError("fixture source generator fields changed")
    if manifest["source_generator"]["path"] != SOURCE_GENERATOR:
        raise ProbeError("fixture source generator changed")
    root = pathlib.Path(__file__).resolve().parents[2]
    if manifest["source_generator"]["sha256"] != sha256(
        (root / SOURCE_GENERATOR).read_bytes()
    ):
        raise ProbeError("fixture source generator identity changed")
    if len(manifest["samples"]) != len(EXPECTED_NAMES):
        raise ProbeError("fixture sample count changed")

    declared = set()
    for sample in manifest["samples"]:
        if set(sample) != {
            "archive_format",
            "changed_byte_count",
            "changed_offset_max",
            "changed_offset_min",
            "control_name",
            "control_sha256",
            "field",
            "mutation",
            "name",
            "purpose",
            "sha256",
            "size",
        }:
            raise ProbeError("fixture sample fields changed")
        name = sample["name"]
        if (
            pathlib.PurePosixPath(name).name != name
            or name in declared
            or name not in EXPECTED_NAMES
        ):
            raise ProbeError(
                f"unsafe, unknown, or duplicate fixture name: {name}"
            )
        path = fixture_dir / name
        if path.is_symlink() or not path.is_file():
            raise ProbeError(
                f"fixture file missing or symlinked: {name}"
            )
        data = path.read_bytes()
        if (
            len(data) != sample["size"]
            or sha256(data) != sample["sha256"]
        ):
            raise ProbeError(f"fixture identity mismatch: {name}")
        if sample["field"] == "control":
            if (
                sample["changed_byte_count"] != 0
                or sample["changed_offset_min"] is not None
                or sample["changed_offset_max"] is not None
            ):
                raise ProbeError("control changed-byte metadata changed")
        elif (
            not isinstance(sample["changed_byte_count"], int)
            or sample["changed_byte_count"] < 1
            or not isinstance(sample["changed_offset_min"], int)
            or not isinstance(sample["changed_offset_max"], int)
        ):
            raise ProbeError("mutation changed-byte metadata changed")
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
    if process.stderr != expected_stderr(sample_name, mode):
        raise ProbeError(f"stderr changed: {sample_name}/{mode}")
    root_filetype, root_names = expected_root(sample_name)
    if (
        summary["root_filetype"] != root_filetype
        or summary["root_detection_names"] != root_names
    ):
        raise ProbeError(
            f"root detection changed: {sample_name}/{mode}"
        )
    streams = expected_streams(sample_name, mode)
    if (
        summary["streams"] != streams
        or summary["stream_count"] != len(streams)
    ):
        raise ProbeError(f"stream result changed: {sample_name}/{mode}")


def _case_stream_count(
    cases: dict[str, Any],
    sample: str,
    mode: str = "archive",
) -> int:
    return cases[sample][mode]["summary"]["stream_count"]


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

        differs_aggressively = (
            sample_name in AGGRESSIVE_ONLY_CHILDREN
        )
        if (
            raw_modes["archive"]
            != raw_modes["archive_aggressive"]
        ) != differs_aggressively:
            raise ProbeError(
                f"aggressive mode relationship changed: {sample_name}"
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

    facts = {
        "all_structure_cases_exit_zero_with_exact_stderr": all(
            case["exit_code"] == 0
            and case["stderr"]["sha256"]
            == sha256(expected_stderr(sample_name, mode))
            for sample_name, sample_cases in cases.items()
            for mode, case in sample_cases.items()
        ),
        "release_and_harness_default_outputs_are_equal": all(
            sample_cases["default"]["stdout"]
            == sample_cases["release_default"]["stdout"]
            and sample_cases["default"]["stderr"]
            == sample_cases["release_default"]["stderr"]
            for sample_cases in cases.values()
        ),
        "sevenzip_start_next_and_packed_crc_mutations_still_unpack": all(
            _case_stream_count(cases, sample) == 1
            for sample in (
                "sevenzip-start-header-crc-bit-flip.7z",
                "sevenzip-next-header-crc-bit-flip.7z",
                "sevenzip-packed-crc-bit-flip.7z",
            )
        ),
        "sevenzip_past_eof_and_unpacked_size_mutations_suppress_child": all(
            _case_stream_count(cases, sample) == 0
            for sample in (
                "sevenzip-next-header-offset-past-eof.7z",
                "sevenzip-next-header-size-past-eof.7z",
                "sevenzip-unpacked-size-plus-one.7z",
            )
        ),
        "sevenzip_zero_and_max_next_header_fields_suppress_child": all(
            _case_stream_count(cases, sample) == 0
            for sample in (
                "sevenzip-next-header-offset-zero.7z",
                "sevenzip-next-header-offset-max-u64.7z",
                "sevenzip-next-header-size-zero.7z",
                "sevenzip-next-header-size-max-u64.7z",
            )
        ),
        "rar4_header_crc_mutations_still_unpack": all(
            _case_stream_count(cases, sample) == 1
            for sample in (
                "rar4-main-header-crc-bit-flip.rar",
                "rar4-file-header-crc-bit-flip.rar",
            )
        ),
        "rar4_packed_and_name_size_plus_one_still_unpack": all(
            _case_stream_count(cases, sample) == 1
            for sample in (
                "rar4-packed-size-plus-one.rar",
                "rar4-name-size-plus-one.rar",
            )
        ),
        "rar4_data_crc_method_and_unpacked_size_mutations_suppress_child": all(
            _case_stream_count(cases, sample) == 0
            for sample in (
                "rar4-data-crc-bit-flip.rar",
                "rar4-method-unknown-0x7f.rar",
                "rar4-unpacked-size-plus-one.rar",
            )
        ),
        "rar4_packed_max_and_name_extremes_still_unpack": all(
            _case_stream_count(cases, sample) == 1
            for sample in (
                "rar4-packed-size-max-u32.rar",
                "rar4-name-size-zero.rar",
                "rar4-name-size-max-u16.rar",
            )
        ),
        "rar4_packed_zero_and_unpacked_max_suppress_child": all(
            _case_stream_count(cases, sample) == 0
            for sample in (
                "rar4-packed-size-zero.rar",
                "rar4-unpacked-size-max-u32.rar",
            )
        ),
        "rar4_unpacked_zero_is_aggressive_empty_child": (
            _case_stream_count(
                cases,
                "rar4-unpacked-size-zero.rar",
            )
            == 0
            and cases["rar4-unpacked-size-zero.rar"][
                "archive_aggressive"
            ]["summary"]["streams"]
            == [EMPTY_0]
        ),
        "cabinet_size_and_uncompressed_size_mutations_still_unpack": all(
            _case_stream_count(cases, sample) == 1
            for sample in (
                "cab-cabinet-size-minus-one.cab",
                "cab-uncompressed-size-plus-one.cab",
            )
        ),
        "cab_files_offset_and_unknown_method_are_aggressive_only": all(
            _case_stream_count(cases, sample) == 0
            and _case_stream_count(
                cases,
                sample,
                "archive_aggressive",
            )
            == 1
            for sample in AGGRESSIVE_ONLY_CHILDREN
        ),
        "cab_data_file_folder_and_compressed_size_mutations_suppress_child": all(
            _case_stream_count(cases, sample) == 0
            for sample in (
                "cab-data-offset-plus-one.cab",
                "cab-file-size-plus-one.cab",
                "cab-folder-offset-plus-one.cab",
                "cab-compressed-size-plus-one.cab",
            )
        ),
        "cab_cabinet_size_extremes_still_unpack": all(
            _case_stream_count(cases, sample) == 1
            for sample in (
                "cab-cabinet-size-zero.cab",
                "cab-cabinet-size-max-u32.cab",
            )
        ),
        "cab_file_zero_is_aggressive_empty_child": (
            _case_stream_count(cases, "cab-file-size-zero.cab") == 0
            and cases["cab-file-size-zero.cab"][
                "archive_aggressive"
            ]["summary"]["streams"]
            == [EMPTY_0]
        ),
        "cab_file_max_and_compressed_extremes_suppress_child": all(
            _case_stream_count(cases, sample) == 0
            for sample in (
                "cab-file-size-max-u32.cab",
                "cab-compressed-size-zero.cab",
                "cab-compressed-size-max-u16.cab",
            )
        ),
        "iso9660_descriptor_id_mutation_falls_back_to_binary": (
            cases["iso9660-descriptor-id-bit-flip.iso"]["archive"][
                "summary"
            ]["root_filetype"]
            == "Binary"
        ),
        "iso9660_volume_and_root_size_mutations_still_unpack": all(
            _case_stream_count(cases, sample) == 1
            for sample in (
                "iso9660-volume-size-minus-one-block.iso",
                "iso9660-root-size-minus-one.iso",
            )
        ),
        "iso9660_payload_size_controls_declared_child_size": (
            cases["iso9660-payload-size-plus-one.iso"]["archive"][
                "summary"
            ]["streams"]
            == [PDF_332]
        ),
        "iso9660_block_extent_and_record_mutations_suppress_child": all(
            _case_stream_count(cases, sample) == 0
            for sample in (
                "iso9660-logical-block-size-set-1024.iso",
                "iso9660-root-extent-plus-one-block.iso",
                "iso9660-payload-record-length-zero.iso",
                "iso9660-payload-extent-plus-one-block.iso",
            )
        ),
        "iso9660_block_extremes_and_payload_size_max_suppress_child": all(
            _case_stream_count(cases, sample) == 0
            for sample in (
                "iso9660-logical-block-size-zero.iso",
                "iso9660-logical-block-size-max-u16.iso",
                "iso9660-payload-size-max-u32.iso",
            )
        ),
        "iso9660_record_length_max_still_unpacks": (
            _case_stream_count(
                cases,
                "iso9660-payload-record-length-max-u8.iso",
            )
            == 1
        ),
        "iso9660_zero_size_is_aggressive_empty_child": (
            _case_stream_count(
                cases,
                "iso9660-payload-size-zero.iso",
            )
            == 0
            and cases["iso9660-payload-size-zero.iso"][
                "archive_aggressive"
            ]["summary"]["streams"]
            == [EMPTY_0]
        ),
        "iso9660_extent_extremes_are_aggressive_binary_children": all(
            _case_stream_count(cases, sample) == 0
            and cases[sample]["archive_aggressive"]["summary"][
                "streams"
            ]
            == [BINARY_331]
            for sample in (
                "iso9660-payload-extent-zero.iso",
                "iso9660-payload-extent-max-u32.iso",
            )
        ),
        "iso9660_max_extent_emits_exact_seek_diagnostics": all(
            cases["iso9660-payload-extent-max-u32.iso"][mode][
                "stderr"
            ]
            == {
                "artifact_sha256": sha256(ISO_MAX_EXTENT_STDERR),
                "bytes": len(ISO_MAX_EXTENT_STDERR),
                "sha256": sha256(ISO_MAX_EXTENT_STDERR),
            }
            for mode in ("archive", "archive_aggressive")
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
                "docs/research/data/archive-structure-corpus.json"
            ),
            "sample_count": len(manifest["samples"]),
            "sha256": manifest_sha256,
        },
        "generator": (
            "tools/upstream/probe_archive_structure_harness.py"
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
            / "archive-structure-corpus.json"
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
