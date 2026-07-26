import hashlib
import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
REPORT_PATH = (
    ROOT / "docs/research/data/component-license-inventory-linux.json"
)
TOOL_PATH = ROOT / "tools/upstream/audit_component_licenses.py"
LOCK_PATH = ROOT / "upstream/components.lock.toml"


class ComponentLicenseInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    def test_report_identity_is_fixed(self):
        self.assertEqual(self.report["schema_version"], 1)
        self.assertEqual(
            self.report["generator"],
            "tools/upstream/audit_component_licenses.py",
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

    def test_all_direct_components_are_commit_and_license_bound(self):
        self.assertEqual(self.report["component_count"], 58)
        self.assertEqual(len(self.report["components"]), 58)
        self.assertTrue(all(self.report["relationships"].values()))
        for component in self.report["components"]:
            self.assertEqual(
                component["actual_commit"],
                component["expected_commit"],
            )
            self.assertEqual(component["root_license_count"], 1)
            self.assertTrue(component["root_license_is_mit"])
            self.assertEqual(component["nested_gitmodules"], [])

    def test_root_mit_attribution_is_not_one_shared_blob(self):
        root_hashes = {
            license_file["sha256"]
            for component in self.report["components"]
            for license_file in component["license_files"]
            if "/" not in license_file["path"]
        }
        self.assertEqual(len(root_hashes), 12)

    def test_bundled_license_candidates_are_explicit(self):
        nested_counts = {
            component["name"]: sum(
                "/" in license_file["path"]
                for license_file in component["license_files"]
            )
            for component in self.report["components"]
        }
        self.assertEqual(
            {name: count for name, count in nested_counts.items() if count},
            {
                "Detect-It-Easy": 41,
                "XArchive": 2,
                "XCapstone": 2,
            },
        )
        self.assertEqual(self.report["license_file_count"], 103)


if __name__ == "__main__":
    unittest.main()
