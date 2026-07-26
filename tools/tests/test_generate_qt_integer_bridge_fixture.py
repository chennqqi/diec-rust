import importlib.util
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT / "tools/corpus/generate_qt_integer_bridge_fixture.py"
)
SPEC = importlib.util.spec_from_file_location(
    "generate_qt_integer_bridge_fixture", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class GenerateQtIntegerBridgeFixtureTests(unittest.TestCase):
    def test_generation_is_byte_deterministic(self):
        with tempfile.TemporaryDirectory() as first_directory:
            with tempfile.TemporaryDirectory() as second_directory:
                first = pathlib.Path(first_directory)
                second = pathlib.Path(second_directory)
                self.assertEqual(
                    MODULE.generate(first),
                    MODULE.generate(second),
                )
                self.assertEqual(
                    (first / "manifest.json").read_bytes(),
                    (second / "manifest.json").read_bytes(),
                )
                for relative_path, _, _ in MODULE.RULES:
                    self.assertEqual(
                        (first / relative_path).read_bytes(),
                        (second / relative_path).read_bytes(),
                    )

    def test_rules_cover_signed_and_unsigned_32_and_64_bit_returns(self):
        observed = {
            type_name: expression
            for _, type_name, expression in MODULE.RULES
        }
        self.assertEqual(
            observed,
            {
                "qint64": "PE.getSize()",
                "quint64": 'PE.getImageFileHeader("Machine")',
                "qint32": "PE.getNumberOfImports()",
                "quint32": "PE.getSectionFileOffset(0)",
            },
        )
        for _, type_name, expression in MODULE.RULES:
            source = MODULE.rule_source(type_name, expression)
            self.assertIn(b"typeof value", source)
            self.assertIn(b"String(value)", source)
            self.assertNotIn(b"includeScript", source)

    def test_matches_committed_manifest(self):
        reference = (
            ROOT / "docs/research/data/qt-integer-bridge-fixture.json"
        )
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory)
            MODULE.generate(output)
            self.assertEqual(
                (output / "manifest.json").read_bytes(),
                reference.read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()
