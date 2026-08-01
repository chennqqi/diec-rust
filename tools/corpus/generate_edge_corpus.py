#!/usr/bin/env python3
"""Generate edge-case corpus samples for differential testing.

These samples test boundary conditions:
- Truncated headers (partial magic bytes)
- Malformed structures (valid magic, invalid fields)
- Oversized length fields
- Empty containers
- Mixed magic bytes

All samples are project-generated (no third-party bytes).
"""

import hashlib
import json
import os
import struct
import sys

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "corpus", "edge")


def write_sample(name: str, data: bytes) -> dict:
    """Write a sample file and return its manifest entry."""
    path = os.path.join(OUTPUT_DIR, name)
    with open(path, "wb") as f:
        f.write(data)
    sha256 = hashlib.sha256(data).hexdigest()
    return {
        "name": name,
        "size": len(data),
        "sha256": sha256,
        "category": "edge",
    }


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    samples = []

    # 1. Truncated ELF (only first 4 bytes of magic)
    samples.append(write_sample("truncated-elf-4bytes.bin", b"\x7fELF"))

    # 2. Truncated PE (only MZ, no PE sig)
    samples.append(write_sample("truncated-pe-mz-only.bin", b"MZ" + b"\x00" * 62))

    # 3. Truncated Mach-O (only magic, no header)
    samples.append(write_sample("truncated-macho-magic.bin",
                                struct.pack("<I", 0xFEEDFACF)))

    # 4. Truncated Zip (only local file header signature)
    samples.append(write_sample("truncated-zip-sig.bin", b"PK\x03\x04"))

    # 5. Malformed ELF (valid magic, invalid class)
    malformed_elf = bytearray(b"\x7fELF")
    malformed_elf.append(99)  # Invalid EI_CLASS (not 1 or 2)
    malformed_elf.extend(b"\x00" * 60)
    samples.append(write_sample("malformed-elf-bad-class.bin", bytes(malformed_elf)))

    # 6. Malformed PE (MZ + invalid e_lfanew pointing beyond file)
    malformed_pe = bytearray(256)
    malformed_pe[0:2] = b"MZ"
    struct.pack_into("<I", malformed_pe, 0x3C, 0x10000)  # e_lfanew way too large
    samples.append(write_sample("malformed-pe-bad-lfanew.bin", bytes(malformed_pe)))

    # 7. Oversized length field in Zip local header
    oversized_zip = bytearray(b"PK\x03\x04")
    oversized_zip.extend(b"\x14\x00")  # version
    oversized_zip.extend(b"\x00\x00")  # flags
    oversized_zip.extend(b"\x00\x00")  # compression
    oversized_zip.extend(b"\x00\x00")  # mod time
    oversized_zip.extend(b"\x00\x00")  # mod date
    oversized_zip.extend(struct.pack("<I", 0xFFFFFFFF))  # crc32
    oversized_zip.extend(struct.pack("<I", 0xFFFFFFFF))  # compressed size
    oversized_zip.extend(struct.pack("<I", 0xFFFFFFFF))  # uncompressed size
    oversized_zip.extend(b"\x00\x00")  # filename length
    oversized_zip.extend(b"\x00\x00")  # extra field length
    samples.append(write_sample("oversized-zip-fields.bin", bytes(oversized_zip)))

    # 8. Empty Zip (end of central directory only)
    empty_zip = b"PK\x05\x06" + b"\x00" * 18
    samples.append(write_sample("empty-zip-eocd.bin", empty_zip))

    # 9. PDF with only header (truncated)
    samples.append(write_sample("truncated-pdf-header.bin", b"%PDF-1.4\n"))

    # 10. PNG with only signature (truncated)
    samples.append(write_sample("truncated-png-sig.bin",
                                b"\x89PNG\r\n\x1a\n"))

    # 11. JPEG with only SOI marker
    samples.append(write_sample("truncated-jpeg-soi.bin", b"\xFF\xD8"))

    # 12. Java class with only magic
    samples.append(write_sample("truncated-class-magic.bin",
                                b"\xCA\xFE\xBA\xBE"))

    # 13. DEX with only magic
    samples.append(write_sample("truncated-dex-magic.bin",
                                b"dex\n"))

    # 14. Random bytes (no magic match expected)
    samples.append(write_sample("random-256.bin", bytes(range(256))))

    # 15. All zeros (256 bytes)
    samples.append(write_sample("zeros-256.bin", b"\x00" * 256))

    # 16. All 0xFF (256 bytes)
    samples.append(write_sample("ff-256.bin", b"\xFF" * 256))

    # 17. Single byte
    samples.append(write_sample("single-byte.bin", b"\x42"))

    # 18. Two bytes
    samples.append(write_sample("two-bytes.bin", b"\x42\x43"))

    # 19. Tar with only header (512 bytes, empty)
    tar_header = bytearray(512)
    tar_header[257:262] = b"ustar"
    samples.append(write_sample("empty-tar-header.bin", bytes(tar_header)))

    # 20. GZIP with only header
    gzip_header = b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\x03"
    samples.append(write_sample("truncated-gzip-header.bin", gzip_header))

    # Write manifest
    manifest = {
        "generator": "tools/corpus/generate_edge_corpus.py",
        "license": "project-generated; no third-party sample bytes",
        "category": "edge cases: truncated, malformed, oversized, empty",
        "samples": samples,
    }
    manifest_path = os.path.join(OUTPUT_DIR, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Generated {len(samples)} edge-case samples in {OUTPUT_DIR}")
    for s in samples:
        print(f"  {s['name']}: {s['size']} bytes")


if __name__ == "__main__":
    main()
