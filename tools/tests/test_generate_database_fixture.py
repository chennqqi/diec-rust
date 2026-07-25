import importlib.util
import pathlib
import sys
import tempfile
import unittest


MODULE_PATH = (
    pathlib.Path(__file__).parents[1]
    / "corpus"
    / "generate_database_fixture.py"
)
SPEC = importlib.util.spec_from_file_location(
    "generate_database_fixture", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class GenerateDatabaseFixtureTests(unittest.TestCase):
    def test_generates_same_manifest_and_files_twice(self):
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
                    path = pathlib.PurePosixPath(entry["path"])
                    self.assertEqual(
                        (first / path).read_bytes(),
                        (second / path).read_bytes(),
                    )

    def test_covers_empty_invalid_and_executable_rule_states(self):
        paths = {entry[0] for entry in MODULE.FILES}
        self.assertIn("not-a-database.bin", paths)
        self.assertIn("malformed-main/Binary/broken.1.sg", paths)
        self.assertIn("throwing-main/Binary/throw.1.sg", paths)
        self.assertIn("valid-main/Binary/fixture.1.sg", paths)
        self.assertIn("empty-main", MODULE.DIRECTORIES)

    def test_matches_versioned_reference_manifest(self):
        reference_path = (
            pathlib.Path(__file__).parents[2]
            / "docs"
            / "research"
            / "data"
            / "database-fixture.json"
        )
        with tempfile.TemporaryDirectory() as output_directory:
            output = pathlib.Path(output_directory)
            MODULE.generate(output)
            generated = (output / "manifest.json").read_bytes()

        self.assertEqual(generated, reference_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
