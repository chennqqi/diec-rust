import importlib.util
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).parents[2]
MODULE_PATH = ROOT / "tools" / "corpus" / "generate_script_scope_fixture.py"
SPEC = importlib.util.spec_from_file_location(
    "generate_script_scope_fixture", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class GenerateScriptScopeFixtureTests(unittest.TestCase):
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
                    relative = pathlib.PurePosixPath(entry["path"])
                    self.assertEqual(
                        (first / relative).read_bytes(),
                        (second / relative).read_bytes(),
                    )

    def test_fixture_covers_cross_evaluate_conflicts(self):
        sources = b"\n".join(data for _, data, _ in MODULE.FILES)
        self.assertIn(b"const scopeValue = 1;", sources)
        self.assertIn(b"scopeValue = 2;", sources)
        self.assertIn(b"const detect = main;", sources)
        self.assertIn(b"const debug = 1;", sources)
        self.assertIn(b"debug = 2;", sources)
        self.assertEqual(len(MODULE.FILES) - 1, 7)

    def test_matches_versioned_reference_manifest(self):
        reference_path = (
            ROOT / "docs" / "research" / "data" / "script-scope-fixture.json"
        )
        with tempfile.TemporaryDirectory() as output_directory:
            output = pathlib.Path(output_directory)
            MODULE.generate(output)
            generated = (output / "manifest.json").read_bytes()

        self.assertEqual(generated, reference_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
