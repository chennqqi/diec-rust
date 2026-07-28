#!/usr/bin/env python3
"""Generate deterministic junction fixtures on native Windows."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


SCHEMA_VERSION = 1
GENERATOR = "tools/corpus/generate_windows_filesystem_fixture.py"
SOURCE_NAME = "minimal.pdf"
FILE_ATTRIBUTE_REPARSE_POINT = 0x400
INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF
FILES = (
    ("single", "single/target.pdf"),
    ("direct_child", "direct-target/child.pdf"),
    ("chain_child", "chain-target/child.pdf"),
    ("tree_child", "tree/real/child.pdf"),
)
JUNCTIONS = (
    ("direct_alias", "direct-alias", "direct-target"),
    ("chain_hop", "chain-hop", "chain-target"),
    ("chain_entry", "chain-entry", "chain-hop"),
    ("tree_alias", "tree/alias", "tree/real"),
)
EXPLICIT_GAPS = (
    {
        "id": "file_symlink",
        "reason": (
            "ordinary-user creation failed with the Windows privilege-required "
            "error; Developer Mode or elevation was not assumed"
        ),
    },
    {
        "id": "directory_symlink",
        "reason": (
            "ordinary-user creation failed with the Windows privilege-required "
            "error; the junction cases remain separately observable"
        ),
    },
    {
        "id": "dangling_reparse_point",
        "reason": (
            "the safe fixture uses directory junctions whose targets exist"
        ),
    },
    {
        "id": "reparse_cycle",
        "reason": (
            "an unbounded junction cycle is excluded from the routine oracle "
            "and remains a resource-limit test"
        ),
    },
    {
        "id": "acl_denial",
        "reason": "no disposable alternate security principal was available",
    },
    {
        "id": "unc_path",
        "reason": "no controlled network share was available",
    },
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_payload(baseline_dir: Path) -> bytes:
    manifest = json.loads(
        (baseline_dir / "manifest.json").read_text(encoding="utf-8")
    )
    samples = manifest.get("samples")
    if manifest.get("schema_version") != 1 or not isinstance(samples, list):
        raise ValueError("unsupported baseline corpus manifest")
    matches = [
        item
        for item in samples
        if isinstance(item, dict) and item.get("name") == SOURCE_NAME
    ]
    if len(matches) != 1:
        raise ValueError(f"baseline must contain one {SOURCE_NAME}")
    payload = (baseline_dir / SOURCE_NAME).read_bytes()
    if (
        len(payload) != matches[0].get("size")
        or sha256(payload) != matches[0].get("sha256")
    ):
        raise ValueError("baseline payload identity mismatch")
    return payload


def get_file_attributes(path: Path) -> int:
    if os.name != "nt":
        raise ValueError("Windows file attributes require os.name == 'nt'")
    value = ctypes.windll.kernel32.GetFileAttributesW(str(path))
    if value == INVALID_FILE_ATTRIBUTES:
        raise OSError(ctypes.get_last_error(), f"GetFileAttributesW: {path}")
    return int(value)


def is_reparse_point(path: Path) -> bool:
    return bool(get_file_attributes(path) & FILE_ATTRIBUTE_REPARSE_POINT)


def create_junction(link: Path, target: Path) -> None:
    result = subprocess.run(
        [
            "cmd.exe",
            "/d",
            "/c",
            "mklink",
            "/J",
            str(link),
            str(target),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise ValueError(
            f"cannot create junction {link}: "
            f"{result.stdout.strip()} {result.stderr.strip()}".strip()
        )
    if not link.is_dir() or not is_reparse_point(link):
        raise ValueError(f"junction was not materialized: {link}")


def serialize_manifest(manifest: dict[str, object]) -> bytes:
    return (
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def fixture_path(root: Path, relative: str) -> Path:
    if (
        not relative
        or "\\" in relative
        or relative.startswith("/")
        or ".." in relative.split("/")
    ):
        raise ValueError(f"unsafe fixture path: {relative!r}")
    return root.joinpath(*relative.split("/"))


def validate_fixture(root: Path, manifest: dict[str, object]) -> None:
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported Windows filesystem fixture schema")
    if manifest.get("generator") != GENERATOR:
        raise ValueError("unexpected Windows filesystem fixture generator")
    entries = manifest.get("files")
    junctions = manifest.get("junctions")
    if not isinstance(entries, list) or not isinstance(junctions, list):
        raise ValueError("fixture manifest entries are invalid")

    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("invalid file entry")
        path = fixture_path(root, str(entry.get("path", "")))
        data = path.read_bytes()
        if (
            len(data) != entry.get("size")
            or sha256(data) != entry.get("sha256")
            or is_reparse_point(path)
        ):
            raise ValueError(f"fixture file mismatch: {entry.get('path')!r}")

    for junction in junctions:
        if not isinstance(junction, dict):
            raise ValueError("invalid junction entry")
        link = fixture_path(root, str(junction.get("path", "")))
        target = fixture_path(root, str(junction.get("target", "")))
        if not link.is_dir() or not target.is_dir() or not is_reparse_point(link):
            raise ValueError(f"junction mismatch: {junction.get('path')!r}")
        probe = str(junction.get("probe", ""))
        if not probe or fixture_path(link, probe).read_bytes() == b"":
            raise ValueError(f"junction target is not readable: {link}")


def generate(
    baseline_dir: Path,
    output_dir: Path,
    manifest_output: Path | None,
) -> dict[str, object]:
    if os.name != "nt":
        raise ValueError("native Windows fixture requires os.name == 'nt'")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("output directory must be absent or empty")
    payload = load_payload(baseline_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    files = []
    for case_id, relative in FILES:
        path = fixture_path(output_dir, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        files.append(
            {
                "id": case_id,
                "path": relative,
                "size": len(payload),
                "sha256": sha256(payload),
            }
        )

    junctions = []
    probe_by_target = {
        "direct-target": "child.pdf",
        "chain-target": "child.pdf",
        "chain-hop": "child.pdf",
        "tree/real": "child.pdf",
    }
    for case_id, relative, target_relative in JUNCTIONS:
        link = fixture_path(output_dir, relative)
        target = fixture_path(output_dir, target_relative)
        create_junction(link, target)
        junctions.append(
            {
                "id": case_id,
                "path": relative,
                "target": target_relative,
                "probe": probe_by_target[target_relative],
                "reparse_point": True,
            }
        )

    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "generator": GENERATOR,
        "license": "project-generated paths; baseline corpus bytes only",
        "payload": {
            "source": SOURCE_NAME,
            "size": len(payload),
            "sha256": sha256(payload),
        },
        "files": files,
        "junctions": junctions,
        "extended_path_cases": [
            "single/target.pdf",
            "direct-alias",
        ],
        "explicit_gaps": list(EXPLICIT_GAPS),
    }
    serialized = serialize_manifest(manifest)
    (output_dir / "manifest.json").write_bytes(serialized)
    if manifest_output is not None:
        manifest_output.parent.mkdir(parents=True, exist_ok=True)
        manifest_output.write_bytes(serialized)
    validate_fixture(output_dir, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--manifest-output", type=Path)
    args = parser.parse_args()
    manifest = generate(
        args.baseline_dir.resolve(strict=True),
        args.output_dir.resolve(),
        (
            args.manifest_output.resolve()
            if args.manifest_output is not None
            else None
        ),
    )
    json.dump(manifest, sys.stdout, ensure_ascii=True, indent=2, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
