import hashlib
import importlib.util
import json
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT / "tools" / "upstream" / "probe_cli_option_behavior.py"
)
REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "cli-option-behavior-linux.json"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_cli_option_behavior",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ProbeCliOptionBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    def test_committed_report_has_fixed_identity(self):
        self.assertEqual(self.report["schema_version"], 1)
        self.assertEqual(
            self.report["generator"],
            "tools/upstream/probe_cli_option_behavior.py",
        )
        self.assertEqual(
            self.report["generator_sha256"],
            hashlib.sha256(MODULE_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            self.report["upstream_commit"],
            MODULE.UPSTREAM_COMMIT,
        )
        self.assertEqual(
            [oracle["name"] for oracle in self.report["oracles"]],
            ["linux-qt5-qmake", "linux-qt5-cmake"],
        )
        self.assertRegex(
            self.report["sample"]["sha256"],
            r"^[0-9a-f]{64}$",
        )

    def test_report_covers_every_declared_case(self):
        self.assertEqual(
            list(self.report["cases"]),
            sorted(case.name for case in MODULE.CASES),
        )
        for case in self.report["cases"].values():
            self.assertTrue(case["all_oracles_equal"])
            self.assertEqual(len(case["oracles"]), 2)

    def test_canonical_raw_text_matches_recorded_hashes(self):
        for name, case in self.report["cases"].items():
            canonical = case["canonical"]
            with self.subTest(case=name, stream="stdout"):
                stdout = canonical["stdout_utf8"].encode("utf-8")
                self.assertEqual(len(stdout), canonical["stdout_bytes"])
                self.assertEqual(
                    hashlib.sha256(stdout).hexdigest(),
                    canonical["stdout_sha256"],
                )
            with self.subTest(case=name, stream="stderr"):
                stderr = canonical["stderr_utf8"].encode("utf-8")
                self.assertEqual(len(stderr), canonical["stderr_bytes"])
                self.assertEqual(
                    hashlib.sha256(stderr).hexdigest(),
                    canonical["stderr_sha256"],
                )

    def test_relationships_capture_legacy_noops_and_deltas(self):
        relationships = self.report["relationships"]
        self.assertTrue(
            relationships["test_directory_value_is_unvalidated"]
        )
        self.assertTrue(
            relationships[
                "createtest_complete_only_prints_announcement"
            ]
        )
        self.assertEqual(
            relationships["createtest_missing_positionals_exit_code"],
            4,
        )
        self.assertTrue(
            relationships["createtest_missing_positionals_uses_addtest_name"]
        )
        self.assertTrue(
            relationships["profiling_without_messages_equals_default"]
        )
        self.assertEqual(
            relationships["messages_added_stdout_lines"],
            ["Cannot load database: /does-not-exist"],
        )
        self.assertEqual(
            relationships["verbose_added_values"],
            [
                {
                    "info": "AMD64, 64-bit",
                    "name": "Linux",
                    "type": "operation system",
                    "version": "ABI: 3.2.0",
                }
            ],
        )

    def test_scan_value_projection_rejects_non_scan_json(self):
        with self.assertRaisesRegex(ValueError, "detect"):
            MODULE.scan_values(b'{"value": 1}')


if __name__ == "__main__":
    unittest.main()
