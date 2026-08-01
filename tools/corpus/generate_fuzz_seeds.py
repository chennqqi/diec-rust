#!/usr/bin/env python3
"""Generate seed corpora for fuzz targets.

libFuzzer starts from seed inputs to guide coverage. This script
creates seed directories for each fuzz target using the project's
baseline and edge corpora.

Seeds are placed in:
  fuzz/corpus/<target_name>/

Each seed is a small file that exercises a distinct code path.
"""

import os
import shutil
import sys

WORKSPACE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CORPUS_DIR = os.path.join(WORKSPACE, "corpus")
EDGE_DIR = os.path.join(CORPUS_DIR, "edge")
FUZZ_CORPUS = os.path.join(WORKSPACE, "fuzz", "corpus")

# Map fuzz target names to seed directories.
TARGETS = {
    "fuzz_byte_source": "byte_source",
    "fuzz_byte_view_subview": "byte_view",
    "fuzz_format_probe": "format_probe",
    "fuzz_scan_engine": "scan_engine",
    "fuzz_output_render": "output_render",
    "fuzz_scan_ffi": "scan_ffi",
}

# Seeds for each target: (filename, bytes)
BASELINE_SEEDS = {
    "empty.bin": b"",
    "single_byte": b"\x42",
    "two_bytes": b"\x42\x43",
    "zeros_16": b"\x00" * 16,
    "ff_16": b"\xff" * 16,
    "ascii_text": b"Hello, World!\n",
    "random_64": bytes(range(64)),
}

FORMAT_SEEDS = {
    # ELF64 magic + minimal header
    "elf64_magic": b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 56,
    # ELF32 magic + minimal header
    "elf32_magic": b"\x7fELF\x01\x01\x01\x00" + b"\x00" * 44,
    # PE MZ header
    "pe_mz": b"MZ" + b"\x00" * 62,
    # Mach-O 64 magic
    "macho64_magic": b"\xcf\xfa\xed\xfe" + b"\x00" * 28,
    # Mach-O 32 magic
    "macho32_magic": b"\xfe\xed\xfa\xce" + b"\x00" * 28,
    # Mach-O FAT magic
    "macho_fat": b"\xca\xfe\xba\xbe" + b"\x00" * 28,
    # Zip local file header
    "zip_lfh": b"PK\x03\x04\x14\x00\x00\x00" + b"\x00" * 22,
    # Zip EOCD
    "zip_eocd": b"PK\x05\x06" + b"\x00" * 18,
    # PDF header
    "pdf_header": b"%PDF-1.4\n",
    # PNG signature
    "png_sig": b"\x89PNG\r\n\x1a\n",
    # JPEG SOI
    "jpeg_soi": b"\xff\xd8\xff\xe0" + b"\x00" * 20,
    # Java class magic
    "class_magic": b"\xca\xfe\xba\xbe" + b"\x00" * 28,
    # DEX magic
    "dex_magic": b"dex\n\x00\x00\x00" + b"\x00" * 100,
    # BMP header
    "bmp_header": b"BM" + b"\x00" * 26,
    # WAV header
    "wav_header": b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * 100,
    # GZIP header
    "gzip_header": b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\x03",
    # tar ustar header
    "tar_ustar": b"\x00" * 257 + b"ustar" + b"\x00" * 250,
}

# Output render seeds: structured data that looks like ScanResult fields.
OUTPUT_SEEDS = {
    "empty_result": b"\x00",
    "single_detection": b"\x04\x04testtype",
    "many_detections": (b"\x04\x04type\x04\x04name") * 10,
    "long_name": b"\x00\x10" + b"A" * 16 + b"\x04\x04type",
    "non_utf8": b"\x04\xff\xff\xff\xff\x04\x04type",
}


def write_seeds(target_dir: str, seeds: dict) -> int:
    """Write seeds to the target directory. Returns count written."""
    os.makedirs(target_dir, exist_ok=True)
    count = 0
    for name, data in seeds.items():
        path = os.path.join(target_dir, name)
        with open(path, "wb") as f:
            f.write(data)
        count += 1
    return count


def copy_corpus_files(target_dir: str, source_dir: str, max_files: int = 20) -> int:
    """Copy corpus files from source_dir to target_dir."""
    if not os.path.isdir(source_dir):
        return 0
    os.makedirs(target_dir, exist_ok=True)
    count = 0
    for entry in sorted(os.listdir(source_dir))[:max_files]:
        src = os.path.join(source_dir, entry)
        dst = os.path.join(target_dir, entry)
        if os.path.isfile(src) and not os.path.exists(dst):
            shutil.copy2(src, dst)
            count += 1
    return count


def main() -> None:
    total = 0

    # Byte source / view seeds: basic byte patterns
    total += write_seeds(
        os.path.join(FUZZ_CORPUS, TARGETS["fuzz_byte_source"]),
        BASELINE_SEEDS,
    )
    total += write_seeds(
        os.path.join(FUZZ_CORPUS, TARGETS["fuzz_byte_view_subview"]),
        BASELINE_SEEDS,
    )

    # Format probe seeds: magic bytes for each format
    total += write_seeds(
        os.path.join(FUZZ_CORPUS, TARGETS["fuzz_format_probe"]),
        FORMAT_SEEDS,
    )
    # Also copy baseline corpus files
    total += copy_corpus_files(
        os.path.join(FUZZ_CORPUS, TARGETS["fuzz_format_probe"]),
        CORPUS_DIR,
    )

    # Scan engine seeds: same as format probe (scan needs format data)
    total += write_seeds(
        os.path.join(FUZZ_CORPUS, TARGETS["fuzz_scan_engine"]),
        FORMAT_SEEDS,
    )
    total += copy_corpus_files(
        os.path.join(FUZZ_CORPUS, TARGETS["fuzz_scan_engine"]),
        CORPUS_DIR,
    )
    # Add edge cases
    total += copy_corpus_files(
        os.path.join(FUZZ_CORPUS, TARGETS["fuzz_scan_engine"]),
        EDGE_DIR,
    )

    # Output render seeds: structured data
    total += write_seeds(
        os.path.join(FUZZ_CORPUS, TARGETS["fuzz_output_render"]),
        OUTPUT_SEEDS,
    )

    # FFI scan seeds: same as scan engine
    total += write_seeds(
        os.path.join(FUZZ_CORPUS, TARGETS["fuzz_scan_ffi"]),
        FORMAT_SEEDS,
    )
    total += copy_corpus_files(
        os.path.join(FUZZ_CORPUS, TARGETS["fuzz_scan_ffi"]),
        CORPUS_DIR,
    )
    total += copy_corpus_files(
        os.path.join(FUZZ_CORPUS, TARGETS["fuzz_scan_ffi"]),
        EDGE_DIR,
    )

    print(f"Generated {total} seed files across {len(TARGETS)} targets")
    for target, subdir in TARGETS.items():
        tdir = os.path.join(FUZZ_CORPUS, subdir)
        if os.path.isdir(tdir):
            n = len(os.listdir(tdir))
            print(f"  {target}: {n} seeds")


if __name__ == "__main__":
    main()
