import base64
import hashlib
import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[2]
REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "database-archive-linux-qt5.json"
)
CACHE_PATH = (
    ROOT / "docs" / "research" / "data" / "database-cache-cli.json"
)
FIXTURE_PATH = (
    ROOT / "docs" / "research" / "data" / "database-fixture.json"
)
DOCUMENT_PATH = (
    ROOT / "docs" / "research" / "database-archive-cache.md"
)


class DatabaseArchiveCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        cls.cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def raw(self, case_name, side="left", stream="stdout"):
        case = self.report["database_fixture"]["cases"][case_name]
        data = base64.b64decode(case[side][f"{stream}_base64"])
        summary = case[side]
        self.assertEqual(len(data), summary[f"{stream}_bytes"])
        self.assertEqual(
            hashlib.sha256(data).hexdigest(),
            summary[f"{stream}_sha256"],
        )
        return data

    def detection_names(self, case_name):
        document = json.loads(self.raw(case_name))
        return [
            value["name"]
            for value in document["detects"][0]["values"]
        ]

    def test_report_is_bound_to_generator_images_and_fixture(self):
        self.assertEqual(self.report["schema_version"], 1)
        self.assertEqual(
            self.report["generator"],
            "tools/upstream/probe_database_archives.py",
        )
        generator = ROOT / self.report["generator"]
        self.assertEqual(
            hashlib.sha256(generator.read_bytes()).hexdigest(),
            self.report["generator_sha256"],
        )
        shared_helper = ROOT / self.report["shared_helper"]
        self.assertEqual(
            hashlib.sha256(shared_helper.read_bytes()).hexdigest(),
            self.report["shared_helper_sha256"],
        )
        fixture_generator = (
            ROOT / "tools" / "corpus" / "generate_database_fixture.py"
        )
        self.assertEqual(
            hashlib.sha256(fixture_generator.read_bytes()).hexdigest(),
            self.report["fixture_generator_sha256"],
        )
        revision = "74eaf505c250ab47e709024e9dc41657cd8f2254"
        self.assertEqual(self.report["expected_revision"], revision)
        self.assertEqual(self.report["left_revision"], revision)
        self.assertEqual(self.report["right_revision"], revision)
        self.assertEqual(
            self.report["left_image_id"],
            (
                "sha256:"
                "cc5561a5d256c7912227a8ecf4ba9c6b9178c99911e471"
                "017d3c3988bac964ab"
            ),
        )
        self.assertEqual(
            self.report["right_image_id"],
            (
                "sha256:"
                "466102628c3a94b7ab1048f0c24261b1920e61a40029b1"
                "28763cf79370255040"
            ),
        )
        self.assertTrue(self.report["equal"])
        self.assertEqual(self.report["failures"], [])
        self.assertEqual(
            self.report["database_fixture"]["directories"],
            self.fixture["directories"],
        )
        self.assertEqual(
            self.report["database_fixture"]["entries"],
            self.fixture["entries"],
        )
        self.assertEqual(
            hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest(),
            self.report["database_fixture"]["manifest_sha256"],
        )

    def test_all_17_archive_cases_preserve_both_raw_streams(self):
        cases = self.report["database_fixture"]["cases"]
        self.assertEqual(len(cases), 17)
        for name, case in cases.items():
            with self.subTest(case=name):
                self.assertEqual(case["differences"], [])
                self.assertEqual(
                    self.raw(name, "left", "stdout"),
                    self.raw(name, "right", "stdout"),
                )
                self.assertEqual(
                    self.raw(name, "left", "stderr"),
                    self.raw(name, "right", "stderr"),
                )

    def test_valid_and_tolerated_truncations_execute_same_rule(self):
        names = (
            "scan_valid_archive_json",
            "scan_truncated_archive_json",
            "scan_local_only_archive_json",
            "scan_payload_truncated_archive_json",
        )
        for name in names:
            with self.subTest(case=name):
                self.assertEqual(self.detection_names(name), ["Fixture"])
                case = self.report["database_fixture"]["cases"][name]
                self.assertTrue(case["left_valid_json"])
                self.assertEqual(case["left"]["exit_code"], 0)

        hashes = {
            self.report["database_fixture"]["cases"][name]["left"][
                "stdout_sha256"
            ]
            for name in names
        }
        self.assertEqual(
            hashes,
            {
                "f4aba52e28e2dcc3bffc03eb016364485834d7501a0a0"
                "859fbfa4bee2593fa17"
            },
        )

    def test_empty_header_truncated_and_prefixed_are_unknown(self):
        for name in (
            "scan_empty_archive_json",
            "scan_local_header_truncated_archive_json",
            "scan_prefixed_archive_json",
        ):
            with self.subTest(case=name):
                self.assertEqual(self.detection_names(name), ["Unknown"])
                self.assertTrue(
                    self.report["database_fixture"]["cases"][name][
                        "left_valid_json"
                    ]
                )

    def test_structurally_truncated_rule_preserves_raw_parse_error(self):
        name = "scan_payload_structure_truncated_archive_json"
        raw = self.raw(name)
        marker = b"\nfixture.1.sg:"
        json_bytes, diagnostic = raw.split(marker, maxsplit=1)
        document = json.loads(json_bytes)
        self.assertEqual(
            [value["name"] for value in document["detects"][0]["values"]],
            ["Unknown"],
        )
        self.assertEqual(
            marker[1:] + diagnostic,
            (
                b"fixture.1.sg: Binary/fixture.1.sg: 4: "
                b"SyntaxError: Parse error\n\n"
            ),
        )
        case = self.report["database_fixture"]["cases"][name]
        self.assertFalse(case["left_valid_json"])
        self.assertEqual(case["left"]["exit_code"], 0)

    def test_duplicate_and_dotdot_entry_names_are_executed(self):
        self.assertEqual(
            self.detection_names("scan_duplicate_archive_json"),
            ["DuplicateFirst", "DuplicateSecond"],
        )
        self.assertEqual(
            self.detection_names("scan_traversal_archive_json"),
            ["TraversalName"],
        )

    def test_show_database_counts_records_without_central_directory(self):
        for name in (
            "show_database_valid_archive",
            "show_database_truncated_archive",
            "show_database_local_only_archive",
            "show_database_payload_truncated_archive",
            "show_database_payload_structure_truncated_archive",
        ):
            with self.subTest(case=name):
                self.assertIn(b"\tBinary: 1\n", self.raw(name))
        for name in (
            "show_database_empty_archive",
            "show_database_local_header_truncated_archive",
        ):
            with self.subTest(case=name):
                self.assertNotIn(b"\tBinary:", self.raw(name))

    def test_cli_cache_probe_and_source_findings_are_explicit(self):
        self.assertEqual(
            hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest(),
            self.cache["fixture"]["manifest_sha256"],
        )
        self.assertFalse(self.cache["cache"]["cli_b_use_cache"])
        self.assertEqual(
            self.cache["cache"]["filename"],
            "2a513e7f3b4e0f02c53e6da3c4b0d866.cache",
        )
        self.assertEqual(len(self.cache["observations"]), 2)
        for observation in self.cache["observations"]:
            self.assertEqual(observation["cache_after_load"], "removed")
            self.assertEqual(observation["exit_code"], 0)

        findings = self.cache["source_findings"]
        self.assertTrue(findings["cli_zero_initializes_scan_options"])
        self.assertTrue(findings["cli_never_enables_b_use_cache"])
        self.assertTrue(findings["zip_database_bypasses_cache"])
        self.assertTrue(
            findings["disabled_cache_removes_matching_cache_file"]
        )
        self.assertEqual(findings["cache_magic"], "0x44494543")
        self.assertEqual(findings["cache_version"], 5)
        self.assertFalse(findings["cache_validates_content_hashes"])
        self.assertFalse(findings["cache_read_all_is_bounded"])
        self.assertFalse(findings["cache_record_count_is_bounded"])

    def test_document_and_research_index_link_machine_evidence(self):
        document = DOCUMENT_PATH.read_text(encoding="utf-8")
        index = (ROOT / "docs" / "research" / "README.md").read_text(
            encoding="utf-8"
        )
        for filename in (
            REPORT_PATH.name,
            CACHE_PATH.name,
            FIXTURE_PATH.name,
        ):
            self.assertIn(filename, document)
            self.assertIn(filename, index)
        self.assertIn("engine `bUseCache=true`", document)
        self.assertIn("仍未覆盖", document)


if __name__ == "__main__":
    unittest.main()
