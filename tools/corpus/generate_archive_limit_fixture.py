#!/usr/bin/env python3
"""Generate deterministic fixtures for nested archive resource-limit research."""

from __future__ import annotations

import argparse
import binascii
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
        "_diec_archive_limit_baseline", module_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load baseline corpus builders")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BASELINE = _load_baseline_module()

DEPTHS = (1, 2, 4, 8, 12, 16)
EXPANDED_LEAF_SIZES = (1024, 65536, 262144, 1048576)
EXPANDED_DEPTH = 2


def make_stored_zip(member_name: str, payload: bytes) -> bytes:
    """Create a deterministic one-member ZIP without optional metadata."""
    encoded_name = member_name.encode("ascii")
    crc = binascii.crc32(payload)
    local = (
        struct.pack(
            "<IHHHHHIIIHH",
            0x04034B50,
            20,
            0,
            0,
            0,
            0,
            crc,
            len(payload),
            len(payload),
            len(encoded_name),
            0,
        )
        + encoded_name
        + payload
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
            0,
            crc,
            len(payload),
            len(payload),
            len(encoded_name),
            0,
            0,
            0,
            0,
            0,
            0,
        )
        + encoded_name
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


def make_leaf(size: int) -> bytes:
    """Pad the existing benign PDF after EOF to an exact byte size."""
    pdf = BASELINE.make_pdf()
    if size < len(pdf):
        raise ValueError(
            f"leaf size {size} is smaller than PDF size {len(pdf)}"
        )
    return pdf + bytes(size - len(pdf))


def make_nested_archive(depth: int, leaf_size: int) -> tuple[bytes, int]:
    """Return the outer ZIP and cumulative extracted member bytes."""
    if depth < 1:
        raise ValueError("archive depth must be positive")
    payload = make_leaf(leaf_size)
    cumulative_expanded_bytes = 0
    for level in range(depth, 0, -1):
        cumulative_expanded_bytes += len(payload)
        member_name = (
            "leaf.pdf"
            if level == depth
            else f"level-{level + 1:02d}.zip"
        )
        payload = make_stored_zip(member_name, payload)
    return payload, cumulative_expanded_bytes


def _sample(
    *,
    name: str,
    series: str,
    depth: int,
    leaf_size: int,
    data: bytes,
    cumulative_expanded_bytes: int,
) -> dict[str, object]:
    return {
        "cumulative_expanded_bytes": cumulative_expanded_bytes,
        "depth": depth,
        "leaf_size": leaf_size,
        "member_count_per_level": 1,
        "name": name,
        "series": series,
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
    }


def generate(output_dir: pathlib.Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    base_leaf_size = len(BASELINE.make_pdf())
    samples: list[dict[str, object]] = []

    for depth in DEPTHS:
        name = f"depth-{depth:02d}.zip"
        data, expanded = make_nested_archive(depth, base_leaf_size)
        (output_dir / name).write_bytes(data)
        samples.append(
            _sample(
                name=name,
                series="depth",
                depth=depth,
                leaf_size=base_leaf_size,
                data=data,
                cumulative_expanded_bytes=expanded,
            )
        )

    for leaf_size in EXPANDED_LEAF_SIZES:
        name = f"expanded-{leaf_size:07d}.zip"
        data, expanded = make_nested_archive(
            EXPANDED_DEPTH,
            leaf_size,
        )
        (output_dir / name).write_bytes(data)
        samples.append(
            _sample(
                name=name,
                series="expanded_bytes",
                depth=EXPANDED_DEPTH,
                leaf_size=leaf_size,
                data=data,
                cumulative_expanded_bytes=expanded,
            )
        )

    manifest: dict[str, object] = {
        "capability": "CAP-NEST-009",
        "generator": (
            "tools/corpus/generate_archive_limit_fixture.py"
        ),
        "license": "project-generated; no third-party sample bytes",
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
