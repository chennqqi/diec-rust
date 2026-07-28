import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT / "tools" / "upstream" / "probe_qt6_resource_context_chain.py"
)
UNDERLYING_PATH = (
    ROOT / "tools" / "upstream" / "probe_resource_context_chain.py"
)
REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "resource-context-chain-qt6.json"
)
QT5_REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "resource-context-chain-qt5.json"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_qt6_resource_context_chain",
    MODULE_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ProbeQt6ResourceContextChainTest(unittest.TestCase):
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
            MODULE.QT6_IMAGE_ID,
        )

    def test_all_raw_streams_and_context_fields_are_retained(self):
        self.assertEqual(len(self.report["cases"]), 4)
        self.assertEqual(len(self.report["relationships"]), 9)
        self.assertTrue(all(self.report["relationships"].values()))
        for name, case in self.report["cases"].items():
            with self.subTest(case=name):
                stdout = case["raw_stdout"].encode("utf-8")
                stderr = bytes.fromhex(case["raw_stderr_hex"])
                self.assertEqual(
                    hashlib.sha256(stdout).hexdigest(),
                    case["raw_stdout_sha256"],
                )
                self.assertEqual(
                    hashlib.sha256(stderr).hexdigest(),
                    case["raw_stderr_sha256"],
                )
                self.assertEqual(stderr, MODULE.QT6_WARNING)
                self.assertEqual(
                    case["raw_stdout"],
                    self.qt5["cases"][name]["raw_stdout"],
                )
                self.assertEqual(
                    case["normalized_detect_tree"],
                    self.qt5["cases"][name]["normalized_detect_tree"],
                )
        self.assertEqual(
            self.report["known_difference"],
            {
                "scope": "PE rule runtime warning in each CLI invocation",
                "case_count": 4,
                "stderr_bytes_per_case": 80,
                "stderr_sha256_per_case": (
                    "b303e6913e76b70a6f0d6a4d3ccd389b"
                    "c342589e45e1615873a37334dea8c51b"
                ),
                "lines_per_case": 4,
                "semantic_output_equal_to_qt5": True,
            },
        )


if __name__ == "__main__":
    unittest.main()
