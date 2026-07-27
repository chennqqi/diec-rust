import importlib.util
import json
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).parents[2]
MODULE_PATH = (
    ROOT
    / "tools"
    / "upstream"
    / "probe_dos_dispatch_source_audit.py"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_dos_dispatch_source_audit",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class DosDispatchSourceAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = json.loads(
            (
                ROOT
                / "docs"
                / "research"
                / "data"
                / "dos-dispatch-source-audit.json"
            ).read_text(encoding="utf-8")
        )

    def test_matching_lines_preserves_line_and_source(self):
        self.assertEqual(
            MODULE.matching_lines("first\n  target(); \n", "target"),
            [{"line": 2, "text": "target();"}],
        )

    def test_reference_proves_split_closure_path(self):
        report = self.reference
        self.assertTrue(report["passed"])
        self.assertEqual(report["failures"], [])
        self.assertEqual(
            report["upstream_commit"], MODULE.UPSTREAM_COMMIT
        )
        self.assertEqual(
            report["component_commits"]["Formats"],
            MODULE.FORMATS_COMMIT,
        )
        self.assertEqual(
            report["facts"]["automatically_detected_family_members"],
            ["MSDOS", "NE", "LE", "LX", "DOS16M", "DOS4G", "COM"],
        )
        self.assertEqual(
            report["facts"]["branch_without_public_detector"],
            ["BW DOS16M"],
        )
        self.assertTrue(
            report["facts"][
                "legacy_xbinary_detector_contains_bw_signature"
            ]
        )
        self.assertTrue(
            report["facts"][
                "external_filetypes_property_can_bypass_detection"
            ]
        )
        self.assertEqual(
            set(report["facts"]["absence_counts"].values()),
            {0},
        )

    def test_reference_sources_are_hash_and_line_bound(self):
        self.assertEqual(
            set(self.reference["sources"]),
            set(MODULE.SOURCES),
        )
        for name, source in self.reference["sources"].items():
            self.assertEqual(
                source["sha256"], MODULE.SOURCES[name]["sha256"]
            )
            for fact, matches in source["occurrences"].items():
                self.assertEqual(
                    [match["line"] for match in matches],
                    MODULE.EXPECTED_LINES[name][fact],
                )

    def test_audit_rejects_an_internal_property_setter(self):
        sources = {
            name: b"\n" * 10 for name in MODULE.SOURCES
        }
        sources["xformats"] += b'setProperty("filetypes", value);\n'
        report = MODULE.audit_sources(sources)
        self.assertFalse(report["passed"])
        self.assertIn(
            "xformats_filetypes_property_setters",
            report["failures"],
        )

    def test_audit_rejects_public_bw_detector_token(self):
        sources = {
            name: b"\n" * 10 for name in MODULE.SOURCES
        }
        sources["xformats"] += b"FT_BWDOS16M\n"
        report = MODULE.audit_sources(sources)
        self.assertFalse(report["passed"])
        self.assertIn(
            "xformats_bw_filetype_tokens",
            report["failures"],
        )


if __name__ == "__main__":
    unittest.main()
