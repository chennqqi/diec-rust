#!/usr/bin/env python3
"""Generate deterministic ISO9660 fixtures around the 100000-record limit."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import struct
import sys


def _load_baseline_module():
    module_path = pathlib.Path(__file__).with_name(
        "generate_baseline_corpus.py"
    )
    spec = importlib.util.spec_from_file_location(
        "_diec_archive_iteration_baseline", module_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load baseline corpus builders")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BASELINE = _load_baseline_module()

BLOCK_SIZE = 2048
RECORD_COUNT = 100001
SENTINEL_ORDINALS = (99999, 100000, 100001)
ROOT_EXTENT = 18
PLACEHOLDER_SIZE = 0x1000000


def _both16(value: int) -> bytes:
    return struct.pack("<H", value) + struct.pack(">H", value)


def _both32(value: int) -> bytes:
    return struct.pack("<I", value) + struct.pack(">I", value)


def _directory_record(
    *,
    name: bytes,
    extent: int,
    size: int,
    flags: int,
) -> bytes:
    if not 1 <= len(name) <= 222:
        raise ValueError("ISO9660 identifier length is out of range")
    padding = b"\0" if len(name) % 2 == 0 else b""
    length = 33 + len(name) + len(padding)
    return (
        bytes((length, 0))
        + _both32(extent)
        + _both32(size)
        + bytes((126, 1, 1, 0, 0, 0, 0))
        + bytes((flags, 0, 0))
        + _both16(1)
        + bytes((len(name),))
        + name
        + padding
    )


def _pack_records(records: list[bytes]) -> bytes:
    result = bytearray()
    offset_in_block = 0
    for record in records:
        if offset_in_block + len(record) > BLOCK_SIZE:
            result.extend(bytes(BLOCK_SIZE - offset_in_block))
            offset_in_block = 0
        result.extend(record)
        offset_in_block += len(record)
        if offset_in_block == BLOCK_SIZE:
            offset_in_block = 0
    if offset_in_block:
        result.extend(bytes(BLOCK_SIZE - offset_in_block))
    return bytes(result)


def _primary_volume_descriptor(
    *,
    total_blocks: int,
    root_size: int,
) -> bytes:
    descriptor = bytearray(BLOCK_SIZE)
    descriptor[0] = 1
    descriptor[1:6] = b"CD001"
    descriptor[6] = 1
    descriptor[8:40] = b"DIEC-RUST".ljust(32, b" ")
    descriptor[40:72] = b"ARCHIVE-ITERATION-BOUNDARY".ljust(
        32, b" "
    )
    descriptor[80:88] = _both32(total_blocks)
    descriptor[120:124] = _both16(1)
    descriptor[124:128] = _both16(1)
    descriptor[128:132] = _both16(BLOCK_SIZE)
    descriptor[156:190] = _directory_record(
        name=b"\0",
        extent=ROOT_EXTENT,
        size=root_size,
        flags=0x02,
    )
    descriptor[881] = 1
    return bytes(descriptor)


def _terminator() -> bytes:
    descriptor = bytearray(BLOCK_SIZE)
    descriptor[0] = 255
    descriptor[1:6] = b"CD001"
    descriptor[6] = 1
    return bytes(descriptor)


def make_fixture(sentinel_ordinal: int) -> bytes:
    """Return an ISO with a valid PDF at the selected one-based ordinal."""
    if sentinel_ordinal not in SENTINEL_ORDINALS:
        raise ValueError("unsupported sentinel ordinal")

    placeholder = _directory_record(
        name=b"F000000;1",
        extent=0,
        size=PLACEHOLDER_SIZE,
        flags=0,
    )
    records_per_block = BLOCK_SIZE // len(placeholder)
    root_record_count = RECORD_COUNT + 2
    root_blocks = (
        root_record_count + records_per_block - 1
    ) // records_per_block
    sentinel_extent = ROOT_EXTENT + root_blocks
    pdf = BASELINE.make_pdf()
    pdf_blocks = (len(pdf) + BLOCK_SIZE - 1) // BLOCK_SIZE
    total_blocks = sentinel_extent + pdf_blocks
    invalid_extent = total_blocks + 1
    records = [
        _directory_record(
            name=b"\0",
            extent=ROOT_EXTENT,
            size=root_blocks * BLOCK_SIZE,
            flags=0x02,
        ),
        _directory_record(
            name=b"\1",
            extent=ROOT_EXTENT,
            size=root_blocks * BLOCK_SIZE,
            flags=0x02,
        ),
    ]
    for ordinal in range(1, RECORD_COUNT + 1):
        records.append(
            _directory_record(
                name=f"F{ordinal - 1:06d};1".encode("ascii"),
                extent=(
                    sentinel_extent
                    if ordinal == sentinel_ordinal
                    else invalid_extent
                ),
                size=(
                    len(pdf)
                    if ordinal == sentinel_ordinal
                    else PLACEHOLDER_SIZE
                ),
                flags=0,
            )
        )

    directory = _pack_records(records)
    if len(directory) != root_blocks * BLOCK_SIZE:
        raise AssertionError("directory block accounting drifted")

    image = (
        bytes(16 * BLOCK_SIZE)
        + _primary_volume_descriptor(
            total_blocks=total_blocks,
            root_size=len(directory),
        )
        + _terminator()
        + directory
        + pdf
        + bytes(pdf_blocks * BLOCK_SIZE - len(pdf))
    )
    if len(image) != total_blocks * BLOCK_SIZE:
        raise AssertionError("ISO block accounting drifted")
    return image


def generate(output_dir: pathlib.Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    samples: list[dict[str, object]] = []
    for ordinal in SENTINEL_ORDINALS:
        name = f"sentinel-{ordinal:06d}.iso"
        data = make_fixture(ordinal)
        (output_dir / name).write_bytes(data)
        samples.append(
            {
                "name": name,
                "record_count": RECORD_COUNT,
                "sentinel_ordinal": ordinal,
                "sha256": hashlib.sha256(data).hexdigest(),
                "size": len(data),
            }
        )

    manifest: dict[str, object] = {
        "capability": "CAP-GAP-006",
        "generator": (
            "tools/corpus/"
            "generate_archive_iteration_boundary_fixture.py"
        ),
        "license": "project-generated; no third-party sample bytes",
        "record_count": RECORD_COUNT,
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=pathlib.Path)
    args = parser.parse_args()
    manifest = generate(args.output_dir.resolve())
    json.dump(manifest, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
