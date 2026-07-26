import collections
import hashlib
import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
REPORT_PATH = (
    ROOT / "docs/research/data/yara-license-closure-linux.json"
)
TOOL_PATH = ROOT / "tools/upstream/audit_yara_license_closure.py"
LOCK_PATH = ROOT / "upstream/components.lock.toml"


class YaraLicenseClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    def test_report_is_bound_to_generator_lock_and_sources(self):
        self.assertEqual(self.report["schema_version"], 1)
        self.assertEqual(
            self.report["generator"],
            "tools/upstream/audit_yara_license_closure.py",
        )
        self.assertEqual(
            self.report["generator_sha256"],
            hashlib.sha256(TOOL_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            self.report["component_lock"]["sha256"],
            hashlib.sha256(LOCK_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            self.report["upstream_commit"],
            "74eaf505c250ab47e709024e9dc41657cd8f2254",
        )
        self.assertEqual(
            self.report["xyara_commit"],
            "34a733e9c733669ad8dcaf4588d51197a08545e3",
        )
        self.assertEqual(
            self.report["official_yara"]["commit"],
            "688268d83983a0d61bb68ef3d8dfd28102b7d1b4",
        )
        self.assertEqual(self.report["official_yara"]["version"], "4.5.2")
        self.assertEqual(
            self.report["official_tlshc"]["commit"],
            "bb91fef822a21d480a6bee2a8d693965b5bca16e",
        )
        self.assertEqual(
            self.report["source_image"]["revision"],
            self.report["upstream_commit"],
        )

    def test_build_and_dependency_closure_are_exact(self):
        self.assertTrue(all(self.report["relationships"].values()))
        self.assertEqual(self.report["build"]["object_count"], 51)
        self.assertEqual(len(self.report["build"]["archive_members"]), 51)
        self.assertEqual(self.report["compile_source_count"], 51)
        self.assertEqual(len(self.report["compile_units"]), 51)
        self.assertEqual(self.report["closure_file_count"], 109)
        self.assertEqual(
            self.report["build"]["archive_sha256"],
            "2a7db6ee2b0191a6092afe3c27640e98702d2b363d01d93e33afe7d2a29d85c9",
        )
        self.assertNotIn(
            "-DHAVE_LIBCRYPTO",
            self.report["build"]["compile_definitions"],
        )

    def test_file_markers_and_generated_parsers_are_auditable(self):
        marker_counts = collections.Counter(
            marker
            for record in self.report["files"]
            for marker in record["license_markers"]
        )
        self.assertEqual(
            marker_counts,
            {
                "bison-gpl3": 6,
                "bison-special-exception": 6,
                "yara-bsd": 89,
            },
        )
        self.assertEqual(
            {
                record["path"]
                for record in self.report["generated_bison_parsers"]
            },
            {
                "src/grammar.c",
                "src/grammar.h",
                "src/hex_grammar.c",
                "src/hex_grammar.h",
                "src/re_grammar.c",
                "src/re_grammar.h",
            },
        )
        self.assertTrue(
            all(
                record["license_markers"]
                == ["bison-gpl3", "bison-special-exception"]
                for record in self.report["generated_bison_parsers"]
            )
        )

    def test_official_yara_mapping_records_all_local_changes(self):
        comparison = self.report["source_comparison"]
        self.assertEqual(comparison["vendored_file_count"], 132)
        self.assertEqual(comparison["official_file_count"], 139)
        self.assertEqual(comparison["mapped_file_count"], 132)
        self.assertEqual(comparison["exact_file_count"], 129)
        self.assertEqual(
            [
                record["vendored_path"]
                for record in comparison["modified_files"]
            ],
            [
                "include/yara/unaligned.h",
                "simple_str.c",
                "strutils.c",
            ],
        )
        self.assertEqual(
            comparison["renamed_exact_files"][0]["vendored_path"],
            "_hash.c",
        )

    def test_tlshc_provenance_and_notices_are_fixed(self):
        provenance = self.report["tlshc_provenance"]
        self.assertEqual(
            provenance["license_expression"],
            "Apache-2.0 OR BSD-3-Clause",
        )
        self.assertEqual(len(provenance["files"]), 6)
        self.assertTrue(
            all(
                record["vendored_equals_yara_v4_5_2"]
                and record["yara_import_equals_tlshc"]
                and not record["inline_license_markers"]
                for record in provenance["files"]
            )
        )
        evidence = {
            record["label"]: record["sha256"]
            for record in provenance["license_evidence"]
        }
        self.assertEqual(
            evidence,
            {
                "avast/tlshc LICENSE": (
                    "ad18f3db3225882e03535e586402699684c744115a667dbbc240ef02b16fdbfc"
                ),
                "avast/tlshc NOTICE.txt": (
                    "84a6a091e05230fd03d7d57f0423d6ac45fdc217dcf997058b255bef530d51c6"
                ),
            },
        )

    def test_authenticode_is_vendored_mit_but_not_built(self):
        parser = self.report["authenticode_parser"]
        self.assertEqual(parser["license_expression"], "MIT")
        self.assertEqual(parser["vendored_file_count"], 10)
        self.assertEqual(parser["compiled_or_included_file_count"], 0)
        self.assertTrue(
            all(
                record["license_markers"]
                == ["avast-mit", "mit-permission"]
                for record in parser["files"]
            )
        )

    def test_optimizer_warnings_remain_visible(self):
        warnings = self.report["build"]["warnings"]
        self.assertEqual(len(warnings), 12)
        counts = collections.Counter(
            (record["path"], record["line"], record["option"])
            for record in warnings
        )
        self.assertEqual(
            counts,
            {
                ("src/atoms.c", 730, "-Wstringop-overflow="): 3,
                ("src/atoms.c", 731, "-Wstringop-overflow="): 3,
                ("src/atoms.c", 1396, "-Wstringop-overflow="): 3,
                ("src/atoms.c", 1397, "-Wstringop-overflow="): 3,
            },
        )


if __name__ == "__main__":
    unittest.main()
