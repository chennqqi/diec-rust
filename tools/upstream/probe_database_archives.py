#!/usr/bin/env python3
"""Probe pinned DIE CLI ZIP-database behavior with raw byte retention."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import pathlib
import subprocess
import sys

import compare_cli_oracles as shared


def fixture_database_args(main_path: str) -> tuple[str, ...]:
    return (
        "--database",
        main_path,
        "--extradatabase",
        "/dbfx/empty-extra",
        "--customdatabase",
        "/dbfx/empty-custom",
    )


ARCHIVE_CASES = (
    shared.Case(
        "show_database_valid_archive",
        ("--showdatabase", *fixture_database_args("/dbfx/valid-main.zip")),
    ),
    shared.Case(
        "show_database_empty_archive",
        ("--showdatabase", *fixture_database_args("/dbfx/empty-main.zip")),
    ),
    shared.Case(
        "show_database_truncated_archive",
        (
            "--showdatabase",
            *fixture_database_args("/dbfx/truncated-main.zip"),
        ),
    ),
    shared.Case(
        "show_database_local_only_archive",
        (
            "--showdatabase",
            *fixture_database_args("/dbfx/local-only-main.zip"),
        ),
    ),
    shared.Case(
        "show_database_payload_truncated_archive",
        (
            "--showdatabase",
            *fixture_database_args("/dbfx/payload-truncated-main.zip"),
        ),
    ),
    shared.Case(
        "show_database_payload_structure_truncated_archive",
        (
            "--showdatabase",
            *fixture_database_args(
                "/dbfx/payload-structure-truncated-main.zip"
            ),
        ),
    ),
    shared.Case(
        "show_database_local_header_truncated_archive",
        (
            "--showdatabase",
            *fixture_database_args(
                "/dbfx/local-header-truncated-main.zip"
            ),
        ),
    ),
    shared.Case(
        "scan_valid_archive_json",
        (
            "--json",
            *fixture_database_args("/dbfx/valid-main.zip"),
            "/dbfx/input/plain.txt",
        ),
    ),
    shared.Case(
        "scan_empty_archive_json",
        (
            "--json",
            *fixture_database_args("/dbfx/empty-main.zip"),
            "/dbfx/input/plain.txt",
        ),
    ),
    shared.Case(
        "scan_truncated_archive_json",
        (
            "--json",
            *fixture_database_args("/dbfx/truncated-main.zip"),
            "/dbfx/input/plain.txt",
        ),
    ),
    shared.Case(
        "scan_local_only_archive_json",
        (
            "--json",
            *fixture_database_args("/dbfx/local-only-main.zip"),
            "/dbfx/input/plain.txt",
        ),
    ),
    shared.Case(
        "scan_payload_truncated_archive_json",
        (
            "--json",
            *fixture_database_args("/dbfx/payload-truncated-main.zip"),
            "/dbfx/input/plain.txt",
        ),
    ),
    shared.Case(
        "scan_payload_structure_truncated_archive_json",
        (
            "--json",
            *fixture_database_args(
                "/dbfx/payload-structure-truncated-main.zip"
            ),
            "/dbfx/input/plain.txt",
        ),
    ),
    shared.Case(
        "scan_local_header_truncated_archive_json",
        (
            "--json",
            *fixture_database_args(
                "/dbfx/local-header-truncated-main.zip"
            ),
            "/dbfx/input/plain.txt",
        ),
    ),
    shared.Case(
        "scan_duplicate_archive_json",
        (
            "--json",
            *fixture_database_args("/dbfx/duplicate-main.zip"),
            "/dbfx/input/plain.txt",
        ),
    ),
    shared.Case(
        "scan_traversal_archive_json",
        (
            "--json",
            *fixture_database_args("/dbfx/traversal-main.zip"),
            "/dbfx/input/plain.txt",
        ),
    ),
    shared.Case(
        "scan_prefixed_archive_json",
        (
            "--json",
            *fixture_database_args("/dbfx/prefixed-main.zip"),
            "/dbfx/input/plain.txt",
        ),
    ),
)


def image_identity(image: str) -> tuple[str, str]:
    result = subprocess.run(
        ["docker", "image", "inspect", image],
        check=True,
        capture_output=True,
        text=True,
    )
    document = json.loads(result.stdout)[0]
    return (
        document["Id"],
        document["Config"]["Labels"][
            "org.opencontainers.image.revision"
        ],
    )


def observe(
    image: str,
    binary: str,
    arguments: tuple[str, ...],
    fixture_dir: pathlib.Path,
) -> shared.Observation:
    command = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--mount",
        (
            f"type=bind,source={fixture_dir},"
            "target=/dbfx,readonly"
        ),
        image,
        "sh",
        "-c",
        'ln -sf "$1" /tmp/diec && shift && exec /tmp/diec "$@"',
        "sh",
        binary,
        *arguments,
    ]
    result = subprocess.run(command, check=False, capture_output=True)
    return shared.Observation(
        result.returncode,
        result.stdout,
        result.stderr,
    )


def raw_streams(observation: shared.Observation) -> dict[str, str]:
    return {
        "stdout_base64": base64.b64encode(
            observation.stdout
        ).decode("ascii"),
        "stderr_base64": base64.b64encode(
            observation.stderr
        ).decode("ascii"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--left-image", required=True)
    parser.add_argument("--left-binary", required=True)
    parser.add_argument("--right-image", required=True)
    parser.add_argument("--right-binary", required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument(
        "--database-fixture-dir",
        required=True,
        type=pathlib.Path,
    )
    parser.add_argument("--output", type=pathlib.Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fixture_dir = args.database_fixture_dir.resolve()
    fixture = shared.load_database_fixture(fixture_dir)
    fixture_manifest_path = fixture_dir / "manifest.json"
    root = pathlib.Path(__file__).resolve().parents[2]
    shared_path = pathlib.Path(shared.__file__).resolve()
    fixture_generator_path = (
        root / "tools" / "corpus" / "generate_database_fixture.py"
    )

    report: dict[str, object] = {
        "schema_version": 1,
        "generator": "tools/upstream/probe_database_archives.py",
        "generator_sha256": hashlib.sha256(
            pathlib.Path(__file__).read_bytes()
        ).hexdigest(),
        "shared_helper": "tools/upstream/compare_cli_oracles.py",
        "shared_helper_sha256": hashlib.sha256(
            shared_path.read_bytes()
        ).hexdigest(),
        "fixture_generator_sha256": hashlib.sha256(
            fixture_generator_path.read_bytes()
        ).hexdigest(),
        "expected_revision": args.expected_revision,
        "left_image": args.left_image,
        "right_image": args.right_image,
        "database_fixture": {
            "manifest_sha256": hashlib.sha256(
                fixture_manifest_path.read_bytes()
            ).hexdigest(),
            "directories": fixture["directories"],
            "entries": fixture["entries"],
            "cases": {},
        },
    }
    failures: list[str] = []
    for side, image in (
        ("left", args.left_image),
        ("right", args.right_image),
    ):
        image_id, revision = image_identity(image)
        report[f"{side}_image_id"] = image_id
        report[f"{side}_revision"] = revision
        if revision != args.expected_revision:
            failures.append(f"{side}_revision")

    cases = report["database_fixture"]["cases"]
    assert isinstance(cases, dict)
    for case in ARCHIVE_CASES:
        left = observe(
            args.left_image,
            args.left_binary,
            case.arguments,
            fixture_dir,
        )
        right = observe(
            args.right_image,
            args.right_binary,
            case.arguments,
            fixture_dir,
        )
        differences = shared.compare_observations(left, right)
        entry: dict[str, object] = {
            "arguments": list(case.arguments),
            "left": {**left.summary(), **raw_streams(left)},
            "right": {**right.summary(), **raw_streams(right)},
            "differences": differences,
        }
        if case.name.endswith("_json"):
            entry["left_valid_json"] = shared.document_is_valid(
                left.stdout,
                "json",
            )
            entry["right_valid_json"] = shared.document_is_valid(
                right.stdout,
                "json",
            )
        cases[case.name] = entry
        failures.extend(
            f"{case.name}.{difference}"
            for difference in differences
        )

    report["equal"] = not failures
    report["failures"] = failures
    serialized = (
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    )
    if args.output is None:
        sys.stdout.write(serialized)
    else:
        args.output.write_text(
            serialized,
            encoding="utf-8",
            newline="\n",
        )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
