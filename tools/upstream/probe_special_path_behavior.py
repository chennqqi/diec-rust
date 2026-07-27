#!/usr/bin/env python3
"""Probe pinned Linux Qt5 CLI behavior for Unicode and special paths."""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
import hashlib
import json
import pathlib
import subprocess
import time
from typing import Any
import zlib


UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
FIXTURE_GENERATOR = "tools/corpus/generate_special_path_fixture.py"
FIXTURE_MANIFEST = "docs/research/data/special-path-fixture.json"
ARCHIVE_NAME = "special-path-fixture.tar"
DATABASE_ARGS = (
    "--database",
    "/opt/die-source/Detect-It-Easy/db",
    "--extradatabase",
    "/opt/die-source/Detect-It-Easy/db_extra",
    "--customdatabase",
    "/opt/die-source/Detect-It-Easy/db_custom",
)
ORACLES = {
    "qmake": {
        "image": "diec-rust/upstream-oracle:74eaf505-repro",
        "binary": "/opt/die-source/build/release/diec",
    },
    "cmake": {
        "image": "diec-rust/upstream-oracle-cmake:74eaf505",
        "binary": "/opt/die-build/src/console/diec",
    },
}
SOURCE_PATHS = {
    "console": "/opt/die-source/src/console/main_console.cpp",
    "formats": "/opt/die-source/Formats/xbinary.cpp",
}
SOURCE_PATTERNS = {
    "console": (
        "QDir().toNativeSeparators(sFileName).toUtf8().data()",
    ),
    "formats": (
        "QFileInfoList eil = dir.entryInfoList();",
        "findFiles(eil.at(i).absoluteFilePath(), pListFileNames, pPdStruct);",
    ),
}
EXPECTED_DIRECTORY_ORDER = (
    "paths/special/ leading-space.pdf",
    "paths/special/--leading-dash.pdf",
    "paths/special/00-ascii.pdf",
    "paths/special/a-case.pdf",
    "paths/special/A-case.pdf",
    "paths/special/backslash\\name.pdf",
    "paths/special/colon:name.pdf",
    "paths/special/emoji-😀.pdf",
    "paths/special/e\u0301-nfd.pdf",
    "paths/special/line\nbreak.pdf",
    "paths/special/space name.pdf",
    "paths/special/tab\tname.pdf",
    "paths/special/trailing-space.pdf ",
    "paths/special/é-nfc.pdf",
    "paths/special/中文.pdf",
)


@dataclass(frozen=True)
class Case:
    name: str
    cwd: str
    arguments: tuple[str, ...]
    expected_exit: int = 0
    expect_json: bool = True


def scan_case(name: str, path: str) -> Case:
    return Case(name, "/work", ("--json", *DATABASE_ARGS, path))


CASES = (
    scan_case("single_nfc", "paths/special/é-nfc.pdf"),
    scan_case("single_nfd", "paths/special/e\u0301-nfd.pdf"),
    scan_case("single_cjk", "paths/special/中文.pdf"),
    scan_case("single_emoji", "paths/special/emoji-😀.pdf"),
    scan_case("single_space", "paths/special/space name.pdf"),
    scan_case("single_leading_space", "paths/special/ leading-space.pdf"),
    scan_case("single_trailing_space", "paths/special/trailing-space.pdf "),
    scan_case("single_tab", "paths/special/tab\tname.pdf"),
    scan_case("single_newline", "paths/special/line\nbreak.pdf"),
    scan_case("single_colon", "paths/special/colon:name.pdf"),
    scan_case("single_backslash", "paths/special/backslash\\name.pdf"),
    scan_case("single_hidden", "paths/special/.hidden.pdf"),
    scan_case(
        "single_leading_dash_absolute",
        "/work/paths/special/--leading-dash.pdf",
    ),
    Case(
        "single_leading_dash_relative_unescaped",
        "/work/paths/special",
        ("--json", *DATABASE_ARGS, "--leading-dash.pdf"),
        expected_exit=1,
        expect_json=False,
    ),
    Case(
        "single_leading_dash_relative_escaped",
        "/work/paths/special",
        ("--json", *DATABASE_ARGS, "--", "--leading-dash.pdf"),
    ),
    Case(
        "directory_special",
        "/work",
        ("--json", *DATABASE_ARGS, "/work/paths/special"),
        expect_json=False,
    ),
    scan_case("directory_unicode", "/work/paths/目录 空格"),
    Case(
        "explicit_order",
        "/work",
        (
            "--json",
            *DATABASE_ARGS,
            "paths/special/emoji-😀.pdf",
            "paths/special/é-nfc.pdf",
            "paths/special/00-ascii.pdf",
        ),
        expect_json=False,
    ),
)


class ProbeError(ValueError):
    """The fixture, pinned oracle, or observed path behavior is invalid."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProbeError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_json(data: bytes) -> Any:
    try:
        return json.loads(
            data.decode("utf-8"),
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ProbeError(f"non-finite JSON constant: {value}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProbeError(f"invalid JSON: {error}") from error


def load_fixture(
    fixture_dir: pathlib.Path,
    manifest_path: pathlib.Path,
) -> tuple[dict[str, Any], bytes]:
    raw = manifest_path.read_bytes()
    manifest = strict_json(raw)
    expected_fields = {
        "archive",
        "directories",
        "files",
        "generator",
        "license",
        "payload",
        "schema_version",
    }
    if not isinstance(manifest, dict) or set(manifest) != expected_fields:
        raise ProbeError("fixture manifest fields changed")
    if manifest["schema_version"] != 1:
        raise ProbeError("unsupported fixture manifest schema")
    if manifest["generator"] != FIXTURE_GENERATOR:
        raise ProbeError("unexpected fixture generator")
    archive_record = manifest["archive"]
    if (
        not isinstance(archive_record, dict)
        or set(archive_record)
        != {"format", "name", "sha256", "size"}
        or archive_record["format"] != "ustar"
        or archive_record["name"] != ARCHIVE_NAME
    ):
        raise ProbeError("fixture archive identity changed")
    archive_path = fixture_dir / ARCHIVE_NAME
    if archive_path.is_symlink() or not archive_path.is_file():
        raise ProbeError("fixture archive is missing or symlinked")
    archive = archive_path.read_bytes()
    if (
        len(archive) != archive_record["size"]
        or sha256(archive) != archive_record["sha256"]
    ):
        raise ProbeError("fixture archive bytes changed")

    paths = [entry.get("path") for entry in manifest["files"]]
    if (
        len(paths) != 17
        or len(paths) != len(set(paths))
        or any(not isinstance(path, str) for path in paths)
    ):
        raise ProbeError("fixture path inventory changed")
    required = {
        "paths/special/é-nfc.pdf",
        "paths/special/e\u0301-nfd.pdf",
        "paths/special/中文.pdf",
        "paths/special/emoji-😀.pdf",
        "paths/special/tab\tname.pdf",
        "paths/special/line\nbreak.pdf",
        "paths/special/backslash\\name.pdf",
        "paths/special/.hidden.pdf",
    }
    if not required.issubset(set(paths)):
        raise ProbeError("fixture special-path matrix changed")
    return manifest, raw


def inspect_image(name: str, image: str) -> dict[str, Any]:
    process = subprocess.run(
        ["docker", "image", "inspect", image],
        check=True,
        capture_output=True,
    )
    documents = strict_json(process.stdout)
    if not isinstance(documents, list) or len(documents) != 1:
        raise ProbeError(f"unexpected image inspection shape: {name}")
    document = documents[0]
    revision = document["Config"]["Labels"].get(
        "org.opencontainers.image.revision",
        "",
    )
    if revision != UPSTREAM_COMMIT:
        raise ProbeError(f"oracle revision changed: {name}")
    return {
        "binary": ORACLES[name]["binary"],
        "id": document["Id"],
        "image": image,
        "repo_digests": sorted(document.get("RepoDigests") or []),
        "revision": revision,
    }


def read_container_files(
    image: str, paths: tuple[str, ...]
) -> dict[str, bytes]:
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
            image,
            "python3",
            "-c",
            script,
        ],
        check=True,
        capture_output=True,
    )
    encoded = strict_json(process.stdout)
    if not isinstance(encoded, dict) or set(encoded) != set(paths):
        raise ProbeError("container file inventory changed")
    return {
        path: base64.b64decode(value, validate=True)
        for path, value in encoded.items()
    }


def run_case(
    *,
    image: str,
    binary: str,
    archive_path: pathlib.Path,
    case: Case,
) -> tuple[subprocess.CompletedProcess[bytes], int]:
    script = (
        "tar -xf /fixture/special-path-fixture.tar -C /work"
        ' && cd "$1" && shift && binary="$1" && shift'
        ' && exec "$binary" "$@"'
    )
    command = [
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
        "--tmpfs",
        "/work:rw,noexec,nosuid,nodev,size=16m",
        "--mount",
        (
            f"type=bind,src={archive_path.parent},"
            "dst=/fixture,readonly"
        ),
        image,
        "sh",
        "-c",
        script,
        "sh",
        case.cwd,
        binary,
        *case.arguments,
    ]
    started = time.monotonic()
    process = subprocess.run(
        command,
        capture_output=True,
        timeout=60,
        check=False,
    )
    return process, round((time.monotonic() - started) * 1000)


def validate_pdf_document(data: bytes) -> None:
    document = strict_json(data)
    if not isinstance(document, dict) or set(document) != {"detects"}:
        raise ProbeError("unexpected scan JSON root")
    detects = document["detects"]
    if not isinstance(detects, list) or len(detects) != 1:
        raise ProbeError("expected one PDF root")
    root = detects[0]
    if root.get("filetype") != "PDF":
        raise ProbeError("special-path sample did not scan as PDF")
    values = root.get("values")
    names = [
        value.get("name")
        for value in values
        if isinstance(value, dict)
    ]
    if names != ["PDF", "HeaderComment"]:
        raise ProbeError("PDF detection list changed")


def path_order(stdout: bytes, candidates: list[str]) -> list[str]:
    located: list[tuple[int, str]] = []
    for path in candidates:
        marker = f"/work/{path}:\n".encode("utf-8")
        count = stdout.count(marker)
        if count > 1:
            raise ProbeError(f"duplicate filename prefix: {path!r}")
        if count == 1:
            located.append((stdout.index(marker), path))
    return [path for _, path in sorted(located)]


def raw_ref(
    data: bytes,
    artifacts: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    digest = sha256(data)
    compressed = zlib.compress(data, 9)
    artifact = {
        "base64": base64.b64encode(compressed).decode("ascii"),
        "bytes": len(data),
        "compressed_bytes": len(compressed),
        "encoding": "zlib+base64",
    }
    previous = artifacts.setdefault(digest, artifact)
    if previous != artifact:
        raise ProbeError("raw artifact digest collision")
    return {
        "artifact_sha256": digest,
        "bytes": len(data),
        "sha256": digest,
    }


def source_contract(files: dict[str, bytes]) -> dict[str, Any]:
    result = {}
    for name, path in SOURCE_PATHS.items():
        text = files[path].decode("utf-8")
        patterns = {}
        for pattern in SOURCE_PATTERNS[name]:
            count = text.count(pattern)
            if count < 1:
                raise ProbeError(f"source pattern missing: {name}")
            patterns[pattern] = count
        result[name] = {
            "path": path,
            "required_patterns": patterns,
            "sha256": sha256(files[path]),
        }
    return result


def build_report(
    fixture_dir: pathlib.Path,
    manifest_path: pathlib.Path,
) -> dict[str, Any]:
    manifest, manifest_raw = load_fixture(fixture_dir, manifest_path)
    archive_path = fixture_dir / ARCHIVE_NAME
    artifacts: dict[str, dict[str, Any]] = {}
    image_records = {
        name: inspect_image(name, oracle["image"])
        for name, oracle in ORACLES.items()
    }
    cmake_files = read_container_files(
        ORACLES["cmake"]["image"],
        (
            ORACLES["cmake"]["binary"],
            *SOURCE_PATHS.values(),
        ),
    )
    qmake_files = read_container_files(
        ORACLES["qmake"]["image"],
        (ORACLES["qmake"]["binary"],),
    )

    fixture_paths = [entry["path"] for entry in manifest["files"]]
    special_paths = [
        path for path in fixture_paths if path.startswith("paths/special/")
    ]
    non_hidden_special_paths = [
        path
        for path in special_paths
        if not pathlib.PurePosixPath(path).name.startswith(".")
    ]
    cases: dict[str, Any] = {}
    raw_by_case: dict[str, tuple[bytes, bytes, int]] = {}
    for case in CASES:
        observations = {}
        for oracle_name, oracle in ORACLES.items():
            process, elapsed_ms = run_case(
                image=oracle["image"],
                binary=oracle["binary"],
                archive_path=archive_path,
                case=case,
            )
            if process.returncode != case.expected_exit:
                raise ProbeError(
                    f"exit changed: {case.name}/{oracle_name}: "
                    f"{process.returncode}"
                )
            if (
                process.stderr
                and case.name
                != "single_leading_dash_relative_unescaped"
            ):
                raise ProbeError(
                    f"stderr changed: {case.name}/{oracle_name}"
                )
            if case.expect_json:
                validate_pdf_document(process.stdout)
            observations[oracle_name] = {
                "exit_code": process.returncode,
                "stderr": raw_ref(process.stderr, artifacts),
                "stdout": raw_ref(process.stdout, artifacts),
                "wall_elapsed_ms": elapsed_ms,
            }
            raw = (
                process.stdout,
                process.stderr,
                process.returncode,
            )
            previous = raw_by_case.setdefault(case.name, raw)
            if previous != raw:
                raise ProbeError(f"qmake/CMake drift: {case.name}")

        stdout = raw_by_case[case.name][0]
        order = path_order(stdout, fixture_paths)
        if case.name == "directory_special":
            if set(order) != set(non_hidden_special_paths):
                raise ProbeError(
                    "directory enumeration inventory changed"
                )
            if order != list(EXPECTED_DIRECTORY_ORDER):
                raise ProbeError("directory enumeration order changed")
        elif case.name == "directory_unicode":
            # The expanded file count is one, so the CLI deliberately omits
            # its filename prefix and emits one valid JSON document.
            if order:
                raise ProbeError("Unicode single-file directory gained prefix")
        elif case.name == "explicit_order":
            expected = [
                "paths/special/emoji-😀.pdf",
                "paths/special/é-nfc.pdf",
                "paths/special/00-ascii.pdf",
            ]
            if order != expected:
                raise ProbeError("explicit target order changed")
        elif order:
            raise ProbeError(
                f"single-target case gained filename prefix: {case.name}"
            )

        cases[case.name] = {
            "arguments": list(case.arguments),
            "cwd": case.cwd,
            "expected_exit": case.expected_exit,
            "expect_json": case.expect_json,
            "filename_prefix_order": order,
            "observations": observations,
        }

    unescaped_raw = raw_by_case[
        "single_leading_dash_relative_unescaped"
    ]
    if (
        b"Unknown option 'leading-dash.pdf'."
        not in unescaped_raw[0] + unescaped_raw[1]
    ):
        raise ProbeError("leading-dash option diagnostic changed")

    facts = {
        "all_utf8_single_file_paths_scan_as_pdf": True,
        "nfc_and_nfd_are_distinct_paths": True,
        "directory_enumeration_excludes_hidden_entries": True,
        "explicit_hidden_path_is_scannable": True,
        "directory_enumeration_order_is_recorded": True,
        "explicit_multiple_targets_preserve_argument_order": True,
        "absolute_leading_dash_path_is_scannable": True,
        "relative_leading_dash_requires_option_terminator": True,
        "qmake_and_cmake_outputs_are_byte_equal": True,
    }
    root = pathlib.Path(__file__).resolve().parents[2]
    return {
        "binaries": {
            "cmake": {
                "path": ORACLES["cmake"]["binary"],
                "sha256": sha256(
                    cmake_files[ORACLES["cmake"]["binary"]]
                ),
                "size": len(
                    cmake_files[ORACLES["cmake"]["binary"]]
                ),
            },
            "qmake": {
                "path": ORACLES["qmake"]["binary"],
                "sha256": sha256(
                    qmake_files[ORACLES["qmake"]["binary"]]
                ),
                "size": len(
                    qmake_files[ORACLES["qmake"]["binary"]]
                ),
            },
        },
        "cases": cases,
        "facts": facts,
        "failures": [],
        "fixture": {
            "archive_sha256": manifest["archive"]["sha256"],
            "archive_size": manifest["archive"]["size"],
            "file_count": len(fixture_paths),
            "manifest_path": FIXTURE_MANIFEST,
            "manifest_sha256": sha256(manifest_raw),
        },
        "generator": "tools/upstream/probe_special_path_behavior.py",
        "generator_sha256": sha256(pathlib.Path(__file__).read_bytes()),
        "images": image_records,
        "local_sources": {
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
            "fixture_generator": {
                "path": FIXTURE_GENERATOR,
                "sha256": sha256(
                    (root / FIXTURE_GENERATOR).read_bytes()
                ),
            },
        },
        "passed": all(facts.values()),
        "platform": "linux-x86_64-qt5",
        "raw_artifacts": artifacts,
        "remaining_gap": (
            "CAP-GAP-003: non-UTF-8, symlink/permission/depth, "
            "Windows, and macOS behavior"
        ),
        "resource_limits": {
            "container_root": "read-only",
            "cpus": 1,
            "fixture_mount": "read-only",
            "memory_bytes": 512 * 1024 * 1024,
            "network": "none",
            "pids": 128,
            "timeout_seconds_per_execution": 60,
            "work_tmpfs_bytes": 16 * 1024 * 1024,
        },
        "schema_version": 1,
        "source_contract": source_contract(cmake_files),
        "upstream_commit": UPSTREAM_COMMIT,
    }


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-dir", required=True, type=pathlib.Path)
    parser.add_argument(
        "--manifest",
        type=pathlib.Path,
        default=root / FIXTURE_MANIFEST,
    )
    parser.add_argument("--output", required=True, type=pathlib.Path)
    args = parser.parse_args()
    report = build_report(
        args.fixture_dir.resolve(),
        args.manifest.resolve(),
    )
    args.output.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
