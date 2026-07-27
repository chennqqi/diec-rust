import importlib.util
import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools/upstream/probe_global_host_api.py"
SPEC = importlib.util.spec_from_file_location(
    "probe_global_host_api", MODULE_PATH
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class GlobalHostApiProbeTests(unittest.TestCase):
    def setUp(self):
        path = ROOT / "docs/research/data/global-host-api-qt5.json"
        self.report = json.loads(path.read_text(encoding="utf-8"))
        self.observation = self.report["observation"]
        qt6_path = ROOT / "docs/research/data/global-host-api-qt6.json"
        self.qt6_report = json.loads(qt6_path.read_text(encoding="utf-8"))
        self.qt6_observation = self.qt6_report["observation"]

    def test_committed_observation_satisfies_oracle_contract(self):
        MODULE.validate_observation(self.observation)
        MODULE.validate_observation(self.qt6_observation, "qt6")

    def test_committed_source_identities_are_current(self):
        for report in (self.report, self.qt6_report):
            for relative, identity in report["sources"].items():
                data = (ROOT / relative).read_bytes()
                self.assertEqual(len(data), identity["bytes"])
                self.assertEqual(MODULE.sha256(data), identity["sha256"])

    def test_qt6_missing_arguments_are_exact_errors(self):
        expected = {
            "_log()",
            "_setResult()",
            "_isResultPresent()",
            "_getNumberOfResults()",
        }
        observed = set()

        def visit(value):
            if isinstance(value, dict):
                if value.get("is_error") is True:
                    observed.add(value["source"])
                    self.assertEqual(
                        value["error_message"],
                        "Insufficient arguments",
                    )
                    self.assertEqual(value["error_line"], 1)
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(self.qt6_observation)
        self.assertEqual(observed, expected)

    def test_qt6_runtime_specific_contract(self):
        methods = self.qt6_observation["surface"]["methods"]
        self.assertEqual(
            methods["_getQtVersion"]["type"]["string"],
            "function",
        )
        self.assertEqual(
            self.qt6_observation["modes"]["qt_version"]["string"],
            "6.4.2",
        )
        info = self.qt6_observation["info"]
        self.assertEqual(info["log_messages"], ["", "42"])
        self.assertEqual(info["encoding_message_count"], 0)
        self.assertTrue(
            info["encoding_call"]["evaluation"]["is_undefined"]
        )

    def test_qt6_unexpected_error_is_rejected(self):
        changed = json.loads(json.dumps(self.qt6_observation))
        changed["modes"]["os"]["is_error"] = True
        with self.assertRaisesRegex(ValueError, "unexpected JavaScript"):
            MODULE.validate_observation(changed, "qt6")

    def test_array_removal_change_is_rejected(self):
        changed = json.loads(json.dumps(self.observation))
        changed["array_removal"]["removal"]["records"].pop()
        with self.assertRaisesRegex(ValueError, "array removeResult"):
            MODULE.validate_observation(changed)

    def test_nonempty_version_info_and_type_priority_are_observed(self):
        first = self.observation["results"]["steps"][0]
        self.assertEqual(
            first["evaluation"]["source"],
            "_setResult('compiler','Rust','1.0','first')",
        )
        self.assertEqual(
            first["records"],
            [
                {
                    "info": "first",
                    "is_advanced_heuristic": False,
                    "is_heuristic": False,
                    "name": "Rust",
                    "priority": 30,
                    "type": "compiler",
                    "version": "1.0",
                }
            ],
        )

    def test_stop_state_conflation_is_rejected(self):
        changed = json.loads(json.dumps(self.observation))
        changed["stop"]["js_stop_before_break"]["evaluation"][
            "boolean"
        ] = True
        with self.assertRaisesRegex(ValueError, "internal wrapper stop"):
            MODULE.validate_observation(changed)

    def test_parser_rejects_diagnostics(self):
        data = json.dumps(self.observation).encode()
        with self.assertRaisesRegex(ValueError, "stderr"):
            MODULE.parse_observation(data, b"warning", 0)
        with self.assertRaisesRegex(ValueError, "trailing"):
            MODULE.parse_observation(data + b"\nwarning", b"", 0)

    def test_qt6_dockerfile_uses_fixed_qt6_base(self):
        source = (
            ROOT
            / "tools/upstream/Dockerfile.global-host-api-harness-qt6"
        ).read_text(encoding="utf-8")
        self.assertIn(
            (
                "ARG BASE_IMAGE="
                "diec-rust/upstream-oracle-cmake-qt6:74eaf505"
            ),
            source,
        )
        self.assertIn(
            "Research-only Qt 6 native global HostApi oracle harness",
            source,
        )
        self.assertIn(
            "CMakeFiles/diec.dir/main_console.cpp.o",
            source,
        )


if __name__ == "__main__":
    unittest.main()
