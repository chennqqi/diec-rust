import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = ROOT / "docs" / "design" / "data" / "adr-review-readiness.json"
GATE_PATH = ROOT / "docs" / "design" / "data" / "phase-0-gate-review.json"


class AdrReviewReadinessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        cls.gate = json.loads(GATE_PATH.read_text(encoding="utf-8"))

    def test_active_and_excluded_adr_sets_are_exact(self):
        adrs = self.report["adrs"]
        self.assertEqual(
            {adr["id"] for adr in adrs},
            {
                "ADR-0001",
                "ADR-0002",
                "ADR-0003",
                "ADR-0004",
                "ADR-0005",
                "ADR-0006",
                "ADR-0008",
                "ADR-0009",
                "ADR-0010",
                "ADR-0011",
                "ADR-0012",
                "ADR-0013",
                "ADR-0014",
                "ADR-0015",
            },
        )
        self.assertEqual(
            self.report["excluded_adrs"],
            [
                {
                    "id": "ADR-0007",
                    "path": (
                        "docs/design/decisions/"
                        "0007-rust-toolchain-baseline.md"
                    ),
                    "status": "Superseded",
                    "reason": (
                        "default toolchain decision is replaced by ADR 0011"
                    ),
                }
            ],
        )

    def test_every_active_adr_is_review_ready_not_acceptance_ready(self):
        for adr in self.report["adrs"]:
            path = ROOT / adr["path"]
            with self.subTest(adr=adr["id"]):
                self.assertTrue(path.is_file())
                text = path.read_text(encoding="utf-8")
                self.assertRegex(
                    text,
                    rf"(?m)^Status: {re.escape(adr['status'])}\s*$",
                )
                self.assertEqual(adr["status"], "Proposed")
                self.assertTrue(adr["review_ready"])
                self.assertFalse(adr["acceptance_ready"])
                self.assertTrue(adr["review_question"])
                self.assertTrue(adr["remaining_acceptance_evidence"])
                for heading in adr["required_headings"]:
                    self.assertIn(heading, text)
                for contract_test in adr["contract_tests"]:
                    self.assertTrue((ROOT / contract_test).is_file())

    def test_excluded_adr_status_matches_document(self):
        excluded = self.report["excluded_adrs"][0]
        text = (ROOT / excluded["path"]).read_text(encoding="utf-8")
        self.assertRegex(
            text,
            rf"(?m)^Status: {re.escape(excluded['status'])}\s*$",
        )

    def test_summary_is_derived_and_keeps_decision_gate_open(self):
        adrs = self.report["adrs"]
        summary = self.report["summary"]
        self.assertEqual(summary["active_adr_count"], len(adrs))
        self.assertEqual(
            summary["review_ready_count"],
            sum(adr["review_ready"] for adr in adrs),
        )
        self.assertEqual(
            summary["acceptance_ready_count"],
            sum(adr["acceptance_ready"] for adr in adrs),
        )
        self.assertEqual(
            summary["proposed_count"],
            sum(adr["status"] == "Proposed" for adr in adrs),
        )
        self.assertEqual(
            summary["superseded_count"],
            len(self.report["excluded_adrs"]),
        )
        self.assertFalse(summary["phase_0_decision_gate_complete"])
        self.assertEqual(self.report["result"], "review_pending")
        self.assertEqual(self.gate["result"], "not_ready")


if __name__ == "__main__":
    unittest.main()
