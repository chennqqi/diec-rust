import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT / "tools" / "upstream" / "probe_qt6_rule_orchestration.py"
)
UNDERLYING_PATH = (
    ROOT / "tools" / "upstream" / "probe_rule_orchestration.py"
)
REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "rule-orchestration-linux-qt5-qt6.json"
)
QT5_REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "rule-orchestration-linux-qt5.json"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_qt6_rule_orchestration",
    MODULE_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ProbeQt6RuleOrchestrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        cls.qt5 = json.loads(
            QT5_REPORT_PATH.read_text(encoding="utf-8")
        )

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
        self.assertEqual(
            [oracle["name"] for oracle in self.report["oracles"]],
            ["linux-qt5-cmake", "linux-qt6-cmake"],
        )

    def test_ten_cases_are_equal_and_successful(self):
        self.assertTrue(self.report["normalized_outputs_equal"])
        self.assertEqual(len(self.report["canonical_cases"]), 10)
        self.assertTrue(all(self.report["relationships"].values()))
        for oracle in self.report["oracles"]:
            self.assertEqual(len(oracle["cases"]), 10)
            for case in oracle["cases"].values():
                self.assertEqual(case["exit_code"], 0)
                self.assertEqual(case["raw_stderr_bytes"], 0)

    def test_qt5_and_qt6_preserve_the_qt5_contract(self):
        self.assertEqual(
            self.report["canonical_cases"],
            self.qt5["canonical_cases"],
        )
        self.assertEqual(
            self.report["relationships"],
            self.qt5["relationships"],
        )
        self.assertEqual(
            self.report["fixture_manifest"],
            self.qt5["fixture_manifest"],
        )


if __name__ == "__main__":
    unittest.main()
