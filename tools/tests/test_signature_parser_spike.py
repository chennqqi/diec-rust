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
STATIC_INVENTORY_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "signature-static-inventory.json"
)
QTSCRIPT_OBJECT_ENUMERATION_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "qtscript-object-enumeration.json"
)


class SignatureParserSpikeTests(unittest.TestCase):
    def setUp(self):
        self.evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
        self.inventory = json.loads(
            INVENTORY_PATH.read_text(encoding="utf-8")
        )
        self.static_inventory = json.loads(
            STATIC_INVENTORY_PATH.read_text(encoding="utf-8")
        )
        self.qtscript_object_enumeration = json.loads(
            QTSCRIPT_OBJECT_ENUMERATION_PATH.read_text(
                encoding="utf-8"
            )
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

    def test_qtscript_object_enumeration_provenance_matches_files(self):
        summary = self.evidence["qtscript_object_enumeration"]
        evidence = self.qtscript_object_enumeration
        self.assertEqual(
            hashlib.sha256(
                QTSCRIPT_OBJECT_ENUMERATION_PATH.read_bytes()
            ).hexdigest(),
            summary["sha256"],
        )
        self.assertEqual(
            summary["path"],
            str(
                QTSCRIPT_OBJECT_ENUMERATION_PATH.relative_to(ROOT)
            ).replace("\\", "/"),
        )
        self.assertEqual(summary["image"], evidence["oracle"]["image"])
        self.assertEqual(
            summary["image_id"],
            evidence["oracle"]["image_id"],
        )
        self.assertEqual(
            summary["qt_version"],
            evidence["oracle"]["qt_version"],
        )
        self.assertEqual(summary["engine"], "QScriptEngine")
        probe = evidence["probe"]
        for path_field, hash_field in (
            ("source", "source_sha256"),
            ("qmake_project", "qmake_project_sha256"),
        ):
            path = ROOT / probe[path_field]
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                probe[hash_field],
            )
        result = evidence["result"]
        self.assertEqual(result["inherited_enumerable_keys"], [])
        self.assertEqual(
            summary["inherited_enumerable_key_count"],
            len(result["inherited_enumerable_keys"]),
        )
        self.assertEqual(
            result["refs_for_in_keys"],
            [
                "'$'11'@P:Microsoft.VisualBasic'00",
                "%%%%%%%%%%'.cs'00",
                "'$'11'@P:FSharp.Core'00",
                "'std::'%%%%%%",
            ],
        )
        self.assertEqual(
            summary["pdb_ref_key_count"],
            len(result["refs_for_in_keys"]),
        )
        self.assertEqual(
            summary["probe_passed"],
            evidence["probe_passed"],
        )
        self.assertTrue(evidence["probe_passed"])

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

    def test_static_inventory_hash_and_scope_are_reproducible(self):
        static = self.evidence["static_inventory"]
        self.assertEqual(
            hashlib.sha256(STATIC_INVENTORY_PATH.read_bytes()).hexdigest(),
            static["sha256"],
        )
        generator_path = ROOT / self.static_inventory["generator"]["path"]
        self.assertEqual(
            hashlib.sha256(generator_path.read_bytes()).hexdigest(),
            static["generator_sha256"],
        )
        self.assertEqual(
            self.static_inventory["parser"]["manifest_sha256"],
            static["parser"]["manifest_sha256"],
        )
        self.assertEqual(
            self.static_inventory["rules"]["manifest_sha256"],
            static["rules_manifest_sha256"],
        )
        self.assertEqual(static["rule_file_count"], 2175)
        self.assertEqual(static["parse_success_count"], 2175)
        self.assertEqual(static["parse_failure_count"], 0)
        self.assertEqual(static["call_site_count"], 5968)
        self.assertEqual(static["calling_file_count"], 1615)
        self.assertEqual(static["unknown_receiver_call_site_count"], 0)
        self.assertEqual(static["max_static_values_per_expression"], 4096)
        self.assertEqual(static["verified_static_transform_count"], 3)
        self.assertEqual(
            static["static_transform_verification_failure_count"],
            0,
        )
        self.assertEqual(static["finite_parameter_value_count"], 26)
        self.assertEqual(static["finite_scoped_assignment_count"], 5)
        self.assertEqual(
            static["top_level_function_audit"],
            {
                "top_level_definition_count": 2290,
                "unique_name_count": 95,
                "duplicate_name_count": 7,
                "unresolved_direct_call_name_count": 72,
                "safe_definition_count": 95,
            },
        )
        self.assertEqual(
            static["argument_kind_counts"],
            {
                "dynamic": 11,
                "literal": 5855,
                "static_expression": 102,
            },
        )
        self.assertEqual(
            static["dynamic_expression_type_counts"],
            {
                "Binary": 3,
                "SymbolRef": 8,
            },
        )
        self.assertEqual(
            static["value_preserving_self_assignment_count"],
            1,
        )
        self.assertEqual(
            static["finite_object_key_iteration_count"],
            1,
        )
        self.assertEqual(
            static["finite_object_element_assignment_count"],
            1,
        )
        self.assertEqual(
            static["plain_object_enumeration_audit"],
            {
                "object_reference_count": 1,
                "safe_has_own_property_call_count": 1,
                "unsafe_reference_count": 0,
            },
        )
        self.assertEqual(static["finite_loop_accumulation_count"], 2)
        self.assertEqual(
            static["finite_adjacent_assignment_count"],
            2,
        )
        self.assertEqual(static["static_pattern_count"], 5614)
        self.assertEqual(static["dynamic_pattern_overlap_count"], 317)
        self.assertEqual(static["dynamic_only_pattern_count"], 0)
        self.assertEqual(static["static_only_pattern_count"], 5297)
        self.assertTrue(static["syntactic_call_site_scope_complete"])
        self.assertFalse(static["runtime_value_scope_complete"])

    def test_compatibility_mode_is_explicitly_scoped(self):
        spike = self.evidence["spike"]
        self.assertEqual(spike["strict_parse_count"], 312)
        self.assertEqual(spike["compatible_parse_count"], 317)
        self.assertEqual(spike["compatible_parse_error_count"], 0)
        self.assertTrue(spike["unknown_syntax_is_diagnostic"])
        self.assertFalse(self.evidence["dynamic_inventory"]["scope_complete"])
        self.assertTrue(
            self.evidence["static_inventory"][
                "syntactic_call_site_scope_complete"
            ]
        )
        self.assertFalse(
            self.evidence["static_inventory"]["runtime_value_scope_complete"]
        )
        self.assertIn(
            "relative offset",
            spike["context_required_operations"],
        )
        self.assertEqual(
            spike["pinned_xbinary_compare_differential"],
            {"case_count": 16, "matched_count": 16},
        )
        self.assertEqual(
            spike["pinned_xbinary_find_differential"],
            {
                "case_count": 19,
                "matched_count": 19,
                "branches": [
                    "plain-hex",
                    "SigByte",
                    "control-record",
                ],
            },
        )
        self.assertEqual(
            spike["pinned_binary_script_compare_differential"],
            {
                "case_count": 5,
                "matched_count": 5,
                "header_fast_path_observed": True,
                "strict_boundary_observed": True,
            },
        )
        self.assertEqual(
            spike["pinned_binary_script_compare_ep_differential"],
            {
                "case_count": 5,
                "matched_count": 5,
                "cache_length_unit_mismatch_observed": True,
                "source_length_branching_observed": True,
                "strict_boundary_observed": True,
            },
        )
        self.assertEqual(
            spike["pinned_binary_script_compare_overlay_differential"],
            {
                "case_count": 5,
                "matched_count": 5,
                "cache_length_unit_mismatch_observed": True,
                "source_length_branching_observed": True,
                "strict_boundary_observed": True,
            },
        )
        self.assertEqual(
            spike["pinned_xbinary_memory_map_differential"],
            {
                "case_count": 7,
                "matched_count": 7,
                "file_types": [
                    "PE",
                    "ELF",
                    "Mach-O",
                    "COM",
                    "MS-DOS",
                    "AmigaHunk",
                ],
            },
        )
        self.assertEqual(
            spike["pinned_format_parser_memory_map_differential"],
            {
                "case_count": 9,
                "matched_count": 9,
                "format_valid_count": 9,
                "file_types": [
                    "PE32",
                    "PE64",
                    "ELF32",
                    "ELF64",
                    "Mach-O32",
                    "Mach-O64",
                    "COM",
                    "MS-DOS",
                    "AmigaHunk",
                ],
            },
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
        self.assertEqual(oracle["case_count"], 63)
        self.assertEqual(len(oracle["compare_find_divergences"]), 4)


if __name__ == "__main__":
    unittest.main()
