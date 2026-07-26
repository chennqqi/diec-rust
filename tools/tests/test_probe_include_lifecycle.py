import hashlib
import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
REPORT_PATH = (
    ROOT / "docs/research/data/include-lifecycle-linux-qt5.json"
)
MANIFEST_PATH = ROOT / "docs/research/data/include-fixture.json"
PROBE_PATH = ROOT / "tools/upstream/probe_include_lifecycle.py"


class ProbeIncludeLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    def test_report_identity_is_fixed(self):
        self.assertEqual(self.report["schema_version"], 1)
        self.assertEqual(
            self.report["generator"],
            "tools/upstream/probe_include_lifecycle.py",
        )
        self.assertEqual(
            self.report["generator_sha256"],
            hashlib.sha256(PROBE_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            self.report["fixture_manifest"]["sha256"],
            hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            self.report["upstream_commit"],
            "74eaf505c250ab47e709024e9dc41657cd8f2254",
        )
        self.assertTrue(self.report["normalized_outputs_equal"])
        self.assertTrue(all(self.report["relationships"].values()))

    def test_resource_limits_are_recorded(self):
        self.assertEqual(
            self.report["resource_limits"],
            {
                "fixture_mount": "readonly",
                "memory": "256m",
                "network": "none",
                "pids": 64,
                "timeout_seconds_per_case": 10,
            },
        )

    def test_each_case_exits_cleanly_and_continues(self):
        expected_names = {
            "self-cycle": ["After self cycle"],
            "two-cycle": ["After two cycle"],
            "parse-error": ["After parse error"],
            "missing": ["After missing include"],
        }
        for oracle in self.report["oracles"]:
            for case_name, expected in expected_names.items():
                case = oracle["cases"][case_name]
                self.assertEqual(case["exit_code"], 0)
                self.assertEqual(case["stderr_bytes"], 0)
                self.assertEqual(case["detection_names"], expected)

    def test_cycles_have_bounded_observed_diagnostic_shape(self):
        for oracle in self.report["oracles"]:
            for case_name in ("self-cycle", "two-cycle"):
                case = oracle["cases"][case_name]
                self.assertEqual(len(case["prefix_lines"]), 28)
                self.assertEqual(
                    case["suffix_lines"],
                    [
                        "_init: Unknown/_init: 1: RangeError: "
                        "Maximum call stack size exceeded."
                    ],
                )

    def test_parse_and_missing_include_use_different_channels(self):
        for oracle in self.report["oracles"]:
            parse = oracle["cases"]["parse-error"]
            missing = oracle["cases"]["missing"]
            self.assertEqual(len(parse["prefix_lines"]), 2)
            self.assertEqual(len(parse["suffix_lines"]), 1)
            self.assertEqual(
                missing["prefix_lines"],
                [
                    "Cannot find: not-present",
                    "Cannot find: not-present",
                ],
            )
            self.assertEqual(missing["suffix_lines"], [])


if __name__ == "__main__":
    unittest.main()
