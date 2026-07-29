import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools/upstream/collect_windows_archive_limits.py"
REPORT = (
    ROOT / "docs/research/data/archive-limit-engine-windows-qt5.json"
)


class CollectWindowsArchiveLimitsTests(unittest.TestCase):
    @unittest.skipUnless(REPORT.exists(), "Windows report not collected")
    def test_formal_report_closes_archive_limit_capability(self):
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        self.assertTrue(report["passed"])
        self.assertEqual(report["failures"], [])
        self.assertEqual(report["capability"], "CAP-NEST-009")
        self.assertEqual(report["repetitions"], 2)
        self.assertEqual(report["normal_case_count"], 14)
        self.assertEqual(report["cancellation_case_count"], 1)
        self.assertEqual(report["execution_count"], 30)
        self.assertEqual(report["case_observation_count"], 30)
        self.assertEqual(len(report["relationships"]), 12)
        self.assertTrue(all(report["relationships"].values()))
        self.assertEqual(
            report["generator_sha256"],
            hashlib.sha256(SCRIPT.read_bytes()).hexdigest(),
        )

    @unittest.skipUnless(REPORT.exists(), "Windows report not collected")
    def test_report_contains_no_local_path(self):
        text = REPORT.read_text(encoding="utf-8")
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
