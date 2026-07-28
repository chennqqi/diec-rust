import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools/corpus/generate_windows_ads_fixture.py"
SPEC = importlib.util.spec_from_file_location(
    "generate_windows_ads_fixture",
    SCRIPT,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class GenerateWindowsAdsFixtureTests(unittest.TestCase):
    def test_default_and_named_stream_sources_are_distinct(self):
        self.assertEqual(MODULE.BASE_SOURCE, "plain.txt")
        self.assertEqual(MODULE.STREAM_SOURCE, "minimal.pdf")
        self.assertNotEqual(MODULE.BASE_SOURCE, MODULE.STREAM_SOURCE)
        self.assertEqual(
            str(MODULE.ads_path(Path("C:/fixture/ads/carrier.bin"))),
            "C:\\fixture\\ads\\carrier.bin:payload.pdf",
        )

    def test_extended_path_preserves_stream_suffix(self):
        path = MODULE.ads_path(Path("C:/fixture/ads/carrier.bin"))
        self.assertEqual(
            MODULE.extended_path(path),
            "\\\\?\\C:\\fixture\\ads\\carrier.bin:payload.pdf",
        )

    def test_fixture_path_rejects_escape_and_backslash(self):
        root = Path("C:/fixture")
        for value in ("../escape", "/absolute", "a\\b", ""):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    MODULE.fixture_path(root, value)


if __name__ == "__main__":
    unittest.main()
