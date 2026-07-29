from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
API = ROOT / "docs" / "design" / "api.md"
ADR = ROOT / "docs" / "design" / "decisions" / "0003-dual-output-contract.md"
C_ABI = ROOT / "docs" / "design" / "c-abi.md"


class ApiDesignTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.api = API.read_text(encoding="utf-8")
        cls.adr = ADR.read_text(encoding="utf-8")
        cls.c_abi = C_ABI.read_text(encoding="utf-8")

    def test_api_is_draft_and_links_evidence(self) -> None:
        self.assertIn("Status: In Review", self.api)
        for evidence in (
            "architecture.md",
            "c-abi.md",
            "behavior-baseline.md",
            "cli-path-behavior.md",
            "path-filesystem-behavior.md",
            "large-directory-behavior.md",
            "path-toctou-behavior.md",
            "path-locale-filesystem-behavior.md",
            "cli-special-modes.md",
            "database-error-behavior.md",
            "nested-scan-behavior.md",
            "rule-compatibility.md",
        ):
            self.assertIn(evidence, self.api)

    def test_core_entry_points_share_service_semantics(self) -> None:
        for api_type in (
            "DatabaseBuilder",
            "Database",
            "Scanner",
            "ScanSource",
            "ScanRequest",
            "ScanReport",
            "CancellationToken",
        ):
            self.assertIn(api_type, self.api)
        self.assertIn("`scan_once` 调用同一个内部 scan service", self.api)
        self.assertIn("`Scanner::scan` 需要 `&mut self`", self.api)
        self.assertIn("不提供隐式 global default database", self.api)

    def test_path_expansion_profiles_are_explicit_and_bounded(self) -> None:
        for contract in (
            "TraversalProfile",
            "LegacyCompatible",
            "SafeCanonical",
            "stable file identity",
            "handle-relative",
            "ADR 0014",
        ):
            self.assertIn(contract, self.api)

    def test_result_states_are_unambiguous(self) -> None:
        self.assertIn("Complete", self.api)
        self.assertIn("Limited { reason: LimitReached }", self.api)
        self.assertIn("cancel/timeout 不返回成功 `ScanReport`", self.api)
        self.assertIn("`Completion::Limited` 的自洽 report 返回 `OK`", self.api)
        self.assertIn("非 OK 时 result null", self.api)

    def test_limits_and_determinism_are_explicit(self) -> None:
        for contract in (
            "max_total_decompressed_bytes",
            "max_single_allocation_bytes",
            "max_archive_entries",
            "max_queue_items",
            "max_diagnostics",
            "typed diagnostic facts",
            "不创建第 `limit+1` 项",
            "child work 不重置额度",
            "不依赖 map iteration",
            "parallel batch 使用 scanner-per-worker",
        ):
            self.assertIn(contract, self.api)

    def test_legacy_and_canonical_outputs_are_separate(self) -> None:
        self.assertIn("canonical JSON 是库、FFI 和现代 CLI 的稳定数据面", self.api)
        self.assertIn("compatibility renderer", self.api)
        self.assertIn("多目标 canonical `BatchReport`", self.api)
        self.assertIn("modern `--output` 与 legacy formatter flags 同时出现是 usage error", self.api)
        self.assertIn("Status: Proposed", self.adr)
        self.assertIn("两个明确命名的输出面", self.adr)

    def test_c_abi_alignment_is_recorded(self) -> None:
        for status in (
            "LIMIT_EXCEEDED",
            "CANCELLED",
            "TIMEOUT",
            "SCRIPT",
            "ALLOCATION_FAILED",
        ):
            self.assertIn(status, self.c_abi)
            self.assertIn(status, self.api)
        self.assertIn("canonical JSON", self.c_abi)
        self.assertIn("canonical JSON", self.api)

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
