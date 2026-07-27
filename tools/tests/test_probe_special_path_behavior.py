import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zlib


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT / "tools" / "upstream" / "probe_special_path_behavior.py"
)
REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "special-path-engine-qt5.json"
)
MANIFEST_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "special-path-fixture.json"
)
DOCUMENT_PATH = (
    ROOT / "docs" / "research" / "special-path-behavior.md"
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MODULE = load_module("probe_special_path_behavior", MODULE_PATH)
BASELINE = load_module(
    "generate_baseline_corpus_for_special_path_probe_tests",
    ROOT / "tools" / "corpus" / "generate_baseline_corpus.py",
)
GENERATOR = load_module(
    "generate_special_path_fixture_for_probe_tests",
    ROOT / "tools" / "corpus" / "generate_special_path_fixture.py",
)


class ProbeSpecialPathBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        cls.manifest = json.loads(
            MANIFEST_PATH.read_text(encoding="utf-8")
        )

    def artifact(self, reference):
        artifact = self.report["raw_artifacts"][
            reference["artifact_sha256"]
        ]
        return zlib.decompress(
            base64.b64decode(artifact["base64"], validate=True)
        )

    def test_report_passes_and_binds_fixed_identity(self):
        self.assertTrue(self.report["passed"])
        self.assertEqual(self.report["failures"], [])
        self.assertTrue(all(self.report["facts"].values()))
        self.assertEqual(
            self.report["upstream_commit"],
            MODULE.UPSTREAM_COMMIT,
        )
        self.assertEqual(
            self.report["generator_sha256"],
            hashlib.sha256(MODULE_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            self.report["fixture"]["manifest_sha256"],
            hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(self.report["fixture"]["file_count"], 21)
        self.assertEqual(set(self.report["images"]), set(MODULE.ORACLES))
        for image in self.report["images"].values():
            self.assertRegex(image["id"], r"^sha256:[0-9a-f]{64}$")

    def test_all_cases_have_byte_equal_qmake_and_cmake_results(self):
        self.assertEqual(
            set(self.report["cases"]),
            {
                *(case.name for case in MODULE.CASES),
                *(case.name for case in MODULE.RAW_ARGV_CASES),
            },
        )
        self.assertEqual(len(self.report["cases"]), 23)
        for name, case in self.report["cases"].items():
            with self.subTest(case=name):
                observations = case["observations"]
                self.assertEqual(
                    observations["qmake"]["exit_code"],
                    observations["cmake"]["exit_code"],
                )
                self.assertEqual(
                    observations["qmake"]["stdout"],
                    observations["cmake"]["stdout"],
                )
                self.assertEqual(
                    observations["qmake"]["stderr"],
                    observations["cmake"]["stderr"],
                )

    def test_unicode_special_and_directory_semantics_are_frozen(self):
        cases = self.report["cases"]
        self.assertEqual(
            cases["directory_special"]["filename_prefix_order"],
            list(MODULE.EXPECTED_DIRECTORY_ORDER),
        )
        self.assertNotIn(
            "paths/special/.hidden.pdf",
            cases["directory_special"]["filename_prefix_order"],
        )
        self.assertEqual(
            cases["single_hidden"]["observations"]["cmake"]["exit_code"],
            0,
        )
        self.assertEqual(
            cases["explicit_order"]["filename_prefix_order"],
            [
                "paths/special/emoji-😀.pdf",
                "paths/special/é-nfc.pdf",
                "paths/special/00-ascii.pdf",
            ],
        )
        self.assertEqual(
            cases["single_nfc"]["filename_prefix_order"],
            [],
        )
        self.assertEqual(
            cases["single_nfd"]["filename_prefix_order"],
            [],
        )

    def test_leading_dash_requires_option_terminator_when_relative(self):
        cases = self.report["cases"]
        unescaped = cases["single_leading_dash_relative_unescaped"]
        escaped = cases["single_leading_dash_relative_escaped"]
        absolute = cases["single_leading_dash_absolute"]
        self.assertEqual(
            unescaped["observations"]["cmake"]["exit_code"],
            1,
        )
        diagnostic = self.artifact(
            unescaped["observations"]["cmake"]["stderr"]
        )
        self.assertIn(b"Unknown option 'leading-dash.pdf'.", diagnostic)
        self.assertEqual(escaped["observations"]["cmake"]["exit_code"], 0)
        self.assertEqual(absolute["observations"]["cmake"]["exit_code"], 0)

    def test_non_utf8_entries_exist_but_qdir_skips_them(self):
        expected = sorted(
            [
                b"ascii-control.pdf".hex(),
                *(
                    path_bytes.rsplit(b"/", 1)[1].hex()
                    for path_bytes, _ in GENERATOR.RAW_FILES
                ),
            ]
        )
        self.assertEqual(
            self.report["fixture"][
                "non_utf8_extracted_basename_hex"
            ],
            expected,
        )
        directory = self.report["cases"]["directory_non_utf8"]
        control = self.report["cases"]["single_non_utf8_control"]
        self.assertEqual(
            directory["raw_path_summary"],
            {
                "ascii_control_prefix_present": False,
                "pdf_root_count": 1,
                "replacement_character_count": 0,
                "stdout_utf8_valid": True,
            },
        )
        for oracle in MODULE.ORACLES:
            with self.subTest(oracle=oracle):
                self.assertEqual(
                    directory["observations"][oracle]["stdout"],
                    control["observations"][oracle]["stdout"],
                )
                self.assertEqual(
                    directory["observations"][oracle]["stderr"],
                    control["observations"][oracle]["stderr"],
                )
                self.assertEqual(
                    directory["observations"][oracle]["exit_code"],
                    0,
                )

    def test_explicit_non_utf8_argv_is_lossy_and_cannot_open(self):
        for raw_case in MODULE.RAW_ARGV_CASES:
            case = self.report["cases"][raw_case.name]
            expected = MODULE.EXPECTED_RAW_ARGV[raw_case.name]
            with self.subTest(case=raw_case.name):
                self.assertEqual(
                    case["path_bytes_hex"],
                    raw_case.path_bytes_hex,
                )
                self.assertEqual(
                    case["raw_argv_summary"],
                    {
                        "cannot_find_count": 1,
                        "pdf_root_count": 0,
                        "replacement_character_count": expected[
                            "replacement_character_count"
                        ],
                        "stdout_utf8_valid": True,
                    },
                )
                for oracle in MODULE.ORACLES:
                    observation = case["observations"][oracle]
                    self.assertEqual(observation["exit_code"], 1)
                    self.assertEqual(
                        observation["stdout"]["sha256"],
                        expected["stdout_sha256"],
                    )
                    self.assertEqual(
                        observation["stderr"]["sha256"],
                        hashlib.sha256(b"").hexdigest(),
                    )

    def test_raw_artifacts_are_content_addressed_and_complete(self):
        referenced = set()
        for case in self.report["cases"].values():
            for observation in case["observations"].values():
                referenced.add(
                    observation["stdout"]["artifact_sha256"]
                )
                referenced.add(
                    observation["stderr"]["artifact_sha256"]
                )
        self.assertEqual(referenced, set(self.report["raw_artifacts"]))
        for digest, artifact in self.report["raw_artifacts"].items():
            with self.subTest(digest=digest):
                raw = zlib.decompress(
                    base64.b64decode(
                        artifact["base64"],
                        validate=True,
                    )
                )
                self.assertEqual(len(raw), artifact["bytes"])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), digest)

    def test_source_contract_and_resource_limits_are_fixed(self):
        self.assertEqual(
            set(self.report["source_contract"]),
            set(MODULE.SOURCE_PATHS),
        )
        for record in self.report["source_contract"].values():
            self.assertTrue(
                all(
                    count >= 1
                    for count in record["required_patterns"].values()
                )
            )
        self.assertEqual(
            self.report["resource_limits"],
            {
                "container_root": "read-only",
                "cpus": 1,
                "fixture_mount": "read-only",
                "memory_bytes": 512 * 1024 * 1024,
                "network": "none",
                "pids": 128,
                "timeout_seconds_per_execution": 60,
                "work_tmpfs_bytes": 16 * 1024 * 1024,
            },
        )

    def test_fixture_loader_rejects_modified_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / "baseline"
            fixture = root / "fixture"
            BASELINE.generate(baseline)
            GENERATOR.generate(baseline, fixture)
            archive = fixture / GENERATOR.ARCHIVE_NAME
            archive.write_bytes(archive.read_bytes() + b"x")
            with self.assertRaisesRegex(
                MODULE.ProbeError,
                "archive bytes changed",
            ):
                MODULE.load_fixture(fixture, MANIFEST_PATH)

    def test_research_document_records_observed_boundaries(self):
        document = DOCUMENT_PATH.read_text(encoding="utf-8")
        for token in (
            "NFC",
            "NFD",
            "leading-dash",
            "非 UTF-8",
            "CAP-GAP-003",
        ):
            self.assertIn(token, document)


if __name__ == "__main__":
    unittest.main()
