import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools/corpus/generate_windows_long_path_fixture.py"
SPEC = importlib.util.spec_from_file_location(
    "generate_windows_long_path_fixture",
    SCRIPT,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class GenerateWindowsLongPathFixtureTests(unittest.TestCase):
    def test_relative_paths_guarantee_true_long_absolute_paths(self):
        self.assertLess(
            len(MODULE.CONTROL_PATH),
            MODULE.MAX_PATH,
        )
        self.assertGreater(
            len(MODULE.EXPLICIT_PATH),
            MODULE.MAX_PATH,
        )
        self.assertGreater(
            len(MODULE.DISCOVERY_PATH),
            MODULE.MAX_PATH,
        )
        self.assertEqual(
            len(MODULE.EXPLICIT_PATH),
            len(MODULE.DISCOVERY_PATH) - 1,
        )

    def test_every_component_stays_below_filesystem_component_limit(self):
        self.assertEqual(len(MODULE.SEGMENTS), 6)
        self.assertTrue(
            all(len(segment) == 49 for segment in MODULE.SEGMENTS)
        )
        self.assertTrue(
            all(len(segment) < 255 for segment in MODULE.SEGMENTS)
        )

    def test_extended_path_handles_drive_and_unc_roots(self):
        self.assertEqual(
            MODULE.extended_path(Path("C:/fixture")),
            "\\\\?\\C:\\fixture",
        )

    def test_fixture_path_rejects_escape_and_backslash(self):
        root = Path("C:/fixture")
        for value in ("../escape", "/absolute", "a\\b", ""):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    MODULE.fixture_path(root, value)


if __name__ == "__main__":
    unittest.main()
