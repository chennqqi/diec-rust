#!/usr/bin/env python3
"""Generate deterministic fixtures for generic Archive dispatch."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import sys


GENERATOR = "tools/corpus/generate_generic_archive_dispatch_fixture.py"


def _load_baseline_module():
    module_path = pathlib.Path(__file__).with_name(
        "generate_baseline_corpus.py"
    )
    spec = importlib.util.spec_from_file_location(
        "_diec_generic_archive_baseline",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load baseline corpus builders")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BASELINE = _load_baseline_module()
CASES = (
    {
        "archive_format": "ZIP",
        "builder": BASELINE.make_zip,
        "expected_member_name": "payload.txt",
        "name": "payload.zip",
        "purpose": "specialized public ZIP branch and forced Archive control",
    },
    {
        "archive_format": "TAR",
        "builder": BASELINE.make_tar,
        "expected_member_name": "payload.txt",
        "name": "payload.tar",
        "purpose": "Binary public fallback and forced Archive adapter",
    },
    {
        "archive_format": "GZIP",
        "builder": BASELINE.make_gzip,
        "expected_member_name": "",
        "name": "payload.txt.gz",
        "purpose": "Binary Unknown public fallback and forced Archive adapter",
    },
)


def generate(output_dir: pathlib.Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    samples = []
    payload_sha256 = hashlib.sha256(BASELINE.PAYLOAD).hexdigest()
    for case in CASES:
        data = case["builder"]()
        name = case["name"]
        (output_dir / name).write_bytes(data)
        samples.append(
            {
                "archive_format": case["archive_format"],
                "expected_member_name": case["expected_member_name"],
                "expected_payload_sha256": payload_sha256,
                "name": name,
                "purpose": case["purpose"],
                "sha256": hashlib.sha256(data).hexdigest(),
                "size": len(data),
            }
        )
    manifest: dict[str, object] = {
        "generator": GENERATOR,
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
    sys.stdout.buffer.write(
        (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode(
            "utf-8"
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
