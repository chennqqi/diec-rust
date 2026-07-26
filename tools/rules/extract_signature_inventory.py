#!/usr/bin/env python3
"""Extract a deterministic unsupported-signature inventory from a trace report."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
FORMATS_COMMIT = "1151e7254fdee3c0294ff7095edbdd7bfccf8201"
XSCANENGINE_COMMIT = "dfe4a419e4f491bb23688ba03c5a5bf39e34da83"


def load_json(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(document, dict):
        raise ValueError("trace root must be a JSON object")
    return document


def extract_inventory(trace: dict[str, Any]) -> dict[str, Any]:
    if trace.get("operation") != (
        "diagnostic invocation of all fixed-order Binary detect functions"
    ):
        raise ValueError("input is not a Binary detect diagnostic report")
    if trace.get("attempted_detect_count") != 292:
        raise ValueError("trace must contain all 292 fixed-order Binary rules")
    if not trace.get("completed"):
        raise ValueError("trace is incomplete")

    observations = trace.get("observations")
    if not isinstance(observations, list):
        raise ValueError("trace observations are missing")

    patterns: set[str] = set()
    calling_rules: list[str] = []
    call_total = 0
    for observation in observations:
        if not isinstance(observation, dict):
            raise ValueError("trace observation must be an object")
        if observation.get("unsupported_signature_patterns_truncated"):
            raise ValueError(
                f"signature capture was truncated for {observation.get('name')}"
            )
        count = observation.get("unsupported_signature_call_count")
        calls = observation.get("unsupported_signature_patterns")
        if not isinstance(count, int) or count < 0:
            raise ValueError("invalid unsupported signature call count")
        if not isinstance(calls, list) or not all(
            isinstance(pattern, str) for pattern in calls
        ):
            raise ValueError("invalid unsupported signature pattern list")
        if count != len(calls):
            raise ValueError(
                f"uncapped call count does not match captured calls for "
                f"{observation.get('name')}"
            )
        if count:
            name = observation.get("name")
            if not isinstance(name, str):
                raise ValueError("calling rule name is missing")
            calling_rules.append(name)
            call_total += count
            patterns.update(calls)

    sorted_patterns = sorted(patterns)
    pattern_bytes = "\n".join(sorted_patterns).encode("utf-8")
    reported_patterns = trace.get("unsupported_signature_patterns")
    if sorted_patterns != reported_patterns:
        raise ValueError("per-rule patterns do not match the trace summary")
    if call_total != trace.get("unsupported_signature_call_total"):
        raise ValueError("per-rule call total does not match the trace summary")
    trace_input = trace.get("input")
    if not isinstance(trace_input, dict):
        raise ValueError("trace input identity is missing")
    input_path = trace_input.get("path")
    input_bytes = trace_input.get("bytes")
    if not isinstance(input_path, str) or not isinstance(input_bytes, int):
        raise ValueError("trace input path or size is invalid")

    return {
        "schema_version": SCHEMA_VERSION,
        "generator": {
            "path": "tools/rules/extract_signature_inventory.py",
            "version": 1,
        },
        "upstream_commit": UPSTREAM_COMMIT,
        "formats_commit": FORMATS_COMMIT,
        "xscanengine_commit": XSCANENGINE_COMMIT,
        "scope": (
            "patterns dynamically passed to the diagnostic X.c wrapper for one "
            "fixed generated sample; not a complete static rule-language inventory"
        ),
        "source_trace": {
            "operation": trace["operation"],
            "input": {
                "name": Path(input_path).name,
                "bytes": input_bytes,
            },
            "order_manifest": trace["order_manifest"],
            "order_sha256": trace["order_sha256"],
            "attempted_detect_count": trace["attempted_detect_count"],
        },
        "calling_rule_count": len(calling_rules),
        "calling_rules": calling_rules,
        "pattern_call_count": call_total,
        "pattern_count": len(sorted_patterns),
        "patterns_lf_sha256": hashlib.sha256(pattern_bytes).hexdigest(),
        "patterns_lf_hash_contract": (
            "UTF-8 of ordinally sorted patterns joined by LF without trailing LF"
        ),
        "patterns": sorted_patterns,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    inventory = extract_inventory(load_json(args.trace))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
