import importlib.util
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).parents[2]
MODULE_PATH = (
    ROOT / "tools" / "corpus"
    / "generate_database_layer_fixture.py"
)
REFERENCE_PATH = (
    ROOT / "docs" / "research" / "data"
    / "database-layer-fixture.json"
)
SPEC = importlib.util.spec_from_file_location(
    "generate_database_layer_fixture",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class GenerateDatabaseLayerFixtureTests(unittest.TestCase):
    def test_generates_identical_manifest_and_files_twice(self):
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
                    relative = pathlib.PurePosixPath(entry["path"])
                    self.assertEqual(
                        (first / relative).read_bytes(),
                        (second / relative).read_bytes(),
                    )

    def test_each_layer_has_same_names_and_distinct_results(self):
        self.assertEqual(MODULE.LAYERS, ("main", "extra", "custom"))
        self.assertEqual(
            [filename for filename, _ in MODULE.RULES],
            [
                "layer-low.1.sg",
                "shared.5.sg",
                "layer-high.9.sg",
            ],
        )
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            manifest = MODULE.generate(root)
            self.assertEqual(len(manifest["entries"]), 10)
            shared_rules = [
                root / layer / "Binary" / "shared.5.sg"
                for layer in MODULE.LAYERS
            ]
            contents = [path.read_bytes() for path in shared_rules]
            self.assertEqual(len(set(contents)), 3)
            self.assertIn(b"MainShared", contents[0])
            self.assertIn(b"ExtraShared", contents[1])
            self.assertIn(b"CustomShared", contents[2])

    def test_matches_versioned_reference_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            MODULE.generate(root)
            generated = (root / "manifest.json").read_bytes()
        self.assertEqual(generated, REFERENCE_PATH.read_bytes())


if __name__ == "__main__":
    unittest.main()
