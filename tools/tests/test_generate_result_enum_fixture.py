import hashlib
import importlib.util
import json
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).parents[2]
SCRIPT = ROOT / "tools" / "corpus" / "generate_result_enum_fixture.py"
MANIFEST = (
    ROOT / "docs" / "research" / "data" / "result-enum-fixture.json"
)
SPEC = importlib.util.spec_from_file_location(
    "generate_result_enum_fixture",
    SCRIPT,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class GenerateResultEnumFixtureTests(unittest.TestCase):
    def test_committed_manifest_is_exact_generator_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            generated = MODULE.generate(root)
            self.assertEqual(
                (root / "manifest.json").read_bytes(),
                MANIFEST.read_bytes(),
            )
            self.assertEqual(
                generated,
                json.loads(MANIFEST.read_text(encoding="utf-8")),
            )

    def test_all_fixture_files_match_size_and_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            manifest = MODULE.generate(root)
            self.assertEqual(len(manifest["entries"]), 4)
            for entry in manifest["entries"]:
                data = (
                    root / pathlib.PurePosixPath(entry["path"])
                ).read_bytes()
                self.assertEqual(len(data), entry["size"])
                self.assertEqual(
                    hashlib.sha256(data).hexdigest(),
                    entry["sha256"],
                )

    def test_rules_preserve_distinct_raw_spellings(self):
        known = MODULE.FILES[1][1]
        heuristic = MODULE.FILES[2][1]
        custom = MODULE.FILES[3][1]
        self.assertIn(b'"PE-Tool", "7 ZIP"', known)
        self.assertIn(b'"~format", "7-Zip"', heuristic)
        self.assertIn(b'"Vendor-Custom", "Project/Custom"', custom)


if __name__ == "__main__":
    unittest.main()
