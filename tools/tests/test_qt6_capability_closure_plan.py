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
        self.assertEqual(summary["evidence_complete"], 62)
        self.assertEqual(summary["partial"], 2)
        self.assertEqual(summary["missing"], 4)
        self.assertEqual(summary["closure_required"], 6)
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
            "CAP-CLI-OPT-001",
            "CAP-CLI-OPT-002",
            "CAP-CLI-OPT-003",
            "CAP-CLI-OPT-005",
            "CAP-CLI-OPT-006",
            "CAP-CLI-OPT-007",
            "CAP-CLI-OPT-010",
            "CAP-NEST-002",
            "CAP-NEST-005",
            "CAP-CLI-MODE-001",
            "CAP-CLI-MODE-002",
            "CAP-CLI-MODE-003",
            "CAP-CLI-IN-002",
            "CAP-CLI-IN-004",
            "CAP-NEST-001",
            "CAP-CLI-OPT-009",
            "CAP-RULE-008",
            "CAP-RULE-010",
            "CAP-CLI-OPT-004",
            "CAP-CLI-OPT-008",
            "CAP-CLI-TEST-001",
            "CAP-CLI-TEST-002",
            "CAP-RULE-011",
            "CAP-ENG-IN-001",
            "CAP-ENG-IN-002",
            "CAP-RULE-006",
            "CAP-RULE-009",
            "CAP-RULE-012",
            "CAP-RULE-001",
            "CAP-RULE-002",
            "CAP-RULE-003",
            "CAP-RULE-004",
            "CAP-RULE-005",
            "CAP-RESULT-001",
            "CAP-RESULT-002",
            "CAP-RESULT-003",
            "CAP-RESULT-004",
            "CAP-RESULT-005",
            "CAP-RESULT-006",
            "CAP-RULE-007",
            "CAP-NEST-007",
            "CAP-NEST-006",
            "CAP-NEST-003",
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
        self.assertEqual(rows["CAP-CLI-IN-003"]["status"], "partial")
        self.assertEqual(
            rows["CAP-NEST-003"]["status"],
            "evidence_complete",
        )
        self.assertEqual(
            rows["CAP-RULE-005"]["status"],
            "evidence_complete",
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

        changed_reports = json.loads(json.dumps(self.reports))
        diagnostics = changed_reports[MODULE.REPORT_PATHS[7]]
        diagnostics["cases"]["alltypes"]["observations"]["qt6"][0][
            "normalized_diagnostics"
        ] = "silently changed"
        with self.assertRaisesRegex(
            MODULE.ClosurePlanError,
            "unexpected Qt6 alltypes diagnostic",
        ):
            MODULE.build_plan(
                self.traceability,
                self.traceability_raw,
                changed_reports,
                self.report_bytes,
            )

        changed_reports = json.loads(json.dumps(self.reports))
        special = changed_reports[MODULE.REPORT_PATHS[9]]
        special["cases"]["entropy_exact_json"][
            "all_oracles_equal"
        ] = False
        with self.assertRaisesRegex(
            MODULE.ClosurePlanError,
            "oracle difference",
        ):
            MODULE.build_plan(
                self.traceability,
                self.traceability_raw,
                changed_reports,
                self.report_bytes,
            )

        changed_reports = json.loads(json.dumps(self.reports))
        path_matrix = changed_reports[MODULE.REPORT_PATHS[10]]
        path_matrix["path_corpus"]["cases"]["two_files_json"][
            "right_filename_prefixes"
        ] = ["changed"]
        with self.assertRaisesRegex(
            MODULE.ClosurePlanError,
            "path prefix difference",
        ):
            MODULE.build_plan(
                self.traceability,
                self.traceability_raw,
                changed_reports,
                self.report_bytes,
            )

        changed_reports = json.loads(json.dumps(self.reports))
        database_diagnostics = changed_reports[MODULE.REPORT_PATHS[12]]
        database_diagnostics["cases"]["malformed"]["observations"][
            "qt6"
        ][0]["diagnostics"] = "changed"
        with self.assertRaisesRegex(
            MODULE.ClosurePlanError,
            "semantic drift",
        ):
            MODULE.build_plan(
                self.traceability,
                self.traceability_raw,
                changed_reports,
                self.report_bytes,
            )

        changed_reports = json.loads(json.dumps(self.reports))
        profiling = changed_reports[MODULE.REPORT_PATHS[14]]
        profiling["order"] = list(reversed(profiling["order"]))
        with self.assertRaisesRegex(
            MODULE.ClosurePlanError,
            "order hash drift",
        ):
            MODULE.build_plan(
                self.traceability,
                self.traceability_raw,
                changed_reports,
                self.report_bytes,
            )

        changed_reports = json.loads(json.dumps(self.reports))
        engine = changed_reports[MODULE.REPORT_PATHS[16]]
        engine["relationships"][
            "entry_points_are_semantically_equal"
        ] = False
        with self.assertRaisesRegex(
            MODULE.ClosurePlanError,
            "relationship drift",
        ):
            MODULE.build_plan(
                self.traceability,
                self.traceability_raw,
                changed_reports,
                self.report_bytes,
            )

        changed_reports = json.loads(json.dumps(self.reports))
        orchestration = changed_reports[MODULE.REPORT_PATHS[18]]
        orchestration["canonical_cases"]["combined"][
            "execution_order"
        ] = []
        with self.assertRaisesRegex(
            MODULE.ClosurePlanError,
            "canonical case drift",
        ):
            MODULE.build_plan(
                self.traceability,
                self.traceability_raw,
                changed_reports,
                self.report_bytes,
            )

        changed_reports = json.loads(json.dumps(self.reports))
        result_model = changed_reports[MODULE.REPORT_PATHS[26]]
        result_model["reports"]["flags"]["harness_output"]["cases"][0][
            "records"
        ][0]["unknown"] = True
        with self.assertRaisesRegex(
            MODULE.ClosurePlanError,
            "comparison drift",
        ):
            MODULE.build_plan(
                self.traceability,
                self.traceability_raw,
                changed_reports,
                self.report_bytes,
            )

        changed_reports = json.loads(json.dumps(self.reports))
        signature_path = changed_reports[MODULE.REPORT_PATHS[28]]
        signature_path["harness_output"]["cases"][0][
            "record_count"
        ] = 99
        with self.assertRaisesRegex(
            MODULE.ClosurePlanError,
            "output drift",
        ):
            MODULE.build_plan(
                self.traceability,
                self.traceability_raw,
                changed_reports,
                self.report_bytes,
            )

        changed_reports = json.loads(json.dumps(self.reports))
        archive_option = changed_reports[MODULE.REPORT_PATHS[33]]
        archive_option["cases"]["pdf-member.zip"]["archive"][
            "observations"
        ]["qt6"]["stdout_sha256"] = "0" * 64
        with self.assertRaisesRegex(
            MODULE.ClosurePlanError,
            "observation drift",
        ):
            MODULE.build_plan(
                self.traceability,
                self.traceability_raw,
                changed_reports,
                self.report_bytes,
            )

        changed_reports = json.loads(json.dumps(self.reports))
        debug_dispatch = changed_reports[MODULE.REPORT_PATHS[30]]
        debug_dispatch["known_difference"]["lines"] = 3
        with self.assertRaisesRegex(
            MODULE.ClosurePlanError,
            "relationship drift",
        ):
            MODULE.build_plan(
                self.traceability,
                self.traceability_raw,
                changed_reports,
                self.report_bytes,
            )

        changed_reports = json.loads(json.dumps(self.reports))
        resource_context = changed_reports[MODULE.REPORT_PATHS[32]]
        resource_context["cases"]["recursive_aggressive"][
            "raw_stdout"
        ] = "silently changed"
        with self.assertRaisesRegex(
            MODULE.ClosurePlanError,
            "output drift",
        ):
            MODULE.build_plan(
                self.traceability,
                self.traceability_raw,
                changed_reports,
                self.report_bytes,
            )


if __name__ == "__main__":
    unittest.main()
