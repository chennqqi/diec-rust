#!/usr/bin/env python3
"""Generate benign stored RAR4, CAB, and ISO9660 archives."""

from __future__ import annotations

import argparse
import binascii
import hashlib
import importlib.util
import json
import pathlib
import struct
import sys


GENERATOR = "tools/corpus/generate_archive_format_fixture.py"
PAYLOAD_NAME = "payload.pdf"


def _load_baseline_module():
    module_path = pathlib.Path(__file__).with_name(
        "generate_baseline_corpus.py"
    )
    spec = importlib.util.spec_from_file_location(
        "_diec_archive_format_baseline",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load baseline corpus builders")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BASELINE = _load_baseline_module()
PDF = BASELINE.make_pdf()


def rar4_header(block_type: int, flags: int, body: bytes) -> bytes:
    header_size = 7 + len(body)
    protected = struct.pack("<BHH", block_type, flags, header_size) + body
    crc16 = binascii.crc32(protected) & 0xFFFF
    return struct.pack("<H", crc16) + protected


def make_rar4_stored(name: str, payload: bytes) -> bytes:
    encoded_name = name.encode("ascii")
    signature = b"Rar!\x1a\x07\x00"
    main = rar4_header(0x73, 0, b"\0" * 6)
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
    file_header = rar4_header(0x74, 0x8000, file_body)
    end = rar4_header(0x7B, 0, b"")
    return signature + main + file_header + payload + end


def make_cab_stored(name: str, payload: bytes) -> bytes:
    encoded_name = name.encode("ascii") + b"\0"
    header_size = 36
    folder_size = 8
    file_entry = struct.pack(
        "<IIHHHH",
        len(payload),
        0,
        0,
        0x0021,
        0,
        0x20,
    ) + encoded_name
    files_offset = header_size + folder_size
    data_offset = files_offset + len(file_entry)
    data_block = struct.pack(
        "<IHH",
        0,
        len(payload),
        len(payload),
    ) + payload
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
        1,
        0,
        0xD1EC,
        0,
    )
    folder = struct.pack("<IHH", data_offset, 1, 0)
    return header + folder + file_entry + data_block


def both16(value: int) -> bytes:
    return struct.pack("<H", value) + struct.pack(">H", value)


def both32(value: int) -> bytes:
    return struct.pack("<I", value) + struct.pack(">I", value)


def iso_directory_record(
    extent: int,
    size: int,
    name: bytes,
    *,
    directory: bool,
) -> bytes:
    length = 33 + len(name)
    if len(name) % 2 == 0:
        length += 1
    record = bytearray(length)
    record[0] = length
    record[2:10] = both32(extent)
    record[10:18] = both32(size)
    record[18:25] = bytes((126, 1, 1, 0, 0, 0, 0))
    record[25] = 0x02 if directory else 0
    record[28:32] = both16(1)
    record[32] = len(name)
    record[33 : 33 + len(name)] = name
    return bytes(record)


def make_iso9660_stored(name: str, payload: bytes) -> bytes:
    block_size = 2048
    volume_blocks = 21
    root_block = 19
    payload_block = 20
    image = bytearray(volume_blocks * block_size)

    pvd = memoryview(image)[16 * block_size : 17 * block_size]
    pvd[0] = 1
    pvd[1:6] = b"CD001"
    pvd[6] = 1
    pvd[8:40] = b"DIEC-RUST".ljust(32, b" ")
    pvd[40:72] = b"ARCHIVE-FORMAT".ljust(32, b" ")
    pvd[80:88] = both32(volume_blocks)
    pvd[120:124] = both16(1)
    pvd[124:128] = both16(1)
    pvd[128:132] = both16(block_size)
    pvd[132:140] = both32(10)
    pvd[140:144] = struct.pack("<I", 18)
    pvd[148:152] = struct.pack(">I", 18)
    root_record = iso_directory_record(
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
    records = (
        root_record,
        iso_directory_record(
            root_block,
            block_size,
            b"\x01",
            directory=True,
        ),
        iso_directory_record(
            payload_block,
            len(payload),
            (name.upper() + ";1").encode("ascii"),
            directory=False,
        ),
    )
    cursor = 0
    for record in records:
        directory[cursor : cursor + len(record)] = record
        cursor += len(record)
    image[
        payload_block * block_size :
        payload_block * block_size + len(payload)
    ] = payload
    return bytes(image)


FIXTURES = (
    (
        "pdf-member.rar",
        "RAR4 store archive containing one PDF",
        make_rar4_stored,
    ),
    (
        "pdf-member.cab",
        "CAB store archive containing one PDF",
        make_cab_stored,
    ),
    (
        "pdf-member.iso",
        "ISO9660 image containing one PDF",
        make_iso9660_stored,
    ),
)


def generate(output_dir: pathlib.Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    samples = []
    for name, purpose, factory in FIXTURES:
        data = factory(PAYLOAD_NAME, PDF)
        (output_dir / name).write_bytes(data)
        samples.append(
            {
                "archive_format": name.rsplit(".", 1)[1].upper(),
                "expected_member_name": PAYLOAD_NAME,
                "expected_payload_sha256": hashlib.sha256(PDF).hexdigest(),
                "name": name,
                "purpose": purpose,
                "sha256": hashlib.sha256(data).hexdigest(),
                "size": len(data),
            }
        )
    manifest: dict[str, object] = {
        "schema_version": 1,
        "generator": GENERATOR,
        "license": "project-generated; no third-party sample bytes",
        "samples": samples,
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
    manifest = generate(args.output_dir.resolve())
    sys.stdout.buffer.write(
        (
            json.dumps(manifest, indent=2, sort_keys=True)
            + "\n"
        ).encode("utf-8")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
