import importlib.util
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).parents[2]
MODULE_PATH = (
    ROOT
    / "tools"
    / "upstream"
    / "probe_result_metadata_harness.py"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_result_metadata_harness",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def result_case(case_id, filename):
    return {
        "id": case_id,
        "nScanTime": 0,
        "sFileName": filename,
        "nSize": MODULE.INPUT_SIZE,
        "ftInit": 7,
        "ftInit_string": "MSDOS",
        "record_count": 1,
        "error_count": 0,
        "scan_success": True,
    }


def valid_document():
    cases = [
        result_case("file", MODULE.FILE_PATH),
        result_case("memory", ""),
        result_case("device", MODULE.DEVICE_NAME),
        result_case("subdevice", ""),
    ]
    return {
        "schema_version": 1,
        "upstream_commit": MODULE.UPSTREAM_COMMIT,
        "formats_commit": MODULE.FORMATS_COMMIT,
        "xscanengine_commit": MODULE.XSCANENGINE_COMMIT,
        "input_size": MODULE.INPUT_SIZE,
        "input_hex": "00" * MODULE.INPUT_SIZE,
        "file_path": MODULE.FILE_PATH,
        "device_name": MODULE.DEVICE_NAME,
        "case_count": len(cases),
        "cases": cases,
    }


class ProbeResultMetadataHarnessTests(unittest.TestCase):
    def test_validates_four_entrypoint_control_set(self):
        relationships = MODULE.validate(valid_document())
        self.assertTrue(all(relationships.values()))
        self.assertEqual(len(relationships), 6)

    def test_accepts_zero_scan_time_but_rejects_float(self):
        document = valid_document()
        document["cases"][0]["nScanTime"] = 0.0
        with self.assertRaisesRegex(ValueError, "scan_time_typed"):
            MODULE.validate(document)

    def test_rejects_subdevice_parent_filename_leak(self):
        document = valid_document()
        document["cases"][3]["sFileName"] = "parent-container.bin"
        with self.assertRaisesRegex(ValueError, "filenames_follow"):
            MODULE.validate(document)

    def test_rejects_inconsistent_numeric_initial_filetype(self):
        document = valid_document()
        document["cases"][1]["ftInit"] = 8
        with self.assertRaisesRegex(ValueError, "filetype_is_consistent"):
            MODULE.validate(document)

    def test_cpp_harness_calls_all_four_entrypoints(self):
        source = (
            ROOT
            / "tools"
            / "upstream"
            / "result_metadata_harness_main.cpp"
        ).read_text(encoding="utf-8")
        self.assertIn("engine->scanFile(", source)
        self.assertIn("engine->scanMemory(", source)
        self.assertIn("engine->scanDevice(", source)
        self.assertIn("engine->scanSubdevice(", source)
        self.assertIn('buffer.setProperty("FileName", DEVICE_NAME)', source)


if __name__ == "__main__":
    unittest.main()
