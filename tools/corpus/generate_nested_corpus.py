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


def make_stored_zip_entries(entries: tuple[tuple[str, bytes], ...]) -> bytes:
    """Create a deterministic store-only ZIP with no optional metadata."""
    if not entries:
        raise ValueError("ZIP fixture requires at least one member")

    local = bytearray()
    central = bytearray()
    names = set()
    for name, payload in entries:
        if name in names:
            raise ValueError(f"duplicate ZIP member: {name}")
        names.add(name)
        encoded_name = name.encode("utf-8")
        crc = binascii.crc32(payload)
        local_offset = len(local)
        local.extend(
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
        central.extend(
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
                local_offset,
            )
            + encoded_name
        )

    end = struct.pack(
        "<IHHHHIIH",
        0x06054B50,
        0,
        0,
        len(entries),
        len(entries),
        len(central),
        len(local),
        0,
    )
    return bytes(local + central + end)


def make_stored_zip(name: str, payload: bytes) -> bytes:
    return make_stored_zip_entries(((name, payload),))


def make_pdf_member_zip() -> bytes:
    return make_stored_zip("embedded.pdf", BASELINE.make_pdf())


def make_nested_zip() -> bytes:
    return make_stored_zip("inner.zip", make_pdf_member_zip())


def make_many_pdf_member_zip() -> bytes:
    payload = BASELINE.make_pdf()
    return make_stored_zip_entries(
        tuple((f"member-{index:02d}.pdf", payload) for index in range(22))
    )


def make_pe_pdf_overlay() -> bytes:
    return BASELINE.make_pe32() + BASELINE.make_pdf()


def make_pe_zip_overlay() -> bytes:
    return BASELINE.make_pe32() + make_pdf_member_zip()


def _align_up(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def make_pe_pdf_resources(count: int) -> bytes:
    """Create a PE32 with ``count`` RT_RCDATA resources containing PDFs."""
    if count < 1:
        raise ValueError("PE resource fixture requires at least one resource")
    payload = BASELINE.make_pdf()
    root_directory_offset = 0
    type_directory_offset = 0x18
    language_directories_offset = (
        type_directory_offset + 0x10 + count * 8
    )
    data_entries_offset = language_directories_offset + count * 0x18
    resource_payload_offset = _align_up(
        data_entries_offset + count * 0x10,
        0x10,
    )
    resource_virtual_address = 0x1000
    resource_size = resource_payload_offset + count * len(payload)
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

    struct.pack_into(
        "<I", image, optional + 56, _align_up(0x1000 + resource_size, 0x1000)
    )

    resource = 0x200
    struct.pack_into(
        "<IIHHHH",
        image,
        resource + root_directory_offset,
        0,
        0,
        0,
        0,
        0,
        1,
    )
    struct.pack_into(
        "<II",
        image,
        resource + 0x10,
        10,
        0x80000000 | type_directory_offset,
    )
    struct.pack_into(
        "<IIHHHH",
        image,
        resource + type_directory_offset,
        0,
        0,
        0,
        0,
        0,
        count,
    )

    for index in range(count):
        language_directory_offset = (
            language_directories_offset + index * 0x18
        )
        data_entry_offset = data_entries_offset + index * 0x10
        payload_offset = resource_payload_offset + index * len(payload)

        struct.pack_into(
            "<II",
            image,
            resource + type_directory_offset + 0x10 + index * 8,
            index + 1,
            0x80000000 | language_directory_offset,
        )
        struct.pack_into(
            "<IIHHHH",
            image,
            resource + language_directory_offset,
            0,
            0,
            0,
            0,
            0,
            1,
        )
        struct.pack_into(
            "<II",
            image,
            resource + language_directory_offset + 0x10,
            0x409,
            data_entry_offset,
        )
        struct.pack_into(
            "<IIII",
            image,
            resource + data_entry_offset,
            resource_virtual_address + payload_offset,
            len(payload),
            0,
            0,
        )
        image[
            resource + payload_offset :
            resource + payload_offset + len(payload)
        ] = payload
    return bytes(image)


def make_pe_pdf_resource() -> bytes:
    return make_pe_pdf_resources(1)


def make_pe_many_pdf_resources() -> bytes:
    return make_pe_pdf_resources(22)


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
        "many-pdf-members.zip",
        "ZIP containing 22 PDF members",
        ("archive", "pdf x22"),
        make_many_pdf_member_zip,
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
        "pe-many-pdf-resources.exe",
        "PE32 with 22 PDF RCDATA resources",
        ("pe", "resource x22", "pdf x22"),
        make_pe_many_pdf_resources,
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
