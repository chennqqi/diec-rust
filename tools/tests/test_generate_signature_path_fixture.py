import hashlib
import importlib.util
import json
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).parents[2]
SCRIPT = (
    ROOT
    / "tools"
    / "corpus"
    / "generate_signature_path_fixture.py"
)
MANIFEST = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "signature-path-fixture.json"
)
SPEC = importlib.util.spec_from_file_location(
    "generate_signature_path_fixture",
    SCRIPT,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class GenerateSignaturePathFixtureTests(unittest.TestCase):
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
            self.assertEqual(len(manifest["entries"]), 3)
            for entry in manifest["entries"]:
                data = (
                    root / pathlib.PurePosixPath(entry["path"])
                ).read_bytes()
                self.assertEqual(len(data), entry["size"])
                self.assertEqual(
                    hashlib.sha256(data).hexdigest(),
                    entry["sha256"],
                )

    def test_rules_share_basename_but_emit_distinct_names(self):
        main_path, main_rule = MODULE.FILES[1][:2]
        extra_path, extra_rule = MODULE.FILES[2][:2]
        self.assertEqual(
            pathlib.PurePosixPath(main_path).name,
            pathlib.PurePosixPath(extra_path).name,
        )
        self.assertNotEqual(
            pathlib.PurePosixPath(main_path).parent,
            pathlib.PurePosixPath(extra_path).parent,
        )
        self.assertIn(b'"main-path"', main_rule)
        self.assertIn(b'"extra-path"', extra_rule)


if __name__ == "__main__":
    unittest.main()
