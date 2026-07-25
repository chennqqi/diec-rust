import importlib.util
import pathlib
import sys
import tempfile
import unittest


TOOLS_DIR = pathlib.Path(__file__).parents[1]


def load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BASELINE = load_module(
    "generate_baseline_corpus_for_path_tests",
    TOOLS_DIR / "corpus" / "generate_baseline_corpus.py",
)
MODULE = load_module(
    "generate_path_corpus",
    TOOLS_DIR / "corpus" / "generate_path_corpus.py",
)


class GeneratePathCorpusTests(unittest.TestCase):
    def test_generates_same_manifest_and_tree_twice(self):
        with tempfile.TemporaryDirectory() as baseline_directory:
            baseline = pathlib.Path(baseline_directory)
            BASELINE.generate(baseline)
            with tempfile.TemporaryDirectory() as first_directory:
                with tempfile.TemporaryDirectory() as second_directory:
                    first = pathlib.Path(first_directory)
                    second = pathlib.Path(second_directory)

                    first_manifest = MODULE.generate(baseline, first)
                    second_manifest = MODULE.generate(baseline, second)

                    self.assertEqual(first_manifest, second_manifest)
                    self.assertEqual(
                        (first / "manifest.json").read_bytes(),
                        (second / "manifest.json").read_bytes(),
                    )
                    for entry in first_manifest["entries"]:
                        relative_path = pathlib.PurePosixPath(entry["path"])
                        self.assertEqual(
                            (first / relative_path).read_bytes(),
                            (second / relative_path).read_bytes(),
                        )

    def test_layout_has_empty_single_and_nested_directories(self):
        self.assertIn("empty-dir", MODULE.DIRECTORIES)
        self.assertIn("single/only.elf", dict(MODULE.LAYOUT))
        self.assertIn(
            "tree/b-dir/c-deep/z-child.zip",
            dict(MODULE.LAYOUT),
        )

    def test_matches_versioned_reference_manifest(self):
        reference_path = (
            pathlib.Path(__file__).parents[2]
            / "docs"
            / "research"
            / "data"
            / "path-corpus.json"
        )
        with tempfile.TemporaryDirectory() as baseline_directory:
            with tempfile.TemporaryDirectory() as output_directory:
                baseline = pathlib.Path(baseline_directory)
                output = pathlib.Path(output_directory)
                BASELINE.generate(baseline)
                MODULE.generate(baseline, output)
                generated = (output / "manifest.json").read_bytes()

        self.assertEqual(generated, reference_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
