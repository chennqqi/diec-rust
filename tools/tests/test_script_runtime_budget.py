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
BUILDER = ROOT / "tools/research/build_script_runtime_budget.py"
REPORT = (
    ROOT / "docs/design/data/script-runtime-budget-candidate.json"
)


def load_builder():
    spec = importlib.util.spec_from_file_location(
        "build_script_runtime_budget",
        BUILDER,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ScriptRuntimeBudgetTests(unittest.TestCase):
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

    def test_profile_values_and_derivations_are_exact(self):
        derivation = self.report["candidate_derivation"]
        self.assertEqual(
            derivation["profiles"],
            {
                "modern_default": {
                    "maximum_live_vm_heap_bytes": 32 * 1024**2,
                    "maximum_js_vm_stack_bytes": 512 * 1024,
                    "maximum_fuel_quanta": 131_072,
                    "runtime_deadline_milliseconds": 10_000,
                },
                "legacy_high_resource": {
                    "maximum_live_vm_heap_bytes": 256 * 1024**2,
                    "maximum_js_vm_stack_bytes": 2 * 1024**2,
                    "maximum_fuel_quanta": 1_048_576,
                    "runtime_deadline_milliseconds": 60_000,
                },
            },
        )
        self.assertEqual(
            derivation["fixed_program_source_bytes"],
            2_902_881,
        )
        self.assertEqual(
            derivation["binary_corpus_operation_anchor"]["total"],
            20_947,
        )
        self.assertTrue(derivation["not_observed_runtime_maxima"])

    def test_units_do_not_conflate_heap_stack_fuel_and_time(self):
        units = self.report["units"]
        self.assertIn("live bytes", units["heap"])
        self.assertIn("JS VM stack", units["stack"])
        self.assertIn("interrupt poll", units["fuel_quantum"])
        self.assertIn("absolute monotonic", units["deadline"])
        identity = self.report["runtime_identity"]
        self.assertTrue(
            identity["default_allocator_required_for_pinned_heap_limit"]
        )

    def test_budget_is_shared_and_never_resets_per_rule_or_child(self):
        sharing = self.report["sharing_and_reset"]
        self.assertTrue(sharing["one_budget_per_scan_runtime"])
        self.assertTrue(sharing["global_and_type_init_count"])
        self.assertTrue(sharing["include_and_detect_count"])
        self.assertTrue(sharing["native_host_api_count"])
        self.assertTrue(sharing["child_work_shares_remaining_budget"])
        self.assertTrue(
            sharing["rule_include_child_or_exception_resets_forbidden"]
        )
        self.assertTrue(
            sharing["effective_deadline_is_minimum_of_script_and_scan"]
        )

    def test_fault_injection_is_not_claimed_as_production_sizing(self):
        evidence = self.report["evidence_boundary"]
        self.assertEqual(
            evidence["fault_injection_only"],
            {
                "heap_limit_bytes": 4 * 1024**2,
                "stack_limit_bytes": 128 * 1024,
                "deadline_milliseconds": 25,
                "infinite_loop_interrupt_polls": 17,
            },
        )
        self.assertFalse(
            evidence["real_corpus_heap_high_water_measured"]
        )
        self.assertTrue(
            evidence["real_corpus_interrupt_poll_count_measured"]
        )
        self.assertEqual(
            evidence["real_corpus_interrupt_poll_repeat_count"],
            3,
        )
        self.assertEqual(
            evidence["real_corpus_interrupt_poll_total_per_repeat"],
            28,
        )
        self.assertTrue(
            evidence[
                "real_corpus_interrupt_poll_stable_projection_equal"
            ]
        )
        self.assertEqual(
            evidence[
                "real_corpus_runtime_measurement_projection_sha256"
            ],
            "286e778c3891dd3b289446526f2910601f9e25932feec25489ee74adbcc5c326",
        )
        self.assertTrue(
            evidence[
                "real_corpus_lifecycle_memory_checkpoints_measured"
            ]
        )
        self.assertEqual(
            evidence["real_corpus_memory_checkpoint_count"],
            4130,
        )
        self.assertEqual(
            evidence[
                "real_corpus_maximum_observed_malloc_size_bytes"
            ],
            654_562,
        )
        self.assertEqual(
            evidence[
                "real_corpus_maximum_observed_memory_used_size_bytes"
            ],
            623_012,
        )
        self.assertTrue(
            evidence["native_host_checkpoint_count_measured"]
        )
        self.assertEqual(
            evidence["real_corpus_native_checkpoint_repeat_count"],
            3,
        )
        self.assertEqual(
            evidence[
                "real_corpus_native_checkpoint_total_per_repeat"
            ],
            16_439,
        )
        self.assertEqual(
            evidence[
                "real_corpus_compare_native_checkpoint_total_per_repeat"
            ],
            16_285,
        )
        self.assertEqual(
            evidence[
                "real_corpus_search_native_checkpoint_total_per_repeat"
            ],
            154,
        )
        self.assertEqual(
            evidence[
                "real_corpus_native_checkpoint_candidate_interval"
            ],
            4096,
        )
        self.assertTrue(
            evidence["native_checkpoint_can_interrupt_single_call"]
        )
        self.assertFalse(evidence["all_format_rule_lifecycles_measured"])
        self.assertIn(
            "operation-anchor to VM-poll conversion",
            evidence["does_not_prove"],
        )
        self.assertIn(
            "native checkpoint coverage for every HostApi",
            evidence["does_not_prove"],
        )

    def test_failure_contract_is_typed_and_no_partial_rule_is_published(self):
        contract = self.report["failure_contract"]
        self.assertEqual(
            contract["fuel_exhaustion"],
            "LimitReached(script_fuel)",
        )
        self.assertEqual(
            contract["script_deadline"],
            "Timeout(script_deadline)",
        )
        self.assertTrue(contract["cancel_has_independent_typed_reason"])
        self.assertTrue(contract["partial_rule_detection_is_not_published"])

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

            report_path = root / self.module.SOURCES["runtime_report"]
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["full_binary_corpus_oracle"][
                "signature_compare_call_total"
            ] += 1
            report_path.write_text(
                json.dumps(report, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                self.module.ScriptBudgetError,
                "full Binary corpus operation evidence drift",
            ):
                self.module.build_candidate(root)

    def test_candidate_remains_unadmitted(self):
        self.assertEqual(
            self.report["result"],
            "review_candidate_not_admitted",
        )


if __name__ == "__main__":
    unittest.main()
