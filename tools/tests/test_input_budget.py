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
BUILDER = ROOT / "tools/research/build_input_budget.py"
REPORT = ROOT / "docs/design/data/input-budget-candidate.json"


def load_builder():
    spec = importlib.util.spec_from_file_location(
        "build_input_budget",
        BUILDER,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class InputBudgetTests(unittest.TestCase):
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

    def test_unit_and_entry_points_are_unambiguous(self):
        unit = self.report["root_input_unit"]
        self.assertEqual(
            unit["definition"],
            "stable logical byte length of the root ScanSource",
        )
        self.assertTrue(unit["root_only"])
        self.assertTrue(unit["child_or_expanded_objects_do_not_count_again"])
        self.assertFalse(unit["unknown_length_streaming_supported"])
        self.assertEqual(unit["bytes_source_measurement"], "borrowed slice length")
        self.assertIn("opened stable file handle", unit["path_measurement"])

    def test_candidate_profiles_and_counter_relationship_are_exact(self):
        profiles = self.report["candidate_derivation"]["profiles"]
        self.assertEqual(
            profiles,
            {
                "modern_default": {
                    "maximum_root_input_bytes": 1024**3,
                    "total_source_bytes_read_or_mapped": 1024**3,
                },
                "legacy_high_resource": {
                    "maximum_root_input_bytes": 8 * 1024**3,
                    "total_source_bytes_read_or_mapped": 8 * 1024**3,
                },
            },
        )
        for profile in profiles.values():
            self.assertEqual(
                profile["maximum_root_input_bytes"],
                profile["total_source_bytes_read_or_mapped"],
            )
        relationships = self.report["counter_relationships"]
        self.assertTrue(relationships["root_length_is_not_cumulative_io"])
        self.assertTrue(
            relationships["total_read_or_mapped_is_charged_independently"]
        )
        self.assertTrue(
            relationships["root_length_does_not_authorize_equal_allocation"]
        )

    def test_boundary_runs_before_work_and_does_not_return_partial(self):
        enforcement = self.report["enforcement"]
        self.assertTrue(enforcement["exact_limit_is_allowed"])
        self.assertIn("before parser", enforcement["reserve_stage"])
        self.assertIn("LimitReached", enforcement["over_limit_behavior"])
        self.assertIn("no partial scan report", enforcement["over_limit_behavior"])
        self.assertTrue(
            enforcement[
                "concurrent_length_change_fails_closed_under_adr_0013"
            ]
        )

    def test_observed_inputs_are_not_sizing_maxima(self):
        evidence = self.report["upstream_evidence_boundary"]
        self.assertEqual(evidence["engine_contract_case_count"], 37)
        self.assertEqual(
            evidence["maximum_observed_root_archive_bytes"],
            16_777_452,
        )
        self.assertEqual(
            evidence["maximum_observed_cumulative_expanded_bytes"],
            33_554_546,
        )
        self.assertTrue(
            self.report["candidate_derivation"][
                "not_upstream_observed_maximum"
            ]
        )
        self.assertIn(
            "1 GiB or 8 GiB memory or latency acceptability",
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

            report_path = root / self.module.SOURCES["engine_contract"]
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["relationships"][
                "incomplete_device_reads_are_silent_success"
            ] = False
            report_path.write_text(
                json.dumps(report, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                self.module.InputBudgetError,
                "engine input/read evidence drift",
            ):
                self.module.build_candidate(root)

    def test_candidate_remains_unadmitted(self):
        self.assertEqual(
            self.report["result"],
            "review_candidate_not_admitted",
        )


if __name__ == "__main__":
    unittest.main()
