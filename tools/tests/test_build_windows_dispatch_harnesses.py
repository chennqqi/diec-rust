from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "tools/upstream/build_windows_dispatch_harnesses.ps1"


class BuildWindowsDispatchHarnessesTests(unittest.TestCase):
    def test_builder_is_identity_bound(self):
        text = BUILDER.read_text(encoding="utf-8")
        for expected in (
            "74eaf505c250ab47e709024e9dc41657cd8f2254",
            "c2c17dfa5ea4e078ba31eab55d87430c96622fb6",
            "e8579a6ed0d2536ea14af154bcbeeaaea6967c0c7559a595"
            "fb3fe52206ac635e",
            "e6f7710cd32be5050e10234f3282d2512b58d28170d5de14f"
            "96c30478ac03725",
            "submodule status --recursive",
            "-arch=amd64 -host_arch=amd64",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)

    def test_three_harnesses_replace_only_console_main(self):
        text = BUILDER.read_text(encoding="utf-8")
        profiles = {
            "bw": "bw_dispatch_harness_main.cpp",
            "npm": "npm_dispatch_harness_main.cpp",
            "generic_archive": (
                "generic_archive_dispatch_harness_main.cpp"
            ),
        }
        for profile, source in profiles.items():
            with self.subTest(profile=profile):
                self.assertIn(f'name = "{profile}"', text)
                self.assertIn(f'source = "{source}"', text)
        self.assertIn('"release\\main_console.obj"', text)
        self.assertIn('"Makefile.Dispatch.$($Profile.name).Release"', text)
        self.assertIn("engine_objects_modified = $false", text)

    def test_database_adaptation_is_exact_and_manifested(self):
        text = BUILDER.read_text(encoding="utf-8")
        for name in ("db", "db_extra", "db_custom"):
            self.assertIn(
                f'"/opt/die-source/Detect-It-Easy/{name}"',
                text,
            )
        self.assertIn("database_path_replacements", text)
        self.assertIn("original_sha256", text)
        self.assertIn("adapted_sha256", text)
        self.assertNotIn("/alternatename:", text)


if __name__ == "__main__":
    unittest.main()
