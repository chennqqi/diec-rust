import hashlib
import importlib.util
import io
import json
import pathlib
import tarfile
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
REPORT_PATH = ROOT / "docs/research/data/rar-decoder-origin.json"
TOOL_PATH = ROOT / "tools/upstream/audit_rar_decoder_origin.py"
SPEC = importlib.util.spec_from_file_location(
    "audit_rar_decoder_origin", TOOL_PATH
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class RarDecoderOriginReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    def test_report_identity_and_relationships_are_fixed(self):
        self.assertEqual(self.report["schema_version"], 2)
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
        self.assertEqual(reference["mirror_update_label"], "7.1.10")
        self.assertEqual(reference["source_version"], "7.13")
        self.assertEqual(reference["source_date"], "2025-07-28")
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

    def test_official_archive_closes_the_mirror_identity(self):
        official = self.report["official_release"]
        self.assertEqual(
            official["archive_url"], MODULE.UNRAR_OFFICIAL_ARCHIVE_URL
        )
        self.assertEqual(
            official["archive_sha256"],
            MODULE.UNRAR_OFFICIAL_ARCHIVE_SHA256,
        )
        self.assertEqual(official["archive_bytes"], 268008)
        self.assertEqual(official["source_version"], "7.13")
        self.assertEqual(official["source_date"], "2025-07-28")
        self.assertEqual(
            official["license"], self.report["reference"]["license"]
        )
        self.assertEqual(
            official["readme"], self.report["reference"]["readme"]
        )
        comparison = official["archive_to_mirror"]
        self.assertEqual(comparison["official_regular_file_count"], 159)
        self.assertEqual(comparison["byte_identical_file_count"], 153)
        self.assertEqual(
            set(comparison["line_ending_only_files"]),
            MODULE.EXPECTED_LINE_ENDING_ONLY_PATHS,
        )
        self.assertEqual(comparison["content_mismatch_files"], [])
        self.assertEqual(comparison["missing_in_mirror"], [])

    def test_reuse_and_fixture_decisions_remain_closed(self):
        observation = self.report["license_observation"]
        constraint = self.report["implementation_constraint"]
        self.assertFalse(observation["legal_review_complete"])
        self.assertFalse(
            observation["third_party_attribution_review_complete"]
        )
        self.assertFalse(
            observation[
                "decoder_files_contain_official_third_party_acknowledgments"
            ]
        )
        self.assertTrue(
            observation[
                "official_acknowledgments_include_public_domain_and_bsd"
            ]
        )
        self.assertFalse(constraint["copy_or_translation_approved"])
        self.assertFalse(
            constraint["compressed_fixture_redistribution_approved"]
        )
        self.assertFalse(
            constraint["oracle_use_copies_decoder_into_project"]
        )

    def test_official_archive_parser_rejects_unsafe_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "unsafe.tar.gz"
            with tarfile.open(path, "w:gz") as archive:
                info = tarfile.TarInfo("../escape")
                payload = b"unsafe"
                info.size = len(payload)
                archive.addfile(info, io.BytesIO(payload))
            with self.assertRaisesRegex(
                ValueError, "unsafe official archive member"
            ):
                MODULE.read_official_archive(
                    path, hashlib.sha256(path.read_bytes()).hexdigest()
                )

    def test_line_ending_normalization_is_narrow(self):
        self.assertEqual(
            MODULE.normalize_line_endings(b"a\r\nb\n"), b"a\nb\n"
        )
        self.assertNotEqual(
            MODULE.normalize_line_endings(b"content-a"),
            MODULE.normalize_line_endings(b"content-b"),
        )

    def test_report_has_no_checkout_or_local_archive_paths(self):
        serialized = REPORT_PATH.read_text(encoding="utf-8")
        self.assertNotIn(str(ROOT), serialized)
        self.assertNotIn("I:\\\\tmp", serialized)
        self.assertNotIn("/tmp/", serialized)


if __name__ == "__main__":
    unittest.main()
