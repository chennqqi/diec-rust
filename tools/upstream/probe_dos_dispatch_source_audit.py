#!/usr/bin/env python3
"""Audit pinned DOS/COM detector and scanner-branch reachability facts."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
from typing import Any


UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
FORMATS_COMMIT = "1151e7254fdee3c0294ff7095edbdd7bfccf8201"
XSCANENGINE_COMMIT = "dfe4a419e4f491bb23688ba03c5a5bf39e34da83"

SOURCES = {
    "xformats": {
        "path": "/opt/die-source/Formats/xformats.cpp",
        "sha256": (
            "674eba0046eb6cc947e547d1ac0b93ac695cbb30f68e11f135e5551d81e0b115"
        ),
    },
    "xbinary": {
        "path": "/opt/die-source/Formats/xbinary.cpp",
        "sha256": (
            "d82bd21326bb7ba07eb343020d50af0ae2cf7e8e534d8e08d07ffa8129913c34"
        ),
    },
    "xscanengine": {
        "path": "/opt/die-source/XScanEngine/xscanengine.cpp",
        "sha256": (
            "e088bebb7c8345ce5832cc51de712c05a8b239873d7f092db3ae5566a761b498"
        ),
    },
}

NEEDLES = {
    "xformats": {
        "filetypes_property_reader": (
            'pDevice->property("filetypes").toString()'
        ),
        "msdos_detector": "if (XMSDOS::isValid(",
        "ne_detector": "else if (XNE::isValid(",
        "le_lx_detector": "else if (XLE::isValid(",
        "dos16_dos4g_detector": "if (XDOS16::isValid(",
        "com_detector": "if (XCOM::isValid(",
    },
    "xbinary": {
        "legacy_bw_signature": (
            "compareSignature(&memoryMap, \"'BW'....00..00000000\", 0)"
        ),
        "legacy_bw_insert": "stResult.insert(FT_BWDOS16M)",
    },
    "xscanengine": {
        "active_detector_call": (
            "QSet<XBinary::FT> stFT = "
            "XFormats::getFileTypes(_pDevice, true, pPdStruct)"
        ),
        "bw_dispatch_branch": (
            "stFT.contains(XBinary::FT_BWDOS16M)"
        ),
        "bw_process_detect": (
            "_processDetect(&scanIdMain, pScanResult, _pDevice, "
            "parentId, XBinary::FT_BWDOS16M"
        ),
    },
}

EXPECTED_LINES = {
    "xformats": {
        "filetypes_property_reader": [1527],
        "msdos_detector": [1533],
        "ne_detector": [1544],
        "le_lx_detector": [1546],
        "dos16_dos4g_detector": [1556],
        "com_detector": [1827],
    },
    "xbinary": {
        "legacy_bw_signature": [9182],
        "legacy_bw_insert": [9183],
    },
    "xscanengine": {
        "active_detector_call": [2650],
        "bw_dispatch_branch": [2739],
        "bw_process_detect": [2740],
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


def audit_sources(sources: dict[str, bytes]) -> dict[str, Any]:
    report_sources = {}
    failures = []
    decoded = {}
    for source_name, metadata in SOURCES.items():
        data = sources[source_name]
        actual_hash = sha256_bytes(data)
        if actual_hash != metadata["sha256"]:
            failures.append(f"{source_name}.sha256")
        text = data.decode("utf-8")
        decoded[source_name] = text
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

    xformats = decoded["xformats"]
    xscanengine = decoded["xscanengine"]
    absence_counts = {
        "xformats_bw_filetype_tokens": xformats.count("FT_BWDOS16M"),
        "xformats_filetypes_property_setters": xformats.count(
            'setProperty("filetypes"'
        ),
        "xscanengine_filetypes_property_setters": xscanengine.count(
            'setProperty("filetypes"'
        ),
        "xscanengine_bw_database_path_tokens": xscanengine.count(
            '"BW DOS16M"'
        ),
    }
    for name, count in absence_counts.items():
        if count != 0:
            failures.append(name)

    return {
        "schema_version": 1,
        "upstream_commit": UPSTREAM_COMMIT,
        "component_commits": {
            "Formats": FORMATS_COMMIT,
            "XScanEngine": XSCANENGINE_COMMIT,
        },
        "sources": report_sources,
        "facts": {
            "public_detector": "XFormats::getFileTypes",
            "automatically_detected_family_members": [
                "MSDOS",
                "NE",
                "LE",
                "LX",
                "DOS16M",
                "DOS4G",
                "COM",
            ],
            "branch_without_public_detector": ["BW DOS16M"],
            "legacy_xbinary_detector_contains_bw_signature": True,
            "external_filetypes_property_can_bypass_detection": True,
            "absence_counts": absence_counts,
            "closure_requirement": (
                "seven-member CLI oracle plus BW forced-property harness "
                "or reviewed scope disposition"
            ),
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


def load_object(path: pathlib.Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(document, dict):
        raise ValueError(f"{path} root must be a JSON object")
    return document


def serialize(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
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
    canonical = serialize(actual)
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
