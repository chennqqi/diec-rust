#!/usr/bin/env python3
"""Generate deterministic public DOS/COM dispatch fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import struct
import sys
from collections.abc import Callable
from typing import Any


FORMATS_REPOSITORY = "https://github.com/horsicq/Formats.git"
FORMATS_COMMIT = "1151e7254fdee3c0294ff7095edbdd7bfccf8201"
XARCHIVE_REPOSITORY = "https://github.com/horsicq/XArchive.git"
XARCHIVE_COMMIT = "0fcd4e8d3e9933baac3b12246d82ac026557ffd0"
PUBLIC_FILETYPES = (
    "MSDOS",
    "NE",
    "LE",
    "LX",
    "DOS/16M",
    "DOS/4G",
    "COM",
)
DOS_HEADER_SIZE = 64
NEW_HEADER_OFFSET = 0x80
COM_MAX_SIZE = 0x10000 - 0x100


def _set_dos_header(
    image: bytearray,
    *,
    offset: int = 0,
    file_size: int,
    new_header_offset: int = 0,
) -> None:
    image[offset : offset + 2] = b"MZ"
    pages, remainder = divmod(file_size, 512)
    if remainder:
        pages += 1
    struct.pack_into("<H", image, offset + 2, remainder)
    struct.pack_into("<H", image, offset + 4, pages)
    struct.pack_into("<H", image, offset + 8, DOS_HEADER_SIZE // 16)
    struct.pack_into("<I", image, offset + 0x3C, new_header_offset)


def make_msdos() -> bytes:
    image = bytearray(0x80)
    _set_dos_header(image, file_size=len(image))
    image[DOS_HEADER_SIZE : DOS_HEADER_SIZE + 3] = b"\x90\xcd\x20"
    return bytes(image)


def _make_linear_executable(signature: bytes) -> bytes:
    image = bytearray(0x100)
    _set_dos_header(
        image,
        file_size=len(image),
        new_header_offset=NEW_HEADER_OFFSET,
    )
    image[NEW_HEADER_OFFSET : NEW_HEADER_OFFSET + len(signature)] = signature
    return bytes(image)


def make_ne() -> bytes:
    return _make_linear_executable(b"NE")


def make_le() -> bytes:
    return _make_linear_executable(b"LE\0\0")


def make_lx() -> bytes:
    return _make_linear_executable(b"LX\0\0")


def _make_dos16_chain(nested_signature: bytes) -> bytes:
    image = bytearray(0x500)
    loader_end = DOS_HEADER_SIZE
    nested_offset = 0x100
    _set_dos_header(image, file_size=loader_end)

    image[loader_end : loader_end + 2] = b"BW"
    # XMSDOS_DEF::dos16m_exe_header::next_header_pos is at +28.
    struct.pack_into("<I", image, loader_end + 28, nested_offset)

    _set_dos_header(
        image,
        offset=nested_offset,
        file_size=len(image) - nested_offset,
        new_header_offset=DOS_HEADER_SIZE,
    )
    signature_offset = nested_offset + DOS_HEADER_SIZE
    image[
        signature_offset : signature_offset + len(nested_signature)
    ] = nested_signature
    return bytes(image)


def make_dos16m() -> bytes:
    return _make_dos16_chain(b"NE")


def make_dos4g() -> bytes:
    return _make_dos16_chain(b"LE\0\0")


def make_com() -> bytes:
    return bytes.fromhex("eb0090")


def _msdos_near_magic() -> bytes:
    data = bytearray(make_msdos())
    data[:2] = b"NZ"
    return bytes(data)


def _linear_truncated(factory: Callable[[], bytes]) -> bytes:
    return factory()[:NEW_HEADER_OFFSET]


def _linear_near_magic(
    factory: Callable[[], bytes],
    signature: bytes,
) -> bytes:
    data = bytearray(factory())
    data[NEW_HEADER_OFFSET : NEW_HEADER_OFFSET + len(signature)] = signature
    return bytes(data)


def _dos_chain_truncated(factory: Callable[[], bytes]) -> bytes:
    return factory()[:1024]


def _dos16m_near_bw() -> bytes:
    data = bytearray(make_dos16m())
    data[DOS_HEADER_SIZE : DOS_HEADER_SIZE + 2] = b"BV"
    return bytes(data)


def _dos4g_near_nested_magic() -> bytes:
    data = bytearray(make_dos4g())
    data[0x140 : 0x144] = b"ME\0\0"
    return bytes(data)


def _com_max_size() -> bytes:
    data = bytearray(COM_MAX_SIZE)
    data[: len(make_com())] = make_com()
    return bytes(data)


def _com_oversized() -> bytes:
    return bytes(COM_MAX_SIZE + 1)


CaseFactory = tuple[
    str,
    str,
    str,
    Callable[[], bytes],
    tuple[str, ...],
    tuple[str, ...],
]


CASES: tuple[CaseFactory, ...] = (
    (
        "minimal-msdos.exe",
        "positive",
        "MSDOS",
        make_msdos,
        ("MSDOS",),
        ("NE", "LE", "LX", "DOS/16M", "DOS/4G", "COM"),
    ),
    (
        "msdos-near-magic.exe",
        "near_magic",
        "MSDOS",
        _msdos_near_magic,
        (),
        ("MSDOS",),
    ),
    (
        "minimal-ne.exe",
        "positive",
        "NE",
        make_ne,
        ("NE",),
        ("LE", "LX", "DOS/16M", "DOS/4G", "COM"),
    ),
    (
        "ne-truncated.exe",
        "truncated",
        "NE",
        lambda: _linear_truncated(make_ne),
        ("MSDOS",),
        ("NE",),
    ),
    (
        "ne-near-magic.exe",
        "near_magic",
        "NE",
        lambda: _linear_near_magic(make_ne, b"NO"),
        ("MSDOS",),
        ("NE",),
    ),
    (
        "minimal-le.exe",
        "positive",
        "LE",
        make_le,
        ("LE",),
        ("NE", "LX", "DOS/16M", "DOS/4G", "COM"),
    ),
    (
        "le-near-magic.exe",
        "near_magic",
        "LE",
        lambda: _linear_near_magic(make_le, b"ME\0\0"),
        ("MSDOS",),
        ("LE",),
    ),
    (
        "minimal-lx.exe",
        "positive",
        "LX",
        make_lx,
        ("LX",),
        ("NE", "LE", "DOS/16M", "DOS/4G", "COM"),
    ),
    (
        "lx-near-magic.exe",
        "near_magic",
        "LX",
        lambda: _linear_near_magic(make_lx, b"LY\0\0"),
        ("MSDOS",),
        ("LX",),
    ),
    (
        "minimal-dos16m.exe",
        "positive",
        "DOS/16M",
        make_dos16m,
        ("DOS/16M",),
        ("NE", "LE", "LX", "DOS/4G", "COM"),
    ),
    (
        "dos16m-truncated.exe",
        "truncated",
        "DOS/16M",
        lambda: _dos_chain_truncated(make_dos16m),
        ("MSDOS",),
        ("DOS/16M", "DOS/4G"),
    ),
    (
        "dos16m-near-bw.exe",
        "near_magic",
        "DOS/16M",
        _dos16m_near_bw,
        ("MSDOS",),
        ("DOS/16M", "DOS/4G"),
    ),
    (
        "minimal-dos4g.exe",
        "positive",
        "DOS/4G",
        make_dos4g,
        ("DOS/4G",),
        ("NE", "LE", "LX", "DOS/16M", "COM"),
    ),
    (
        "dos4g-truncated.exe",
        "truncated",
        "DOS/4G",
        lambda: _dos_chain_truncated(make_dos4g),
        ("MSDOS",),
        ("DOS/16M", "DOS/4G"),
    ),
    (
        "dos4g-near-nested-magic.exe",
        "adjacent_dispatch",
        "DOS/4G",
        _dos4g_near_nested_magic,
        ("DOS/16M",),
        ("DOS/4G",),
    ),
    (
        "minimal.com",
        "positive",
        "COM",
        make_com,
        ("COM",),
        ("MSDOS", "NE", "LE", "LX", "DOS/16M", "DOS/4G"),
    ),
    (
        "com-wrong-suffix.bin",
        "wrong_suffix",
        "COM",
        make_com,
        (),
        ("COM",),
    ),
    (
        "com-max-size.com",
        "boundary_positive",
        "COM",
        _com_max_size,
        ("COM",),
        (),
    ),
    (
        "com-oversized.com",
        "oversized",
        "COM",
        _com_oversized,
        (),
        ("COM",),
    ),
)


def generate(output_dir: pathlib.Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    samples = []
    for (
        name,
        case_kind,
        target,
        factory,
        present,
        absent,
    ) in CASES:
        data = factory()
        (output_dir / name).write_bytes(data)
        samples.append(
            {
                "name": name,
                "case_kind": case_kind,
                "target_filetype": target,
                "expected_dispatch": {
                    "present_filetypes": list(present),
                    "absent_filetypes": list(absent),
                },
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "generator": "tools/corpus/generate_dos_dispatch_corpus.py",
        "license": "project-generated; no third-party sample bytes",
        "capability": "CAP-DISPATCH-002",
        "public_filetypes": list(PUBLIC_FILETYPES),
        "excluded_member": {
            "filetype": "BW DOS16M",
            "reason": (
                "scanner branch has no public XFormats detector at the "
                "pinned commit"
            ),
            "evidence": (
                "docs/research/data/dos-dispatch-source-audit.json"
            ),
        },
        "source_identity": {
            "Formats": {
                "repository": FORMATS_REPOSITORY,
                "commit": FORMATS_COMMIT,
            },
            "XArchive": {
                "repository": XARCHIVE_REPOSITORY,
                "commit": XARCHIVE_COMMIT,
            },
            "validity_sources": [
                "Formats/exec/xcom.cpp",
                "Formats/exec/xcom_def.h",
                "Formats/exec/xmsdos.cpp",
                "Formats/exec/xmsdos_def.h",
                "Formats/exec/xne.cpp",
                "Formats/exec/xle.cpp",
                "Formats/xformats.cpp",
                "XArchive/xdos16.cpp",
            ],
        },
        "samples": samples,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=pathlib.Path)
    args = parser.parse_args()
    manifest = generate(args.output_dir.resolve())
    json.dump(
        manifest,
        fp=sys.stdout,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    )
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
