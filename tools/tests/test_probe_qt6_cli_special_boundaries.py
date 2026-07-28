import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT / "tools" / "upstream" / "probe_qt6_cli_special_boundaries.py"
)
UNDERLYING_PATH = (
    ROOT / "tools" / "upstream" / "probe_cli_special_boundaries.py"
)
REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "cli-special-boundaries-linux-qt5-qt6.json"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_qt6_cli_special_boundaries",
    MODULE_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ProbeQt6CliSpecialBoundariesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    def test_report_identity_is_fixed(self):
        self.assertEqual(self.report["schema_version"], 1)
        self.assertEqual(self.report["generator"], MODULE.GENERATOR)
        self.assertEqual(
            self.report["generator_sha256"],
            hashlib.sha256(MODULE_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            self.report["underlying_probe"],
            {
                "path": MODULE.UNDERLYING_PROBE,
                "sha256": hashlib.sha256(
                    UNDERLYING_PATH.read_bytes()
                ).hexdigest(),
            },
        )
        self.assertEqual(self.report["result"], "equal")
        self.assertEqual(self.report["case_count"], 28)
        self.assertEqual(self.report["upstream_commit"], "74eaf505c250ab47e709024e9dc41657cd8f2254")

    def test_both_fixed_oracles_are_admitted(self):
        self.assertEqual(
            [oracle["name"] for oracle in self.report["oracles"]],
            ["linux-qt5-cmake", "linux-qt6-cmake"],
        )
        self.assertEqual(
            [oracle["image_id"] for oracle in self.report["oracles"]],
            [
                "sha256:466102628c3a94b7ab1048f0c24261b1920e61a40029b128763cf79370255040",
                "sha256:e015495c313d0715f0b80f395da983a113a439f2a135eb637e9f0638c225200b",
            ],
        )
        self.assertTrue(
            all(
                case["all_oracles_equal"]
                for case in self.report["cases"].values()
            )
        )

    def test_relationships_retain_full_boundary_contract(self):
        relationships = self.report["relationships"]
        self.assertEqual(
            relationships["runtime_entropy_statuses"],
            {
                "below": "not packed",
                "exact": "not packed",
                "above": "packed",
            },
        )
        self.assertTrue(relationships["struct_filter_is_case_insensitive"])
        self.assertTrue(
            relationships["struct_trailing_segments_are_ignored"]
        )
        self.assertEqual(
            len(relationships["format_struct_methods"]),
            11,
        )
        self.assertEqual(
            set(relationships["multi_target_structured_outputs"]),
            {
                "entropy_two_json",
                "info_two_json",
                "struct_hash_md5_two_json",
            },
        )


if __name__ == "__main__":
    unittest.main()
