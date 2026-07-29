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
BUILDER = ROOT / "tools/research/build_allocation_budget.py"
REPORT = ROOT / "docs/design/data/allocation-budget-candidate.json"


def load_builder():
    spec = importlib.util.spec_from_file_location(
        "build_allocation_budget",
        BUILDER,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class AllocationBudgetTests(unittest.TestCase):
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

    def test_allocation_unit_is_monotonic_and_conservative(self):
        unit = self.report["allocation_unit"]
        self.assertIn("monotonic sum", unit["definition"])
        self.assertEqual(
            unit["byte_storage_charge"],
            "requested capacity bytes",
        )
        self.assertIn(
            "portable element charge",
            unit["typed_storage_charge"],
        )
        self.assertTrue(
            unit[
                "cross_target_compile_time_size_assertion_required"
            ]
        )
        self.assertTrue(
            unit["moving_grow_or_replacement_charges_full_new_capacity"]
        )
        self.assertTrue(
            unit["reuse_within_committed_capacity_charges_zero"]
        )
        self.assertFalse(unit["deallocation_refunds"])
        self.assertFalse(unit["failed_allocator_attempt_commits_charge"])

    def test_candidate_profiles_have_exact_structural_relationships(self):
        profiles = self.report["candidate_derivation"]["profiles"]
        self.assertEqual(
            profiles,
            {
                "modern_default": {
                    "maximum_single_allocation_bytes": 128 * 1024**2,
                    "maximum_total_allocation_bytes": 1024**3,
                    "total_expanded_bytes": 512 * 1024**2,
                },
                "legacy_high_resource": {
                    "maximum_single_allocation_bytes": 512 * 1024**2,
                    "maximum_total_allocation_bytes": 8 * 1024**3,
                    "total_expanded_bytes": 4 * 1024**3,
                },
            },
        )
        for profile in profiles.values():
            self.assertEqual(
                profile["maximum_total_allocation_bytes"],
                2 * profile["total_expanded_bytes"],
            )
        self.assertTrue(
            self.report["candidate_derivation"][
                "not_upstream_observed_maximum"
            ]
        )

    def test_reservation_protocol_fails_before_allocator(self):
        protocol = self.report["reservation_protocol"]
        self.assertFalse(protocol["budget_rejection_allocates"])
        self.assertEqual(
            protocol["counter_overflow"],
            "fail closed before allocator call",
        )
        self.assertTrue(protocol["exact_limit_can_reuse_existing_capacity"])
        self.assertEqual(
            protocol["first_positive_increment_after_exact_limit"],
            "LimitReached",
        )
        self.assertIn(
            "commit charge only after allocator success",
            protocol["order"],
        )

    def test_scope_is_not_misrepresented_as_process_rss(self):
        scope = self.report["scope"]
        self.assertTrue(scope["not_an_os_or_process_rss_cap"])
        self.assertEqual(
            scope["excluded"]["script_heap"],
            "ScriptLimits",
        )
        self.assertEqual(
            scope["excluded"]["database_owned_memory"],
            "DatabaseLimits",
        )
        evidence = self.report["upstream_evidence_boundary"]
        self.assertTrue(evidence["measurements_are_whole_process_rss"])
        self.assertTrue(
            evidence["measurements_are_not_scan_owned_allocations"]
        )
        self.assertFalse(evidence["benchmark_targets_frozen"])

    def test_observed_evidence_boundary_is_exact(self):
        evidence = self.report["upstream_evidence_boundary"]
        self.assertEqual(evidence["archive_normal_case_count"], 14)
        self.assertEqual(
            evidence["archive_maximum_process_peak_rss_kib"],
            56_472,
        )
        self.assertEqual(
            evidence["archive_maximum_process_peak_rss_delta_kib"],
            37_572,
        )
        self.assertEqual(
            evidence["repeated_product_maximum_process_peak_rss_bytes"],
            80_953_344,
        )
        self.assertIn(
            "cumulative allocation capacity used by upstream",
            evidence["does_not_prove"],
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

            report_path = root / self.module.SOURCES["repeated_benchmark"]
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["targets_frozen"] = True
            report_path.write_text(
                json.dumps(report, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                self.module.AllocationBudgetError,
                "repeated benchmark identity drift",
            ):
                self.module.build_candidate(root)

    def test_candidate_remains_unadmitted(self):
        self.assertEqual(
            self.report["result"],
            "review_candidate_not_admitted",
        )


if __name__ == "__main__":
    unittest.main()
