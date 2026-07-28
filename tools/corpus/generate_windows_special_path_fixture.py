#!/usr/bin/env python3
"""Generate deterministic special-path fixtures on native Windows."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import sys


SCHEMA_VERSION = 1
GENERATOR = "tools/corpus/generate_windows_special_path_fixture.py"
SOURCE_NAME = "minimal.pdf"
FILE_ATTRIBUTE_HIDDEN = 0x2
INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF
DIRECTORIES = ("special", "目录 空格")
ENTRIES = (
    ("ascii", "special/00-ascii.pdf", False),
    ("upper_case", "special/A-case.pdf", False),
    ("nfc", "special/é-nfc.pdf", False),
    ("nfd", "special/e\u0301-nfd.pdf", False),
    ("cjk", "special/中文.pdf", False),
    ("emoji", "special/emoji-😀.pdf", False),
    ("space", "special/space name.pdf", False),
    ("leading_space", "special/ leading-space.pdf", False),
    ("leading_dash", "special/--leading-dash.pdf", False),
    ("dot_hidden", "special/.dot-hidden.pdf", False),
    ("attribute_hidden", "special/attribute-hidden.pdf", True),
    ("unicode_child", "目录 空格/子 文件.pdf", False),
)
UNREPRESENTABLE_CONTROLS = (
    {
        "linux_path": "paths/special/trailing-space.pdf ",
        "reason": "Win32 path parsing trims trailing spaces by default",
    },
    {
        "linux_path": "paths/special/colon:name.pdf",
        "reason": "colon selects an NTFS alternate data stream",
    },
    {
        "linux_path": "paths/special/backslash\\name.pdf",
        "reason": "backslash is the native directory separator",
    },
    {
        "linux_path": "paths/special/<TAB and LF names>",
        "reason": "Win32 rejects control characters U+0001 through U+001F",
    },
    {
        "linux_path": "paths/nonutf8/<three raw byte names>",
        "reason": "Windows path identity is UTF-16, not an arbitrary byte string",
    },
    {
        "linux_path": "paths/special/A-case.pdf + a-case.pdf",
        "reason": (
            "both names alias on the default case-insensitive fixture directory"
        ),
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
        sample
        for sample in samples
        if isinstance(sample, dict) and sample.get("name") == SOURCE_NAME
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


def set_hidden(path: Path) -> None:
    attributes = get_file_attributes(path)
    if not ctypes.windll.kernel32.SetFileAttributesW(
        str(path),
        attributes | FILE_ATTRIBUTE_HIDDEN,
    ):
        raise OSError(ctypes.get_last_error(), f"SetFileAttributesW: {path}")


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


def validate_fixture(root: Path, manifest: dict[str, object]) -> None:
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported Windows special-path fixture schema")
    if manifest.get("generator") != GENERATOR:
        raise ValueError("unexpected Windows special-path fixture generator")
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise ValueError("fixture manifest has no entries")

    declared_files = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("invalid fixture entry")
        relative = entry.get("path")
        if not isinstance(relative, str) or "\\" in relative:
            raise ValueError("unsafe fixture path")
        path = root.joinpath(*relative.split("/"))
        data = path.read_bytes()
        if (
            len(data) != entry.get("size")
            or sha256(data) != entry.get("sha256")
        ):
            raise ValueError(f"fixture entry mismatch: {relative!r}")
        is_hidden = bool(get_file_attributes(path) & FILE_ATTRIBUTE_HIDDEN)
        if is_hidden != entry.get("hidden_attribute"):
            raise ValueError(f"hidden attribute mismatch: {relative!r}")
        declared_files.add(relative)

    actual_files = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    actual_directories = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_dir()
    }
    if actual_files != declared_files:
        raise ValueError("fixture contains undeclared or missing files")
    if actual_directories != set(DIRECTORIES):
        raise ValueError("fixture contains undeclared or missing directories")


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
    for directory in DIRECTORIES:
        output_dir.joinpath(*directory.split("/")).mkdir(parents=True)

    entries = []
    for case_id, relative, hidden in ENTRIES:
        path = output_dir.joinpath(*relative.split("/"))
        path.write_bytes(payload)
        if hidden:
            set_hidden(path)
        entries.append(
            {
                "id": case_id,
                "path": relative,
                "hidden_attribute": hidden,
                "size": len(payload),
                "sha256": sha256(payload),
            }
        )

    special = output_dir / "special"
    nfc = special / "é-nfc.pdf"
    nfd = special / "e\u0301-nfd.pdf"
    if os.path.samefile(nfc, nfd):
        raise ValueError("fixture filesystem aliases NFC and NFD")
    case_alias_exists = (special / "a-case.pdf").exists()
    if not case_alias_exists:
        raise ValueError("fixture directory is not default case-insensitive")

    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "generator": GENERATOR,
        "license": "project-generated paths; baseline corpus bytes only",
        "payload": {
            "source": SOURCE_NAME,
            "size": len(payload),
            "sha256": sha256(payload),
        },
        "directories": list(DIRECTORIES),
        "entries": entries,
        "filesystem_observations": {
            "nfc_nfd_distinct": True,
            "lowercase_case_alias_exists": case_alias_exists,
            "dot_file_has_hidden_attribute": False,
            "attribute_hidden_has_hidden_attribute": True,
        },
        "unrepresentable_linux_controls": list(
            UNREPRESENTABLE_CONTROLS
        ),
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
