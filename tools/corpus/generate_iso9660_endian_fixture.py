#!/usr/bin/env python3
"""Generate deterministic ISO9660 dual-endian conflict fixtures."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import pathlib
import struct
import sys


GENERATOR = "tools/corpus/generate_iso9660_endian_fixture.py"
SOURCE_GENERATOR = "tools/corpus/generate_archive_format_fixture.py"
PVD = 16 * 2048
DIRECTORY = 19 * 2048
PVD_ROOT = PVD + 156
DOT_RECORD = DIRECTORY
DOTDOT_RECORD = DIRECTORY + 34
PAYLOAD_RECORD = DIRECTORY + 68


def _load_format_module():
    module_path = pathlib.Path(__file__).with_name(
        "generate_archive_format_fixture.py"
    )
    spec = importlib.util.spec_from_file_location(
        "_diec_iso9660_endian_format",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load archive format builders")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


FORMAT = _load_format_module()


@dataclass(frozen=True)
class Field:
    name: str
    offset: int
    width: int
    control: int
    alternate: int


FIELDS = (
    Field("pvd-volume-space-size", PVD + 80, 4, 21, 20),
    Field("pvd-volume-set-size", PVD + 120, 2, 1, 2),
    Field("pvd-volume-sequence-number", PVD + 124, 2, 1, 2),
    Field("pvd-logical-block-size", PVD + 128, 2, 2048, 1024),
    Field("pvd-path-table-size", PVD + 132, 4, 10, 9),
    Field("pvd-root-extent", PVD_ROOT + 2, 4, 19, 20),
    Field("pvd-root-size", PVD_ROOT + 10, 4, 2048, 2047),
    Field("pvd-root-volume-sequence", PVD_ROOT + 28, 2, 1, 2),
    Field("dot-extent", DOT_RECORD + 2, 4, 19, 20),
    Field("dot-size", DOT_RECORD + 10, 4, 2048, 2047),
    Field("dot-volume-sequence", DOT_RECORD + 28, 2, 1, 2),
    Field("dotdot-extent", DOTDOT_RECORD + 2, 4, 19, 20),
    Field("dotdot-size", DOTDOT_RECORD + 10, 4, 2048, 2047),
    Field("dotdot-volume-sequence", DOTDOT_RECORD + 28, 2, 1, 2),
    Field("payload-extent", PAYLOAD_RECORD + 2, 4, 20, 21),
    Field(
        "payload-size",
        PAYLOAD_RECORD + 10,
        4,
        len(FORMAT.PDF),
        len(FORMAT.PDF) + 1,
    ),
    Field("payload-volume-sequence", PAYLOAD_RECORD + 28, 2, 1, 2),
)
SIDES = ("little", "big")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def control() -> bytes:
    return FORMAT.make_iso9660_stored(
        FORMAT.PAYLOAD_NAME,
        FORMAT.PDF,
    )


def read_side(data: bytes, field: Field, side: str) -> int:
    if side == "little":
        offset = field.offset
        byteorder = "little"
    elif side == "big":
        offset = field.offset + field.width
        byteorder = "big"
    else:
        raise ValueError(f"unknown side: {side}")
    return int.from_bytes(
        data[offset : offset + field.width],
        byteorder,
    )


def mutate(base: bytes, field: Field, side: str) -> bytes:
    data = bytearray(base)
    if read_side(data, field, "little") != field.control:
        raise RuntimeError(f"little control changed: {field.name}")
    if read_side(data, field, "big") != field.control:
        raise RuntimeError(f"big control changed: {field.name}")
    if side == "little":
        offset = field.offset
        encoding = "<"
    elif side == "big":
        offset = field.offset + field.width
        encoding = ">"
    else:
        raise ValueError(f"unknown side: {side}")
    format_code = "H" if field.width == 2 else "I"
    data[offset : offset + field.width] = struct.pack(
        encoding + format_code,
        field.alternate,
    )
    output = bytes(data)
    if read_side(output, field, side) != field.alternate:
        raise RuntimeError(f"mutation failed: {field.name}/{side}")
    other_side = "big" if side == "little" else "little"
    if read_side(output, field, other_side) != field.control:
        raise RuntimeError(f"opposite side changed: {field.name}/{side}")
    return output


def sample_record(
    *,
    base: bytes,
    output: bytes,
    name: str,
    field: Field | None,
    side: str | None,
) -> dict[str, object]:
    changed_offsets = [
        index
        for index, (before, after) in enumerate(
            zip(base, output, strict=True)
        )
        if before != after
    ]
    if (field is None) != (not changed_offsets):
        raise RuntimeError(f"unexpected changed bytes: {name}")
    return {
        "alternate_value": (
            field.alternate if field is not None else None
        ),
        "changed_byte_count": len(changed_offsets),
        "changed_offset_max": (
            max(changed_offsets) if changed_offsets else None
        ),
        "changed_offset_min": (
            min(changed_offsets) if changed_offsets else None
        ),
        "control_sha256": sha256(base),
        "control_value": field.control if field is not None else None,
        "field": field.name if field is not None else "control",
        "field_offset": field.offset if field is not None else None,
        "field_width": field.width if field is not None else None,
        "mutated_side": side,
        "name": name,
        "purpose": (
            "ISO9660 valid dual-endian control"
            if field is None
            else (
                f"ISO9660 {field.name} {side}-endian alternate "
                "with opposite side left at control"
            )
        ),
        "sha256": sha256(output),
        "size": len(output),
    }


def generate(output_dir: pathlib.Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_path = pathlib.Path(__file__).with_name(
        "generate_archive_format_fixture.py"
    )
    base = control()
    samples = []

    control_name = "iso9660-control.iso"
    (output_dir / control_name).write_bytes(base)
    samples.append(
        sample_record(
            base=base,
            output=base,
            name=control_name,
            field=None,
            side=None,
        )
    )
    for field in FIELDS:
        for side in SIDES:
            output = mutate(base, field, side)
            name = f"iso9660-{field.name}-{side}-alternate.iso"
            (output_dir / name).write_bytes(output)
            samples.append(
                sample_record(
                    base=base,
                    output=output,
                    name=name,
                    field=field,
                    side=side,
                )
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
