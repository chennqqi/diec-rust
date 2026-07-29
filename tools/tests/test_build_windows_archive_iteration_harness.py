from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
BUILDER = (
    ROOT / "tools/upstream/build_windows_archive_iteration_harness.ps1"
)


class BuildWindowsArchiveIterationHarnessTests(unittest.TestCase):
    def test_builder_is_fixed_and_replaces_only_console_main(self):
        text = BUILDER.read_text(encoding="utf-8")
        for expected in (
            "74eaf505c250ab47e709024e9dc41657cd8f2254",
            "c2c17dfa5ea4e078ba31eab55d87430c96622fb6",
            "b8f35799ddda9e61fcff70081e7cdb6550ca2b9e9442a340"
            "a8b4ff31d2170e41",
            "archive_iteration_boundary_harness_main.cpp",
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
