import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT / "tools" / "upstream" / "probe_qt6_result_model.py"
)
REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "result-model-engine-qt6.json"
)
IMAGE_IDS = {
    "metadata": (
        "sha256:50a28ac93d422b86246be12da48e0c25"
        "ed71786cb8a069b32d436fcf44679cfa"
    ),
    "lists": (
        "sha256:7b3f4b9f9a87a6cf07a2c9a6dafdf32c"
        "c5020071174bcb0e89f2e86842645444"
    ),
    "ids": (
        "sha256:5a705ac19dbcff4ff3d72710dfaa454240"
        "1cb4e04414d896606e8812f2105bc4"
    ),
    "flags": (
        "sha256:7476806c3f776636993bf0c48911557dcd"
        "e1d677c2d960a5336ca81101153fe6"
    ),
    "enums": (
        "sha256:ea9e04d6ad279f7c058e58571ace05313c"
        "95ff3cb4e4c8a05d322d999810c434"
    ),
}
SPEC = importlib.util.spec_from_file_location(
    "probe_qt6_result_model",
    MODULE_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ProbeQt6ResultModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    def test_bundle_and_underlying_probe_identities_are_fixed(self):
        self.assertEqual(self.report["schema_version"], 1)
        self.assertEqual(self.report["generator"], MODULE.GENERATOR)
        self.assertEqual(
            self.report["generator_sha256"],
            hashlib.sha256(MODULE_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(self.report["result"], "observed")
        self.assertEqual(set(self.report["reports"]), set(MODULE.PROFILES))
        for profile, specification in MODULE.PROFILES.items():
            path = ROOT / specification["probe"]
            self.assertEqual(
                self.report["underlying_probes"][
                    specification["probe"]
                ],
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )

    def test_all_qt6_harnesses_pass_the_original_relationships(self):
        for profile, report in self.report["reports"].items():
            with self.subTest(profile=profile):
                self.assertEqual(
                    report["oracle"]["image_id"],
                    IMAGE_IDS[profile],
                )
                self.assertEqual(report["oracle"]["exit_code"], 0)
                self.assertEqual(report["oracle"]["raw_stderr_bytes"], 0)
                self.assertTrue(all(report["relationships"].values()))

    def test_all_qt5_differences_are_explicitly_classified(self):
        expected_paths = {
            "metadata": {
                f"cases/{index}/nScanTime" for index in range(4)
            },
            "lists": {"cases/1/errors/1/message"},
            "ids": {
                "records/0/id/uuid",
                "records/1/id/uuid",
                "records/1/parent_id/uuid",
            },
            "flags": set(),
            "enums": set(),
        }
        for profile, comparison in self.report["comparisons"].items():
            with self.subTest(profile=profile):
                self.assertTrue(comparison["relationships_equal"])
                self.assertTrue(comparison["fixture_equal"])
                self.assertTrue(comparison["differences_classified"])
                self.assertEqual(
                    {
                        item["path"]
                        for item in comparison[
                            "harness_output_differences"
                        ]
                    },
                    expected_paths[profile],
                )
                qt5_path = ROOT / comparison["qt5_report"]
                self.assertEqual(
                    comparison["qt5_report_sha256"],
                    hashlib.sha256(qt5_path.read_bytes()).hexdigest(),
                )

    def test_record_metadata_sources_cover_result_six(self):
        self.assertIn(
            "CAP-RESULT-006",
            self.report["capability_scope"],
        )
        comparison = self.report["record_metadata_comparison"]
        self.assertEqual(comparison["common_record_count"], 47)
        self.assertTrue(all(comparison["facts"].values()))
        self.assertEqual(
            comparison["qt5_only_record_paths"],
            [
                (
                    "isolated_query_conversions/cyclic_array_count/"
                    "observation/final_records/0"
                ),
                "missing_arguments/count/records/0",
                "missing_arguments/is_present/records/0",
                "missing_arguments/set_result/records/0",
            ],
        )
        self.assertEqual(comparison["qt6_only_record_paths"], [])
        for relative_path, expected_hash in comparison[
            "sources"
        ].items():
            self.assertEqual(
                expected_hash,
                hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest(),
            )

    def test_research_document_binds_current_report_and_images(self):
        document = (
            ROOT / "docs/research/qt6-result-model-runtime-evidence.md"
        ).read_text(encoding="utf-8")
        self.assertIn(
            hashlib.sha256(REPORT_PATH.read_bytes()).hexdigest(),
            document,
        )
        for image_id in IMAGE_IDS.values():
            self.assertIn(image_id, document)


if __name__ == "__main__":
    unittest.main()
