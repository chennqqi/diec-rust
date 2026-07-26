import hashlib
import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[2]
REFERENCE = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "rquickjs-rule-runtime.json"
)


class RQuickJsRuleRuntimeSpikeTests(unittest.TestCase):
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
            self.reference["candidate"]["version"],
            "0.12.1",
        )
        self.assertEqual(
            self.reference["candidate"]["engine_version"],
            "0.15.1",
        )
        self.assertEqual(
            self.reference["candidate"]["features"],
            ["std"],
        )

    def test_reference_matches_spike_inputs(self):
        experiment = self.reference["experiment"]
        paths = {
            "cargo_toml_sha256": (
                ROOT / "spikes" / "rquickjs-rule-runtime" / "Cargo.toml"
            ),
            "cargo_lock_sha256": (
                ROOT / "spikes" / "rquickjs-rule-runtime" / "Cargo.lock"
            ),
            "source_sha256": (
                ROOT
                / "spikes"
                / "rquickjs-rule-runtime"
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
        self.assertTrue(
            self.reference["fixture"]["sloppy_script_required"]
        )
        self.assertEqual(
            self.reference["isolated_eval"],
            {
                "bytes": 2_902_881,
                "error_count": 1,
                "error_path": (
                    "db/Binary/"
                    "format_bin.Nintendo-certified-file.1.sg"
                ),
                "files": 2235,
                "operation": "sloppy eval with explicit host proxy",
            },
        )
        self.assertEqual(
            self.reference["shared_eval"]["error_count"],
            3,
        )

    def test_reference_records_native_resource_limits(self):
        fixture = self.reference["fixture"]
        self.assertTrue(fixture["interrupt_observed"])
        self.assertTrue(fixture["memory_limit_observed"])
        self.assertEqual(fixture["memory_limit_bytes"], 4 * 1024 * 1024)
        self.assertEqual(
            fixture["external_cancel"],
            {
                "hard_stop_handler_call_limit": 1_000_000,
                "hard_stop_reached": False,
                "interrupt_observed": True,
                "requested": True,
                "same_context_recovered": True,
                "same_context_recovery_result": "42",
            },
        )
        self.assertEqual(
            fixture["native_host_cooperative_cancel"],
            {
                "hard_stop_iteration_limit": 1_000_000,
                "hard_stop_reached": False,
                "iteration_count_positive": True,
                "requested": True,
                "returned": True,
            },
        )
        self.assertEqual(
            fixture["wall_clock_deadline"],
            {
                "deadline_expired": True,
                "deadline_milliseconds": 25,
                "hard_stop_handler_call_limit": 1_000_000,
                "hard_stop_reached": False,
                "interrupt_observed": True,
                "same_context_recovered": True,
            },
        )
        self.assertEqual(
            fixture["native_host_cooperative_deadline"],
            {
                "deadline_expired": True,
                "deadline_milliseconds": 25,
                "hard_stop_iteration_limit": 10_000_000,
                "hard_stop_reached": False,
                "iteration_count_positive": True,
                "returned": True,
                "same_context_recovered": True,
            },
        )
        self.assertEqual(
            fixture["numeric_host_api"],
            {
                "expected": [
                    0x563412,
                    0x123456,
                    0x123456,
                    0xFFFFFFFF,
                    0x0FFFFFFF,
                    0,
                ],
                "matches_qt5_qt6_oracle": True,
                "methods": [
                    "X.U24",
                    "X.read_uint24",
                    "Util.shru64",
                ],
                "result": [
                    0x563412,
                    0x123456,
                    0x123456,
                    0xFFFFFFFF,
                    0x0FFFFFFF,
                    0,
                ],
            },
        )

    def test_nintendo_probe_uses_real_init_and_include_sequence(self):
        detection = self.reference["nintendo_detect"]
        self.assertEqual(detection["init_sequence"], ["_init", "Binary/_init"])
        self.assertEqual(
            detection["include_trace"],
            ["_debug", "_runtime_helpers", "language", "read"],
        )
        self.assertTrue(detection["all_match"])
        self.assertEqual(detection["matched_count"], 14)
        lifecycle = detection["selected_lifecycle"]
        self.assertTrue(lifecycle["all_match"])
        self.assertEqual(lifecycle["rule_count"], 292)
        self.assertEqual(lifecycle["include_call_count"], 30)
        self.assertEqual(lifecycle["sample_count"], 14)
        self.assertEqual(lifecycle["matched_count"], 14)
        self.assertEqual(
            lifecycle["selected_rules"],
            [
                "archive_DEFLATE.1.sg",
                "audio_EXA.1.sg",
                "format_bin.Nintendo-certified-file.1.sg",
            ],
        )
        self.assertEqual(lifecycle["selected_detect_fallback_call_count"], 0)
        self.assertEqual(
            lifecycle["non_target_top_level_fallback_calls"],
            [
                "Binary.getString",
                "Binary.getString.replace",
                "Binary.getString.replace.match",
            ],
        )

    def test_full_binary_detect_diagnostic_is_scoped_as_gap_inventory(self):
        diagnostic = self.reference["full_binary_detect_diagnostic"]
        self.assertTrue(diagnostic["completed"])
        self.assertEqual(diagnostic["attempted_detect_count"], 292)
        self.assertEqual(diagnostic["accepted_detect_count"], 281)
        self.assertEqual(diagnostic["detect_error_count"], 11)
        self.assertEqual(diagnostic["include_call_count"], 30)
        self.assertEqual(diagnostic["compatibility_overlay_count"], 1)
        self.assertEqual(diagnostic["fallback_rule_count"], 253)
        self.assertEqual(diagnostic["fallback_call_total"], 496)
        self.assertEqual(diagnostic["fallback_truncated_rule_count"], 0)
        self.assertEqual(diagnostic["zero_recorded_fallback_rule_count"], 39)
        self.assertEqual(diagnostic["zero_recorded_fallback_error_count"], 0)
        self.assertFalse(diagnostic["detection_evidence_valid"])
        self.assertEqual(len(diagnostic["fallback_paths"]), 34)
        self.assertEqual(len(diagnostic["error_rules"]), 11)
        self.assertEqual(
            diagnostic["error_categories"],
            {
                "fallback_proxy_reached_string_result_boundary": 10,
                "no_input_detection_name": 1,
            },
        )
        manifest = json.loads(
            (
                ROOT
                / diagnostic["input"]["generator_manifest"]
            ).read_text(encoding="utf-8")
        )
        sample = next(
            sample
            for sample in manifest["samples"]
            if sample["name"] == diagnostic["input"]["name"]
        )
        self.assertEqual(sample["size"], diagnostic["input"]["bytes"])
        self.assertEqual(sample["sha256"], diagnostic["input"]["sha256"])

    def test_basic_host_api_increment_records_remaining_dynamic_gaps(self):
        increment = self.reference["basic_host_api_increment"]
        numeric_oracle = increment["numeric_oracle"]
        for profile in ("qt5", "qt6"):
            path = ROOT / numeric_oracle[f"{profile}_report"]
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                numeric_oracle[f"{profile}_report_sha256"],
            )
        comparison = ROOT / numeric_oracle["comparison_report"]
        self.assertEqual(
            hashlib.sha256(comparison.read_bytes()).hexdigest(),
            numeric_oracle["comparison_report_sha256"],
        )
        after = increment["after"]
        self.assertEqual(after["attempted_detect_count"], 292)
        self.assertEqual(after["accepted_detect_count"], 285)
        self.assertEqual(after["detect_error_count"], 7)
        self.assertEqual(after["include_call_count"], 30)
        self.assertEqual(after["fallback_rule_count"], 233)
        self.assertEqual(after["fallback_call_total"], 365)
        self.assertEqual(after["fallback_truncated_rule_count"], 0)
        self.assertEqual(len(after["fallback_paths"]), 17)
        self.assertEqual(after["zero_recorded_fallback_rule_count"], 59)
        self.assertEqual(after["zero_recorded_fallback_error_count"], 0)
        self.assertEqual(after["unsupported_signature_rule_count"], 32)
        self.assertEqual(after["unsupported_signature_call_total"], 331)
        self.assertEqual(after["unsupported_signature_pattern_count"], 317)
        self.assertEqual(
            after["unsupported_signature_patterns_truncated_rule_count"],
            0,
        )
        inventory = json.loads(
            (ROOT / after["unsupported_signature_inventory"]).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            inventory["patterns_lf_sha256"],
            after["unsupported_signature_patterns_lf_sha256"],
        )
        self.assertEqual(
            inventory["pattern_count"],
            after["unsupported_signature_pattern_count"],
        )
        self.assertFalse(after["detection_evidence_valid"])
        self.assertEqual(len(after["error_rules"]), 7)
        self.assertNotIn("Binary.read_uint24", after["fallback_paths"])
        self.assertNotIn("Util.shru64", after["fallback_paths"])
        self.assertNotIn("Binary.read_uint32", after["fallback_paths"])

    def test_binary_compare_increment_records_wrapper_and_remaining_gaps(self):
        increment = self.reference["binary_compare_increment"]
        oracle = increment["oracle"]
        baseline = ROOT / oracle["baseline"]
        self.assertEqual(
            hashlib.sha256(baseline.read_bytes()).hexdigest(),
            oracle["baseline_sha256"],
        )
        self.assertEqual(oracle["case_count"], 66)
        self.assertEqual(oracle["wrapper_case_count"], 7)
        self.assertEqual(oracle["wrapper_matched_count"], 7)
        self.assertTrue(oracle["negative_offset_qstring_mid_clamp_observed"])
        after = increment["after"]
        self.assertEqual(after["attempted_detect_count"], 292)
        self.assertEqual(after["accepted_detect_count"], 292)
        self.assertEqual(after["detect_error_count"], 0)
        self.assertEqual(after["include_call_count"], 30)
        self.assertEqual(after["fallback_rule_count"], 16)
        self.assertEqual(after["fallback_call_total"], 58)
        self.assertEqual(sum(after["fallback_path_counts"].values()), 58)
        self.assertEqual(len(after["fallback_path_counts"]), 18)
        self.assertEqual(after["zero_recorded_fallback_rule_count"], 276)
        self.assertEqual(after["signature_calling_rule_count"], 255)
        self.assertEqual(after["signature_compare_call_total"], 799)
        self.assertEqual(after["signature_compare_fast_path_total"], 776)
        self.assertEqual(after["signature_compare_generic_path_total"], 23)
        self.assertEqual(after["signature_compare_quirk_total"], 5)
        self.assertEqual(after["signature_compare_error_total"], 0)
        self.assertEqual(after["signature_compare_unique_errors"], [])
        self.assertFalse(after["detection_evidence_valid"])
        self.assertNotIn("Binary.compare", after["fallback_path_counts"])

    def test_signature_search_increment_records_branch_effect_and_gaps(self):
        increment = self.reference["signature_search_increment"]
        oracle = increment["oracle"]
        baseline = ROOT / oracle["baseline"]
        self.assertEqual(
            hashlib.sha256(baseline.read_bytes()).hexdigest(),
            oracle["baseline_sha256"],
        )
        self.assertEqual(oracle["case_count"], 66)
        self.assertEqual(oracle["wrapper_case_count"], 4)
        self.assertEqual(oracle["wrapper_matched_count"], 4)
        self.assertTrue(oracle["oversized_range_clamp_observed"])
        self.assertTrue(oracle["size_minus_one_to_eof_observed"])
        after = increment["after"]
        self.assertEqual(after["attempted_detect_count"], 292)
        self.assertEqual(after["accepted_detect_count"], 291)
        self.assertEqual(after["detect_error_count"], 1)
        self.assertEqual(after["error_rules"], ["data_overlays.6.sg"])
        self.assertEqual(after["include_call_count"], 30)
        self.assertEqual(after["fallback_rule_count"], 14)
        self.assertEqual(after["fallback_call_total"], 39)
        self.assertEqual(sum(after["fallback_path_counts"].values()), 39)
        self.assertEqual(len(after["fallback_path_counts"]), 15)
        self.assertEqual(after["fallback_truncated_rule_count"], 0)
        self.assertEqual(after["zero_recorded_fallback_rule_count"], 278)
        self.assertEqual(after["zero_recorded_fallback_error_count"], 0)
        self.assertEqual(after["signature_calling_rule_count"], 255)
        self.assertEqual(after["signature_compare_call_total"], 1179)
        self.assertEqual(after["signature_compare_fast_path_total"], 1115)
        self.assertEqual(after["signature_compare_generic_path_total"], 64)
        self.assertEqual(after["signature_compare_quirk_total"], 5)
        self.assertEqual(after["signature_compare_error_total"], 0)
        self.assertEqual(after["signature_search_call_total"], 11)
        self.assertEqual(after["signature_search_calling_rule_count"], 4)
        self.assertEqual(
            after["signature_search_method_call_totals"],
            {
                "fSig": 5,
                "findSignature": 0,
                "isSignaturePresent": 6,
            },
        )
        self.assertEqual(after["signature_search_match_total"], 0)
        self.assertEqual(after["signature_search_quirk_total"], 1)
        self.assertEqual(after["signature_search_error_total"], 0)
        self.assertEqual(after["signature_search_unique_errors"], [])
        self.assertFalse(after["detection_evidence_valid"])
        for method in (
            "Binary.fSig",
            "Binary.findSignature",
            "Binary.isSignaturePresent",
        ):
            self.assertNotIn(method, after["fallback_path_counts"])
        self.assertIn("truthy fallback proxies", increment["branch_effect"])

    def test_binary_lifecycle_uses_fixed_order_and_exact_overlays(self):
        lifecycle = self.reference["binary_lifecycle"]
        self.assertEqual(lifecycle["files"], 292)
        self.assertEqual(lifecycle["bytes"], 1_122_477)
        self.assertEqual(lifecycle["include_call_count"], 30)
        self.assertEqual(
            lifecycle["order_sha256"],
            "27138d68ed788dd2609b7c533fecf540593fa2e4ddb7195adc26b1a9ff0e1ff3",
        )
        self.assertEqual(lifecycle["raw"]["error_count"], 3)
        self.assertEqual(
            [error["index"] for error in lifecycle["raw"]["errors"]],
            [212, 288, 291],
        )
        self.assertEqual(
            lifecycle["with_compatibility_overlays"]["error_count"], 0
        )
        self.assertEqual(
            lifecycle["with_compatibility_overlays"][
                "overlay_applied_count"
            ],
            3,
        )
        lexical = lifecycle["per_rule_lexical_wrapper"]
        self.assertEqual(lexical["error_count"], 0)
        self.assertEqual(lexical["detect_function_count"], 292)
        self.assertEqual(lexical["non_function_detect_count"], 0)
        self.assertEqual(lexical["overlay_applied_count"], 1)
        self.assertEqual(
            lexical["overlay_id"], "nintendo-unused-var-tp-v1"
        )
        for overlay in lifecycle["compatibility_overlays"]:
            with self.subTest(overlay=overlay["id"]):
                rule = ROOT / "upstream" / "Detect-It-Easy" / overlay["path"]
                self.assertEqual(rule.stat().st_size, overlay["source_bytes"])
                self.assertEqual(
                    hashlib.sha256(rule.read_bytes()).hexdigest(),
                    overlay["source_sha256"],
                )
                self.assertEqual(
                    len(overlay["declaration"].encode()),
                    len(overlay["replacement"].encode()),
                )
                self.assertEqual(
                    rule.read_bytes().count(
                        overlay["declaration"].encode()
                    ),
                    1,
                )

    def test_reference_records_manifest_pinned_compatibility_overlay(self):
        overlay = self.reference["fixture"][
            "nintendo_compatibility_overlay"
        ]
        self.assertEqual(overlay["id"], "nintendo-unused-var-tp-v1")
        self.assertTrue(overlay["eval_accepted"])
        self.assertTrue(overlay["evaluated_length_unchanged"])
        rule = (
            ROOT
            / "upstream"
            / "Detect-It-Easy"
            / "db"
            / "Binary"
            / "format_bin.Nintendo-certified-file.1.sg"
        )
        self.assertEqual(rule.stat().st_size, overlay["source_bytes"])
        self.assertEqual(
            hashlib.sha256(rule.read_bytes()).hexdigest(),
            overlay["source_sha256"],
        )
        corpus = self.reference[
            "isolated_eval_with_compatibility_overlay"
        ]
        self.assertEqual(corpus["files"], 2235)
        self.assertEqual(corpus["bytes"], 2_902_881)
        self.assertEqual(corpus["overlay_applied_count"], 1)
        self.assertEqual(corpus["error_count"], 0)
        self.assertTrue(corpus["preserves_source_file"])

    def test_script_scope_probe_records_qt5_incompatibility(self):
        scope = self.reference["script_scope"]
        self.assertEqual(scope["rule_count"], 7)
        self.assertEqual(scope["qt5_detection_count"], 7)
        self.assertEqual(scope["quickjs_detection_count"], 4)
        self.assertEqual(scope["quickjs_eval_error_count"], 3)
        self.assertFalse(scope["matches_qt5_oracle"])
        self.assertEqual(
            scope["lexical_wrapper"],
            {
                "detection_count": 7,
                "eval_error_count": 0,
                "matches_qt5_oracle": True,
                "operation": (
                    "shared host/global context with per-rule function "
                    "lexical wrapper and immediate detect invocation"
                ),
            },
        )
        self.assertEqual(
            [error["name"] for error in scope["quickjs_errors"]],
            [
                "scope_const_assign.2.sg",
                "scope_const_detect.4.sg",
                "scope_debug_assign.7.sg",
            ],
        )
        for field in ("fixture_manifest", "qt5_baseline"):
            path = ROOT / scope[field]
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                scope[f"{field}_sha256"],
            )

    def test_script_state_probe_bounds_lexical_wrapper(self):
        state = self.reference["script_state"]
        self.assertEqual(state["rule_count"], 7)
        self.assertEqual(state["qt5_detection_count"], 7)
        self.assertEqual(
            state["raw_shared_context"],
            {
                "detection_count": 7,
                "eval_error_count": 0,
                "matches_qt5_oracle": True,
            },
        )
        self.assertEqual(state["lexical_wrapper"]["detection_count"], 5)
        self.assertEqual(state["lexical_wrapper"]["eval_error_count"], 2)
        self.assertFalse(state["lexical_wrapper"]["matches_qt5_oracle"])
        self.assertEqual(
            state["lexical_wrapper"]["error_rules"],
            ["state_var_update.2.sg", "state_function_read.4.sg"],
        )
        for field in ("fixture_manifest", "qt5_baseline"):
            path = ROOT / state[field]
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                state[f"{field}_sha256"],
            )
        audit_path = ROOT / state["fixed_binary_static_audit"]
        self.assertEqual(
            hashlib.sha256(audit_path.read_bytes()).hexdigest(),
            state["fixed_binary_static_audit_sha256"],
        )
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        self.assertEqual(
            audit["wrapper_loss_candidate_count"],
            state["fixed_binary_wrapper_loss_candidate_count"],
        )


if __name__ == "__main__":
    unittest.main()
