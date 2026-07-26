import importlib.util
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT / "tools/upstream/audit_embedded_compression_origins.py"
)
SPEC = importlib.util.spec_from_file_location(
    "audit_embedded_compression_origins", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class EmbeddedCompressionOriginUnitTests(unittest.TestCase):
    def test_tokenizer_ignores_comments_but_preserves_literals(self):
        data = (
            b'/* copyright */ extern "C" { // license\n'
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

    def test_version_and_license_word_detection(self):
        data = (
            b"#define TOOL_MAJOR 1\n"
            b"#define TOOL_MINOR 2\n"
            b"#define TOOL_PATCH 3\n"
        )
        self.assertEqual(
            MODULE.parse_version(
                data, "TOOL_", ("MAJOR", "MINOR", "PATCH")
            ),
            "1.2.3",
        )
        self.assertFalse(MODULE.has_license_words(data))
        self.assertTrue(
            MODULE.has_license_words(b"Redistribution and use")
        )

    def test_shingle_evidence_records_unique_origin(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            source = root / "c/example.c"
            source.parent.mkdir()
            source.write_text(
                "int unique_function(int value) { "
                "return value + 1 + 2 + 3 + 4; }\n",
                encoding="utf-8",
            )
            tokens = MODULE.tokenize_c(source.read_bytes())
            evidence = MODULE.shingle_evidence(tokens, root, 4)
        self.assertEqual(evidence["coverage"], 1.0)
        self.assertEqual(evidence["unique_origin_file_count"], 1)
        self.assertEqual(
            evidence["unique_origin_files"][0]["path"],
            "c/example.c",
        )


if __name__ == "__main__":
    unittest.main()
