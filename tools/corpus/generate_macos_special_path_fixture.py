#!/usr/bin/env python3
"""Generate a non-admitted macOS special-path fixture candidate."""

from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
PLATFORM = "macos-x86_64"
GENERATOR = "tools/corpus/generate_macos_special_path_fixture.py"
VALIDATOR = "tools/corpus/validate_macos_special_path_fixture.py"
BASELINE_MANIFEST = "docs/research/data/baseline-corpus.json"
SOURCE_NAME = "minimal.pdf"
DIRECTORIES = ("special", "目录 空格", "nonutf8")
STABLE_ENTRIES = (
    ("ascii", "special/00-ascii.pdf"),
    ("upper_case", "special/A-case.pdf"),
    ("nfc", "special/é-nfc.pdf"),
    ("cjk", "special/中文.pdf"),
    ("emoji", "special/emoji-😀.pdf"),
    ("space", "special/space name.pdf"),
    ("leading_space", "special/ leading-space.pdf"),
    ("trailing_space", "special/trailing-space.pdf "),
    ("tab", "special/tab\tname.pdf"),
    ("newline", "special/line\nbreak.pdf"),
    ("colon", "special/colon:name.pdf"),
    ("backslash", "special/backslash\\name.pdf"),
    ("leading_dash", "special/--leading-dash.pdf"),
    ("dot_hidden", "special/.hidden.pdf"),
    ("unicode_child", "目录 空格/子 文件.pdf"),
)
CASE_ALIAS = ("lower_case", "special/a-case.pdf", "upper_case")
UNICODE_ALIAS = ("nfd", "special/e\u0301-nfd.pdf", "nfc")
RAW_NAMES = (
    b"invalid-ff-\xff.pdf",
    b"invalid-c0af-\xc0\xaf.pdf",
    b"truncated-e282-\xe2\x82.pdf",
)
ADMISSION_REASON = (
    "filesystem fixture candidate only; no CLI or engine capability row "
    "is admitted"
)
LIMITATIONS = [
    (
        "the candidate records the actual runner volume's case and "
        "NFC/NFD alias behavior instead of assuming an APFS mode"
    ),
    (
        "invalid UTF-8 byte names are attempted and their errno is "
        "retained when the host API rejects them"
    ),
    (
        "symlink cycles, permissions, long paths, large directories, "
        "TOCTOU, and CLI scan behavior require separate candidates"
    ),
]


class FixtureError(ValueError):
    """The macOS special-path fixture cannot be generated safely."""


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def serialize(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _load_payload(
    root: Path, baseline_dir: Path
) -> tuple[bytes, bytes]:
    reference_raw = (root / BASELINE_MANIFEST).read_bytes()
    actual_raw = (baseline_dir / "manifest.json").read_bytes()
    if actual_raw != reference_raw:
        raise FixtureError("baseline corpus manifest differs")
    manifest = json.loads(reference_raw)
    matches = [
        sample
        for sample in manifest.get("samples", [])
        if sample.get("name") == SOURCE_NAME
    ]
    if len(matches) != 1:
        raise FixtureError("baseline manifest minimal.pdf drift")
    payload = (baseline_dir / SOURCE_NAME).read_bytes()
    if (
        len(payload) != matches[0]["size"]
        or sha256(payload) != matches[0]["sha256"]
    ):
        raise FixtureError("baseline minimal.pdf identity differs")
    return payload, reference_raw


def _write_entry(
    root: Path,
    case_id: str,
    relative: str,
    payload: bytes,
) -> dict[str, Any]:
    path = root.joinpath(*relative.split("/"))
    path.write_bytes(payload)
    matches = [
        os.fsencode(entry.name).hex()
        for entry in os.scandir(path.parent)
        if os.path.samefile(entry.path, path)
    ]
    if len(matches) != 1:
        raise FixtureError(
            f"fixture entry directory identity is ambiguous: {relative}"
        )
    return {
        "id": case_id,
        "path": relative,
        "directory_name_bytes_hex": matches[0],
        "size": len(payload),
        "sha256": sha256(payload),
    }


def _same_file(first: Path, second: Path) -> tuple[bool, bool]:
    exists = second.exists()
    return exists, exists and os.path.samefile(first, second)


def _directory_inventory(path: Path) -> list[str]:
    return [os.fsencode(entry.name).hex() for entry in os.scandir(path)]


def generate(
    *,
    root: Path,
    baseline_dir: Path,
    fixture_dir: Path,
    output: Path,
) -> dict[str, Any]:
    if sys.platform != "darwin" or platform.machine() != "x86_64":
        raise FixtureError("generator requires native Darwin x86_64")
    baseline_dir = baseline_dir.resolve(strict=True)
    fixture_dir = fixture_dir.resolve()
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FixtureError("candidate report already exists")
    fixture_dir.mkdir(parents=True, exist_ok=True)
    if any(fixture_dir.iterdir()):
        raise FixtureError("fixture directory must be empty")
    payload, baseline_raw = _load_payload(root, baseline_dir)
    for directory in DIRECTORIES:
        fixture_dir.joinpath(*directory.split("/")).mkdir(parents=True)

    entries = [
        _write_entry(fixture_dir, case_id, relative, payload)
        for case_id, relative in STABLE_ENTRIES
    ]
    by_id = {entry["id"]: entry for entry in entries}
    upper = fixture_dir.joinpath(*by_id["upper_case"]["path"].split("/"))
    lower = fixture_dir.joinpath(*CASE_ALIAS[1].split("/"))
    lower_exists, lower_same = _same_file(upper, lower)
    if not lower_same:
        entries.append(
            _write_entry(
                fixture_dir, CASE_ALIAS[0], CASE_ALIAS[1], payload
            )
        )
    nfc = fixture_dir.joinpath(*by_id["nfc"]["path"].split("/"))
    nfd = fixture_dir.joinpath(*UNICODE_ALIAS[1].split("/"))
    nfd_exists, nfd_same = _same_file(nfc, nfd)
    if not nfd_same:
        entries.append(
            _write_entry(
                fixture_dir,
                UNICODE_ALIAS[0],
                UNICODE_ALIAS[1],
                payload,
            )
        )

    raw_attempts = []
    raw_root = os.fsencode(fixture_dir / "nonutf8")
    for name in RAW_NAMES:
        raw_path = raw_root + b"/" + name
        try:
            descriptor = os.open(
                raw_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            try:
                view = memoryview(payload)
                while view:
                    written = os.write(descriptor, view)
                    if written <= 0:
                        raise OSError("short write for raw-name fixture")
                    view = view[written:]
            finally:
                os.close(descriptor)
        except OSError as error:
            if error.errno in {errno.EILSEQ, errno.EINVAL, errno.ENOTSUP}:
                raw_attempts.append(
                    {
                        "name_bytes_hex": name.hex(),
                        "created": False,
                        "errno": error.errno,
                        "size": None,
                        "sha256": None,
                    }
                )
            else:
                raise
        else:
            raw_attempts.append(
                {
                    "name_bytes_hex": name.hex(),
                    "created": True,
                    "errno": None,
                    "size": len(payload),
                    "sha256": sha256(payload),
                }
            )

    report = {
        "schema_version": SCHEMA_VERSION,
        "result": "candidate",
        "platform": PLATFORM,
        "generator": {
            "path": GENERATOR,
            "sha256": sha256((root / GENERATOR).read_bytes()),
            "validator_path": VALIDATOR,
            "validator_sha256": sha256(
                (root / VALIDATOR).read_bytes()
            ),
        },
        "source": {
            "manifest": BASELINE_MANIFEST,
            "manifest_sha256": sha256(baseline_raw),
            "sample": SOURCE_NAME,
            "size": len(payload),
            "sha256": sha256(payload),
        },
        "fixture": {
            "local_path": str(fixture_dir),
            "directories": list(DIRECTORIES),
            "entries": entries,
            "raw_attempts": raw_attempts,
            "directory_inventory_name_bytes_hex": {
                directory: _directory_inventory(
                    fixture_dir.joinpath(*directory.split("/"))
                )
                for directory in DIRECTORIES
            },
        },
        "filesystem_observations": {
            "lowercase_alias_exists_after_upper_create": (
                lower_exists
            ),
            "lowercase_alias_is_same_file": lower_same,
            "case_distinct_names_materialized": not lower_same,
            "nfd_alias_exists_after_nfc_create": nfd_exists,
            "nfd_alias_is_same_file": nfd_same,
            "nfc_nfd_distinct_names_materialized": not nfd_same,
        },
        "admission": {
            "fixture_admitted": False,
            "capability_rows_admitted": 0,
            "reason": ADMISSION_REASON,
        },
        "limitations": LIMITATIONS,
    }
    output.write_bytes(serialize(report))
    return report


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-dir", type=Path, required=True)
    parser.add_argument("--fixture-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.set_defaults(root=root)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        generate(
            root=args.root.resolve(),
            baseline_dir=args.baseline_dir,
            fixture_dir=args.fixture_dir,
            output=args.output,
        )
    except (FixtureError, OSError, ValueError) as error:
        print(
            f"macOS special-path fixture error: {error}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
