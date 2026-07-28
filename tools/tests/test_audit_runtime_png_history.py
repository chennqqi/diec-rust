import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT
    / "tools"
    / "upstream"
    / "audit_runtime_png_history.py"
)
REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "runtime-png-history.json"
)
RUNTIME_REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "runtime-rule-assets-license.json"
)
DOCUMENT_PATH = (
    ROOT / "docs" / "research" / "runtime-png-provenance.md"
)
SPEC = importlib.util.spec_from_file_location(
    "audit_runtime_png_history",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

FIRST = "62432a2608cf114a8ae881fbad40bb8e2e3335fc"
SECOND = "ae8ec5903a3bf1c3c6c4e674a37b84e7e97dc91a"


class RuntimePngHistoryAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = json.loads(
            REPORT_PATH.read_text(encoding="utf-8")
        )

    def test_report_is_exact_reproducible_audit(self):
        self.assertEqual(MODULE.audit(), self.report)
        self.assertEqual(self.report["schema_version"], 1)
        self.assertEqual(
            self.report["generator"],
            "tools/upstream/audit_runtime_png_history.py",
        )
        self.assertEqual(
            self.report["generator_sha256"],
            hashlib.sha256(MODULE_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            self.report["scope"]["commit"],
            "c2c17dfa5ea4e078ba31eab55d87430c96622fb6",
        )
        self.assertEqual(self.report["scope"]["asset_count"], 22)
        self.assertEqual(
            self.report["identity"]["runtime_asset_report_sha256"],
            hashlib.sha256(
                RUNTIME_REPORT_PATH.read_bytes()
            ).hexdigest(),
        )

    def test_all_assets_bind_subtree_git_blob_and_png_structure(self):
        runtime_report = json.loads(
            RUNTIME_REPORT_PATH.read_text(encoding="utf-8")
        )
        runtime_assets = {
            asset["path"]: asset
            for asset in runtime_report["binary_assets"]
        }
        self.assertEqual(len(self.report["assets"]), 22)
        self.assertEqual(
            {asset["path"] for asset in self.report["assets"]},
            set(runtime_assets),
        )
        for asset in self.report["assets"]:
            with self.subTest(asset=asset["path"]):
                data = (
                    ROOT
                    / "upstream"
                    / "Detect-It-Easy"
                    / asset["path"]
                ).read_bytes()
                self.assertEqual(asset["bytes"], len(data))
                self.assertEqual(
                    asset["sha256"],
                    hashlib.sha256(data).hexdigest(),
                )
                self.assertEqual(
                    asset["git_blob_oid"],
                    MODULE.git_blob_oid(data),
                )
                self.assertEqual(
                    asset["png"]["ihdr"],
                    {
                        "bit_depth": 8,
                        "color_type": 6,
                        "compression": 0,
                        "filter": 0,
                        "height": 16,
                        "interlace": 0,
                        "width": 16,
                    },
                )
                self.assertTrue(
                    all(
                        chunk["crc_valid"]
                        for chunk in asset["png"]["chunks"]
                    )
                )
                self.assertFalse(
                    asset["png"][
                        "has_license_or_attribution_text"
                    ]
                )
                self.assertEqual(
                    asset["sha256"],
                    runtime_assets[asset["path"]]["sha256"],
                )

    def test_history_commits_and_three_history_counts_are_exact(self):
        commits = self.report["history_commits"]
        self.assertEqual(
            [record["commit"] for record in commits],
            [FIRST, SECOND],
        )
        self.assertEqual(
            [record["subject"] for record in commits],
            [
                "Add icon images for various detection types",
                "Add new icon files and rename library icon",
            ],
        )
        for record in commits:
            with self.subTest(commit=record["commit"]):
                self.assertEqual(
                    record["author"],
                    record["committer"],
                )
                self.assertEqual(
                    record["author"]["name"],
                    "DosX",
                )
                self.assertEqual(
                    record["author"]["email"],
                    "collab@kay-software.ru",
                )
                self.assertFalse(record["gpg_signature_present"])
                self.assertEqual(record["signed_off_by"], [])
                self.assertTrue(
                    record["root_license"]["declares_mit"]
                )
                self.assertEqual(
                    record["root_license"]["sha256"],
                    (
                        "5203a1e5b50c6fcaf9127174aecf01fb"
                        "179a296a85cb963735b3895693f887ad"
                    ),
                )

        summary = self.report["summary"]
        self.assertEqual(
            summary["asset_introduction_counts"],
            {FIRST: 18, SECOND: 4},
        )
        self.assertEqual(
            summary["current_path_first_counts"],
            {FIRST: 17, SECOND: 5},
        )
        self.assertEqual(
            summary["lineage_first_counts"],
            {FIRST: 20, SECOND: 2},
        )
        self.assertEqual(summary["history_commit_count"], 2)
        self.assertEqual(summary["unique_blob_count"], 20)
        self.assertEqual(summary["content_change_after_add_count"], 0)

    def test_copy_rename_and_embedded_software_are_explicit(self):
        summary = self.report["summary"]
        self.assertEqual(
            summary["copy_assets"],
            [
                "db/_icons/archive.png",
                "db/_icons/package.png",
            ],
        )
        self.assertEqual(
            summary["rename_assets"],
            ["db/_icons/library, module.png"],
        )
        self.assertEqual(
            summary["software_text_counts"],
            {
                "paint.net 4.0.2": 2,
                "paint.net 4.0.3": 1,
            },
        )
        self.assertEqual(
            summary["license_or_attribution_text_asset_count"],
            0,
        )
        by_path = {
            asset["path"]: asset for asset in self.report["assets"]
        }
        self.assertIn(
            "C100",
            {
                change["status"]
                for event in by_path[
                    "db/_icons/archive.png"
                ]["history"]["changes_newest_first"]
                for change in event["changes"]
            },
        )
        self.assertIn(
            "R100",
            {
                change["status"]
                for event in by_path[
                    "db/_icons/library, module.png"
                ]["history"]["changes_newest_first"]
                for change in event["changes"]
            },
        )

    def test_contribution_policy_and_legal_boundary_are_exact(self):
        policy = self.report["contribution_policy"]
        self.assertEqual(
            [
                record["candidate_count"]
                for record in policy["origin_commits"]
            ],
            [0, 0],
        )
        self.assertEqual(policy["pinned"]["candidate_count"], 1)
        candidate = policy["pinned"]["candidates"][0]
        self.assertEqual(candidate["path"], "CONTRIBUTING.md")
        self.assertFalse(
            candidate["mentions_license_or_copyright"]
        )
        self.assertFalse(candidate["mentions_cla_dco_or_signoff"])

        findings = self.report["findings"]
        self.assertTrue(
            findings[
                "all_subtree_bytes_match_pinned_original_blobs"
            ]
        )
        self.assertTrue(findings["all_png_chunk_crcs_are_valid"])
        self.assertTrue(findings["all_pngs_are_16x16_rgba8"])
        self.assertTrue(
            findings["all_history_commits_are_pinned_ancestors"]
        )
        self.assertTrue(
            findings["all_origin_commits_have_root_mit_text"]
        )
        self.assertTrue(
            findings["pinned_root_license_has_mit_text"]
        )
        self.assertFalse(
            findings["origin_license_blob_matches_pinned"]
        )
        self.assertFalse(
            findings[
                "asset_license_or_attribution_metadata_present"
            ]
        )
        self.assertTrue(
            findings["pinned_contribution_policy_file_present"]
        )
        self.assertFalse(
            findings["origin_contribution_policy_file_present"]
        )
        self.assertFalse(
            findings[
                "pinned_policy_explicit_license_or_dco_cla_present"
            ]
        )
        self.assertFalse(
            findings[
                "origin_commit_signature_or_signoff_present"
            ]
        )
        self.assertFalse(findings["legal_review_complete"])
        self.assertEqual(len(findings["limitations"]), 5)

    def test_png_parser_rejects_crc_corruption(self):
        asset_path = (
            ROOT
            / "upstream"
            / "Detect-It-Easy"
            / self.report["assets"][0]["path"]
        )
        corrupted = bytearray(asset_path.read_bytes())
        corrupted[29] ^= 1
        with self.assertRaisesRegex(
            MODULE.AuditError,
            "chunk CRC",
        ):
            MODULE.parse_png(bytes(corrupted))

    def test_research_document_binds_report_and_open_review(self):
        document = DOCUMENT_PATH.read_text(encoding="utf-8")
        self.assertIn(
            hashlib.sha256(REPORT_PATH.read_bytes()).hexdigest(),
            document,
        )
        for token in (
            FIRST,
            SECOND,
            "C100",
            "R100",
            "legal_review_complete = false",
            "P0-BLOCK-004",
        ):
            self.assertIn(token, document)


if __name__ == "__main__":
    unittest.main()
