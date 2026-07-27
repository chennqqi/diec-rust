#!/usr/bin/env python3
"""Build a deterministic GNU tar for symlink, permission, and depth probes."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import pathlib
import sys
import tarfile


SCHEMA_VERSION = 1
GENERATOR = "tools/corpus/generate_path_filesystem_fixture.py"
ARCHIVE_NAME = "path-filesystem-fixture.tar"
SOURCE_NAME = "minimal.pdf"
DEEP_LEVELS = 64


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_payload(baseline_dir: pathlib.Path) -> bytes:
    manifest = json.loads(
        (baseline_dir / "manifest.json").read_text(encoding="utf-8")
    )
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported baseline corpus manifest schema")
    matches = [
        sample
        for sample in manifest.get("samples", [])
        if isinstance(sample, dict) and sample.get("name") == SOURCE_NAME
    ]
    if len(matches) != 1:
        raise ValueError(f"baseline must contain exactly one {SOURCE_NAME}")
    payload = (baseline_dir / SOURCE_NAME).read_bytes()
    if (
        len(payload) != matches[0].get("size")
        or sha256(payload) != matches[0].get("sha256")
    ):
        raise ValueError(f"baseline corpus sample mismatch: {SOURCE_NAME}")
    return payload


def directory(name: str, mode: int = 0o755) -> dict[str, object]:
    return {"path": name.rstrip("/") + "/", "type": "directory", "mode": mode}


def regular(name: str, mode: int = 0o644) -> dict[str, object]:
    return {
        "path": name,
        "type": "file",
        "mode": mode,
        "source": SOURCE_NAME,
    }


def symlink(name: str, target: str) -> dict[str, object]:
    return {
        "path": name,
        "type": "symlink",
        "mode": 0o777,
        "target": target,
    }


def entries() -> list[dict[str, object]]:
    result = [
        directory("paths"),
        directory("paths/symlink"),
        regular("paths/symlink/target.pdf"),
        symlink("paths/symlink/file-link.pdf", "target.pdf"),
        directory("paths/symlink/dir-target"),
        regular("paths/symlink/dir-target/child.pdf"),
        symlink("paths/symlink/dir-link", "dir-target"),
        symlink("paths/symlink/dangling.pdf", "missing.pdf"),
        directory("paths/cycle"),
        regular("paths/cycle/root.pdf"),
        symlink("paths/cycle/loop", "."),
        directory("paths/denied", mode=0),
        regular("paths/denied/secret.pdf"),
        directory("paths/deep"),
    ]
    current = "paths/deep"
    for level in range(DEEP_LEVELS):
        current = f"{current}/level-{level:03d}"
        result.append(directory(current))
    result.append(regular(f"{current}/leaf.pdf"))
    return result


def tar_info(record: dict[str, object], payload_size: int) -> tarfile.TarInfo:
    info = tarfile.TarInfo(str(record["path"]))
    info.mode = int(record["mode"])
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = 0
    kind = record["type"]
    if kind == "directory":
        info.type = tarfile.DIRTYPE
        info.size = 0
    elif kind == "file":
        info.type = tarfile.REGTYPE
        info.size = payload_size
    elif kind == "symlink":
        info.type = tarfile.SYMTYPE
        info.size = 0
        info.linkname = str(record["target"])
    else:
        raise ValueError(f"unsupported fixture entry type: {kind}")
    return info


def build_archive(payload: bytes) -> tuple[bytes, list[dict[str, object]]]:
    records = entries()
    stream = io.BytesIO()
    with tarfile.open(
        fileobj=stream,
        mode="w:",
        format=tarfile.GNU_FORMAT,
    ) as archive:
        for record in records:
            info = tar_info(record, len(payload))
            archive.addfile(
                info,
                io.BytesIO(payload) if record["type"] == "file" else None,
            )
    return stream.getvalue(), records


def generate(
    baseline_dir: pathlib.Path, output_dir: pathlib.Path
) -> dict[str, object]:
    payload = load_payload(baseline_dir)
    archive, records = build_archive(payload)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / ARCHIVE_NAME).write_bytes(archive)
    manifest: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "generator": GENERATOR,
        "license": "project-generated paths; baseline corpus bytes only",
        "archive": {
            "name": ARCHIVE_NAME,
            "format": "gnu",
            "size": len(archive),
            "sha256": sha256(archive),
        },
        "payload": {
            "source": SOURCE_NAME,
            "size": len(payload),
            "sha256": sha256(payload),
        },
        "deep_levels": DEEP_LEVELS,
        "entries": [
            {
                **record,
                **(
                    {
                        "size": len(payload),
                        "sha256": sha256(payload),
                    }
                    if record["type"] == "file"
                    else {}
                ),
            }
            for record in records
        ],
    }
    (output_dir / "manifest.json").write_bytes(serialize_manifest(manifest))
    return manifest


def serialize_manifest(manifest: dict[str, object]) -> bytes:
    return (
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline_dir", type=pathlib.Path)
    parser.add_argument("output_dir", type=pathlib.Path)
    parser.add_argument("--manifest-output", type=pathlib.Path)
    args = parser.parse_args()
    manifest = generate(
        args.baseline_dir.resolve(),
        args.output_dir.resolve(),
    )
    if args.manifest_output is not None:
        args.manifest_output.parent.mkdir(parents=True, exist_ok=True)
        args.manifest_output.write_bytes(serialize_manifest(manifest))
    json.dump(manifest, sys.stdout, indent=2, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
