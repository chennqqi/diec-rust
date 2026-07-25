import importlib.util
import json
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).parents[2]
MODULE_PATH = ROOT / "tools" / "upstream" / "probe_script_state.py"
SPEC = importlib.util.spec_from_file_location("probe_script_state", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ProbeScriptStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = json.loads(
            (
                ROOT
                / "docs"
                / "research"
                / "data"
                / "script-state-qt5.json"
            ).read_text(encoding="utf-8")
        )

    def test_reference_pins_equal_successful_oracles(self):
        self.assertEqual(
            self.reference["upstream_commit"], MODULE.BASE.UPSTREAM_COMMIT
        )
        self.assertEqual(
            self.reference["generator"],
            "tools/upstream/probe_script_state.py",
        )
        self.assertTrue(self.reference["normalized_outputs_equal"])
        self.assertEqual(len(self.reference["rule_order"]), 7)
        self.assertEqual(
            [item["version"] for item in self.reference["detections"]],
            ["40", "42", "42", "42", "7", "7", "true"],
        )
        for oracle in self.reference["oracles"]:
            self.assertEqual(
                oracle["revision"], MODULE.BASE.UPSTREAM_COMMIT
            )
            self.assertEqual(oracle["exit_code"], 0)
            self.assertEqual(oracle["raw_stderr_bytes"], 0)
            self.assertEqual(
                oracle["raw_stderr_sha256"], MODULE.BASE.EMPTY_SHA256
            )


if __name__ == "__main__":
    unittest.main()
