import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools/upstream/probe_global_typo_errors.py"
SPEC = importlib.util.spec_from_file_location(
    "probe_global_typo_errors", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class GlobalTypoErrorProbeTests(unittest.TestCase):
    def test_parse_stdout_requires_exact_trailing_diagnostic(self):
        document = {
            "detects": [
                {
                    "filetype": "Binary",
                    "offset": "0",
                    "size": "32",
                    "parentfilepart": "Header",
                    "values": [
                        {
                            "type": "Unknown",
                            "name": "Unknown",
                            "version": "",
                            "info": "",
                        }
                    ],
                }
            ]
        }
        name = "debug-dwarf-typo.bin"
        data = (
            json.dumps(document)
            + "\n\n"
            + MODULE.EXPECTED_ERRORS[name]
            + "\n"
        ).encode()
        parsed = MODULE.parse_stdout(data, name, 32)
        self.assertIn("get_DWRAF_vi", parsed["diagnostic"])
        with self.assertRaisesRegex(ValueError, "messages"):
            MODULE.parse_stdout(data + b"extra\n", name, 32)

    def test_committed_report_has_equal_exact_errors(self):
        path = (
            ROOT
            / "docs/research/data/global-typo-errors-qt5.json"
        )
        report = json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue(report["normalized_outputs_equal"])
        self.assertEqual(len(report["oracles"]), 2)
        for oracle in report["oracles"]:
            self.assertEqual(len(oracle["inputs"]), 2)
            for item in oracle["inputs"]:
                self.assertEqual(
                    item["diagnostic"],
                    MODULE.EXPECTED_ERRORS[item["path"]],
                )
                self.assertEqual(item["exit_code"], 0)
                self.assertEqual(item["raw_stderr_bytes"], 0)

    def test_fixture_validation_rejects_mutation(self):
        manifest = (
            ROOT / "docs/research/data/global-typo-corpus.json"
        )
        rules = ROOT / "upstream/Detect-It-Easy"
        with tempfile.TemporaryDirectory() as directory:
            fixture = pathlib.Path(directory)
            for entry in json.loads(
                manifest.read_text(encoding="utf-8")
            )["entries"]:
                (fixture / entry["path"]).write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "identity mismatch"):
                MODULE.load_and_verify_fixture(
                    fixture, manifest, rules
                )


if __name__ == "__main__":
    unittest.main()
