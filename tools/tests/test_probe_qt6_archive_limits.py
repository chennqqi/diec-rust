import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT / "tools" / "upstream" / "probe_qt6_archive_limits.py"
)
REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "archive-limit-engine-qt5-qt6.json"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_qt6_archive_limits",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


@unittest.skipUnless(REPORT_PATH.exists(), "paired report not generated")
class ProbeQt6ArchiveLimitsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    def test_report_closes_the_fixed_qt5_qt6_boundary(self):
        self.assertTrue(self.report["passed"])
        self.assertEqual(self.report["failures"], [])
        self.assertEqual(self.report["capability"], "CAP-NEST-009")
        self.assertEqual(
            self.report["platform"],
            "linux-x86_64-qt5-qt6",
        )
        self.assertTrue(all(self.report["facts"].values()))

    def test_qt6_raw_report_passes_base_semantic_assertions(self):
        base = MODULE.load_probe(ROOT)
        qt6 = self.report["qt6"]
        self.assertTrue(qt6["passed"])
        self.assertEqual(base.evaluate_report(qt6), [])
        self.assertEqual(
            qt6["environment"]["platform"],
            "linux-x86_64-qt6",
        )

    def test_stable_projection_matches_the_qt5_reference(self):
        qt5 = json.loads(
            (ROOT / MODULE.QT5_REPORT_PATH).read_text(
                encoding="utf-8"
            )
        )
        left = MODULE.behavior_projection(qt5)
        right = MODULE.behavior_projection(self.report["qt6"])
        self.assertEqual(left, right)
        self.assertEqual(
            MODULE.projection_sha256(left),
            self.report["comparison"][
                "behavior_projection_sha256"
            ],
        )

    def test_projection_rejects_a_depth_change(self):
        qt5 = json.loads(
            (ROOT / MODULE.QT5_REPORT_PATH).read_text(
                encoding="utf-8"
            )
        )
        changed = copy.deepcopy(self.report["qt6"])
        changed["normal_cases"][-1]["harness"][
            "deepest_pdf_depth"
        ] += 1
        self.assertNotEqual(
            MODULE.behavior_projection(qt5),
            MODULE.behavior_projection(changed),
        )

    def test_supporting_reports_are_current_and_hash_bound(self):
        self.assertEqual(
            MODULE.validate_supporting_reports(ROOT),
            self.report["supporting_reports"],
        )

    def test_local_harness_sources_are_hash_bound(self):
        expected = {
            path: MODULE.sha256((ROOT / path).read_bytes())
            for path in MODULE.LOCAL_SOURCES
        }
        self.assertEqual(self.report["local_sources"], expected)


if __name__ == "__main__":
    unittest.main()
