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
BUILDER = (
    ROOT / "tools/research/build_traversal_attempt_budget.py"
)
REPORT = (
    ROOT
    / "docs/design/data/traversal-attempt-budget-candidate.json"
)


def load_builder():
    spec = importlib.util.spec_from_file_location(
        "build_traversal_attempt_budget",
        BUILDER,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TraversalAttemptBudgetTests(unittest.TestCase):
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

    def test_attempt_unit_counts_failure_and_retry(self):
        unit = self.report["attempt_unit"]
        self.assertTrue(unit["reserve_before_adapter_call"])
        self.assertTrue(unit["failed_attempts_count"])
        self.assertTrue(unit["automatic_retries_count_again"])
        self.assertFalse(unit["cached_facts_without_refresh_count"])
        self.assertIn("read-link", unit["definition"])
        self.assertIn("reparse", unit["definition"])

    def test_profiles_follow_structural_formula(self):
        derivation = self.report["derivation"]
        modern = derivation["modern_default"]
        legacy = derivation["legacy_high_resource"]
        self.assertEqual(
            modern,
            {
                "maximum_entries_considered": 100_000,
                "maximum_files_emitted": 100_000,
                "root_attempt_allowance": 4,
                "per_considered_entry_attempt_allowance": 4,
                "per_emitted_file_handoff_allowance": 1,
                "raw_structural_allowance": 500_004,
                "maximum_metadata_open_attempts": 524_288,
            },
        )
        self.assertEqual(
            legacy,
            {
                "maximum_entries_considered": 1_000_000,
                "maximum_files_emitted": 1_000_000,
                "root_attempt_allowance": 4,
                "per_considered_entry_attempt_allowance": 4,
                "per_emitted_file_handoff_allowance": 1,
                "raw_structural_allowance": 5_000_004,
                "maximum_metadata_open_attempts": 8_388_608,
            },
        )
        self.assertEqual(
            self.module.derive_attempt_limit(1, 1)[
                "maximum_metadata_open_attempts"
            ],
            16,
        )

    def test_upstream_observations_are_not_attempt_measurements(self):
        evidence = self.report["upstream_evidence_boundary"]
        self.assertFalse(evidence["filesystem_attempt_count_measured"])
        self.assertEqual(evidence["linux_complete_flat_entries"], 4096)
        self.assertEqual(evidence["linux_complete_nested_files"], 4096)
        self.assertEqual(evidence["windows_complete_flat_entries"], 4096)
        self.assertEqual(evidence["windows_complete_nested_files"], 4096)
        self.assertTrue(
            evidence["enumerate_then_reopen_toctou_observed"]
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

            report_path = root / self.module.SOURCES["linux_toctou"]
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["facts"][
                "swap_old_to_new_matches_stable_new"
            ] = False
            report_path.write_text(
                json.dumps(report, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                self.module.AttemptBudgetError,
                "Linux TOCTOU facts drift|linux TOCTOU facts drift",
            ):
                self.module.build_candidate(root)

    def test_candidate_remains_unadmitted(self):
        self.assertEqual(
            self.report["result"],
            "review_candidate_not_admitted",
        )
        self.assertIn(
            "not an upstream syscall measurement",
            self.report["derivation"]["interpretation"],
        )


if __name__ == "__main__":
    unittest.main()
