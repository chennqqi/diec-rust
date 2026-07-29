import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "tools/research/build_diagnostic_budget.py"
REPORT = ROOT / "docs/design/data/diagnostic-budget-candidate.json"


def load_builder():
    spec = importlib.util.spec_from_file_location(
        "build_diagnostic_budget",
        BUILDER,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class DiagnosticBudgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_builder()
        cls.report = json.loads(REPORT.read_text(encoding="utf-8"))

    def test_committed_candidate_is_exactly_reproducible(self):
        expected = self.module.serialize(
            self.module.build_candidate(ROOT)
        )
        self.assertEqual(REPORT.read_bytes(), expected)
        completed = subprocess.run(
            [sys.executable, str(BUILDER), "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_diagnostic_unit_and_overflow_are_unambiguous(self):
        unit = self.report["diagnostic_unit"]
        self.assertEqual(
            unit["definition"],
            "one canonical typed diagnostic fact",
        )
        self.assertTrue(unit["renderer_lines_or_views_do_not_count"])
        self.assertTrue(unit["reserve_before_message_path_or_detail_copy"])
        self.assertTrue(unit["child_work_shares_parent_counter"])
        self.assertTrue(unit["silent_drop_or_fact_merge_forbidden"])
        self.assertIn("do not create limit+1", unit["overflow_behavior"])
        self.assertIn("outside the diagnostic arena", unit["overflow_behavior"])

    def test_profile_candidates_and_field_closure_are_exact(self):
        profiles = self.report["candidate_derivation"]["profiles"]
        self.assertEqual(
            profiles["modern_default"],
            {
                "maximum_archive_entries_considered": 4096,
                "maximum_queued_items": 4096,
                "maximum_result_nodes": 100_000,
                "maximum_diagnostics": 4096,
            },
        )
        self.assertEqual(
            profiles["legacy_high_resource"],
            {
                "maximum_archive_entries_considered": 100_001,
                "maximum_queued_items": 131_072,
                "maximum_result_nodes": 1_048_576,
                "maximum_diagnostics": 131_072,
            },
        )
        closure = self.report["profile_closure"]
        self.assertTrue(closure["field_sets_must_match"])
        self.assertEqual(
            len(closure["scan_fields_required_in_both_profiles"]),
            10,
        )
        self.assertIn(
            "maximum_diagnostics",
            closure["scan_fields_required_in_both_profiles"],
        )
        self.assertIn(
            "maximum_root_input_bytes",
            closure["scan_fields_required_in_both_profiles"],
        )

    def test_observed_single_line_cases_are_not_sizing_maxima(self):
        evidence = self.report["upstream_evidence_boundary"]
        self.assertEqual(evidence["qt5_typo"]["scan_count"], 4)
        self.assertEqual(
            evidence["qt5_typo"][
                "maximum_diagnostic_lines_per_scan"
            ],
            1,
        )
        self.assertEqual(evidence["qt5_qt6_typo"]["scan_count"], 6)
        self.assertTrue(
            evidence["qt5_qt6_typo"]["normalized_detections_equal"]
        )
        self.assertFalse(
            evidence["qt5_qt6_typo"]["diagnostic_text_equal"]
        )
        self.assertTrue(
            self.report["candidate_derivation"][
                "not_upstream_observed_maximum"
            ]
        )

    def test_source_bindings_are_complete_and_current(self):
        bindings = self.report["source_bindings"]
        self.assertEqual(set(bindings), set(self.module.SOURCES))
        for name, relative in self.module.SOURCES.items():
            self.assertEqual(bindings[name]["path"], relative)
            self.assertEqual(
                bindings[name]["sha256"],
                hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(),
            )

    def test_report_or_contract_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in self.module.SOURCES.values():
                destination = root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, destination)

            report_path = root / self.module.SOURCES["qt5_qt6_typo"]
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["diagnostics_equal"] = True
            report_path.write_text(
                json.dumps(report, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                self.module.DiagnosticBudgetError,
                "Qt5/Qt6 typo diagnostic boundary drift",
            ):
                self.module.build_candidate(root)

    def test_candidate_remains_unadmitted(self):
        self.assertEqual(
            self.report["result"],
            "review_candidate_not_admitted",
        )
        self.assertIn(
            "maximum diagnostics produced by arbitrary input",
            self.report["upstream_evidence_boundary"]["does_not_prove"],
        )


if __name__ == "__main__":
    unittest.main()
