from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
BUILDER = (
    ROOT / "tools/upstream/build_windows_result_model_harnesses.ps1"
)


class BuildWindowsResultModelHarnessesTests(unittest.TestCase):
    def test_builder_is_identity_bound(self):
        text = BUILDER.read_text(encoding="utf-8")
        for expected in (
            "74eaf505c250ab47e709024e9dc41657cd8f2254",
            "c2c17dfa5ea4e078ba31eab55d87430c96622fb6",
            "e8579a6ed0d2536ea14af154bcbeeaaea6967c0c7559a595"
            "fb3fe52206ac635e",
            "e873ad3a689a0628c3037a6440221dcd2e426395edf14ffa6"
            "379612dede26d36",
            "submodule status --recursive",
            "status --porcelain=v1 --untracked-files=no",
            "-arch=amd64 -host_arch=amd64",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)

    def test_all_five_harnesses_replace_only_console_main(self):
        text = BUILDER.read_text(encoding="utf-8")
        profiles = {
            "metadata": "result_metadata_harness_main.cpp",
            "lists": "result_lists_harness_main.cpp",
            "flags": "result_flags_harness_main.cpp",
            "ids": "result_ids_harness_main.cpp",
            "enums": "result_enums_harness_main.cpp",
        }
        for profile, source in profiles.items():
            with self.subTest(profile=profile):
                self.assertIn(f'name = "{profile}"', text)
                self.assertIn(f'source = "{source}"', text)
        self.assertIn('"release\\main_console.obj"', text)
        self.assertIn('"Makefile.ResultModel.$($Profile.name).Release"', text)
        self.assertIn("harness_count = $Profiles.Count", text)

    def test_builder_does_not_modify_engine_objects(self):
        text = BUILDER.read_text(encoding="utf-8")
        self.assertIn(
            "original_die_script_object_sha256 = Get-Sha256 "
            "$DieScriptObject",
            text,
        )
        self.assertNotIn("/alternatename:", text)
        self.assertNotIn("die_script.cpp", text)


if __name__ == "__main__":
    unittest.main()
