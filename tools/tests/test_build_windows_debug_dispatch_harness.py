from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
BUILDER = (
    ROOT / "tools/upstream/build_windows_debug_dispatch_harness.ps1"
)


class BuildWindowsDebugDispatchHarnessTests(unittest.TestCase):
    def test_builder_is_fixed_and_replaces_only_console_main(self):
        text = BUILDER.read_text(encoding="utf-8")
        for expected in (
            "74eaf505c250ab47e709024e9dc41657cd8f2254",
            "c2c17dfa5ea4e078ba31eab55d87430c96622fb6",
            "e8579a6ed0d2536ea14af154bcbeeaaea6967c0c7559a595"
            "fb3fe52206ac635e",
            "debug_dispatch_harness_main.cpp",
            "release\\main_console.obj",
            "engine_objects_modified = $false",
            "verified-source-root",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)

    def test_private_bridge_and_path_adaptation_are_explicit(self):
        text = BUILDER.read_text(encoding="utf-8")
        self.assertIn("/alternatename:", text)
        self.assertIn("?processDetect@DiE_Script@@QEAAX", text)
        self.assertIn("?processDetect@DiE_Script@@AEAAX", text)
        self.assertIn("database_path_replacements", text)
        self.assertIn('"Detect-It-Easy/db"', text)


if __name__ == "__main__":
    unittest.main()
