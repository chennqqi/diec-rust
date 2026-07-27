#!/usr/bin/env python3
"""Probe the pinned DIE aggressive archive 100000-record boundary."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


SCHEMA_VERSION = 1
CAPABILITY = "CAP-GAP-006"
EXPECTED_REVISION = "74eaf505c250ab47e709024e9dc41657cd8f2254"
EXPECTED_XSCANENGINE_COMMIT = "dfe4a419e4f491bb23688ba03c5a5bf39e34da83"
EXPECTED_SOURCE_SHA256 = (
    "e088bebb7c8345ce5832cc51de712c05"
    "a8b239873d7f092db3ae5566a761b498"
)
SOURCE_PATH = "/opt/die-source/XScanEngine/xscanengine.cpp"
CORPUS_GENERATOR = (
    "tools/corpus/generate_archive_iteration_boundary_fixture.py"
)
DEFAULT_BINARY = (
    "/opt/die-build/src/console/"
    "diec-archive-iteration-boundary-harness"
)
RESOURCE_LIMITS = {
    "cpus": "1",
    "memory": "512m",
    "pids": 128,
    "wall_timeout_seconds": 30,
}
FAULT_INJECTION = {
    "placeholder_declared_size": 0x1000000,
    "temporary_directory": "/proc",
    "purpose": (
        "force placeholder QTemporaryFile allocation to fail before "
        "unpack/child scan while preserving archive-record iteration"
    ),
}
SOURCE_PATTERNS = {
    "aggressive_limit": "nLimit = 100000;",
    "hard_iteration_guard": "(i < 100000)",
    "current_index_initialization": "qint32 nCurrentIndex = 0;",
    "single_increment": "nCurrentIndex++;",
    "post_increment_limit_check": "if (nCurrentIndex > nLimit) {",
    "allocation_before_scan": (
        "XBinary::createFileBuffer("
        "archiveRecord.mapProperties.value("
        "XBinary::FPART_PROP_UNCOMPRESSEDSIZE).toLongLong(), "
        "pPdStruct)"
    ),
}


class ProbeError(ValueError):
    """The archive-iteration experiment or evidence is invalid."""


def reject_duplicate_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProbeError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_json(raw: bytes, description: str) -> dict[str, Any]:
    try:
        value = json.loads(
            raw,
            object_pairs_hook=reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProbeError(
            f"invalid {description} JSON: {error}"
        ) from error
    if not isinstance(value, dict):
        raise ProbeError(f"{description} root must be an object")
    return value


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_and_verify_corpus(
    corpus_dir: Path,
    reference_manifest: Path,
) -> tuple[dict[str, Any], bytes]:
    reference_raw = reference_manifest.read_bytes()
    reference = parse_json(reference_raw, "reference manifest")
    generated_raw = (corpus_dir / "manifest.json").read_bytes()
    generated = parse_json(generated_raw, "generated manifest")
    if generated_raw != reference_raw or generated != reference:
        raise ProbeError("generated corpus manifest differs from reference")
    if generated.get("schema_version") != 1:
        raise ProbeError("unsupported corpus schema")
    if generated.get("capability") != CAPABILITY:
        raise ProbeError("corpus capability mismatch")
    if generated.get("generator") != CORPUS_GENERATOR:
        raise ProbeError("corpus generator mismatch")

    samples = generated.get("samples")
    if not isinstance(samples, list) or len(samples) != 3:
        raise ProbeError("corpus must contain exactly three samples")
    names = set()
    for sample in samples:
        if not isinstance(sample, dict):
            raise ProbeError("corpus sample must be an object")
        name = sample.get("name")
        if (
            not isinstance(name, str)
            or Path(name).name != name
            or name in names
        ):
            raise ProbeError(
                f"invalid or duplicate sample name: {name!r}"
            )
        names.add(name)
        data = (corpus_dir / name).read_bytes()
        if len(data) != sample.get("size"):
            raise ProbeError(f"sample size mismatch: {name}")
        if sha256(data) != sample.get("sha256"):
            raise ProbeError(f"sample SHA-256 mismatch: {name}")

    actual_files = {
        path.name
        for path in corpus_dir.iterdir()
        if path.is_file()
    }
    if actual_files != names | {"manifest.json"}:
        raise ProbeError(
            "corpus directory contains missing or extra files"
        )
    return generated, reference_raw


def docker_inspect(image: str) -> dict[str, Any]:
    completed = subprocess.run(
        ["docker", "image", "inspect", image],
        check=True,
        capture_output=True,
    )
    value = json.loads(completed.stdout)
    if not isinstance(value, list) or len(value) != 1:
        raise ProbeError(
            "docker image inspect returned unexpected shape"
        )
    inspected = value[0]
    revision = (
        inspected.get("Config", {})
        .get("Labels", {})
        .get("org.opencontainers.image.revision")
    )
    if revision != EXPECTED_REVISION:
        raise ProbeError(
            f"image revision mismatch: {revision!r}"
        )
    return {
        "id": inspected["Id"],
        "repo_digests": sorted(
            inspected.get("RepoDigests") or []
        ),
        "revision": revision,
    }


def read_image_file(image: str, path: str) -> bytes:
    completed = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            image,
            "cat",
            path,
        ],
        check=True,
        capture_output=True,
    )
    if completed.stderr:
        raise ProbeError(
            f"unexpected stderr while reading {path}"
        )
    return completed.stdout


def observe_source(image: str) -> dict[str, Any]:
    source = read_image_file(image, SOURCE_PATH)
    source_hash = sha256(source)
    if source_hash != EXPECTED_SOURCE_SHA256:
        raise ProbeError(
            f"XScanEngine source SHA-256 mismatch: {source_hash}"
        )
    text = source.decode("utf-8")
    block_start = text.index(
        "if (pScanOptions->bIsArchivesScan) {"
    )
    block_end = text.index(
        "QList<XBinary::FPART> listFileParts;",
        block_start,
    )
    archive_block = text[block_start:block_end]
    counts = {
        name: archive_block.count(pattern)
        for name, pattern in SOURCE_PATTERNS.items()
    }
    if any(count < 1 for count in counts.values()):
        raise ProbeError(
            f"required source pattern missing: {counts}"
        )
    positions = {
        name: archive_block.index(pattern)
        for name, pattern in SOURCE_PATTERNS.items()
    }
    ordered = (
        positions["current_index_initialization"]
        < positions["hard_iteration_guard"]
        < positions["allocation_before_scan"]
        < positions["single_increment"]
        < positions["post_increment_limit_check"]
    )
    if not ordered:
        raise ProbeError(
            "archive-loop source operations are not in expected order"
        )
    return {
        "archive_block_end_line": (
            text[:block_end].count("\n") + 1
        ),
        "archive_block_start_line": (
            text[:block_start].count("\n") + 1
        ),
        "component_commit": EXPECTED_XSCANENGINE_COMMIT,
        "path": SOURCE_PATH,
        "required_pattern_counts": counts,
        "sha256": source_hash,
        "source_order_verified": ordered,
    }


def observe_binary(image: str, binary: str) -> dict[str, Any]:
    data = read_image_file(image, binary)
    return {
        "path": binary,
        "sha256": sha256(data),
        "size": len(data),
    }


def run_case(
    *,
    image: str,
    binary: str,
    corpus_dir: Path,
    sample_name: str,
) -> dict[str, Any]:
    logical_arguments = [f"/corpus/{sample_name}"]
    command = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--memory",
        RESOURCE_LIMITS["memory"],
        "--cpus",
        RESOURCE_LIMITS["cpus"],
        "--pids-limit",
        str(RESOURCE_LIMITS["pids"]),
        "--env",
        f"TMPDIR={FAULT_INJECTION['temporary_directory']}",
        "--env",
        "QT_LOGGING_RULES=*.warning=false",
        "-v",
        f"{corpus_dir}:/corpus:ro",
        image,
        binary,
        *logical_arguments,
    ]
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            timeout=RESOURCE_LIMITS["wall_timeout_seconds"],
        )
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout or b""
        stderr = error.stderr or b""
        return {
            "arguments": logical_arguments,
            "exit_code": None,
            "harness": None,
            "possible_oom_exit_137": False,
            "stderr": stderr.decode("utf-8", errors="replace"),
            "stderr_sha256": sha256(stderr),
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stdout_sha256": sha256(stdout),
            "timed_out": True,
            "wall_elapsed_ms": round(
                (time.monotonic() - started) * 1000
            ),
        }

    harness = None
    if completed.returncode == 0:
        harness = parse_json(
            completed.stdout,
            f"{sample_name} harness",
        )
    return {
        "arguments": logical_arguments,
        "exit_code": completed.returncode,
        "harness": harness,
        "possible_oom_exit_137": completed.returncode == 137,
        "stderr": completed.stderr.decode(
            "utf-8", errors="replace"
        ),
        "stderr_sha256": sha256(completed.stderr),
        "stdout": completed.stdout.decode(
            "utf-8", errors="replace"
        ),
        "stdout_sha256": sha256(completed.stdout),
        "timed_out": False,
        "wall_elapsed_ms": round(
            (time.monotonic() - started) * 1000
        ),
    }


def evaluate_report(report: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    by_sample = {
        case["sample"]: case for case in report["cases"]
    }
    for sample in report["corpus"]["samples"]:
        name = sample["name"]
        case = by_sample.get(name)
        if case is None:
            failures.append(f"{name}.missing")
            continue
        if case["exit_code"] != 0:
            failures.append(f"{name}.exit_code")
        if case["timed_out"]:
            failures.append(f"{name}.timed_out")
        if case["possible_oom_exit_137"]:
            failures.append(f"{name}.possible_oom")
        if case["stderr"]:
            failures.append(f"{name}.stderr")
        harness = case.get("harness")
        if not isinstance(harness, dict):
            failures.append(f"{name}.harness")
            continue
        reachable = sample["sentinel_ordinal"] <= 100000
        expected = {
            "aggressive_scan": True,
            "error_count": 0,
            "node_count": 2 if reachable else 1,
            "pdf_node_count": 1 if reachable else 0,
            "pd_stopped": False,
            "record_count": 3 if reachable else 1,
            "stream_node_count": 1 if reachable else 0,
        }
        for field, value in expected.items():
            if harness.get(field) != value:
                failures.append(f"{name}.{field}")
        if harness.get("elapsed_ms", -1) < 0:
            failures.append(f"{name}.elapsed_ms")
        if harness.get("peak_rss_before_kib", 0) <= 0:
            failures.append(f"{name}.peak_rss_before_kib")
        if (
            harness.get("peak_rss_after_kib", 0)
            < harness.get("peak_rss_before_kib", 0)
        ):
            failures.append(f"{name}.peak_rss_after_kib")

    source = report["source_contract"]
    if source["sha256"] != EXPECTED_SOURCE_SHA256:
        failures.append("source.sha256")
    if not source["source_order_verified"]:
        failures.append("source.order")
    if any(
        count < 1
        for count in source["required_pattern_counts"].values()
    ):
        failures.append("source.required_pattern")
    return failures


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


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--binary", default=DEFAULT_BINARY)
    parser.add_argument("--corpus-dir", required=True, type=Path)
    parser.add_argument(
        "--reference-manifest",
        type=Path,
        default=(
            root
            / "docs"
            / "research"
            / "data"
            / "archive-iteration-boundary-corpus.json"
        ),
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    corpus_dir = args.corpus_dir.resolve()
    corpus, manifest_raw = load_and_verify_corpus(
        corpus_dir,
        args.reference_manifest.resolve(),
    )
    cases = []
    for sample in corpus["samples"]:
        case = run_case(
            image=args.image,
            binary=args.binary,
            corpus_dir=corpus_dir,
            sample_name=sample["name"],
        )
        case["sample"] = sample["name"]
        cases.append(case)

    report: dict[str, Any] = {
        "capability": CAPABILITY,
        "cases": cases,
        "corpus": corpus,
        "corpus_manifest_sha256": sha256(manifest_raw),
        "environment": {
            "container_network": "none",
            "fault_injection": FAULT_INJECTION,
            "image": args.image,
            "image_identity": docker_inspect(args.image),
            "platform": "linux-x86_64-qt5",
            "resource_limits": RESOURCE_LIMITS,
        },
        "harness_binary": observe_binary(
            args.image, args.binary
        ),
        "schema_version": SCHEMA_VERSION,
        "source_contract": observe_source(args.image),
        "upstream_commit": EXPECTED_REVISION,
        "xscanengine_commit": EXPECTED_XSCANENGINE_COMMIT,
    }
    failures = evaluate_report(report)
    report["assertions"] = {
        "aggressive_member_limit_is_unreachable_before_hard_guard": (
            not any(
                failure.startswith("source.")
                for failure in failures
            )
        ),
        "record_100000_is_reachable": not any(
            failure.startswith("sentinel-100000.iso.")
            for failure in failures
        ),
        "record_100001_is_not_reachable": not any(
            failure.startswith("sentinel-100001.iso.")
            for failure in failures
        ),
        "record_99999_is_reachable_control": not any(
            failure.startswith("sentinel-099999.iso.")
            for failure in failures
        ),
    }
    report["failures"] = failures
    report["passed"] = not failures
    raw = serialize(report)
    if args.output is None:
        sys.stdout.buffer.write(raw)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(raw)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
