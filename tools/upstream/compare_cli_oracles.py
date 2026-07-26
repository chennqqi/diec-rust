#!/usr/bin/env python3
"""Compare observable CLI behavior from two pinned DIE-engine Docker images."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass
from typing import Sequence


DATABASE_ARGS = (
    "--database",
    "/opt/die-source/Detect-It-Easy/db",
    "--extradatabase",
    "/opt/die-source/Detect-It-Easy/db_extra",
    "--customdatabase",
    "/opt/die-source/Detect-It-Easy/db_custom",
)


@dataclass(frozen=True)
class Observation:
    exit_code: int
    stdout: bytes
    stderr: bytes

    def summary(self) -> dict[str, object]:
        return {
            "exit_code": self.exit_code,
            "stdout_sha256": hashlib.sha256(self.stdout).hexdigest(),
            "stderr_sha256": hashlib.sha256(self.stderr).hexdigest(),
        }


@dataclass(frozen=True)
class Case:
    name: str
    arguments: tuple[str, ...]


CASES = (
    Case("version", ("--version",)),
    Case("help", ("--help",)),
    Case("show_structs", ("--showstructs",)),
    Case("show_structs_with_target", ("--showstructs", "/usr/bin/true")),
    Case("database", ("--showdatabase", *DATABASE_ARGS)),
    Case("true_json", ("--json", *DATABASE_ARGS, "/usr/bin/true")),
    Case("no_args", ()),
    Case("missing", ("/does-not-exist",)),
)

OUTPUT_MATRIX = (
    Case("text", DATABASE_ARGS),
    Case("plaintext", ("--plaintext", *DATABASE_ARGS)),
    Case("json", ("--json", *DATABASE_ARGS)),
    Case("xml", ("--xml", *DATABASE_ARGS)),
    Case("csv", ("--csv", *DATABASE_ARGS)),
    Case("tsv", ("--tsv", *DATABASE_ARGS)),
    Case(
        "all_output_flags",
        (
            "--xml",
            "--json",
            "--csv",
            "--tsv",
            "--plaintext",
            *DATABASE_ARGS,
        ),
    ),
)

SCAN_MATRIX = (
    Case("default", ("--json", *DATABASE_ARGS)),
    Case("deep", ("--json", "--deepscan", *DATABASE_ARGS)),
    Case("heuristic", ("--json", "--heuristicscan", *DATABASE_ARGS)),
    Case("aggressive", ("--json", "--aggressivecscan", *DATABASE_ARGS)),
    Case("alltypes", ("--json", "--alltypes", *DATABASE_ARGS)),
    Case("format", ("--json", "--format", *DATABASE_ARGS)),
    Case("hideunknown", ("--json", "--hideunknown", *DATABASE_ARGS)),
    Case(
        "combined",
        (
            "--json",
            "--deepscan",
            "--heuristicscan",
            "--aggressivecscan",
            "--alltypes",
            *DATABASE_ARGS,
        ),
    ),
)

NESTED_MATRIX = (
    Case("default", ("--json", *DATABASE_ARGS)),
    Case(
        "recursive",
        ("--json", "--recursivescan", *DATABASE_ARGS),
    ),
    Case(
        "aggressive",
        ("--json", "--aggressivecscan", *DATABASE_ARGS),
    ),
    Case(
        "recursive_aggressive",
        (
            "--json",
            "--recursivescan",
            "--aggressivecscan",
            *DATABASE_ARGS,
        ),
    ),
)

SPECIAL_MATRIX = (
    Case("entropy_text", ("--entropy", *DATABASE_ARGS)),
    Case(
        "entropy_plaintext",
        ("--entropy", "--plaintext", *DATABASE_ARGS),
    ),
    Case("entropy_json", ("--entropy", "--json", *DATABASE_ARGS)),
    Case("entropy_xml", ("--entropy", "--xml", *DATABASE_ARGS)),
    Case("entropy_csv", ("--entropy", "--csv", *DATABASE_ARGS)),
    Case("entropy_tsv", ("--entropy", "--tsv", *DATABASE_ARGS)),
    Case(
        "entropy_all_output_flags",
        (
            "--entropy",
            "--xml",
            "--json",
            "--csv",
            "--tsv",
            "--plaintext",
            *DATABASE_ARGS,
        ),
    ),
    Case("info_text", ("--info", *DATABASE_ARGS)),
    Case("info_plaintext", ("--info", "--plaintext", *DATABASE_ARGS)),
    Case("info_json", ("--info", "--json", *DATABASE_ARGS)),
    Case("info_xml", ("--info", "--xml", *DATABASE_ARGS)),
    Case("info_csv", ("--info", "--csv", *DATABASE_ARGS)),
    Case("info_tsv", ("--info", "--tsv", *DATABASE_ARGS)),
    Case(
        "info_all_output_flags",
        (
            "--info",
            "--xml",
            "--json",
            "--csv",
            "--tsv",
            "--plaintext",
            *DATABASE_ARGS,
        ),
    ),
    Case("struct_hash_json", ("--struct", "Hash", "--json", *DATABASE_ARGS)),
    Case(
        "struct_hash_md5_json",
        ("--struct", "Hash#MD5", "--json", *DATABASE_ARGS),
    ),
    Case(
        "struct_unknown_json",
        ("--struct", "NoSuchMethod", "--json", *DATABASE_ARGS),
    ),
    Case(
        "entropy_over_info_struct_json",
        (
            "--entropy",
            "--info",
            "--struct",
            "Hash",
            "--json",
            *DATABASE_ARGS,
        ),
    ),
    Case(
        "struct_over_info_json",
        ("--info", "--struct", "Hash", "--json", *DATABASE_ARGS),
    ),
)

PATH_CASES = (
    Case(
        "single_file_json",
        ("--json", *DATABASE_ARGS, "/paths/tree/a-first.pdf"),
    ),
    Case(
        "two_files_json",
        (
            "--json",
            *DATABASE_ARGS,
            "/paths/tree/z-last.txt",
            "/paths/tree/a-first.pdf",
        ),
    ),
    Case(
        "duplicate_file_json",
        (
            "--json",
            *DATABASE_ARGS,
            "/paths/tree/a-first.pdf",
            "/paths/tree/a-first.pdf",
        ),
    ),
    Case("tree_json", ("--json", *DATABASE_ARGS, "/paths/tree")),
    Case(
        "tree_recursive_json",
        ("--json", "--recursivescan", *DATABASE_ARGS, "/paths/tree"),
    ),
    Case("tree_xml", ("--xml", *DATABASE_ARGS, "/paths/tree")),
    Case("tree_csv", ("--csv", *DATABASE_ARGS, "/paths/tree")),
    Case(
        "tree_plaintext",
        ("--plaintext", *DATABASE_ARGS, "/paths/tree"),
    ),
    Case(
        "tree_entropy_json",
        ("--entropy", "--json", *DATABASE_ARGS, "/paths/tree"),
    ),
    Case(
        "tree_info_json",
        ("--info", "--json", *DATABASE_ARGS, "/paths/tree"),
    ),
    Case(
        "single_directory_json",
        ("--json", *DATABASE_ARGS, "/paths/single"),
    ),
    Case(
        "empty_directory_json",
        ("--json", *DATABASE_ARGS, "/paths/empty-dir"),
    ),
    Case(
        "missing_and_existing_json",
        (
            "--json",
            *DATABASE_ARGS,
            "/paths/does-not-exist",
            "/paths/tree/a-first.pdf",
        ),
    ),
    Case(
        "directory_plus_duplicate_json",
        (
            "--json",
            *DATABASE_ARGS,
            "/paths/tree",
            "/paths/tree/a-first.pdf",
        ),
    ),
)


def fixture_database_args(main_path: str) -> tuple[str, ...]:
    return (
        "--database",
        main_path,
        "--extradatabase",
        "/dbfx/empty-extra",
        "--customdatabase",
        "/dbfx/empty-custom",
    )


DATABASE_CASES = (
    Case(
        "show_database_missing_main",
        ("--showdatabase", *fixture_database_args("/dbfx/missing-main")),
    ),
    Case(
        "show_database_missing_main_messages",
        (
            "--showdatabase",
            "--messages",
            *fixture_database_args("/dbfx/missing-main"),
        ),
    ),
    Case(
        "show_database_empty_main",
        ("--showdatabase", *fixture_database_args("/dbfx/empty-main")),
    ),
    Case(
        "show_database_invalid_archive",
        (
            "--showdatabase",
            *fixture_database_args("/dbfx/not-a-database.bin"),
        ),
    ),
    Case(
        "show_database_invalid_archive_messages",
        (
            "--showdatabase",
            "--messages",
            *fixture_database_args("/dbfx/not-a-database.bin"),
        ),
    ),
    Case(
        "show_database_malformed_main",
        ("--showdatabase", *fixture_database_args("/dbfx/malformed-main")),
    ),
    Case(
        "scan_missing_main_json",
        (
            "--json",
            *fixture_database_args("/dbfx/missing-main"),
            "/dbfx/input/plain.txt",
        ),
    ),
    Case(
        "scan_missing_main_messages_json",
        (
            "--json",
            "--messages",
            *fixture_database_args("/dbfx/missing-main"),
            "/dbfx/input/plain.txt",
        ),
    ),
    Case(
        "scan_empty_main_json",
        (
            "--json",
            *fixture_database_args("/dbfx/empty-main"),
            "/dbfx/input/plain.txt",
        ),
    ),
    Case(
        "scan_invalid_archive_json",
        (
            "--json",
            *fixture_database_args("/dbfx/not-a-database.bin"),
            "/dbfx/input/plain.txt",
        ),
    ),
    Case(
        "scan_invalid_archive_messages_json",
        (
            "--json",
            "--messages",
            *fixture_database_args("/dbfx/not-a-database.bin"),
            "/dbfx/input/plain.txt",
        ),
    ),
    Case(
        "scan_malformed_main_json",
        (
            "--json",
            *fixture_database_args("/dbfx/malformed-main"),
            "/dbfx/input/plain.txt",
        ),
    ),
    Case(
        "scan_throwing_main_json",
        (
            "--json",
            *fixture_database_args("/dbfx/throwing-main"),
            "/dbfx/input/plain.txt",
        ),
    ),
    Case(
        "scan_valid_main_json",
        (
            "--json",
            *fixture_database_args("/dbfx/valid-main"),
            "/dbfx/input/plain.txt",
        ),
    ),
    Case(
        "entropy_missing_main_messages_json",
        (
            "--entropy",
            "--json",
            "--messages",
            *fixture_database_args("/dbfx/missing-main"),
            "/dbfx/input/plain.txt",
        ),
    ),
    Case(
        "info_missing_main_messages_json",
        (
            "--info",
            "--json",
            "--messages",
            *fixture_database_args("/dbfx/missing-main"),
            "/dbfx/input/plain.txt",
        ),
    ),
    Case(
        "scan_valid_main_missing_extra_json",
        (
            "--json",
            "--messages",
            "--database",
            "/opt/die-source/Detect-It-Easy/db",
            "--extradatabase",
            "/dbfx/missing-extra",
            "--customdatabase",
            "/dbfx/missing-custom",
            "/dbfx/input/plain.txt",
        ),
    ),
    Case(
        "show_database_valid_main_missing_extra",
        (
            "--showdatabase",
            "--messages",
            "--database",
            "/opt/die-source/Detect-It-Easy/db",
            "--extradatabase",
            "/dbfx/missing-extra",
            "--customdatabase",
            "/dbfx/missing-custom",
        ),
    ),
)

UNREADABLE_CASES = (
    Case(
        "scan_json",
        ("--json", *DATABASE_ARGS, "/tmp/unreadable-fixture"),
    ),
    Case(
        "scan_messages_json",
        (
            "--json",
            "--messages",
            *DATABASE_ARGS,
            "/tmp/unreadable-fixture",
        ),
    ),
    Case(
        "info_json",
        ("--info", "--json", *DATABASE_ARGS, "/tmp/unreadable-fixture"),
    ),
    Case(
        "entropy_json",
        (
            "--entropy",
            "--json",
            *DATABASE_ARGS,
            "/tmp/unreadable-fixture",
        ),
    ),
)


def observe(
    image: str,
    binary: str,
    arguments: Sequence[str],
    corpus_dir: pathlib.Path | None = None,
    mount_target: str = "/corpus",
) -> Observation:
    # The symlink gives both programs the same argv[0], making the Usage line
    # comparable even though their build-tree paths differ.
    command = [
        "docker",
        "run",
        "--rm",
    ]
    if corpus_dir is not None:
        command.extend(
            [
                "--mount",
                (
                    f"type=bind,source={corpus_dir},"
                    f"target={mount_target},readonly"
                ),
            ]
        )
    command.extend(
        [
            image,
            "sh",
            "-c",
            'ln -sf "$1" /tmp/diec && shift && exec /tmp/diec "$@"',
            "sh",
            binary,
            *arguments,
        ]
    )
    result = subprocess.run(command, check=False, capture_output=True)
    return Observation(result.returncode, result.stdout, result.stderr)


def observe_unreadable(
    image: str,
    binary: str,
    arguments: Sequence[str],
) -> Observation:
    command = [
        "docker",
        "run",
        "--rm",
        image,
        "sh",
        "-c",
        (
            "install -m 000 /dev/null /tmp/unreadable-fixture"
            ' && exec runuser -u nobody -- "$@"'
        ),
        "sh",
        binary,
        *arguments,
    ]
    result = subprocess.run(command, check=False, capture_output=True)
    return Observation(result.returncode, result.stdout, result.stderr)


def image_revision(image: str) -> str:
    result = subprocess.run(
        ["docker", "image", "inspect", image],
        check=True,
        capture_output=True,
        text=True,
    )
    document = json.loads(result.stdout)
    return document[0]["Config"]["Labels"]["org.opencontainers.image.revision"]


def sample_sha256(image: str) -> str:
    result = subprocess.run(
        ["docker", "run", "--rm", image, "sha256sum", "/usr/bin/true"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.split()[0]


def compare_observations(
    left: Observation, right: Observation
) -> list[str]:
    differences = []
    if left.exit_code != right.exit_code:
        differences.append("exit_code")
    if left.stdout != right.stdout:
        differences.append("stdout")
    if left.stderr != right.stderr:
        differences.append("stderr")
    return differences


def load_corpus(corpus_dir: pathlib.Path) -> list[dict[str, object]]:
    manifest_path = corpus_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported corpus manifest schema")
    samples = manifest.get("samples")
    if not isinstance(samples, list) or not samples:
        raise ValueError("corpus manifest has no samples")

    validated = []
    names = set()
    for sample in samples:
        if not isinstance(sample, dict):
            raise ValueError("corpus sample must be an object")
        name = sample.get("name")
        expected_size = sample.get("size")
        expected_sha256 = sample.get("sha256")
        if (
            not isinstance(name, str)
            or pathlib.PurePath(name).name != name
            or name in {".", ".."}
        ):
            raise ValueError(f"unsafe corpus sample name: {name!r}")
        if not isinstance(expected_size, int) or expected_size < 0:
            raise ValueError(f"invalid size for corpus sample: {name}")
        if (
            not isinstance(expected_sha256, str)
            or len(expected_sha256) != 64
            or any(character not in "0123456789abcdef" for character in expected_sha256)
        ):
            raise ValueError(f"invalid SHA-256 for corpus sample: {name}")
        if name in names:
            raise ValueError(f"duplicate corpus sample name: {name}")
        names.add(name)

        data = (corpus_dir / name).read_bytes()
        actual_sha256 = hashlib.sha256(data).hexdigest()
        if len(data) != expected_size or actual_sha256 != expected_sha256:
            raise ValueError(f"corpus sample does not match manifest: {name}")
        validated.append(sample)
    return validated


def load_nested_corpus(
    nested_corpus_dir: pathlib.Path,
) -> list[dict[str, object]]:
    samples = load_corpus(nested_corpus_dir)
    manifest = json.loads(
        (nested_corpus_dir / "manifest.json").read_text(encoding="utf-8")
    )
    if (
        manifest.get("generator")
        != "tools/corpus/generate_nested_corpus.py"
    ):
        raise ValueError("unexpected nested corpus generator")
    return samples


def _safe_relative_path(value: object) -> pathlib.PurePosixPath:
    if not isinstance(value, str) or "\\" in value:
        raise ValueError(f"unsafe path corpus entry: {value!r}")
    path = pathlib.PurePosixPath(value)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError(f"unsafe path corpus entry: {value!r}")
    return path


def load_path_corpus(path_corpus_dir: pathlib.Path) -> dict[str, object]:
    manifest_path = path_corpus_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported path corpus manifest schema")

    directories = manifest.get("directories")
    entries = manifest.get("entries")
    if not isinstance(directories, list) or not isinstance(entries, list):
        raise ValueError("path corpus manifest is missing layout")

    declared_directories = set()
    for value in directories:
        path = _safe_relative_path(value)
        if path.as_posix() in declared_directories:
            raise ValueError(f"duplicate path corpus directory: {value}")
        declared_directories.add(path.as_posix())
        actual = path_corpus_dir / pathlib.Path(*path.parts)
        if not actual.is_dir() or actual.is_symlink():
            raise ValueError(f"path corpus directory mismatch: {value}")

    declared_files = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("path corpus entry must be an object")
        path = _safe_relative_path(entry.get("path"))
        relative_path = path.as_posix()
        if relative_path in declared_files:
            raise ValueError(f"duplicate path corpus file: {relative_path}")
        declared_files.add(relative_path)

        expected_size = entry.get("size")
        expected_sha256 = entry.get("sha256")
        source = entry.get("source")
        if (
            not isinstance(source, str)
            or pathlib.PurePath(source).name != source
            or source in {".", ".."}
        ):
            raise ValueError(f"invalid path corpus source: {relative_path}")
        if not isinstance(expected_size, int) or expected_size < 0:
            raise ValueError(f"invalid path corpus size: {relative_path}")
        if (
            not isinstance(expected_sha256, str)
            or len(expected_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in expected_sha256
            )
        ):
            raise ValueError(f"invalid path corpus SHA-256: {relative_path}")

        actual = path_corpus_dir / pathlib.Path(*path.parts)
        if actual.is_symlink():
            raise ValueError(
                f"path corpus symlink is not allowed: {relative_path}"
            )
        data = actual.read_bytes()
        if (
            len(data) != expected_size
            or hashlib.sha256(data).hexdigest() != expected_sha256
        ):
            raise ValueError(f"path corpus file mismatch: {relative_path}")

    actual_files = set()
    actual_directories = set()
    for path in path_corpus_dir.rglob("*"):
        relative_path = path.relative_to(path_corpus_dir).as_posix()
        if path.is_symlink():
            raise ValueError(
                f"path corpus symlink is not allowed: {relative_path}"
            )
        if path.is_dir():
            actual_directories.add(relative_path)
        elif path.is_file() and path != manifest_path:
            actual_files.add(relative_path)

    if actual_directories != declared_directories:
        raise ValueError("path corpus contains undeclared or missing directories")
    if actual_files != declared_files:
        raise ValueError("path corpus contains undeclared or missing files")
    return manifest


def load_database_fixture(
    database_fixture_dir: pathlib.Path,
) -> dict[str, object]:
    manifest = load_path_corpus(database_fixture_dir)
    if (
        manifest.get("generator")
        != "tools/corpus/generate_database_fixture.py"
    ):
        raise ValueError("unexpected database fixture generator")
    return manifest


def document_is_valid(data: bytes, kind: str) -> bool:
    try:
        if kind == "json":
            json.loads(data)
        elif kind == "xml":
            ElementTree.fromstring(data)
        else:
            raise ValueError(f"unsupported document kind: {kind}")
    except (UnicodeDecodeError, json.JSONDecodeError, ElementTree.ParseError):
        return False
    return True


def filename_prefixes(data: bytes) -> list[str]:
    return [
        line[:-1]
        for line in data.decode("utf-8", errors="replace").splitlines()
        if line.startswith("/paths/") and line.endswith(":")
    ]


def json_detect_tree(data: bytes) -> object:
    """Return only stable nested-result fields from a normal JSON scan."""
    try:
        document = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(document, dict):
        return None
    detects = document.get("detects")
    if not isinstance(detects, list):
        return None

    def summarize(detect: object) -> object:
        if not isinstance(detect, dict):
            return None
        is_nested_detect = "parentfilepart" in detect
        keys = (
            ("filetype", "offset", "parentfilepart", "size")
            if is_nested_detect
            else ("name", "type", "version")
        )
        result = {key: detect[key] for key in keys if key in detect}
        values = detect.get("values")
        if isinstance(values, list):
            result["values"] = [summarize(value) for value in values]
        return result

    return [summarize(detect) for detect in detects]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--left-image", required=True)
    parser.add_argument("--left-binary", required=True)
    parser.add_argument("--right-image", required=True)
    parser.add_argument("--right-binary", required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--corpus-dir", type=pathlib.Path)
    parser.add_argument(
        "--path-corpus-dir",
        type=pathlib.Path,
        help="Generated path corpus used for multi-target/directory cases",
    )
    parser.add_argument(
        "--database-fixture-dir",
        type=pathlib.Path,
        help="Generated database fixture used for load/error cases",
    )
    parser.add_argument(
        "--nested-corpus-dir",
        type=pathlib.Path,
        help="Generated archive/overlay corpus used for nested scan cases",
    )
    parser.add_argument(
        "--matrix-sample",
        action="append",
        default=[],
        help="Corpus sample to include in the selected option matrix",
    )
    parser.add_argument(
        "--matrix-all",
        action="store_true",
        help="Include every corpus sample in the selected matrices",
    )
    parser.add_argument(
        "--matrix-kind",
        choices=("both", "all", "output", "scan", "special"),
        default="both",
        help=(
            "'both' preserves the output+scan matrix; 'all' also includes "
            "special modes"
        ),
    )
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        help="Write the JSON report to this path instead of stdout",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report: dict[str, object] = {
        "expected_revision": args.expected_revision,
        "left_image": args.left_image,
        "right_image": args.right_image,
        "cases": {},
    }
    failures = []
    corpus_dir = args.corpus_dir.resolve() if args.corpus_dir else None
    path_corpus_dir = (
        args.path_corpus_dir.resolve() if args.path_corpus_dir else None
    )
    database_fixture_dir = (
        args.database_fixture_dir.resolve()
        if args.database_fixture_dir
        else None
    )
    nested_corpus_dir = (
        args.nested_corpus_dir.resolve()
        if args.nested_corpus_dir
        else None
    )

    for side, image in (
        ("left", args.left_image),
        ("right", args.right_image),
    ):
        revision = image_revision(image)
        report[f"{side}_revision"] = revision
        if revision != args.expected_revision:
            failures.append(f"{side}_revision")

    left_sample = sample_sha256(args.left_image)
    right_sample = sample_sha256(args.right_image)
    report["sample"] = {
        "path": "/usr/bin/true",
        "left_sha256": left_sample,
        "right_sha256": right_sample,
    }
    if left_sample != right_sample:
        failures.append("sample_sha256")

    case_report = report["cases"]
    assert isinstance(case_report, dict)
    for case in CASES:
        left = observe(args.left_image, args.left_binary, case.arguments)
        right = observe(args.right_image, args.right_binary, case.arguments)
        differences = compare_observations(left, right)
        case_report[case.name] = {
            "arguments": list(case.arguments),
            "left": left.summary(),
            "right": right.summary(),
            "differences": differences,
        }
        failures.extend(f"{case.name}.{item}" for item in differences)

    unreadable_report = {}
    report["unreadable_input"] = unreadable_report
    for case in UNREADABLE_CASES:
        left = observe_unreadable(
            args.left_image,
            args.left_binary,
            case.arguments,
        )
        right = observe_unreadable(
            args.right_image,
            args.right_binary,
            case.arguments,
        )
        differences = compare_observations(left, right)
        unreadable_report[case.name] = {
            "arguments": list(case.arguments),
            "left": left.summary(),
            "right": right.summary(),
            "differences": differences,
            "left_valid_json": document_is_valid(left.stdout, "json"),
            "right_valid_json": document_is_valid(right.stdout, "json"),
        }
        failures.extend(
            f"unreadable_input.{case.name}.{item}" for item in differences
        )

    if corpus_dir is not None:
        corpus_report = {}
        report["corpus"] = corpus_report
        samples = load_corpus(corpus_dir)
        samples_by_name = {str(sample["name"]): sample for sample in samples}
        for sample in samples:
            name = str(sample["name"])
            arguments = ("--json", *DATABASE_ARGS, f"/corpus/{name}")
            left = observe(
                args.left_image,
                args.left_binary,
                arguments,
                corpus_dir,
            )
            right = observe(
                args.right_image,
                args.right_binary,
                arguments,
                corpus_dir,
            )
            differences = compare_observations(left, right)
            corpus_report[name] = {
                "intended_format": sample.get("intended_format"),
                "size": sample["size"],
                "sha256": sample["sha256"],
                "left": left.summary(),
                "right": right.summary(),
                "left_detect_tree": json_detect_tree(left.stdout),
                "right_detect_tree": json_detect_tree(right.stdout),
                "differences": differences,
            }
            failures.extend(f"corpus.{name}.{item}" for item in differences)

        matrix_names = (
            list(samples_by_name)
            if args.matrix_all
            else list(dict.fromkeys(args.matrix_sample))
        )
        if matrix_names:
            unknown_samples = sorted(
                set(matrix_names) - samples_by_name.keys()
            )
            if unknown_samples:
                raise ValueError(
                    "matrix samples are not in corpus: "
                    + ", ".join(unknown_samples)
                )

            matrix_report = {}
            report["matrix"] = matrix_report
            for name in matrix_names:
                sample_report = {}
                matrix_report[name] = sample_report
                container_path = f"/corpus/{name}"

                if args.matrix_kind in {"both", "all", "output"}:
                    output_report = {}
                    sample_report["output"] = output_report
                    for case in OUTPUT_MATRIX:
                        arguments = (*case.arguments, container_path)
                        left = observe(
                            args.left_image,
                            args.left_binary,
                            arguments,
                            corpus_dir,
                        )
                        right = observe(
                            args.right_image,
                            args.right_binary,
                            arguments,
                            corpus_dir,
                        )
                        differences = compare_observations(left, right)
                        output_report[case.name] = {
                            "arguments": list(arguments),
                            "left": left.summary(),
                            "right": right.summary(),
                            "differences": differences,
                        }
                        failures.extend(
                            f"matrix.{name}.output.{case.name}.{item}"
                            for item in differences
                        )

                if args.matrix_kind in {"both", "all", "scan"}:
                    scan_report = {}
                    sample_report["scan"] = scan_report
                    scan_observations = {}
                    for case in SCAN_MATRIX:
                        arguments = (*case.arguments, container_path)
                        left = observe(
                            args.left_image,
                            args.left_binary,
                            arguments,
                            corpus_dir,
                        )
                        right = observe(
                            args.right_image,
                            args.right_binary,
                            arguments,
                            corpus_dir,
                        )
                        differences = compare_observations(left, right)
                        scan_observations[case.name] = (left, right)
                        scan_report[case.name] = {
                            "arguments": list(arguments),
                            "left": left.summary(),
                            "right": right.summary(),
                            "differences": differences,
                        }
                        failures.extend(
                            f"matrix.{name}.scan.{case.name}.{item}"
                            for item in differences
                        )

                    default_left, default_right = scan_observations["default"]
                    for case_name, (left, right) in scan_observations.items():
                        entry = scan_report[case_name]
                        entry["left_changes"] = compare_observations(
                            default_left, left
                        )
                        entry["right_changes"] = compare_observations(
                            default_right, right
                        )

                if args.matrix_kind in {"all", "special"}:
                    special_report = {}
                    sample_report["special"] = special_report
                    for case in SPECIAL_MATRIX:
                        arguments = (*case.arguments, container_path)
                        left = observe(
                            args.left_image,
                            args.left_binary,
                            arguments,
                            corpus_dir,
                        )
                        right = observe(
                            args.right_image,
                            args.right_binary,
                            arguments,
                            corpus_dir,
                        )
                        differences = compare_observations(left, right)
                        special_report[case.name] = {
                            "arguments": list(arguments),
                            "left": left.summary(),
                            "right": right.summary(),
                            "differences": differences,
                        }
                        failures.extend(
                            f"matrix.{name}.special.{case.name}.{item}"
                            for item in differences
                        )
    elif args.matrix_sample or args.matrix_all:
        raise ValueError("matrix options require --corpus-dir")

    if path_corpus_dir is not None:
        path_manifest = load_path_corpus(path_corpus_dir)
        path_report = {}
        report["path_corpus"] = {
            "generator": path_manifest.get("generator"),
            "directories": path_manifest["directories"],
            "entries": path_manifest["entries"],
            "cases": path_report,
        }
        path_observations = {}
        for case in PATH_CASES:
            left = observe(
                args.left_image,
                args.left_binary,
                case.arguments,
                path_corpus_dir,
                "/paths",
            )
            right = observe(
                args.right_image,
                args.right_binary,
                case.arguments,
                path_corpus_dir,
                "/paths",
            )
            differences = compare_observations(left, right)
            path_observations[case.name] = (left, right)
            entry: dict[str, object] = {
                "arguments": list(case.arguments),
                "left": left.summary(),
                "right": right.summary(),
                "differences": differences,
                "left_filename_prefixes": filename_prefixes(left.stdout),
                "right_filename_prefixes": filename_prefixes(right.stdout),
            }
            if case.name.endswith("_json"):
                entry["left_valid_json"] = document_is_valid(
                    left.stdout, "json"
                )
                entry["right_valid_json"] = document_is_valid(
                    right.stdout, "json"
                )
            elif case.name.endswith("_xml"):
                entry["left_valid_xml"] = document_is_valid(
                    left.stdout, "xml"
                )
                entry["right_valid_xml"] = document_is_valid(
                    right.stdout, "xml"
                )
            path_report[case.name] = entry
            failures.extend(
                f"path_corpus.{case.name}.{item}" for item in differences
            )

        default_left, default_right = path_observations["tree_json"]
        recursive_entry = path_report["tree_recursive_json"]
        recursive_left, recursive_right = path_observations[
            "tree_recursive_json"
        ]
        recursive_entry["left_changes"] = compare_observations(
            default_left, recursive_left
        )
        recursive_entry["right_changes"] = compare_observations(
            default_right, recursive_right
        )

    if database_fixture_dir is not None:
        database_manifest = load_database_fixture(database_fixture_dir)
        database_report = {}
        report["database_fixture"] = {
            "generator": database_manifest["generator"],
            "directories": database_manifest["directories"],
            "entries": database_manifest["entries"],
            "cases": database_report,
        }
        for case in DATABASE_CASES:
            left = observe(
                args.left_image,
                args.left_binary,
                case.arguments,
                database_fixture_dir,
                "/dbfx",
            )
            right = observe(
                args.right_image,
                args.right_binary,
                case.arguments,
                database_fixture_dir,
                "/dbfx",
            )
            differences = compare_observations(left, right)
            entry: dict[str, object] = {
                "arguments": list(case.arguments),
                "left": left.summary(),
                "right": right.summary(),
                "differences": differences,
                "left_reports_load_error": (
                    b"Cannot load database:" in left.stdout
                ),
                "right_reports_load_error": (
                    b"Cannot load database:" in right.stdout
                ),
            }
            if case.name.endswith("_json"):
                entry["left_valid_json"] = document_is_valid(
                    left.stdout, "json"
                )
                entry["right_valid_json"] = document_is_valid(
                    right.stdout, "json"
                )
            database_report[case.name] = entry
            failures.extend(
                f"database_fixture.{case.name}.{item}"
                for item in differences
            )

    if nested_corpus_dir is not None:
        samples = load_nested_corpus(nested_corpus_dir)
        nested_report = {}
        report["nested_corpus"] = {
            "generator": "tools/corpus/generate_nested_corpus.py",
            "samples": samples,
            "cases": nested_report,
        }
        for sample in samples:
            name = str(sample["name"])
            sample_report = {}
            nested_report[name] = sample_report
            observations = {}
            for case in NESTED_MATRIX:
                arguments = (
                    *case.arguments,
                    f"/nested/{name}",
                )
                left = observe(
                    args.left_image,
                    args.left_binary,
                    arguments,
                    nested_corpus_dir,
                    "/nested",
                )
                right = observe(
                    args.right_image,
                    args.right_binary,
                    arguments,
                    nested_corpus_dir,
                    "/nested",
                )
                differences = compare_observations(left, right)
                observations[case.name] = (left, right)
                sample_report[case.name] = {
                    "arguments": list(arguments),
                    "left": left.summary(),
                    "right": right.summary(),
                    "differences": differences,
                    "left_detect_tree": json_detect_tree(left.stdout),
                    "right_detect_tree": json_detect_tree(right.stdout),
                }
                failures.extend(
                    f"nested_corpus.{name}.{case.name}.{item}"
                    for item in differences
                )

            default_left, default_right = observations["default"]
            for case_name, (left, right) in observations.items():
                entry = sample_report[case_name]
                entry["left_changes"] = compare_observations(
                    default_left, left
                )
                entry["right_changes"] = compare_observations(
                    default_right, right
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
