from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
ADR_PATH = (
    ROOT
    / "docs"
    / "design"
    / "decisions"
    / "0014-bounded-path-expansion.md"
)
API_PATH = ROOT / "docs" / "design" / "api.md"
RISKS_PATH = ROOT / "docs" / "design" / "risks.md"
EVIDENCE_PATH = ROOT / "docs" / "research" / "path-filesystem-behavior.md"


class PathExpansionDesignTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.adr = ADR_PATH.read_text(encoding="utf-8")
        cls.api = API_PATH.read_text(encoding="utf-8")
        cls.risks = RISKS_PATH.read_text(encoding="utf-8")
        cls.evidence = EVIDENCE_PATH.read_text(encoding="utf-8")

    def test_adr_is_proposed_and_has_review_sections(self) -> None:
        self.assertIn("Status: Proposed", self.adr)
        for heading in (
            "## 背景",
            "## 决策",
            "## 考虑过的替代方案",
            "## 后果",
            "## 证据",
            "## 验收条件",
        ):
            self.assertIn(heading, self.adr)

    def test_profiles_keep_legacy_aliases_separate_from_safe_default(self) -> None:
        for token in (
            "`LegacyCompatible`",
            "`SafeCanonical`",
            "非循环 alias 重复",
            "默认跳过所有发现的 symlink/junction/reparse point",
            "`SafetyDeviation`",
        ):
            self.assertIn(token, self.adr)
        self.assertIn("TraversalProfile", self.api)
        self.assertIn("LegacyCompatible", self.api)
        self.assertIn("SafeCanonical", self.api)

    def test_cycle_detection_does_not_use_global_dedup_or_os_limit(self) -> None:
        for token in (
            "ancestry",
            "stable identity",
            "不把全局已见 identity 当作去重集合",
            "`CycleDetected`",
            "不会复刻 41 次",
        ):
            self.assertIn(token, self.adr)
        self.assertIn("self-cycle", self.evidence)
        self.assertIn("41", self.evidence)

    def test_traversal_is_bounded_before_metadata_or_queue_work(self) -> None:
        for budget in (
            "`max_directory_depth`",
            "`max_entries_considered`",
            "`max_files_emitted`",
            "`max_total_path_bytes`",
            "deadline",
            "cancellation",
        ):
            self.assertIn(budget, self.adr)
        self.assertIn("metadata、分配 path 或入队前 reserve", self.adr)
        self.assertIn("child 不重置额度", self.adr)

    def test_toctou_and_permission_are_typed_not_silent(self) -> None:
        for token in (
            "handle-relative",
            "`ChangedDuringTraversal`",
            "`UnsupportedSafetyGuarantee`",
            "permission denied",
            "合法 empty directory",
        ):
            self.assertIn(token, self.adr)
        self.assertIn("ADR 0014", self.risks)
        self.assertIn("TOCTOU", self.risks)


if __name__ == "__main__":
    unittest.main()
