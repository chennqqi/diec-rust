import hashlib
import importlib.util
import json
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools/upstream/probe_engine_contract.py"
REPORT_PATH = (
    ROOT / "docs/research/data/engine-contract-linux-qt5.json"
)
sys.path.insert(0, str(ROOT / "tools/upstream"))
SPEC = importlib.util.spec_from_file_location(
    "probe_engine_contract", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ProbeEngineContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        cls.cases = {
            case["id"]: case
            for case in cls.report["harness_output"]["cases"]
        }

    def test_report_identity_is_fixed(self):
        self.assertEqual(self.report["schema_version"], 1)
        self.assertEqual(
            self.report["generator"],
            "tools/upstream/probe_engine_contract.py",
        )
        self.assertEqual(
            self.report["generator_sha256"],
            hashlib.sha256(MODULE_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            self.report["upstream_commit"], MODULE.UPSTREAM_COMMIT
        )
        self.assertEqual(self.report["harness_output"]["case_count"], 16)

    def test_all_validated_relationships_hold(self):
        self.assertTrue(all(self.report["relationships"].values()))

    def test_stop_paths_keep_current_result_and_mark_failure(self):
        for case_id, expected in (
            ("callback_stop_first", "Priority one"),
            ("break_scan", "Break first"),
        ):
            case = self.cases[case_id]
            self.assertEqual(
                [record["name"] for record in case["records"]],
                [expected],
            )
            self.assertTrue(case["pd_stopped"])
            self.assertFalse(case["pd_success"])

    def test_all_entry_points_have_identical_records(self):
        records = [
            self.cases[case_id]["records"]
            for case_id in (
                "entry_file",
                "entry_memory",
                "entry_device",
                "entry_subdevice",
            )
        ]
        self.assertTrue(all(value == records[0] for value in records[1:]))

    def test_signature_file_path_is_not_publicly_reachable(self):
        audit = self.report["source_audit"]
        self.assertTrue(
            audit["public_scan_options_has_signature_name"]
        )
        self.assertFalse(
            audit["public_scan_options_has_signature_file_path"]
        )
        self.assertTrue(
            audit["private_process_detect_has_signature_file_path"]
        )
        self.assertTrue(
            audit["protected_process_detect_passes_empty_path"]
        )
        self.assertFalse(audit["public_runtime_filter_reachable"])


if __name__ == "__main__":
    unittest.main()
