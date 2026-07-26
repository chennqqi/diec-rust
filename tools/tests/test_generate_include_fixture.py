import importlib.util
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools/corpus/generate_include_fixture.py"
SPEC = importlib.util.spec_from_file_location(
    "generate_include_fixture", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class GenerateIncludeFixtureTests(unittest.TestCase):
    def test_generation_is_byte_deterministic(self):
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
                for entry in first_manifest["entries"]:
                    relative = pathlib.PurePosixPath(entry["path"])
                    self.assertEqual(
                        (first / relative).read_bytes(),
                        (second / relative).read_bytes(),
                    )

    def test_inventory_has_each_include_failure_mode(self):
        paths = {entry[0] for entry in MODULE.FILES}
        self.assertIn("self-cycle-main/self", paths)
        self.assertIn("two-cycle-main/cycle-a", paths)
        self.assertIn("two-cycle-main/cycle-b", paths)
        self.assertIn("parse-error-main/broken-helper", paths)
        self.assertIn("missing-main/_init", paths)
        self.assertEqual(len(MODULE.CASE_NAMES), 4)

    def test_matches_versioned_reference_manifest(self):
        reference = ROOT / "docs/research/data/include-fixture.json"
        with tempfile.TemporaryDirectory() as output_dir:
            output = pathlib.Path(output_dir)
            MODULE.generate(output)
            self.assertEqual(
                (output / "manifest.json").read_bytes(),
                reference.read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()
