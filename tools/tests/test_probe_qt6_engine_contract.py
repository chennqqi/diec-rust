import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT / "tools" / "upstream" / "probe_qt6_engine_contract.py"
)
UNDERLYING_PATH = (
    ROOT / "tools" / "upstream" / "probe_engine_contract.py"
)
REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "engine-contract-linux-qt6.json"
)
QT5_REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "engine-contract-linux-qt5.json"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_qt6_engine_contract",
    MODULE_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ProbeQt6EngineContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        cls.qt5 = json.loads(QT5_REPORT_PATH.read_text(encoding="utf-8"))

    def test_report_and_harness_identity_are_fixed(self):
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
        self.assertEqual(self.report["result"], "observed")
        self.assertEqual(
            self.report["oracle"]["image"],
            MODULE.IMAGE,
        )
        self.assertEqual(
            self.report["oracle"]["image_id"],
            "sha256:ffd09170f4c37a49bffff6a3c3c59469c19caabf6aa9c78f0981e1bd95591a6b",
        )

    def test_all_37_cases_and_source_contracts_pass(self):
        self.assertEqual(
            self.report["harness_output"]["case_count"], 37
        )
        self.assertEqual(
            len(self.report["harness_output"]["cases"]), 37
        )
        self.assertTrue(all(self.report["relationships"].values()))
        self.assertTrue(
            all(
                self.report["source_audit"]["device_contracts"].values()
            )
        )
        self.assertTrue(
            all(
                self.report["source_audit"][
                    "cancellation_contracts"
                ].values()
            )
        )
        self.assertEqual(self.report["oracle"]["exit_code"], 0)
        self.assertEqual(self.report["oracle"]["raw_stderr_bytes"], 0)

    def test_qt5_and_qt6_relationship_projections_are_equal(self):
        self.assertEqual(
            self.report["relationships"],
            self.qt5["relationships"],
        )
        self.assertEqual(
            self.report["fixture_manifest"],
            self.qt5["fixture_manifest"],
        )
        self.assertEqual(
            self.report["source_audit"],
            self.qt5["source_audit"],
        )


if __name__ == "__main__":
    unittest.main()
