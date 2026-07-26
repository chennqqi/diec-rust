import collections
import hashlib
import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
REPORT_PATH = ROOT / "docs/research/data/rule-assets.json"
TOOL_PATH = ROOT / "tools/upstream/audit_rule_assets.py"
LOCK_PATH = ROOT / "upstream/components.lock.toml"


class RuleAssetReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        cls.sets = {
            item["name"]: item for item in cls.report["asset_sets"]
        }

    def test_report_is_bound_to_generator_lock_image_and_commits(self):
        self.assertEqual(self.report["schema_version"], 1)
        self.assertEqual(
            self.report["generator"],
            "tools/upstream/audit_rule_assets.py",
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
            self.report["source_image"]["revision"],
            self.report["upstream_commit"],
        )
        self.assertEqual(
            {
                name: item["commit"]
                for name, item in self.sets.items()
            },
            {
                "detect-release-yara": (
                    "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
                ),
                "detect-release-peid": (
                    "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
                ),
                "xyara-component-yara": (
                    "34a733e9c733669ad8dcaf4588d51197a08545e3"
                ),
                "xpeid-component-peid": (
                    "15c2e2951ab2443c7794e8f88c9fc5c65b217f28"
                ),
                "signatures-component-data": (
                    "5d80fb2863d02e9366aee7b3ade6abb7d6598dbb"
                ),
            },
        )

    def test_asset_counts_and_tree_hashes_are_exact(self):
        observed = {
            name: (
                item["file_count"],
                item["yara_rule_count"],
                item["peid_section_count"],
                item["tree_sha256"],
            )
            for name, item in self.sets.items()
        }
        self.assertEqual(
            observed,
            {
                "detect-release-yara": (
                    8,
                    10056,
                    0,
                    "24684a5ca84971ec11aac060955ad77f255ec58195e1a44551cd3c965422501f",
                ),
                "detect-release-peid": (
                    11,
                    0,
                    8890,
                    "9333a04068a80b2e3349477cfd8080c684b58fcb61e08ad2525c58355e4f9d38",
                ),
                "xyara-component-yara": (
                    10,
                    10069,
                    0,
                    "a9ca2ae58309386ec9b6045eae5344fbf4873adc6449a832ea2749428196f3df",
                ),
                "xpeid-component-peid": (
                    14,
                    0,
                    4136,
                    "8423847fa72e06444dfcc20c3914b14c2140ee222006ea92e89aab355f4eb331",
                ),
                "signatures-component-data": (
                    4,
                    0,
                    0,
                    "0cc6bff37cc9a65260ee0a8aec30d852639029eec0be9d229ee1ad610a7d40a5",
                ),
            },
        )

    def test_release_and_component_trees_are_explicitly_distinct(self):
        yara = self.report["comparisons"][
            "yara_release_vs_component"
        ]
        self.assertEqual(yara["common_path_count"], 8)
        self.assertEqual(yara["byte_exact_count"], 0)
        self.assertEqual(
            yara["right_only_paths"],
            ["DosX_Heuristic.yar", "info.ini"],
        )
        peid = self.report["comparisons"][
            "peid_release_vs_component"
        ]
        self.assertEqual(peid["common_path_count"], 8)
        self.assertEqual(peid["byte_exact_count"], 0)
        self.assertEqual(
            peid["left_only_paths"],
            [
                "PE/file_format.userdb.txt",
                "PE/split_userdb.ps1",
                "PE/userdb.txt",
            ],
        )
        self.assertEqual(
            peid["right_only_paths"],
            [
                "Binary/archive.userdb.txt",
                "Binary/file_format.userdb.txt",
                "COM/packer.userdb.txt",
                "MSDOS/dos_extender.userdb.txt",
                "PE/crypter.userdb.txt",
                "info.ini",
            ],
        )

    def test_visible_markers_do_not_hide_mixed_or_unknown_provenance(self):
        yara = self.sets["xyara-component-yara"]["files"]
        marker_counts = collections.Counter(
            marker
            for record in yara
            for marker in record["visible_markers"]
        )
        self.assertEqual(marker_counts["explicit-gpl-v2"], 3)
        self.assertEqual(
            marker_counts["retain-copyright-request"], 3
        )
        self.assertEqual(marker_counts["peid2yara-generated"], 1)
        self.assertEqual(marker_counts["upstream-database-urls"], 1)
        peid = self.sets["xpeid-component-peid"]["files"]
        self.assertEqual(
            sum(
                "peid-category-header" in record["visible_markers"]
                for record in peid
            ),
            13,
        )
        signatures = self.sets["signatures-component-data"]["files"]
        self.assertTrue(
            all(not record["visible_markers"] for record in signatures)
        )
        self.assertTrue(
            all(
                record["first_nonempty_line"] == "MIT License"
                for record in self.report[
                    "root_license_evidence"
                ].values()
            )
        )

    def test_component_assets_have_file_history(self):
        for set_name in (
            "xyara-component-yara",
            "xpeid-component-peid",
            "signatures-component-data",
        ):
            for record in self.sets[set_name]["files"]:
                self.assertRegex(
                    record["history"]["first"]["commit"],
                    r"^[0-9a-f]{40}$",
                )
                self.assertRegex(
                    record["history"]["last"]["commit"],
                    r"^[0-9a-f]{40}$",
                )
                self.assertGreaterEqual(
                    record["history"]["commit_count"], 1
                )

    def test_reachability_and_packaging_claims_are_all_proven(self):
        self.assertTrue(all(self.report["relationships"].values()))
        self.assertTrue(
            all(
                self.report["reachability"][
                    "relationships"
                ].values()
            )
        )
        self.assertEqual(
            self.report["reachability"][
                "current_die_cli_does_not_load"
            ],
            [
                "Detect-It-Easy/yara_rules",
                "Detect-It-Easy/peid_rules",
                "XYara/yara_rules",
                "XPEID/peid",
                "signatures/*.db",
            ],
        )


if __name__ == "__main__":
    unittest.main()
