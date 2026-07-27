import hashlib
import importlib.util
import json
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).parents[2]
SCRIPT = (
    ROOT / "tools" / "corpus" / "generate_result_list_fixture.py"
)
MANIFEST = (
    ROOT / "docs" / "research" / "data" / "result-list-fixture.json"
)
SPEC = importlib.util.spec_from_file_location(
    "generate_result_list_fixture",
    SCRIPT,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class GenerateResultListFixtureTests(unittest.TestCase):
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
            self.assertEqual(len(manifest["entries"]), 5)
            for entry in manifest["entries"]:
                data = (
                    root / pathlib.PurePosixPath(entry["path"])
                ).read_bytes()
                self.assertEqual(len(data), entry["size"])
                self.assertEqual(
                    hashlib.sha256(data).hexdigest(),
                    entry["sha256"],
                )

    def test_duplicate_rules_are_byte_identical_and_errors_are_distinct(self):
        self.assertEqual(MODULE.FILES[1][1], MODULE.FILES[2][1])
        self.assertNotEqual(MODULE.FILES[3][1], MODULE.FILES[4][1])
        self.assertIn(b"throw new Error", MODULE.FILES[3][1])
        self.assertEqual(MODULE.FILES[4][1], b"function detect( {\n")


if __name__ == "__main__":
    unittest.main()
