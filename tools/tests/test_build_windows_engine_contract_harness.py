import hashlib
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
BUILDER = (
    ROOT / "tools/upstream/build_windows_engine_contract_harness.ps1"
)
SHARED_HARNESS = (
    ROOT / "tools/upstream/engine_contract_harness_main.cpp"
)


class BuildWindowsEngineContractHarnessTests(unittest.TestCase):
    def test_builder_replaces_only_the_console_main_object(self):
        builder = BUILDER.read_text(encoding="utf-8")
        self.assertIn('"release\\main_console.obj"', builder)
        self.assertIn(
            '"release\\engine_contract_harness_main.obj"',
            builder,
        )
        self.assertIn("original_main_object_sha256", builder)
        self.assertIn("original_makefile_sha256", builder)
        self.assertIn("-arch=amd64 -host_arch=amd64", builder)
        self.assertNotIn("git checkout", builder)

    def test_builder_reuses_shared_37_case_harness(self):
        builder = BUILDER.read_text(encoding="utf-8")
        harness = SHARED_HARNESS.read_text(encoding="utf-8")
        self.assertIn(
            '"engine_contract_harness_main.cpp"',
            builder,
        )
        self.assertIn("const CaseSpec cases[]", harness)
        self.assertIn("const DeviceCaseSpec deviceCases[]", harness)
        self.assertIn(
            'root.insert("case_count", outputs.size())',
            harness,
        )
        self.assertNotIn("filter_all", builder)

    def test_builder_pins_source_qt_and_cli_identities(self):
        builder = BUILDER.read_text(encoding="utf-8")
        for token in (
            "74eaf505c250ab47e709024e9dc41657cd8f2254",
            "c2c17dfa5ea4e078ba31eab55d87430c96622fb6",
            "e8579a6ed0d2536ea14af154bcbeeaaea6967c0c7559a595fb3fe52206ac635e",
            "e873ad3a689a0628c3037a6440221dcd2e426395edf14ffa6379612dede26d36",
        ):
            with self.subTest(token=token):
                self.assertIn(token, builder)

    def test_inputs_have_stable_hashes(self):
        for path in (BUILDER, SHARED_HARNESS):
            with self.subTest(path=path.name):
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                self.assertEqual(len(digest), 64)


if __name__ == "__main__":
    unittest.main()
