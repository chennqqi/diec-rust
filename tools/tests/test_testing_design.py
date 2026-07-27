from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
TESTING = ROOT / "docs" / "design" / "testing.md"
ADR = ROOT / "docs" / "design" / "decisions" / "0004-evidence-bound-difference-waivers.md"


class TestingDesignTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.testing = TESTING.read_text(encoding="utf-8")
        cls.adr = ADR.read_text(encoding="utf-8")

    def test_document_is_draft_and_evidence_backed(self) -> None:
        self.assertIn("Status: In Review", self.testing)
        for evidence in (
            "upstream-baseline.md",
            "upstream-build-baseline.md",
            "upstream-cmake-differential.md",
            "behavior-baseline.md",
            "nested-scan-behavior.md",
            "rule-compatibility.md",
            "c-static-link-spike.md",
            "architecture.md",
            "api.md",
            "c-abi.md",
        ):
            self.assertIn(evidence, self.testing)

    def test_case_and_raw_evidence_are_content_addressed(self) -> None:
        for contract in (
            "ID 全局唯一",
            "argv 是数组",
            "stdout/stderr 是 byte stream",
            "SHA-256",
            "原始记录永不修改",
            "normalizer 名称、版本和",
            "输入/输出 hash",
        ):
            self.assertIn(contract, self.testing)

    def test_differential_compares_semantics_and_order(self) -> None:
        for contract in (
            "逐字节比较 stdout 和 stderr",
            "parent/child、file-part、offset、size 和 child order",
            "数组默认有序比较",
            "不能用“排序后相同”隐藏上游优先级差异",
            "oracle crash、timeout 或",
            "`ORACLE_ERROR`",
        ):
            self.assertIn(contract, self.testing)

    def test_waivers_are_precise_and_default_deny(self) -> None:
        for contract in (
            "未匹配差异默认失败",
            "不允许 `*` case",
            "原始两侧 hash/diff fingerprint",
            "expired、unmatched 或意外不再需要的 waiver",
            "永远不可 waiver",
        ):
            self.assertIn(contract, self.testing)
        self.assertIn("Status: Proposed", self.adr)
        self.assertIn("wildcard case", self.adr)
        self.assertIn("差异扩大后失败", self.adr)

    def test_required_test_families_exist(self) -> None:
        for heading in (
            "## 12. Unit、property 与 integration",
            "## 13. Rule conformance",
            "## 14. Fuzz 设计",
            "## 15. FFI 与语言集成",
            "## 16. 性能与资源 benchmark",
            "## 17. CI 矩阵",
        ):
            self.assertIn(heading, self.testing)
        for language in ("C 编译/链接/执行", "Go 运行 cgo", "Python 测试 CPython"):
            self.assertIn(language, self.testing)

    def test_security_failures_cannot_be_waived(self) -> None:
        for failure in (
            "panic",
            "data race",
            "hang",
            "unbounded allocation",
            "silent",
            "ABI UB",
        ):
            self.assertIn(failure, self.adr)

    def test_phase_gates_and_traceability_are_measurable(self) -> None:
        for phase in ("### Phase 1", "### Phase 2", "### Phase 3", "### Phase 4", "### Phase 5", "### Phase 6/release"):
            self.assertIn(phase, self.testing)
        self.assertIn("100% discovered/parsed/loaded", self.testing)
        self.assertIn("100% traceable", self.testing)
        self.assertIn("无 unmatched/expired/stale waiver", self.testing)

    def test_adr_has_required_sections(self) -> None:
        for heading in (
            "## Context",
            "## Decision",
            "## Alternatives considered",
            "## Consequences",
            "## Evidence",
            "## Acceptance conditions",
        ):
            self.assertIn(heading, self.adr)


if __name__ == "__main__":
    unittest.main()
