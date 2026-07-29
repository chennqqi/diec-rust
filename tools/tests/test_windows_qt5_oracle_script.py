import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools/upstream/build_windows_qt5_oracle.ps1"
EVIDENCE = (
    ROOT / "docs/research/data/windows-qt5-build-baseline.json"
)
RESEARCH = ROOT / "docs/research/windows-qt5-build-baseline.md"
UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"


class WindowsQt5OracleScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SCRIPT.read_text(encoding="utf-8")
        cls.evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        cls.research = RESEARCH.read_text(encoding="utf-8")

    def test_pins_source_rules_and_qt_runtime_identity(self):
        self.assertIn(UPSTREAM_COMMIT, self.source)
        self.assertIn(RULES_COMMIT, self.source)
        self.assertIn('$ExpectedSubmoduleCount = 58', self.source)
        self.assertIn('$ExpectedQtVersion = "5.15.2"', self.source)
        self.assertIn(
            "e873ad3a689a0628c3037a6440221dcd"
            "2e426395edf14ffa6379612dede26d36",
            self.source,
        )
        self.assertIn(
            "8d2ff4ce9096ddccc4f4cd62c2e41fc"
            "854cfd1b0d6e8d296645a7f5fd4ae565a",
            self.source,
        )
        self.assertIn(
            "0b58e5e79df13110a8258f14d7b3658d"
            "1dd0c8dddc337a164b89d4ac12a0638f",
            self.source,
        )

    def test_rejects_dirty_or_incomplete_recursive_checkout(self):
        self.assertIn("RuntimeInformation]::IsOSPlatform", self.source)
        self.assertIn("status --porcelain=v1 --untracked-files=no", self.source)
        self.assertIn("submodule status --recursive", self.source)
        self.assertIn("submodule foreach --quiet --recursive", self.source)
        self.assertIn("Submodule identity is not clean", self.source)
        self.assertIn("Submodules have tracked changes", self.source)

    def test_builds_qmake_dependencies_before_console(self):
        libraries = self.source.index("sub-build_libs-release")
        console = self.source.index("sub-console_source-release")
        self.assertLess(libraries, console)
        self.assertIn("& $env:ComSpec /d /c $BuildCommand", self.source)
        self.assertIn("xsimd_sse2-win-x86_64.lib", self.source)
        self.assertIn("xsimd_avx2-win-x86_64.lib", self.source)
        self.assertNotIn("--target diec", self.source)

    def test_emits_hash_bound_machine_summary(self):
        self.assertIn("ConvertTo-Json -Depth 6", self.source)
        self.assertIn("elapsed_milliseconds", self.source)
        self.assertIn("Get-Sha256 $ArtifactPath", self.source)
        self.assertIn('"die 4.0.0"', self.source)
        self.assertIn("recursive_submodule_count", self.source)

    def test_versioned_evidence_records_clean_build_and_runtime_smoke(self):
        self.assertEqual(self.evidence["schema_version"], 1)
        self.assertEqual(
            self.evidence["upstream"]["commit"], UPSTREAM_COMMIT
        )
        self.assertEqual(
            self.evidence["upstream"]["rules_commit"], RULES_COMMIT
        )
        self.assertEqual(
            self.evidence["clean_qmake_build"]["targets"],
            ["sub-build_libs-release", "sub-console_source-release"],
        )
        self.assertEqual(
            self.evidence["clean_qmake_build"]["artifact"]["version_stdout"],
            "die 4.0.0",
        )
        self.assertEqual(
            self.evidence["runtime_smoke"]["projection"]["filetype"],
            "PE64",
        )
        self.assertEqual(self.evidence["runtime_smoke"]["exit_code"], 0)
        self.assertEqual(self.evidence["runtime_smoke"]["stderr_size"], 0)

    def test_research_scopes_build_record_and_platform_admission(self):
        self.assertIn("Windows 的 68 项能力已", self.research)
        self.assertIn("接纳为 `runtime_observed`", self.research)
        self.assertIn("该单份报告本身不足以接纳", self.research)
        self.assertIn("46 个 `LNK2019`", self.research)
        self.assertIn("bit-for-bit reproducible", self.research)


if __name__ == "__main__":
    unittest.main()
