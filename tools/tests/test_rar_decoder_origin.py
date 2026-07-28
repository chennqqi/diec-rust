import hashlib
import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
REPORT_PATH = ROOT / "docs/research/data/rar-decoder-origin.json"
TOOL_PATH = ROOT / "tools/upstream/audit_rar_decoder_origin.py"


class RarDecoderOriginReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    def test_report_identity_and_relationships_are_fixed(self):
        self.assertEqual(self.report["schema_version"], 1)
        self.assertEqual(
            self.report["generator"],
            "tools/upstream/audit_rar_decoder_origin.py",
        )
        self.assertEqual(
            self.report["generator_sha256"],
            hashlib.sha256(TOOL_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            self.report["upstream_commit"],
            "74eaf505c250ab47e709024e9dc41657cd8f2254",
        )
        self.assertTrue(all(self.report["relationships"].values()))

    def test_xarchive_decoder_and_introduction_are_content_bound(self):
        xarchive = self.report["xarchive"]
        self.assertEqual(
            xarchive["commit"],
            "0fcd4e8d3e9933baac3b12246d82ac026557ffd0",
        )
        self.assertEqual(
            xarchive["introduction"]["commit"],
            "d48321dcc54b5011756853437de1a7220fd2a440",
        )
        self.assertEqual(xarchive["decoder_token_count"], 26627)
        self.assertEqual(
            {
                item["path"]: item["sha256"]
                for item in xarchive["decoder_files"]
            },
            {
                "Algos/xrardecoder.cpp": (
                    "55f36d7b0188f5093ffad5723637fedaf"
                    "ae32321b1fde3cf2f81ff5983e94026"
                ),
                "Algos/xrardecoder.h": (
                    "29e0f4e1091df88f992f2cf5688df044"
                    "bfbb46e607cb6536cbd5b4e234665540"
                ),
            },
        )
        self.assertEqual(
            {
                item["path"]: item["sha256"]
                for item in xarchive["introduction"]["files"]
            },
            {
                "Algos/xrardecoder.cpp": (
                    "45f99e3e7d3776f7ca1f052952c52763"
                    "3039fc576eff970256a7dd2bcf5648f0"
                ),
                "Algos/xrardecoder.h": (
                    "00f648b00d9fcdd5fc1b7fd0c4f71a86"
                    "d50a3fd5bb51d5e2280113edaca2312f"
                ),
            },
        )

    def test_unrar_reference_and_overlap_are_content_bound(self):
        reference = self.report["reference"]
        self.assertEqual(
            reference["commit"],
            "9f1ce54025e0175634cbdb21b06341aa29eba591",
        )
        self.assertEqual(reference["mirror_release"], "7.1.10")
        self.assertEqual(reference["source_file_count"], 150)
        self.assertEqual(
            reference["license"]["sha256"],
            "6ecc1687808b7d66b24f874755abfed74"
            "64d9751ed0001cd4e8e5d9bf397ff8a",
        )
        evidence = {
            item["shingle_length"]: item
            for item in self.report["comparison"]["shingle_evidence"]
        }
        self.assertEqual(evidence[12]["covered_token_count"], 25086)
        self.assertEqual(evidence[64]["covered_token_count"], 19759)
        self.assertEqual(evidence[64]["unique_origin_file_count"], 17)
        self.assertEqual(
            {
                item["path"]
                for item in evidence[64]["unique_origin_files"]
            },
            {
                "compress.hpp",
                "getbits.cpp",
                "getbits.hpp",
                "largepage.hpp",
                "model.cpp",
                "model.hpp",
                "rarvm.cpp",
                "suballoc.cpp",
                "suballoc.hpp",
                "unpack.cpp",
                "unpack.hpp",
                "unpack15.cpp",
                "unpack20.cpp",
                "unpack30.cpp",
                "unpack50.cpp",
                "unpack50frag.cpp",
                "unpackinline.cpp",
            },
        )

    def test_reuse_and_fixture_decisions_remain_closed(self):
        observation = self.report["license_observation"]
        constraint = self.report["implementation_constraint"]
        self.assertFalse(observation["legal_review_complete"])
        self.assertFalse(constraint["copy_or_translation_approved"])
        self.assertFalse(
            constraint["compressed_fixture_redistribution_approved"]
        )
        self.assertFalse(
            constraint["oracle_use_copies_decoder_into_project"]
        )


if __name__ == "__main__":
    unittest.main()
