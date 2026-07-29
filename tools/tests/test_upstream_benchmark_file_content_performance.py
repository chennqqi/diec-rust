import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
PROBE_PATH = (
    ROOT
    / "tools/benchmark/"
    "probe_upstream_benchmark_file_content_performance.py"
)
RUNNER_PATH = (
    ROOT / "tools/benchmark/run_process_benchmark.py"
)
MEASUREMENT_PATH = (
    ROOT / "tools/benchmark/measure_linux_file_content_benchmark.c"
)
PAGE_CONTROLLER_PATH = (
    ROOT / "tools/benchmark/control_linux_page_cache.c"
)
REPORT_PATH = (
    ROOT
    / "docs/research/data/"
    "upstream-benchmark-linux-qt5-file-content-performance.json"
)
DOCUMENT_PATH = (
    ROOT
    / "docs/research/"
    "upstream-benchmark-file-content-performance.md"
)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


PROBE = load_module(
    "probe_upstream_benchmark_file_content_performance_test",
    PROBE_PATH,
)
RUNNER = load_module(
    "run_process_benchmark_file_content_performance_test",
    RUNNER_PATH,
)


class UpstreamBenchmarkFileContentPerformanceTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls):
        cls.report_raw = REPORT_PATH.read_bytes()
        cls.report = json.loads(cls.report_raw)

    def test_report_binds_generator_controller_and_inputs(self):
        report = self.report
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(
            report["upstream_commit"],
            PROBE.EXPECTED_REVISION,
        )
        self.assertEqual(
            report["generator_sha256"],
            hashlib.sha256(PROBE_PATH.read_bytes()).hexdigest(),
        )
        expected_inputs = {
            "plan_suite": PROBE.EXPECTED_PLAN_SHA256,
            "affinity_baseline": PROBE.EXPECTED_AFFINITY_SHA256,
            "successful_file_access": PROBE.EXPECTED_ACCESS_SHA256,
            "page_cache": PROBE.EXPECTED_PAGE_CACHE_SHA256,
            "cache_environment": (
                PROBE.EXPECTED_CACHE_ENVIRONMENT_SHA256
            ),
        }
        for name, digest in expected_inputs.items():
            artifact = report["inputs"][name]
            self.assertEqual(artifact["sha256"], digest)
            self.assertEqual(
                hashlib.sha256(
                    (ROOT / artifact["path"]).read_bytes()
                ).hexdigest(),
                digest,
            )

        controller = report["controller"]
        self.assertEqual(
            controller["measurement_source_sha256"],
            hashlib.sha256(
                MEASUREMENT_PATH.read_bytes()
            ).hexdigest(),
        )
        self.assertEqual(
            controller["page_controller_source_sha256"],
            hashlib.sha256(
                PAGE_CONTROLLER_PATH.read_bytes()
            ).hexdigest(),
        )
        self.assertEqual(controller["binary_bytes"], 804_184)
        self.assertEqual(
            controller["binary_sha256"],
            (
                "2a0c02d469a7f6829c04fc356cd33e9a"
                "8ac67b21adf22213a5d9596da2550a31"
            ),
        )
        self.assertTrue(controller["statically_linked"])
        self.assertFalse(controller["pt_interp_present"])
        self.assertFalse(controller["pt_dynamic_present"])
        self.assertEqual(
            controller["clock"],
            "clock_gettime(CLOCK_MONOTONIC)",
        )
        self.assertEqual(
            controller["peak_rss_method"],
            "wait4 child rusage.ru_maxrss * 1024",
        )
        runner = report["runner_integration"]
        self.assertEqual(runner["runner"], RUNNER.RUNNER)
        self.assertEqual(runner["plan_schema"], 2)
        self.assertEqual(runner["report_schema"], 2)
        self.assertEqual(
            runner["controller_kind"],
            RUNNER.FILE_CONTENT_CONTROLLER_KIND,
        )
        self.assertEqual(
            runner["source_sha256"],
            hashlib.sha256(RUNNER_PATH.read_bytes()).hexdigest(),
        )

    def test_case_medians_and_pair_counts_are_exact(self):
        expected = {
            "upstream.archive-depth16.v1": (
                160_986_221,
                1_104_170_445,
                6_589_210,
                944_330_166,
            ),
            "upstream.cli-baseline-batch-json.v1": (
                3_041_579_296,
                4_171_030_428,
                1_333_355,
                1_063_505_759,
            ),
            "upstream.cli-pe32-json.v1": (
                253_032_207,
                999_513_549,
                4_114_096,
                753_470_668,
            ),
            "upstream.database-load.v1": (
                97_396_370,
                933_205_003,
                8_760_115,
                813_255_314,
            ),
            "upstream.qt-process-control.v1": (
                12_034_763,
                66_311_523,
                5_683_948,
                53_524_125,
            ),
        }
        self.assertEqual(set(self.report["cases"]), set(expected))
        for benchmark_id, values in expected.items():
            case = self.report["cases"][benchmark_id]
            warm, file_content, ratio, delta = values
            summaries = case["state_summaries"]
            self.assertEqual(case["pair_count"], 10)
            self.assertEqual(case["sample_count"], 20)
            self.assertEqual(
                summaries[PROBE.WARM]["duration_ns"]["median"],
                warm,
            )
            self.assertEqual(
                summaries[PROBE.FILE_CONTENT]["duration_ns"][
                    "median"
                ],
                file_content,
            )
            self.assertEqual(
                case["paired_effect"][
                    "duration_ratio_file_over_warm_scaled_1e6"
                ]["median"],
                ratio,
            )
            self.assertEqual(
                case["paired_effect"]["duration_delta_ns"][
                    "median"
                ],
                delta,
            )
            self.assertEqual(
                case["paired_effect"]["negative_delta_pair_count"],
                0,
            )

    def test_every_pair_has_abba_order_and_verified_page_state(self):
        total = 0
        for case in self.report["cases"].values():
            logical_pages = case["manifest"]["logical_pages"]
            file_count = case["manifest"]["file_count"]
            for pair_index, pair in enumerate(case["pairs"]):
                expected_order = (
                    [PROBE.WARM, PROBE.FILE_CONTENT]
                    if pair_index % 2 == 0
                    else [PROBE.FILE_CONTENT, PROBE.WARM]
                )
                self.assertEqual(pair["pair_index"], pair_index)
                self.assertEqual(pair["order"], expected_order)
                warm = pair[PROBE.WARM]
                file_content = pair[PROBE.FILE_CONTENT]
                for run in (warm, file_content):
                    evidence = run["controller_evidence"]
                    self.assertTrue(
                        evidence["before_run_page_state_verified"]
                    )
                    self.assertEqual(
                        evidence["file_count"],
                        file_count,
                    )
                    self.assertEqual(
                        evidence["logical_pages"],
                        logical_pages,
                    )
                    self.assertEqual(
                        evidence["resident_pages_after_warm"],
                        logical_pages,
                    )
                    self.assertEqual(run["exit_code"], 0)
                self.assertFalse(
                    warm["controller_evidence"]["fadvise_executed"]
                )
                self.assertEqual(
                    warm["controller_evidence"][
                        "resident_pages_before_run"
                    ],
                    logical_pages,
                )
                self.assertTrue(
                    file_content["controller_evidence"][
                        "fadvise_executed"
                    ]
                )
                self.assertEqual(
                    file_content["controller_evidence"][
                        "resident_pages_before_run"
                    ],
                    0,
                )
                self.assertEqual(warm["stdout"], file_content["stdout"])
                self.assertEqual(warm["stderr"], file_content["stderr"])
                for run in (warm, file_content):
                    runner = run["runner_evidence"]
                    self.assertEqual(
                        runner["benchmark_report_schema"],
                        2,
                    )
                    self.assertEqual(
                        runner["runner"],
                        RUNNER.RUNNER,
                    )
                    self.assertEqual(
                        runner["runner_source_sha256"],
                        hashlib.sha256(
                            RUNNER_PATH.read_bytes()
                        ).hexdigest(),
                    )
                    self.assertEqual(
                        runner["controller_kind"],
                        RUNNER.FILE_CONTENT_CONTROLLER_KIND,
                    )
                    self.assertEqual(
                        runner["measurement"]["clock"],
                        "clock_gettime(CLOCK_MONOTONIC)",
                    )
                total += 2
        self.assertEqual(total, 100)
        self.assertEqual(
            self.report["total_measured_processes"],
            total,
        )

    def test_report_summaries_recompute_from_raw_pairs(self):
        for case in self.report["cases"].values():
            deltas = [
                pair["duration_delta_ns"]
                for pair in case["pairs"]
            ]
            ratios = [
                round(
                    pair[
                        "duration_ratio_file_over_warm"
                    ]
                    * 1_000_000
                )
                for pair in case["pairs"]
            ]
            self.assertEqual(
                PROBE.summarize_values(deltas),
                case["paired_effect"]["duration_delta_ns"],
            )
            self.assertEqual(
                PROBE.summarize_values(ratios),
                case["paired_effect"][
                    "duration_ratio_file_over_warm_scaled_1e6"
                ],
            )
            for state in (PROBE.WARM, PROBE.FILE_CONTENT):
                durations = [
                    pair[state]["duration_ns"]
                    for pair in case["pairs"]
                ]
                self.assertEqual(
                    PROBE.summarize_values(durations),
                    case["state_summaries"][state]["duration_ns"],
                )

    def test_scope_keeps_system_cold_rust_and_thresholds_false(self):
        self.assertTrue(all(self.report["relationships"].values()))
        scope = self.report["scope"]
        for field in (
            "descriptive_upstream_cache_state_spike",
            "direct_child_process_only",
            "runner_plan_integration_present",
            "same_launcher_clock_and_rss_method_across_states",
        ):
            self.assertTrue(scope[field])
        for field in (
            "long_horizon_sessions_present",
            "metadata_cache_controlled",
            "physical_core_topology_proven",
            "regression_thresholds_frozen",
            "rust_paired_measurements_present",
            "system_cold_cache_controlled",
        ):
            self.assertFalse(scope[field])

    def test_measurement_and_elf_parsers_fail_closed(self):
        valid = (
            b"schema_version\t1\n"
            b"cache_state\twarm\n"
            b"fadvise_executed\t0\n"
            b"page_size\t4096\n"
            b"file_count\t2\n"
            b"logical_pages\t3\n"
            b"resident_pages_after_warm\t3\n"
            b"resident_pages_before_run\t3\n"
            b"before_run_page_state_verified\t1\n"
            b"duration_ns\t100\n"
            b"peak_rss_bytes\t4096\n"
            b"exit_code\t0\n"
            b"timed_out\t0\n"
        )
        controller = {
            "kind": RUNNER.FILE_CONTENT_CONTROLLER_KIND,
            "page_size": 4096,
            "file_count": 2,
            "logical_pages": 3,
        }
        parsed = RUNNER.parse_controller_measurement(
            valid,
            RUNNER.WARM,
            controller,
        )
        self.assertEqual(parsed["duration_ns"], 100)
        with self.assertRaisesRegex(
            RUNNER.BenchmarkError,
            "duplicate cache controller field",
        ):
            RUNNER.parse_controller_measurement(
                valid + b"duration_ns\t101\n",
                RUNNER.WARM,
                controller,
            )
        with self.assertRaisesRegex(
            RUNNER.BenchmarkError,
            "measurement invariant failed",
        ):
            RUNNER.parse_controller_measurement(
                valid.replace(
                    b"resident_pages_before_run\t3",
                    b"resident_pages_before_run\t0",
                ),
                RUNNER.WARM,
                controller,
            )

        elf = bytearray(120)
        elf[:6] = b"\x7fELF\x02\x01"
        struct.pack_into("<H", elf, 18, 62)
        struct.pack_into("<Q", elf, 32, 64)
        struct.pack_into("<H", elf, 54, 56)
        struct.pack_into("<H", elf, 56, 1)
        struct.pack_into("<I", elf, 64, 1)
        self.assertTrue(
            PROBE.validate_static_elf(bytes(elf))[
                "statically_linked"
            ]
        )
        struct.pack_into("<I", elf, 64, 3)
        with self.assertRaisesRegex(
            PROBE.FileContentPerformanceError,
            "PT_DYNAMIC or PT_INTERP",
        ):
            PROBE.validate_static_elf(bytes(elf))

    def test_sources_and_document_preserve_boundaries(self):
        source = MEASUREMENT_PATH.read_text(encoding="utf-8")
        page_source = PAGE_CONTROLLER_PATH.read_text(encoding="utf-8")
        for text in (
            "CLOCK_MONOTONIC",
            "wait4(",
            "RLIMIT_FSIZE",
            "SIGKILL",
            "file-content-nonresident-metadata-warm",
            "--finalizer-python",
            "--preflight",
        ):
            self.assertIn(text, source)
        for text in ("POSIX_FADV_DONTNEED", "mincore("):
            self.assertIn(text, page_source)
        self.assertNotIn("system(", source + page_source)
        runner_source = RUNNER_PATH.read_text(encoding="utf-8")
        for text in (
            "os.execve(",
            "exec_controlled_benchmark",
            "finalize_controlled_benchmark",
            "preflight/exec/finalize",
        ):
            self.assertIn(text, runner_source)

        document = DOCUMENT_PATH.read_text(encoding="utf-8")
        for text in (
            "100",
            "ABBA",
            "8.760115",
            "plan schema v2",
            "system-cold",
            "regression_thresholds_frozen=false",
            "rust_paired_measurements_present=false",
        ):
            self.assertIn(text, document)
        self.assertIn(
            hashlib.sha256(self.report_raw).hexdigest(),
            document,
        )
        for local in (
            b"I:\\\\",
            b"C:\\\\",
            b"Users\\\\worker",
            b"github.com\\\\chennqqi",
        ):
            self.assertNotIn(local, self.report_raw)


if __name__ == "__main__":
    unittest.main()
