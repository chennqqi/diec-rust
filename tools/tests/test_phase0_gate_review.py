import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = ROOT / "docs" / "design" / "data" / "phase-0-gate-review.json"
DOCUMENT_PATH = ROOT / "docs" / "design" / "phase-0-gate-review.md"
ROADMAP_PATH = ROOT / "ROADMAP.md"


class PhaseZeroGateReviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        cls.document = DOCUMENT_PATH.read_text(encoding="utf-8")
        cls.roadmap = ROADMAP_PATH.read_text(encoding="utf-8")

    def test_gate_is_explicitly_not_ready(self) -> None:
        self.assertEqual(self.report["schema_version"], 1)
        self.assertEqual(self.report["phase"], 0)
        self.assertEqual(self.report["result"], "not_ready")
        self.assertEqual(self.report["roadmap_status"], "IN PROGRESS")
        self.assertIn(
            "## Phase 0：上游调研与设计门禁 — IN PROGRESS",
            self.roadmap,
        )
        self.assertNotIn(
            "## Phase 0：上游调研与设计门禁 — DONE",
            self.roadmap,
        )

    def test_required_deliverable_sets_are_complete_and_statuses_match(self):
        expected_research = {
            "docs/research/upstream-baseline.md",
            "docs/research/capability-matrix.md",
            "docs/research/source-analysis.md",
            "docs/research/rule-compatibility.md",
            "docs/research/behavior-baseline.md",
        }
        expected_design = {
            "docs/design/architecture.md",
            "docs/design/api.md",
            "docs/design/c-abi.md",
            "docs/design/testing.md",
            "docs/design/risks.md",
        }
        for field, expected in (
            ("required_research_deliverables", expected_research),
            ("required_design_deliverables", expected_design),
        ):
            entries = self.report[field]
            self.assertEqual({entry["path"] for entry in entries}, expected)
            self.assertEqual(
                len({entry["id"] for entry in entries}),
                len(entries),
            )
            for entry in entries:
                path = ROOT / entry["path"]
                with self.subTest(path=entry["path"]):
                    self.assertTrue(path.is_file())
                    front_matter = path.read_text(encoding="utf-8")
                    self.assertRegex(
                        front_matter,
                        rf"(?m)^Status: {re.escape(entry['document_status'])}\s*$",
                    )
                    self.assertIn(
                        entry["gate_status"],
                        {"review_pending", "evidence_incomplete"},
                    )
                    if field == "required_design_deliverables":
                        self.assertIn(
                            f"[`{entry['path']}`]({entry['path']}) — "
                            f"{entry['document_status']}",
                            self.roadmap,
                        )

    def test_three_technical_validations_have_existing_evidence(self):
        validations = self.report["technical_validations"]
        self.assertEqual(
            {validation["id"] for validation in validations},
            {"P0-SPIKE-001", "P0-SPIKE-002", "P0-SPIKE-003"},
        )
        self.assertEqual(
            {validation["name"] for validation in validations},
            {"rule_runtime", "c_static_link", "upstream_oracle"},
        )
        for validation in validations:
            self.assertEqual(validation["gate_status"], "evidence_available")
            self.assertTrue(validation["limitation"])
            for evidence in validation["evidence"]:
                with self.subTest(evidence=evidence):
                    self.assertTrue((ROOT / evidence).is_file())

    def test_exit_conditions_and_blockers_are_closed_sets(self):
        exit_conditions = self.report["exit_conditions"]
        blockers = self.report["blockers"]
        blocker_ids = {blocker["id"] for blocker in blockers}
        self.assertEqual(
            {condition["id"] for condition in exit_conditions},
            {f"P0-EXIT-{index:03d}" for index in range(1, 8)},
        )
        self.assertEqual(
            blocker_ids,
            {f"P0-BLOCK-{index:03d}" for index in range(1, 7)},
        )
        self.assertEqual(len(blocker_ids), len(blockers))
        open_blocker_ids = {
            blocker["id"]
            for blocker in blockers
            if blocker["status"] == "open"
        }
        referenced_blockers = {
            blocker
            for condition in exit_conditions
            for blocker in condition["blockers"]
        }
        self.assertEqual(referenced_blockers, open_blocker_ids)
        self.assertEqual(
            {
                blocker["id"]
                for blocker in blockers
                if blocker["status"] == "closed"
            },
            {"P0-BLOCK-001"},
        )
        for condition in exit_conditions:
            self.assertIn(
                condition["status"],
                {"not_ready", "ready_for_review"},
            )
            if condition["status"] == "not_ready":
                self.assertTrue(condition["blockers"])
        for blocker in blockers:
            self.assertTrue(blocker["owner"])
            self.assertIn(blocker["status"], {"open", "closed"})
            self.assertTrue(blocker["closure_evidence"])
            self.assertIn(blocker["id"], self.document)

    def test_active_proposed_adr_count_is_not_silently_changed(self):
        decisions = ROOT / "docs" / "design" / "decisions"
        statuses = {}
        for path in decisions.glob("*.md"):
            match = re.search(
                r"(?m)^Status: (Proposed|Accepted|Rejected|Superseded)\s*$",
                path.read_text(encoding="utf-8"),
            )
            if match:
                statuses[path.name] = match.group(1)
        proposed = {path for path, status in statuses.items() if status == "Proposed"}
        self.assertEqual(
            proposed,
            {
                "0001-c-abi-opaque-ownership.md",
                "0002-layered-workspace.md",
                "0003-dual-output-contract.md",
                "0004-evidence-bound-difference-waivers.md",
                "0005-deterministic-text-classification.md",
                "0006-rquickjs-rule-runtime.md",
                "0008-pinned-rule-order-manifest.md",
                "0009-cancellation-result-contract.md",
                "0010-bounded-include-graph.md",
                "0011-rust-1.97.1-default-toolchain.md",
                "0012-bounded-nested-scan-budget.md",
                "0013-fail-closed-incomplete-input.md",
            },
        )
        self.assertIn("十二个有效 ADR", self.document)


if __name__ == "__main__":
    unittest.main()
