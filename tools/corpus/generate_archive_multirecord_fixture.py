#!/usr/bin/env python3
"""Generate deterministic two-record archives for four formats."""

from __future__ import annotations

import argparse
import binascii
import hashlib
import importlib.util
import json
import pathlib
import struct
import sys
from typing import Callable


GENERATOR = "tools/corpus/generate_archive_multirecord_fixture.py"
SOURCE_GENERATOR = "tools/corpus/generate_archive_format_fixture.py"


def _load_format_module():
    module_path = pathlib.Path(__file__).with_name(
        "generate_archive_format_fixture.py"
    )
    spec = importlib.util.spec_from_file_location(
        "_diec_archive_multirecord_format",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load archive format builders")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


FORMAT = _load_format_module()
PDF_331 = FORMAT.PDF
PDF_332 = FORMAT.PDF + b"\n"
Entry = tuple[str, bytes]
Builder = Callable[[tuple[Entry, ...]], bytes]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_entries(entries: tuple[Entry, ...]) -> None:
    if len(entries) != 2:
        raise ValueError("multi-record fixture requires exactly two entries")
    for name, payload in entries:
        encoded = name.encode("ascii")
        if not encoded or b"\0" in encoded:
            raise ValueError("entry name must be non-empty ASCII without NUL")
        if len(payload) > 0xFFFF:
            raise ValueError("entry payload is too large")


def make_7z_copy(entries: tuple[Entry, ...]) -> bytes:
    validate_entries(entries)
    packed = b"".join(payload for _, payload in entries)
    sizes = b"".join(
        FORMAT.sevenzip_uint64(len(payload))
        for _, payload in entries
    )
    crcs = b"".join(
        struct.pack("<I", binascii.crc32(payload) & 0xFFFFFFFF)
        for _, payload in entries
    )
    coder = b"\x01" + FORMAT.SEVENZIP_CODER_IDS["Copy"]
    count = FORMAT.sevenzip_uint64(len(entries))
    pack_info = (
        b"\x06"
        + FORMAT.sevenzip_uint64(0)
        + count
        + b"\x09"
        + sizes
        + b"\x0a\x01"
        + crcs
        + b"\x00"
    )
    unpack_info = (
        b"\x07\x0b"
        + count
        + b"\x00"
        + (FORMAT.sevenzip_uint64(1) + coder) * len(entries)
        + b"\x0c"
        + sizes
        + b"\x0a\x01"
        + crcs
        + b"\x00"
    )
    main_streams = b"\x04" + pack_info + unpack_info + b"\x00"
    encoded_names = b"".join(
        name.encode("utf-16le") + b"\0\0"
        for name, _ in entries
    )
    name_property = b"\x00" + encoded_names
    files_info = (
        b"\x05"
        + count
        + b"\x11"
        + FORMAT.sevenzip_uint64(len(name_property))
        + name_property
        + b"\x00"
    )
    next_header = b"\x01" + main_streams + files_info + b"\x00"
    start_header = struct.pack(
        "<QQI",
        len(packed),
        len(next_header),
        binascii.crc32(next_header) & 0xFFFFFFFF,
    )
    return (
        b"7z\xbc\xaf\x27\x1c"
        + b"\x00\x04"
        + struct.pack(
            "<I",
            binascii.crc32(start_header) & 0xFFFFFFFF,
        )
        + start_header
        + packed
        + next_header
    )


def make_rar4_stored(entries: tuple[Entry, ...]) -> bytes:
    validate_entries(entries)
    output = bytearray(b"Rar!\x1a\x07\x00")
    output.extend(FORMAT.rar4_header(0x73, 0, b"\0" * 6))
    for name, payload in entries:
        encoded_name = name.encode("ascii")
        file_body = struct.pack(
            "<IIBIIBBHI",
            len(payload),
            len(payload),
            3,
            binascii.crc32(payload) & 0xFFFFFFFF,
            0,
            20,
            0x30,
            len(encoded_name),
            0x20,
        ) + encoded_name
        output.extend(FORMAT.rar4_header(0x74, 0x8000, file_body))
        output.extend(payload)
    output.extend(FORMAT.rar4_header(0x7B, 0, b""))
    return bytes(output)


def make_cab_stored(entries: tuple[Entry, ...]) -> bytes:
    validate_entries(entries)
    header_size = 36
    folder_size = 8
    file_entries = bytearray()
    folder_offset = 0
    packed = bytearray()
    for name, payload in entries:
        file_entries.extend(
            struct.pack(
                "<IIHHHH",
                len(payload),
                folder_offset,
                0,
                0x0021,
                0,
                0x20,
            )
        )
        file_entries.extend(name.encode("ascii") + b"\0")
        folder_offset += len(payload)
        packed.extend(payload)
    files_offset = header_size + folder_size
    data_offset = files_offset + len(file_entries)
    data_block = (
        struct.pack("<IHH", 0, len(packed), len(packed)) + packed
    )
    cabinet_size = data_offset + len(data_block)
    header = struct.pack(
        "<4sIIIIIBBHHHHH",
        b"MSCF",
        0,
        cabinet_size,
        0,
        files_offset,
        0,
        3,
        1,
        1,
        len(entries),
        0,
        0xD1EC,
        0,
    )
    folder = struct.pack("<IHH", data_offset, 1, 0)
    return header + folder + bytes(file_entries) + bytes(data_block)


def make_iso9660(entries: tuple[Entry, ...]) -> bytes:
    validate_entries(entries)
    block_size = 2048
    root_block = 19
    first_payload_block = 20
    volume_blocks = first_payload_block + len(entries)
    image = bytearray(volume_blocks * block_size)

    pvd = memoryview(image)[16 * block_size : 17 * block_size]
    pvd[0] = 1
    pvd[1:6] = b"CD001"
    pvd[6] = 1
    pvd[8:40] = b"DIEC-RUST".ljust(32, b" ")
    pvd[40:72] = b"ARCHIVE-MULTIRECORD".ljust(32, b" ")
    pvd[80:88] = FORMAT.both32(volume_blocks)
    pvd[120:124] = FORMAT.both16(1)
    pvd[124:128] = FORMAT.both16(1)
    pvd[128:132] = FORMAT.both16(block_size)
    pvd[132:140] = FORMAT.both32(10)
    pvd[140:144] = struct.pack("<I", 18)
    pvd[148:152] = struct.pack(">I", 18)
    root_record = FORMAT.iso_directory_record(
        root_block,
        block_size,
        b"\0",
        directory=True,
    )
    pvd[156 : 156 + len(root_record)] = root_record
    pvd[881] = 1

    terminator = memoryview(image)[17 * block_size : 18 * block_size]
    terminator[0] = 255
    terminator[1:6] = b"CD001"
    terminator[6] = 1
    path_table = memoryview(image)[18 * block_size : 19 * block_size]
    path_table[0:10] = (
        b"\x01\x00"
        + struct.pack("<I", root_block)
        + struct.pack("<H", 1)
        + b"\0\0"
    )

    directory = memoryview(image)[
        root_block * block_size : (root_block + 1) * block_size
    ]
    records = [
        root_record,
        FORMAT.iso_directory_record(
            root_block,
            block_size,
            b"\x01",
            directory=True,
        ),
    ]
    for index, (name, payload) in enumerate(entries):
        records.append(
            FORMAT.iso_directory_record(
                first_payload_block + index,
                len(payload),
                (name.upper() + ";1").encode("ascii"),
                directory=False,
            )
        )
        start = (first_payload_block + index) * block_size
        image[start : start + len(payload)] = payload
    cursor = 0
    for record in records:
        directory[cursor : cursor + len(record)] = record
        cursor += len(record)
    return bytes(image)


FORMATS: tuple[tuple[str, str, str, Builder], ...] = (
    ("sevenzip", "7Z", "7z", make_7z_copy),
    ("rar4", "RAR4", "rar", make_rar4_stored),
    ("cab", "CAB", "cab", make_cab_stored),
    ("iso9660", "ISO9660", "iso", make_iso9660),
)
ENTRY_CASES: tuple[tuple[str, tuple[Entry, ...]], ...] = (
    (
        "forward",
        (("first.pdf", PDF_331), ("second.pdf", PDF_332)),
    ),
    (
        "reverse",
        (("second.pdf", PDF_332), ("first.pdf", PDF_331)),
    ),
    (
        "duplicate-name",
        (("same.pdf", PDF_331), ("same.pdf", PDF_332)),
    ),
    (
        "empty-first",
        (("empty.bin", b""), ("second.pdf", PDF_331)),
    ),
)


def generate(output_dir: pathlib.Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_path = pathlib.Path(__file__).with_name(
        "generate_archive_format_fixture.py"
    )
    samples = []
    for slug, archive_format, extension, builder in FORMATS:
        for case_name, entries in ENTRY_CASES:
            output = builder(entries)
            name = f"{slug}-{case_name}.{extension}"
            (output_dir / name).write_bytes(output)
            samples.append(
                {
                    "archive_format": archive_format,
                    "entries": [
                        {
                            "name": entry_name,
                            "sha256": sha256(payload),
                            "size": len(payload),
                        }
                        for entry_name, payload in entries
                    ],
                    "name": name,
                    "order_case": case_name,
                    "purpose": (
                        f"{archive_format} two-record {case_name} "
                        "ordering and duplicate-name boundary"
                    ),
                    "sha256": sha256(output),
                    "size": len(output),
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
    serialized = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    (output_dir / "manifest.json").write_text(
        serialized,
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=pathlib.Path)
    parser.add_argument("--manifest-output", type=pathlib.Path)
    args = parser.parse_args()
    manifest = generate(args.output_dir)
    serialized = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if args.manifest_output is not None:
        args.manifest_output.parent.mkdir(parents=True, exist_ok=True)
        args.manifest_output.write_text(
            serialized,
            encoding="utf-8",
            newline="\n",
        )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
