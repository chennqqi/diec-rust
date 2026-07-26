#!/usr/bin/env python3
"""Capture pinned Qt 5/Qt 6 native global HostApi behavior oracles."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import subprocess
from typing import Any


UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
DIE_SCRIPT_COMMIT = "5d82316c110abf0eb863b50bc679d330e05067b6"
RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
QT5_IMAGE = "diec-rust/upstream-global-host-api-harness:74eaf505"
QT6_IMAGE = "diec-rust/upstream-global-host-api-harness-qt6:74eaf505"
DEFAULT_BINARY = "/opt/die-build/src/console/diec-global-host-api-harness"
QT5_GLOBALS = (
    "includeScript",
    "_log",
    "_setResult",
    "_isResultPresent",
    "_getNumberOfResults",
    "_removeResult",
    "_isStop",
    "_encodingList",
    "_isConsoleMode",
    "_isLiteMode",
    "_isGuiMode",
    "_isLibraryMode",
    "_breakScan",
    "_getEngineVersion",
    "_getOS",
)
QT6_ALLOWED_ERRORS = {
    "_log()": "%entry@file:log-missing.js:1",
    "_setResult()": "%entry@file:missing-set-result.js:1",
    "_isResultPresent()": "%entry@file:missing-is-present.js:1",
    "_getNumberOfResults()": "%entry@file:missing-count.js:1",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _evaluation(step: dict[str, Any]) -> dict[str, Any]:
    return step["evaluation"]


def _record_names(step: dict[str, Any]) -> list[str]:
    return [record["name"] for record in step["records"]]


def validate_observation(
    observation: dict[str, Any],
    runtime: str = "qt5",
) -> None:
    if runtime not in {"qt5", "qt6"}:
        raise ValueError("unsupported runtime profile")
    identities = {
        "schema_version": 1,
        "upstream_commit": UPSTREAM_COMMIT,
        "die_script_commit": DIE_SCRIPT_COMMIT,
        "rules_commit": RULES_COMMIT,
        "qt_version": "5.15.13" if runtime == "qt5" else "6.4.2",
    }
    for key, expected in identities.items():
        if observation.get(key) != expected:
            raise ValueError(f"unexpected {key}")

    observed_errors: dict[str, str] = {}

    def validate_errors(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("is_error") is True:
                source = value.get("source", "")
                if runtime != "qt6" or source not in QT6_ALLOWED_ERRORS:
                    raise ValueError("unexpected JavaScript error")
                if (
                    value.get("error_name") != "Error"
                    or value.get("error_message") != "Insufficient arguments"
                    or value.get("error_line") != 1
                    or value.get("string")
                    != "Error: Insufficient arguments"
                    or value.get("backtrace")
                    != [QT6_ALLOWED_ERRORS[source]]
                ):
                    raise ValueError("unexpected Qt6 missing-argument error")
                observed_errors[source] = value["error_message"]
            for child in value.values():
                validate_errors(child)
        elif isinstance(value, list):
            for child in value:
                validate_errors(child)

    validate_errors(observation)
    expected_error_sources = (
        set() if runtime == "qt5" else set(QT6_ALLOWED_ERRORS)
    )
    if set(observed_errors) != expected_error_sources:
        raise ValueError("missing expected JavaScript error")

    methods = observation["surface"]["methods"]
    if set(methods) != set(QT5_GLOBALS) | {"_getQtVersion"}:
        raise ValueError("unexpected native global surface")
    for name in (
        QT5_GLOBALS
        if runtime == "qt5"
        else QT5_GLOBALS + ("_getQtVersion",)
    ):
        if methods[name]["type"].get("string") != "function":
            raise ValueError(f"{name} is not a function")
        if methods[name]["length"].get("number") != 0:
            raise ValueError(f"{name} wrapper length is not zero")
    if runtime == "qt5":
        if (
            methods["_getQtVersion"]["type"].get("string") != "undefined"
            or not methods["_getQtVersion"]["length"]["is_null"]
        ):
            raise ValueError("Qt5 unexpectedly exposes _getQtVersion")

    steps = observation["results"]["steps"]
    if [len(step["records"]) for step in steps] != [1, 2, 2, 2, 1, 1, 1]:
        raise ValueError("unexpected result mutation sequence")
    if _record_names(steps[1]) != ["Rust", "rust"]:
        raise ValueError("case-insensitive duplicate was not retained")
    if _evaluation(steps[2]).get("boolean") is not True:
        raise ValueError("case-insensitive result lookup failed")
    if _evaluation(steps[3]).get("number") != 2:
        raise ValueError("empty result type did not count all records")
    if _record_names(steps[4]) != ["rust"]:
        raise ValueError("removeResult did not remove only the first match")
    if _record_names(steps[5]) != ["rust"]:
        raise ValueError("removed result was not blocked from re-add")
    if _record_names(steps[6]) != ["rust"]:
        raise ValueError("empty removeResult name unexpectedly acted as wildcard")

    array_removal = observation["array_removal"]
    if [record["name"] for record in array_removal["before"]] != [
        "Enigma",
        "Denuvo",
    ]:
        raise ValueError("unexpected array-removal fixture seed")
    if _record_names(array_removal["removal"]) != ["Enigma", "Denuvo"]:
        raise ValueError("array removeResult unexpectedly removed records")
    if _record_names(array_removal["add_combined"]) != ["Enigma", "Denuvo"]:
        raise ValueError("array string block did not suppress combined result")

    missing = observation["missing_arguments"]
    missing_record = missing["set_result"]["records"]
    if runtime == "qt5":
        if len(missing_record) != 1 or {
            missing_record[0][key]
            for key in ("type", "name", "version", "info")
        } != {"undefined"}:
            raise ValueError("missing _setResult arguments did not stringify")
        if _evaluation(missing["is_present"]).get("boolean") is not True:
            raise ValueError(
                "missing result query did not match undefined record"
            )
        if _evaluation(missing["count"]).get("number") != 1:
            raise ValueError("missing result count did not count all records")
    elif (
        missing_record
        or not _evaluation(missing["set_result"])["is_error"]
        or not _evaluation(missing["is_present"])["is_error"]
        or not _evaluation(missing["count"])["is_error"]
    ):
        raise ValueError("Qt6 missing arguments did not fail atomically")

    stop = observation["stop"]
    if stop["compiler"]["records"]:
        raise ValueError("first-wrapper compiler result was retained")
    if len(stop["protection"]["records"]) != 1:
        raise ValueError("first-wrapper protection result was not retained")
    if not stop["protection"]["engine_is_stopped"]:
        raise ValueError("first-wrapper internal stop was not set")
    if _evaluation(stop["js_stop_before_break"]).get("boolean") is not False:
        raise ValueError("_isStop unexpectedly observes internal wrapper stop")
    if _evaluation(stop["js_stop_after_break"]).get("boolean") is not True:
        raise ValueError("_breakScan did not set the PDSTRUCT stop")

    include = observation["include"]
    if _evaluation(include["value_after_first"]).get("number") != 1:
        raise ValueError("case-insensitive include failed")
    if _evaluation(include["value_after_second"]).get("number") != 2:
        raise ValueError("repeated include did not re-evaluate")
    if include["error_messages"] != ["Cannot find: missing-include"]:
        raise ValueError("unexpected missing include diagnostic")

    info = observation["info"]
    if runtime == "qt5":
        if info["log_messages"] != ["undefined", "null", "42"]:
            raise ValueError("_log conversion behavior changed")
        if _evaluation(info["encoding_call"]).get("boolean") is not False:
            raise ValueError("_encodingList return value changed")
        if (
            info["encoding_message_count"] != 104
            or info["encoding_first"] != ""
            or info["encoding_last"] != "TIS-620"
            or info["encoding_messages_sha256"]
            != (
                "4ca2afaa9d6924630d5329ad327d6651d"
                "eb705e8bc4ecc9b46fecaf030474d02"
            )
        ):
            raise ValueError("encoding list behavior changed")
    elif (
        info["log_messages"] != ["", "42"]
        or not _evaluation(info["missing"])["is_error"]
        or not _evaluation(info["encoding_call"])["is_undefined"]
        or info["encoding_message_count"] != 0
        or info["encoding_first"] != ""
        or info["encoding_last"] != ""
        or info["encoding_messages_sha256"] != sha256(b"")
    ):
        raise ValueError("unexpected Qt6 log/encoding behavior")

    modes = observation["modes"]
    if (
        modes["die"]["application_name"] != "die"
        or modes["die"]["console"].get("boolean") is not True
        or modes["die"]["gui"].get("boolean") is not False
        or modes["die"]["lite"].get("boolean") is not False
        or modes["die"]["library"].get("boolean") is not False
    ):
        raise ValueError("console mode behavior changed")
    if modes["diel"]["lite"].get("boolean") is not True:
        raise ValueError("lite mode behavior changed")
    if (
        modes["empty_requested"]["application_name"]
        != "diec-global-host-api-harness"
        or modes["empty_requested"]["library"].get("boolean") is not False
    ):
        raise ValueError("empty application-name fallback changed")
    version = modes["engine_version"].get("string", "")
    if not re.fullmatch(r"9\.9\.9\.\d{4}\.\d{2}\.\d{2}", version):
        raise ValueError("engine version does not expose the compile date")
    if modes["os"].get("string") != "Linux Ubuntu x64":
        raise ValueError("unexpected fixed oracle OS string")
    if runtime == "qt5":
        if "qt_version" in modes:
            raise ValueError("Qt5 unexpectedly called _getQtVersion")
    elif modes["qt_version"].get("string") != "6.4.2":
        raise ValueError("Qt6 _getQtVersion return changed")


def parse_observation(
    stdout: bytes,
    stderr: bytes,
    returncode: int,
    runtime: str = "qt5",
) -> dict[str, Any]:
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
    validate_observation(observation, runtime)
    return observation


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
    repo: pathlib.Path,
    runtime: str = "qt5",
    image: str | None = None,
    binary: str = DEFAULT_BINARY,
) -> dict[str, Any]:
    if runtime not in {"qt5", "qt6"}:
        raise ValueError("unsupported runtime profile")
    if image is None:
        image = QT5_IMAGE if runtime == "qt5" else QT6_IMAGE
    image_id, revision = inspect_image(image)
    process = observe(image, binary)
    observation = parse_observation(
        process.stdout, process.stderr, process.returncode, runtime
    )
    sources = {}
    for relative in (
        "tools/upstream/global_host_api_harness_main.cpp",
        f"tools/upstream/Dockerfile.global-host-api-harness-{runtime}",
        "tools/upstream/probe_global_host_api.py",
    ):
        data = (repo / relative).read_bytes()
        sources[relative] = {"bytes": len(data), "sha256": sha256(data)}
    return {
        "schema_version": 1,
        "generator": "tools/upstream/probe_global_host_api.py",
        "runtime_profile": runtime,
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
    parser.add_argument("--runtime", choices=("qt5", "qt6"), default="qt5")
    parser.add_argument("--image")
    parser.add_argument("--binary", default=DEFAULT_BINARY)
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()
    output = args.output or (
        repo / f"docs/research/data/global-host-api-{args.runtime}.json"
    )
    report = build_report(repo, args.runtime, args.image, args.binary)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
