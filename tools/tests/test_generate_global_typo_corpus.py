import importlib.util
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools/corpus/generate_global_typo_corpus.py"
SPEC = importlib.util.spec_from_file_location(
    "generate_global_typo_corpus", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class GenerateGlobalTypoCorpusTests(unittest.TestCase):
    def test_generates_identical_manifest_and_files(self):
        with tempfile.TemporaryDirectory() as first_directory:
            with tempfile.TemporaryDirectory() as second_directory:
                first = pathlib.Path(first_directory)
                second = pathlib.Path(second_directory)
                first_manifest = MODULE.generate(first)
                second_manifest = MODULE.generate(second)
                self.assertEqual(first_manifest, second_manifest)
                self.assertEqual(
                    (first / "manifest.json").read_bytes(),
                    (second / "manifest.json").read_bytes(),
                )
                for entry in first_manifest["entries"]:
                    self.assertEqual(
                        (first / entry["path"]).read_bytes(),
                        (second / entry["path"]).read_bytes(),
                    )

    def test_trigger_bytes_are_minimal_and_explicit(self):
        debug = MODULE.debug_dwarf_typo()
        self.assertEqual(len(debug), 32)
        self.assertEqual(int.from_bytes(debug[16:20], "little"), 0x534954)
        self.assertEqual(debug[20:28], bytes(8))
        self.assertEqual(int.from_bytes(debug[28:32], "little"), 16)

        wem = MODULE.wem_xma2_typo()
        self.assertEqual(len(wem), 40)
        self.assertEqual(wem[0:4], b"RIFF")
        self.assertEqual(wem[8:12], b"WAVE")
        self.assertEqual(wem[12:16], b"XMA2")
        self.assertEqual(wem[24:28], b"data")

    def test_matches_versioned_reference_manifest_and_rule_hashes(self):
        reference = (
            ROOT / "docs/research/data/global-typo-corpus.json"
        )
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory)
            MODULE.generate(output)
            self.assertEqual(
                (output / "manifest.json").read_bytes(),
                reference.read_bytes(),
            )
        rules = ROOT / "upstream/Detect-It-Easy"
        for path, digest, _ in MODULE.RULE_EVIDENCE:
            import hashlib

            self.assertEqual(
                hashlib.sha256((rules / path).read_bytes()).hexdigest(),
                digest,
            )


if __name__ == "__main__":
    unittest.main()
