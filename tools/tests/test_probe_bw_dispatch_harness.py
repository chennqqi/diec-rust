import importlib.util
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).parents[2]
MODULE_PATH = (
    ROOT
    / "tools"
    / "upstream"
    / "probe_bw_dispatch_harness.py"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_bw_dispatch_harness",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def case(case_id, *, detected, initial, forced):
    filetype = "BW DOS16M" if forced else initial
    return {
        "id": case_id,
        "forced": forced,
        "property": "BW DOS16M" if forced else "",
        "detected_filetypes": detected,
        "initial_filetype": initial,
        "records": [
            {
                "filetype": filetype,
                "type": "Unknown",
                "name": "Unknown",
                "unknown": True,
            }
        ],
        "error_count": 0,
        "detector_success": True,
        "scan_success": True,
    }


def valid_document():
    cases = [
        case(
            "automatic_detection",
            detected="Binary",
            initial="Binary",
            forced=False,
        ),
        case(
            "forced_property",
            detected="BW DOS16M",
            initial="BW DOS16M",
            forced=True,
        ),
    ]
    return {
        "schema_version": 1,
        "upstream_commit": MODULE.UPSTREAM_COMMIT,
        "formats_commit": MODULE.FORMATS_COMMIT,
        "xscanengine_commit": MODULE.XSCANENGINE_COMMIT,
        "input_hex": MODULE.INPUT_HEX,
        "case_count": len(cases),
        "cases": cases,
    }


class ProbeBwDispatchHarnessTests(unittest.TestCase):
    def test_validates_automatic_and_forced_control_pair(self):
        relationships = MODULE.validate(valid_document())
        self.assertTrue(all(relationships.values()))
        self.assertEqual(len(relationships), 6)

    def test_rejects_public_automatic_bw_detection(self):
        document = valid_document()
        document["cases"][0]["detected_filetypes"] = "Binary|BW DOS16M"
        with self.assertRaisesRegex(ValueError, "automatic_detector"):
            MODULE.validate(document)

    def test_rejects_forced_branch_without_bw_record(self):
        document = valid_document()
        document["cases"][1]["records"][0]["filetype"] = "Binary"
        with self.assertRaisesRegex(ValueError, "forced_scan"):
            MODULE.validate(document)

    def test_cpp_harness_sets_only_forced_case_property(self):
        source = (
            ROOT
            / "tools"
            / "upstream"
            / "bw_dispatch_harness_main.cpp"
        ).read_text(encoding="utf-8")
        self.assertIn('buffer.setProperty("filetypes", "BW DOS16M")', source)
        self.assertIn("runCase(false)", source)
        self.assertIn("runCase(true)", source)
        self.assertEqual(source.count('setProperty("filetypes"'), 1)


if __name__ == "__main__":
    unittest.main()
