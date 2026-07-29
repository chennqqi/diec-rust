import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
OBSERVER_PATH = (
    ROOT / "tools/benchmark/observe_windows_cache_environment.py"
)
PROBE_PATH = (
    ROOT / "tools/benchmark/probe_windows_benchmark_cache_environment.py"
)
REPORT_PATH = (
    ROOT
    / "docs/research/data/"
    "upstream-benchmark-windows-cache-environment.json"
)
DOCUMENT_PATH = (
    ROOT / "docs/research/windows-benchmark-cache-state.md"
)
ADR_PATH = (
    ROOT
    / "docs/design/decisions/"
    "0015-benchmark-cache-state-model.md"
)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


PROBE = load_module(
    "probe_windows_benchmark_cache_environment_test",
    PROBE_PATH,
)


class WindowsBenchmarkCacheEnvironmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report_raw = REPORT_PATH.read_bytes()
        cls.report = json.loads(cls.report_raw)

    def test_report_binds_sources_and_fixed_upstream(self):
        report = self.report
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(
            report["upstream_commit"],
            PROBE.EXPECTED_REVISION,
        )
        self.assertEqual(
            report["generator_sha256"],
            hashlib.sha256(PROBE_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            report["observer"]["sha256"],
            hashlib.sha256(OBSERVER_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(report["observer"]["repetitions"], 2)

    def test_observation_is_native_read_only_and_path_private(self):
        observation = self.report["observation"]
        self.assertEqual(
            observation["platform"]["windows_version"]["build"],
            26100,
        )
        self.assertEqual(observation["platform"]["machine"], "AMD64")
        self.assertEqual(observation["platform"]["page_size"], 4096)
        self.assertEqual(
            observation["target_volume"]["filesystem"],
            "NTFS",
        )
        self.assertFalse(
            observation["target_volume"]["target_path_recorded"]
        )
        self.assertFalse(
            observation["target_volume"]["volume_identity_recorded"]
        )
        self.assertEqual(
            observation["process"][
                "set_system_file_cache_privilege"
            ],
            {
                "attributes": None,
                "enabled": False,
                "name": "SeIncreaseQuotaPrivilege",
                "present": False,
            },
        )
        self.assertTrue(
            observation["scope"]["read_only_observation"]
        )
        self.assertFalse(observation["scope"]["cache_state_changed"])
        for field in (
            "set_system_file_cache_size_called",
            "empty_working_set_called",
            "flush_file_buffers_called",
            "no_buffering_handle_opened",
        ):
            self.assertFalse(observation["scope"][field])

    def test_assessment_refuses_false_cross_platform_equivalence(self):
        assessment = self.report["cache_state_assessment"]
        self.assertTrue(assessment["warm"]["portable_name_allowed"])
        self.assertFalse(
            assessment[
                "file_content_nonresident_metadata_warm"
            ]["portable_name_allowed"]
        )
        self.assertFalse(
            assessment["system_cold"]["portable_name_allowed"]
        )
        self.assertFalse(assessment["generic_cold"]["allowed"])
        relationships = self.report["relationships"]
        self.assertTrue(
            relationships["two_native_observations_identical"]
        )
        self.assertTrue(relationships["observation_was_read_only"])
        self.assertFalse(
            relationships[
                "windows_file_content_state_equivalent_to_linux_proven"
            ]
        )
        self.assertFalse(
            relationships["windows_system_cold_state_proven"]
        )

    def test_official_contract_sources_are_exact(self):
        sources = self.report["official_contract_sources"]
        self.assertEqual(len(sources), 5)
        self.assertEqual(
            {source["url"] for source in sources},
            {source["url"] for source in PROBE.OFFICIAL_CONTRACT_SOURCES},
        )
        self.assertTrue(all(source["claim"] for source in sources))

    def test_probe_json_parser_rejects_ambiguous_input(self):
        with self.assertRaisesRegex(PROBE.ProbeError, "duplicate JSON"):
            PROBE.parse_json(b'{"a":1,"a":2}', "test JSON")
        with self.assertRaisesRegex(PROBE.ProbeError, "non-finite"):
            PROBE.parse_json(b'{"a":NaN}', "test JSON")
        with self.assertRaisesRegex(PROBE.ProbeError, "root"):
            PROBE.parse_json(b"[]", "test JSON")

    def test_document_adr_and_report_are_aligned(self):
        document = DOCUMENT_PATH.read_text(encoding="utf-8")
        adr = ADR_PATH.read_text(encoding="utf-8")
        for text in (
            "`SeIncreaseQuotaPrivilege`",
            "`SetSystemFileCacheSize`",
            "`FILE_FLAG_NO_BUFFERING`",
            "`EmptyWorkingSet`",
            "Windows build 26100",
        ):
            self.assertIn(text, document)
        self.assertIn(
            hashlib.sha256(self.report_raw).hexdigest(),
            document,
        )
        self.assertIn(
            "Windows 策略评审输入",
            adr,
        )
        for local in (
            b"I:\\\\",
            b"C:\\\\",
            b"Users\\\\worker",
            b"github.com\\\\chennqqi",
        ):
            self.assertNotIn(local, self.report_raw)


if __name__ == "__main__":
    unittest.main()
