import importlib.util
import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools/upstream/probe_host_api_arity.py"
SPEC = importlib.util.spec_from_file_location("probe_host_api_arity", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class HostApiArityProbeTests(unittest.TestCase):
    def setUp(self):
        path = ROOT / "docs/research/data/host-api-arity-qt5.json"
        self.report = json.loads(path.read_text(encoding="utf-8"))
        self.observation = self.report["observation"]

    def test_committed_observation_satisfies_oracle_contract(self):
        MODULE.validate_observation(self.observation)

    def test_committed_source_identities_are_current(self):
        for relative, identity in self.report["sources"].items():
            data = (ROOT / relative).read_bytes()
            self.assertEqual(len(data), identity["bytes"])
            self.assertEqual(MODULE.sha256(data), identity["sha256"])

    def test_extra_argument_change_is_rejected(self):
        changed = json.loads(json.dumps(self.observation))
        changed["binary"]["u8_extra"]["number"] = 66
        with self.assertRaisesRegex(ValueError, "extra arguments"):
            MODULE.validate_observation(changed)

    def test_missing_method_alias_is_rejected(self):
        changed = json.loads(json.dumps(self.observation))
        changed["pe"]["get_ep_signature_type_after_init"]["string"] = "function"
        with self.assertRaisesRegex(ValueError, "method type"):
            MODULE.validate_observation(changed)

    def test_parser_rejects_diagnostics(self):
        data = json.dumps(self.observation).encode()
        with self.assertRaisesRegex(ValueError, "stderr"):
            MODULE.parse_observation(data, b"warning", 0)
        with self.assertRaisesRegex(ValueError, "trailing"):
            MODULE.parse_observation(data + b"\nwarning", b"", 0)


if __name__ == "__main__":
    unittest.main()
