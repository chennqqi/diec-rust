#!/usr/bin/env python3
"""Build the evidence closure for the Linux Qt5 archive corpus gap."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import subprocess
from typing import Any


SCHEMA_VERSION = 1
EVALUATED_ON = "2026-07-28"
UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
FORMATS_COMMIT = "1151e7254fdee3c0294ff7095edbdd7bfccf8201"
FORMATS_REMOTE = "https://github.com/horsicq/Formats.git"
FORMATS_SOURCE_SHA256 = (
    "674eba0046eb6cc947e547d1ac0b93ac695cbb30f68e11f135e5551d81e0b115"
)
XSCANENGINE_COMMIT = "dfe4a419e4f491bb23688ba03c5a5bf39e34da83"
XSCANENGINE_REMOTE = "https://github.com/horsicq/XScanEngine"
XSCANENGINE_SOURCE_SHA256 = (
    "e088bebb7c8345ce5832cc51de712c05a8b239873d7f092db3ae5566a761b498"
)
CAPABILITY_IDS = (
    "CAP-DISPATCH-004",
    "CAP-NEST-003",
    "CAP-NEST-004",
    "CAP-NEST-009",
)
SCANABLE_FAMILIES = ("ZIP", "7Z", "RAR", "CAB", "ISO9660")
FAMILY_ADAPTERS = {
    "ZIP": "XZip",
    "7Z": "XSevenZip",
    "RAR": "XRar",
    "CAB": "XCab",
    "ISO9660": "XISO9660",
}
REPORTS = {
    "archive_adversarial": (
        "docs/research/data/archive-adversarial-engine-qt5.json",
        "f00210b660cbc45f6afb66599ea48b9285b392dd06fd9d686fef95148cc67937",
    ),
    "archive_format": (
        "docs/research/data/archive-format-engine-qt5.json",
        "d27ee4aa9c03be0939d495e6b9ab062f669f123eeff36ccfac16062d3089a784",
    ),
    "archive_iteration": (
        "docs/research/data/archive-iteration-boundary-engine-qt5.json",
        "57a78308860d6842bf2b33367451d696a7c3252d1411de2ed5c32d9659c29533",
    ),
    "archive_limit": (
        "docs/research/data/archive-limit-engine-qt5.json",
        "e4786dcc578fb0714c86f71955161f981a06be26aefe663281d74202f5372ecd",
    ),
    "generic_dispatch": (
        "docs/research/data/generic-archive-dispatch-engine-qt5.json",
        "960fca28122af3bddb2fcd22706f5350ee8f4753a79a61cc2338aba7d1f53c04",
    ),
    "npm_dispatch": (
        "docs/research/data/npm-dispatch-engine-qt5.json",
        "d23168aff29696f46d3579f6d914353865035bd02a8bbbcf9af065475c036ce7",
    ),
}
GENERATOR_PATH = "tools/research/build_archive_gap_closure.py"


class ClosureError(ValueError):
    """The archive gap cannot be closed from the supplied evidence."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ClosureError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: pathlib.Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    try:
        value = json.loads(
            raw,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ClosureError(f"non-finite JSON constant: {value}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ClosureError(f"invalid JSON: {path}: {error}") from error
    if not isinstance(value, dict):
        raise ClosureError(f"JSON root is not an object: {path}")
    return value, raw


def run_git(path: pathlib.Path, *arguments: str) -> str:
    process = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={path}",
            "-C",
            str(path),
            *arguments,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    if process.stderr:
        raise ClosureError(
            f"git wrote stderr: {path}: {' '.join(arguments)}"
        )
    return process.stdout.strip()


def verify_checkout(
    path: pathlib.Path, commit: str, remote: str
) -> dict[str, str]:
    if run_git(path, "rev-parse", "HEAD") != commit:
        raise ClosureError(f"checkout commit mismatch: {path}")
    if run_git(path, "status", "--porcelain"):
        raise ClosureError(f"checkout is dirty: {path}")
    actual_remote = run_git(path, "remote", "get-url", "origin")
    if actual_remote.rstrip("/").removesuffix(".git") != (
        remote.rstrip("/").removesuffix(".git")
    ):
        raise ClosureError(f"checkout remote mismatch: {path}")
    return {"commit": commit, "remote": remote}


def extract_braced_function(text: str, signature: str) -> str:
    start = text.find(signature)
    if start < 0:
        raise ClosureError(f"missing function signature: {signature}")
    opening = text.find("{", start + len(signature))
    if opening < 0:
        raise ClosureError(f"missing function body: {signature}")
    depth = 0
    for position in range(opening, len(text)):
        character = text[position]
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return text[start : position + 1]
    raise ClosureError(f"unterminated function body: {signature}")


def extract_scanable_families(function: str) -> tuple[str, ...]:
    matches = re.findall(
        r"if\s*\((?P<condition>[^{}]*?)\)\s*\{\s*"
        r"bScanableArchive\s*=\s*true\s*;",
        function,
        flags=re.DOTALL,
    )
    if len(matches) != 1:
        raise ClosureError("archive family gate count changed")
    condition = matches[0]
    token_pattern = (
        r"stFT\.contains\s*\(\s*XBinary::FT_([A-Z0-9_]+)\s*\)"
    )
    families = tuple(re.findall(token_pattern, condition))
    residue = re.sub(token_pattern, "", condition)
    residue = re.sub(r"\|\||\s+", "", residue)
    if residue:
        raise ClosureError(f"unexpected archive family gate syntax: {residue}")
    if len(families) != len(set(families)):
        raise ClosureError("duplicate archive family in engine gate")
    return families


def extract_family_adapters(function: str) -> dict[str, str]:
    adapters: dict[str, str] = {}
    for family, adapter in FAMILY_ADAPTERS.items():
        pattern = (
            rf"checkFileType\s*\(\s*XBinary::FT_{re.escape(family)}\s*,"
            rf"\s*fileType\s*\)\)\s*return\s+new\s+{adapter}\s*\("
        )
        count = len(re.findall(pattern, function))
        if count != 1:
            raise ClosureError(
                f"adapter mapping changed: {family} -> {adapter}: {count}"
            )
        adapters[family] = adapter
    return adapters


def require_true_map(
    value: Any, expected_keys: set[str], label: str
) -> None:
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise ClosureError(f"{label} assertion keys changed")
    if not all(item is True for item in value.values()):
        raise ClosureError(f"{label} contains a failed assertion")


def input_report(
    repository_root: pathlib.Path,
    label: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    relative, expected_hash = REPORTS[label]
    path = repository_root / relative
    report, raw = load_json(path)
    actual_hash = sha256(raw)
    if actual_hash != expected_hash:
        raise ClosureError(
            f"input report hash mismatch: {relative}: {actual_hash}"
        )
    if report.get("upstream_commit") != UPSTREAM_COMMIT:
        raise ClosureError(f"input report commit mismatch: {relative}")
    if report.get("passed") is not True:
        raise ClosureError(f"input report is not passing: {relative}")
    if report.get("failures") != []:
        raise ClosureError(f"input report contains failures: {relative}")
    return report, {
        "path": relative,
        "bytes": len(raw),
        "sha256": actual_hash,
    }


def family_runtime_evidence(
    archive_adversarial: dict[str, Any],
    archive_format: dict[str, Any],
    archive_limit: dict[str, Any],
) -> list[dict[str, Any]]:
    result = []
    zip_case = archive_adversarial["cases"]["deflate-valid.zip"]
    if zip_case["default"]["summary"]["stream_count"] != 0:
        raise ClosureError("ZIP default unexpectedly expands a member")
    zip_summary = zip_case["archive"]["summary"]
    if (
        zip_summary["stream_count"] != 1
        or zip_summary["streams"][0]["filetype"] != "PDF"
    ):
        raise ClosureError("ZIP archive positive case changed")
    depth_one = next(
        case
        for case in archive_limit["normal_cases"]
        if case["sample"] == "depth-01.zip"
    )
    if (
        depth_one["harness"]["stream_node_count"] != 1
        or depth_one["harness"]["pdf_node_count"] != 1
    ):
        raise ClosureError("ZIP nested positive case changed")
    result.append(
        {
            "family": "ZIP",
            "adapter": FAMILY_ADAPTERS["ZIP"],
            "case": "deflate-valid.zip",
            "default_stream_count": 0,
            "archive_stream_count": 1,
            "archive_stream_filetypes": ["PDF"],
            "nested_control": "depth-01.zip",
        }
    )

    case_map = {
        "7Z": "pdf-member.7z",
        "RAR": "pdf-member.rar",
        "CAB": "pdf-member.cab",
        "ISO9660": "pdf-member.iso",
    }
    for family, case_name in case_map.items():
        case = archive_format["cases"][case_name]
        default_summary = case["default"]["summary"]
        archive_summary = case["archive"]["summary"]
        if default_summary["stream_count"] != 0:
            raise ClosureError(
                f"{family} default unexpectedly expands a member"
            )
        if (
            archive_summary["stream_count"] != 1
            or archive_summary["stream_filetypes"] != ["PDF"]
        ):
            raise ClosureError(f"{family} archive positive case changed")
        result.append(
            {
                "family": family,
                "adapter": FAMILY_ADAPTERS[family],
                "case": case_name,
                "default_stream_count": 0,
                "archive_stream_count": 1,
                "archive_stream_filetypes": ["PDF"],
            }
        )
    if tuple(item["family"] for item in result) != SCANABLE_FAMILIES:
        raise ClosureError("runtime archive family order changed")
    return result


def limit_evidence(report: dict[str, Any]) -> dict[str, Any]:
    require_true_map(
        report["assertions"],
        {
            "cancellation_retains_partial_result",
            "depth_reaches_maximum_tested",
            "expanded_bytes_reach_maximum_tested",
            "source_has_no_independent_depth_or_total_token",
        },
        "archive limit",
    )
    source = report["source_contract"]
    if source["sha256"] != XSCANENGINE_SOURCE_SHA256:
        raise ClosureError("archive limit source hash changed")
    if set(source["negative_token_counts"].values()) != {0}:
        raise ClosureError("independent depth/total token appeared")

    samples = report["corpus"]["samples"]
    depth_sample = max(
        (sample for sample in samples if sample["series"] == "depth"),
        key=lambda sample: sample["depth"],
    )
    expanded_sample = max(
        (
            sample
            for sample in samples
            if sample["series"] == "expanded_bytes"
        ),
        key=lambda sample: sample["cumulative_expanded_bytes"],
    )
    cases = {case["sample"]: case for case in report["normal_cases"]}
    depth_case = cases[depth_sample["name"]]
    expanded_case = cases[expanded_sample["name"]]
    if (
        depth_sample["depth"] != 64
        or depth_case["harness"]["max_stream_depth"] != 64
        or depth_case["harness"]["deepest_pdf_depth"] != 64
    ):
        raise ClosureError("depth-64 observation changed")
    if (
        expanded_sample["cumulative_expanded_bytes"] != 33_554_546
        or expanded_case["harness"]["deepest_pdf_depth"] != 2
        or expanded_case["harness"]["pdf_node_count"] != 1
    ):
        raise ClosureError("expanded-byte observation changed")
    return {
        "maximum_observed_depth": 64,
        "maximum_observed_cumulative_expanded_bytes": 33_554_546,
        "source_has_no_independent_depth_or_total_token": True,
        "cancellation_retains_partial_result": True,
    }


def iteration_evidence(report: dict[str, Any]) -> dict[str, Any]:
    require_true_map(
        report["assertions"],
        {
            "aggressive_member_limit_is_unreachable_before_hard_guard",
            "record_100000_is_reachable",
            "record_100001_is_not_reachable",
            "record_99999_is_reachable_control",
        },
        "archive iteration",
    )
    if (
        report["source_contract"]["sha256"]
        != XSCANENGINE_SOURCE_SHA256
        or report["source_contract"]["source_order_verified"] is not True
    ):
        raise ClosureError("archive iteration source contract changed")
    cases = {
        case["sample"]: case["harness"] for case in report["cases"]
    }
    expected = {
        "sentinel-099999.iso": 1,
        "sentinel-100000.iso": 1,
        "sentinel-100001.iso": 0,
    }
    for sample, pdf_count in expected.items():
        if cases[sample]["pdf_node_count"] != pdf_count:
            raise ClosureError(f"archive iteration case changed: {sample}")
    return {
        "hard_iteration_guard": 100_000,
        "record_99999_reachable": True,
        "record_100000_reachable": True,
        "record_100001_reachable": False,
        "aggressive_scanable_member_limit": (
            "unreachable before hard iteration guard"
        ),
    }


def build_report(
    repository_root: pathlib.Path,
    formats_root: pathlib.Path,
    xscanengine_root: pathlib.Path,
) -> dict[str, Any]:
    formats_identity = verify_checkout(
        formats_root, FORMATS_COMMIT, FORMATS_REMOTE
    )
    xscanengine_identity = verify_checkout(
        xscanengine_root, XSCANENGINE_COMMIT, XSCANENGINE_REMOTE
    )
    formats_path = formats_root / "xformats.cpp"
    xscanengine_path = xscanengine_root / "xscanengine.cpp"
    formats_raw = formats_path.read_bytes()
    xscanengine_raw = xscanengine_path.read_bytes()
    if sha256(formats_raw) != FORMATS_SOURCE_SHA256:
        raise ClosureError("Formats source hash changed")
    if sha256(xscanengine_raw) != XSCANENGINE_SOURCE_SHA256:
        raise ClosureError("XScanEngine source hash changed")

    formats_function = extract_braced_function(
        formats_raw.decode("utf-8"),
        "XBinary *XFormats::createClass(",
    )
    scan_function = extract_braced_function(
        xscanengine_raw.decode("utf-8"),
        "void XScanEngine::scanProcess(",
    )
    families = extract_scanable_families(scan_function)
    if families != SCANABLE_FAMILIES:
        raise ClosureError(
            f"engine archive family set changed: {families}"
        )
    adapters = extract_family_adapters(formats_function)

    reports: dict[str, dict[str, Any]] = {}
    input_records: dict[str, dict[str, Any]] = {}
    for label in REPORTS:
        reports[label], input_records[label] = input_report(
            repository_root, label
        )

    family_evidence = family_runtime_evidence(
        reports["archive_adversarial"],
        reports["archive_format"],
        reports["archive_limit"],
    )
    limits = limit_evidence(reports["archive_limit"])
    iteration = iteration_evidence(reports["archive_iteration"])
    if not reports["generic_dispatch"]["facts"][
        "natural_detection_pairs_archive_with_concrete_subtype"
    ]:
        raise ClosureError("generic archive dispatch fact changed")
    if not reports["npm_dispatch"]["facts"][
        "automatic_scan_falls_back_to_binary_unknown"
    ]:
        raise ClosureError("NPM public fallback fact changed")
    generator_raw = (repository_root / GENERATOR_PATH).read_bytes()

    return {
        "schema_version": SCHEMA_VERSION,
        "evaluated_on": EVALUATED_ON,
        "result": "closed",
        "upstream_commit": UPSTREAM_COMMIT,
        "platform": "linux-x86_64-qt5",
        "generator": {
            "path": GENERATOR_PATH,
            "bytes": len(generator_raw),
            "sha256": sha256(generator_raw),
        },
        "gap": {
            "id": "CAP-GAP-006",
            "prior_scope": (
                "additional archive formats, depth, and total "
                "extraction limits"
            ),
            "capability_ids": list(CAPABILITY_IDS),
            "disposition": (
                "closed by exhaustive engine extraction-family inventory, "
                "positive/default runtime controls, exact iteration "
                "boundary, and bounded depth/expanded-byte observations "
                "paired with source absence of an independent budget"
            ),
        },
        "sources": {
            "formats": {
                **formats_identity,
                "path": "xformats.cpp",
                "bytes": len(formats_raw),
                "sha256": sha256(formats_raw),
            },
            "xscanengine": {
                **xscanengine_identity,
                "path": "xscanengine.cpp",
                "bytes": len(xscanengine_raw),
                "sha256": sha256(xscanengine_raw),
            },
        },
        "input_reports": input_records,
        "engine_extraction_families": {
            "count": len(families),
            "ordered_filetypes": list(families),
            "adapters": adapters,
            "all_have_positive_and_default_controls": True,
            "runtime_evidence": family_evidence,
        },
        "iteration_boundary": iteration,
        "depth_and_total_observation": limits,
        "capability_dispositions": [
            {
                "id": "CAP-DISPATCH-004",
                "verification": "observed",
                "reason": (
                    "public archive dispatch evidence is already fixed; "
                    "all five engine-extractable families are now proven "
                    "as a closed source set with runtime controls"
                ),
            },
            {
                "id": "CAP-NEST-003",
                "verification": "observed",
                "reason": (
                    "all five families retain zero children without the "
                    "engine archive option and positive children with it"
                ),
            },
            {
                "id": "CAP-NEST-004",
                "verification": "observed",
                "reason": (
                    "the archive loop reaches records 99999 and 100000 "
                    "and excludes record 100001"
                ),
            },
            {
                "id": "CAP-NEST-009",
                "verification": "observed",
                "reason": (
                    "source has no independent depth/total budget and "
                    "runtime reaches depth 64 and 33,554,546 cumulative "
                    "expanded bytes"
                ),
            },
        ],
        "closure_assertions": {
            "all_named_capabilities_have_observed_dispositions": True,
            "engine_extraction_family_inventory_is_exhaustive": True,
            "every_engine_extraction_family_has_runtime_controls": True,
            "iteration_boundary_is_exact": True,
            "depth_and_total_claim_is_bounded_and_source_paired": True,
            "cap_gap_006_closed": True,
        },
        "remaining_risks": [
            (
                "upstream still lacks an independent depth, total "
                "expanded-byte, time, or allocation budget"
            ),
            (
                "depth 64 and 33,554,546 bytes are maximum observations, "
                "not claims that larger inputs are safe"
            ),
            (
                "RAR15/RAR20/RAR7-v1, encrypted, multi-volume, recovery, "
                "and corrupt compressed streams remain format-method "
                "coverage, not an unclassified engine family"
            ),
            (
                "Windows, macOS, and a complete Linux Qt6 capability "
                "baseline remain separate platform gaps"
            ),
        ],
    }


def serialize(report: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def parse_args() -> argparse.Namespace:
    root = pathlib.Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repository-root",
        type=pathlib.Path,
        default=root,
    )
    parser.add_argument("--formats-root", type=pathlib.Path, required=True)
    parser.add_argument(
        "--xscanengine-root", type=pathlib.Path, required=True
    )
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=(
            root
            / "docs"
            / "research"
            / "data"
            / "archive-gap-closure.json"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(
        args.repository_root.resolve(),
        args.formats_root.resolve(),
        args.xscanengine_root.resolve(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(serialize(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
