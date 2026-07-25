#!/usr/bin/env python3
"""Build a deterministic directory tree from the benign baseline corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil
import sys


DIRECTORIES = (
    "empty-dir",
    "single",
    "tree",
    "tree/b-dir",
    "tree/b-dir/c-deep",
)

LAYOUT = (
    ("single/only.elf", "minimal.elf"),
    ("tree/a-first.pdf", "minimal.pdf"),
    ("tree/b-dir/a-child.exe", "minimal.exe"),
    ("tree/b-dir/c-deep/z-child.zip", "payload.zip"),
    ("tree/z-last.txt", "plain.txt"),
)


def _load_baseline(baseline_dir: pathlib.Path) -> dict[str, dict[str, object]]:
    manifest_path = baseline_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported baseline corpus manifest schema")

    samples = manifest.get("samples")
    if not isinstance(samples, list):
        raise ValueError("baseline corpus manifest has no samples")

    result = {}
    for sample in samples:
        if not isinstance(sample, dict) or not isinstance(
            sample.get("name"), str
        ):
            raise ValueError("invalid baseline corpus sample")
        name = sample["name"]
        if name in result:
            raise ValueError(f"duplicate baseline corpus sample: {name}")

        data = (baseline_dir / name).read_bytes()
        expected_size = sample.get("size")
        expected_sha256 = sample.get("sha256")
        if (
            len(data) != expected_size
            or hashlib.sha256(data).hexdigest() != expected_sha256
        ):
            raise ValueError(f"baseline corpus sample mismatch: {name}")
        result[name] = sample
    return result


def generate(
    baseline_dir: pathlib.Path, output_dir: pathlib.Path
) -> dict[str, object]:
    samples = _load_baseline(baseline_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for directory in DIRECTORIES:
        (output_dir / pathlib.PurePosixPath(directory)).mkdir(
            parents=True, exist_ok=True
        )

    entries = []
    for relative_path, source_name in LAYOUT:
        if source_name not in samples:
            raise ValueError(f"missing baseline corpus sample: {source_name}")
        source_path = baseline_dir / source_name
        destination = output_dir / pathlib.PurePosixPath(relative_path)
        shutil.copyfile(source_path, destination)
        data = destination.read_bytes()
        entries.append(
            {
                "path": relative_path,
                "source": source_name,
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )

    manifest: dict[str, object] = {
        "schema_version": 1,
        "generator": "tools/corpus/generate_path_corpus.py",
        "license": "project-generated layout; baseline corpus bytes only",
        "directories": list(DIRECTORIES),
        "entries": entries,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline_dir", type=pathlib.Path)
    parser.add_argument("output_dir", type=pathlib.Path)
    args = parser.parse_args()
    manifest = generate(
        args.baseline_dir.resolve(),
        args.output_dir.resolve(),
    )
    json.dump(manifest, fp=sys.stdout, indent=2, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
