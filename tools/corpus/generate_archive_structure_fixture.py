#!/usr/bin/env python3
"""Generate deterministic structural mutations for four archive formats."""

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


GENERATOR = "tools/corpus/generate_archive_structure_fixture.py"
SOURCE_GENERATOR = "tools/corpus/generate_archive_format_fixture.py"


def _load_format_module():
    module_path = pathlib.Path(__file__).with_name(
        "generate_archive_format_fixture.py"
    )
    spec = importlib.util.spec_from_file_location(
        "_diec_archive_structure_format",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load archive format builders")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


FORMAT = _load_format_module()
Mutation = Callable[[bytearray], None]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_u16(data: bytearray, offset: int, value: int) -> None:
    data[offset : offset + 2] = struct.pack("<H", value)


def _write_u32(data: bytearray, offset: int, value: int) -> None:
    data[offset : offset + 4] = struct.pack("<I", value)


def _write_u64(data: bytearray, offset: int, value: int) -> None:
    data[offset : offset + 8] = struct.pack("<Q", value)


def _write_both16(data: bytearray, offset: int, value: int) -> None:
    data[offset : offset + 4] = FORMAT.both16(value)


def _write_both32(data: bytearray, offset: int, value: int) -> None:
    data[offset : offset + 8] = FORMAT.both32(value)


def _recompute_7z_start_crc(data: bytearray) -> None:
    _write_u32(
        data,
        8,
        binascii.crc32(data[12:32]) & 0xFFFFFFFF,
    )


def _sevenzip_next_header_bounds(data: bytearray) -> tuple[int, int]:
    offset = int.from_bytes(data[12:20], "little")
    size = int.from_bytes(data[20:28], "little")
    return 32 + offset, size


def _recompute_7z_next_and_start_crc(data: bytearray) -> None:
    offset, size = _sevenzip_next_header_bounds(data)
    if offset + size > len(data):
        raise RuntimeError("7Z next header no longer fits")
    _write_u32(
        data,
        28,
        binascii.crc32(data[offset : offset + size]) & 0xFFFFFFFF,
    )
    _recompute_7z_start_crc(data)


def _flip_7z_start_crc(data: bytearray) -> None:
    data[8] ^= 1


def _move_7z_next_header_past_eof(data: bytearray) -> None:
    offset = int.from_bytes(data[12:20], "little")
    _write_u64(data, 12, offset + 1)
    _recompute_7z_start_crc(data)


def _grow_7z_next_header_past_eof(data: bytearray) -> None:
    size = int.from_bytes(data[20:28], "little")
    _write_u64(data, 20, size + 1)
    _recompute_7z_start_crc(data)


def _flip_7z_next_header_crc(data: bytearray) -> None:
    data[28] ^= 1
    _recompute_7z_start_crc(data)


def _flip_7z_packed_crc(data: bytearray) -> None:
    header_offset, header_size = _sevenzip_next_header_bounds(data)
    payload_crc = struct.pack(
        "<I",
        binascii.crc32(FORMAT.PDF) & 0xFFFFFFFF,
    )
    header = bytes(
        data[header_offset : header_offset + header_size]
    )
    positions = []
    cursor = 0
    while True:
        found = header.find(payload_crc, cursor)
        if found < 0:
            break
        positions.append(found)
        cursor = found + 1
    if len(positions) != 2:
        raise RuntimeError("7Z Copy CRC inventory changed")
    data[header_offset + positions[0]] ^= 1
    _recompute_7z_next_and_start_crc(data)


def _grow_7z_unpacked_size(data: bytearray) -> None:
    header_offset, header_size = _sevenzip_next_header_bounds(data)
    old = b"\x0c" + FORMAT.sevenzip_uint64(len(FORMAT.PDF))
    new = b"\x0c" + FORMAT.sevenzip_uint64(len(FORMAT.PDF) + 1)
    if len(old) != len(new):
        raise RuntimeError("7Z size encoding width changed")
    header = bytes(
        data[header_offset : header_offset + header_size]
    )
    if header.count(old) != 1:
        raise RuntimeError("7Z unpacked-size field inventory changed")
    position = header.index(old)
    data[
        header_offset + position :
        header_offset + position + len(old)
    ] = new
    _recompute_7z_next_and_start_crc(data)


def _recompute_rar_header_crc(
    data: bytearray,
    offset: int,
) -> None:
    size = int.from_bytes(data[offset + 5 : offset + 7], "little")
    _write_u16(
        data,
        offset,
        binascii.crc32(data[offset + 2 : offset + size])
        & 0xFFFF,
    )


def _flip_rar_main_crc(data: bytearray) -> None:
    data[7] ^= 1


def _flip_rar_file_crc(data: bytearray) -> None:
    data[20] ^= 1


def _grow_rar_packed_size(data: bytearray) -> None:
    _write_u32(data, 27, len(FORMAT.PDF) + 1)
    _recompute_rar_header_crc(data, 20)


def _grow_rar_unpacked_size(data: bytearray) -> None:
    _write_u32(data, 31, len(FORMAT.PDF) + 1)
    _recompute_rar_header_crc(data, 20)


def _flip_rar_data_crc(data: bytearray) -> None:
    data[36] ^= 1
    _recompute_rar_header_crc(data, 20)


def _set_rar_unknown_method(data: bytearray) -> None:
    data[45] = 0x7F
    _recompute_rar_header_crc(data, 20)


def _grow_rar_name_size(data: bytearray) -> None:
    _write_u16(data, 46, len(FORMAT.PAYLOAD_NAME) + 1)
    _recompute_rar_header_crc(data, 20)


def _shrink_cabinet_size(data: bytearray) -> None:
    _write_u32(data, 8, len(data) - 1)


def _move_cab_files_offset(data: bytearray) -> None:
    _write_u32(data, 16, 45)


def _move_cab_data_offset(data: bytearray) -> None:
    _write_u32(data, 36, 73)


def _set_cab_unknown_method(data: bytearray) -> None:
    _write_u16(data, 42, 0xFFFF)


def _grow_cab_file_size(data: bytearray) -> None:
    _write_u32(data, 44, len(FORMAT.PDF) + 1)


def _grow_cab_folder_offset(data: bytearray) -> None:
    _write_u32(data, 48, 1)


def _grow_cab_compressed_size(data: bytearray) -> None:
    _write_u16(data, 76, len(FORMAT.PDF) + 1)


def _grow_cab_uncompressed_size(data: bytearray) -> None:
    _write_u16(data, 78, len(FORMAT.PDF) + 1)


ISO_PVD = 16 * 2048
ISO_DIRECTORY = 19 * 2048
ISO_PAYLOAD_RECORD = ISO_DIRECTORY + 68


def _flip_iso_descriptor_id(data: bytearray) -> None:
    data[ISO_PVD + 1] ^= 1


def _shrink_iso_volume_size(data: bytearray) -> None:
    _write_both32(data, ISO_PVD + 80, 20)


def _set_iso_block_size_1024(data: bytearray) -> None:
    _write_both16(data, ISO_PVD + 128, 1024)


def _move_iso_root_extent(data: bytearray) -> None:
    _write_both32(data, ISO_PVD + 156 + 2, 20)


def _shrink_iso_root_size(data: bytearray) -> None:
    _write_both32(data, ISO_PVD + 156 + 10, 2047)


def _zero_iso_payload_record_length(data: bytearray) -> None:
    data[ISO_PAYLOAD_RECORD] = 0


def _move_iso_payload_extent(data: bytearray) -> None:
    _write_both32(data, ISO_PAYLOAD_RECORD + 2, 21)


def _grow_iso_payload_size(data: bytearray) -> None:
    _write_both32(
        data,
        ISO_PAYLOAD_RECORD + 10,
        len(FORMAT.PDF) + 1,
    )


CASES: tuple[
    tuple[str, str, str, str, str, Mutation | None],
    ...,
] = (
    ("sevenzip", "7Z", "7z", "control", "none", None),
    (
        "sevenzip",
        "7Z",
        "7z",
        "start-header-crc",
        "bit-flip",
        _flip_7z_start_crc,
    ),
    (
        "sevenzip",
        "7Z",
        "7z",
        "next-header-offset",
        "past-eof",
        _move_7z_next_header_past_eof,
    ),
    (
        "sevenzip",
        "7Z",
        "7z",
        "next-header-size",
        "past-eof",
        _grow_7z_next_header_past_eof,
    ),
    (
        "sevenzip",
        "7Z",
        "7z",
        "next-header-crc",
        "bit-flip",
        _flip_7z_next_header_crc,
    ),
    (
        "sevenzip",
        "7Z",
        "7z",
        "packed-crc",
        "bit-flip",
        _flip_7z_packed_crc,
    ),
    (
        "sevenzip",
        "7Z",
        "7z",
        "unpacked-size",
        "plus-one",
        _grow_7z_unpacked_size,
    ),
    ("rar4", "RAR4", "rar", "control", "none", None),
    (
        "rar4",
        "RAR4",
        "rar",
        "main-header-crc",
        "bit-flip",
        _flip_rar_main_crc,
    ),
    (
        "rar4",
        "RAR4",
        "rar",
        "file-header-crc",
        "bit-flip",
        _flip_rar_file_crc,
    ),
    (
        "rar4",
        "RAR4",
        "rar",
        "packed-size",
        "plus-one",
        _grow_rar_packed_size,
    ),
    (
        "rar4",
        "RAR4",
        "rar",
        "unpacked-size",
        "plus-one",
        _grow_rar_unpacked_size,
    ),
    (
        "rar4",
        "RAR4",
        "rar",
        "data-crc",
        "bit-flip",
        _flip_rar_data_crc,
    ),
    (
        "rar4",
        "RAR4",
        "rar",
        "method",
        "unknown-0x7f",
        _set_rar_unknown_method,
    ),
    (
        "rar4",
        "RAR4",
        "rar",
        "name-size",
        "plus-one",
        _grow_rar_name_size,
    ),
    ("cab", "CAB", "cab", "control", "none", None),
    (
        "cab",
        "CAB",
        "cab",
        "cabinet-size",
        "minus-one",
        _shrink_cabinet_size,
    ),
    (
        "cab",
        "CAB",
        "cab",
        "files-offset",
        "plus-one",
        _move_cab_files_offset,
    ),
    (
        "cab",
        "CAB",
        "cab",
        "data-offset",
        "plus-one",
        _move_cab_data_offset,
    ),
    (
        "cab",
        "CAB",
        "cab",
        "method",
        "unknown-0xffff",
        _set_cab_unknown_method,
    ),
    (
        "cab",
        "CAB",
        "cab",
        "file-size",
        "plus-one",
        _grow_cab_file_size,
    ),
    (
        "cab",
        "CAB",
        "cab",
        "folder-offset",
        "plus-one",
        _grow_cab_folder_offset,
    ),
    (
        "cab",
        "CAB",
        "cab",
        "compressed-size",
        "plus-one",
        _grow_cab_compressed_size,
    ),
    (
        "cab",
        "CAB",
        "cab",
        "uncompressed-size",
        "plus-one",
        _grow_cab_uncompressed_size,
    ),
    ("iso9660", "ISO9660", "iso", "control", "none", None),
    (
        "iso9660",
        "ISO9660",
        "iso",
        "descriptor-id",
        "bit-flip",
        _flip_iso_descriptor_id,
    ),
    (
        "iso9660",
        "ISO9660",
        "iso",
        "volume-size",
        "minus-one-block",
        _shrink_iso_volume_size,
    ),
    (
        "iso9660",
        "ISO9660",
        "iso",
        "logical-block-size",
        "set-1024",
        _set_iso_block_size_1024,
    ),
    (
        "iso9660",
        "ISO9660",
        "iso",
        "root-extent",
        "plus-one-block",
        _move_iso_root_extent,
    ),
    (
        "iso9660",
        "ISO9660",
        "iso",
        "root-size",
        "minus-one",
        _shrink_iso_root_size,
    ),
    (
        "iso9660",
        "ISO9660",
        "iso",
        "payload-record-length",
        "zero",
        _zero_iso_payload_record_length,
    ),
    (
        "iso9660",
        "ISO9660",
        "iso",
        "payload-extent",
        "plus-one-block",
        _move_iso_payload_extent,
    ),
    (
        "iso9660",
        "ISO9660",
        "iso",
        "payload-size",
        "plus-one",
        _grow_iso_payload_size,
    ),
)


def controls() -> dict[str, bytes]:
    return {
        "sevenzip": FORMAT.make_7z_single(
            FORMAT.PAYLOAD_NAME,
            FORMAT.PDF,
            "Copy",
        ),
        "rar4": FORMAT.make_rar4_stored(
            FORMAT.PAYLOAD_NAME,
            FORMAT.PDF,
        ),
        "cab": FORMAT.make_cab_stored(
            FORMAT.PAYLOAD_NAME,
            FORMAT.PDF,
        ),
        "iso9660": FORMAT.make_iso9660_stored(
            FORMAT.PAYLOAD_NAME,
            FORMAT.PDF,
        ),
    }


def generate(output_dir: pathlib.Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_path = pathlib.Path(__file__).with_name(
        "generate_archive_format_fixture.py"
    )
    control_data = controls()
    samples = []
    names = set()
    for (
        control_name,
        archive_format,
        extension,
        field,
        mutation_name,
        mutation,
    ) in CASES:
        control = control_data[control_name]
        data = bytearray(control)
        if mutation is not None:
            mutation(data)
        name = f"{control_name}-{field}-{mutation_name}.{extension}"
        if name in names:
            raise RuntimeError(f"duplicate fixture name: {name}")
        names.add(name)
        output = bytes(data)
        changed_offsets = [
            index
            for index, (before, after) in enumerate(
                zip(control, output, strict=True)
            )
            if before != after
        ]
        if mutation is None:
            if changed_offsets:
                raise RuntimeError("control unexpectedly changed")
        elif not changed_offsets:
            raise RuntimeError(f"mutation changed no bytes: {name}")
        (output_dir / name).write_bytes(output)
        samples.append(
            {
                "archive_format": archive_format,
                "changed_byte_count": len(changed_offsets),
                "changed_offset_max": (
                    max(changed_offsets) if changed_offsets else None
                ),
                "changed_offset_min": (
                    min(changed_offsets) if changed_offsets else None
                ),
                "control_name": control_name,
                "control_sha256": sha256(control),
                "field": field,
                "mutation": mutation_name,
                "name": name,
                "purpose": (
                    f"{archive_format} {field} {mutation_name} "
                    "structural boundary"
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
