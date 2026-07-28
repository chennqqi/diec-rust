#!/usr/bin/env python3
"""Probe 7Z coders plus RAR4/CAB/ISO members with the pinned harness."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import pathlib
import subprocess
import zlib
from typing import Any


UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
FIXTURE_GENERATOR = "tools/corpus/generate_archive_format_fixture.py"
FIXTURE_REQUIREMENTS = "tools/corpus/requirements-archive-format.txt"
HARNESS_SOURCE = "tools/upstream/archive_harness_main.cpp"
HARNESS_DOCKERFILE = "tools/upstream/Dockerfile.archive-harness-qt5"
IMAGE = "diec-rust/upstream-archive-harness:74eaf505"
HARNESS_BINARY = "/opt/die-build/src/console/diec-archive-harness"
RELEASE_BINARY = "/opt/die-build/src/console/diec"
DATABASE_ARGS = (
    "--database",
    "/opt/die-source/Detect-It-Easy/db",
    "--extradatabase",
    "/opt/die-source/Detect-It-Easy/db_extra",
    "--customdatabase",
    "/opt/die-source/Detect-It-Easy/db_custom",
)
SOURCE_PATHS = {
    "engine": "/opt/die-source/XScanEngine/xscanengine.cpp",
    "sevenzip": "/opt/die-source/XArchive/xsevenzip.cpp",
    "sevenzip_methods": "/opt/die-source/XArchive/xsevenzip.cpp",
    "sevenzip_filters": "/opt/die-source/XArchive/xsevenzip.cpp",
    "decompress_dispatch": "/opt/die-source/XArchive/xdecompress.cpp",
    "deflate_decoder": (
        "/opt/die-source/XArchive/Algos/xdeflatedecoder.cpp"
    ),
    "bcj2_dispatch": "/opt/die-source/XArchive/xdecompress.cpp",
    "bcj2_decoder": (
        "/opt/die-source/XArchive/Algos/xbcj2decoder.cpp"
    ),
    "sevenzip_bcj2_graph": "/opt/die-source/XArchive/xsevenzip.cpp",
    "rar": "/opt/die-source/XArchive/xrar.cpp",
    "cab": "/opt/die-source/XArchive/xcab.cpp",
    "cab_lzx_method": "/opt/die-source/XArchive/xcab.cpp",
    "cab_unknown_method": "/opt/die-source/XArchive/xcab.cpp",
    "cab_decompress_dispatch": "/opt/die-source/XArchive/xdecompress.cpp",
    "iso9660": "/opt/die-source/XArchive/xiso9660.cpp",
}
SOURCE_PATTERNS = {
    "engine": (
        "stFT.contains(XBinary::FT_ZIP) || "
        "stFT.contains(XBinary::FT_7Z) || "
        "stFT.contains(XBinary::FT_RAR) || "
        "stFT.contains(XBinary::FT_CAB)"
    ),
    "sevenzip": "bool XSevenZip::initUnpack(",
    "sevenzip_methods": (
        "HANDLE_METHOD_STORE, HANDLE_METHOD_LZMA, "
        "HANDLE_METHOD_LZMA2, HANDLE_METHOD_PPMD7, "
        "HANDLE_METHOD_BZIP2, HANDLE_METHOD_DEFLATE, "
        "HANDLE_METHOD_DEFLATE64"
    ),
    "sevenzip_filters": (
        "HANDLE_METHOD_BCJ,\n"
        "        HANDLE_METHOD_ARM64_BCJ"
    ),
    "decompress_dispatch": (
        "compressMethod == XBinary::HANDLE_METHOD_DEFLATE64"
    ),
    "deflate_decoder": "bool XDeflateDecoder::decompress64(",
    "bcj2_dispatch": (
        "compressMethod == XBinary::HANDLE_METHOD_BCJ2"
    ),
    "bcj2_decoder": "bool XBCJ2Decoder::decompress(",
    "sevenzip_bcj2_graph": (
        "listResult.append(createPMInfo(HANDLE_METHOD_BCJ2));"
    ),
    "rar": "bool XRar::initUnpack(",
    "cab": "bool XCab::initUnpack(",
    "cab_lzx_method": (
        "result.mapProperties.insert(FPART_PROP_HANDLEMETHOD, "
        "HANDLE_METHOD_LZX_CAB);"
    ),
    "cab_unknown_method": (
        "result.mapProperties.insert(FPART_PROP_HANDLEMETHOD, "
        "HANDLE_METHOD_UNKNOWN);"
    ),
    "cab_decompress_dispatch": (
        "} else if ((compressMethod == "
        "XBinary::HANDLE_METHOD_STORE_CAB) || "
        "(compressMethod == XBinary::HANDLE_METHOD_MSZIP_CAB)) {"
    ),
    "iso9660": "bool XISO9660::initUnpack(",
}
EXPECTED_ROOTS = {
    "pdf-member.7z": {
        "filetype": "Binary",
        "root_names": ["7-Zip"],
    },
    "pdf-member-lzma.7z": {
        "filetype": "Binary",
        "root_names": ["7-Zip"],
    },
    "pdf-member-lzma2.7z": {
        "filetype": "Binary",
        "root_names": ["7-Zip"],
    },
    "pdf-member-ppmd7.7z": {
        "filetype": "Binary",
        "root_names": ["7-Zip"],
    },
    "pdf-member-bzip2.7z": {
        "filetype": "Binary",
        "root_names": ["7-Zip"],
    },
    "pdf-member-deflate.7z": {
        "filetype": "Binary",
        "root_names": ["7-Zip"],
    },
    "pdf-member-deflate64.7z": {
        "filetype": "Binary",
        "root_names": ["7-Zip"],
        "stream_size": "32772",
    },
    "pdf-member-bcj-lzma2.7z": {
        "filetype": "Binary",
        "root_names": ["7-Zip"],
    },
    "pdf-member-bcj2-lzma2.7z": {
        "filetype": "Binary",
        "root_names": ["7-Zip"],
    },
    "pdf-member-bcj2-e8-lzma2.7z": {
        "filetype": "Binary",
        "root_names": ["7-Zip"],
        "stream_size": "336",
    },
    "pdf-member-bcj2-e9-lzma2.7z": {
        "filetype": "Binary",
        "root_names": ["7-Zip"],
        "stream_size": "336",
    },
    "pdf-member-bcj2-jcc-lzma2.7z": {
        "filetype": "Binary",
        "root_names": ["7-Zip"],
        "stream_size": "337",
    },
    "pdf-member-arm64-bcj-lzma2.7z": {
        "filetype": "Binary",
        "root_names": ["7-Zip"],
        "stream_size": "4100",
    },
    "pdf-member.rar": {
        "filetype": "RAR",
        "root_names": ["Unknown"],
    },
    "pdf-member.cab": {
        "filetype": "Binary",
        "root_names": ["CAB"],
    },
    "pdf-member-mszip.cab": {
        "filetype": "Binary",
        "root_names": ["CAB"],
    },
    "pdf-member-lzx.cab": {
        "filetype": "Binary",
        "root_names": ["CAB"],
        "archive_stream_count": 0,
        "aggressive_stream": {
            "filetypes": ["Binary"],
            "detection_names": ["Unknown"],
            "sizes": ["331"],
        },
    },
    "text-member-quantum.cab": {
        "filetype": "Binary",
        "root_names": ["CAB"],
        "archive_stream_count": 0,
        "aggressive_stream": {
            "filetypes": ["Binary"],
            "detection_names": ["Unknown"],
            "sizes": ["59"],
        },
    },
    "pdf-member.iso": {
        "filetype": "ISO 9660",
        "root_names": ["Unknown"],
    },
}


class ProbeError(ValueError):
    """The archive-format fixture, oracle, or report is invalid."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def reject_duplicate_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProbeError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_json(data: bytes) -> Any:
    return json.loads(
        data.decode("utf-8"),
        object_pairs_hook=reject_duplicate_keys,
        parse_constant=lambda value: (_ for _ in ()).throw(
            ProbeError(f"non-finite JSON constant: {value}")
        ),
    )


def load_fixture(
    fixture_dir: pathlib.Path,
    manifest_path: pathlib.Path,
) -> tuple[dict[str, Any], str]:
    manifest_bytes = manifest_path.read_bytes()
    manifest = strict_json(manifest_bytes)
    if not isinstance(manifest, dict) or set(manifest) != {
        "schema_version",
        "generator",
        "generator_dependencies",
        "license",
        "samples",
        "third_party_inputs",
    }:
        raise ProbeError("fixture manifest fields changed")
    if manifest["schema_version"] != 2:
        raise ProbeError("unsupported fixture schema")
    if manifest["generator"] != FIXTURE_GENERATOR:
        raise ProbeError("unexpected fixture generator")
    if manifest["generator_dependencies"] != {
        "inflate64": {
            "license": "LGPL-2.1-or-later",
            "version": "1.0.4",
        },
        "pyppmd": {
            "license": "LGPL-2.1-or-later",
            "version": "1.3.1",
        }
    }:
        raise ProbeError("unexpected fixture generator dependencies")
    if manifest["license"] != (
        "project-generated except the attributed CAB Quantum "
        "compressed stream"
    ):
        raise ProbeError("unexpected fixture license declaration")
    if manifest["third_party_inputs"] != {
        "cab_quantum_stream": {
            "commit": "55d501976171397ccd5d5a7a1ca7da065b1d9a06",
            "license": "LGPL-2.1-only",
            "path": (
                "libmspack/test/test_files/cabd/"
                "mszip_lzx_qtm.cab"
            ),
            "repository": "https://github.com/kyz/libmspack",
            "source_sha256": (
                "0ce0b55fe705b744d41bb361170c0467"
                "db30da0c7f9bdd386d5dade71a78e171"
            ),
            "source_size": 379,
            "stream_offset": 331,
            "stream_sha256": (
                "6131acbaf1867209d537751a567e4c0a"
                "72756e7731a166395433c65d1543c04d"
            ),
            "stream_size": 48,
        }
    }:
        raise ProbeError("unexpected third-party fixture input")
    if len(manifest["samples"]) != 19:
        raise ProbeError("fixture sample count changed")

    declared = set()
    for sample in manifest["samples"]:
        if set(sample) != {
            "archive_format",
            "compression_method",
            "expected_member_name",
            "expected_payload_sha256",
            "name",
            "purpose",
            "sha256",
            "size",
        }:
            raise ProbeError("fixture sample fields changed")
        name = sample["name"]
        if pathlib.PurePosixPath(name).name != name or name in declared:
            raise ProbeError(f"unsafe or duplicate fixture name: {name}")
        path = fixture_dir / name
        if path.is_symlink() or not path.is_file():
            raise ProbeError(f"fixture file missing or symlinked: {name}")
        data = path.read_bytes()
        if len(data) != sample["size"] or sha256(data) != sample["sha256"]:
            raise ProbeError(f"fixture identity mismatch: {name}")
        declared.add(name)
    actual = {
        path.name
        for path in fixture_dir.iterdir()
        if path.is_file() and path.name != "manifest.json"
    }
    if actual != declared:
        raise ProbeError("fixture file inventory mismatch")
    return manifest, sha256(manifest_bytes)


def inspect_image() -> dict[str, Any]:
    process = subprocess.run(
        ["docker", "image", "inspect", IMAGE],
        check=True,
        capture_output=True,
    )
    documents = strict_json(process.stdout)
    if not isinstance(documents, list) or len(documents) != 1:
        raise ProbeError("unexpected image inspection shape")
    document = documents[0]
    revision = document["Config"]["Labels"].get(
        "org.opencontainers.image.revision",
        "",
    )
    if revision != UPSTREAM_COMMIT:
        raise ProbeError("archive harness revision changed")
    return {
        "id": document["Id"],
        "revision": revision,
        "repo_digests": sorted(document.get("RepoDigests") or []),
    }


def read_container_files(paths: tuple[str, ...]) -> dict[str, bytes]:
    script = (
        "import base64,json,pathlib;"
        f"paths={paths!r};"
        "print(json.dumps({p:base64.b64encode("
        "pathlib.Path(p).read_bytes()).decode('ascii') for p in paths},"
        "sort_keys=True))"
    )
    process = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            IMAGE,
            "python3",
            "-c",
            script,
        ],
        check=True,
        capture_output=True,
    )
    encoded = strict_json(process.stdout)
    if set(encoded) != set(paths):
        raise ProbeError("container file inventory changed")
    return {
        path: base64.b64decode(value, validate=True)
        for path, value in encoded.items()
    }


def source_contract(files: dict[str, bytes]) -> dict[str, Any]:
    result = {}
    for name, path in SOURCE_PATHS.items():
        data = files[path]
        text = data.decode("utf-8")
        count = text.count(SOURCE_PATTERNS[name])
        if count < 1:
            raise ProbeError(f"source pattern missing: {name}")
        result[name] = {
            "path": path,
            "sha256": sha256(data),
            "required_pattern": SOURCE_PATTERNS[name],
            "required_pattern_count": count,
        }
    return result


def run_binary(
    *,
    binary: str,
    fixture_dir: pathlib.Path,
    arguments: tuple[str, ...],
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--cpus",
            "1",
            "--memory",
            "512m",
            "--pids-limit",
            "128",
            "--read-only",
            "--mount",
            f"type=bind,src={fixture_dir},dst=/fixture,readonly",
            IMAGE,
            binary,
            *arguments,
        ],
        capture_output=True,
        timeout=60,
        check=False,
    )


def walk_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_dicts(child)


def summarize(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict) or set(document) != {"detects"}:
        raise ProbeError("unexpected scan JSON root")
    detects = document["detects"]
    if not isinstance(detects, list) or len(detects) != 1:
        raise ProbeError("expected exactly one root detection")
    root = detects[0]
    streams = [
        item
        for item in walk_dicts(root)
        if item.get("parentfilepart") == "Stream"
    ]
    root_names = [
        value["name"]
        for value in root.get("values", [])
        if isinstance(value, dict) and "parentfilepart" not in value
    ]
    stream_names = [
        value["name"]
        for stream in streams
        for value in stream.get("values", [])
        if isinstance(value, dict) and "parentfilepart" not in value
    ]
    return {
        "root_filetype": root.get("filetype"),
        "root_detection_names": root_names,
        "stream_count": len(streams),
        "stream_filetypes": [
            stream.get("filetype") for stream in streams
        ],
        "stream_detection_names": stream_names,
        "stream_sizes": [stream.get("size") for stream in streams],
    }


def raw_ref(
    data: bytes,
    artifacts: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    digest = sha256(data)
    compressed = zlib.compress(data, 9)
    artifact = {
        "bytes": len(data),
        "encoding": "zlib+base64",
        "compressed_bytes": len(compressed),
        "base64": base64.b64encode(compressed).decode("ascii"),
    }
    previous = artifacts.setdefault(digest, artifact)
    if previous != artifact:
        raise ProbeError("raw artifact digest collision")
    return {
        "artifact_sha256": digest,
        "bytes": len(data),
        "sha256": digest,
    }


def validate_case(
    sample_name: str,
    mode: str,
    summary: dict[str, Any],
) -> None:
    expected = EXPECTED_ROOTS[sample_name]
    if summary["root_filetype"] != expected["filetype"]:
        raise ProbeError(f"root filetype changed: {sample_name}/{mode}")
    if summary["root_detection_names"] != expected["root_names"]:
        raise ProbeError(f"root detections changed: {sample_name}/{mode}")
    aggressive_stream = expected.get("aggressive_stream")
    if mode == "archive_aggressive" and aggressive_stream:
        expected_stream_count = 1
    else:
        expected_stream_count = (
            0
            if mode == "default"
            else expected.get("archive_stream_count", 1)
        )
    if summary["stream_count"] != expected_stream_count:
        raise ProbeError(f"member count changed: {sample_name}/{mode}")
    if expected_stream_count == 0:
        if (
            summary["stream_filetypes"]
            or summary["stream_detection_names"]
            or summary["stream_sizes"]
        ):
            raise ProbeError(f"unexpected member data: {sample_name}/{mode}")
    elif mode == "archive_aggressive" and aggressive_stream:
        if summary["stream_filetypes"] != aggressive_stream["filetypes"]:
            raise ProbeError(f"member filetype changed: {sample_name}/{mode}")
        if (
            summary["stream_detection_names"]
            != aggressive_stream["detection_names"]
        ):
            raise ProbeError(f"member detections changed: {sample_name}/{mode}")
        if summary["stream_sizes"] != aggressive_stream["sizes"]:
            raise ProbeError(f"member size changed: {sample_name}/{mode}")
    else:
        if summary["stream_count"] != 1:
            raise ProbeError(f"member count changed: {sample_name}/{mode}")
        if summary["stream_filetypes"] != ["PDF"]:
            raise ProbeError(f"member filetype changed: {sample_name}/{mode}")
        if summary["stream_detection_names"] != [
            "PDF",
            "HeaderComment",
        ]:
            raise ProbeError(f"member detections changed: {sample_name}/{mode}")
        if summary["stream_sizes"] != [
            expected.get("stream_size", "331")
        ]:
            raise ProbeError(f"member size changed: {sample_name}/{mode}")


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
    container_files = read_container_files(container_paths)
    artifacts: dict[str, dict[str, Any]] = {}
    cases: dict[str, Any] = {}

    for sample in manifest["samples"]:
        sample_name = sample["name"]
        sample_cases: dict[str, Any] = {}
        raw_modes: dict[str, tuple[bytes, bytes]] = {}
        for mode, flags in (
            ("default", ()),
            ("archive", ("--archive",)),
            ("archive_aggressive", ("--archive", "--aggressive")),
        ):
            arguments = (*flags, f"/fixture/{sample_name}")
            process = run_binary(
                binary=HARNESS_BINARY,
                fixture_dir=fixture_dir,
                arguments=arguments,
            )
            if process.returncode != 0 or process.stderr:
                raise ProbeError(
                    f"harness failed: {sample_name}/{mode}"
                )
            summary = summarize(strict_json(process.stdout))
            validate_case(sample_name, mode, summary)
            raw_modes[mode] = (process.stdout, process.stderr)
            sample_cases[mode] = {
                "arguments": list(arguments),
                "exit_code": process.returncode,
                "stdout": raw_ref(process.stdout, artifacts),
                "stderr": raw_ref(process.stderr, artifacts),
                "summary": summary,
            }

        if sample_name in {
            "pdf-member-lzx.cab",
            "text-member-quantum.cab",
        }:
            if raw_modes["archive"] == raw_modes["archive_aggressive"]:
                raise ProbeError(
                    f"CAB aggressive fallback disappeared: {sample_name}"
                )
        elif raw_modes["archive"] != raw_modes["archive_aggressive"]:
            raise ProbeError(
                f"aggressive changed single-member output: {sample_name}"
            )
        release_arguments = (
            "--json",
            *DATABASE_ARGS,
            f"/fixture/{sample_name}",
        )
        release = run_binary(
            binary=RELEASE_BINARY,
            fixture_dir=fixture_dir,
            arguments=release_arguments,
        )
        if release.returncode != 0 or release.stderr:
            raise ProbeError(f"release failed: {sample_name}")
        if (release.stdout, release.stderr) != raw_modes["default"]:
            raise ProbeError(f"harness default drift: {sample_name}")
        sample_cases["release_default"] = {
            "arguments": list(release_arguments),
            "exit_code": release.returncode,
            "stdout": raw_ref(release.stdout, artifacts),
            "stderr": raw_ref(release.stderr, artifacts),
            "summary": summarize(strict_json(release.stdout)),
        }
        cases[sample_name] = sample_cases

    facts = {
        "release_and_harness_default_outputs_are_equal": True,
        "archive_option_is_required_for_unpacking": True,
        "sevenzip_copy_member_reaches_pdf_rules": True,
        "sevenzip_lzma_member_reaches_pdf_rules": True,
        "sevenzip_lzma2_member_reaches_pdf_rules": True,
        "sevenzip_ppmd7_member_reaches_pdf_rules": True,
        "sevenzip_bzip2_member_reaches_pdf_rules": True,
        "sevenzip_deflate_member_reaches_pdf_rules": True,
        "sevenzip_deflate64_distance_32769_member_reaches_pdf_rules": True,
        "sevenzip_bcj_lzma2_member_reaches_pdf_rules": True,
        "sevenzip_bcj2_lzma2_control_reaches_pdf_rules": True,
        "sevenzip_bcj2_e8_lzma2_member_reaches_pdf_rules": True,
        "sevenzip_bcj2_e9_lzma2_member_reaches_pdf_rules": True,
        "sevenzip_bcj2_jcc_lzma2_member_reaches_pdf_rules": True,
        "sevenzip_arm64_bcj_lzma2_bl_and_adrp_reach_pdf_rules": True,
        "rar4_store_member_reaches_pdf_rules": True,
        "cab_store_member_reaches_pdf_rules": True,
        "cab_mszip_member_reaches_pdf_rules": True,
        "cab_lzx_archive_has_no_child_but_aggressive_scans_unknown_output": True,
        "cab_quantum_archive_has_no_child_but_aggressive_scans_unknown_output": True,
        "iso9660_store_member_reaches_pdf_rules": True,
        "cab_root_dispatches_as_binary_while_archive_adapter_runs": True,
        "sevenzip_root_dispatches_as_binary_while_archive_adapter_runs": True,
        "aggressive_does_not_change_supported_single_member_results": True,
    }
    root = pathlib.Path(__file__).resolve().parents[2]
    return {
        "schema_version": 1,
        "generator": "tools/upstream/probe_archive_format_harness.py",
        "generator_sha256": sha256(pathlib.Path(__file__).read_bytes()),
        "upstream_commit": UPSTREAM_COMMIT,
        "platform": "linux-x86_64-qt5",
        "image": {
            **inspect_image(),
            "name": IMAGE,
        },
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
        "local_sources": {
            "fixture_generator": {
                "path": FIXTURE_GENERATOR,
                "sha256": sha256((root / FIXTURE_GENERATOR).read_bytes()),
            },
            "fixture_requirements": {
                "path": FIXTURE_REQUIREMENTS,
                "sha256": sha256(
                    (root / FIXTURE_REQUIREMENTS).read_bytes()
                ),
            },
            "harness_source": {
                "path": HARNESS_SOURCE,
                "sha256": sha256((root / HARNESS_SOURCE).read_bytes()),
            },
            "harness_dockerfile": {
                "path": HARNESS_DOCKERFILE,
                "sha256": sha256((root / HARNESS_DOCKERFILE).read_bytes()),
            },
            "baseline_generator": {
                "path": "tools/corpus/generate_baseline_corpus.py",
                "sha256": sha256(
                    (
                        root
                        / "tools"
                        / "corpus"
                        / "generate_baseline_corpus.py"
                    ).read_bytes()
                ),
            },
        },
        "source_contract": source_contract(container_files),
        "fixture_manifest": {
            "path": "docs/research/data/archive-format-corpus.json",
            "sha256": manifest_sha256,
            "sample_count": len(manifest["samples"]),
        },
        "resource_limits": {
            "network": "none",
            "cpus": 1,
            "memory_bytes": 512 * 1024 * 1024,
            "pids": 128,
            "timeout_seconds_per_execution": 60,
            "fixture_mount": "read-only",
            "container_root": "read-only",
        },
        "cases": cases,
        "raw_artifacts": artifacts,
        "facts": facts,
        "passed": all(facts.values()),
        "failures": [],
        "remaining_gap": "CAP-GAP-006",
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
            / "archive-format-corpus.json"
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
