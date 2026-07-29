import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools/upstream/collect_windows_dispatch.py"
REPORT = ROOT / "docs/research/data/dispatch-engine-windows-qt5.json"


class CollectWindowsDispatchTests(unittest.TestCase):
    def test_collector_reuses_all_five_linux_validators(self):
        text = SCRIPT.read_text(encoding="utf-8")
        for helper in (
            "probe_dos_dispatch.py",
            "probe_legacy_dispatch.py",
            "probe_bw_dispatch_harness.py",
            "probe_npm_dispatch_harness.py",
            "probe_generic_archive_dispatch_harness.py",
        ):
            with self.subTest(helper=helper):
                self.assertIn(helper, text)

    @unittest.skipUnless(REPORT.exists(), "Windows report not collected")
    def test_formal_report_closes_three_dispatch_rows(self):
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        self.assertTrue(report["passed"])
        self.assertEqual(report["failures"], [])
        self.assertEqual(report["repetitions"], 2)
        self.assertEqual(report["execution_count"], 86)
        self.assertEqual(report["case_observation_count"], 72)
        self.assertEqual(
            report["capability_scope"],
            [
                "CAP-DISPATCH-002",
                "CAP-DISPATCH-003",
                "CAP-DISPATCH-004",
            ],
        )
        self.assertTrue(all(report["relationships"].values()))

    @unittest.skipUnless(REPORT.exists(), "Windows report not collected")
    def test_public_and_private_comparisons_are_complete(self):
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        public = report["public_cli"]
        self.assertEqual(public["dos"]["case_count"], 19)
        self.assertEqual(public["dos"]["execution_count"], 38)
        self.assertEqual(public["legacy"]["case_count"], 8)
        self.assertEqual(public["legacy"]["execution_count"], 32)
        for suite in public.values():
            self.assertTrue(
                suite["all_linux_qt5_semantic_projections_equal"]
            )
            self.assertTrue(suite["all_semantic_outputs_equal"])
        private = report["private_harnesses"]
        self.assertEqual(set(private), {"bw", "npm", "generic_archive"})
        self.assertTrue(
            all(
                suite["all_full_documents_equal_linux_qt5"]
                for suite in private.values()
            )
        )

    @unittest.skipUnless(REPORT.exists(), "Windows report not collected")
    def test_report_contains_no_local_path(self):
        text = REPORT.read_text(encoding="utf-8")
        self.assertIn("<working-directory>/Detect-It-Easy", text)
        for forbidden in (
            "C:/Users",
            "C:\\\\Users",
            "I:/tmp",
            "I:\\\\tmp",
            "worker",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
