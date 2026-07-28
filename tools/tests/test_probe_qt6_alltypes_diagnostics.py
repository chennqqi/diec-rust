import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT / "tools" / "upstream" / "probe_qt6_alltypes_diagnostics.py"
)
REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "qt6-alltypes-diagnostics.json"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_qt6_alltypes_diagnostics",
    MODULE_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ProbeQt6AlltypesDiagnosticsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    def test_report_identity_and_result_are_fixed(self):
        self.assertEqual(self.report["schema_version"], 1)
        self.assertEqual(self.report["generator"], MODULE.GENERATOR)
        self.assertEqual(
            self.report["generator_sha256"],
            hashlib.sha256(MODULE_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            self.report["upstream_commit"],
            MODULE.UPSTREAM_COMMIT,
        )
        self.assertEqual(self.report["repetitions"], 3)
        self.assertTrue(self.report["passed"])
        self.assertTrue(all(self.report["facts"].values()))

    def test_raw_streams_match_hashes_and_parsed_fields(self):
        for case_name, case in self.report["cases"].items():
            for oracle_name, observations in case["observations"].items():
                self.assertEqual(len(observations), 3)
                for index, observation in enumerate(observations):
                    with self.subTest(
                        case=case_name,
                        oracle=oracle_name,
                        repetition=index,
                    ):
                        stdout = base64.b64decode(
                            observation["stdout_base64"]
                        )
                        stderr = base64.b64decode(
                            observation["stderr_base64"]
                        )
                        self.assertEqual(
                            len(stdout), observation["stdout_bytes"]
                        )
                        self.assertEqual(
                            hashlib.sha256(stdout).hexdigest(),
                            observation["stdout_sha256"],
                        )
                        self.assertEqual(
                            len(stderr), observation["stderr_bytes"]
                        )
                        self.assertEqual(
                            hashlib.sha256(stderr).hexdigest(),
                            observation["stderr_sha256"],
                        )
                        document, diagnostics = (
                            MODULE.split_json_and_diagnostics(stdout)
                        )
                        self.assertEqual(
                            document, observation["json_document"]
                        )
                        self.assertEqual(
                            diagnostics, observation["diagnostics"]
                        )
                        self.assertEqual(
                            MODULE.ADDRESS_PATTERN.sub(
                                "<address>", diagnostics
                            ),
                            observation["normalized_diagnostics"],
                        )

    def test_qt6_difference_is_exact_and_raw_first(self):
        for case in self.report["cases"].values():
            qt5 = case["observations"]["qt5"]
            qt6 = case["observations"]["qt6"]
            self.assertTrue(
                all(item["diagnostics"] == "" for item in qt5)
            )
            self.assertTrue(
                all(
                    item["normalized_diagnostics"]
                    == MODULE.EXPECTED_DIAGNOSTICS
                    for item in qt6
                )
            )
            self.assertEqual(
                case["qt6_raw_diagnostic_variant_count"],
                len({item["diagnostics"] for item in qt6}),
            )
            self.assertGreaterEqual(
                case["qt6_raw_diagnostic_variant_count"], 1
            )
            self.assertTrue(
                all(
                    base64.b64decode(item["stderr_base64"])
                    == MODULE.QT6_WARNING
                    for item in qt6
                )
            )
            self.assertTrue(
                all(
                    item["json_document"] == qt5[0]["json_document"]
                    for item in qt6
                )
            )


if __name__ == "__main__":
    unittest.main()
