import importlib.util
import pathlib
import sys
import unittest


MODULE_PATH = (
    pathlib.Path(__file__).parents[1]
    / "upstream"
    / "probe_subdevice_source_audit.py"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_subdevice_source_audit",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class SubdeviceSourceAuditTests(unittest.TestCase):
    def test_matching_lines_preserves_line_and_trimmed_source(self):
        matches = MODULE.matching_lines(
            "first\n  target();  \nlast\n",
            "target",
        )
        self.assertEqual(
            matches,
            [{"line": 2, "text": "target();"}],
        )

    def test_engine_fact_requires_global_debugdata_absence(self):
        source = (
            b"XBinary::FILEPART_DEBUGDATA\n"
            b"XBinary::FILEPART_RESOURCE, 10000\n"
            b"XBinary::FILEPART_OVERLAY, 1\n"
            b"_options.sScanID = filePart.mapProperties.value\n"
            b"scanProcess(&subDevice, &scanResultFilePart\n"
        )
        formats = (
            b"(nFileParts & FILEPART_RESOURCE) || "
            b"(nFileParts & FILEPART_DEBUGDATA)\n"
            b"if (nFileParts & FILEPART_DEBUGDATA)\n"
            b"record.filePart = XBinary::FILEPART_DEBUGDATA\n"
        )
        report = MODULE.audit_sources(
            {"xscanengine": source, "xpe": formats}
        )
        self.assertEqual(
            report["facts"]["xscanengine_debugdata_token_count"],
            1,
        )
        self.assertIn(
            "xscanengine.debugdata_token_count",
            report["failures"],
        )

    def test_expected_source_inventory_is_exact(self):
        self.assertEqual(
            set(MODULE.SOURCES),
            {"xscanengine", "xpe"},
        )
        self.assertEqual(
            MODULE.EXPECTED_LINES["xscanengine"],
            {
                "resource_enumeration": [2935],
                "overlay_enumeration": [2939],
                "resource_scan_id": [2990],
                "child_scan": [2995],
            },
        )
        self.assertEqual(
            MODULE.EXPECTED_LINES["xpe"]["debugdata_record"],
            [11261],
        )


if __name__ == "__main__":
    unittest.main()
