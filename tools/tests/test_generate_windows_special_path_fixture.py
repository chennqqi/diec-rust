import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT / "tools/corpus/generate_windows_special_path_fixture.py"
)
MANIFEST = (
    ROOT / "docs/research/data/windows-special-path-fixture.json"
)
SPEC = importlib.util.spec_from_file_location(
    "generate_windows_special_path_fixture",
    SCRIPT,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class GenerateWindowsSpecialPathFixtureTests(unittest.TestCase):
    def test_declared_entries_cover_windows_unicode_and_controls(self):
        ids = {entry[0] for entry in MODULE.ENTRIES}
        self.assertEqual(len(ids), 12)
        self.assertTrue(
            {
                "nfc",
                "nfd",
                "cjk",
                "emoji",
                "dot_hidden",
                "attribute_hidden",
            }.issubset(ids)
        )

    def test_unrepresentable_linux_controls_are_explicit(self):
        paths = {
            entry["linux_path"]
            for entry in MODULE.UNREPRESENTABLE_CONTROLS
        }
        self.assertEqual(len(paths), 6)
        self.assertIn("paths/special/trailing-space.pdf ", paths)
        self.assertIn("paths/special/colon:name.pdf", paths)
        self.assertIn("paths/special/backslash\\name.pdf", paths)
        self.assertIn("paths/special/<TAB and LF names>", paths)

    @unittest.skipUnless(MANIFEST.exists(), "fixture not generated")
    def test_committed_manifest_matches_generator_contract(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["generator"], MODULE.GENERATOR)
        self.assertEqual(
            [entry["id"] for entry in manifest["entries"]],
            [entry[0] for entry in MODULE.ENTRIES],
        )
        self.assertEqual(
            manifest["unrepresentable_linux_controls"],
            list(MODULE.UNREPRESENTABLE_CONTROLS),
        )
        self.assertTrue(
            manifest["filesystem_observations"][
                "lowercase_case_alias_exists"
            ]
        )


if __name__ == "__main__":
    unittest.main()
