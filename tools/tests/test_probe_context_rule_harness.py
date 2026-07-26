import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[2]
MODULE_PATH = (
    ROOT / "tools" / "upstream" / "probe_context_rule_harness.py"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_context_rule_harness",
    MODULE_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ContextRuleHarnessProbeTests(unittest.TestCase):
    def test_expected_case_inventory_is_exact(self):
        self.assertEqual(
            list(MODULE.EXPECTED),
            [
                "resource_manifest",
                "resource_unknown_id",
                "resource_header_gate",
                "debug_rsds",
                "debug_header_gate",
                "desktop_entry",
                "desktop_missing_marker",
                "desktop_binary_gate",
            ],
        )

    def test_validate_accepts_exact_observations(self):
        cases = []
        for case_id, expected in MODULE.EXPECTED.items():
            cases.append(
                {
                    "id": case_id,
                    **expected,
                    "detect_is_boolean": True,
                    "binary_script_error": "",
                }
            )
        actual = {
            "schema_version": 1,
            "upstream_commit": (
                "74eaf505c250ab47e709024e9dc41657cd8f2254"
            ),
            "xscanengine_commit": MODULE.XSCANENGINE_COMMIT,
            "rules_commit": MODULE.RULES_COMMIT,
            "qt_version": "5.15.13",
            "engine": "QScriptEngine",
            "case_count": len(cases),
            "cases": cases,
        }
        self.assertEqual(
            MODULE.validate(
                actual,
                "74eaf505c250ab47e709024e9dc41657cd8f2254",
            ),
            [],
        )

    def test_validate_rejects_semantic_drift(self):
        actual = {
            "schema_version": 1,
            "upstream_commit": (
                "74eaf505c250ab47e709024e9dc41657cd8f2254"
            ),
            "xscanengine_commit": MODULE.XSCANENGINE_COMMIT,
            "rules_commit": MODULE.RULES_COMMIT,
            "qt_version": "5.15.13",
            "engine": "QScriptEngine",
            "case_count": 0,
            "cases": [],
        }
        failures = MODULE.validate(
            actual,
            "74eaf505c250ab47e709024e9dc41657cd8f2254",
        )
        self.assertIn("case_count", failures)
        self.assertIn("case_ids", failures)


if __name__ == "__main__":
    unittest.main()
