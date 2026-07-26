import hashlib
import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
REPORT_PATH = (
    ROOT / "docs/research/data/baseline-corpus-linux-qt5.json"
)
MANIFEST_PATH = ROOT / "docs/research/data/baseline-corpus.json"
TOOL_PATH = ROOT / "tools/upstream/compare_cli_oracles.py"


class BaselineCorpusReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    def test_report_and_inputs_are_identity_bound(self):
        self.assertEqual(self.report["schema_version"], 1)
        self.assertEqual(
            self.report["generator"],
            "tools/upstream/compare_cli_oracles.py",
        )
        self.assertEqual(
            self.report["generator_sha256"],
            hashlib.sha256(TOOL_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            self.report["corpus_manifest"]["sha256"],
            hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            self.report["expected_revision"],
            "74eaf505c250ab47e709024e9dc41657cd8f2254",
        )
        self.assertTrue(self.report["equal"])
        self.assertEqual(self.report["failures"], [])
        self.assertEqual(len(self.report["corpus"]), 26)

    def test_every_raw_observation_has_length_and_hash(self):
        for case in self.report["corpus"].values():
            self.assertEqual(case["differences"], [])
            for side in ("left", "right"):
                observation = case[side]
                self.assertGreater(observation["stdout_bytes"], 0)
                self.assertEqual(observation["stderr_bytes"], 0)
                self.assertEqual(
                    observation["stderr_sha256"],
                    hashlib.sha256(b"").hexdigest(),
                )

    def test_new_major_formats_have_expected_dispatch(self):
        expected = {
            "minimal-elf32.elf": "ELF32",
            "minimal-pe64.exe": "PE64",
            "minimal-macho32.macho": "Mach-O32",
            "minimal-fat.macho": "Mach-O FAT",
            "minimal.pyc": "Python Bytecode",
            "pixel.jpg": "JPEG",
            "minimal.apk": "APK",
            "minimal.jar": "JAR",
            # IPA is recognized internally, but scanProcess intentionally
            # dispatches its rules through FT_BINARY at this commit.
            "minimal.ipa": "Binary",
            "minimal.rar": "RAR",
            "minimal.iso": "ISO 9660",
        }
        for name, filetype in expected.items():
            left = self.report["corpus"][name]["left_detect_tree"]
            right = self.report["corpus"][name]["right_detect_tree"]
            self.assertEqual(left, right)
            self.assertEqual(left[0]["filetype"], filetype)

    def test_distinctive_rule_results_are_preserved(self):
        cases = self.report["corpus"]
        self.assertEqual(
            cases["minimal-fat.macho"]["left_detect_tree"][0]["values"],
            [{"name": "lipo", "type": "converter", "version": ""}],
        )
        self.assertEqual(
            cases["minimal.pyc"]["left_detect_tree"][0]["values"],
            [
                {
                    "name": "Python Bytecode",
                    "type": "format",
                    "version": "3.8b4",
                }
            ],
        )
        self.assertEqual(
            cases["pixel.jpg"]["left_detect_tree"][0]["values"],
            [
                {"name": "JPEG", "type": "format", "version": "1.1"},
                {"name": "DQT", "type": "image", "version": ""},
            ],
        )
        self.assertEqual(
            cases["minimal.ipa"]["left_detect_tree"][0]["values"],
            [{"name": "Zip", "type": "archive", "version": "2.0"}],
        )


if __name__ == "__main__":
    unittest.main()
