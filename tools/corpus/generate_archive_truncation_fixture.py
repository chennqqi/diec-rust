#!/usr/bin/env python3
"""Generate deterministic 7Z, RAR4, CAB, and ISO truncation ladders."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import sys


GENERATOR = "tools/corpus/generate_archive_truncation_fixture.py"
SOURCE_GENERATOR = "tools/corpus/generate_archive_format_fixture.py"


def _load_format_module():
    module_path = pathlib.Path(__file__).with_name(
        "generate_archive_format_fixture.py"
    )
    spec = importlib.util.spec_from_file_location(
        "_diec_archive_truncation_format",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load archive format builders")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


FORMAT = _load_format_module()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def controls() -> dict[str, tuple[str, bytes]]:
    return {
        "sevenzip": (
            "7Z",
            FORMAT.make_7z_single(
                FORMAT.PAYLOAD_NAME,
                FORMAT.PDF,
                "Copy",
            ),
        ),
        "rar4": (
            "RAR4",
            FORMAT.make_rar4_stored(
                FORMAT.PAYLOAD_NAME,
                FORMAT.PDF,
            ),
        ),
        "cab": (
            "CAB",
            FORMAT.make_cab_stored(
                FORMAT.PAYLOAD_NAME,
                FORMAT.PDF,
            ),
        ),
        "iso9660": (
            "ISO9660",
            FORMAT.make_iso9660_stored(
                FORMAT.PAYLOAD_NAME,
                FORMAT.PDF,
            ),
        ),
    }


LADDERS = {
    "sevenzip": (
        ("signature", 6),
        ("header-minus-one", 31),
        ("header", 32),
        ("packed-data", 363),
        ("full-minus-one", 426),
        ("full", 427),
    ),
    "rar4": (
        ("signature", 7),
        ("main-header-minus-one", 19),
        ("main-header", 20),
        ("file-header", 63),
        ("payload", 394),
        ("full-minus-one", 400),
        ("full", 401),
    ),
    "cab": (
        ("signature", 4),
        ("header-minus-one", 35),
        ("header", 36),
        ("folder", 44),
        ("data-start", 72),
        ("full-minus-one", 410),
        ("full", 411),
    ),
    "iso9660": (
        ("descriptor-signature", 32774),
        ("descriptor-version", 32775),
        ("primary-descriptor", 34816),
        ("directory-end", 40960),
        ("full-minus-one", 43007),
        ("full", 43008),
    ),
}
EXTENSIONS = {
    "sevenzip": "7z",
    "rar4": "rar",
    "cab": "cab",
    "iso9660": "iso",
}


def generate(output_dir: pathlib.Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_path = pathlib.Path(__file__).with_name(
        "generate_archive_format_fixture.py"
    )
    samples = []
    control_data = controls()
    if set(control_data) != set(LADDERS):
        raise RuntimeError("truncation control inventory changed")
    for control_name, ladder in LADDERS.items():
        archive_format, full_data = control_data[control_name]
        expected_full_size = ladder[-1][1]
        if len(full_data) != expected_full_size:
            raise RuntimeError(
                f"{control_name} control size changed: "
                f"{len(full_data)} != {expected_full_size}"
            )
        previous_cut = -1
        for boundary, cut in ladder:
            if cut <= previous_cut or cut > len(full_data):
                raise RuntimeError(
                    f"invalid {control_name} truncation ladder"
                )
            previous_cut = cut
            name = (
                f"{control_name}-{boundary}."
                f"{EXTENSIONS[control_name]}"
            )
            data = full_data[:cut]
            (output_dir / name).write_bytes(data)
            samples.append(
                {
                    "archive_format": archive_format,
                    "boundary": boundary,
                    "control_name": control_name,
                    "cut_offset": cut,
                    "full_sha256": sha256(full_data),
                    "full_size": len(full_data),
                    "name": name,
                    "purpose": (
                        f"{archive_format} prefix ending at "
                        f"{boundary}"
                    ),
                    "sha256": sha256(data),
                    "size": len(data),
                }
            )
    manifest: dict[str, object] = {
        "generator": GENERATOR,
        "license": "project-generated",
        "samples": samples,
        "schema_version": 1,
        "source_generator": {
            "path": SOURCE_GENERATOR,
            "sha256": sha256(source_path.read_bytes()),
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=pathlib.Path)
    args = parser.parse_args()
    print(json.dumps(generate(args.output_dir), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
