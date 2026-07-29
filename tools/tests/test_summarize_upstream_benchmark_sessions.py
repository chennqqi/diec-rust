import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
TOOL_PATH = (
    ROOT
    / "tools"
    / "benchmark"
    / "summarize_upstream_benchmark_sessions.py"
)
REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "upstream-benchmark-linux-qt5-affinity-repeated.json"
)
SESSION_PATHS = [
    (
        ROOT
        / "docs"
        / "research"
        / "data"
        / "upstream-benchmark-linux-qt5-affinity.json"
    ),
    (
        ROOT
        / "docs"
        / "research"
        / "data"
        / "upstream-benchmark-linux-qt5-affinity-session-2.json"
    ),
    (
        ROOT
        / "docs"
        / "research"
        / "data"
        / "upstream-benchmark-linux-qt5-affinity-session-3.json"
    ),
]
DOCUMENT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "upstream-performance-repeated-sessions.md"
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODULE = load_module(
    "summarize_upstream_benchmark_sessions_for_test",
    TOOL_PATH,
)


class RepeatedBenchmarkSessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report_raw = REPORT_PATH.read_bytes()
        cls.report = json.loads(cls.report_raw)

    def test_report_rebuilds_exactly_from_three_raw_sessions(self):
        rebuilt = MODULE.build_report(ROOT, SESSION_PATHS)
        self.assertEqual(rebuilt, self.report)
        self.assertEqual(
            self.report["generator_sha256"],
            hashlib.sha256(TOOL_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(self.report["session_count"], 3)
        self.assertEqual(self.report["total_warmup_runs"], 51)
        self.assertEqual(self.report["total_measured_runs"], 270)
        self.assertFalse(self.report["targets_frozen"])
        self.assertTrue(all(self.report["relationships"].values()))

    def test_source_reports_are_exact_and_distinct(self):
        expected_hashes = [
            (
                "67e6d594a5b93e1b791c11ef89bdb12e"
                "85399964cea9bee87baf591047f5d7de"
            ),
            (
                "3329d85989efec599b8621013f644aa3"
                "933ecacf86bdd3fb737c831010f5f011"
            ),
            (
                "c6c171899b7366e3858f2ac039ed9346"
                "b48b9ba154ef4beee3607dcb4b376128"
            ),
        ]
        sources = self.report["source_reports"]
        self.assertEqual(
            [source["sha256"] for source in sources],
            expected_hashes,
        )
        for source, path in zip(
            sources,
            SESSION_PATHS,
            strict=True,
        ):
            self.assertEqual(
                source["sha256"],
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )
            self.assertEqual(source["bytes"], path.stat().st_size)

    def test_case_sets_outputs_and_rss_boundaries_are_preserved(self):
        cases = self.report["cases"]
        self.assertEqual(
            set(cases),
            {
                "upstream.archive-depth16.v1",
                "upstream.cli-baseline-batch-json.v1",
                "upstream.cli-pe32-json.v1",
                "upstream.database-load.v1",
                "upstream.qt-process-control.v1",
            },
        )
        for benchmark_id, case in cases.items():
            with self.subTest(benchmark=benchmark_id):
                self.assertTrue(
                    case[
                        "stdout_hashes_identical_across_sessions"
                    ]
                )
                self.assertTrue(
                    case[
                        "stderr_hashes_identical_across_sessions"
                    ]
                )
                self.assertEqual(
                    len(case["session_duration_median_ns"]),
                    3,
                )
        self.assertEqual(
            cases["upstream.qt-process-control.v1"][
                "session_peak_rss_sample_count"
            ],
            [9, 12, 12],
        )
        for benchmark_id, case in cases.items():
            if benchmark_id != "upstream.qt-process-control.v1":
                self.assertEqual(
                    case["session_peak_rss_sample_count"],
                    [15, 15, 15],
                )

    def test_cross_session_drift_is_exact_and_not_a_threshold(self):
        cases = self.report["cases"]
        self.assertEqual(
            cases["upstream.archive-depth16.v1"][
                "session_duration_median_ns"
            ],
            [120_414_988, 68_040_262, 68_017_412],
        )
        self.assertEqual(
            cases["upstream.cli-pe32-json.v1"][
                "session_duration_median_ns"
            ],
            [167_140_608, 119_921_145, 119_900_932],
        )
        self.assertGreater(
            cases["upstream.archive-depth16.v1"][
                "duration_median_max_over_min"
            ],
            1.77,
        )
        self.assertGreater(
            cases["upstream.cli-baseline-batch-json.v1"][
                "duration_p95_max_over_min"
            ],
            1.68,
        )
        scope = self.report["scope"]
        for field in (
            "physical_core_topology_proven",
            "cold_cache_controlled",
            "power_and_frequency_controlled",
            "long_horizon_variability_measured",
            "regression_thresholds_approved",
        ):
            self.assertFalse(scope[field])

    def test_fail_closed_for_duplicate_outside_and_duplicate_json(self):
        with self.assertRaisesRegex(
            MODULE.SummaryError,
            "unique hashes",
        ):
            MODULE.build_report(
                ROOT,
                [SESSION_PATHS[0], SESSION_PATHS[0], SESSION_PATHS[0]],
            )
        with tempfile.TemporaryDirectory() as directory:
            outside = Path(directory) / "session.json"
            outside.write_bytes(SESSION_PATHS[0].read_bytes())
            with self.assertRaisesRegex(
                MODULE.SummaryError,
                "outside repository",
            ):
                MODULE.build_report(
                    ROOT,
                    [SESSION_PATHS[0], SESSION_PATHS[1], outside],
                )
        with self.assertRaisesRegex(
            MODULE.SummaryError,
            "duplicate JSON key",
        ):
            MODULE.parse_json(b'{"a":1,"a":2}', "fixture")

    def test_document_preserves_exact_results_and_boundaries(self):
        document = DOCUMENT_PATH.read_text(encoding="utf-8")
        for text in (
            "51 warmup",
            "270 measured",
            "1.7704",
            "1.3940",
            "1.6848",
            "`targets_frozen=false`",
            "cold_cache_controlled=false",
            "不是物理核心",
        ):
            self.assertIn(text, document)
        self.assertIn(
            hashlib.sha256(self.report_raw).hexdigest(),
            document,
        )


if __name__ == "__main__":
    unittest.main()
