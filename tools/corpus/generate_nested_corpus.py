#!/usr/bin/env python3
"""Generate benign, deterministic archive and overlay scan fixtures."""

from __future__ import annotations

import argparse
import binascii
import hashlib
import importlib.util
import json
import pathlib
import struct
import sys
from collections.abc import Callable


def _load_baseline_module():
    module_path = pathlib.Path(__file__).with_name(
        "generate_baseline_corpus.py"
    )
    spec = importlib.util.spec_from_file_location(
        "_diec_baseline_corpus", module_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load baseline corpus builders")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BASELINE = _load_baseline_module()


def make_stored_zip(name: str, payload: bytes) -> bytes:
    """Create a single-member ZIP without timestamps or compression."""
    encoded_name = name.encode("utf-8")
    crc = binascii.crc32(payload)
    local = (
        struct.pack(
            "<IHHHHHIIIHH",
            0x04034B50,
            20,
            0,
            0,
            0,
            0x0021,
            crc,
            len(payload),
            len(payload),
            len(encoded_name),
            0,
        )
        + encoded_name
        + payload
    )
    central = (
        struct.pack(
            "<IHHHHHHIIIHHHHHII",
            0x02014B50,
            0x0314,
            20,
            0,
            0,
            0,
            0x0021,
            crc,
            len(payload),
            len(payload),
            len(encoded_name),
            0,
            0,
            0,
            0,
            0,
            0,
        )
        + encoded_name
    )
    end = struct.pack(
        "<IHHHHIIH",
        0x06054B50,
        0,
        0,
        1,
        1,
        len(central),
        len(local),
        0,
    )
    return local + central + end


def make_pdf_member_zip() -> bytes:
    return make_stored_zip("embedded.pdf", BASELINE.make_pdf())


def make_nested_zip() -> bytes:
    return make_stored_zip("inner.zip", make_pdf_member_zip())


def make_pe_pdf_overlay() -> bytes:
    return BASELINE.make_pe32() + BASELINE.make_pdf()


def make_pe_zip_overlay() -> bytes:
    return BASELINE.make_pe32() + make_pdf_member_zip()


def _align_up(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def make_pe_pdf_resource() -> bytes:
    """Create a PE32 with one RT_RCDATA resource containing a PDF."""
    payload = BASELINE.make_pdf()
    resource_payload_offset = 0x60
    resource_virtual_address = 0x1000
    resource_size = resource_payload_offset + len(payload)
    raw_size = _align_up(resource_size, 0x200)
    image = bytearray(0x200 + raw_size)

    image[0:2] = b"MZ"
    struct.pack_into("<I", image, 0x3C, 0x80)
    image[0x80:0x84] = b"PE\0\0"
    struct.pack_into(
        "<HHIIIHH",
        image,
        0x84,
        0x14C,
        1,
        0,
        0,
        0,
        224,
        0x0102,
    )
    optional = 0x98
    struct.pack_into("<H", image, optional, 0x10B)
    struct.pack_into("<II", image, optional + 20, 0x1000, 0x1000)
    struct.pack_into("<I", image, optional + 28, 0x400000)
    struct.pack_into("<II", image, optional + 32, 0x1000, 0x200)
    struct.pack_into("<II", image, optional + 56, 0x2000, 0x200)
    struct.pack_into("<H", image, optional + 68, 3)
    struct.pack_into("<I", image, optional + 92, 16)
    struct.pack_into(
        "<II",
        image,
        optional + 96 + 2 * 8,
        resource_virtual_address,
        resource_size,
    )

    section = optional + 224
    image[section : section + 8] = b".rsrc\0\0\0"
    struct.pack_into(
        "<IIIIIIHHI",
        image,
        section + 8,
        resource_size,
        resource_virtual_address,
        raw_size,
        0x200,
        0,
        0,
        0,
        0,
        0x40000040,
    )

    resource = 0x200
    struct.pack_into("<IIHHHH", image, resource, 0, 0, 0, 0, 0, 1)
    struct.pack_into("<II", image, resource + 0x10, 10, 0x80000018)
    struct.pack_into(
        "<IIHHHH", image, resource + 0x18, 0, 0, 0, 0, 0, 1
    )
    struct.pack_into("<II", image, resource + 0x28, 1, 0x80000030)
    struct.pack_into(
        "<IIHHHH", image, resource + 0x30, 0, 0, 0, 0, 0, 1
    )
    struct.pack_into("<II", image, resource + 0x40, 0x409, 0x48)
    struct.pack_into(
        "<IIII",
        image,
        resource + 0x48,
        resource_virtual_address + resource_payload_offset,
        len(payload),
        0,
        0,
    )
    image[
        resource + resource_payload_offset :
        resource + resource_payload_offset + len(payload)
    ] = payload
    return bytes(image)


GENERATORS: tuple[
    tuple[str, str, tuple[str, ...], Callable[[], bytes]], ...
] = (
    (
        "pdf-member.zip",
        "ZIP containing a PDF member",
        ("archive", "pdf"),
        make_pdf_member_zip,
    ),
    (
        "nested-zip.zip",
        "ZIP containing a ZIP containing a PDF",
        ("archive", "archive", "pdf"),
        make_nested_zip,
    ),
    (
        "pe-pdf-overlay.exe",
        "PE32 with a PDF overlay",
        ("pe", "overlay", "pdf"),
        make_pe_pdf_overlay,
    ),
    (
        "pe-pdf-resource.exe",
        "PE32 with a PDF RCDATA resource",
        ("pe", "resource", "pdf"),
        make_pe_pdf_resource,
    ),
    (
        "pe-zip-overlay.exe",
        "PE32 with a ZIP overlay containing a PDF",
        ("pe", "overlay", "archive", "pdf"),
        make_pe_zip_overlay,
    ),
)


def generate(output_dir: pathlib.Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    samples = []
    for name, intended_structure, layers, factory in GENERATORS:
        data = factory()
        (output_dir / name).write_bytes(data)
        samples.append(
            {
                "intended_structure": intended_structure,
                "layers": list(layers),
                "name": name,
                "sha256": hashlib.sha256(data).hexdigest(),
                "size": len(data),
            }
        )

    manifest: dict[str, object] = {
        "generator": "tools/corpus/generate_nested_corpus.py",
        "license": "project-generated; no third-party sample bytes",
        "samples": samples,
        "schema_version": 1,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir", type=pathlib.Path)
    args = parser.parse_args()
    manifest = generate(args.output_dir.resolve())
    json.dump(manifest, fp=sys.stdout, indent=2, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
