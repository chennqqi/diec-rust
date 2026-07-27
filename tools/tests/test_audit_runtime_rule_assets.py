import hashlib
import importlib.util
import json
from pathlib import Path
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "tools" / "upstream" / "audit_runtime_rule_assets.py"
REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "runtime-rule-assets-license.json"
)
RUNTIME_REPORT_PATH = (
    ROOT / "docs" / "research" / "data" / "rquickjs-rule-runtime.json"
)
LOCK_PATH = ROOT / "upstream" / "components.lock.toml"
DETECT_ROOT = ROOT / "upstream" / "Detect-It-Easy"

SPEC = importlib.util.spec_from_file_location(
    "audit_runtime_rule_assets",
    SCRIPT_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class RuntimeRuleAssetLicenseAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        cls.runtime_report = json.loads(
            RUNTIME_REPORT_PATH.read_text(encoding="utf-8")
        )
        with LOCK_PATH.open("rb") as stream:
            cls.lock = tomllib.load(stream)

    def test_report_is_reproducible_from_pinned_subtree(self):
        self.assertEqual(MODULE.audit(DETECT_ROOT), self.report)
        self.assertEqual(self.report["schema_version"], 1)
        self.assertEqual(
            self.report["scope"]["commit"],
            self.lock["gitlink"]["Detect-It-Easy"]["commit"],
        )
        self.assertEqual(
            self.report["scope"]["trees"],
            ["db", "db_extra", "db_custom"],
        )

    def test_identity_binds_component_lock_and_root_license(self):
        identity = self.report["identity"]
        self.assertEqual(
            identity["component_lock_sha256"],
            hashlib.sha256(LOCK_PATH.read_bytes()).hexdigest(),
        )
        license_path = ROOT / identity["root_license"]
        self.assertEqual(
            identity["root_license_sha256"],
            hashlib.sha256(license_path.read_bytes()).hexdigest(),
        )
        self.assertEqual(identity["root_license_declared"], "MIT")
        self.assertEqual(
            identity["combined_tree_sha256"],
            "20f2b74effc2bdaf069e3b2e13060432b8890d38364511f5cde56a337348bfda",
        )

    def test_inventory_covers_programs_and_distribution_assets(self):
        inventory = self.report["inventory"]
        self.assertEqual(inventory["file_count"], 2268)
        self.assertEqual(inventory["byte_count"], 2_909_316)
        self.assertEqual(inventory["program_file_count"], 2235)
        self.assertEqual(inventory["program_byte_count"], 2_902_881)
        self.assertEqual(inventory["non_program_file_count"], 33)
        self.assertEqual(
            inventory["extension_counts"],
            {
                ".ini": 2,
                ".json": 3,
                ".png": 22,
                ".sg": 2175,
                ".txt": 6,
                "<none>": 60,
            },
        )
        self.assertEqual(
            [tree["file_count"] for tree in inventory["trees"]],
            [2124, 142, 2],
        )
        isolated = self.runtime_report["isolated_eval"]
        self.assertEqual(isolated["files"], inventory["program_file_count"])
        self.assertEqual(isolated["bytes"], inventory["program_byte_count"])

    def test_visible_license_markers_do_not_hide_unknown_provenance(self):
        markers = self.report["visible_markers"]
        self.assertEqual(markers["license_marker_counts"], {"mit": 1})
        self.assertEqual(
            markers["license_markers"],
            [
                {
                    "line": 73,
                    "marker": "mit",
                    "path": (
                        "db/PE/"
                        "__GenericHeuristicAnalysis_By_DosX.7.sg"
                    ),
                    "text": (
                        "//       │  ┌ Copyright (C) 2026 DosX. "
                        "MIT License.                    │"
                    ),
                }
            ],
        )
        self.assertEqual(markers["author_marker_file_count"], 2101)
        self.assertEqual(markers["unique_author_marker_count"], 65)
        self.assertEqual(markers["copyright_marker_file_count"], 7)
        self.assertEqual(markers["url_domain_counts"]["<invalid-url>"], 1)

    def test_binary_assets_are_hash_bound_pngs_and_review_remains_open(self):
        binary_assets = self.report["binary_assets"]
        self.assertEqual(len(binary_assets), 22)
        for asset in binary_assets:
            path = DETECT_ROOT / asset["path"]
            with self.subTest(path=asset["path"]):
                data = path.read_bytes()
                self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
                self.assertEqual(asset["bytes"], len(data))
                self.assertEqual(
                    asset["sha256"],
                    hashlib.sha256(data).hexdigest(),
                )
        findings = self.report["findings"]
        self.assertTrue(findings["all_runtime_assets_covered_by_tree_hash"])
        self.assertTrue(findings["root_mit_license_present"])
        self.assertEqual(
            findings["explicit_non_mit_license_marker_count"],
            0,
        )
        self.assertEqual(findings["binary_asset_count"], 22)
        self.assertFalse(findings["legal_review_complete"])
        self.assertEqual(len(findings["limitations"]), 4)


if __name__ == "__main__":
    unittest.main()
