#!/usr/bin/env python3
"""Collect a raw-output macOS Qt5 CLI baseline candidate bundle."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import sys
from pathlib import Path
from typing import Any

UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
PLATFORM = "macos-x86_64-qt5"
SHARED_COLLECTOR = "tools/upstream/collect_windows_cli_baseline.py"
ORACLE_VALIDATOR = (
    "tools/upstream/validate_macos_qt5_oracle_report.py"
)
BASELINE_MANIFEST = "docs/research/data/baseline-corpus.json"
LINUX_REFERENCE = (
    "docs/research/data/baseline-corpus-linux-qt5.json"
)
VALIDATOR = "tools/upstream/validate_macos_cli_baseline.py"
ADMISSION_REASON = (
    "general CLI and baseline corpus candidate only; "
    "the complete 68-row macOS closure is missing"
)
LIMITATIONS = [
    (
        "the bundle covers general CLI identity, database "
        "listing, missing-path handling, and one default JSON "
        "scan per generated baseline sample"
    ),
    (
        "option, output, special, nested, filesystem, database "
        "error, and engine-only matrices require separate "
        "macOS evidence"
    ),
    (
        "every raw stdout and stderr stream is retained; only "
        "the named detection projection and exit code are "
        "compared with Linux Qt5"
    ),
]


class BaselineError(ValueError):
    """The candidate bundle cannot be collected safely."""


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise BaselineError(f"cannot load helper module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()

    def reject_duplicates(
        pairs: list[tuple[str, Any]],
    ) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise BaselineError(f"duplicate JSON key: {key}")
            value[key] = item
        return value

    try:
        value = json.loads(
            raw,
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda constant: (_ for _ in ()).throw(
                BaselineError(
                    f"non-finite JSON constant: {constant}"
                )
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BaselineError(f"invalid JSON: {path}: {error}") from error
    if not isinstance(value, dict):
        raise BaselineError(f"JSON root must be an object: {path}")
    return value, raw


def require_empty_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if any(path.iterdir()):
        raise BaselineError(f"raw output directory must be empty: {path}")


def write_observation(
    bundle_dir: Path,
    stem: str,
    observation: Any,
) -> dict[str, object]:
    result = dict(observation.summary())
    for stream, raw in (
        ("stdout", observation.stdout),
        ("stderr", observation.stderr),
    ):
        relative = Path("raw") / f"{stem}.{stream}"
        path = bundle_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        result[f"{stream}_path"] = relative.as_posix()
    return result


def pair_report(
    common: Any,
    bundle_dir: Path,
    stem: str,
    first: Any,
    second: Any,
) -> dict[str, object]:
    paired = common.pair_report(first, second)
    paired["first"] = write_observation(
        bundle_dir, f"{stem}.first", first
    )
    paired["second"] = write_observation(
        bundle_dir, f"{stem}.second", second
    )
    return paired


def expected_cases(common: Any) -> tuple[Any, ...]:
    database = (
        "--database",
        "<source>/Detect-It-Easy/db",
        "--extradatabase",
        "<source>/Detect-It-Easy/db_extra",
        "--customdatabase",
        "<source>/Detect-It-Easy/db_custom",
    )
    return (
        common.Case("version", ("--version",), ("--version",)),
        common.Case("help", ("--help",), ("--help",)),
        common.Case("no_args", (), ()),
        common.Case(
            "show_structs",
            ("--showstructs",),
            ("--showstructs",),
        ),
        common.Case(
            "database",
            ("--showdatabase",),
            ("--showdatabase", *database),
        ),
        common.Case(
            "missing",
            ("does-not-exist",),
            ("<binary-dir>/does-not-exist",),
        ),
    )


def actual_arguments(case: Any, source_dir: Path) -> tuple[str, ...]:
    if case.name == "database":
        return (
            "--showdatabase",
            "--database",
            str(source_dir / "Detect-It-Easy" / "db"),
            "--extradatabase",
            str(source_dir / "Detect-It-Easy" / "db_extra"),
            "--customdatabase",
            str(source_dir / "Detect-It-Easy" / "db_custom"),
        )
    return case.arguments


def validate_oracle_inputs(
    root: Path,
    oracle_path: Path,
    source_dir: Path,
    qt_dir: Path,
    binary: Path,
) -> tuple[dict[str, Any], bytes]:
    oracle_validator = load_module(
        "macos_oracle_validator_for_cli_baseline",
        root / ORACLE_VALIDATOR,
    )
    oracle = oracle_validator.load_report(oracle_path)
    oracle_validator.validate_report(oracle)
    if (
        oracle["source"]["commit"] != UPSTREAM_COMMIT
        or oracle["source"]["rules_commit"] != RULES_COMMIT
    ):
        raise BaselineError("oracle source identity drift")
    local_paths = oracle["local_paths"]
    expected_paths = {
        "source_dir": source_dir,
        "qt_dir": qt_dir,
        "artifact": binary,
    }
    for field, expected in expected_paths.items():
        actual = Path(local_paths[field]).resolve(strict=True)
        if actual != expected:
            raise BaselineError(
                f"oracle local path mismatch: {field}"
            )
    return oracle, oracle_path.read_bytes()


def validate_qt(
    common: Any,
    qt_dir: Path,
    oracle: dict[str, Any],
) -> dict[str, str]:
    qmake = qt_dir / "bin" / "qmake"
    if not qmake.is_file():
        raise BaselineError(f"qmake is missing: {qmake}")
    qt_libs = Path(
        common.run_checked([str(qmake), "-query", "QT_INSTALL_LIBS"])
    )
    qtcore = qt_libs / "QtCore.framework/Versions/5/QtCore"
    qtscript = qt_libs / "QtScript.framework/Versions/5/QtScript"
    for path in (qtcore, qtscript):
        if not path.is_file():
            raise BaselineError(f"Qt framework is missing: {path}")
    actual = {
        "version": common.run_checked(
            [str(qmake), "-query", "QT_VERSION"]
        ),
        "qmake_spec": common.run_checked(
            [str(qmake), "-query", "QMAKE_SPEC"]
        ),
        "qmake_sha256": common.sha256_file(qmake),
        "qtcore_sha256": common.sha256_file(qtcore),
        "qtscript_sha256": common.sha256_file(qtscript),
    }
    expected = {
        "version": oracle["qt"]["version"],
        "qmake_spec": oracle["qt"]["qmake_spec"],
        "qmake_sha256": oracle["qt"]["qmake_sha256"],
        "qtcore_sha256": oracle["qt"]["qtcore_sha256"],
        "qtscript_sha256": oracle["qt"]["qtscript_sha256"],
    }
    if actual != expected:
        raise BaselineError("Qt identity differs from oracle report")
    return actual


def collect(
    *,
    root: Path,
    binary: Path,
    source_dir: Path,
    qt_dir: Path,
    corpus_dir: Path,
    oracle_path: Path,
    output: Path,
    timeout_seconds: int,
) -> dict[str, Any]:
    if sys.platform != "darwin" or platform.machine() != "x86_64":
        raise BaselineError("collector requires native Darwin x86_64")
    if not 1 <= timeout_seconds <= 3600:
        raise BaselineError("timeout-seconds must be in 1..3600")

    source_dir = source_dir.resolve(strict=True)
    qt_dir = qt_dir.resolve(strict=True)
    corpus_dir = corpus_dir.resolve(strict=True)
    binary = binary.resolve(strict=True)
    oracle_path = oracle_path.resolve(strict=True)
    output = output.resolve()
    bundle_dir = output.parent
    bundle_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = bundle_dir / "raw"
    require_empty_directory(raw_dir)
    if output.exists():
        raise BaselineError("candidate report already exists")

    common = load_module(
        "windows_cli_baseline_shared_for_macos",
        root / SHARED_COLLECTOR,
    )
    expected_binary = (
        source_dir / "build" / "release" / "diec"
    ).resolve(strict=True)
    if binary != expected_binary:
        raise BaselineError(
            "binary must be <source>/build/release/diec"
        )

    oracle, oracle_raw = validate_oracle_inputs(
        root, oracle_path, source_dir, qt_dir, binary
    )
    source = common.validate_source(source_dir)
    source["tracked_files_clean_before_and_after"] = True
    qt = validate_qt(common, qt_dir, oracle)
    binary_sha256 = common.sha256_file(binary)
    if binary_sha256 != oracle["artifact"]["sha256"]:
        raise BaselineError("binary differs from oracle report")

    manifest_path = root / BASELINE_MANIFEST
    samples, manifest_sha256 = common.load_corpus(
        corpus_dir, manifest_path
    )
    linux_path = root / LINUX_REFERENCE
    linux, linux_raw = load_json(linux_path)
    linux_corpus = linux.get("corpus")
    if (
        not isinstance(linux_corpus, dict)
        or set(linux_corpus)
        != {str(sample["name"]) for sample in samples}
    ):
        raise BaselineError("Linux reference corpus set differs")

    database_args = (
        "--database",
        str(source_dir / "Detect-It-Easy" / "db"),
        "--extradatabase",
        str(source_dir / "Detect-It-Easy" / "db_extra"),
        "--customdatabase",
        str(source_dir / "Detect-It-Easy" / "db_custom"),
    )
    database_report_args = (
        "--database",
        "<source>/Detect-It-Easy/db",
        "--extradatabase",
        "<source>/Detect-It-Easy/db_extra",
        "--customdatabase",
        "<source>/Detect-It-Easy/db_custom",
    )

    determinism_failures: list[str] = []
    case_reports: dict[str, object] = {}
    for case in expected_cases(common):
        arguments = actual_arguments(case, source_dir)
        first = common.observe(
            binary, qt_dir, arguments, timeout_seconds=timeout_seconds
        )
        second = common.observe(
            binary, qt_dir, arguments, timeout_seconds=timeout_seconds
        )
        paired = pair_report(
            common,
            bundle_dir,
            f"cli-baseline/cases/{case.name}",
            first,
            second,
        )
        paired["arguments"] = list(case.report_arguments)
        case_reports[case.name] = paired
        if paired["determinism_differences"]:
            determinism_failures.append(f"cases.{case.name}")

    corpus_reports: dict[str, object] = {}
    projection_failures: list[str] = []
    for sample in samples:
        name = str(sample["name"])
        if Path(name).name != name:
            raise BaselineError(f"unsafe corpus sample name: {name}")
        arguments = (
            "--json",
            *database_args,
            str(corpus_dir / name),
        )
        first = common.observe(
            binary, qt_dir, arguments, timeout_seconds=timeout_seconds
        )
        second = common.observe(
            binary, qt_dir, arguments, timeout_seconds=timeout_seconds
        )
        paired = pair_report(
            common,
            bundle_dir,
            f"cli-baseline/corpus/{name}",
            first,
            second,
        )
        first_tree = common.json_detect_tree(first.stdout)
        second_tree = common.json_detect_tree(second.stdout)
        linux_item = linux_corpus[name]
        linux_tree = linux_item["left_detect_tree"]
        paired.update(
            {
                "arguments": [
                    "--json",
                    *database_report_args,
                    f"<corpus>/{name}",
                ],
                "intended_format": sample["intended_format"],
                "sample_sha256": sample["sha256"],
                "first_detect_tree": first_tree,
                "second_detect_tree": second_tree,
                "linux_qt5_detect_tree": linux_tree,
                "linux_projection_equal": first_tree == linux_tree,
                "linux_exit_code_equal": (
                    first.exit_code
                    == linux_item["left"]["exit_code"]
                ),
            }
        )
        corpus_reports[name] = paired
        if paired["determinism_differences"]:
            determinism_failures.append(f"corpus.{name}")
        if (
            first_tree != linux_tree
            or first.exit_code != linux_item["left"]["exit_code"]
        ):
            projection_failures.append(name)

    post_source = common.validate_source(source_dir)
    post_source["tracked_files_clean_before_and_after"] = True
    if post_source != source:
        raise BaselineError("source identity changed during collection")
    if common.sha256_file(binary) != binary_sha256:
        raise BaselineError("binary changed during collection")
    _, post_manifest_sha256 = common.load_corpus(
        corpus_dir, manifest_path
    )
    if post_manifest_sha256 != manifest_sha256:
        raise BaselineError("corpus changed during collection")

    report = {
        "schema_version": 1,
        "result": "candidate",
        "platform": PLATFORM,
        "generator": {
            "path": (
                "tools/upstream/collect_macos_cli_baseline.py"
            ),
            "sha256": sha256(Path(__file__).read_bytes()),
            "shared_collector_path": SHARED_COLLECTOR,
            "shared_collector_sha256": sha256(
                (root / SHARED_COLLECTOR).read_bytes()
            ),
            "validator_path": VALIDATOR,
            "validator_sha256": sha256(
                (root / VALIDATOR).read_bytes()
            ),
        },
        "oracle_report": {
            "path": "oracle-candidate.json",
            "sha256": sha256(oracle_raw),
        },
        "source": source,
        "qt": qt,
        "binary": {
            "size": binary.stat().st_size,
            "sha256": binary_sha256,
            "relative_path": "build/release/diec",
        },
        "corpus_manifest": {
            "path": BASELINE_MANIFEST,
            "sha256": manifest_sha256,
            "sample_count": len(samples),
        },
        "linux_qt5_reference": {
            "path": LINUX_REFERENCE,
            "sha256": sha256(linux_raw),
        },
        "cases": case_reports,
        "corpus": corpus_reports,
        "summary": {
            "case_count": len(case_reports),
            "corpus_count": len(corpus_reports),
            "execution_count": 2
            * (len(case_reports) + len(corpus_reports)),
            "determinism_failures": determinism_failures,
            "linux_projection_failures": projection_failures,
            "deterministic": not determinism_failures,
            "linux_projection_equal": not projection_failures,
        },
        "admission": {
            "platform_admitted": False,
            "capability_rows_admitted": 0,
            "reason": ADMISSION_REASON,
        },
        "limitations": LIMITATIONS,
    }
    output.write_bytes(
        (
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    )
    return report


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--qt-dir", type=Path, required=True)
    parser.add_argument("--corpus-dir", type=Path, required=True)
    parser.add_argument("--oracle-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.set_defaults(root=root)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        collect(
            root=args.root.resolve(),
            binary=args.binary,
            source_dir=args.source_dir,
            qt_dir=args.qt_dir,
            corpus_dir=args.corpus_dir,
            oracle_path=args.oracle_report,
            output=args.output,
            timeout_seconds=args.timeout_seconds,
        )
    except (BaselineError, OSError, ValueError) as error:
        print(f"macOS CLI baseline error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
