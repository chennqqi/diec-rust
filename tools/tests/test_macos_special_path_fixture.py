import errno
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GENERATOR_PATH = (
    ROOT / "tools/corpus/generate_macos_special_path_fixture.py"
)
VALIDATOR_PATH = (
    ROOT / "tools/corpus/validate_macos_special_path_fixture.py"
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


GENERATOR = load_module(
    "generate_macos_special_path_fixture_test", GENERATOR_PATH
)
VALIDATOR = load_module(
    "validate_macos_special_path_fixture_test", VALIDATOR_PATH
)


def candidate_report(
    *,
    case_alias: bool,
    unicode_alias: bool,
    raw_created: tuple[bool, bool, bool] = (True, False, True),
) -> dict:
    manifest_raw = (
        ROOT / GENERATOR.BASELINE_MANIFEST
    ).read_bytes()
    manifest = json.loads(manifest_raw)
    sample = next(
        item
        for item in manifest["samples"]
        if item["name"] == GENERATOR.SOURCE_NAME
    )
    entries = []
    for case_id, relative in GENERATOR.STABLE_ENTRIES:
        entries.append(
            {
                "id": case_id,
                "path": relative,
                "directory_name_bytes_hex": (
                    relative.rsplit("/", 1)[1].encode().hex()
                ),
                "size": sample["size"],
                "sha256": sample["sha256"],
            }
        )
    if not case_alias:
        entries.append(
            {
                "id": GENERATOR.CASE_ALIAS[0],
                "path": GENERATOR.CASE_ALIAS[1],
                "directory_name_bytes_hex": (
                    GENERATOR.CASE_ALIAS[1]
                    .rsplit("/", 1)[1]
                    .encode()
                    .hex()
                ),
                "size": sample["size"],
                "sha256": sample["sha256"],
            }
        )
    if not unicode_alias:
        entries.append(
            {
                "id": GENERATOR.UNICODE_ALIAS[0],
                "path": GENERATOR.UNICODE_ALIAS[1],
                "directory_name_bytes_hex": (
                    GENERATOR.UNICODE_ALIAS[1]
                    .rsplit("/", 1)[1]
                    .encode()
                    .hex()
                ),
                "size": sample["size"],
                "sha256": sample["sha256"],
            }
        )
    raw_attempts = []
    for name, created in zip(
        GENERATOR.RAW_NAMES, raw_created, strict=True
    ):
        raw_attempts.append(
            {
                "name_bytes_hex": name.hex(),
                "created": created,
                "errno": None if created else errno.EILSEQ,
                "size": sample["size"] if created else None,
                "sha256": sample["sha256"] if created else None,
            }
        )
    inventory = {
        directory: [] for directory in GENERATOR.DIRECTORIES
    }
    for entry in entries:
        parent = entry["path"].rsplit("/", 1)[0]
        inventory[parent].append(
            entry["directory_name_bytes_hex"]
        )
    for attempt in raw_attempts:
        if attempt["created"]:
            inventory["nonutf8"].append(
                attempt["name_bytes_hex"]
            )
    return {
        "schema_version": 1,
        "result": "candidate",
        "platform": GENERATOR.PLATFORM,
        "generator": {
            "path": GENERATOR.GENERATOR,
            "sha256": hashlib.sha256(
                GENERATOR_PATH.read_bytes()
            ).hexdigest(),
            "validator_path": GENERATOR.VALIDATOR,
            "validator_sha256": hashlib.sha256(
                VALIDATOR_PATH.read_bytes()
            ).hexdigest(),
        },
        "source": {
            "manifest": GENERATOR.BASELINE_MANIFEST,
            "manifest_sha256": hashlib.sha256(
                manifest_raw
            ).hexdigest(),
            "sample": GENERATOR.SOURCE_NAME,
            "size": sample["size"],
            "sha256": sample["sha256"],
        },
        "fixture": {
            "local_path": "/private/tmp/macos-special-path",
            "directories": list(GENERATOR.DIRECTORIES),
            "entries": entries,
            "raw_attempts": raw_attempts,
            "directory_inventory_name_bytes_hex": inventory,
        },
        "filesystem_observations": {
            "lowercase_alias_exists_after_upper_create": case_alias,
            "lowercase_alias_is_same_file": case_alias,
            "case_distinct_names_materialized": not case_alias,
            "nfd_alias_exists_after_nfc_create": unicode_alias,
            "nfd_alias_is_same_file": unicode_alias,
            "nfc_nfd_distinct_names_materialized": (
                not unicode_alias
            ),
        },
        "admission": {
            "fixture_admitted": False,
            "capability_rows_admitted": 0,
            "reason": GENERATOR.ADMISSION_REASON,
        },
        "limitations": GENERATOR.LIMITATIONS,
    }


class MacosSpecialPathFixtureTests(unittest.TestCase):
    def test_validator_accepts_all_alias_modes(self):
        for case_alias in (False, True):
            for unicode_alias in (False, True):
                with self.subTest(
                    case_alias=case_alias,
                    unicode_alias=unicode_alias,
                ), tempfile.TemporaryDirectory() as temporary:
                    report_path = (
                        Path(temporary)
                        / "special-path-fixture-candidate.json"
                    )
                    report = candidate_report(
                        case_alias=case_alias,
                        unicode_alias=unicode_alias,
                    )
                    report_path.write_text(
                        json.dumps(report, sort_keys=True),
                        encoding="utf-8",
                    )
                    VALIDATOR.validate_report(
                        report,
                        report_path=report_path,
                        root=ROOT,
                    )

    def test_validator_rejects_admission_inventory_and_alias_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            report_path = (
                Path(temporary)
                / "special-path-fixture-candidate.json"
            )
            report = candidate_report(
                case_alias=True,
                unicode_alias=True,
            )
            report_path.write_text(
                json.dumps(report, sort_keys=True),
                encoding="utf-8",
            )
            report["admission"]["fixture_admitted"] = True
            with self.assertRaisesRegex(
                VALIDATOR.ReportError, "must not admit"
            ):
                VALIDATOR.validate_report(
                    report,
                    report_path=report_path,
                    root=ROOT,
                )
            report["admission"]["fixture_admitted"] = False
            report["filesystem_observations"][
                "case_distinct_names_materialized"
            ] = True
            with self.assertRaisesRegex(
                VALIDATOR.ReportError, "alias projection"
            ):
                VALIDATOR.validate_report(
                    report,
                    report_path=report_path,
                    root=ROOT,
                )
            report["filesystem_observations"][
                "case_distinct_names_materialized"
            ] = False
            report["fixture"][
                "directory_inventory_name_bytes_hex"
            ]["special"].append("00")
            with self.assertRaisesRegex(
                VALIDATOR.ReportError, "directory inventory"
            ):
                VALIDATOR.validate_report(
                    report,
                    report_path=report_path,
                    root=ROOT,
                )

    def test_generator_refuses_non_macos_before_writing(self):
        if sys.platform == "darwin":
            self.skipTest("native Darwin is the intended generator host")
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            with self.assertRaisesRegex(
                GENERATOR.FixtureError, "native Darwin x86_64"
            ):
                GENERATOR.generate(
                    root=ROOT,
                    baseline_dir=directory,
                    fixture_dir=directory / "fixture",
                    output=directory / "candidate.json",
                )
            self.assertFalse((directory / "fixture").exists())


if __name__ == "__main__":
    unittest.main()
