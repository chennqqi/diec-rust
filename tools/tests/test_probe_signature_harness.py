import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[2]
MODULE_PATH = ROOT / "tools" / "upstream" / "probe_signature_harness.py"
SPEC = importlib.util.spec_from_file_location(
    "probe_signature_harness", MODULE_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

VECTORS = (
    ROOT / "docs" / "research" / "data" / "signature-oracle-vectors.json"
)
BASELINE = (
    ROOT / "docs" / "research" / "data" / "signature-oracle-qt5.json"
)
REVISION = "74eaf505c250ab47e709024e9dc41657cd8f2254"


class SignatureHarnessProbeTests(unittest.TestCase):
    def test_committed_baseline_matches_vectors_and_known_quirks(self):
        failures = MODULE.validate_baseline(
            MODULE.load_object(VECTORS),
            MODULE.load_object(BASELINE),
            REVISION,
        )
        self.assertEqual(failures, [])

    def test_validation_detects_semantic_drift(self):
        vectors = MODULE.load_object(VECTORS)
        baseline = MODULE.load_object(BASELINE)
        target = next(
            case
            for case in baseline["cases"]
            if case["id"] == "invalid_suffix_partially_compares"
        )
        target["compare"] = False
        failures = MODULE.validate_baseline(vectors, baseline, REVISION)
        self.assertIn(
            "invalid_suffix_partially_compares.compare",
            failures,
        )


if __name__ == "__main__":
    unittest.main()
