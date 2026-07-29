import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = (
    ROOT / "tools" / "benchmark" / "run_process_benchmark.py"
)
SPEC = importlib.util.spec_from_file_location(
    "run_process_benchmark",
    SCRIPT_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ProcessBenchmarkRunnerTest(unittest.TestCase):
    def plan(self, command=None):
        artifact = ROOT / "README.md"
        return {
            "benchmark_plan_schema": 1,
            "benchmark_id": "synthetic.process.v1",
            "command": command
            or [
                sys.executable,
                "-c",
                (
                    "import time; "
                    "print('deterministic benchmark output'); "
                    "time.sleep(0.03)"
                ),
            ],
            "working_directory": "docs",
            "environment": {"PYTHONHASHSEED": "0"},
            "inherit_environment": True,
            "producer": {
                "implementation": "synthetic-test",
                "source_commit": (
                    "74eaf505c250ab47e709024e9dc41657cd8f2254"
                ),
                "rules_commit": (
                    "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
                ),
                "build_profile": "test",
                "toolchain": f"python {sys.version_info.major}.{sys.version_info.minor}",
            },
            "input_artifacts": [
                {
                    "path": "README.md",
                    "bytes": artifact.stat().st_size,
                    "sha256": hashlib.sha256(
                        artifact.read_bytes()
                    ).hexdigest(),
                }
            ],
            "cache_state": "warm",
            "warmup_runs": 1,
            "measured_runs": 3,
            "timeout_ms": 2000,
            "max_stdout_bytes": 4096,
            "max_stderr_bytes": 4096,
            "work_bytes": artifact.stat().st_size,
            "work_definition": "README.md bytes processed once",
            "require_deterministic_output": True,
            "require_peak_rss": True,
            "notes": ["synthetic runner contract test; not a product baseline"],
        }

    def controlled_plan(self):
        plan = self.plan()
        plan["benchmark_plan_schema"] = 2
        plan["cache_state"] = MODULE.FILE_CONTENT
        plan["warmup_runs"] = 0
        plan["measured_runs"] = 1
        plan["timeout_ms"] = 120_000
        plan["cache_controller"] = {
            "kind": MODULE.FILE_CONTENT_CONTROLLER_KIND,
            "binary": {
                "path": "/io/file-content-measure",
                "bytes": 804_240,
                "sha256": "1" * 64,
            },
            "manifest": {
                "path": "/io/candidates.manifest",
                "bytes": 128,
                "sha256": "2" * 64,
            },
            "page_size": 4096,
            "file_count": 2,
            "logical_pages": 3,
            "working_directory": "/bench",
        }
        return plan

    def test_benchmark_binds_identity_and_reports_required_statistics(self):
        plan = self.plan()
        report = MODULE.run_benchmark(plan, ROOT)
        self.assertEqual(report["benchmark_report_schema"], 1)
        self.assertEqual(report["result"], "pass")
        self.assertEqual(report["benchmark_id"], "synthetic.process.v1")
        self.assertEqual(report["runner"], MODULE.RUNNER)
        self.assertEqual(report["producer"], plan["producer"])
        self.assertEqual(report["execution"]["warmup_runs"], 1)
        self.assertEqual(report["execution"]["measured_runs"], 3)
        self.assertEqual(len(report["runs"]), 3)
        self.assertEqual(
            report["executable"]["sha256"],
            MODULE.sha256_file(Path(sys.executable)),
        )
        self.assertEqual(report["input_artifacts"], plan["input_artifacts"])
        summary = report["summary"]
        self.assertEqual(summary["sample_count"], 3)
        durations = summary["duration_ns"]
        self.assertLessEqual(durations["min"], durations["median"])
        self.assertLessEqual(
            durations["median"],
            durations["p95_nearest_rank"],
        )
        self.assertLessEqual(
            durations["p95_nearest_rank"],
            durations["max"],
        )
        self.assertGreaterEqual(durations["mad"], 0)
        self.assertGreater(
            summary["throughput_bytes_per_second_at_median"],
            0,
        )
        self.assertEqual(summary["peak_rss_bytes"]["sample_count"], 3)
        self.assertGreater(summary["peak_rss_bytes"]["max"], 0)
        self.assertEqual(len(summary["stdout_unique_sha256"]), 1)
        self.assertEqual(len(summary["stderr_unique_sha256"]), 1)
        self.assertEqual(len(report["limitations"]), 5)
        self.assertNotIn("PYTHONHASHSEED", json.dumps(report["host"]))

    def test_run_once_retries_rss_synchronously_before_monitor_thread(self):
        original = MODULE.sample_rss_bytes
        calls = []

        def second_main_thread_sample_only(pid):
            del pid
            is_main = threading.current_thread() is threading.main_thread()
            calls.append(is_main)
            if len(calls) == 2 and is_main:
                return 4096
            return None

        MODULE.sample_rss_bytes = second_main_thread_sample_only
        try:
            result = MODULE.run_once(
                command=[
                    sys.executable,
                    "-c",
                    "import time; time.sleep(0.03)",
                ],
                cwd=ROOT,
                environment=dict(os.environ),
                timeout_ms=2000,
                max_stdout_bytes=0,
                max_stderr_bytes=0,
            )
        finally:
            MODULE.sample_rss_bytes = original

        self.assertGreaterEqual(len(calls), 2)
        self.assertEqual(calls[:2], [True, True])
        self.assertEqual(result["peak_rss_bytes"], 4096)

    def test_plan_rejects_unknown_fields_cold_cache_and_too_few_runs(self):
        root_plan = self.plan()
        root_plan["working_directory"] = "."
        self.assertEqual(
            MODULE.validate_plan(root_plan)["working_directory"],
            ".",
        )

        plan = self.plan()
        plan["unexpected"] = True
        with self.assertRaisesRegex(MODULE.BenchmarkError, "unknown fields"):
            MODULE.validate_plan(plan)
        plan = self.plan()
        plan["benchmark_plan_schema"] = True
        with self.assertRaisesRegex(
            MODULE.BenchmarkError,
            "unsupported benchmark_plan_schema",
        ):
            MODULE.validate_plan(plan)
        plan = self.plan()
        plan["cache_state"] = "cold"
        with self.assertRaisesRegex(
            MODULE.BenchmarkError,
            "only explicit warm",
        ):
            MODULE.validate_plan(plan)
        plan = self.plan()
        plan["measured_runs"] = 2
        with self.assertRaisesRegex(MODULE.BenchmarkError, "3..100"):
            MODULE.validate_plan(plan)

    def test_schema_v2_requires_exact_controller_and_rejects_cold(self):
        plan = self.controlled_plan()
        validated = MODULE.validate_plan(plan)
        self.assertEqual(validated, plan)
        self.assertEqual(validated["measured_runs"], 1)

        missing = self.controlled_plan()
        del missing["cache_controller"]
        with self.assertRaisesRegex(
            MODULE.BenchmarkError,
            "requires plan.cache_controller",
        ):
            MODULE.validate_plan(missing)
        cold = self.controlled_plan()
        cold["cache_state"] = "cold"
        with self.assertRaisesRegex(
            MODULE.BenchmarkError,
            "schema v2 cache_state",
        ):
            MODULE.validate_plan(cold)
        timeout = self.controlled_plan()
        timeout["timeout_ms"] = 10_000
        with self.assertRaisesRegex(
            MODULE.BenchmarkError,
            "requires timeout_ms=120000",
        ):
            MODULE.validate_plan(timeout)
        warmup = self.controlled_plan()
        warmup["warmup_runs"] = 1
        with self.assertRaisesRegex(
            MODULE.BenchmarkError,
            "pairing belongs to the suite",
        ):
            MODULE.validate_plan(warmup)
        unknown = self.controlled_plan()
        unknown["cache_controller"]["authority"] = "privileged"
        with self.assertRaisesRegex(
            MODULE.BenchmarkError,
            "unknown fields",
        ):
            MODULE.validate_plan(unknown)

    def test_controller_measurement_parser_is_exact_and_fail_closed(self):
        plan = MODULE.validate_plan(self.controlled_plan())
        controller = plan["cache_controller"]
        valid = (
            b"schema_version\t1\n"
            b"cache_state\tfile-content-nonresident-metadata-warm\n"
            b"fadvise_executed\t1\n"
            b"page_size\t4096\n"
            b"file_count\t2\n"
            b"logical_pages\t3\n"
            b"resident_pages_after_warm\t3\n"
            b"resident_pages_before_run\t0\n"
            b"before_run_page_state_verified\t1\n"
            b"duration_ns\t100\n"
            b"peak_rss_bytes\t4096\n"
            b"exit_code\t0\n"
            b"timed_out\t0\n"
        )
        parsed = MODULE.parse_controller_measurement(
            valid,
            MODULE.FILE_CONTENT,
            controller,
        )
        self.assertEqual(parsed["duration_ns"], 100)
        evidence = parsed["cache_controller_evidence"]
        self.assertTrue(evidence["fadvise_executed"])
        self.assertEqual(evidence["resident_pages_before_run"], 0)
        with self.assertRaisesRegex(
            MODULE.BenchmarkError,
            "duplicate cache controller field",
        ):
            MODULE.parse_controller_measurement(
                valid + b"duration_ns\t101\n",
                MODULE.FILE_CONTENT,
                controller,
            )
        with self.assertRaisesRegex(
            MODULE.BenchmarkError,
            "measurement invariant failed",
        ):
            MODULE.parse_controller_measurement(
                valid.replace(
                    b"resident_pages_before_run\t0",
                    b"resident_pages_before_run\t1",
                ),
                MODULE.FILE_CONTENT,
                controller,
            )

    def test_schema_v2_rejects_in_process_execution(self):
        plan = self.controlled_plan()
        with self.assertRaisesRegex(
            MODULE.BenchmarkError,
            "preflight/exec/finalize",
        ):
            MODULE.run_benchmark(plan, ROOT)

    def test_duplicate_json_keys_and_non_finite_values_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            path.write_text(
                '{"benchmark_plan_schema":1,"benchmark_plan_schema":1}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                MODULE.BenchmarkError,
                "duplicate JSON key",
            ):
                MODULE.load_json(path)
            path.write_text('{"value":NaN}', encoding="utf-8")
            with self.assertRaisesRegex(
                MODULE.BenchmarkError,
                "non-finite",
            ):
                MODULE.load_json(path)

    def test_input_identity_output_limit_and_timeout_fail_explicitly(self):
        plan = self.plan()
        plan["input_artifacts"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(MODULE.BenchmarkError, "SHA-256 mismatch"):
            MODULE.run_benchmark(plan, ROOT)

        plan = self.plan(
            [sys.executable, "-c", "print('output exceeds cap')"]
        )
        plan["warmup_runs"] = 0
        plan["max_stdout_bytes"] = 1
        plan["require_peak_rss"] = False
        with self.assertRaisesRegex(MODULE.BenchmarkError, "stdout exceeded"):
            MODULE.run_benchmark(plan, ROOT)

        plan = self.plan(
            [sys.executable, "-c", "import time; time.sleep(0.2)"]
        )
        plan["warmup_runs"] = 0
        plan["timeout_ms"] = 20
        plan["require_peak_rss"] = False
        with self.assertRaisesRegex(MODULE.BenchmarkError, "timed out"):
            MODULE.run_benchmark(plan, ROOT)

    def test_cli_writes_report_without_copying_environment_values(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            plan_path = temp / "plan.json"
            output_path = temp / "report.json"
            plan = self.plan()
            plan["warmup_runs"] = 0
            plan_path.write_text(
                json.dumps(plan),
                encoding="utf-8",
            )
            exit_code = MODULE.main(
                [
                    "--plan",
                    str(plan_path),
                    "--output",
                    str(output_path),
                    "--repo-root",
                    str(ROOT),
                ]
            )
            self.assertEqual(exit_code, 0)
            report = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(report["result"], "pass")
            self.assertEqual(
                report["execution"]["environment_override_keys"],
                ["PYTHONHASHSEED"],
            )
            self.assertNotIn(
                "PYTHONHASHSEED",
                json.dumps(report["host"]),
            )


if __name__ == "__main__":
    unittest.main()
