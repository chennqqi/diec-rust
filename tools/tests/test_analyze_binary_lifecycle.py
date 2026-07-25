import importlib.util
import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[2]
MODULE_PATH = ROOT / "tools" / "rules" / "analyze_binary_lifecycle.py"
REFERENCE_PATH = (
    ROOT / "docs" / "research" / "data" / "binary-rule-lifecycle.json"
)
SPEC = importlib.util.spec_from_file_location(
    "analyze_binary_lifecycle", MODULE_PATH
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class BinaryLifecycleAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.reference = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))

    def test_checked_manifest_is_reproducible(self):
        self.assertEqual(self.reference, MODULE.build_manifest(ROOT))

    def test_fixed_binary_inventory_and_resolution(self):
        binary = self.reference["binary"]
        self.assertEqual(
            binary["executable_count_by_database"],
            {"db": 292, "db_custom": 0, "db_extra": 0},
        )
        self.assertEqual(
            binary["selected_global_init"]["path"], "db/_init"
        )
        self.assertEqual(
            binary["selected_type_init"]["path"], "db/Binary/_init"
        )
        self.assertEqual(binary["missing_literal_includes"], [])
        self.assertEqual(binary["non_literal_include_sites"], [])
        self.assertEqual(
            {
                call["target"]: call["resolved_path"]
                for call in binary["literal_include_calls"]
                if call["caller"] in {"db/_init", "db/Binary/_init"}
            },
            {
                "_debug": "db/_debug",
                "_runtime_helpers": "db/_runtime_helpers",
                "language": "db/language",
                "read": "db/read",
            },
        )

    def test_upstream_comparator_has_a_cycle(self):
        risk = self.reference["ordering_risk"]
        self.assertFalse(risk["strict_weak_ordering_satisfied"])
        self.assertTrue(risk["cycle_witnesses"])
        for first, second, third in risk["cycle_witnesses"]:
            self.assertTrue(MODULE.precedes(first, second))
            self.assertTrue(MODULE.precedes(second, third))
            self.assertTrue(MODULE.precedes(third, first))


if __name__ == "__main__":
    unittest.main()
