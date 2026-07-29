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
            "tracking_allocator_source_sha256": (
                ROOT
                / "spikes"
                / "rquickjs-rule-runtime"
                / "src"
                / "tracking_allocator.rs"
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
        self.assertTrue(fixture["memory_limit_same_context_recovered"])
        self.assertEqual(
            fixture["memory_limit_same_context_recovery_result"],
            "42",
        )
        self.assertEqual(
            fixture["tracking_allocator"],
            {
                "accounting": (
                    "RustAllocator allocation Layout bytes: aligned payload "
                    "plus internal header"
                ),
                "denied_allocation_count": 1,
                "high_water_bytes": 109_056,
                "limit_bytes": 4 * 1024 * 1024,
                "live_bytes_after_drop": 0,
                "live_bytes_before_drop": 107_976,
                "oversized_allocation_error": "out of memory",
                "same_context_recovered": True,
                "same_context_recovery_result": "42",
                "set_memory_limit_used": False,
            },
        )
        self.assertEqual(
            fixture["stack_limit"],
            {
                "bytes": 128 * 1024,
                "overflow_observed": True,
                "same_context_recovered": True,
                "same_context_recovery_result": "42",
            },
        )
        self.assertEqual(
            fixture["native_host_panic"],
            {
                "caught_at_rust_eval_boundary": True,
                "payload_matches_sentinel": True,
                "same_context_recovered": True,
                "same_context_recovery_result": "42",
                "unwound_across_c_abi": False,
            },
        )
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

    def test_full_binary_corpus_oracle_is_hash_bound_and_complete(self):
        oracle = self.reference["full_binary_corpus_oracle"]
        self.assertTrue(oracle["all_match"])
        self.assertEqual(oracle["sample_count"], 14)
        self.assertEqual(oracle["matched_count"], 14)
        self.assertEqual(oracle["input_identity_matched_count"], 14)
        self.assertEqual(oracle["rule_count_per_sample"], 292)
        self.assertEqual(oracle["attempted_detect_count"], 14 * 292)
        self.assertEqual(oracle["accepted_detect_count"], 14 * 292)
        self.assertEqual(oracle["detect_error_count"], 0)
        self.assertEqual(oracle["fallback_call_total"], 0)
        self.assertEqual(oracle["signature_compare_error_total"], 0)
        self.assertEqual(oracle["signature_search_error_total"], 0)
        self.assertEqual(oracle["detection_count"], 21)
        self.assertEqual(oracle["include_call_count_per_sample"], 30)
        self.assertEqual(oracle["compatibility_overlay_count_per_sample"], 1)
        self.assertEqual(oracle["unambiguous_priority_sample_count"], 14)
        self.assertEqual(oracle["nintendo_info_matched_count"], 14)
        for path_field, hash_field in (
            ("corpus_manifest", "corpus_manifest_sha256"),
            ("baseline", "baseline_sha256"),
        ):
            path = ROOT / oracle[path_field]
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                oracle[hash_field],
            )
        self.assertEqual(
            oracle["result_sort_oracle"]["component"],
            (
                "horsicq/XScanEngine@"
                "dfe4a419e4f491bb23688ba03c5a5bf39e34da83"
            ),
        )
        self.assertIn(
            "std::sort",
            oracle["result_sort_oracle"]["equal_priority_limitation"],
        )
        self.assertIn(
            "not all-rule or all-format compatibility",
            oracle["scope"],
        )
        measurement = oracle["runtime_measurement"]
        self.assertEqual(measurement["repeat_count"], 3)
        self.assertEqual(measurement["sample_runtime_count_per_repeat"], 14)
        self.assertTrue(measurement["stable_projection_equal"])
        self.assertTrue(measurement["projection_hash_emitted_by_spike"])
        self.assertEqual(
            measurement["stable_projection_sha256"],
            "286e778c3891dd3b289446526f2910601f9e25932feec25489ee74adbcc5c326",
        )
        self.assertEqual(
            measurement["native_checkpoint"],
            {
                "call_total": 16_439,
                "can_interrupt_single_native_call": True,
                "candidate_interval": 4096,
                "compare_call_total": 16_285,
                "search_call_total": 154,
                "semantics": (
                    "one callback at each Binary signature compare/search "
                    "entry and then before every 4096th searched candidate "
                    "position within the same native call"
                ),
            },
        )
        self.assertEqual(
            measurement["interrupt"],
            {
                "detect_handler_call_sum": 9,
                "handler_call_total": 28,
                "handler_calls_outside_detects": 19,
                "handler_semantics": (
                    "one QuickJS-NG interrupt callback invocation; "
                    "each sample uses one monotonic runtime counter"
                ),
                "maximum_handler_calls_per_rule": 1,
            },
        )
        memory = measurement["memory"]
        self.assertEqual(memory["checkpoint_count"], 14 * (292 + 3))
        self.assertEqual(
            memory["maximum_observed_malloc_size"],
            {
                "bytes": 654_562,
                "sample": "ps3-type-1-elf.self",
            },
        )
        self.assertEqual(
            memory["maximum_observed_memory_used_size"],
            {
                "bytes": 623_012,
                "sample": "ps3-type-1-elf.self",
            },
        )
        self.assertFalse(memory["transient_high_water_measured"])
        self.assertIn("transient in-eval", memory["scope"])

    def test_full_binary_corpus_tracked_heap_is_stable_bounded_and_scoped(self):
        evidence = self.reference["full_binary_corpus_tracked_heap"]
        self.assertTrue(evidence["all_match"])
        self.assertEqual(evidence["sample_count"], 14)
        self.assertEqual(evidence["matched_count"], 14)
        self.assertEqual(evidence["attempted_detect_count"], 14 * 292)
        self.assertEqual(evidence["accepted_detect_count"], 14 * 292)
        self.assertEqual(evidence["detect_error_count"], 0)
        self.assertEqual(evidence["fallback_call_total"], 0)
        measurement = evidence["runtime_measurement"]
        self.assertEqual(measurement["repeat_count"], 3)
        self.assertEqual(measurement["sample_runtime_count_per_repeat"], 14)
        self.assertTrue(measurement["stable_projection_equal"])
        self.assertTrue(measurement["projection_hash_emitted_by_spike"])
        self.assertTrue(
            measurement["projection_hash_independently_recomputed"]
        )
        self.assertEqual(
            measurement["stable_projection_sha256"],
            "c455f6932322ff8161a4f6c9288710b5ed792ff5486b4459e11ef27e794e45c4",
        )
        memory = measurement["memory"]
        self.assertTrue(memory["transient_high_water_measured"])
        self.assertEqual(memory["limit_bytes_per_sample_runtime"], 32 * 1024 * 1024)
        self.assertEqual(memory["maximum_high_water_bytes"], 4_478_992)
        self.assertEqual(
            memory["maximum_high_water_sample"],
            "ps3-type-1-elf.self",
        )
        self.assertEqual(memory["denied_allocation_count"], 0)
        self.assertTrue(memory["all_runtimes_released_to_zero"])
        self.assertFalse(memory["set_memory_limit_used"])
        self.assertIn("custom tracking/limit allocator", evidence["scope"])
        self.assertIn("not default-allocator", evidence["scope"])
        self.assertIn("not", evidence["scope"])
        self.assertIn("cross-platform proof", evidence["scope"])

    def test_representative_format_runtime_matrix_is_stable_and_scoped(self):
        matrix = self.reference["representative_format_runtime_matrix"]
        self.assertTrue(matrix["all_match"])
        self.assertEqual(matrix["repeat_count"], 3)
        self.assertEqual(matrix["format_count"], 7)
        self.assertEqual(matrix["case_count_per_repeat"], 25)
        self.assertEqual(matrix["matched_count_per_repeat"], 25)
        self.assertEqual(
            matrix["interrupt_handler_call_total_per_repeat"],
            25,
        )
        self.assertEqual(matrix["memory_checkpoint_count_per_repeat"], 75)
        self.assertTrue(matrix["stable_canonical_reports_equal"])
        self.assertFalse(matrix["transient_high_water_measured"])
        self.assertIn("representative", matrix["scope"])
        self.assertIn("not all formats", matrix["scope"])
        formats = matrix["formats"]
        self.assertEqual(
            {name: value["case_count"] for name, value in formats.items()},
            {
                "apk": 3,
                "archive": 3,
                "dex": 3,
                "elf": 6,
                "macho": 4,
                "pdf": 3,
                "pe": 3,
            },
        )
        self.assertTrue(
            all(
                value["interrupt_handler_call_total"]
                == value["case_count"]
                for value in formats.values()
            )
        )
        self.assertTrue(
            all(
                value["memory_checkpoint_count"]
                == 3 * value["case_count"]
                for value in formats.values()
            )
        )
        self.assertEqual(
            matrix["maximum_observed_malloc_size"],
            {
                "bytes": 124_485,
                "case": "verbose_stored_zip",
                "format": "archive",
                "stage": "after_rule",
            },
        )
        self.assertEqual(
            matrix["maximum_observed_memory_used_size"],
            {
                "bytes": 113_926,
                "case": "verbose_stored_zip",
                "format": "archive",
                "stage": "after_rule",
            },
        )
        self.assertEqual(
            {
                name: value["canonical_report_sha256"]
                for name, value in formats.items()
            },
            {
                "apk": (
                    "86f6eb3869c53a74ad1f80bb1880777f55a8f65fea6ab5dfa3571fb41646c75c"
                ),
                "archive": (
                    "aaba2413d96771bc5bd10f4733a320c015bc92bd97acfe344a7f54acbe988107"
                ),
                "dex": (
                    "28e38b2520406a5d9348c251befbb13abe5169ed222a34101ccff716d9681d8d"
                ),
                "elf": (
                    "f5a2277b1ef10a31448ddcb1d176d3ece74917d978a8606048f82990163f6ce8"
                ),
                "macho": (
                    "fd12966f6243a6c7995bc8f565ecdd72ee9d7b210f8e2be00f24f63c116a12f6"
                ),
                "pdf": (
                    "a4f8efe49ec4e0bb28954780b4539e298201eb6e20aa6b5d0e5fd3f00ed2f8c8"
                ),
                "pe": (
                    "13b6436d8eb326aa0f8075527bc9acd16132cba4e9a4ee4981c7f3dccfa3ca7e"
                ),
            },
        )
        tracked = matrix["tracked_heap"]
        self.assertTrue(tracked["all_match"])
        self.assertEqual(tracked["repeat_count"], 3)
        self.assertEqual(tracked["case_count_per_repeat"], 25)
        self.assertEqual(
            tracked["limit_bytes_per_case_runtime"],
            32 * 1024 * 1024,
        )
        self.assertEqual(tracked["denied_allocation_count_per_repeat"], 0)
        self.assertTrue(tracked["all_runtimes_released_to_zero"])
        self.assertTrue(tracked["stable_canonical_reports_equal"])
        self.assertTrue(tracked["transient_high_water_measured"])
        self.assertFalse(tracked["set_memory_limit_used"])
        self.assertEqual(tracked["maximum_high_water_bytes"], 134_792)
        self.assertEqual(tracked["maximum_high_water_format"], "macho")
        self.assertEqual(
            tracked["maximum_high_water_case"],
            "rust_macho64_x86_64_entry_point_match",
        )
        tracked_formats = tracked["formats"]
        self.assertEqual(
            {
                name: value["maximum_high_water_bytes"]
                for name, value in tracked_formats.items()
            },
            {
                "apk": 129_160,
                "archive": 130_560,
                "dex": 129_136,
                "elf": 129_392,
                "macho": 134_792,
                "pdf": 131_704,
                "pe": 129_176,
            },
        )
        self.assertEqual(
            {
                name: value["canonical_report_sha256"]
                for name, value in tracked_formats.items()
            },
            {
                "apk": (
                    "4de395c973069adbb40a4c1d3405f428154d41722b4b015d7c71f9358050f5dd"
                ),
                "archive": (
                    "6b82e6c324736dc88e54a780ae5c1b29cceb5e14bb46c94b982a34fa64c3ffd5"
                ),
                "dex": (
                    "9f795bba6ac85ab204ac410a3767535ce9aa26b54708a52a2cfe62dd72c78c48"
                ),
                "elf": (
                    "94e9ca327c8fb56d11d148631d23a3bf4fedf0489003a32807e38c4d30e6d9a5"
                ),
                "macho": (
                    "08a48936c916ca1536cef1363c9ba700919214bc2c832015509776dccadccb36"
                ),
                "pdf": (
                    "7f8005e862c19b3d12c34bdbda133b59a4ac230ef5384b4d6293421d12a0bbf4"
                ),
                "pe": (
                    "b646a1a918a689100914c14606e61d29ee11461a70d8f037b7df04572bcd6145"
                ),
            },
        )
        self.assertIn("not all-format", tracked["scope"])
        self.assertIn("not", tracked["scope"])
        self.assertIn("cross-platform proof", tracked["scope"])

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
        self.assertEqual(oracle["case_count"], 89)
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
        self.assertEqual(oracle["case_count"], 89)
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

    def test_overlay_host_increment_separates_context_and_nested_overlay(self):
        increment = self.reference["overlay_host_increment"]
        oracle = increment["oracle"]
        baseline = ROOT / oracle["baseline"]
        self.assertEqual(
            hashlib.sha256(baseline.read_bytes()).hexdigest(),
            oracle["baseline_sha256"],
        )
        self.assertEqual(oracle["case_count"], 89)
        self.assertEqual(oracle["overlay_host_case_count"], 3)
        self.assertEqual(oracle["overlay_host_matched_count"], 3)
        self.assertTrue(
            increment["adapter"]["file_part_is_independent_from_nested_overlay"]
        )
        after = increment["after"]
        self.assertEqual(after["attempted_detect_count"], 292)
        self.assertEqual(after["accepted_detect_count"], 292)
        self.assertEqual(after["detect_error_count"], 0)
        self.assertEqual(after["error_rules"], [])
        self.assertEqual(after["include_call_count"], 30)
        self.assertEqual(after["fallback_rule_count"], 12)
        self.assertEqual(after["fallback_call_total"], 34)
        self.assertEqual(sum(after["fallback_path_counts"].values()), 34)
        self.assertEqual(len(after["fallback_path_counts"]), 11)
        self.assertEqual(after["fallback_truncated_rule_count"], 0)
        self.assertEqual(after["zero_recorded_fallback_rule_count"], 280)
        self.assertEqual(after["zero_recorded_fallback_error_count"], 0)
        self.assertEqual(
            after["overlay_host_call_totals"],
            {
                "getOverlayOffset": 0,
                "getOverlaySize": 0,
                "isOverlay": 2,
                "isOverlayPresent": 0,
            },
        )
        self.assertEqual(len(after["overlay_host_calling_rules"]), 2)
        self.assertEqual(after["signature_calling_rule_count"], 254)
        self.assertEqual(after["signature_compare_call_total"], 1109)
        self.assertEqual(after["signature_compare_fast_path_total"], 1047)
        self.assertEqual(after["signature_compare_generic_path_total"], 62)
        self.assertEqual(after["signature_compare_quirk_total"], 5)
        self.assertEqual(after["signature_compare_error_total"], 0)
        self.assertEqual(after["signature_search_call_total"], 11)
        self.assertEqual(after["signature_search_calling_rule_count"], 4)
        self.assertEqual(after["signature_search_match_total"], 0)
        self.assertEqual(after["signature_search_quirk_total"], 1)
        self.assertEqual(after["signature_search_error_total"], 0)
        self.assertFalse(after["detection_evidence_valid"])
        for method in (
            "Binary.getOverlayOffset",
            "Binary.getOverlaySize",
            "Binary.isOverlay",
            "Binary.isOverlayPresent",
        ):
            self.assertNotIn(method, after["fallback_path_counts"])
        self.assertIn("short-circuited", increment["branch_effect"])

    def test_string_host_increment_matches_oracle_and_trace_totals(self):
        increment = self.reference["string_host_increment"]
        oracle = increment["oracle"]
        baseline = ROOT / oracle["baseline"]
        self.assertEqual(
            hashlib.sha256(baseline.read_bytes()).hexdigest(),
            oracle["baseline_sha256"],
        )
        self.assertEqual(oracle["case_count"], 89)
        self.assertEqual(oracle["string_context_case_count"], 15)
        self.assertEqual(oracle["string_context_matched_count"], 15)
        after = increment["after"]
        self.assertEqual(after["attempted_detect_count"], 292)
        self.assertEqual(after["accepted_detect_count"], 292)
        self.assertEqual(after["detect_error_count"], 0)
        self.assertEqual(after["error_rules"], [])
        self.assertEqual(after["include_call_count"], 30)
        self.assertEqual(after["fallback_rule_count"], 3)
        self.assertEqual(after["fallback_call_total"], 4)
        self.assertEqual(sum(after["fallback_path_counts"].values()), 4)
        self.assertEqual(len(after["fallback_path_counts"]), 4)
        self.assertEqual(after["fallback_truncated_rule_count"], 0)
        self.assertEqual(after["zero_recorded_fallback_rule_count"], 289)
        self.assertEqual(after["zero_recorded_fallback_error_count"], 0)
        self.assertEqual(
            after["string_host_call_totals"],
            {
                "getFileSuffix": 9,
                "getHeaderString": 5,
                "isPlainText": 2,
                "isUTF8Text": 0,
            },
        )
        self.assertEqual(len(after["string_host_calling_rules"]), 9)
        self.assertEqual(after["signature_compare_call_total"], 1109)
        self.assertEqual(after["signature_compare_fast_path_total"], 1047)
        self.assertEqual(after["signature_compare_generic_path_total"], 62)
        self.assertEqual(after["signature_compare_quirk_total"], 5)
        self.assertEqual(after["signature_compare_error_total"], 0)
        self.assertEqual(after["signature_search_call_total"], 11)
        self.assertEqual(after["signature_search_match_total"], 0)
        self.assertEqual(after["signature_search_error_total"], 0)
        self.assertFalse(after["detection_evidence_valid"])
        for method in (
            "Binary.getFileSuffix",
            "Binary.getHeaderString",
            "Binary.isPlainText",
            "Binary.isUTF8Text",
        ):
            self.assertNotIn(method, after["fallback_path_counts"])
        self.assertIn(
            "m_bIsUnicodeText",
            increment["remaining_undefined_behavior"],
        )

    def test_execution_context_increment_closes_observed_fallbacks(self):
        increment = self.reference["execution_context_increment"]
        oracle = increment["oracle"]
        baseline = ROOT / oracle["baseline"]
        self.assertEqual(
            hashlib.sha256(baseline.read_bytes()).hexdigest(),
            oracle["baseline_sha256"],
        )
        self.assertEqual(oracle["case_count"], 89)
        self.assertEqual(oracle["execution_context_case_count"], 3)
        self.assertEqual(oracle["execution_context_matched_count"], 3)
        self.assertEqual(oracle["text_prefill_case_count"], 4)
        self.assertEqual(oracle["text_prefill_matched_count"], 4)
        self.assertTrue(oracle["upstream_uninitialized_state_observed"])
        self.assertNotEqual(
            oracle["non_unicode_prefill_results"]["zero"],
            oracle["non_unicode_prefill_results"]["one"],
        )
        after = increment["after"]
        self.assertEqual(after["attempted_detect_count"], 292)
        self.assertEqual(after["accepted_detect_count"], 292)
        self.assertEqual(after["detect_error_count"], 0)
        self.assertEqual(after["error_rules"], [])
        self.assertEqual(after["fallback_rule_count"], 0)
        self.assertEqual(after["fallback_call_total"], 0)
        self.assertEqual(after["fallback_path_counts"], {})
        self.assertEqual(after["zero_recorded_fallback_rule_count"], 292)
        self.assertEqual(
            after["context_host_call_totals"],
            {
                "getScanID": 0,
                "isDebugData": 1,
                "isFilePart": 0,
                "isResource": 1,
            },
        )
        self.assertEqual(after["signature_compare_call_total"], 1105)
        self.assertEqual(after["signature_compare_fast_path_total"], 1043)
        self.assertEqual(after["signature_compare_generic_path_total"], 62)
        self.assertEqual(after["signature_search_call_total"], 11)
        self.assertEqual(after["detection_count"], 1)
        self.assertFalse(after["detection_evidence_valid"])
        self.assertIn(
            "0005-deterministic-text-classification.md",
            increment["adapter"]["text_policy_adr"],
        )
        self.assertIn(
            "Phase 1",
            increment["deterministic_deviation"]["waiver_status"],
        )

    def test_context_rule_differential_matches_fixed_sources_and_oracle(self):
        differential = self.reference["context_rule_differential"]
        oracle = differential["oracle"]
        for path_field, hash_field in (
            ("baseline", "baseline_sha256"),
            ("dockerfile", "dockerfile_sha256"),
            ("harness_source", "harness_source_sha256"),
            ("probe", "probe_sha256"),
        ):
            path = ROOT / oracle[path_field]
            with self.subTest(path=path_field):
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                    oracle[hash_field],
                )
        for source in oracle["rule_sources"]:
            path = ROOT / source["path"]
            with self.subTest(rule=source["path"]):
                self.assertEqual(path.stat().st_size, source["bytes"])
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                    source["sha256"],
                )
        baseline = json.loads(
            (ROOT / oracle["baseline"]).read_text(encoding="utf-8")
        )
        self.assertEqual(baseline["case_count"], 8)
        self.assertEqual(len(baseline["cases"]), 8)
        self.assertTrue(oracle["probe_passed"])
        self.assertEqual(oracle["qt_version"], "5.15.13")
        self.assertEqual(oracle["engine"], "QScriptEngine")
        self.assertEqual(differential["rust"]["case_count"], 8)
        self.assertEqual(differential["rust"]["matched_count"], 8)
        self.assertTrue(differential["rust"]["rule_bytes_preserved"])
        self.assertEqual(
            differential["coverage"]["positive_case_count"], 3
        )
        self.assertEqual(
            differential["coverage"]["negative_case_count"], 5
        )
        self.assertEqual(
            sum(
                bool(case["detect_result"])
                for case in baseline["cases"]
            ),
            3,
        )
        self.assertEqual(
            [
                case["detections"][0]
                for case in baseline["cases"]
                if case["detect_result"]
            ],
            differential["coverage"]["positive_detections"],
        )

    def test_pe_rule_differential_binds_real_context_and_qt5_oracle(self):
        differential = self.reference["pe_rule_differential"]
        oracle = differential["oracle"]
        for path_field, hash_field in (
            ("baseline", "baseline_sha256"),
            ("dockerfile", "dockerfile_sha256"),
            ("fixture", "fixture_sha256"),
            ("fixture_generator", "fixture_generator_sha256"),
            ("harness_source", "harness_source_sha256"),
            ("probe", "probe_sha256"),
        ):
            path = ROOT / oracle[path_field]
            with self.subTest(path=path_field):
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                    oracle[hash_field],
                )
        rule = oracle["rule_source"]
        rule_path = ROOT / rule["path"]
        self.assertEqual(rule_path.stat().st_size, rule["bytes"])
        self.assertEqual(
            hashlib.sha256(rule_path.read_bytes()).hexdigest(),
            rule["sha256"],
        )
        fixture = json.loads(
            (ROOT / oracle["fixture"]).read_text(encoding="utf-8")
        )
        baseline = json.loads(
            (ROOT / oracle["baseline"]).read_text(encoding="utf-8")
        )
        self.assertEqual(fixture["case_count"], 3)
        self.assertEqual(baseline["case_count"], 3)
        self.assertEqual(
            [case["id"] for case in fixture["cases"]],
            [
                "cygwin32_entry_point_match",
                "cygwin32_entry_point_mismatch",
                "cygwin32_entry_point_truncated",
            ],
        )
        self.assertTrue(oracle["probe_passed"])
        self.assertEqual(oracle["qt_version"], "5.15.13")
        self.assertEqual(oracle["engine"], "QScriptEngine")
        self.assertEqual(differential["rust"]["matched_count"], 3)
        self.assertEqual(
            differential["rust"]["compare_ep_call_count"],
            3,
        )
        self.assertEqual(
            differential["rust"]["compare_ep_error_count"],
            0,
        )
        self.assertEqual(
            differential["coverage"][
                "entry_point_and_physical_map_match_count"
            ],
            3,
        )
        self.assertEqual(
            differential["coverage"][
                "bounded_upstream_section_alias_count"
            ],
            1,
        )

    def test_elf_rule_differential_binds_real_context_and_qt5_oracle(self):
        differential = self.reference["elf_rule_differential"]
        oracle = differential["oracle"]
        for path_field, hash_field in (
            ("baseline", "baseline_sha256"),
            ("dockerfile", "dockerfile_sha256"),
            ("fixture", "fixture_sha256"),
            ("fixture_generator", "fixture_generator_sha256"),
            ("harness_source", "harness_source_sha256"),
            ("probe", "probe_sha256"),
        ):
            path = ROOT / oracle[path_field]
            with self.subTest(path=path_field):
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                    oracle[hash_field],
                )
        rule = oracle["rule_source"]
        rule_path = ROOT / rule["path"]
        self.assertEqual(rule_path.stat().st_size, rule["bytes"])
        self.assertEqual(
            hashlib.sha256(rule_path.read_bytes()).hexdigest(),
            rule["sha256"],
        )
        fixture = json.loads(
            (ROOT / oracle["fixture"]).read_text(encoding="utf-8")
        )
        baseline = json.loads(
            (ROOT / oracle["baseline"]).read_text(encoding="utf-8")
        )
        self.assertEqual(fixture["case_count"], 6)
        self.assertEqual(baseline["case_count"], 6)
        self.assertEqual(
            {case["elf_class"] for case in fixture["cases"]},
            {32, 64},
        )
        self.assertTrue(oracle["probe_passed"])
        self.assertEqual(oracle["qt_version"], "5.15.13")
        self.assertEqual(oracle["engine"], "QScriptEngine")
        self.assertEqual(differential["rust"]["matched_count"], 6)
        self.assertEqual(
            differential["rust"]["compare_ep_call_count"],
            6,
        )
        self.assertEqual(
            differential["rust"]["compare_ep_error_count"],
            0,
        )
        self.assertEqual(
            differential["coverage"][
                "entry_point_and_matcher_map_match_count"
            ],
            6,
        )
        self.assertEqual(
            differential["coverage"][
                "qt5_discarded_nonpositive_size_record_count"
            ],
            4,
        )
        self.assertEqual(
            differential["coverage"]["rust_declared_out_of_bounds_load_count"],
            4,
        )

    def test_macho_rule_differential_binds_real_context_and_qt5_oracle(self):
        differential = self.reference["macho_rule_differential"]
        oracle = differential["oracle"]
        for path_field, hash_field in (
            ("baseline", "baseline_sha256"),
            ("dockerfile", "dockerfile_sha256"),
            ("fixture", "fixture_sha256"),
            ("fixture_generator", "fixture_generator_sha256"),
            ("harness_source", "harness_source_sha256"),
            ("probe", "probe_sha256"),
        ):
            path = ROOT / oracle[path_field]
            with self.subTest(path=path_field):
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                    oracle[hash_field],
                )
        rule = oracle["rule_source"]
        rule_path = ROOT / rule["path"]
        self.assertEqual(rule_path.stat().st_size, rule["bytes"])
        self.assertEqual(
            hashlib.sha256(rule_path.read_bytes()).hexdigest(),
            rule["sha256"],
        )
        fixture = json.loads(
            (ROOT / oracle["fixture"]).read_text(encoding="utf-8")
        )
        baseline = json.loads(
            (ROOT / oracle["baseline"]).read_text(encoding="utf-8")
        )
        self.assertEqual(fixture["case_count"], 4)
        self.assertEqual(baseline["case_count"], 4)
        self.assertEqual(
            {case["architecture"] for case in fixture["cases"]},
            {"x86_64", "arm64"},
        )
        self.assertTrue(oracle["probe_passed"])
        self.assertEqual(oracle["qt_version"], "5.15.13")
        self.assertEqual(oracle["engine"], "QScriptEngine")
        self.assertEqual(differential["rust"]["matched_count"], 4)
        self.assertEqual(
            differential["rust"]["compare_ep_call_count"],
            29,
        )
        self.assertEqual(
            differential["rust"]["fast_path_count"],
            20,
        )
        self.assertEqual(
            differential["rust"]["generic_path_count"],
            9,
        )
        self.assertEqual(
            differential["coverage"][
                "entry_point_and_matcher_map_match_count"
            ],
            4,
        )
        self.assertEqual(
            differential["coverage"][
                "rust_declared_out_of_bounds_segment_count"
            ],
            1,
        )

    def test_dex_rule_differential_binds_real_context_and_qt5_oracle(self):
        differential = self.reference["dex_rule_differential"]
        oracle = differential["oracle"]
        for path_field, hash_field in (
            ("baseline", "baseline_sha256"),
            ("dockerfile", "dockerfile_sha256"),
            ("fixture", "fixture_sha256"),
            ("fixture_generator", "fixture_generator_sha256"),
            ("harness_source", "harness_source_sha256"),
            ("probe", "probe_sha256"),
        ):
            path = ROOT / oracle[path_field]
            with self.subTest(path=path_field):
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                    oracle[hash_field],
                )
        rule = oracle["rule_source"]
        rule_path = ROOT / rule["path"]
        self.assertEqual(rule_path.stat().st_size, rule["bytes"])
        self.assertEqual(
            hashlib.sha256(rule_path.read_bytes()).hexdigest(),
            rule["sha256"],
        )
        fixture = json.loads(
            (ROOT / oracle["fixture"]).read_text(encoding="utf-8")
        )
        baseline = json.loads(
            (ROOT / oracle["baseline"]).read_text(encoding="utf-8")
        )
        self.assertEqual(fixture["case_count"], 3)
        self.assertEqual(baseline["case_count"], 3)
        self.assertEqual(
            [case["parsed_strings"] for case in baseline["cases"]],
            [["/qdbh"], ["/nope"], [""]],
        )
        self.assertTrue(oracle["probe_passed"])
        self.assertEqual(oracle["qt_version"], "5.15.13")
        self.assertEqual(oracle["engine"], "QScriptEngine")
        self.assertEqual(
            oracle["xdex_commit"],
            "035c61966d3a9018edf80cd0013083ee32626e71",
        )
        self.assertEqual(differential["rust"]["matched_count"], 3)
        self.assertEqual(
            differential["rust"]["is_dex_string_present_call_count"],
            3,
        )
        self.assertEqual(
            differential["coverage"]["map_and_string_table_match_count"],
            3,
        )
        self.assertEqual(
            differential["coverage"][
                "rust_out_of_bounds_string_offset_count"
            ],
            1,
        )

    def test_apk_rule_differential_binds_real_context_and_qt5_oracle(self):
        differential = self.reference["apk_rule_differential"]
        oracle = differential["oracle"]
        for path_field, hash_field in (
            ("baseline", "baseline_sha256"),
            ("dockerfile", "dockerfile_sha256"),
            ("fixture", "fixture_sha256"),
            ("fixture_generator", "fixture_generator_sha256"),
            ("harness_source", "harness_source_sha256"),
            ("probe", "probe_sha256"),
        ):
            path = ROOT / oracle[path_field]
            with self.subTest(path=path_field):
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                    oracle[hash_field],
                )
        rule = oracle["rule_source"]
        rule_path = ROOT / rule["path"]
        self.assertEqual(rule_path.stat().st_size, rule["bytes"])
        self.assertEqual(
            hashlib.sha256(rule_path.read_bytes()).hexdigest(),
            rule["sha256"],
        )
        fixture = json.loads(
            (ROOT / oracle["fixture"]).read_text(encoding="utf-8")
        )
        baseline = json.loads(
            (ROOT / oracle["baseline"]).read_text(encoding="utf-8")
        )
        self.assertEqual(fixture["case_count"], 3)
        self.assertEqual(baseline["case_count"], 3)
        self.assertEqual(
            [case["archive_record_names"] for case in baseline["cases"]],
            [
                ["classes.dex", "assets/qdbh"],
                ["classes.dex", "assets/QDBH"],
                ["classes.dex", "assets/qdbh"],
            ],
        )
        self.assertTrue(oracle["probe_passed"])
        self.assertEqual(oracle["qt_version"], "5.15.13")
        self.assertEqual(oracle["engine"], "QScriptEngine")
        self.assertEqual(
            oracle["xarchive_commit"],
            "0fcd4e8d3e9933baac3b12246d82ac026557ffd0",
        )
        self.assertEqual(differential["rust"]["matched_count"], 3)
        self.assertEqual(
            differential["rust"]["is_archive_record_present_call_count"],
            3,
        )
        self.assertEqual(
            differential["coverage"]["record_name_list_match_count"],
            3,
        )
        self.assertEqual(
            differential["coverage"][
                "rust_local_header_signature_mismatch_count"
            ],
            2,
        )

    def test_archive_rule_differential_binds_real_context_and_qt5_oracle(self):
        differential = self.reference["archive_rule_differential"]
        oracle = differential["oracle"]
        for path_field, hash_field in (
            ("baseline", "baseline_sha256"),
            ("dockerfile", "dockerfile_sha256"),
            ("fixture", "fixture_sha256"),
            ("fixture_generator", "fixture_generator_sha256"),
            ("harness_source", "harness_source_sha256"),
            ("probe", "probe_sha256"),
        ):
            path = ROOT / oracle[path_field]
            with self.subTest(path=path_field):
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                    oracle[hash_field],
                )
        rule = oracle["rule_source"]
        rule_path = ROOT / rule["path"]
        self.assertEqual(rule_path.stat().st_size, rule["bytes"])
        self.assertEqual(
            hashlib.sha256(rule_path.read_bytes()).hexdigest(),
            rule["sha256"],
        )
        fixture = json.loads(
            (ROOT / oracle["fixture"]).read_text(encoding="utf-8")
        )
        baseline = json.loads(
            (ROOT / oracle["baseline"]).read_text(encoding="utf-8")
        )
        self.assertEqual(fixture["case_count"], 3)
        self.assertEqual(baseline["case_count"], 3)
        self.assertEqual(
            [case["verbose"] for case in baseline["cases"]],
            [True, False, True],
        )
        self.assertEqual(
            [
                (
                    case["native_format_name"],
                    case["native_format_version"],
                    case["native_format_options"],
                )
                for case in baseline["cases"]
            ],
            [("ZIP", "2.0", "Store")] * 3,
        )
        self.assertTrue(oracle["probe_passed"])
        self.assertEqual(oracle["qt_version"], "5.15.13")
        self.assertEqual(oracle["engine"], "QScriptEngine")
        self.assertEqual(
            oracle["xarchive_commit"],
            "0fcd4e8d3e9933baac3b12246d82ac026557ffd0",
        )
        self.assertEqual(differential["rust"]["matched_count"], 3)
        self.assertEqual(
            differential["rust"]["is_verbose_call_count"],
            3,
        )
        self.assertEqual(
            differential["rust"]["metadata_getter_call_count"],
            6,
        )
        self.assertEqual(
            differential["coverage"]["metadata_match_count"],
            3,
        )
        self.assertEqual(
            differential["coverage"][
                "rust_local_header_signature_mismatch_count"
            ],
            1,
        )

    def test_pdf_rule_differential_binds_real_context_and_qt5_oracle(self):
        differential = self.reference["pdf_rule_differential"]
        oracle = differential["oracle"]
        for path_field, hash_field in (
            ("baseline", "baseline_sha256"),
            ("dockerfile", "dockerfile_sha256"),
            ("fixture", "fixture_sha256"),
            ("fixture_generator", "fixture_generator_sha256"),
            ("harness_source", "harness_source_sha256"),
            ("probe", "probe_sha256"),
        ):
            path = ROOT / oracle[path_field]
            with self.subTest(path=path_field):
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                    oracle[hash_field],
                )
        rule = oracle["rule_source"]
        rule_path = ROOT / rule["path"]
        self.assertEqual(rule_path.stat().st_size, rule["bytes"])
        self.assertEqual(
            hashlib.sha256(rule_path.read_bytes()).hexdigest(),
            rule["sha256"],
        )
        fixture = json.loads(
            (ROOT / oracle["fixture"]).read_text(encoding="utf-8")
        )
        baseline = json.loads(
            (ROOT / oracle["baseline"]).read_text(encoding="utf-8")
        )
        self.assertEqual(fixture["case_count"], 3)
        self.assertEqual(baseline["case_count"], 3)
        self.assertEqual(
            [case["object_count"] for case in baseline["cases"]],
            [2, 1, 0],
        )
        self.assertEqual(
            [case["native_creator_values"] for case in baseline["cases"]],
            [["Tool A", "Tool)B"], [], []],
        )
        self.assertEqual(
            [
                case["native_header_comment_hex"]
                for case in baseline["cases"]
            ],
            ["e2e3cfd3", "4153434949", "fffe"],
        )
        self.assertTrue(oracle["probe_passed"])
        self.assertEqual(oracle["qt_version"], "5.15.13")
        self.assertEqual(oracle["engine"], "QScriptEngine")
        self.assertEqual(
            oracle["xpdf_commit"],
            "cdcee54dce97f566f2c023f400a457f4e6278de2",
        )
        self.assertEqual(differential["rust"]["matched_count"], 3)
        self.assertEqual(
            differential["rust"]["get_string_values_by_key_call_count"],
            6,
        )
        self.assertEqual(
            differential["rust"]["get_header_comment_as_hex_call_count"],
            3,
        )
        self.assertEqual(differential["rust"]["object_match_count"], 3)
        self.assertEqual(differential["rust"]["token_match_count"], 3)
        self.assertEqual(differential["coverage"]["object_match_count"], 3)
        self.assertEqual(differential["coverage"]["token_match_count"], 3)

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

    def test_full_rule_corpus_tracked_heap_is_stable_bounded_and_scoped(self):
        evidence = self.reference["full_rule_corpus_tracked_heap"]
        self.assertTrue(evidence["all_eval_accepted"])
        self.assertEqual(evidence["files"], 2235)
        self.assertEqual(evidence["bytes"], 2_902_881)
        self.assertEqual(evidence["compatibility_overlay_count"], 1)
        self.assertEqual(evidence["repeat_count"], 3)
        self.assertTrue(evidence["stable_projection_equal"])
        self.assertTrue(evidence["projection_hash_emitted_by_spike"])
        self.assertTrue(
            evidence["projection_hash_independently_recomputed"]
        )
        self.assertEqual(
            evidence["stable_projection_sha256"],
            "582d5af0995925fa9c2188a38d999e0bcb3373b91fe22510798786828cbc5f58",
        )
        self.assertEqual(evidence["limit_bytes"], 32 * 1024**2)
        self.assertEqual(evidence["high_water_bytes"], 3_486_384)
        self.assertEqual(evidence["live_bytes_before_drop"], 171_272)
        self.assertEqual(evidence["denied_allocation_count"], 0)
        self.assertTrue(evidence["all_runtimes_released_to_zero"])
        self.assertFalse(evidence["set_memory_limit_used"])
        self.assertEqual(
            evidence["tracking_accounting"],
            (
                "RustAllocator allocation Layout bytes: aligned payload "
                "plus internal header"
            ),
        )
        projection = {
            "bytes": evidence["bytes"],
            "compatibility_overlay": {
                "applied_count": evidence[
                    "compatibility_overlay_count"
                ],
                "id": "nintendo-unused-var-tp-v1",
            },
            "eval_error_count": 0,
            "files": evidence["files"],
            "realm_mode": "isolated",
            "rules_commit": self.reference["rules_commit"],
            "schema_version": 1,
            "selection": "recursive files with .sg or no extension",
            "tracking_allocator": {
                "accounting": evidence["tracking_accounting"],
                "backend": (
                    "rquickjs RustAllocator wrapped by "
                    "TrackingLimitAllocator"
                ),
                "denied_allocation_count": evidence[
                    "denied_allocation_count"
                ],
                "high_water_bytes": evidence["high_water_bytes"],
                "limit_bytes": evidence["limit_bytes"],
                "live_bytes_after_drop": 0,
                "live_bytes_before_drop": evidence[
                    "live_bytes_before_drop"
                ],
                "set_memory_limit_used": evidence[
                    "set_memory_limit_used"
                ],
            },
            "upstream_commit": self.reference["upstream_commit"],
        }
        canonical = json.dumps(
            projection,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        self.assertEqual(
            hashlib.sha256(canonical).hexdigest(),
            evidence["stable_projection_sha256"],
        )
        self.assertIn("detect functions are not called", evidence["scope"])
        self.assertIn("not default-allocator", evidence["scope"])
        self.assertIn("cross-platform evidence", evidence["scope"])

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
