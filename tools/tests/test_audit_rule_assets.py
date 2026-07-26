import importlib.util
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools/upstream/audit_rule_assets.py"
SPEC = importlib.util.spec_from_file_location(
    "audit_rule_assets", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class AuditRuleAssetsUnitTests(unittest.TestCase):
    def test_visible_markers_do_not_infer_unknown_license(self):
        data = (
            b"// Author: Example\n"
            b"// Please retain the copyright information\n"
        )
        self.assertEqual(
            MODULE.visible_markers(pathlib.Path("rule.yar"), data),
            ["author-metadata", "retain-copyright-request"],
        )

    def test_visible_markers_capture_explicit_and_generated_sources(self):
        data = (
            b"// GNU-GPLv2 license\n"
            b"YARA rules generated with ./peid2yara.py\n"
            b"https://raw.githubusercontent.com/example/db\n"
        )
        self.assertEqual(
            MODULE.visible_markers(pathlib.Path("peid.yar"), data),
            [
                "explicit-gpl-v2",
                "peid2yara-generated",
                "upstream-database-urls",
            ],
        )

    def test_inventory_counts_yara_rules_and_peid_sections(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "assets").mkdir()
            (root / "assets/rules.yar").write_bytes(
                b"private rule one {}\nglobal rule two {}\n"
            )
            (root / "assets/userdb.txt").write_bytes(
                b"; PEiD signature database - test\r\n"
                b"[one]\r\nsignature = 90\r\n"
                b"[ two ]\r\nsignature = 91\r\n"
            )
            result = MODULE.inventory(
                name="fixture",
                repository="fixture",
                commit="0" * 40,
                root=root,
                base=pathlib.Path("assets"),
                paths=[
                    pathlib.Path("assets/rules.yar"),
                    pathlib.Path("assets/userdb.txt"),
                ],
                include_history=False,
            )
        self.assertEqual(result["file_count"], 2)
        self.assertEqual(result["yara_rule_count"], 2)
        self.assertEqual(result["peid_section_count"], 2)
        self.assertEqual(
            result["files"][1]["visible_markers"],
            ["peid-category-header"],
        )
        self.assertEqual(result["files"][1]["newline_style"], "crlf")

    def test_tree_digest_binds_path_size_and_content(self):
        records = [
            {"path": "a", "bytes": 1, "sha256": "1" * 64},
            {"path": "b", "bytes": 2, "sha256": "2" * 64},
        ]
        first = MODULE.tree_sha256(records)
        records[1]["path"] = "c"
        self.assertNotEqual(first, MODULE.tree_sha256(records))

    def test_comparison_preserves_all_differences(self):
        left = {
            "name": "left",
            "files": [
                {"path": "same", "sha256": "a"},
                {"path": "changed", "sha256": "b"},
                {"path": "left-only", "sha256": "c"},
            ],
        }
        right = {
            "name": "right",
            "files": [
                {"path": "same", "sha256": "a"},
                {"path": "changed", "sha256": "d"},
                {"path": "right-only", "sha256": "e"},
            ],
        }
        result = MODULE.compare_inventories(left, right)
        self.assertEqual(result["common_path_count"], 2)
        self.assertEqual(result["byte_exact_paths"], ["same"])
        self.assertEqual(result["modified_common_paths"], ["changed"])
        self.assertEqual(result["left_only_paths"], ["left-only"])
        self.assertEqual(result["right_only_paths"], ["right-only"])


if __name__ == "__main__":
    unittest.main()
