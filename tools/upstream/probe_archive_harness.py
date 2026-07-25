#!/usr/bin/env python3
"""Probe pinned engine-only archive options with a research harness."""

from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys


def _load_shared_module():
    module_path = pathlib.Path(__file__).with_name(
        "compare_cli_oracles.py"
    )
    spec = importlib.util.spec_from_file_location(
        "_diec_compare_cli_oracles", module_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load shared oracle helpers")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SHARED = _load_shared_module()

HARNESS_MATRIX = (
    SHARED.Case("default", ()),
    SHARED.Case("archive", ("--archive",)),
    SHARED.Case("aggressive", ("--aggressive",)),
    SHARED.Case(
        "archive_aggressive",
        ("--archive", "--aggressive"),
    ),
    SHARED.Case("recursive", ("--recursive",)),
    SHARED.Case(
        "recursive_aggressive",
        ("--recursive", "--aggressive"),
    ),
    SHARED.Case(
        "archive_recursive",
        ("--archive", "--recursive"),
    ),
    SHARED.Case(
        "archive_recursive_aggressive",
        ("--archive", "--recursive", "--aggressive"),
    ),
)

RELEASE_EQUIVALENTS = {
    "default": ("--json", *SHARED.DATABASE_ARGS),
    "aggressive": (
        "--json",
        "--aggressivecscan",
        *SHARED.DATABASE_ARGS,
    ),
    "recursive": (
        "--json",
        "--recursivescan",
        *SHARED.DATABASE_ARGS,
    ),
    "recursive_aggressive": (
        "--json",
        "--recursivescan",
        "--aggressivecscan",
        *SHARED.DATABASE_ARGS,
    ),
}

EXPECTED_BOUNDARY_COUNTS = {
    ("many-pdf-members.zip", "archive", "Stream"): 21,
    ("many-pdf-members.zip", "archive_aggressive", "Stream"): 22,
    ("pe-many-pdf-resources.exe", "recursive", "Resource"): 21,
    (
        "pe-many-pdf-resources.exe",
        "recursive_aggressive",
        "Resource",
    ): 22,
}


def count_file_parts(tree: object, file_part: str) -> int:
    if isinstance(tree, list):
        return sum(count_file_parts(item, file_part) for item in tree)
    if not isinstance(tree, dict):
        return 0
    count = int(tree.get("parentfilepart") == file_part)
    return count + sum(
        count_file_parts(value, file_part) for value in tree.values()
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--harness-image", required=True)
    parser.add_argument("--harness-binary", required=True)
    parser.add_argument("--release-image", required=True)
    parser.add_argument("--release-binary", required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--nested-corpus-dir", required=True, type=pathlib.Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    corpus_dir = args.nested_corpus_dir.resolve()
    samples = SHARED.load_nested_corpus(corpus_dir)
    failures = []
    report: dict[str, object] = {
        "expected_revision": args.expected_revision,
        "harness_image": args.harness_image,
        "release_image": args.release_image,
        "samples": samples,
        "cases": {},
    }

    for side, image in (
        ("harness", args.harness_image),
        ("release", args.release_image),
    ):
        revision = SHARED.image_revision(image)
        report[f"{side}_revision"] = revision
        if revision != args.expected_revision:
            failures.append(f"{side}_revision")

    case_report = report["cases"]
    assert isinstance(case_report, dict)
    for sample in samples:
        name = str(sample["name"])
        sample_report = {}
        case_report[name] = sample_report
        for case in HARNESS_MATRIX:
            harness_arguments = (
                *case.arguments,
                f"/nested/{name}",
            )
            harness = SHARED.observe(
                args.harness_image,
                args.harness_binary,
                harness_arguments,
                corpus_dir,
                "/nested",
            )
            tree = SHARED.json_detect_tree(harness.stdout)
            entry: dict[str, object] = {
                "arguments": list(harness_arguments),
                "harness": harness.summary(),
                "detect_tree": tree,
                "stream_count": count_file_parts(tree, "Stream"),
                "resource_count": count_file_parts(tree, "Resource"),
                "overlay_count": count_file_parts(tree, "Overlay"),
            }
            sample_report[case.name] = entry

            if harness.exit_code != 0:
                failures.append(
                    f"{name}.{case.name}.harness_exit_code"
                )
            if harness.stderr:
                failures.append(f"{name}.{case.name}.harness_stderr")
            if tree is None:
                failures.append(f"{name}.{case.name}.invalid_json")

            release_prefix = RELEASE_EQUIVALENTS.get(case.name)
            if release_prefix is not None:
                release_arguments = (
                    *release_prefix,
                    f"/nested/{name}",
                )
                release = SHARED.observe(
                    args.release_image,
                    args.release_binary,
                    release_arguments,
                    corpus_dir,
                    "/nested",
                )
                differences = SHARED.compare_observations(
                    harness, release
                )
                entry["release_arguments"] = list(release_arguments)
                entry["release"] = release.summary()
                entry["release_differences"] = differences
                failures.extend(
                    f"{name}.{case.name}.release.{difference}"
                    for difference in differences
                )

    for key, expected_count in EXPECTED_BOUNDARY_COUNTS.items():
        name, case_name, file_part = key
        entry = case_report[name][case_name]
        assert isinstance(entry, dict)
        actual_count = entry[f"{file_part.lower()}_count"]
        if actual_count != expected_count:
            failures.append(
                f"{name}.{case_name}.{file_part}_count"
            )

    report["equal_release_without_archive"] = not any(
        ".release." in failure for failure in failures
    )
    report["failures"] = failures
    report["passed"] = not failures
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
