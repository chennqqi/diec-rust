import importlib.util
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools/upstream/audit_rar_decoder_origin.py"
SPEC = importlib.util.spec_from_file_location(
    "audit_rar_decoder_origin", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class RarDecoderOriginAuditUnitTests(unittest.TestCase):
    def test_tokenizer_ignores_comments_and_preserves_literals(self):
        data = (
            b'/* notice */ extern "C" { // comment\n'
            b'const char *value = "not // a comment"; }\n'
        )
        self.assertEqual(
            MODULE.tokenize_c(data),
            [
                "extern",
                '"C"',
                "{",
                "const",
                "char",
                "*",
                "value",
                "=",
                '"not // a comment"',
                ";",
                "}",
            ],
        )

    def test_shingle_evidence_records_only_explicit_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            included = root / "included.cpp"
            excluded = root / "excluded.cpp"
            included.write_text(
                "int included(int value) { return value + 1; }\n",
                encoding="utf-8",
            )
            excluded.write_text(
                "int excluded(int value) { return value + 2; }\n",
                encoding="utf-8",
            )
            tokens = MODULE.tokenize_c(included.read_bytes())
            evidence = MODULE.shingle_evidence(
                tokens, root, [included], 4
            )
        self.assertEqual(evidence["coverage"], 1.0)
        self.assertEqual(
            [item["path"] for item in evidence["unique_origin_files"]],
            ["included.cpp"],
        )

    def test_source_files_are_top_level_cpp_and_hpp_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "one.cpp").write_text("", encoding="utf-8")
            (root / "two.hpp").write_text("", encoding="utf-8")
            (root / "skip.txt").write_text("", encoding="utf-8")
            nested = root / "nested"
            nested.mkdir()
            (nested / "skip.cpp").write_text("", encoding="utf-8")
            paths = MODULE.source_files(root)
        self.assertEqual(
            [path.name for path in paths],
            ["one.cpp", "two.hpp"],
        )


if __name__ == "__main__":
    unittest.main()
