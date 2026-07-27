#!/usr/bin/env python3
"""Probe seven publicly detected DOS/COM formats in pinned Qt5 oracles."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[2]
SHARED_PATH = ROOT / "tools" / "upstream" / "probe_legacy_dispatch.py"
SHARED_SPEC = importlib.util.spec_from_file_location(
    "probe_legacy_dispatch_for_dos", SHARED_PATH
)
assert SHARED_SPEC is not None and SHARED_SPEC.loader is not None
SHARED = importlib.util.module_from_spec(SHARED_SPEC)
sys.modules[SHARED_SPEC.name] = SHARED
SHARED_SPEC.loader.exec_module(SHARED)


UPSTREAM_COMMIT = SHARED.UPSTREAM_COMMIT
RULES_COMMIT = SHARED.RULES_COMMIT
FORMATS_COMMIT = SHARED.FORMATS_COMMIT
XARCHIVE_COMMIT = "0fcd4e8d3e9933baac3b12246d82ac026557ffd0"
EXPECTED_GENERATOR = "tools/corpus/generate_dos_dispatch_corpus.py"
EXPECTED_FILETYPES = {
    "MSDOS",
    "NE",
    "LE",
    "LX",
    "DOS16M",
    "DOS4G",
    "COM",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_fixture(
    repo: pathlib.Path,
    corpus_dir: pathlib.Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], bytes]:
    reference_path = (
        repo
        / "docs"
        / "research"
        / "data"
        / "dos-dispatch-corpus.json"
    )
    reference = reference_path.read_bytes()
    generated = (corpus_dir / "manifest.json").read_bytes()
    if generated != reference:
        raise ValueError("generated corpus manifest differs from reference")

    manifest = json.loads(generated)
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported DOS dispatch manifest schema")
    if manifest.get("generator") != EXPECTED_GENERATOR:
        raise ValueError("unexpected DOS dispatch corpus generator")
    if manifest.get("capability") != "CAP-DISPATCH-002":
        raise ValueError("unexpected DOS dispatch capability")
    if set(manifest.get("public_filetypes", [])) != EXPECTED_FILETYPES:
        raise ValueError("DOS dispatch public filetype set mismatch")
    if manifest.get("excluded_member", {}).get("filetype") != "BW DOS16M":
        raise ValueError("DOS dispatch excluded member mismatch")
    source_identity = manifest.get("source_identity", {})
    if (
        source_identity.get("Formats", {}).get("commit")
        != FORMATS_COMMIT
    ):
        raise ValueError("DOS dispatch Formats commit mismatch")
    if (
        source_identity.get("XArchive", {}).get("commit")
        != XARCHIVE_COMMIT
    ):
        raise ValueError("DOS dispatch XArchive commit mismatch")

    samples = SHARED.SHARED.load_corpus(corpus_dir)
    positive_targets = {
        str(sample["target_filetype"])
        for sample in samples
        if sample.get("case_kind") == "positive"
    }
    if positive_targets != EXPECTED_FILETYPES:
        raise ValueError("DOS dispatch positive target set mismatch")
    for sample in samples:
        expectation = sample.get("expected_dispatch")
        if not isinstance(expectation, dict):
            raise ValueError("dispatch expectation must be an object")
        for key in ("present_filetypes", "absent_filetypes"):
            values = expectation.get(key)
            if (
                not isinstance(values, list)
                or any(not isinstance(item, str) for item in values)
            ):
                raise ValueError(f"invalid dispatch expectation: {key}")
        if set(expectation["present_filetypes"]) & set(
            expectation["absent_filetypes"]
        ):
            raise ValueError("dispatch expectation overlaps")
    return manifest, samples, reference


def build_report(
    repo: pathlib.Path,
    corpus_dir: pathlib.Path,
    raw_dir: pathlib.Path,
) -> dict[str, Any]:
    manifest, samples, manifest_bytes = load_fixture(repo, corpus_dir)
    oracle_identities, cases, failures = SHARED.probe_dispatch_cases(
        corpus_dir,
        raw_dir,
        samples,
    )
    return {
        "schema_version": 1,
        "generator": "tools/upstream/probe_dos_dispatch.py",
        "generator_sha256": sha256(pathlib.Path(__file__).read_bytes()),
        "result": "pass" if not failures else "fail",
        "upstream_commit": UPSTREAM_COMMIT,
        "rules_commit": RULES_COMMIT,
        "formats_commit": FORMATS_COMMIT,
        "xarchive_commit": XARCHIVE_COMMIT,
        "platform": "linux-amd64-qt5",
        "capability": "CAP-DISPATCH-002",
        "scope": {
            "public_filetypes": sorted(EXPECTED_FILETYPES),
            "excluded_member": "BW DOS16M",
            "excluded_member_evidence": (
                "docs/research/data/dos-dispatch-source-audit.json"
            ),
        },
        "corpus_manifest": {
            "path": "docs/research/data/dos-dispatch-corpus.json",
            "sha256": sha256(manifest_bytes),
            "sample_count": len(manifest["samples"]),
        },
        "raw_artifacts": {
            "storage": "untracked external directory selected by --raw-dir",
            "stdout_and_stderr_retained_for_every_case": True,
        },
        "oracle_identities": oracle_identities,
        "cases": cases,
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        type=pathlib.Path,
        default=ROOT,
    )
    parser.add_argument("--corpus-dir", type=pathlib.Path, required=True)
    parser.add_argument("--raw-dir", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()
    report = build_report(
        args.repo.resolve(),
        args.corpus_dir.resolve(),
        args.raw_dir.resolve(),
    )
    args.output.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0 if report["result"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
