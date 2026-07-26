#!/usr/bin/env python3
"""Audit pinned subdevice enumeration and scheduling source facts."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
from typing import Any


UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
XSCANENGINE_COMMIT = "dfe4a419e4f491bb23688ba03c5a5bf39e34da83"
FORMATS_COMMIT = "1151e7254fdee3c0294ff7095edbdd7bfccf8201"
SOURCES = {
    "xscanengine": {
        "path": "/opt/die-source/XScanEngine/xscanengine.cpp",
        "sha256": (
            "e088bebb7c8345ce5832cc51de712c05a8b239873d7f092db3ae5566a761b498"
        ),
    },
    "xpe": {
        "path": "/opt/die-source/Formats/exec/xpe.cpp",
        "sha256": (
            "bfad885df2569b03bc33c040852a884bfe40d781a58bef5f6d8c53c16b488a0c"
        ),
    },
}
NEEDLES = {
    "xscanengine": {
        "resource_enumeration": "XBinary::FILEPART_RESOURCE, 10000",
        "overlay_enumeration": "XBinary::FILEPART_OVERLAY, 1",
        "resource_scan_id": "_options.sScanID = filePart.mapProperties.value",
        "child_scan": "scanProcess(&subDevice, &scanResultFilePart",
    },
    "xpe": {
        "resource_or_debugdata_gate": (
            "(nFileParts & FILEPART_RESOURCE) || "
            "(nFileParts & FILEPART_DEBUGDATA)"
        ),
        "debugdata_enumeration": (
            "if (nFileParts & FILEPART_DEBUGDATA)"
        ),
        "debugdata_record": (
            "record.filePart = XBinary::FILEPART_DEBUGDATA"
        ),
    },
}
EXPECTED_LINES = {
    "xscanengine": {
        "resource_enumeration": [2935],
        "overlay_enumeration": [2939],
        "resource_scan_id": [2990],
        "child_scan": [2995],
    },
    "xpe": {
        "resource_or_debugdata_gate": [11102],
        "debugdata_enumeration": [11244],
        "debugdata_record": [11261],
    },
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def matching_lines(text: str, needle: str) -> list[dict[str, Any]]:
    return [
        {"line": number, "text": line.strip()}
        for number, line in enumerate(text.splitlines(), start=1)
        if needle in line
    ]


def audit_sources(sources: dict[str, bytes]) -> dict[str, object]:
    report_sources = {}
    failures = []
    for source_name, metadata in SOURCES.items():
        data = sources[source_name]
        actual_hash = sha256_bytes(data)
        if actual_hash != metadata["sha256"]:
            failures.append(f"{source_name}.sha256")
        text = data.decode("utf-8")
        occurrences = {}
        for fact_name, needle in NEEDLES[source_name].items():
            matches = matching_lines(text, needle)
            occurrences[fact_name] = matches
            actual_lines = [match["line"] for match in matches]
            if actual_lines != EXPECTED_LINES[source_name][fact_name]:
                failures.append(f"{source_name}.{fact_name}")
        report_sources[source_name] = {
            "path": metadata["path"],
            "sha256": actual_hash,
            "occurrences": occurrences,
        }

    engine_text = sources["xscanengine"].decode("utf-8")
    debugdata_count = engine_text.count("FILEPART_DEBUGDATA")
    if debugdata_count != 0:
        failures.append("xscanengine.debugdata_token_count")

    return {
        "schema_version": 1,
        "upstream_commit": UPSTREAM_COMMIT,
        "component_commits": {
            "XScanEngine": XSCANENGINE_COMMIT,
            "Formats": FORMATS_COMMIT,
        },
        "sources": report_sources,
        "facts": {
            "xscanengine_debugdata_token_count": debugdata_count,
            "xscanengine_enumerated_file_parts": [
                "resource",
                "overlay",
            ],
            "xpe_can_enumerate_debugdata": True,
        },
        "failures": failures,
        "passed": not failures,
    }


def inspect_revision(image: str, docker_context: str) -> str:
    process = subprocess.run(
        [
            "docker",
            f"--context={docker_context}",
            "image",
            "inspect",
            "--format",
            (
                "{{index .Config.Labels "
                '"org.opencontainers.image.revision"}}'
            ),
            image,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return process.stdout.strip()


def read_source(
    image: str,
    path: str,
    docker_context: str,
) -> bytes:
    process = subprocess.run(
        [
            "docker",
            f"--context={docker_context}",
            "run",
            "--rm",
            "--network=none",
            "--memory=512m",
            "--cpus=1",
            "--pids-limit=128",
            "--entrypoint",
            "cat",
            image,
            path,
        ],
        check=True,
        capture_output=True,
    )
    return process.stdout


def load_object(path: pathlib.Path) -> dict[str, object]:
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(document, dict):
        raise ValueError(f"{path} root must be a JSON object")
    return document


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument(
        "--expected-revision",
        default=UPSTREAM_COMMIT,
    )
    parser.add_argument("--baseline", required=True, type=pathlib.Path)
    parser.add_argument("--docker-context", default="default")
    parser.add_argument("--record-baseline", action="store_true")
    args = parser.parse_args()

    revision = inspect_revision(args.image, args.docker_context)
    if revision != args.expected_revision or revision != UPSTREAM_COMMIT:
        raise SystemExit(f"image revision mismatch: {revision!r}")
    sources = {
        name: read_source(
            args.image,
            str(metadata["path"]),
            args.docker_context,
        )
        for name, metadata in SOURCES.items()
    }
    actual = audit_sources(sources)
    if not actual["passed"]:
        raise SystemExit(
            "source audit failed: " + ", ".join(actual["failures"])
        )
    actual["image"] = args.image
    canonical = (
        json.dumps(actual, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")
    if args.record_baseline:
        args.baseline.write_bytes(canonical)
    if load_object(args.baseline) != actual:
        raise SystemExit("baseline content differs from current source audit")

    print(
        json.dumps(
            {
                "schema_version": 1,
                "image": args.image,
                "image_revision": revision,
                "baseline": str(args.baseline).replace("\\", "/"),
                "baseline_sha256": sha256_bytes(
                    args.baseline.read_bytes()
                ),
                "failures": [],
                "passed": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as error:
        if error.stderr:
            sys.stderr.buffer.write(error.stderr)
        raise
