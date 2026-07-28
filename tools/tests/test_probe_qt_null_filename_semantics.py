import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT
    / "tools"
    / "upstream"
    / "probe_qt_null_filename_semantics.py"
)
SOURCE_PATH = (
    ROOT / "tools" / "upstream" / "qt_null_filename_probe.cpp"
)
REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "qt-null-filename-semantics-qt5-qt6.json"
)
REPORT_SHA256 = (
    "0a62837f0a32b4147a379f1fdba3a4c286f658734bbcefc2c2b0e2e22493f8c2"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_qt_null_filename_semantics",
    MODULE_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ProbeQtNullFilenameSemanticsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = REPORT_PATH.read_bytes()
        cls.report = json.loads(cls.raw)

    def test_report_source_and_generator_are_fixed(self):
        self.assertEqual(
            hashlib.sha256(self.raw).hexdigest(),
            REPORT_SHA256,
        )
        self.assertEqual(self.report["generator"], MODULE.GENERATOR)
        self.assertEqual(
            self.report["generator_sha256"],
            hashlib.sha256(MODULE_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            self.report["source"],
            {
                "path": MODULE.SOURCE,
                "sha256": hashlib.sha256(
                    SOURCE_PATH.read_bytes()
                ).hexdigest(),
            },
        )

    def test_exact_qt5_qt6_semantics_are_retained(self):
        self.assertEqual(len(self.report["relationships"]), 5)
        self.assertTrue(all(self.report["relationships"].values()))
        for oracle_name, oracle in MODULE.ORACLES.items():
            with self.subTest(oracle=oracle_name):
                observation = self.report["observations"][oracle_name]
                self.assertEqual(
                    observation["image_id"],
                    oracle["image_id"],
                )
                self.assertEqual(
                    observation["result"],
                    oracle["expected"],
                )
                stdout = observation["stdout"].encode("utf-8")
                stderr = observation["stderr"].encode("utf-8")
                self.assertEqual(
                    hashlib.sha256(stdout).hexdigest(),
                    observation["stdout_sha256"],
                )
                self.assertEqual(
                    hashlib.sha256(stderr).hexdigest(),
                    observation["stderr_sha256"],
                )
                self.assertEqual(stderr, b"")

    def test_probe_directly_explains_iso_dot_filter_difference(self):
        qt5 = self.report["observations"]["qt5"]["result"]
        qt6 = self.report["observations"]["qt6"]["result"]
        self.assertEqual(qt5["string_size"], 0)
        self.assertTrue(qt5["equals_c_string"])
        self.assertEqual(qt6["string_size"], 1)
        self.assertEqual(qt6["first_code_unit"], 0)
        self.assertFalse(qt6["equals_c_string"])
        self.assertEqual(
            self.report["relevance"]["expression"],
            'sFileName == "\\x00" in the dot-entry filter',
        )


if __name__ == "__main__":
    unittest.main()
