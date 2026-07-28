import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT / "tools/corpus/generate_windows_filesystem_fixture.py"
)
SPEC = importlib.util.spec_from_file_location(
    "generate_windows_filesystem_fixture",
    SCRIPT,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class GenerateWindowsFilesystemFixtureTests(unittest.TestCase):
    def test_fixture_graph_is_finite_and_declared(self):
        self.assertEqual(len(MODULE.FILES), 4)
        self.assertEqual(len(MODULE.JUNCTIONS), 4)
        by_path = {path: target for _, path, target in MODULE.JUNCTIONS}
        self.assertEqual(by_path["chain-entry"], "chain-hop")
        self.assertEqual(by_path["chain-hop"], "chain-target")
        self.assertNotIn("chain-entry", set(by_path.values()))

    def test_sensitive_unavailable_cases_are_explicit(self):
        gaps = {item["id"] for item in MODULE.EXPLICIT_GAPS}
        self.assertEqual(
            gaps,
            {
                "file_symlink",
                "directory_symlink",
                "dangling_reparse_point",
                "reparse_cycle",
                "acl_denial",
                "unc_path",
            },
        )

    def test_fixture_path_rejects_escape_and_backslash(self):
        root = Path("C:/fixture")
        for value in ("../escape", "/absolute", "a\\b", ""):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    MODULE.fixture_path(root, value)


if __name__ == "__main__":
    unittest.main()
