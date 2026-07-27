import copy
import importlib.util
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).parents[2]
MODULE_PATH = (
    ROOT / "tools" / "upstream" / "probe_result_enums_harness.py"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_result_enums_harness",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def valid_document():
    cases = [
        {
            "id": "known_alias",
            "database_loaded": True,
            "load_not_canceled": True,
            "scan_not_canceled": True,
            "error_count": 0,
            "records": [{
                "raw_type": "PE-Tool",
                "raw_name": "7 ZIP",
                "type_value": 29,
                "type_canonical": "PE Tool",
                "name_value": 4,
                "name_canonical": "7-Zip",
                "unknown": False,
            }],
        },
        {
            "id": "heuristic_prefix",
            "database_loaded": True,
            "load_not_canceled": True,
            "scan_not_canceled": True,
            "error_count": 0,
            "records": [{
                "raw_type": "~format",
                "raw_name": "7-Zip",
                "type_value": 13,
                "type_canonical": "Format",
                "name_value": 4,
                "name_canonical": "7-Zip",
                "unknown": False,
            }],
        },
        {
            "id": "custom_raw",
            "database_loaded": True,
            "load_not_canceled": True,
            "scan_not_canceled": True,
            "error_count": 0,
            "records": [{
                "raw_type": "Vendor-Custom",
                "raw_name": "Project/Custom",
                "type_value": 0,
                "type_canonical": "Unknown",
                "name_value": 0,
                "name_canonical": "Unknown",
                "unknown": False,
            }],
        },
        {
            "id": "unknown_fallback",
            "database_loaded": True,
            "load_not_canceled": True,
            "scan_not_canceled": True,
            "error_count": 0,
            "records": [{
                "raw_type": "Unknown",
                "raw_name": "Unknown",
                "type_value": 0,
                "type_canonical": "Unknown",
                "name_value": 0,
                "name_canonical": "Unknown",
                "unknown": True,
            }],
        },
    ]
    aliases = [
        {"value": value, "canonical": "_Unknown"}
        for value in range(800, 810)
    ]
    return {
        "schema_version": 1,
        "upstream_commit": MODULE.UPSTREAM_COMMIT,
        "formats_commit": MODULE.FORMATS_COMMIT,
        "xscanengine_commit": MODULE.XSCANENGINE_COMMIT,
        "die_script_commit": MODULE.DIE_SCRIPT_COMMIT,
        "input_sha256": MODULE.INPUT_SHA256,
        "case_count": len(cases),
        "cases": cases,
        "type_mappings": [
            {"input": text, "value": 29, "canonical": "PE Tool"}
            for text in (
                "PE Tool",
                "pe-tool",
                "PETOOL",
                "~PE Tool",
                "!pe-tool",
            )
        ],
        "name_mappings": [
            {"input": text, "value": 4, "canonical": "7-Zip"}
            for text in ("7-Zip", "7 ZIP", "7zip")
        ],
        "reserved_name_aliases": aliases,
        "fallbacks": {
            "reserved_alias_first_value": 800,
            "reserved_alias_last_value": 809,
            "reserved_alias_input": {
                "input": "_Unknown",
                "value": 800,
                "canonical": "_Unknown",
            },
            "unknown_type_input": {
                "value": 0,
                "canonical": "Unknown",
            },
            "unknown_name_input": {
                "value": 0,
                "canonical": "Unknown",
            },
            "out_of_range_type_value": 74,
            "out_of_range_type_string": "Unknown",
            "out_of_range_name_value": 826,
            "out_of_range_name_string": "Unknown",
        },
    }


class ProbeResultEnumsHarnessTests(unittest.TestCase):
    def test_validates_all_enum_relationships(self):
        relationships = MODULE.validate(valid_document())
        self.assertTrue(all(relationships.values()))
        self.assertEqual(len(relationships), 9)

    def test_rejects_canonicalization_alias_mismatch(self):
        document = valid_document()
        document["type_mappings"][1]["value"] = 30
        with self.assertRaisesRegex(ValueError, "canonicalization"):
            MODULE.validate(document)

    def test_rejects_custom_raw_conflated_with_unknown_fallback(self):
        document = valid_document()
        document["cases"][2]["records"][0]["unknown"] = True
        with self.assertRaisesRegex(ValueError, "custom_raw"):
            MODULE.validate(document)

    def test_rejects_collapsed_reserved_unknown_slots(self):
        document = valid_document()
        document["reserved_name_aliases"][1]["value"] = 800
        with self.assertRaisesRegex(ValueError, "reserved_unknown"):
            MODULE.validate(document)

    def test_rejects_out_of_range_string_not_unknown(self):
        document = valid_document()
        document["fallbacks"]["out_of_range_name_string"] = "_Unknown"
        with self.assertRaisesRegex(ValueError, "out_of_range"):
            MODULE.validate(document)

    def test_cpp_harness_serializes_raw_and_numeric_together(self):
        source = (
            ROOT
            / "tools"
            / "upstream"
            / "result_enums_harness_main.cpp"
        ).read_text(encoding="utf-8")
        self.assertIn('output.insert("raw_type", record.sType)', source)
        self.assertIn('output.insert("raw_name", record.sName)', source)
        self.assertIn('output.insert("type_value"', source)
        self.assertIn('output.insert("name_value"', source)


if __name__ == "__main__":
    unittest.main()
