import hashlib
import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[2]
EVIDENCE_PATH = (
    ROOT / "docs" / "research" / "data" / "signature-parser.json"
)
INVENTORY_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "signature-pattern-inventory.json"
)


class SignatureParserSpikeTests(unittest.TestCase):
    def setUp(self):
        self.evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
        self.inventory = json.loads(
            INVENTORY_PATH.read_text(encoding="utf-8")
        )

    def test_fixed_source_versions_are_consistent(self):
        self.assertEqual(
            self.evidence["upstream_commit"],
            "74eaf505c250ab47e709024e9dc41657cd8f2254",
        )
        self.assertEqual(
            self.evidence["formats_commit"],
            self.inventory["formats_commit"],
        )
        self.assertEqual(
            self.evidence["xscanengine_commit"],
            self.inventory["xscanengine_commit"],
        )

    def test_spike_hashes_match_files(self):
        spike = self.evidence["spike"]
        paths = {
            "cargo_toml_sha256": (
                ROOT / "spikes" / "signature-parser" / "Cargo.toml"
            ),
            "cargo_lock_sha256": (
                ROOT / "spikes" / "signature-parser" / "Cargo.lock"
            ),
            "source_sha256": (
                ROOT / "spikes" / "signature-parser" / "src" / "lib.rs"
            ),
        }
        for field, path in paths.items():
            with self.subTest(field=field):
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                    spike[field],
                )

    def test_inventory_hash_and_counts_are_reproducible(self):
        dynamic = self.evidence["dynamic_inventory"]
        self.assertEqual(
            hashlib.sha256(INVENTORY_PATH.read_bytes()).hexdigest(),
            dynamic["sha256"],
        )
        generator_path = ROOT / self.inventory["generator"]["path"]
        self.assertEqual(self.inventory["generator"]["version"], 1)
        self.assertEqual(
            hashlib.sha256(generator_path.read_bytes()).hexdigest(),
            dynamic["generator_sha256"],
        )
        patterns = self.inventory["patterns"]
        self.assertEqual(patterns, sorted(set(patterns)))
        pattern_bytes = "\n".join(patterns).encode("utf-8")
        pattern_hash = hashlib.sha256(pattern_bytes).hexdigest()
        self.assertEqual(
            pattern_hash,
            self.inventory["patterns_lf_sha256"],
        )
        self.assertEqual(pattern_hash, dynamic["patterns_lf_sha256"])
        self.assertEqual(len(patterns), dynamic["pattern_count"])
        self.assertEqual(
            self.inventory["calling_rule_count"],
            dynamic["calling_rule_count"],
        )
        self.assertEqual(
            self.inventory["pattern_call_count"],
            dynamic["pattern_call_count"],
        )

    def test_compatibility_mode_is_explicitly_scoped(self):
        spike = self.evidence["spike"]
        self.assertEqual(spike["strict_parse_count"], 312)
        self.assertEqual(spike["compatible_parse_count"], 317)
        self.assertEqual(spike["compatible_parse_error_count"], 0)
        self.assertTrue(spike["unknown_syntax_is_diagnostic"])
        self.assertFalse(self.evidence["dynamic_inventory"]["scope_complete"])
        self.assertIn(
            "relative offset",
            spike["context_required_operations"],
        )
        self.assertEqual(
            spike["pinned_xbinary_compare_differential"],
            {"case_count": 16, "matched_count": 16},
        )

    def test_signature_oracle_provenance_matches_files(self):
        oracle = self.evidence["signature_oracle"]
        paths = {
            "dockerfile_sha256": (
                ROOT
                / "tools"
                / "upstream"
                / "Dockerfile.signature-harness-qt5"
            ),
            "harness_source_sha256": (
                ROOT
                / "tools"
                / "upstream"
                / "signature_harness_main.cpp"
            ),
            "probe_sha256": (
                ROOT
                / "tools"
                / "upstream"
                / "probe_signature_harness.py"
            ),
            "vector_generator_sha256": (
                ROOT
                / "tools"
                / "corpus"
                / "generate_signature_oracle_vectors.py"
            ),
            "vectors_sha256": ROOT / oracle["vectors"],
            "baseline_sha256": ROOT / oracle["baseline"],
        }
        for field, path in paths.items():
            with self.subTest(field=field):
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                    oracle[field],
                )
        baseline = json.loads(
            (ROOT / oracle["baseline"]).read_text(encoding="utf-8")
        )
        self.assertEqual(baseline["case_count"], oracle["case_count"])
        self.assertTrue(oracle["probe_passed"])
        self.assertEqual(len(oracle["compare_find_divergences"]), 4)


if __name__ == "__main__":
    unittest.main()
