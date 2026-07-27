import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
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
