#!/usr/bin/env python3
"""Build a deterministic USTAR fixture for Linux special-path experiments."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys


SCHEMA_VERSION = 1
GENERATOR = "tools/corpus/generate_special_path_fixture.py"
ARCHIVE_NAME = "special-path-fixture.tar"
SOURCE_NAME = "minimal.pdf"

DIRECTORIES = (
    "paths/",
    "paths/special/",
    "paths/目录 空格/",
)

FILES = (
    "paths/special/00-ascii.pdf",
    "paths/special/A-case.pdf",
    "paths/special/a-case.pdf",
    "paths/special/é-nfc.pdf",
    "paths/special/e\u0301-nfd.pdf",
    "paths/special/中文.pdf",
    "paths/special/emoji-😀.pdf",
    "paths/special/space name.pdf",
    "paths/special/ leading-space.pdf",
    "paths/special/trailing-space.pdf ",
    "paths/special/tab\tname.pdf",
    "paths/special/line\nbreak.pdf",
    "paths/special/colon:name.pdf",
    "paths/special/backslash\\name.pdf",
    "paths/special/--leading-dash.pdf",
    "paths/special/.hidden.pdf",
    "paths/目录 空格/子 文件.pdf",
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_payload(baseline_dir: pathlib.Path) -> bytes:
    manifest_path = baseline_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported baseline corpus manifest schema")
    samples = manifest.get("samples")
    if not isinstance(samples, list):
        raise ValueError("baseline corpus manifest has no samples")
    matches = [
        sample
        for sample in samples
        if isinstance(sample, dict) and sample.get("name") == SOURCE_NAME
    ]
    if len(matches) != 1:
        raise ValueError(f"baseline corpus must contain exactly one {SOURCE_NAME}")
    sample = matches[0]
    payload = (baseline_dir / SOURCE_NAME).read_bytes()
    if (
        len(payload) != sample.get("size")
        or _sha256(payload) != sample.get("sha256")
    ):
        raise ValueError(f"baseline corpus sample mismatch: {SOURCE_NAME}")
    return payload


def _octal(value: int, width: int) -> bytes:
    encoded = f"{value:0{width - 1}o}".encode("ascii") + b"\0"
    if len(encoded) != width:
        raise ValueError(f"value does not fit USTAR field: {value}")
    return encoded


def _header(name: str, *, size: int, typeflag: bytes) -> bytes:
    name_bytes = name.encode("utf-8")
    if not name_bytes or len(name_bytes) > 100 or b"\0" in name_bytes:
        raise ValueError(f"path is not representable in fixture USTAR: {name!r}")
    if typeflag not in {b"0", b"5"}:
        raise ValueError("unsupported USTAR fixture type")

    header = bytearray(512)
    header[0 : len(name_bytes)] = name_bytes
    header[100:108] = _octal(0o755 if typeflag == b"5" else 0o644, 8)
    header[108:116] = _octal(0, 8)
    header[116:124] = _octal(0, 8)
    header[124:136] = _octal(size, 12)
    header[136:148] = _octal(0, 12)
    header[148:156] = b"        "
    header[156:157] = typeflag
    header[257:263] = b"ustar\0"
    header[263:265] = b"00"
    checksum = sum(header)
    header[148:156] = f"{checksum:06o}".encode("ascii") + b"\0 "
    return bytes(header)


def _entry(name: str, payload: bytes, *, typeflag: bytes) -> bytes:
    result = bytearray(_header(name, size=len(payload), typeflag=typeflag))
    result.extend(payload)
    result.extend(b"\0" * ((-len(payload)) % 512))
    return bytes(result)


def build_archive(payload: bytes) -> bytes:
    archive = bytearray()
    for directory in DIRECTORIES:
        archive.extend(_entry(directory, b"", typeflag=b"5"))
    for path in FILES:
        archive.extend(_entry(path, payload, typeflag=b"0"))
    archive.extend(b"\0" * 1024)
    return bytes(archive)


def generate(
    baseline_dir: pathlib.Path, output_dir: pathlib.Path
) -> dict[str, object]:
    payload = _load_payload(baseline_dir)
    archive = build_archive(payload)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / ARCHIVE_NAME).write_bytes(archive)

    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "generator": GENERATOR,
        "license": "project-generated paths; baseline corpus bytes only",
        "archive": {
            "name": ARCHIVE_NAME,
            "format": "ustar",
            "size": len(archive),
            "sha256": _sha256(archive),
        },
        "payload": {
            "source": SOURCE_NAME,
            "size": len(payload),
            "sha256": _sha256(payload),
        },
        "directories": list(DIRECTORIES),
        "files": [
            {
                "path": path,
                "source": SOURCE_NAME,
                "size": len(payload),
                "sha256": _sha256(payload),
            }
            for path in FILES
        ],
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline_dir", type=pathlib.Path)
    parser.add_argument("output_dir", type=pathlib.Path)
    args = parser.parse_args()
    manifest = generate(
        args.baseline_dir.resolve(),
        args.output_dir.resolve(),
    )
    # Keep stdout portable on Windows consoles whose active code page is not
    # UTF-8. The versioned manifest remains human-readable UTF-8.
    json.dump(manifest, sys.stdout, ensure_ascii=True, indent=2, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
