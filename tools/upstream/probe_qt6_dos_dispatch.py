#!/usr/bin/env python3
"""Compare the seven public DOS/COM dispatch families on Qt5 and Qt6."""

from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import re
import subprocess
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[2]
UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
FORMATS_COMMIT = "1151e7254fdee3c0294ff7095edbdd7bfccf8201"
XARCHIVE_COMMIT = "0fcd4e8d3e9933baac3b12246d82ac026557ffd0"
QT5_REPORT_SHA256 = (
    "21abf20ac50e694fb135d31bc786d0d61c9d701530334900329f9360b9b5ee77"
)
SOURCE_AUDIT_SHA256 = (
    "07661cdefb773fb397870fdacbfefa010ae67fa1284253ddc000808ea7192c4c"
)
QT6_WARNING = b"Unimplemented code.\n" * 4
ADDRESS_PATTERN = re.compile(rb"0x[0-9a-fA-F]+")
DIAGNOSTIC_LINE_PATTERN = re.compile(
    rb"^(?:[^:\r\n]+: ){2,3}\d+: TypeError: .+$"
)
SOURCE_PATHS = (
    "/opt/die-source/Formats/xbinary.cpp",
    "/opt/die-source/Formats/xformats.cpp",
    "/opt/die-source/XScanEngine/xscanengine.cpp",
)


def _load_module(name: str, filename: str):
    path = pathlib.Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BASE = _load_module("_diec_qt5_dos_dispatch", "probe_dos_dispatch.py")
QT6 = _load_module(
    "_diec_qt6_legacy_helpers",
    "probe_qt6_legacy_dispatch.py",
)


def inspect_qt6_image() -> dict[str, Any]:
    process = subprocess.run(
        ["docker", "image", "inspect", QT6.QT6_IMAGE],
        check=True,
        capture_output=True,
    )
    document = QT6.strict_json(process.stdout)[0]
    revision = document["Config"]["Labels"].get(
        "org.opencontainers.image.revision",
        "",
    )
    if revision != UPSTREAM_COMMIT:
        raise ValueError("Qt6 DOS image revision mismatch")
    paths = (QT6.QT6_BINARY, *SOURCE_PATHS)
    hash_process = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            QT6.QT6_IMAGE,
            "sha256sum",
            *paths,
        ],
        check=True,
        capture_output=True,
    )
    hashes = {}
    for line in hash_process.stdout.decode("ascii").splitlines():
        digest, path = line.split(maxsplit=1)
        hashes[path] = digest
    if set(hashes) != set(paths):
        raise ValueError("Qt6 DOS source hash inventory mismatch")
    return {
        "image": QT6.QT6_IMAGE,
        "image_id": document["Id"],
        "revision": revision,
        "binary": QT6.QT6_BINARY,
        "binary_sha256": hashes[QT6.QT6_BINARY],
        "source_sha256": {
            path: hashes[path] for path in SOURCE_PATHS
        },
    }


def load_qt5_reference(
    report_path: pathlib.Path,
    manifest_sha256: str,
) -> tuple[dict[str, Any], str]:
    report_bytes = report_path.read_bytes()
    digest = QT6.sha256(report_bytes)
    report = QT6.strict_json(report_bytes)
    if (
        digest != QT5_REPORT_SHA256
        or report.get("schema_version") != 1
        or report.get("result") != "pass"
        or report.get("failures") != []
        or report.get("upstream_commit") != UPSTREAM_COMMIT
        or report.get("rules_commit") != RULES_COMMIT
        or report.get("formats_commit") != FORMATS_COMMIT
        or report.get("xarchive_commit") != XARCHIVE_COMMIT
        or report.get("platform") != "linux-amd64-qt5"
        or report.get("capability") != "CAP-DISPATCH-002"
        or report.get("corpus_manifest", {}).get("sha256")
        != manifest_sha256
    ):
        raise ValueError("Qt5 DOS dispatch reference drift")
    return report, digest


def split_json_and_diagnostics(
    data: bytes,
) -> tuple[bytes, Any, bytes, bytes]:
    text = data.decode("utf-8")
    start = len(text) - len(text.lstrip())
    document, end = json.JSONDecoder().raw_decode(text, start)
    json_bytes = (text[:end] + "\n").encode("utf-8")
    diagnostics = text[end:].lstrip("\r\n").encode("utf-8")
    normalized = ADDRESS_PATTERN.sub(b"0x<address>", diagnostics)
    lines = normalized.split(b"\n")
    while lines and lines[-1] == b"":
        lines.pop()
    if any(
        not line or not DIAGNOSTIC_LINE_PATTERN.fullmatch(line)
        for line in lines
    ):
        raise ValueError(
            f"unclassified Qt6 DOS stdout diagnostic: {lines!r}"
        )
    return json_bytes, document, diagnostics, normalized


def strip_formatter_extras(
    value: Any,
    path: str = "$",
) -> tuple[Any, list[dict[str, Any]]]:
    extras = []
    if isinstance(value, dict):
        stripped = {}
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key == "info":
                if child != "":
                    raise ValueError(
                        "non-empty Qt6 DOS info field is unclassified"
                    )
                extras.append({"path": child_path, "value": child})
            elif key == "string":
                if not isinstance(child, str):
                    raise ValueError(
                        "non-string Qt6 DOS string field"
                    )
                extras.append({"path": child_path, "value": child})
            else:
                normalized, nested = strip_formatter_extras(
                    child,
                    child_path,
                )
                stripped[key] = normalized
                extras.extend(nested)
        return stripped, extras
    if isinstance(value, list):
        stripped_items = []
        for index, child in enumerate(value):
            normalized, nested = strip_formatter_extras(
                child,
                f"{path}[{index}]",
            )
            stripped_items.append(normalized)
            extras.extend(nested)
        return stripped_items, extras
    return value, extras


def build_report(
    corpus_dir: pathlib.Path,
    qt5_report_path: pathlib.Path,
) -> dict[str, Any]:
    manifest, samples, manifest_bytes = BASE.load_fixture(
        ROOT,
        corpus_dir,
    )
    manifest_sha256 = QT6.sha256(manifest_bytes)
    qt5, qt5_sha256 = load_qt5_reference(
        qt5_report_path,
        manifest_sha256,
    )
    source_audit_path = (
        ROOT
        / "docs"
        / "research"
        / "data"
        / "dos-dispatch-source-audit.json"
    )
    if QT6.sha256(source_audit_path.read_bytes()) != SOURCE_AUDIT_SHA256:
        raise ValueError("DOS dispatch source audit drift")

    identity = inspect_qt6_image()
    raw_artifacts: dict[str, dict[str, Any]] = {}
    cases = {}
    known_differences = []
    for sample in samples:
        name = sample["name"]
        arguments = (
            "--json",
            *BASE.SHARED.SHARED.DATABASE_ARGS,
            f"/corpus/{name}",
        )
        executions = []
        stable_projections = []
        for _ in range(QT6.REPETITIONS):
            process = QT6.observe(corpus_dir, arguments)
            if process.returncode != 0:
                raise ValueError(f"Qt6 DOS dispatch failed: {name}")
            (
                json_bytes,
                _document,
                diagnostics,
                normalized_diagnostics,
            ) = split_json_and_diagnostics(process.stdout)
            tree = BASE.SHARED.SHARED.json_detect_tree(json_bytes)
            if not isinstance(tree, list):
                raise ValueError(f"Qt6 DOS JSON tree is invalid: {name}")
            stripped_document, formatter_extras = (
                strip_formatter_extras(_document)
            )
            if stripped_document != {"detects": tree}:
                raise ValueError(
                    f"unclassified Qt6 DOS JSON fields: {name}"
                )
            failures = BASE.SHARED.expectation_failures(
                f"cases.{name}.qt6",
                tree,
                sample["expected_dispatch"],
            )
            if failures:
                raise ValueError(
                    f"Qt6 DOS dispatch expectation failed: {name}"
                )
            stable_projections.append(
                (
                    json_bytes,
                    process.stderr,
                    normalized_diagnostics,
                    tree,
                    formatter_extras,
                )
            )
            executions.append(
                {
                    "arguments": list(arguments),
                    "exit_code": process.returncode,
                    "stdout": QT6.raw_stream(
                        process.stdout,
                        raw_artifacts,
                    ),
                    "stderr": QT6.raw_stream(
                        process.stderr,
                        raw_artifacts,
                    ),
                    "json_document_sha256": QT6.sha256(json_bytes),
                    "diagnostics": QT6.raw_stream(
                        diagnostics,
                        raw_artifacts,
                    ),
                    "normalized_diagnostics": (
                        normalized_diagnostics.decode("utf-8")
                    ),
                    "normalized_diagnostics_sha256": QT6.sha256(
                        normalized_diagnostics
                    ),
                    "formatter_extras": formatter_extras,
                    "detect_tree": tree,
                }
            )
        if stable_projections[0] != stable_projections[1]:
            raise ValueError(
                f"Qt6 DOS normalized output is unstable: {name}"
            )

        qt5_case = qt5["cases"][name]["oracles"][
            "linux-qt5-cmake"
        ]
        if stable_projections[0][3] != qt5_case["detect_tree"]:
            raise ValueError(f"Qt5/Qt6 DOS semantics differ: {name}")
        differences = []
        if (
            executions[0]["json_document_sha256"]
            != qt5_case["stdout_sha256"]
        ):
            if not stable_projections[0][4]:
                raise ValueError(
                    f"unclassified Qt5/Qt6 DOS JSON difference: {name}"
                )
            differences.append("stdout_json_fields")
        diagnostics = stable_projections[0][2]
        if diagnostics:
            differences.append("stdout_diagnostics")
        qt5_stderr_sha256 = qt5_case["stderr_sha256"]
        qt6_stderr = stable_projections[0][1]
        if executions[0]["stderr"]["sha256"] != qt5_stderr_sha256:
            if (
                qt5_case["stderr_bytes"] != 0
                or qt6_stderr != QT6_WARNING
            ):
                raise ValueError(
                    f"unclassified Qt5/Qt6 DOS stderr: {name}"
                )
            differences.append("stderr")
        if differences:
            known_differences.append(
                {
                    "case": name,
                    "streams": differences,
                    "normalized_stdout_diagnostics": (
                        executions[0][
                            "normalized_diagnostics"
                        ]
                    ),
                    "normalized_stdout_diagnostics_sha256": (
                        executions[0][
                            "normalized_diagnostics_sha256"
                        ]
                    ),
                    "qt6_formatter_extras": executions[0][
                        "formatter_extras"
                    ],
                    "qt5_stderr_sha256": qt5_stderr_sha256,
                    "qt6_stderr_sha256": QT6.sha256(qt6_stderr),
                    "semantic_dispatch_equal": True,
                }
            )
        cases[name] = {
            "case_kind": sample["case_kind"],
            "target_filetype": sample["target_filetype"],
            "expected_dispatch": sample["expected_dispatch"],
            "size": sample["size"],
            "sha256": sample["sha256"],
            "qt5_cmake": {
                key: qt5_case[key]
                for key in (
                    "exit_code",
                    "stdout_bytes",
                    "stdout_sha256",
                    "stderr_bytes",
                    "stderr_sha256",
                    "detect_tree",
                )
            },
            "qt6_executions": executions,
            "comparison": {
                "semantic_dispatch_equal": True,
                "raw_stream_differences": differences,
            },
        }

    relationships = {
        "seven_public_filetype_positives_match_qt5": True,
        "all_twelve_boundary_controls_match_qt5": True,
        "dos4g_near_magic_falls_back_to_dos16m": True,
        "com_size_and_suffix_boundaries_match_qt5": True,
        "qt6_two_repetitions_are_equal_after_address_normalization": True,
        "all_json_document_differences_are_classified": True,
        "all_stdout_and_stderr_differences_are_classified": True,
    }
    return {
        "schema_version": 1,
        "generator": "tools/upstream/probe_qt6_dos_dispatch.py",
        "generator_sha256": QT6.sha256(
            pathlib.Path(__file__).read_bytes()
        ),
        "shared_probe": (
            "tools/upstream/probe_qt6_legacy_dispatch.py"
        ),
        "shared_probe_sha256": QT6.sha256(
            pathlib.Path(QT6.__file__).read_bytes()
        ),
        "result": "pass",
        "upstream_commit": UPSTREAM_COMMIT,
        "rules_commit": RULES_COMMIT,
        "formats_commit": FORMATS_COMMIT,
        "xarchive_commit": XARCHIVE_COMMIT,
        "platform": "linux-amd64-qt5-qt6",
        "capability": "CAP-DISPATCH-002",
        "scope": {
            "public_filetypes": sorted(BASE.EXPECTED_FILETYPES),
            "excluded_member": "BW DOS16M",
            "excluded_member_evidence": (
                "docs/research/data/"
                "dos-dispatch-source-audit.json"
            ),
        },
        "corpus_manifest": {
            "path": "docs/research/data/dos-dispatch-corpus.json",
            "sha256": manifest_sha256,
            "sample_count": len(manifest["samples"]),
        },
        "source_audit": {
            "path": (
                "docs/research/data/"
                "dos-dispatch-source-audit.json"
            ),
            "sha256": SOURCE_AUDIT_SHA256,
        },
        "qt5_reference": {
            "path": (
                "docs/research/data/dos-dispatch-linux-qt5.json"
            ),
            "sha256": qt5_sha256,
            "oracle": "linux-qt5-cmake",
        },
        "qt6_oracle": identity,
        "resource_limits": {
            "network": "none",
            "cpus": 1,
            "memory_bytes": 512 * 1024 * 1024,
            "pids": 128,
            "timeout_seconds_per_execution": 60,
            "fixture_mount": "read-only",
            "container_root": "read-only",
        },
        "repetitions": QT6.REPETITIONS,
        "cases": cases,
        "known_differences": known_differences,
        "raw_artifacts": raw_artifacts,
        "relationships": relationships,
        "failures": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-dir", required=True, type=pathlib.Path)
    parser.add_argument(
        "--qt5-report",
        type=pathlib.Path,
        default=(
            ROOT
            / "docs"
            / "research"
            / "data"
            / "dos-dispatch-linux-qt5.json"
        ),
    )
    parser.add_argument("--output", required=True, type=pathlib.Path)
    args = parser.parse_args()
    report = build_report(
        args.corpus_dir.resolve(),
        args.qt5_report.resolve(),
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
