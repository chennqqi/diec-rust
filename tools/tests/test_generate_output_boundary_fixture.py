import hashlib
import json
import pathlib
import tempfile
import unittest

from importlib.util import module_from_spec, spec_from_file_location


ROOT = pathlib.Path(__file__).parents[2]
GENERATOR_PATH = (
    ROOT / "tools" / "corpus" / "generate_output_boundary_fixture.py"
)
MANIFEST_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "output-boundary-fixture.json"
)
SPEC = spec_from_file_location(
    "generate_output_boundary_fixture",
    GENERATOR_PATH,
)
MODULE = module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class OutputBoundaryFixtureTests(unittest.TestCase):
    def test_generation_is_reproducible_and_matches_manifest(self):
        expected = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        with (
            tempfile.TemporaryDirectory() as first_directory,
            tempfile.TemporaryDirectory() as second_directory,
        ):
            first = pathlib.Path(first_directory)
            second = pathlib.Path(second_directory)
            first_manifest = MODULE.generate(first)
            second_manifest = MODULE.generate(second)
            self.assertEqual(first_manifest, expected)
            self.assertEqual(second_manifest, expected)
            self.assertEqual(
                (first / "manifest.json").read_bytes(),
                (second / "manifest.json").read_bytes(),
            )
            for entry in expected["entries"]:
                relative = pathlib.PurePosixPath(entry["path"])
                first_data = (first / relative).read_bytes()
                second_data = (second / relative).read_bytes()
                self.assertEqual(first_data, second_data)
                self.assertEqual(len(first_data), entry["size"])
                self.assertEqual(
                    hashlib.sha256(first_data).hexdigest(),
                    entry["sha256"],
                )

    def test_fixture_is_project_generated_and_covers_boundaries(self):
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema_version"], 1)
        self.assertIn("project-generated", manifest["license"])
        self.assertEqual(len(manifest["expected_records"]), 3)
        special = manifest["expected_records"][0]
        for value in (
            '"',
            "\\",
            "/",
            ";",
            ",",
            "\t",
            "\r",
            "\n",
            "<",
            ">",
            "&",
            "'",
            "☃",
            "中",
            "😀",
            "\u2028",
            "\u2029",
        ):
            with self.subTest(value=repr(value)):
                self.assertTrue(
                    any(
                        value in special[field]
                        for field in ("name", "version", "info")
                    )
                )

    def test_rule_bytes_are_ascii_and_use_javascript_escapes(self):
        rule = MODULE.RULE
        rule.decode("ascii")
        for token in (
            b"_setResult",
            b"\\t",
            b"\\r",
            b"\\n",
            b"\\u2603",
            b"\\u4e2d",
            b"\\ud83d\\ude00",
            b"\\u2028",
            b"\\u2029",
        ):
            with self.subTest(token=token):
                self.assertIn(token, rule)


if __name__ == "__main__":
    unittest.main()
