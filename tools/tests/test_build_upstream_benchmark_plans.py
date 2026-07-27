import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
BUILDER_PATH = (
    ROOT / "tools" / "benchmark" / "build_upstream_benchmark_plans.py"
)
RUNNER_PATH = (
    ROOT / "tools" / "benchmark" / "run_process_benchmark.py"
)
OUTPUT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "upstream-benchmark-plans.json"
)
BASELINE_PATH = (
    ROOT / "docs" / "research" / "data" / "baseline-corpus.json"
)
ARCHIVE_PATH = (
    ROOT / "docs" / "research" / "data" / "archive-limit-corpus.json"
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BUILDER = load_module("build_upstream_benchmark_plans", BUILDER_PATH)
RUNNER = load_module("benchmark_runner_for_plan_test", RUNNER_PATH)


class BuildUpstreamBenchmarkPlansTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.baseline, cls.baseline_raw = BUILDER.load_manifest(
            BASELINE_PATH
        )
        cls.archive, cls.archive_raw = BUILDER.load_manifest(
            ARCHIVE_PATH
        )
        cls.expected = BUILDER.build_plans(
            cls.baseline,
            cls.baseline_raw,
            cls.archive,
            cls.archive_raw,
        )
        cls.committed = json.loads(
            OUTPUT_PATH.read_text(encoding="utf-8")
        )

    def test_committed_plans_are_exact_generator_output(self):
        self.assertEqual(self.committed, self.expected)
        self.assertEqual(
            OUTPUT_PATH.read_bytes(),
            BUILDER.serialize(self.expected),
        )

    def test_case_set_and_runner_schema_are_exact(self):
        plans = self.committed["plans"]
        self.assertEqual(
            [plan["benchmark_id"] for plan in plans],
            [
                "upstream.qt-process-control.v1",
                "upstream.database-load.v1",
                "upstream.cli-pe32-json.v1",
                "upstream.cli-baseline-batch-json.v1",
                "upstream.archive-depth16.v1",
            ],
        )
        for plan in plans:
            with self.subTest(plan=plan["benchmark_id"]):
                self.assertEqual(RUNNER.validate_plan(plan), plan)
                self.assertTrue(plan["require_deterministic_output"])
                self.assertTrue(plan["require_peak_rss"])
                self.assertEqual(plan["cache_state"], "warm")
        self.assertEqual(
            sum(plan["warmup_runs"] for plan in plans),
            17,
        )
        self.assertEqual(
            sum(plan["measured_runs"] for plan in plans),
            90,
        )

    def test_batch_artifacts_cover_exact_generated_directory(self):
        plan = next(
            plan
            for plan in self.committed["plans"]
            if plan["benchmark_id"]
            == "upstream.cli-baseline-batch-json.v1"
        )
        expected_paths = {
            f"baseline/{sample['name']}"
            for sample in self.baseline["samples"]
        } | {"baseline/manifest.json"}
        self.assertEqual(
            {artifact["path"] for artifact in plan["input_artifacts"]},
            expected_paths,
        )
        self.assertEqual(
            plan["work_bytes"],
            sum(
                artifact["bytes"]
                for artifact in plan["input_artifacts"]
            ),
        )

    def test_depth_work_uses_cumulative_expanded_bytes(self):
        depth_sample = next(
            sample
            for sample in self.archive["samples"]
            if sample["name"] == "depth-16.zip"
        )
        plan = next(
            plan
            for plan in self.committed["plans"]
            if plan["benchmark_id"]
            == "upstream.archive-depth16.v1"
        )
        self.assertEqual(
            plan["work_bytes"],
            depth_sample["cumulative_expanded_bytes"],
        )


if __name__ == "__main__":
    unittest.main()
