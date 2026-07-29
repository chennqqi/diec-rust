import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools/research/build_windows_closure_plan.py"
REPORT = (
    ROOT / "docs/research/data/windows-capability-closure-plan.json"
)
TRACEABILITY = (
    ROOT / "docs/research/data/capability-traceability.json"
)
DOCUMENT = ROOT / "docs/research/windows-capability-closure-plan.md"
SPEC = importlib.util.spec_from_file_location(
    "build_windows_closure_plan",
    SCRIPT,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class WindowsCapabilityClosurePlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT.read_text(encoding="utf-8"))
        cls.traceability = json.loads(
            TRACEABILITY.read_text(encoding="utf-8")
        )

    def test_report_is_reproducible_and_source_bound(self):
        subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--root",
                str(ROOT),
                "--output",
                str(REPORT),
                "--check",
            ],
            check=True,
            capture_output=True,
        )
        sources = self.report["sources"]
        for path, digest in sources.items():
            with self.subTest(path=path):
                self.assertEqual(
                    hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
                    digest,
                )

    def test_all_68_rows_are_classified_once_in_traceability_order(self):
        expected = [
            row["id"] for row in self.traceability["capabilities"]
        ]
        actual = [row["id"] for row in self.report["capabilities"]]
        self.assertEqual(actual, expected)
        self.assertEqual(len(actual), 68)
        self.assertEqual(len(set(actual)), 68)
        self.assertTrue(
            self.report["summary"]["all_capabilities_accounted_for"]
        )

    def test_status_counts_are_conservative(self):
        summary = self.report["summary"]
        self.assertEqual(summary["evidence_complete"], 42)
        self.assertEqual(summary["partial"], 12)
        self.assertEqual(summary["missing"], 14)
        self.assertEqual(summary["closure_required"], 26)
        self.assertFalse(summary["windows_baseline_admitted"])
        statuses = {
            row["status"] for row in self.report["capabilities"]
        }
        self.assertEqual(
            statuses,
            {"evidence_complete", "partial", "missing"},
        )

    def test_complete_partial_and_missing_contracts_are_explicit(self):
        for row in self.report["capabilities"]:
            with self.subTest(capability=row["id"]):
                self.assertTrue(row["acceptance"])
                if row["status"] == "evidence_complete":
                    self.assertTrue(row["observed_scope"])
                    self.assertIsNone(row["missing_scope"])
                    self.assertIsNone(row["proposed_experiment"])
                    self.assertTrue(row["evidence_paths"])
                elif row["status"] == "partial":
                    self.assertTrue(row["observed_scope"])
                    self.assertTrue(row["missing_scope"])
                    self.assertTrue(row["proposed_experiment"])
                    self.assertTrue(row["evidence_paths"])
                else:
                    self.assertIsNone(row["observed_scope"])
                    self.assertTrue(row["missing_scope"])
                    self.assertTrue(row["proposed_experiment"])
                if row["status"] != "evidence_complete":
                    experiment = row["proposed_experiment"]
                    self.assertTrue(experiment["fixture"])
                    self.assertTrue(experiment["harness"])
                    self.assertGreaterEqual(
                        len(experiment["assertions"]),
                        3,
                    )

    def test_known_blockers_are_not_promoted(self):
        rows = {
            row["id"]: row for row in self.report["capabilities"]
        }
        self.assertEqual(rows["CAP-CLI-IN-003"]["status"], "partial")
        self.assertEqual(
            rows["CAP-ENG-IN-001"]["status"],
            "evidence_complete",
        )
        self.assertEqual(
            rows["CAP-ENG-IN-002"]["status"],
            "evidence_complete",
        )
        self.assertEqual(
            rows["CAP-RULE-006"]["status"],
            "evidence_complete",
        )
        self.assertEqual(
            rows["CAP-RULE-009"]["status"],
            "evidence_complete",
        )
        self.assertEqual(
            rows["CAP-RULE-012"]["status"],
            "evidence_complete",
        )
        self.assertEqual(rows["CAP-RULE-007"]["status"], "missing")
        self.assertEqual(rows["CAP-NEST-003"]["status"], "missing")
        self.assertEqual(rows["CAP-RESULT-001"]["status"], "partial")
        self.assertEqual(
            rows["CAP-CLI-OUT-002"]["status"],
            "evidence_complete",
        )
        self.assertEqual(
            rows["CAP-CLI-DB-004"]["status"],
            "evidence_complete",
        )

    def test_machine_report_binds_all_13_windows_reports(self):
        self.assertEqual(
            self.report["summary"]["windows_report_count"],
            13,
        )
        self.assertEqual(
            self.report["summary"]["windows_process_execution_count"],
            2072,
        )
        report_sources = {
            path
            for path in self.report["sources"]
            if path.startswith("docs/research/data/")
            and "windows" in path
            and path
            not in {
                "docs/research/data/windows-qt5-build-baseline.json"
            }
        }
        self.assertEqual(len(report_sources), 13)

    def test_document_names_every_open_row_and_machine_report(self):
        text = DOCUMENT.read_text(encoding="utf-8")
        self.assertIn(REPORT.name, text)
        for row in self.report["capabilities"]:
            if row["status"] != "evidence_complete":
                with self.subTest(capability=row["id"]):
                    self.assertIn(row["id"], text)


if __name__ == "__main__":
    unittest.main()
