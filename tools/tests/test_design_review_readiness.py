import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = (
    ROOT / "docs" / "design" / "data" / "design-review-readiness.json"
)
GATE_PATH = ROOT / "docs" / "design" / "data" / "phase-0-gate-review.json"
ROADMAP_PATH = ROOT / "ROADMAP.md"


class DesignReviewReadinessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        cls.gate = json.loads(GATE_PATH.read_text(encoding="utf-8"))
        cls.roadmap = ROADMAP_PATH.read_text(encoding="utf-8")

    def test_required_design_document_set_is_exact(self):
        documents = self.report["documents"]
        self.assertEqual(
            {document["id"] for document in documents},
            {
                "DESIGN-ARCHITECTURE",
                "DESIGN-API",
                "DESIGN-C-ABI",
                "DESIGN-TESTING",
                "DESIGN-RISKS",
            },
        )
        self.assertEqual(
            {document["path"] for document in documents},
            {
                "docs/design/architecture.md",
                "docs/design/api.md",
                "docs/design/c-abi.md",
                "docs/design/testing.md",
                "docs/design/risks.md",
            },
        )

    def test_every_document_is_review_ready_but_not_acceptance_ready(self):
        for document in self.report["documents"]:
            path = ROOT / document["path"]
            contract_test = ROOT / document["contract_test"]
            with self.subTest(document=document["id"]):
                self.assertTrue(path.is_file())
                self.assertTrue(contract_test.is_file())
                text = path.read_text(encoding="utf-8")
                self.assertRegex(
                    text,
                    rf"(?m)^Status: {re.escape(document['document_status'])}\s*$",
                )
                self.assertEqual(document["document_status"], "In Review")
                self.assertTrue(document["review_ready"])
                self.assertFalse(document["acceptance_ready"])
                self.assertTrue(document["blocking_items"])
                for heading in document["required_headings"]:
                    self.assertIn(heading, text)

    def test_summary_is_derived_from_documents(self):
        documents = self.report["documents"]
        summary = self.report["summary"]
        self.assertEqual(summary["document_count"], len(documents))
        self.assertEqual(
            summary["review_ready_count"],
            sum(document["review_ready"] for document in documents),
        )
        self.assertEqual(
            summary["acceptance_ready_count"],
            sum(document["acceptance_ready"] for document in documents),
        )
        self.assertTrue(summary["all_in_review"])
        self.assertFalse(summary["phase_0_authorized_to_exit"])
        self.assertEqual(self.report["result"], "review_pending")

    def test_phase_zero_remains_not_ready_and_in_progress(self):
        self.assertEqual(self.gate["result"], "not_ready")
        self.assertIn(
            "## Phase 0：上游调研与设计门禁 — IN PROGRESS",
            self.roadmap,
        )
        self.assertNotIn(
            "## Phase 0：上游调研与设计门禁 — DONE",
            self.roadmap,
        )


if __name__ == "__main__":
    unittest.main()
