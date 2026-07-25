#!/usr/bin/env python3
"""Generate benign deterministic fixtures for the Nintendo certified rule."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import struct
import sys
from collections.abc import Callable


TYPE_NAMES = {
    2: "revoke-list",
    3: "package",
    4: "security-policy-profile",
    5: "diff",
    6: "param-sfo",
}


def make_certified_file(
    byte_order: str,
    certified_type: int,
    *,
    elf_header: bool = False,
) -> bytes:
    """Build only fields read by the fixed upstream detection rule."""
    if byte_order not in {"big", "little"}:
        raise ValueError(f"unsupported byte order: {byte_order}")
    if certified_type not in {1, *TYPE_NAMES}:
        raise ValueError(f"unsupported certified type: {certified_type}")
    if elf_header and certified_type != 1:
        raise ValueError("ELF header is only meaningful for type 1")

    endian = ">" if byte_order == "big" else "<"
    size = 0x200 if certified_type == 1 else 0x80
    data = bytearray(size)
    data[0:4] = b"SCE\0"
    if byte_order == "big":
        data[4:8] = b"\0\0\0\2"
        payload_start = 0x20
    else:
        data[4:8] = b"\3\0\0\0"
        payload_start = 0x30

    struct.pack_into(f"{endian}H", data, 8, 0x8000)
    struct.pack_into(f"{endian}H", data, 0xA, certified_type)
    struct.pack_into(f"{endian}I", data, 0xC, 0)
    struct.pack_into(f"{endian}Q", data, 0x10, payload_start)
    struct.pack_into(f"{endian}Q", data, 0x18, payload_start)

    if certified_type == 1:
        struct.pack_into(
            f"{endian}Q",
            data,
            payload_start,
            3 if byte_order == "big" else 4,
        )
        program_id_header = 0x80
        elf_header_offset = program_id_header + 0x20
        program_header = elf_header_offset + 0x40
        section_header = 0x140
        for offset, value in (
            (payload_start + 8, program_id_header),
            (payload_start + 0x10, elf_header_offset),
            (payload_start + 0x18, program_header),
            (payload_start + 0x20, section_header),
        ):
            struct.pack_into(f"{endian}Q", data, offset, value)
        if elf_header:
            data[elf_header_offset : elf_header_offset + 7] = (
                b"\x7fELF\x00\x00\x01"
            )

    return bytes(data)


GENERATORS: tuple[tuple[str, str, Callable[[], bytes]], ...] = (
    (
        "ps3-type-1-elf.self",
        "PS3 certified type 1 with ELF header",
        lambda: make_certified_file("big", 1, elf_header=True),
    ),
    (
        "ps3-type-1-headerless.self",
        "PS3 certified type 1 without ELF header",
        lambda: make_certified_file("big", 1),
    ),
    *tuple(
        (
            f"ps3-type-{type_id}-{name}.self",
            f"PS3 certified type {type_id}",
            lambda type_id=type_id: make_certified_file("big", type_id),
        )
        for type_id, name in TYPE_NAMES.items()
    ),
    (
        "vita-type-1-elf.self",
        "PS Vita certified type 1 with ELF header",
        lambda: make_certified_file("little", 1, elf_header=True),
    ),
    (
        "vita-type-1-headerless.self",
        "PS Vita certified type 1 without ELF header",
        lambda: make_certified_file("little", 1),
    ),
    *tuple(
        (
            f"vita-type-{type_id}-{name}.self",
            f"PS Vita certified type {type_id}",
            lambda type_id=type_id: make_certified_file("little", type_id),
        )
        for type_id, name in TYPE_NAMES.items()
    ),
)


def generate(output_dir: pathlib.Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    samples = []
    for name, intended_format, factory in GENERATORS:
        data = factory()
        (output_dir / name).write_bytes(data)
        samples.append(
            {
                "name": name,
                "intended_format": intended_format,
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    manifest: dict[str, object] = {
        "schema_version": 1,
        "generator": (
            "tools/corpus/generate_nintendo_certified_corpus.py"
        ),
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
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir", type=pathlib.Path)
    args = parser.parse_args()
    manifest = generate(args.output_dir.resolve())
    json.dump(manifest, fp=sys.stdout, indent=2, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
