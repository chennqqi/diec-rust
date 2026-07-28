#!/usr/bin/env python3
"""Generate benign, project-owned RAR5 Store and solid fixtures."""

from __future__ import annotations

import argparse
import binascii
import hashlib
import importlib.util
import json
import pathlib
import sys
from collections.abc import Iterable


GENERATOR = "tools/corpus/generate_rar5_store_fixture.py"
RAR5_SIGNATURE = b"Rar!\x1a\x07\x01\x00"
RAR5_HEADER_MAIN = 1
RAR5_HEADER_FILE = 2
RAR5_HEADER_END = 5
RAR5_COMMON_DATA = 0x0002
RAR5_MAIN_SOLID = 0x0004
RAR5_FILE_CRC32 = 0x0004
RAR5_COMP_SOLID = 1 << 6
RAR5_HOST_UNIX = 1


def _load_baseline_module():
    module_path = pathlib.Path(__file__).with_name(
        "generate_baseline_corpus.py"
    )
    spec = importlib.util.spec_from_file_location(
        "_diec_rar5_store_baseline",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load baseline corpus builders")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


PDF = _load_baseline_module().make_pdf()


def encode_uleb128(value: int) -> bytes:
    if value < 0:
        raise ValueError("ULEB128 value must be non-negative")
    result = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            byte |= 0x80
        result.append(byte)
        if not value:
            return bytes(result)


def rar5_header(
    header_type: int,
    body: bytes,
    *,
    common_flags: int = 0,
    data: bytes = b"",
) -> bytes:
    flags = common_flags | (RAR5_COMMON_DATA if data else 0)
    fields = (
        encode_uleb128(header_type)
        + encode_uleb128(flags)
        + (encode_uleb128(len(data)) if data else b"")
        + body
    )
    protected = encode_uleb128(len(fields)) + fields
    crc32 = binascii.crc32(protected) & 0xFFFFFFFF
    return crc32.to_bytes(4, "little") + protected + data


def rar5_main_header(*, solid: bool) -> bytes:
    archive_flags = RAR5_MAIN_SOLID if solid else 0
    return rar5_header(
        RAR5_HEADER_MAIN,
        encode_uleb128(archive_flags),
    )


def rar5_file_header(
    name: str,
    payload: bytes,
    *,
    solid: bool,
) -> bytes:
    encoded_name = name.encode("utf-8")
    if not encoded_name or b"\0" in encoded_name:
        raise ValueError("RAR5 member name must be non-empty UTF-8")
    compression_info = RAR5_COMP_SOLID if solid else 0
    body = (
        encode_uleb128(RAR5_FILE_CRC32)
        + encode_uleb128(len(payload))
        + encode_uleb128(0o100644)
        + (binascii.crc32(payload) & 0xFFFFFFFF).to_bytes(4, "little")
        + encode_uleb128(compression_info)
        + encode_uleb128(RAR5_HOST_UNIX)
        + encode_uleb128(len(encoded_name))
        + encoded_name
    )
    return rar5_header(RAR5_HEADER_FILE, body, data=payload)


def rar5_end_header() -> bytes:
    return rar5_header(RAR5_HEADER_END, encode_uleb128(0))


def make_rar5_store(
    members: Iterable[tuple[str, bytes, bool]],
    *,
    solid: bool,
) -> bytes:
    materialized = list(members)
    if not materialized:
        raise ValueError("RAR5 fixture requires at least one member")
    if any(member_solid for _, _, member_solid in materialized) and not solid:
        raise ValueError("solid member requires solid archive flag")
    return (
        RAR5_SIGNATURE
        + rar5_main_header(solid=solid)
        + b"".join(
            rar5_file_header(name, payload, solid=member_solid)
            for name, payload, member_solid in materialized
        )
        + rar5_end_header()
    )


FIXTURES = (
    {
        "name": "rar5-store-single.rar",
        "purpose": "RAR5 Store archive containing one canonical PDF",
        "solid": False,
        "members": (("payload.pdf", PDF, False),),
    },
    {
        "name": "rar5-store-solid-pair.rar",
        "purpose": (
            "RAR5 solid archive containing a boundary PDF and one "
            "solid-following PDF"
        ),
        "solid": True,
        "members": (
            ("first.pdf", PDF, False),
            ("second.pdf", PDF, True),
        ),
    },
)


def generate(output_dir: pathlib.Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    samples = []
    for fixture in FIXTURES:
        members = fixture["members"]
        data = make_rar5_store(
            members,
            solid=bool(fixture["solid"]),
        )
        name = str(fixture["name"])
        (output_dir / name).write_bytes(data)
        samples.append(
            {
                "archive_format": "RAR5",
                "compression_method": "Store",
                "expected_members": [
                    {
                        "name": member_name,
                        "sha256": hashlib.sha256(payload).hexdigest(),
                        "size": len(payload),
                        "solid": member_solid,
                    }
                    for member_name, payload, member_solid in members
                ],
                "name": name,
                "purpose": fixture["purpose"],
                "sha256": hashlib.sha256(data).hexdigest(),
                "size": len(data),
                "solid": fixture["solid"],
            }
        )
    manifest: dict[str, object] = {
        "schema_version": 1,
        "generator": GENERATOR,
        "license": "project-generated",
        "format_reference": {
            "scope": (
                "RAR5 container headers and Store data only; no "
                "proprietary compression algorithm and no "
                "third-party binary"
            ),
            "source": "https://www.rarlab.com/technote.htm",
        },
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
    parser.add_argument("--manifest", type=pathlib.Path)
    args = parser.parse_args()
    manifest = generate(args.output_dir)
    if args.manifest:
        args.manifest.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
