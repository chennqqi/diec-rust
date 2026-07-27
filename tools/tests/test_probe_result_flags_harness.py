import importlib.util
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).parents[2]
MODULE_PATH = (
    ROOT / "tools" / "upstream" / "probe_result_flags_harness.py"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_result_flags_harness",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def valid_document():
    cases = []
    for case_id, expected in MODULE.EXPECTED_CASES.items():
        cases.append(
            {
                "id": case_id,
                "database": expected["database"],
                "signature": expected["signature"],
                "heuristic_scan": expected["heuristic_scan"],
                "database_loaded": True,
                "load_not_canceled": True,
                "scan_not_canceled": True,
                "error_count": 0,
                "records": [
                    {
                        "type": expected["type"],
                        "name": expected["name"],
                        "signature": expected["signature"],
                        "heuristic": expected["heuristic"],
                        "advanced_heuristic": (
                            expected["advanced_heuristic"]
                        ),
                        "unknown": expected["unknown"],
                    }
                ],
            }
        )
    return {
        "schema_version": 1,
        "upstream_commit": MODULE.UPSTREAM_COMMIT,
        "formats_commit": MODULE.FORMATS_COMMIT,
        "xscanengine_commit": MODULE.XSCANENGINE_COMMIT,
        "die_script_commit": MODULE.DIE_SCRIPT_COMMIT,
        "input_sha256": MODULE.INPUT_SHA256,
        "case_count": len(cases),
        "cases": cases,
    }


class ProbeResultFlagsHarnessTests(unittest.TestCase):
    def test_validates_all_flag_truth_table_rows(self):
        relationships = MODULE.validate(valid_document())
        self.assertTrue(all(relationships.values()))
        self.assertEqual(len(relationships), 6)

    def test_rejects_heuristic_prefix_without_flag(self):
        document = valid_document()
        document["cases"][1]["records"][0]["heuristic"] = False
        with self.assertRaisesRegex(ValueError, "flags_match"):
            MODULE.validate(document)

    def test_rejects_advanced_flag_also_marked_heuristic(self):
        document = valid_document()
        document["cases"][2]["records"][0]["heuristic"] = True
        with self.assertRaisesRegex(ValueError, "flags_match|mutually"):
            MODULE.validate(document)

    def test_rejects_unknown_inferred_only_from_text(self):
        document = valid_document()
        document["cases"][3]["records"][0]["unknown"] = False
        with self.assertRaisesRegex(ValueError, "flags_match"):
            MODULE.validate(document)

    def test_cpp_harness_serializes_raw_text_and_flags_together(self):
        source = (
            ROOT
            / "tools"
            / "upstream"
            / "result_flags_harness_main.cpp"
        ).read_text(encoding="utf-8")
        self.assertIn('item.insert("type", record.sType)', source)
        self.assertIn("record.bIsHeuristic", source)
        self.assertIn("record.bIsAHeuristic", source)
        self.assertIn("record.bIsUnknown", source)


if __name__ == "__main__":
    unittest.main()
