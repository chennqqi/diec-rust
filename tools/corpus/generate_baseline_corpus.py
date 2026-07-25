#!/usr/bin/env python3
"""Generate small, benign, deterministic files for upstream differential tests."""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import pathlib
import struct
import sys
import zlib
from collections.abc import Callable


PAYLOAD = b"diec-rust deterministic corpus\n"


def _stored_deflate(data: bytes) -> bytes:
    if len(data) > 0xFFFF:
        raise ValueError("stored DEFLATE helper only supports one 16-bit block")
    length = len(data)
    return b"\x01" + struct.pack("<HH", length, length ^ 0xFFFF) + data


def _zlib_stored(data: bytes) -> bytes:
    return b"\x78\x01" + _stored_deflate(data) + struct.pack(
        ">I", zlib.adler32(data)
    )


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", binascii.crc32(kind + data))
    )


def make_png() -> bytes:
    scanline = b"\x00\xff\x00\x00"
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(
            b"IHDR",
            struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0),
        )
        + _png_chunk(b"IDAT", _zlib_stored(scanline))
        + _png_chunk(b"IEND", b"")
    )


def make_bmp() -> bytes:
    pixel_data = b"\x00\x00\xff\x00"
    file_size = 14 + 40 + len(pixel_data)
    return (
        b"BM"
        + struct.pack("<IHHI", file_size, 0, 0, 54)
        + struct.pack(
            "<IiiHHIIiiII",
            40,
            1,
            1,
            1,
            24,
            0,
            len(pixel_data),
            2835,
            2835,
            0,
            0,
        )
        + pixel_data
    )


def make_pdf() -> bytes:
    objects = (
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 1 1] >>\nendobj\n",
    )
    document = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for item in objects:
        offsets.append(len(document))
        document.extend(item)
    xref_offset = len(document)
    document.extend(b"xref\n0 4\n0000000000 65535 f \n")
    for offset in offsets:
        document.extend(f"{offset:010d} 00000 n \n".encode())
    document.extend(
        b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n"
        + str(xref_offset).encode()
        + b"\n%%EOF\n"
    )
    return bytes(document)


def make_elf64() -> bytes:
    ident = b"\x7fELF" + bytes((2, 1, 1, 0, 0)) + bytes(7)
    return ident + struct.pack(
        "<HHIQQQIHHHHHH",
        3,
        62,
        1,
        0,
        0,
        0,
        0,
        64,
        0,
        0,
        0,
        0,
        0,
    )


def make_pe32() -> bytes:
    image = bytearray(512)
    image[0:2] = b"MZ"
    struct.pack_into("<I", image, 0x3C, 0x80)
    image[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", image, 0x84, 0x14C, 0, 0, 0, 0, 224, 0x0102)
    optional = 0x98
    struct.pack_into("<H", image, optional, 0x10B)
    struct.pack_into("<I", image, optional + 28, 0x400000)
    struct.pack_into("<II", image, optional + 32, 0x1000, 0x200)
    struct.pack_into("<II", image, optional + 56, 0x1000, 0x200)
    struct.pack_into("<H", image, optional + 68, 3)
    struct.pack_into("<I", image, optional + 92, 16)
    return bytes(image)


def make_macho64() -> bytes:
    header = struct.pack(
        "<IiiIIIII",
        0xFEEDFACF,
        0x01000007,
        3,
        2,
        1,
        72,
        0,
        0,
    )
    segment = struct.pack(
        "<II16sQQQQiiII",
        0x19,
        72,
        b"__TEXT" + bytes(10),
        0,
        0,
        0,
        0,
        7,
        5,
        0,
        0,
    )
    return header + segment


def make_dex() -> bytes:
    header = bytearray(0x70)
    header[0:8] = b"dex\n035\0"
    struct.pack_into("<I", header, 32, len(header))
    struct.pack_into("<I", header, 36, 0x70)
    struct.pack_into("<I", header, 40, 0x12345678)
    header[12:32] = hashlib.sha1(header[32:]).digest()
    struct.pack_into("<I", header, 8, zlib.adler32(header[12:]))
    return bytes(header)


def make_java_class() -> bytes:
    class_name = b"Minimal"
    super_name = b"java/lang/Object"
    constant_pool = (
        b"\x01"
        + struct.pack(">H", len(class_name))
        + class_name
        + b"\x07\x00\x01"
        + b"\x01"
        + struct.pack(">H", len(super_name))
        + super_name
        + b"\x07\x00\x03"
    )
    return (
        struct.pack(">IHHH", 0xCAFEBABE, 0, 52, 5)
        + constant_pool
        + struct.pack(">HHHHHHH", 0x21, 2, 4, 0, 0, 0, 0)
    )


def make_cfbf() -> bytes:
    header = bytearray(512)
    header[0:8] = bytes.fromhex("D0CF11E0A1B11AE1")
    struct.pack_into("<HHHHH", header, 24, 0x003E, 3, 0xFFFE, 9, 6)
    struct.pack_into("<I", header, 40, 0)
    struct.pack_into("<I", header, 44, 0)
    struct.pack_into("<I", header, 48, 0xFFFFFFFE)
    struct.pack_into("<I", header, 56, 4096)
    struct.pack_into("<I", header, 60, 0xFFFFFFFE)
    struct.pack_into("<I", header, 64, 0)
    struct.pack_into("<I", header, 68, 0xFFFFFFFE)
    struct.pack_into("<I", header, 72, 0)
    for offset in range(76, 512, 4):
        struct.pack_into("<I", header, offset, 0xFFFFFFFF)
    return bytes(header)


def make_wav() -> bytes:
    samples = b"\x80"
    fmt = struct.pack("<HHIIHH", 1, 1, 8000, 8000, 1, 8)
    body = b"WAVEfmt " + struct.pack("<I", len(fmt)) + fmt
    body += b"data" + struct.pack("<I", len(samples)) + samples + b"\x00"
    return b"RIFF" + struct.pack("<I", len(body)) + body


def make_gzip() -> bytes:
    return (
        b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\xff"
        + _stored_deflate(PAYLOAD)
        + struct.pack("<II", binascii.crc32(PAYLOAD), len(PAYLOAD))
    )


def make_zip() -> bytes:
    name = b"payload.txt"
    crc = binascii.crc32(PAYLOAD)
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
            len(PAYLOAD),
            len(PAYLOAD),
            len(name),
            0,
        )
        + name
        + PAYLOAD
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
            len(PAYLOAD),
            len(PAYLOAD),
            len(name),
            0,
            0,
            0,
            0,
            0,
            0,
        )
        + name
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


def _tar_octal(value: int, width: int) -> bytes:
    return f"{value:0{width - 1}o}\0".encode()


def make_tar() -> bytes:
    header = bytearray(512)
    header[0:11] = b"payload.txt"
    header[100:108] = _tar_octal(0o644, 8)
    header[108:116] = _tar_octal(0, 8)
    header[116:124] = _tar_octal(0, 8)
    header[124:136] = _tar_octal(len(PAYLOAD), 12)
    header[136:148] = _tar_octal(0, 12)
    header[148:156] = b"        "
    header[156:157] = b"0"
    header[257:263] = b"ustar\0"
    header[263:265] = b"00"
    checksum = sum(header)
    header[148:156] = f"{checksum:06o}\0 ".encode()
    padding = bytes((-len(PAYLOAD)) % 512)
    return bytes(header) + PAYLOAD + padding + bytes(1024)


GENERATORS: tuple[tuple[str, str, Callable[[], bytes]], ...] = (
    ("empty.bin", "empty", lambda: b""),
    ("plain.txt", "text", lambda: PAYLOAD),
    ("minimal.elf", "ELF64", make_elf64),
    ("minimal.exe", "PE32", make_pe32),
    ("minimal.macho", "Mach-O 64", make_macho64),
    ("minimal.dex", "DEX", make_dex),
    ("Minimal.class", "Java Class", make_java_class),
    ("pixel.png", "PNG", make_png),
    ("pixel.bmp", "BMP", make_bmp),
    ("minimal.pdf", "PDF", make_pdf),
    ("payload.zip", "ZIP with text member", make_zip),
    ("payload.tar", "TAR with text member", make_tar),
    ("payload.txt.gz", "GZIP with text member", make_gzip),
    ("minimal.cfbf", "CFBF", make_cfbf),
    ("tone.wav", "WAV PCM", make_wav),
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
        "generator": "tools/corpus/generate_baseline_corpus.py",
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
