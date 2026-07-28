import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "research" / "build_qt6_closure_plan.py"
MANIFEST = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "qt6-capability-closure-plan.json"
)
SPEC = importlib.util.spec_from_file_location("build_qt6_closure_plan", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class Qt6CapabilityClosurePlanTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.traceability, cls.traceability_raw = MODULE.load_json(
            ROOT / MODULE.TRACEABILITY_PATH
        )
        cls.reports = {}
        cls.report_bytes = {}
        for relative_path in MODULE.REPORT_PATHS:
            (
                cls.reports[relative_path],
                cls.report_bytes[relative_path],
            ) = MODULE.load_json(ROOT / relative_path)
        cls.plan = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_committed_plan_is_exact_generator_output(self):
        expected = MODULE.build_plan(
            self.traceability,
            self.traceability_raw,
            self.reports,
            self.report_bytes,
        )
        self.assertEqual(self.plan, expected)
        self.assertEqual(MANIFEST.read_bytes(), MODULE.serialize(expected))

    def test_plan_accounts_for_exactly_all_68_capabilities(self):
        expected_ids = {
            item["id"] for item in self.traceability["capabilities"]
        }
        rows = self.plan["rows"]
        self.assertEqual(len(rows), 68)
        self.assertEqual({row["id"] for row in rows}, expected_ids)
        self.assertEqual(
            self.plan["summary"]["capability_count"],
            68,
        )
        self.assertTrue(
            self.plan["summary"]["all_capabilities_accounted_for"]
        )

    def test_incomplete_rows_have_executable_closure_contracts(self):
        for row in self.plan["rows"]:
            with self.subTest(capability=row["id"]):
                self.assertIn(
                    row["status"],
                    {"evidence_complete", "partial", "missing"},
                )
                self.assertTrue(row["acceptance"])
                if row["status"] == "evidence_complete":
                    self.assertIsNone(row["missing_scope"])
                    self.assertIsNone(row["proposed_experiment"])
                    self.assertTrue(row["observed_scope"])
                else:
                    self.assertTrue(row["missing_scope"])
                    experiment = row["proposed_experiment"]
                    self.assertTrue(experiment["fixture"])
                    self.assertTrue(experiment["harness"])
                    self.assertGreaterEqual(len(experiment["assertions"]), 3)

    def test_current_plan_is_conservatively_incomplete(self):
        summary = self.plan["summary"]
        self.assertEqual(summary["evidence_complete"], 19)
        self.assertEqual(summary["partial"], 10)
        self.assertEqual(summary["missing"], 39)
        self.assertEqual(summary["closure_required"], 49)
        self.assertFalse(summary["cap_gap_007_closed"])
        self.assertEqual(self.plan["result"], "incomplete")

    def test_cli_output_and_dispatch_promotions_are_exact(self):
        rows = {row["id"]: row for row in self.plan["rows"]}
        promoted = {
            "CAP-CLI-OUT-001",
            "CAP-CLI-OUT-003",
            "CAP-CLI-OUT-004",
            "CAP-CLI-OUT-005",
            "CAP-DISPATCH-001",
            "CAP-DISPATCH-005",
            "CAP-DISPATCH-007",
            "CAP-NEST-008",
        }
        for capability_id in promoted:
            with self.subTest(capability=capability_id):
                self.assertEqual(
                    rows[capability_id]["status"],
                    "evidence_complete",
                )
        self.assertEqual(
            rows["CAP-DISPATCH-004"]["status"],
            "partial",
        )

    def test_pinned_identity_and_duplicate_keys_are_enforced(self):
        changed = json.loads(json.dumps(self.traceability))
        changed["upstream_commit"] = "0" * 40
        with self.assertRaisesRegex(
            MODULE.ClosurePlanError,
            "upstream commit drift",
        ):
            MODULE.build_plan(
                changed,
                self.traceability_raw,
                self.reports,
                self.report_bytes,
            )

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"schema_version":1,"schema_version":1}')
            with self.assertRaisesRegex(
                MODULE.ClosurePlanError,
                "duplicate JSON key",
            ):
                MODULE.load_json(path)

    def test_semantic_or_warning_drift_is_rejected(self):
        changed_reports = json.loads(json.dumps(self.reports))
        output_matrix = changed_reports[MODULE.REPORT_PATHS[5]]
        output_matrix["matrix"]["empty.bin"]["output"]["xml"]["right"][
            "stdout_sha256"
        ] = "0" * 64
        with self.assertRaisesRegex(
            MODULE.ClosurePlanError,
            "semantic difference",
        ):
            MODULE.build_plan(
                self.traceability,
                self.traceability_raw,
                changed_reports,
                self.report_bytes,
            )

        changed_reports = json.loads(json.dumps(self.reports))
        output_boundary = changed_reports[MODULE.REPORT_PATHS[4]]
        nested_json = next(
            case
            for case in output_boundary["cases"]
            if case["id"] == "nested_json"
        )
        nested_json["right"]["stderr_sha256"] = "0" * 64
        with self.assertRaisesRegex(
            MODULE.ClosurePlanError,
            "unexpected nested formatter difference",
        ):
            MODULE.build_plan(
                self.traceability,
                self.traceability_raw,
                changed_reports,
                self.report_bytes,
            )


if __name__ == "__main__":
    unittest.main()
