import importlib.util
import pathlib
import sys
import tempfile
import unittest


MODULE_PATH = (
    pathlib.Path(__file__).parents[1]
    / "corpus"
    / "generate_baseline_corpus.py"
)
SPEC = importlib.util.spec_from_file_location(
    "generate_baseline_corpus", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class GenerateBaselineCorpusTests(unittest.TestCase):
    def test_generates_same_manifest_and_bytes_twice(self):
        with tempfile.TemporaryDirectory() as first_dir:
            with tempfile.TemporaryDirectory() as second_dir:
                first = pathlib.Path(first_dir)
                second = pathlib.Path(second_dir)

                first_manifest = MODULE.generate(first)
                second_manifest = MODULE.generate(second)

                self.assertEqual(first_manifest, second_manifest)
                self.assertEqual(
                    (first / "manifest.json").read_bytes(),
                    (second / "manifest.json").read_bytes(),
                )
                for sample in first_manifest["samples"]:
                    name = sample["name"]
                    self.assertEqual(
                        (first / name).read_bytes(),
                        (second / name).read_bytes(),
                    )

    def test_manifest_covers_every_declared_generator(self):
        with tempfile.TemporaryDirectory() as output_dir:
            manifest = MODULE.generate(pathlib.Path(output_dir))

        self.assertEqual(
            [sample["name"] for sample in manifest["samples"]],
            [item[0] for item in MODULE.GENERATORS],
        )
        self.assertEqual(len(manifest["samples"]), 15)

    def test_matches_versioned_reference_manifest(self):
        reference_path = (
            pathlib.Path(__file__).parents[2]
            / "docs"
            / "research"
            / "data"
            / "baseline-corpus.json"
        )
        with tempfile.TemporaryDirectory() as output_dir:
            MODULE.generate(pathlib.Path(output_dir))
            generated = (
                pathlib.Path(output_dir) / "manifest.json"
            ).read_bytes()

        self.assertEqual(generated, reference_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
