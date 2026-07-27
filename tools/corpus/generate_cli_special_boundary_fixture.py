#!/usr/bin/env python3
"""Generate benign entropy/struct boundary inputs for the pinned CLI."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
from typing import Any


SCHEMA_VERSION = 1
GENERATOR = "tools/corpus/generate_cli_special_boundary_fixture.py"
BASELINE_GENERATOR = "tools/corpus/generate_baseline_corpus.py"


def load_baseline_generator() -> Any:
    path = pathlib.Path(__file__).with_name(
        "generate_baseline_corpus.py"
    )
    spec = importlib.util.spec_from_file_location(
        "special_boundary_baseline_generator",
        path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load baseline corpus generator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def distribution(double_symbols: int, single_symbols: int) -> bytes:
    if (
        double_symbols < 0
        or single_symbols < 0
        or double_symbols + single_symbols > 256
    ):
        raise ValueError("invalid symbol distribution")
    values = bytearray()
    for value in range(double_symbols):
        values.extend((value, value))
    values.extend(
        range(double_symbols, double_symbols + single_symbols)
    )
    if len(values) != 128:
        raise ValueError("boundary distribution must contain 128 bytes")
    return bytes(values)


def build_fixture() -> tuple[dict[str, Any], dict[str, bytes]]:
    entropy_samples = (
        (
            "entropy-below-6_5.bin",
            distribution(33, 62),
            "not packed",
            6.484375,
        ),
        (
            "entropy-exact-6_5.bin",
            distribution(32, 64),
            "not packed",
            6.5,
        ),
        (
            "entropy-above-6_5.bin",
            distribution(31, 66),
            "packed",
            6.515625,
        ),
    )
    baseline = load_baseline_generator()
    format_samples = (
        ("minimal-pe32.exe", "PE32", baseline.make_pe32()),
        ("minimal-elf64.elf", "ELF64", baseline.make_elf64()),
        ("minimal-macho64.macho", "Mach-O 64", baseline.make_macho64()),
        ("minimal.dex", "DEX", baseline.make_dex()),
    )
    files = {
        name: data for name, data, _, _ in entropy_samples
    }
    files.update(
        {name: data for name, _, data in format_samples}
    )
    entries = [
        {
            "name": name,
            "size": len(data),
            "sha256": sha256(data),
            "source": "project-generated",
            "purpose": (
                "exercise floating entropy around the >= 6.5 "
                "packed boundary"
            ),
            "theoretical_entropy": expected_entropy,
            "expected_status": expected_status,
            "double_frequency_symbol_count": double_count,
            "single_frequency_symbol_count": single_count,
        }
        for (
            name,
            data,
            expected_status,
            expected_entropy,
        ), (
            double_count,
            single_count,
        ) in zip(
            entropy_samples,
            ((33, 62), (32, 64), (31, 66)),
        )
    ]
    entries.extend(
        {
            "name": name,
            "size": len(data),
            "sha256": sha256(data),
            "source": "project-generated",
            "purpose": "exercise format-specific struct method dispatch",
            "intended_format": intended_format,
        }
        for name, intended_format, data in format_samples
    )
    baseline_path = pathlib.Path(__file__).with_name(
        "generate_baseline_corpus.py"
    )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generator": GENERATOR,
        "license": "project-generated; no third-party sample bytes",
        "threshold": {
            "value": 6.5,
            "comparison": ">=",
        },
        "dependencies": [
            {
                "path": BASELINE_GENERATOR,
                "sha256": sha256(baseline_path.read_bytes()),
                "role": "safe deterministic format constructors",
            }
        ],
        "entries": entries,
    }
    return manifest, files


def serialize(document: dict[str, Any]) -> bytes:
    return (
        json.dumps(document, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def write_fixture(output_dir: pathlib.Path) -> dict[str, Any]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("output directory must be absent or empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest, files = build_fixture()
    for name, data in files.items():
        (output_dir / name).write_bytes(data)
    (output_dir / "manifest.json").write_bytes(serialize(manifest))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir", type=pathlib.Path)
    args = parser.parse_args()
    manifest = write_fixture(args.output_dir.resolve())
    print(serialize(manifest).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
