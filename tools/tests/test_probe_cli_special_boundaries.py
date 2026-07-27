import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT / "tools" / "upstream" / "probe_cli_special_boundaries.py"
)
REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "cli-special-boundaries-linux-qt5.json"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_cli_special_boundaries",
    MODULE_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ProbeCliSpecialBoundariesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    def observations(self, report=None):
        report = report or self.report
        return {
            name: MODULE.Observation(
                case["canonical"]["exit_code"],
                case["canonical"]["stdout_utf8"].encode("utf-8"),
                case["canonical"]["stderr_utf8"].encode("utf-8"),
            )
            for name, case in report["cases"].items()
        }

    def test_report_and_oracle_identity_are_fixed(self):
        self.assertEqual(self.report["schema_version"], 1)
        self.assertEqual(self.report["generator"], MODULE.GENERATOR)
        self.assertEqual(
            self.report["generator_sha256"],
            hashlib.sha256(MODULE_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            self.report["upstream_commit"], MODULE.UPSTREAM_COMMIT
        )
        self.assertEqual(
            self.report["closed_corpus_gap"], "CAP-GAP-001"
        )
        self.assertEqual(self.report["case_count"], 28)
        self.assertEqual(
            {
                case["name"]: (
                    case["image_id"],
                    case["binary_sha256"],
                )
                for case in self.report["oracles"]
            },
            {
                "qmake": (
                    "sha256:"
                    "cc5561a5d256c7912227a8ecf4ba9c6b9178c99911e471017d3c3988bac964ab",
                    "721ec846507a8567aae07e91dcd1f576182481ae0dc1595b1f19e4a3e859b79d",
                ),
                "cmake": (
                    "sha256:"
                    "466102628c3a94b7ab1048f0c24261b1920e61a40029b128763cf79370255040",
                    "da1fab49f7ba5970d1fc1c7fe3d4f380cf5e8775dd8097207e7b3c30f08236cf",
                ),
            },
        )

    def test_fixture_and_generator_hashes_are_current(self):
        fixture = self.report["fixture"]
        manifest = ROOT / fixture["manifest_path"]
        generator = ROOT / fixture["generator"]
        self.assertEqual(
            fixture["manifest_sha256"],
            hashlib.sha256(manifest.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            fixture["generator_sha256"],
            hashlib.sha256(generator.read_bytes()).hexdigest(),
        )
        self.assertEqual(len(fixture["entries"]), 7)

    def test_report_relationships_are_recomputed(self):
        self.assertEqual(
            self.report["relationships"],
            MODULE.validate(self.observations()),
        )

    def test_entropy_floating_boundary_is_exact(self):
        relationships = self.report["relationships"]
        self.assertEqual(
            relationships["runtime_entropy_totals"],
            {
                "below": 6.484374999999999,
                "exact": 6.499999999999999,
                "above": 6.515624999999999,
            },
        )
        self.assertEqual(
            relationships["runtime_entropy_statuses"],
            {
                "below": "not packed",
                "exact": "not packed",
                "above": "packed",
            },
        )
        self.assertTrue(
            relationships["theoretical_6_5_rounds_below_threshold"]
        )
        self.assertTrue(
            relationships[
                "text_rounds_exact_case_to_6_5_but_status_is_not_packed"
            ]
        )

    def test_struct_filter_and_empty_value_boundaries_are_exact(self):
        relationships = self.report["relationships"]
        self.assertTrue(relationships["struct_filter_is_case_insensitive"])
        self.assertTrue(
            relationships["struct_trailing_segments_are_ignored"]
        )
        self.assertTrue(
            relationships["empty_struct_value_falls_back_to_normal_scan"]
        )
        self.assertTrue(relationships["entropy_precedes_struct"])

    def test_multi_target_special_json_is_not_one_document(self):
        multi = self.report["relationships"][
            "multi_target_structured_outputs"
        ]
        self.assertEqual(
            set(multi),
            {
                "entropy_two_json",
                "info_two_json",
                "struct_hash_md5_two_json",
            },
        )
        for observation in multi.values():
            self.assertFalse(observation["valid_single_json_document"])
            self.assertEqual(len(observation["filename_prefixes"]), 2)

    def test_all_advertised_format_struct_methods_are_exercised(self):
        methods = self.report["relationships"]["format_struct_methods"]
        self.assertEqual(
            set(methods),
            {
                "pe_entry_point_json",
                "pe_dos_header_json",
                "pe_nt_headers_json",
                "pe_section_header_json",
                "pe_resource_directory_json",
                "pe_export_directory_json",
                "elf_entry_point_json",
                "elf_ehdr_json",
                "macho_entry_point_json",
                "macho_header_json",
                "dex_header_json",
            },
        )
        self.assertTrue(methods["pe_section_header_json"]["empty_data"])
        self.assertEqual(
            methods["dex_header_json"]["sentinel_value"],
            "00000070",
        )

    def test_source_contracts_are_hash_bound(self):
        audit = self.report["source_audit"]
        self.assertTrue(all(audit["assumptions"].values()))
        self.assertEqual(set(audit["sources"]), set(MODULE.SOURCE_PATHS))
        for identity in audit["sources"].values():
            self.assertGreater(identity["bytes"], 0)
            self.assertRegex(identity["sha256"], r"^[0-9a-f]{64}$")

    def test_falsified_entropy_status_is_rejected(self):
        changed = copy.deepcopy(self.report)
        document = json.loads(
            changed["cases"]["entropy_exact_json"]["canonical"][
                "stdout_utf8"
            ]
        )
        document["status"] = "packed"
        document["records"][0]["status"] = "packed"
        changed["cases"]["entropy_exact_json"]["canonical"][
            "stdout_utf8"
        ] = json.dumps(document)
        with self.assertRaisesRegex(ValueError, "packed boundary"):
            MODULE.validate(self.observations(changed))

    def test_falsified_struct_trailing_behavior_is_rejected(self):
        changed = copy.deepcopy(self.report)
        changed["cases"]["struct_hash_md5_trailing_json"]["canonical"][
            "stdout_utf8"
        ] = '{"data": ""}'
        with self.assertRaisesRegex(ValueError, "casefold/trailing"):
            MODULE.validate(self.observations(changed))


if __name__ == "__main__":
    unittest.main()
