#!/usr/bin/env python3
"""Generate benign minimal inputs reaching two pinned undefined globals."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys


RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
RULE_EVIDENCE = (
    (
        "db/Binary/debug_data_debugData.1.sg",
        "381b6259b239f2633b92fbd84fd0d99b972751e20cab12b6e09139a260f1f47d",
        "calls undefined get_DWRAF_vi at line 58",
    ),
    (
        "db/Binary/audio_WEM.1.sg",
        "3ea818a39cf03337249883771a55cd1acacdecd3097f79edb85bce6b9bd85d94",
        "calls undefined xma2_pase_xma2_chunk at line 55",
    ),
    (
        "db/vgmcodingutils",
        "ef43f8258558b6dbfc212d5505a9d2b803b27e76a8fd8be5821ad60ea2d815e7",
        "defines xma2_parse_xma2_chunk at line 14",
    ),
)


def debug_dwarf_typo() -> bytes:
    data = bytearray(32)
    data[16:20] = (0x534954).to_bytes(4, "little")
    data[28:32] = (16).to_bytes(4, "little")
    return bytes(data)


def wem_xma2_typo() -> bytes:
    data = bytearray(40)
    data[0:4] = b"RIFF"
    data[4:8] = (32).to_bytes(4, "little")
    data[8:12] = b"WAVE"
    data[12:16] = b"XMA2"
    data[16:20] = (4).to_bytes(4, "little")
    data[24:28] = b"data"
    data[28:32] = (8).to_bytes(4, "little")
    return bytes(data)


FILES = (
    (
        "debug-dwarf-typo.bin",
        debug_dwarf_typo(),
        "reach get_DWRAF_vi after SIT/zero/zero trailer checks",
        "get_DWRAF_vi",
    ),
    (
        "audio-xma2-typo.wem",
        wem_xma2_typo(),
        "reach xma2_pase_xma2_chunk after RIFF/WAVE XMA2+data scan",
        "xma2_pase_xma2_chunk",
    ),
)


def generate(output_dir: pathlib.Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    for relative_path, data, purpose, undefined_global in FILES:
        destination = output_dir / relative_path
        destination.write_bytes(data)
        entries.append(
            {
                "path": relative_path,
                "source": "project-generated",
                "purpose": purpose,
                "undefined_global": undefined_global,
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    manifest: dict[str, object] = {
        "schema_version": 1,
        "generator": "tools/corpus/generate_global_typo_corpus.py",
        "license": "project-generated; no third-party sample or rule bytes",
        "rules_commit": RULES_COMMIT,
        "rule_evidence": [
            {"path": path, "sha256": digest, "purpose": purpose}
            for path, digest, purpose in RULE_EVIDENCE
        ],
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
    parser.add_argument("output_dir", type=pathlib.Path)
    args = parser.parse_args()
    manifest = generate(args.output_dir.resolve())
    json.dump(manifest, fp=sys.stdout, indent=2, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
