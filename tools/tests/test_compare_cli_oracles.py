import hashlib
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT / "tools"
    / "upstream"
    / "compare_cli_oracles.py"
)
SPEC = importlib.util.spec_from_file_location("compare_cli_oracles", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class CompareObservationsTests(unittest.TestCase):
    def test_committed_qt5_qt6_report_has_one_exact_difference(self):
        report = json.loads(
            (
                ROOT / "docs/research/data/qt5-qt6-cli.json"
            ).read_text(encoding="utf-8")
        )
        revision = "74eaf505c250ab47e709024e9dc41657cd8f2254"
        self.assertEqual(report["expected_revision"], revision)
        self.assertEqual(report["left_revision"], revision)
        self.assertEqual(report["right_revision"], revision)
        self.assertEqual(len(report["cases"]), 8)
        self.assertEqual(len(report["unreadable_input"]), 4)
        self.assertEqual(len(report["corpus"]), 15)
        self.assertFalse(report["equal"])
        self.assertEqual(
            report["failures"],
            ["corpus.minimal.exe.stderr"],
        )

        for case in report["cases"].values():
            self.assertEqual(case["differences"], [])
        for case in report["unreadable_input"].values():
            self.assertEqual(case["differences"], [])
        differing = {
            name: case["differences"]
            for name, case in report["corpus"].items()
            if case["differences"]
        }
        self.assertEqual(differing, {"minimal.exe": ["stderr"]})

        minimal = report["corpus"]["minimal.exe"]
        self.assertEqual(minimal["left"]["exit_code"], 0)
        self.assertEqual(minimal["right"]["exit_code"], 0)
        self.assertEqual(
            minimal["left"]["stdout_sha256"],
            minimal["right"]["stdout_sha256"],
        )
        self.assertEqual(
            minimal["left_detect_tree"],
            minimal["right_detect_tree"],
        )
        self.assertEqual(
            minimal["left"]["stderr_sha256"],
            hashlib.sha256(b"").hexdigest(),
        )
        self.assertEqual(
            minimal["right"]["stderr_sha256"],
            (
                "b303e6913e76b70a6f0d6a4d3ccd389"
                "bc342589e45e1615873a37334dea8c51b"
            ),
        )

    def test_parse_args_accepts_optional_output_path(self):
        original = sys.argv
        try:
            sys.argv = [
                "compare_cli_oracles.py",
                "--left-image",
                "left",
                "--left-binary",
                "/left",
                "--right-image",
                "right",
                "--right-binary",
                "/right",
                "--expected-revision",
                "revision",
                "--output",
                "report.json",
            ]
            arguments = MODULE.parse_args()
        finally:
            sys.argv = original
        self.assertEqual(arguments.output, pathlib.Path("report.json"))

    def test_accepts_identical_observations(self):
        observation = MODULE.Observation(0, b"same\n", b"")

        self.assertEqual(
            MODULE.compare_observations(observation, observation),
            [],
        )

    def test_reports_each_observable_difference(self):
        left = MODULE.Observation(0, b"left", b"left error")
        right = MODULE.Observation(1, b"right", b"right error")

        self.assertEqual(
            MODULE.compare_observations(left, right),
            ["exit_code", "stdout", "stderr"],
        )

    def test_summary_hashes_raw_bytes(self):
        observation = MODULE.Observation(1, b"output\r\n", b"error\n")

        self.assertEqual(
            observation.summary(),
            {
                "exit_code": 1,
                "stdout_sha256": (
                    "50be220f44c8a03a97b92b50debecbbdb2876205aa5d0e"
                    "ec4b69c93a17c64b48"
                ),
                "stderr_sha256": (
                    "f097b5f4f46cda2da21b954c9ff4097e1e14ae7064ecde"
                    "e2c2cec2d3c1f08e6b"
                ),
            },
        )

    def test_output_precedence_case_lists_all_flags(self):
        case = next(
            item
            for item in MODULE.OUTPUT_MATRIX
            if item.name == "all_output_flags"
        )

        self.assertEqual(
            case.arguments[:5],
            ("--xml", "--json", "--csv", "--tsv", "--plaintext"),
        )

    def test_scan_matrix_has_default_and_combined_cases(self):
        self.assertEqual(
            [case.name for case in MODULE.SCAN_MATRIX],
            [
                "default",
                "deep",
                "heuristic",
                "aggressive",
                "alltypes",
                "format",
                "hideunknown",
                "combined",
            ],
        )

    def test_nested_matrix_separates_recursive_and_aggressive_flags(self):
        self.assertEqual(
            [case.name for case in MODULE.NESTED_MATRIX],
            [
                "default",
                "recursive",
                "aggressive",
                "recursive_aggressive",
            ],
        )

    def test_output_matrix_has_each_supported_normal_scan_formatter(self):
        self.assertEqual(
            [case.name for case in MODULE.OUTPUT_MATRIX],
            [
                "text",
                "plaintext",
                "json",
                "xml",
                "csv",
                "tsv",
                "all_output_flags",
            ],
        )

    def test_special_matrix_covers_formatters_structs_and_precedence(self):
        self.assertEqual(
            [case.name for case in MODULE.SPECIAL_MATRIX],
            [
                "entropy_text",
                "entropy_plaintext",
                "entropy_json",
                "entropy_xml",
                "entropy_csv",
                "entropy_tsv",
                "entropy_all_output_flags",
                "info_text",
                "info_plaintext",
                "info_json",
                "info_xml",
                "info_csv",
                "info_tsv",
                "info_all_output_flags",
                "struct_hash_json",
                "struct_hash_md5_json",
                "struct_unknown_json",
                "entropy_over_info_struct_json",
                "struct_over_info_json",
            ],
        )

    def test_general_cases_include_structure_inventory(self):
        case_names = [case.name for case in MODULE.CASES]
        self.assertIn("show_structs", case_names)
        self.assertIn("show_structs_with_target", case_names)

    def test_path_cases_cover_recursive_and_mixed_target_behavior(self):
        case_names = [case.name for case in MODULE.PATH_CASES]
        self.assertIn("tree_json", case_names)
        self.assertIn("tree_recursive_json", case_names)
        self.assertIn("missing_and_existing_json", case_names)
        self.assertIn("directory_plus_duplicate_json", case_names)

    def test_database_cases_cover_load_and_script_failures(self):
        case_names = [case.name for case in MODULE.DATABASE_CASES]
        self.assertIn("show_database_missing_main", case_names)
        self.assertIn("show_database_empty_main", case_names)
        self.assertIn("scan_invalid_archive_json", case_names)
        self.assertIn("scan_malformed_main_json", case_names)
        self.assertIn("scan_throwing_main_json", case_names)
        self.assertIn("scan_valid_main_missing_extra_json", case_names)

    def test_unreadable_cases_cover_each_cli_processing_path(self):
        self.assertEqual(
            [case.name for case in MODULE.UNREADABLE_CASES],
            [
                "scan_json",
                "scan_messages_json",
                "info_json",
                "entropy_json",
            ],
        )

    def test_document_validation_preserves_invalid_aggregate_behavior(self):
        self.assertTrue(MODULE.document_is_valid(b'{"value": 1}', "json"))
        self.assertFalse(
            MODULE.document_is_valid(b"/paths/a:\n{\"value\": 1}", "json")
        )
        self.assertTrue(MODULE.document_is_valid(b"<root/>", "xml"))
        self.assertFalse(
            MODULE.document_is_valid(b"<root/><root/>", "xml")
        )

    def test_extracts_only_path_filename_prefix_lines(self):
        self.assertEqual(
            MODULE.filename_prefixes(
                b"/paths/a:\n{\n  \"value\": \"text:\"\n}\n/paths/b:\n"
            ),
            ["/paths/a", "/paths/b"],
        )

    def test_json_detect_tree_keeps_nested_scan_identity_fields(self):
        data = json.dumps(
            {
                "detects": [
                    {
                        "filetype": "PE32",
                        "info": "ignored",
                        "offset": "0",
                        "parentfilepart": "Header",
                        "size": "10",
                        "values": [
                            {
                                "info": "ignored",
                                "name": "PDF",
                                "string": "ignored",
                                "type": "format",
                                "version": "1.4",
                            }
                        ],
                    }
                ]
            }
        ).encode()

        self.assertEqual(
            MODULE.json_detect_tree(data),
            [
                {
                    "filetype": "PE32",
                    "offset": "0",
                    "parentfilepart": "Header",
                    "size": "10",
                    "values": [
                        {
                            "name": "PDF",
                            "type": "format",
                            "version": "1.4",
                        }
                    ],
                }
            ],
        )

    def test_json_detect_tree_rejects_non_scan_output(self):
        self.assertIsNone(MODULE.json_detect_tree(b"not json"))
        self.assertIsNone(MODULE.json_detect_tree(b"[]"))


class LoadCorpusTests(unittest.TestCase):
    def test_loads_and_verifies_manifest(self):
        data = b"sample"
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "sample.bin").write_bytes(data)
            (root / "manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "samples": [
                            {
                                "name": "sample.bin",
                                "size": len(data),
                                "sha256": (
                                    "af2bdbe1aa9b6ec1e2ade1d694f41fc71a831d02"
                                    "68e9891562113d8a62add1bf"
                                ),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            samples = MODULE.load_corpus(root)

        self.assertEqual(samples[0]["name"], "sample.bin")

    def test_rejects_path_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "samples": [
                            {
                                "name": "../escape",
                                "size": 0,
                                "sha256": "0" * 64,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "unsafe"):
                MODULE.load_corpus(root)

    def test_rejects_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "sample.bin").write_bytes(b"sample")
            (root / "manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "samples": [
                            {
                                "name": "sample.bin",
                                "size": 6,
                                "sha256": "0" * 64,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "does not match"):
                MODULE.load_corpus(root)

    def test_nested_corpus_rejects_unexpected_generator(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "sample.bin").write_bytes(b"")
            (root / "manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "generator": "unexpected",
                        "samples": [
                            {
                                "name": "sample.bin",
                                "size": 0,
                                "sha256": (
                                    "e3b0c44298fc1c149afbf4c8996fb924"
                                    "27ae41e4649b934ca495991b7852b855"
                                ),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "generator"):
                MODULE.load_nested_corpus(root)


class LoadPathCorpusTests(unittest.TestCase):
    def test_loads_and_verifies_nested_tree(self):
        data = b"sample"
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            nested = root / "tree" / "nested"
            nested.mkdir(parents=True)
            (nested / "sample.bin").write_bytes(data)
            (root / "manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "directories": ["tree", "tree/nested"],
                        "entries": [
                            {
                                "path": "tree/nested/sample.bin",
                                "source": "sample.bin",
                                "size": len(data),
                                "sha256": (
                                    "af2bdbe1aa9b6ec1e2ade1d694f41fc71a831d02"
                                    "68e9891562113d8a62add1bf"
                                ),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            manifest = MODULE.load_path_corpus(root)

        self.assertEqual(
            manifest["entries"][0]["path"],
            "tree/nested/sample.bin",
        )

    def test_rejects_path_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "directories": ["../escape"],
                        "entries": [],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "unsafe"):
                MODULE.load_path_corpus(root)

    def test_database_fixture_rejects_unexpected_generator(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "generator": "unexpected",
                        "directories": [],
                        "entries": [],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "generator"):
                MODULE.load_database_fixture(root)


if __name__ == "__main__":
    unittest.main()
