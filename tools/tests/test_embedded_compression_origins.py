import hashlib
import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
REPORT_PATH = (
    ROOT / "docs/research/data/embedded-compression-origins.json"
)
TOOL_PATH = (
    ROOT / "tools/upstream/audit_embedded_compression_origins.py"
)


class EmbeddedCompressionOriginReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    def test_report_identity_is_fixed(self):
        self.assertEqual(self.report["schema_version"], 1)
        self.assertEqual(
            self.report["generator"],
            "tools/upstream/audit_embedded_compression_origins.py",
        )
        self.assertEqual(
            self.report["generator_sha256"],
            hashlib.sha256(TOOL_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            self.report["upstream_commit"],
            "74eaf505c250ab47e709024e9dc41657cd8f2254",
        )
        self.assertEqual(
            self.report["xarchive_commit"],
            "0fcd4e8d3e9933baac3b12246d82ac026557ffd0",
        )
        self.assertTrue(all(self.report["relationships"].values()))

    def test_brotli_origin_and_license_are_content_bound(self):
        official = self.report["official_sources"]["brotli"]
        embedded = self.report["embedded_sources"]["brotli"]
        self.assertEqual(
            official["commit"],
            "028fb5a23661f123017c060daa546b55cf4bde29",
        )
        self.assertEqual(official["tag"], "v1.2.0")
        self.assertEqual(official["declared_version"], "1.2.0")
        self.assertEqual(
            official["license"]["sha256"],
            "3d180008e36922a4e8daec11c34c7af"
            "264fed5962d07924aea928c38e8663c94",
        )
        self.assertEqual(embedded["token_count"], 296486)
        self.assertFalse(embedded["contains_license_words"])
        evidence = {
            item["shingle_length"]: item
            for item in embedded["shingle_evidence"]
        }
        self.assertEqual(evidence[12]["covered_token_count"], 295463)
        self.assertEqual(evidence[64]["covered_token_count"], 292346)
        self.assertEqual(evidence[64]["unique_origin_file_count"], 28)
        self.assertEqual(
            {
                item["path"]
                for item in evidence[64]["unique_origin_files"]
            },
            {
                "c/common/constants.c",
                "c/common/constants.h",
                "c/common/context.c",
                "c/common/context.h",
                "c/common/dictionary.c",
                "c/common/dictionary.h",
                "c/common/dictionary_inc.h",
                "c/common/platform.h",
                "c/common/shared_dictionary.c",
                "c/common/shared_dictionary_internal.h",
                "c/common/transform.c",
                "c/common/transform.h",
                "c/common/version.h",
                "c/dec/bit_reader.c",
                "c/dec/bit_reader.h",
                "c/dec/decode.c",
                "c/dec/huffman.c",
                "c/dec/huffman.h",
                "c/dec/prefix.c",
                "c/dec/prefix.h",
                "c/dec/prefix_inc.h",
                "c/dec/state.c",
                "c/dec/state.h",
                "c/dec/static_init.c",
                "c/include/brotli/decode.h",
                "c/include/brotli/port.h",
                "c/include/brotli/shared_dictionary.h",
                "c/include/brotli/types.h",
            },
        )

    def test_zstd_is_exact_official_amalgamation_inside_wrapper(self):
        official = self.report["official_sources"]["zstandard"]
        embedded = self.report["embedded_sources"]["zstandard"]
        self.assertEqual(
            official["commit"],
            "5c7b7bad26808e6b40ac3b3d0075466e27738a9d",
        )
        self.assertIsNone(official["tag"])
        self.assertEqual(official["declared_version"], "1.6.0")
        self.assertEqual(
            official["license"]["sha256"],
            "7055266497633c9025b777c78eb7235af"
            "13922117480ed5c674677adc381c9d8",
        )
        self.assertEqual(
            official["copying"]["sha256"],
            "f9c375a1be4a41f7b70301dd83c91cb8"
            "9e41567478859b77eef375a52d782505",
        )
        self.assertEqual(embedded["token_count"], 90414)
        self.assertEqual(embedded["official_generated_token_count"], 90410)
        self.assertEqual(
            embedded["wrapper_prefix_tokens"],
            ["extern", '"C"', "{"],
        )
        self.assertEqual(embedded["wrapper_suffix_tokens"], ["}"])
        self.assertTrue(
            embedded["exact_official_tokens_inside_wrapper"]
        )
        self.assertFalse(embedded["contains_license_words"])


if __name__ == "__main__":
    unittest.main()
