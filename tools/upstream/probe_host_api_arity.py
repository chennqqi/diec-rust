#!/usr/bin/env python3
"""Capture the pinned Qt5 QObject HostApi arity/error oracle."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
from typing import Any


UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
XSCANENGINE_COMMIT = "dfe4a419e4f491bb23688ba03c5a5bf39e34da83"
RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
PE_INIT_SHA256 = (
    "26f5912c5ac137ed44d0d9edade8d3ce65501a61ce06d0491db5e1faa59c1f90"
)
DEFAULT_IMAGE = "diec-rust/upstream-host-api-arity-harness:74eaf505"
DEFAULT_BINARY = "/opt/die-build/src/console/diec-host-api-arity-harness"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_observation(stdout: bytes, stderr: bytes, returncode: int) -> dict[str, Any]:
    if returncode != 0:
        raise ValueError(f"harness exited with {returncode}")
    if stderr:
        raise ValueError("harness wrote stderr")
    try:
        text = stdout.decode("utf-8")
        observation, end = json.JSONDecoder().raw_decode(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("harness did not emit one UTF-8 JSON document") from error
    if text[end:].strip():
        raise ValueError("harness emitted trailing stdout")
    validate_observation(observation)
    return observation


def _semantic_value(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != "source"}


def validate_observation(observation: dict[str, Any]) -> None:
    identities = {
        "schema_version": 1,
        "upstream_commit": UPSTREAM_COMMIT,
        "xscanengine_commit": XSCANENGINE_COMMIT,
        "rules_commit": RULES_COMMIT,
        "qt_version": "5.15.13",
    }
    for key, expected in identities.items():
        if observation.get(key) != expected:
            raise ValueError(f"unexpected {key}")
    if observation.get("pe_init", {}).get("sha256") != PE_INIT_SHA256:
        raise ValueError("unexpected PE _init identity")

    binary = observation["binary"]
    for name in ("u8", "sa", "sc"):
        exact = binary[f"{name}_exact"]
        extra = binary[f"{name}_extra"]
        if exact["is_error"] or extra["is_error"]:
            raise ValueError(f"{name} invocation raised an exception")
        if _semantic_value(exact) != _semantic_value(extra):
            raise ValueError(f"{name} extra arguments changed the result")
        length = binary[f"{name}_function_length"]
        if not length["is_number"] or length.get("number") != 0:
            raise ValueError(f"{name} wrapper length is not zero")

    pe = observation["pe"]
    if pe["init_evaluation"]["is_error"]:
        raise ValueError("PE _init evaluation failed")
    expected_types = {
        "get_ep_signature_type_before_init": "undefined",
        "get_ep_signature_type_after_init": "undefined",
        "get_entry_point_signature_type_before_init": "undefined",
        "get_entry_point_signature_type_after_init": "function",
    }
    for key, expected in expected_types.items():
        if pe[key].get("string") != expected:
            raise ValueError(f"unexpected PE method type: {key}")
    error = pe["get_ep_signature_call"]
    if (
        not error["is_error"]
        or error.get("error_name") != "TypeError"
        or "PE.getEPSignature" not in error.get("error_message", "")
        or error.get("error_line") != 1
    ):
        raise ValueError("unexpected PE.getEPSignature failure")


def inspect_image(image: str) -> tuple[str, str]:
    process = subprocess.run(
        ["docker", "image", "inspect", image],
        check=True,
        capture_output=True,
    )
    document = json.loads(process.stdout)[0]
    revision = document["Config"]["Labels"].get(
        "org.opencontainers.image.revision", ""
    )
    if revision != UPSTREAM_COMMIT:
        raise ValueError("harness image revision mismatch")
    return document["Id"], revision


def binary_sha256(image: str, binary: str) -> str:
    process = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            image,
            "sha256sum",
            binary,
        ],
        check=True,
        capture_output=True,
    )
    return process.stdout.decode("ascii").split()[0]


def observe(image: str, binary: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--memory",
            "512m",
            "--cpus",
            "1",
            "--pids-limit",
            "128",
            image,
            binary,
        ],
        check=False,
        capture_output=True,
    )


def build_report(
    repo: pathlib.Path, image: str = DEFAULT_IMAGE, binary: str = DEFAULT_BINARY
) -> dict[str, Any]:
    image_id, revision = inspect_image(image)
    process = observe(image, binary)
    observation = parse_observation(
        process.stdout, process.stderr, process.returncode
    )

    init = observation["pe"]["init_evaluation"]
    init_source = init.pop("source").encode("utf-8")
    if sha256(init_source) != PE_INIT_SHA256:
        raise ValueError("evaluated PE _init source identity mismatch")
    init["source_bytes"] = len(init_source)
    init["source_sha256"] = sha256(init_source)

    sources = {}
    for relative in (
        "tools/upstream/host_api_arity_harness_main.cpp",
        "tools/upstream/Dockerfile.host-api-arity-harness-qt5",
        "tools/upstream/probe_host_api_arity.py",
    ):
        data = (repo / relative).read_bytes()
        sources[relative] = {"bytes": len(data), "sha256": sha256(data)}

    return {
        "schema_version": 1,
        "generator": "tools/upstream/probe_host_api_arity.py",
        "image": {
            "name": image,
            "id": image_id,
            "revision": revision,
        },
        "binary": {"path": binary, "sha256": binary_sha256(image, binary)},
        "sources": sources,
        "observation": observation,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    repo = pathlib.Path(__file__).resolve().parents[2]
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--binary", default=DEFAULT_BINARY)
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=repo / "docs/research/data/host-api-arity-qt5.json",
    )
    args = parser.parse_args()
    report = build_report(repo, args.image, args.binary)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
