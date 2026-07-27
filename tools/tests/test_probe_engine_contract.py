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
FIXTURE_MANIFEST_PATH = (
    ROOT / "docs/research/data/rule-orchestration-fixture.json"
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
        self.assertEqual(
            self.report["closed_corpus_gap"], "CAP-GAP-011"
        )
        self.assertEqual(self.report["harness_output"]["case_count"], 37)
        self.assertEqual(
            self.report["oracle"]["image_id"],
            "sha256:"
            "2a3ce9d5dd003ceb714b978706aac370bc4fff14cf86bd3967185af61164462a",
        )
        self.assertEqual(
            self.report["oracle"]["binary_sha256"],
            "22d0219a70aca23513d6d4c392e4ea96f9759c9781b1e56719aeba4c0cc0cdb2",
        )
        self.assertEqual(
            self.report["oracle"]["raw_stdout_bytes"], 59412
        )
        self.assertEqual(
            self.report["oracle"]["raw_stdout_sha256"],
            "d7f23f56025a6507ee06bbcfb5e6976a038dae9c9fbde02504391a428bfaa39a",
        )
        self.assertEqual(
            self.report["fixture_manifest"]["sha256"],
            hashlib.sha256(FIXTURE_MANIFEST_PATH.read_bytes()).hexdigest(),
        )
        for item in self.report["harness_inputs"].values():
            path = ROOT / item["path"]
            self.assertTrue(path.is_file())
            self.assertEqual(
                item["sha256"],
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )

    def test_all_validated_relationships_hold(self):
        self.assertTrue(all(self.report["relationships"].values()))
        self.assertEqual(
            self.report["relationships"],
            MODULE.validate(self.report["harness_output"]),
        )

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

    def test_callback_and_synchronized_external_stop_boundaries(self):
        expected = {
            "callback_stop_first": ["Priority one"],
            "callback_stop_second": [
                "Priority one",
                "Priority two",
            ],
            "callback_stop_last": [
                "Priority one",
                "Priority two",
                "Priority four",
            ],
            "external_stop_second": [
                "Priority one",
                "Priority two",
            ],
        }
        for case_id, names in expected.items():
            with self.subTest(case=case_id):
                case = self.cases[case_id]
                self.assertEqual(
                    [record["name"] for record in case["records"]],
                    names,
                )
                self.assertEqual(
                    len(case["callback_events"]),
                    len(names),
                )
                self.assertTrue(case["pd_stopped"])
                self.assertFalse(case["pd_success"])

        external = self.cases["external_stop_second"]
        self.assertEqual(external["external_stop_writes"], 1)
        self.assertTrue(external["external_stop_thread_distinct"])

    def test_fresh_state_recovers_same_engine_after_cancel(self):
        recovery = self.cases["post_cancel_fresh_state_recovery"]
        self.assertEqual(
            [
                record["name"]
                for record in recovery["canceled"]["records"]
            ],
            ["Priority one", "Priority two"],
        )
        self.assertTrue(recovery["canceled"]["pd_stopped"])
        self.assertFalse(recovery["canceled"]["pd_success"])
        self.assertEqual(
            [
                record["name"]
                for record in recovery["fresh"]["records"]
            ],
            ["Priority one", "Priority two", "Priority four"],
        )
        self.assertFalse(recovery["fresh"]["pd_stopped"])
        self.assertTrue(recovery["fresh"]["pd_success"])

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

    def test_rule_identity_and_priority_metadata_are_observed(self):
        record = self.cases["filter_exact_extra"]["records"][0]
        self.assertEqual(
            {
                "version": record["version"],
                "info": record["info"],
                "priority": record["priority"],
                "signature": record["signature"],
                "signature_file": record["signature_file"],
            },
            {
                "version": "main-global:main-helper:main-type",
                "info": "",
                "priority": 12,
                "signature": "a_extra.0.sg",
                "signature_file": (
                    "/fixture/extra/Binary/a_extra.0.sg"
                ),
            },
        )

    def test_chunked_and_incomplete_device_reads_are_exact(self):
        self.assertEqual(
            self.cases["device_chunked_read"]["read_returns"],
            ["3"] * 11 + ["2"],
        )
        self.assertEqual(
            self.cases["subdevice_chunked_read"]["read_returns"],
            ["3"] * 12,
        )
        self.assertEqual(
            self.cases["subdevice_chunked_read"]["bytes_returned"],
            36,
        )

        incomplete = (
            "device_early_eof",
            "device_read_error",
            "device_seek_error",
            "device_sequential",
            "subdevice_early_eof",
            "subdevice_read_error",
            "subdevice_seek_error",
            "subdevice_sequential",
        )
        for case_id in incomplete:
            with self.subTest(case=case_id):
                case = self.cases[case_id]
                self.assertLess(
                    case["bytes_returned"],
                    case["result_size"],
                )
                self.assertEqual(
                    [record["name"] for record in case["records"]],
                    ["Priority one"],
                )
                self.assertEqual(case["errors"], [])
                self.assertEqual(case["pd_error"], "")
                self.assertTrue(case["pd_success"])
                self.assertTrue(case["pd_finished"])

    def test_read_error_is_not_promoted_to_scan_error(self):
        for case_id in ("device_read_error", "subdevice_read_error"):
            case = self.cases[case_id]
            self.assertEqual(case["read_returns"], ["-1"])
            self.assertEqual(case["device_error"], "injected read error")
            self.assertEqual(case["errors"], [])
            self.assertEqual(case["pd_error"], "")

    def test_invalid_subdevice_ranges_return_zero_result_without_io(self):
        for case_id in (
            "subdevice_negative_offset",
            "subdevice_zero_size",
            "subdevice_negative_size",
            "subdevice_offset_at_end",
            "subdevice_crosses_end",
        ):
            with self.subTest(case=case_id):
                case = self.cases[case_id]
                self.assertFalse(case["range_valid"])
                self.assertEqual(case["result_size"], 0)
                self.assertEqual(case["result_filetype"], "Unknown")
                self.assertEqual(case["records"], [])
                self.assertEqual(case["seek_calls"], 0)
                self.assertEqual(case["read_calls"], 0)
                self.assertFalse(case["pd_success"])
                self.assertFalse(case["pd_finished"])

        tail = self.cases["subdevice_exact_tail"]
        self.assertTrue(tail["range_valid"])
        self.assertEqual(tail["result_size"], 1)
        self.assertEqual(tail["bytes_returned"], 1)

    def test_device_source_contracts_are_hash_bound(self):
        audit = self.report["source_audit"]
        self.assertTrue(all(audit["device_contracts"].values()))
        self.assertEqual(
            set(audit["sources"]),
            set(MODULE.SOURCE_PATHS),
        )
        for identity in audit["sources"].values():
            self.assertGreater(identity["bytes"], 0)
            self.assertRegex(identity["sha256"], r"^[0-9a-f]{64}$")

    def test_cross_thread_stop_race_is_not_an_upstream_contract(self):
        contracts = self.report["source_audit"][
            "cancellation_contracts"
        ]
        self.assertEqual(
            contracts,
            {
                "stop_flag_is_plain_bool": True,
                "stop_reader_is_plain_read": True,
                "stop_setter_is_plain_assignment": True,
            },
        )


if __name__ == "__main__":
    unittest.main()
