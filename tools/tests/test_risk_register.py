from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
RISKS = ROOT / "docs" / "design" / "risks.md"


class RiskRegisterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.risks = RISKS.read_text(encoding="utf-8")

    def test_register_is_draft_and_links_design_evidence(self) -> None:
        self.assertIn("Status: Draft", self.risks)
        for evidence in (
            "architecture.md",
            "api.md",
            "c-abi.md",
            "testing.md",
            "rule-compatibility.md",
            "rule-runtime-spike.md",
            "rquickjs-rule-runtime-spike.md",
            "nested-scan-behavior.md",
            "cli-dependency-and-license.md",
        ):
            self.assertIn(evidence, self.risks)

    def test_ids_are_unique_and_have_detail_sections(self) -> None:
        overview_ids = re.findall(r"^\| (R-\d{3}) \|", self.risks, re.MULTILINE)
        detail_ids = re.findall(r"^### (R-\d{3})：", self.risks, re.MULTILINE)
        self.assertEqual(20, len(overview_ids))
        self.assertEqual(len(overview_ids), len(set(overview_ids)))
        self.assertEqual(overview_ids, detail_ids)

    def test_all_overview_risks_have_governance_fields(self) -> None:
        for line in self.risks.splitlines():
            if re.match(r"^\| R-\d{3} \|", line):
                cells = [cell.strip() for cell in line.strip("|").split("|")]
                self.assertEqual(7, len(cells), line)
                self.assertIn(cells[2], {"Critical", "High", "Medium", "Low"})
                self.assertIn(cells[3], {"Likely", "Possible", "Unlikely"})
                self.assertIn(cells[5], {"Open", "Mitigating", "Accepted", "Closed"})
                self.assertTrue(cells[4], line)
                self.assertTrue(cells[6], line)

    def test_critical_domains_are_covered(self) -> None:
        for domain in (
            "规则 runtime",
            "许可证",
            "畸形二进制",
            "解压炸弹",
            "static link",
            "C ABI",
            "跨平台",
            "数据竞争",
            "upstream subtree",
            "供应链",
            "取消/timeout",
            "symlink/junction",
            "waiver",
        ):
            self.assertIn(domain, self.risks)

    def test_each_detail_has_trigger_mitigation_and_verification(self) -> None:
        sections = re.split(r"^### R-\d{3}：", self.risks, flags=re.MULTILINE)[1:]
        self.assertEqual(20, len(sections))
        for section in sections:
            self.assertIn("**触发**", section)
            self.assertRegex(section, r"\*\*(当前)?缓解\*\*")
            self.assertIn("**验证**", section)
            self.assertIn("**关闭**", section)

    def test_phase_zero_gate_does_not_claim_risks_are_closed(self) -> None:
        self.assertIn("Phase 0 不要求所有实现期风险 Closed", self.risks)
        self.assertIn("不能接受缺少关闭路径或验证证据的风险", self.risks)
        self.assertIn("R-001 + R-015", self.risks)


if __name__ == "__main__":
    unittest.main()
