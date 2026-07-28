import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT / "tools" / "upstream" / "probe_qt6_cli_option_behavior.py"
)
UNDERLYING_PATH = (
    ROOT / "tools" / "upstream" / "probe_cli_option_behavior.py"
)
REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "cli-option-behavior-linux-qt5-qt6.json"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_qt6_cli_option_behavior",
    MODULE_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ProbeQt6CliOptionBehaviorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    def test_report_and_probe_identity_are_fixed(self):
        self.assertEqual(self.report["schema_version"], 1)
        self.assertEqual(self.report["generator"], MODULE.GENERATOR)
        self.assertEqual(
            self.report["generator_sha256"],
            hashlib.sha256(MODULE_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            self.report["underlying_probe"],
            {
                "path": MODULE.UNDERLYING_PROBE,
                "sha256": hashlib.sha256(
                    UNDERLYING_PATH.read_bytes()
                ).hexdigest(),
            },
        )
        self.assertEqual(self.report["result"], "equal")

    def test_fixed_oracles_and_nine_cases_are_equal(self):
        self.assertEqual(
            [oracle["name"] for oracle in self.report["oracles"]],
            ["linux-qt5-cmake", "linux-qt6-cmake"],
        )
        self.assertEqual(len(self.report["cases"]), 9)
        for case_name, case in self.report["cases"].items():
            with self.subTest(case=case_name):
                self.assertTrue(case["all_oracles_equal"])
                self.assertEqual(len(case["oracles"]), 2)

    def test_relationships_preserve_option_contract(self):
        relationships = self.report["relationships"]
        self.assertTrue(
            relationships["test_directory_value_is_unvalidated"]
        )
        self.assertTrue(
            relationships["createtest_complete_only_prints_announcement"]
        )
        self.assertEqual(
            relationships["createtest_missing_positionals_exit_code"], 4
        )
        self.assertTrue(
            relationships["profiling_without_messages_equals_default"]
        )
        self.assertEqual(
            relationships["verbose_added_values"],
            [
                {
                    "info": "AMD64, 64-bit",
                    "name": "Linux",
                    "type": "operation system",
                    "version": "ABI: 3.2.0",
                }
            ],
        )
        self.assertTrue(relationships["all_stderr_empty"])


if __name__ == "__main__":
    unittest.main()
