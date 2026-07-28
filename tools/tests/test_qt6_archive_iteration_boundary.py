import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT
    / "tools"
    / "upstream"
    / "probe_archive_iteration_boundary_harness.py"
)
QT5_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "archive-iteration-boundary-engine-qt5.json"
)
QT6_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "archive-iteration-boundary-engine-qt6.json"
)
MANIFEST_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "archive-iteration-boundary-corpus.json"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_archive_iteration_boundary_harness_for_qt6_test",
    MODULE_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class Qt6ArchiveIterationBoundaryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt5 = json.loads(QT5_PATH.read_text(encoding="utf-8"))
        cls.qt6 = json.loads(QT6_PATH.read_text(encoding="utf-8"))

    def test_qt6_report_passes_platform_specific_contract(self):
        self.assertTrue(self.qt6["passed"])
        self.assertEqual(self.qt6["failures"], [])
        self.assertEqual(MODULE.evaluate_report(self.qt6), [])
        self.assertTrue(all(self.qt6["assertions"].values()))
        self.assertEqual(
            self.qt6["environment"]["platform"],
            "linux-x86_64-qt6",
        )
        self.assertEqual(
            self.qt6["environment"]["image_identity"]["id"],
            "sha256:a51310e8e03ada9fb907d6ea3d3d3b0a"
            "5d0c1917a3aaef971f3a07683486508f",
        )
        self.assertEqual(
            self.qt6["harness_binary"]["sha256"],
            "d13b381bc5353f8e261a741c235a825e"
            "65461d8ab38cf9f9ba71c16fb94dfbcb",
        )

    def test_qt6_boundary_is_stably_one_record_earlier(self):
        qt5 = {
            case["sample"]: case["harness"]
            for case in self.qt5["cases"]
        }
        qt6 = {
            case["sample"]: case["harness"]
            for case in self.qt6["cases"]
        }
        self.assertEqual(
            {
                name: (
                    item["node_count"],
                    item["pdf_node_count"],
                    item["record_count"],
                    item["stream_node_count"],
                )
                for name, item in qt5.items()
            },
            {
                "sentinel-099999.iso": (2, 1, 3, 1),
                "sentinel-100000.iso": (2, 1, 3, 1),
                "sentinel-100001.iso": (1, 0, 1, 0),
            },
        )
        self.assertEqual(
            {
                name: (
                    item["node_count"],
                    item["pdf_node_count"],
                    item["record_count"],
                    item["stream_node_count"],
                )
                for name, item in qt6.items()
            },
            {
                "sentinel-099999.iso": (3, 1, 4, 2),
                "sentinel-100000.iso": (2, 0, 2, 1),
                "sentinel-100001.iso": (2, 0, 2, 1),
            },
        )
        self.assertEqual(
            self.qt6["known_difference"],
            {
                "scope": "ISO9660 NUL dot-entry filtering",
                "qt5_last_reachable_pdf_ordinal": 100000,
                "qt6_last_reachable_pdf_ordinal": 99999,
                "qt6_extra_stream_count_per_case": 1,
                "source_revision_equal": True,
                "requires_qt_string_semantics_probe": True,
            },
        )

    def test_source_corpus_and_raw_observations_are_bound(self):
        self.assertEqual(
            self.qt6["source_contract"]["sha256"],
            MODULE.EXPECTED_SOURCE_SHA256,
        )
        self.assertEqual(
            self.qt6["iso_source_contract"]["sha256"],
            MODULE.EXPECTED_ISO_SOURCE_SHA256,
        )
        self.assertEqual(
            self.qt6["iso_source_contract"][
                "dot_filter_pattern"
            ],
            MODULE.ISO_DOT_FILTER_PATTERN,
        )
        self.assertEqual(
            self.qt6["corpus_manifest_sha256"],
            hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(),
        )
        for case in self.qt6["cases"]:
            with self.subTest(sample=case["sample"]):
                stdout = case["stdout"].encode("utf-8")
                stderr = case["stderr"].encode("utf-8")
                self.assertEqual(
                    hashlib.sha256(stdout).hexdigest(),
                    case["stdout_sha256"],
                )
                self.assertEqual(
                    hashlib.sha256(stderr).hexdigest(),
                    case["stderr_sha256"],
                )
                self.assertEqual(json.loads(case["stdout"]), case["harness"])
                self.assertEqual(case["exit_code"], 0)
                self.assertFalse(case["timed_out"])
                self.assertFalse(case["possible_oom_exit_137"])


if __name__ == "__main__":
    unittest.main()
