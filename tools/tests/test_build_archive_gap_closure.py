import importlib.util
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools/research/build_archive_gap_closure.py"
SPEC = importlib.util.spec_from_file_location(
    "build_archive_gap_closure", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ArchiveGapClosureUnitTests(unittest.TestCase):
    def test_extract_braced_function_stops_at_matching_brace(self):
        source = (
            "void before() {}\n"
            "void target(int value)\n"
            "{\n"
            "  if (value) { value++; }\n"
            "}\n"
            "void after() {}\n"
        )
        function = MODULE.extract_braced_function(
            source, "void target("
        )
        self.assertIn("if (value) { value++; }", function)
        self.assertNotIn("void after", function)

    def test_scanable_family_gate_is_exact_and_ordered(self):
        function = """
        void scan() {
          bool bScanableArchive = false;
          if (stFT.contains(XBinary::FT_ZIP) ||
              stFT.contains(XBinary::FT_RAR)) {
            bScanableArchive = true;
          }
        }
        """
        self.assertEqual(
            MODULE.extract_scanable_families(function),
            ("ZIP", "RAR"),
        )

    def test_scanable_family_gate_rejects_extra_predicate(self):
        function = """
        void scan() {
          if (stFT.contains(XBinary::FT_ZIP) || enabled) {
            bScanableArchive = true;
          }
        }
        """
        with self.assertRaisesRegex(
            MODULE.ClosureError, "unexpected archive family gate syntax"
        ):
            MODULE.extract_scanable_families(function)

    def test_scanable_family_gate_rejects_duplicate(self):
        function = """
        void scan() {
          if (stFT.contains(XBinary::FT_ZIP) ||
              stFT.contains(XBinary::FT_ZIP)) {
            bScanableArchive = true;
          }
        }
        """
        with self.assertRaisesRegex(
            MODULE.ClosureError, "duplicate archive family"
        ):
            MODULE.extract_scanable_families(function)

    def test_family_adapter_map_requires_every_expected_adapter(self):
        function = "\n".join(
            (
                "XBinary *create() {",
                *(
                    "if (XBinary::checkFileType("
                    f"XBinary::FT_{family}, fileType)) "
                    f"return new {adapter}(device);"
                    for family, adapter in MODULE.FAMILY_ADAPTERS.items()
                ),
                "}",
            )
        )
        self.assertEqual(
            MODULE.extract_family_adapters(function),
            MODULE.FAMILY_ADAPTERS,
        )
        with self.assertRaisesRegex(
            MODULE.ClosureError, "adapter mapping changed"
        ):
            MODULE.extract_family_adapters(
                function.replace("new XRar(", "new OtherRar(")
            )

    def test_duplicate_json_keys_are_rejected(self):
        with self.assertRaisesRegex(
            MODULE.ClosureError, "duplicate JSON key"
        ):
            MODULE.reject_duplicate_keys([("key", 1), ("key", 2)])


if __name__ == "__main__":
    unittest.main()
