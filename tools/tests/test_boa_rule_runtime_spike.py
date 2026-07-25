import hashlib
import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[2]
REFERENCE = (
    ROOT / "docs" / "research" / "data" / "boa-rule-runtime.json"
)


class BoaRuleRuntimeSpikeTests(unittest.TestCase):
    def setUp(self):
        self.reference = json.loads(REFERENCE.read_text(encoding="utf-8"))

    def test_reference_pins_upstream_rules_and_candidate(self):
        self.assertEqual(
            self.reference["upstream_commit"],
            "74eaf505c250ab47e709024e9dc41657cd8f2254",
        )
        self.assertEqual(
            self.reference["rules_commit"],
            "c2c17dfa5ea4e078ba31eab55d87430c96622fb6",
        )
        self.assertEqual(
            self.reference["candidate"],
            {
                "crate": "boa_engine",
                "default_features": False,
                "version": "0.21.1",
            },
        )

    def test_reference_matches_spike_inputs(self):
        experiment = self.reference["experiment"]
        paths = {
            "cargo_toml_sha256": (
                ROOT / "spikes" / "boa-rule-runtime" / "Cargo.toml"
            ),
            "cargo_lock_sha256": (
                ROOT / "spikes" / "boa-rule-runtime" / "Cargo.lock"
            ),
            "source_sha256": (
                ROOT
                / "spikes"
                / "boa-rule-runtime"
                / "src"
                / "main.rs"
            ),
        }
        for field, path in paths.items():
            with self.subTest(field=field):
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                    experiment[field],
                )

    def test_reference_records_candidate_failure_and_full_corpus(self):
        self.assertFalse(
            self.reference["fixture"][
                "candidate_compatible_with_fixed_rules"
            ]
        )
        self.assertEqual(
            self.reference["isolated_parse"],
            {
                "bytes": 2_902_881,
                "error_count": 1,
                "error_path": (
                    "db/Binary/"
                    "format_bin.Nintendo-certified-file.1.sg"
                ),
                "files": 2235,
            },
        )
        self.assertEqual(
            self.reference["shared_parse"]["error_count"],
            2021,
        )


if __name__ == "__main__":
    unittest.main()
