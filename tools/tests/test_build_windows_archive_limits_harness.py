from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
BUILDER = (
    ROOT / "tools/upstream/build_windows_archive_limits_harness.ps1"
)


class BuildWindowsArchiveLimitsHarnessTests(unittest.TestCase):
    def test_builder_is_fixed_and_replaces_only_console_main(self):
        text = BUILDER.read_text(encoding="utf-8")
        for expected in (
            "74eaf505c250ab47e709024e9dc41657cd8f2254",
            "c2c17dfa5ea4e078ba31eab55d87430c96622fb6",
            "9bba1c21cf01b93a1ac80ab5cea4145330e1b2621d9f2b6e4"
            "275ab04723a68a4",
            "archive_limits_harness_main.cpp",
            "release\\main_console.obj",
            "engine_objects_modified = $false",
            "verified-source-root",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)

    def test_platform_adaptation_is_harness_only_and_explicit(self):
        text = BUILDER.read_text(encoding="utf-8")
        self.assertIn("getrusage(RUSAGE_SELF)", text)
        self.assertIn("GetProcessMemoryInfo", text)
        self.assertIn("harness-only-peak-rss", text)
        self.assertIn("engine_semantics_changed = $false", text)
        self.assertIn("database_path_replacements", text)


if __name__ == "__main__":
    unittest.main()
