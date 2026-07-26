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

    def test_committed_observation_satisfies_oracle_contract(self):
        MODULE.validate_observation(self.observation)

    def test_committed_source_identities_are_current(self):
        for relative, identity in self.report["sources"].items():
            data = (ROOT / relative).read_bytes()
            self.assertEqual(len(data), identity["bytes"])
            self.assertEqual(MODULE.sha256(data), identity["sha256"])

    def test_array_removal_change_is_rejected(self):
        changed = json.loads(json.dumps(self.observation))
        changed["array_removal"]["removal"]["records"].pop()
        with self.assertRaisesRegex(ValueError, "array removeResult"):
            MODULE.validate_observation(changed)

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


if __name__ == "__main__":
    unittest.main()
