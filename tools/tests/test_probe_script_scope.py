import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).parents[2]
MODULE_PATH = ROOT / "tools" / "upstream" / "probe_script_scope.py"
SPEC = importlib.util.spec_from_file_location("probe_script_scope", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ProbeScriptScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = json.loads(
            (
                ROOT
                / "docs"
                / "research"
                / "data"
                / "script-scope-qt5.json"
            ).read_text(encoding="utf-8")
        )

    def test_parses_profiling_prefix_and_detection_values(self):
        stdout = (
            b"one.1.sg\none.1.sg: [1 ms]\n"
            b"two.2.sg\ntwo.2.sg: [0 ms]\n"
            b'{"detects":[{"values":[{"type":"format","name":"Scope",'
            b'"version":"2","info":""}]}]}\n'
        )
        order, detections = MODULE.parse_stdout(
            stdout, ["one.1.sg", "two.2.sg"]
        )
        self.assertEqual(order, ["one.1.sg", "two.2.sg"])
        self.assertEqual(
            detections,
            [
                {
                    "type": "format",
                    "name": "Scope",
                    "version": "2",
                    "info": "",
                }
            ],
        )

    def test_rejects_wrong_rule_order(self):
        stdout = (
            b"two.2.sg\none.1.sg\n"
            b'{"detects":[{"values":[]}]}\n'
        )
        with self.assertRaisesRegex(ValueError, "profiling order"):
            MODULE.parse_stdout(stdout, ["one.1.sg", "two.2.sg"])

    def test_rejects_trailing_oracle_diagnostics(self):
        stdout = (
            b"one.1.sg\n"
            b'{"detects":[{"values":[]}]}\n'
            b"one.1.sg: ReferenceError\n"
        )
        with self.assertRaisesRegex(ValueError, "trailing diagnostics"):
            MODULE.parse_stdout(stdout, ["one.1.sg"])

    def test_fixture_verification_rejects_undeclared_file(self):
        generator_path = (
            ROOT / "tools" / "corpus" / "generate_script_scope_fixture.py"
        )
        generator_spec = importlib.util.spec_from_file_location(
            "scope_fixture_for_probe_test", generator_path
        )
        assert generator_spec is not None and generator_spec.loader is not None
        generator = importlib.util.module_from_spec(generator_spec)
        sys.modules[generator_spec.name] = generator
        generator_spec.loader.exec_module(generator)
        with tempfile.TemporaryDirectory() as directory:
            fixture = pathlib.Path(directory)
            generator.generate(fixture)
            (fixture / "unexpected").write_bytes(b"x")
            with self.assertRaisesRegex(ValueError, "inventory mismatch"):
                MODULE.load_and_verify_fixture(
                    fixture, fixture / "manifest.json"
                )

    def test_reference_pins_equal_successful_oracles(self):
        self.assertEqual(
            self.reference["upstream_commit"], MODULE.UPSTREAM_COMMIT
        )
        self.assertTrue(self.reference["normalized_outputs_equal"])
        self.assertEqual(len(self.reference["rule_order"]), 7)
        self.assertEqual(len(self.reference["detections"]), 7)
        self.assertEqual(
            [item["version"] for item in self.reference["detections"]],
            ["1", "2", "", "", "", "1", "2"],
        )
        for oracle in self.reference["oracles"]:
            self.assertEqual(oracle["revision"], MODULE.UPSTREAM_COMMIT)
            self.assertEqual(oracle["exit_code"], 0)
            self.assertEqual(oracle["raw_stderr_bytes"], 0)
            self.assertEqual(
                oracle["raw_stderr_sha256"], MODULE.EMPTY_SHA256
            )


if __name__ == "__main__":
    unittest.main()
