import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT / "tools" / "upstream" / "probe_qt6_signature_path_harness.py"
)
UNDERLYING_PATH = (
    ROOT / "tools" / "upstream" / "probe_signature_path_harness.py"
)
REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "signature-path-engine-qt6.json"
)
QT5_REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "signature-path-engine-qt5.json"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_qt6_signature_path_harness",
    MODULE_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ProbeQt6SignaturePathHarnessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        cls.qt5 = json.loads(
            QT5_REPORT_PATH.read_text(encoding="utf-8")
        )

    def test_report_and_probe_identity_are_fixed(self):
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
        self.assertEqual(self.report["result"], "observed")
        self.assertEqual(
            self.report["oracle"]["image_id"],
            "sha256:df9be77359a4b9eb877ddf03c247ab553385b35b103d617655f973e916a333fd",
        )

    def test_qt6_preserves_all_seven_cases_and_relationships(self):
        self.assertEqual(
            self.report["harness_output"]["case_count"], 7
        )
        self.assertEqual(len(self.report["relationships"]), 11)
        self.assertTrue(all(self.report["relationships"].values()))
        self.assertEqual(self.report["oracle"]["exit_code"], 0)
        self.assertEqual(self.report["oracle"]["raw_stderr_bytes"], 0)
        self.assertEqual(
            self.report["harness_output"],
            self.qt5["harness_output"],
        )
        self.assertEqual(
            self.report["relationships"],
            self.qt5["relationships"],
        )
        self.assertEqual(self.report["fixture"], self.qt5["fixture"])


if __name__ == "__main__":
    unittest.main()
