import hashlib
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT
    / "tools"
    / "corpus"
    / "generate_rule_orchestration_fixture.py"
)
MANIFEST_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "rule-orchestration-fixture.json"
)
SPEC = importlib.util.spec_from_file_location(
    "generate_rule_orchestration_fixture",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class GenerateRuleOrchestrationFixtureTests(unittest.TestCase):
    def test_generation_is_deterministic_and_matches_manifest(self):
        expected = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as first_directory:
            with tempfile.TemporaryDirectory() as second_directory:
                first_root = pathlib.Path(first_directory)
                second_root = pathlib.Path(second_directory)
                first = MODULE.generate(first_root)
                second = MODULE.generate(second_root)

                self.assertEqual(first, expected)
                self.assertEqual(second, expected)
                for entry in expected["entries"]:
                    first_data = (
                        first_root / pathlib.PurePosixPath(entry["path"])
                    ).read_bytes()
                    second_data = (
                        second_root / pathlib.PurePosixPath(entry["path"])
                    ).read_bytes()
                    self.assertEqual(first_data, second_data)
                    self.assertEqual(len(first_data), entry["size"])
                    self.assertEqual(
                        hashlib.sha256(first_data).hexdigest(),
                        entry["sha256"],
                    )

    def test_fixture_covers_layers_filters_init_and_include(self):
        manifest = json.loads(
            MANIFEST_PATH.read_text(encoding="utf-8")
        )
        paths = {entry["path"] for entry in manifest["entries"]}
        self.assertTrue(
            {
                "main/_init",
                "extra/_init",
                "custom/_init",
                "main/shared_helper",
                "extra/shared_helper",
                "custom/shared_helper",
                "main/Binary/_init",
                "extra/Binary/_init",
                "custom/Binary/_init",
                "main/Binary/DS.deep.2.sg",
                "main/Binary/EP.entrypoint.4.sg",
                "main/Binary/HEUR.heuristic.3.sg",
                "main/PE/decoy.0.sg",
                "priority-main/Binary/z_priority.1.sg",
                "priority-main/Binary/a_priority.2.sg",
                "priority-main/Binary/m_priority.4.sg",
                "equal-main/Binary/a_equal.2.sg",
                "equal-main/Binary/m_equal.2.sg",
                "equal-main/Binary/z_equal.2.sg",
                "lexical-priority-main/Binary/z_ten.10.sg",
                "lexical-priority-main/Binary/a_two.2.sg",
                "missing-priority-main/Binary/a_plain.sg",
                "missing-priority-main/Binary/z_ranked.1.sg",
                "empty-priority-main/Binary/a_empty..sg",
                "empty-priority-main/Binary/z_empty_ranked.1.sg",
                "sort-main/Binary/sort_records.1.sg",
                "break-main/Binary/break_scan.1.sg",
                "break-main/Binary/after_break.2.sg",
            }.issubset(paths)
        )
        self.assertEqual(
            manifest["mode_orders"]["combined"],
            [
                "DS.deep.2.sg",
                "HEUR.heuristic.3.sg",
                "EP.entrypoint.4.sg",
                "z_normal.1.sg",
                "a_extra.0.sg",
                "a_custom.0.sg",
            ],
        )
        self.assertEqual(
            manifest["priority_only_order"],
            [
                "z_priority.1.sg",
                "a_priority.2.sg",
                "m_priority.4.sg",
            ],
        )
        self.assertEqual(
            manifest["ordering_cases"],
            {
                "empty_priority": {
                    "database_prefix": "empty-priority",
                    "execution_order": [
                        "a_empty..sg",
                        "z_empty_ranked.1.sg",
                    ],
                },
                "equal_priority": {
                    "database_prefix": "equal",
                    "execution_order": [
                        "a_equal.2.sg",
                        "m_equal.2.sg",
                        "z_equal.2.sg",
                    ],
                },
                "lexical_priority": {
                    "database_prefix": "lexical-priority",
                    "execution_order": [
                        "z_ten.10.sg",
                        "a_two.2.sg",
                    ],
                },
                "missing_priority": {
                    "database_prefix": "missing-priority",
                    "execution_order": [
                        "a_plain.sg",
                        "z_ranked.1.sg",
                    ],
                },
            },
        )
        self.assertEqual(
            manifest["engine_contract"],
            {
                "sort_unsorted_names": [
                    "Packer last",
                    "Format first",
                    "Compiler middle",
                ],
                "sort_sorted_names": [
                    "Format first",
                    "Compiler middle",
                    "Packer last",
                ],
                "break_execution_order": ["break_scan.1.sg"],
                "break_detection_names": ["Break first"],
            },
        )


if __name__ == "__main__":
    unittest.main()
