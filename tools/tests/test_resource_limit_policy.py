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
BUILDER = ROOT / "tools/research/build_resource_limit_policy.py"
POLICY_PATH = (
    ROOT / "docs/design/data/resource-limit-policy-candidate.json"
)


def load_builder():
    spec = importlib.util.spec_from_file_location(
        "build_resource_limit_policy",
        BUILDER,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ResourceLimitPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builder = load_builder()
        cls.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))

    def test_committed_policy_is_exactly_reproducible(self):
        expected = self.builder.serialize(
            self.builder.build_policy(ROOT)
        )
        self.assertEqual(POLICY_PATH.read_bytes(), expected)
        completed = subprocess.run(
            [sys.executable, str(BUILDER), "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_source_bindings_are_complete_and_current(self):
        bindings = self.policy["source_bindings"]
        self.assertEqual(set(bindings), set(self.builder.SOURCES))
        for name, relative in self.builder.SOURCES.items():
            binding = bindings[name]
            self.assertEqual(binding["path"], relative)
            self.assertEqual(
                binding["sha256"],
                hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(),
            )
            self.assertNotIn("\\", relative)
            self.assertFalse(Path(relative).is_absolute())

    def test_candidate_profiles_match_proposed_adrs(self):
        profiles = self.policy["profiles"]
        modern = profiles["modern_default"]
        legacy = profiles["legacy_high_resource"]
        self.assertEqual(
            modern["scan"],
            {
                "wall_deadline_milliseconds": 30_000,
                "maximum_nested_depth": 32,
                "total_archive_entries_considered": 4096,
                "maximum_queued_items": 4096,
                "maximum_result_nodes": 100_000,
                "maximum_single_expanded_object_bytes": 128 * 1024**2,
                "total_expanded_bytes": 512 * 1024**2,
                "total_source_bytes_read_or_mapped": 1024**3,
            },
        )
        self.assertEqual(
            modern["traversal"],
            {
                "wall_deadline_milliseconds": 30_000,
                "maximum_directory_depth": 64,
                "maximum_entries_considered": 100_000,
                "maximum_files_emitted": 100_000,
                "maximum_total_native_path_bytes": 64 * 1024**2,
            },
        )
        self.assertEqual(
            modern["include"],
            {
                "maximum_active_depth": 16,
                "maximum_total_evaluations": 256,
                "status": "review_candidate_not_admitted",
            },
        )
        self.assertEqual(
            modern["database"],
            {
                "status": "review_candidate_not_admitted",
                "maximum_sources": 32,
                "maximum_entries": 32_768,
                "maximum_single_entry_bytes": 8 * 1024**2,
                "maximum_total_entry_bytes": 32 * 1024**2,
                "maximum_single_container_bytes": 32 * 1024**2,
                "maximum_total_container_bytes": 32 * 1024**2,
                "maximum_single_logical_path_bytes": 512,
                "maximum_total_logical_path_bytes": 512 * 1024,
                "maximum_cache_bytes": 64 * 1024**2,
                "maximum_cache_records": 32_768,
            },
        )
        self.assertEqual(
            legacy["database"],
            {
                "status": "review_candidate_not_admitted",
                "default_for_any_adapter": False,
                "maximum_sources": 256,
                "maximum_entries": 262_144,
                "maximum_single_entry_bytes": 64 * 1024**2,
                "maximum_total_entry_bytes": 256 * 1024**2,
                "maximum_single_container_bytes": 256 * 1024**2,
                "maximum_total_container_bytes": 256 * 1024**2,
                "maximum_single_logical_path_bytes": 4096,
                "maximum_total_logical_path_bytes": 4 * 1024**2,
                "maximum_cache_bytes": 512 * 1024**2,
                "maximum_cache_records": 262_144,
            },
        )
        self.assertEqual(
            legacy["include"],
            {
                "maximum_active_depth": 64,
                "maximum_total_evaluations": 4096,
                "status": "review_candidate_not_admitted",
            },
        )
        self.assertFalse(legacy["default_for_any_adapter"])
        self.assertGreater(
            legacy["scan"]["total_expanded_bytes"],
            modern["scan"]["total_expanded_bytes"],
        )
        self.assertGreater(
            legacy["traversal"]["maximum_entries_considered"],
            modern["traversal"]["maximum_entries_considered"],
        )
        self.assertEqual(
            {modern["status"], legacy["status"]},
            {"review_candidate_not_admitted"},
        )

    def test_upstream_facts_and_spike_limits_stay_separate(self):
        facts = self.policy["upstream_compatibility_observations"]
        self.assertEqual(facts["archive_depth_maximum_tested"], 64)
        self.assertEqual(
            facts["archive_expanded_bytes_maximum_tested"],
            33_554_546,
        )
        self.assertTrue(
            facts["archive_has_no_independent_depth_or_total_limit"]
        )
        self.assertEqual(
            facts["legacy_default_resource_children_inclusive"],
            21,
        )
        self.assertEqual(
            facts["legacy_aggressive_resource_children_inclusive"],
            2001,
        )
        self.assertEqual(
            facts["legacy_aggressive_archive_record_reachable"],
            100_000,
        )
        self.assertEqual(
            facts["legacy_aggressive_archive_record_not_reachable"],
            100_001,
        )
        spike = facts["runtime_spike_only"]
        self.assertEqual(spike["memory_limit_bytes"], 4 * 1024**2)
        self.assertEqual(spike["stack_limit_bytes"], 128 * 1024)
        self.assertEqual(spike["deadline_milliseconds"], 25)
        self.assertFalse(spike["production_default_candidate"])
        self.assertEqual(
            facts["fixed_rule_include_graph"],
            {
                "program_file_count": 2235,
                "literal_call_count": 56,
                "maximum_transitive_evaluations": 30,
                "maximum_active_depth": 2,
                "non_literal_or_unresolved_or_cyclic_count": 0,
                "binary_dynamic_trace_matches": True,
            },
        )
        self.assertEqual(
            facts["fixed_database_bundle"],
            {
                "source_count": 3,
                "entry_count": 2268,
                "total_entry_bytes": 2_909_316,
                "maximum_single_entry_bytes": 603_640,
                "total_container_bytes": 3_201_508,
            },
        )

    def test_unresolved_budgets_keep_policy_unadmitted(self):
        unresolved = self.policy["unresolved_required_budgets"]
        ids = [item["id"] for item in unresolved]
        self.assertEqual(len(ids), 8)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(
            set(ids),
            {
                "scan.maximum_input_bytes",
                "scan.maximum_diagnostics",
                "scan.maximum_total_allocated_bytes",
                "traversal.maximum_metadata_open_attempts",
                "script.maximum_heap_bytes",
                "script.maximum_stack_bytes",
                "script.maximum_instruction_or_fuel",
                "script.runtime_deadline",
            },
        )
        self.assertEqual(
            self.policy["result"],
            "review_candidate_incomplete",
        )
        self.assertFalse(self.policy["decision_status"]["admitted"])
        self.assertIn(
            "ADRs 0010, 0012, and 0014 remain Proposed",
            self.policy["decision_status"]["reason"],
        )

    def test_report_or_contract_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in self.builder.SOURCES.values():
                destination = root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, destination)

            report_path = (
                root / self.builder.SOURCES["archive_iteration"]
            )
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["assertions"]["record_100001_is_not_reachable"] = False
            report_path.write_text(
                json.dumps(report, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                self.builder.PolicyError,
                "archive iteration assertions drift",
            ):
                self.builder.build_policy(root)

            shutil.copy2(
                ROOT / self.builder.SOURCES["archive_iteration"],
                report_path,
            )
            adr_path = root / self.builder.SOURCES["adr_scan"]
            adr_path.write_text(
                adr_path.read_text(encoding="utf-8").replace(
                    "| maximum nested depth | 32 |",
                    "| maximum nested depth | 33 |",
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                self.builder.PolicyError,
                "contract drift",
            ):
                self.builder.build_policy(root)

    def test_docs_preserve_evidence_design_and_review_boundaries(self):
        research = (
            ROOT / "docs/research/resource-limit-evidence.md"
        ).read_text(encoding="utf-8")
        design = (
            ROOT / "docs/design/resource-limit-policy.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Status: In Review", research)
        self.assertIn(
            f"Upstream: `horsicq/DIE-engine@{self.builder.UPSTREAM_COMMIT}`",
            research,
        )
        self.assertIn("Status: In Review", design)
        self.assertIn("review_candidate_incomplete", design)
        self.assertIn("`admitted=false`", design)
        self.assertIn("8 个明确 unresolved 项", design)
        self.assertIn("production_default_candidate=false", research)
        self.assertIn("不是已冻结的发布", design)
        self.assertIn("不是生产默认候选", research)

        gate = json.loads(
            (
                ROOT / "docs/design/data/phase-0-gate-review.json"
            ).read_text(encoding="utf-8")
        )
        blocker = next(
            item
            for item in gate["blockers"]
            if item["id"] == "P0-BLOCK-006"
        )
        self.assertEqual(blocker["status"], "open")
        self.assertEqual(
            blocker["resource_limit_policy_status"],
            (
                "review_candidate_incomplete_and_unadmitted_"
                "with_8_unresolved_budgets"
            ),
        )
        self.assertEqual(
            blocker["resource_limit_policy_evidence"],
            [
                "docs/research/resource-limit-evidence.md",
                "docs/research/include-graph-sizing.md",
                "docs/research/data/include-graph-sizing.json",
                "docs/research/database-load-sizing.md",
                "docs/research/data/database-load-sizing.json",
                "docs/design/resource-limit-policy.md",
                (
                    "docs/design/data/"
                    "resource-limit-policy-candidate.json"
                ),
            ],
        )


if __name__ == "__main__":
    unittest.main()
