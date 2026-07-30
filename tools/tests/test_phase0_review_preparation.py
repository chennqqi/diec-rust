"""Verify Phase 0 review preparation document structure and referenced evidence."""

from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
DOCUMENT_PATH = ROOT / "docs" / "design" / "phase-0-review-preparation.md"


class PhaseZeroReviewPreparationTest(unittest.TestCase):
    """Ensure the review preparation summary stays structurally consistent."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.document = DOCUMENT_PATH.read_text(encoding="utf-8")

    def test_document_exists_and_has_draft_status(self) -> None:
        self.assertRegex(
            self.document,
            r"(?m)^Status: Draft\s*$",
        )

    def test_covers_three_windows_doable_blockers(self) -> None:
        for blocker_id in ("P0-BLOCK-004", "P0-BLOCK-002/003", "P0-BLOCK-006"):
            with self.subTest(blocker=blocker_id):
                self.assertIn(blocker_id, self.document)

    def test_excludes_macos_blocker_from_scope(self) -> None:
        self.assertIn("P0-BLOCK-005", self.document)
        self.assertIn("Darwin", self.document)

    def test_referenced_research_documents_exist(self) -> None:
        referenced = re.findall(r"`([a-z][a-z0-9-]*\.md)`", self.document)
        for name in referenced:
            path = ROOT / "docs" / "research" / name
            if path.suffix == ".md" and not path.exists():
                path = ROOT / "docs" / "design" / name
            with self.subTest(name=name):
                self.assertTrue(
                    path.exists(),
                    f"Referenced document not found: {name}",
                )

    def test_license_section_lists_remaining_gaps(self) -> None:
        self.assertIn("XUCL", self.document)
        self.assertIn("RAR", self.document)
        self.assertIn("Brotli", self.document)
        self.assertIn("SBOM", self.document)

    def test_design_adr_section_references_correct_counts(self) -> None:
        self.assertIn("14", self.document)
        self.assertIn("review_ready", self.document)
        self.assertIn("acceptance_ready", self.document)

    def test_performance_section_references_cache_model(self) -> None:
        self.assertIn("warm", self.document)
        self.assertIn("system-cold", self.document)
        self.assertIn("limit", self.document)


if __name__ == "__main__":
    unittest.main()
