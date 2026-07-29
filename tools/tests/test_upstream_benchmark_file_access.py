import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
PROBE_PATH = (
    ROOT
    / "tools"
    / "benchmark"
    / "probe_upstream_benchmark_file_access.py"
)
TRACER_PATH = (
    ROOT
    / "tools"
    / "benchmark"
    / "trace_linux_file_access.py"
)
REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "upstream-benchmark-linux-qt5-file-access.json"
)
DOCUMENT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "upstream-benchmark-file-access.md"
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


PROBE = load_module(
    "probe_upstream_benchmark_file_access_for_test",
    PROBE_PATH,
)
TRACER = load_module(
    "trace_linux_file_access_for_test",
    TRACER_PATH,
)


class UpstreamBenchmarkFileAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report_raw = REPORT_PATH.read_bytes()
        cls.report = json.loads(cls.report_raw)

    def test_report_binds_exact_generators_and_environment(self):
        report = self.report
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(
            report["generator_sha256"],
            hashlib.sha256(PROBE_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            report["tracer"]["sha256"],
            hashlib.sha256(TRACER_PATH.read_bytes()).hexdigest(),
        )
        environment = report["environment"]
        self.assertEqual(
            environment["image_identity"]["id"],
            PROBE.EXPECTED_IMAGE_ID,
        )
        self.assertEqual(
            environment["cgroup"]["cpuset_effective"],
            "0",
        )
        self.assertEqual(
            report["plan_suite"]["sha256"],
            PROBE.EXPECTED_PLAN_SHA256,
        )
        self.assertEqual(report["trace_repetitions_per_case"], 2)
        self.assertTrue(all(report["relationships"].values()))

    def test_case_closures_are_exact_and_repeat_identically(self):
        expected = {
            "upstream.archive-depth16.v1": (
                2254,
                65_263_871,
                (
                    "4fca0bb3fb4ae4ca11c91471ca0fc6b6"
                    "61f0b1207c027b8879a175d6e220150c"
                ),
            ),
            "upstream.cli-baseline-batch-json.v1": (
                2281,
                65_319_431,
                (
                    "f665d589922f583701086ad32746b58e"
                    "8a3f526bbb8456cb71ff01781ed05ece"
                ),
            ),
            "upstream.cli-pe32-json.v1": (
                2255,
                65_271_878,
                (
                    "f477a3df05173f4b6317f38895045542"
                    "f9bcfa0e8bf80d5329fd3d1b1d6d3389"
                ),
            ),
            "upstream.database-load.v1": (
                2253,
                65_261_596,
                (
                    "ee4ddca31895f7e63b704301ab427cd1"
                    "b49136099ec981715b607801f7c230a6"
                ),
            ),
            "upstream.qt-process-control.v1": (
                18,
                62_358_715,
                (
                    "e9a17c43d2be07ef371d7eadcea86b93"
                    "8dae3a39e9c60846810a8e15a5f660ef"
                ),
            ),
        }
        self.assertEqual(set(self.report["cases"]), set(expected))
        for benchmark_id, (count, size, digest) in expected.items():
            case = self.report["cases"][benchmark_id]
            self.assertEqual(
                case["successful_regular_file_count"],
                count,
            )
            self.assertEqual(
                case["successful_regular_file_bytes"],
                size,
            )
            self.assertEqual(case["records_sha256"], digest)
            self.assertTrue(case["repeated_records_identical"])
            self.assertEqual(case["trace_repetitions"], 2)

    def test_union_is_hash_bound_and_includes_elf_interpreter(self):
        union = self.report["successful_regular_file_union"]
        self.assertEqual(union["file_count"], 2283)
        self.assertEqual(union["bytes"], 73_560_058)
        self.assertEqual(
            union["records_sha256"],
            (
                "bbe42686c5708e441cacd3188a4c3252"
                "ec89ff973f85050bb77898d58ac7ef15"
            ),
        )
        self.assertEqual(
            hashlib.sha256(
                PROBE.canonical_json(union["records"])
            ).hexdigest(),
            union["records_sha256"],
        )
        paths = [record["path"] for record in union["records"]]
        self.assertEqual(paths, sorted(paths))
        self.assertEqual(len(paths), len(set(paths)))
        loader = next(
            record
            for record in union["records"]
            if record["path"]
            == "/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2"
        )
        self.assertEqual(loader["bytes"], 236_616)
        self.assertEqual(loader["syscalls"], ["exec_mapping"])
        self.assertEqual(
            loader["sha256"],
            (
                "1cd555ac46b7887edeaf3c42aac5408c"
                "8135e52f6b37870da2cf82d5fe14e829"
            ),
        )
        self.assertEqual(
            sum(
                record["route"] == "system_library"
                for record in union["records"]
            ),
            16,
        )

    def test_rule_asset_successful_open_subset_is_exact(self):
        expected = {
            "db": (2124, 2097, 27, 5735),
            "db_extra": (142, 138, 4, 504),
            "db_custom": (2, 0, 2, 196),
        }
        inventory = PROBE.rule_inventory(ROOT)
        for tree, (
            asset_count,
            opened_count,
            missing_count,
            missing_bytes,
        ) in expected.items():
            item = self.report["rule_asset_access"][tree]
            self.assertEqual(item["asset_file_count"], asset_count)
            self.assertEqual(
                item["successfully_opened_file_count"],
                opened_count,
            )
            self.assertEqual(
                item["missing_file_count"],
                missing_count,
            )
            self.assertEqual(item["missing_bytes"], missing_bytes)
            self.assertEqual(
                item["asset_records_sha256"],
                inventory[tree]["records_sha256"],
            )
            self.assertEqual(
                hashlib.sha256(
                    PROBE.canonical_json(item["missing_records"])
                ).hexdigest(),
                item["missing_records_sha256"],
            )
        missing = [
            record["path"]
            for item in self.report["rule_asset_access"].values()
            for record in item["missing_records"]
        ]
        self.assertEqual(len(missing), 33)
        self.assertFalse(any(path.endswith(".sg") for path in missing))
        self.assertEqual(
            sum("/_icons/" in path for path in missing),
            22,
        )

    def test_scope_keeps_cold_and_cache_claims_false(self):
        scope = self.report["scope"]
        self.assertTrue(
            scope["successful_regular_file_access_closure"]
        )
        for field in (
            "failed_lookup_closure",
            "directory_and_metadata_cache_closure",
            "descendant_process_access_closure",
            "page_residency_observed",
            "posix_fadvise_executed",
            "cold_cache_controlled",
            "cold_benchmark_collected",
            "performance_timings_from_ptrace",
        ):
            self.assertFalse(scope[field])
        self.assertEqual(
            self.report["cases"]["upstream.cli-pe32-json.v1"][
                "volatile_regular_paths"
            ],
            ["/proc/self/maps"],
        )

    def test_helpers_and_repeat_comparison_fail_closed(self):
        self.assertEqual(PROBE.route("/etc/ld.so.cache"), "loader_cache")
        self.assertEqual(
            PROBE.route(
                "/opt/die-source/Detect-It-Easy/db/PE/a.sg"
            ),
            "rules/db",
        )
        self.assertEqual(TRACER.signed_64(2**64 - 1), -1)
        self.assertFalse(TRACER.persistent_path("/proc/self/maps"))
        self.assertTrue(TRACER.persistent_path("/opt/data"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "value.bin"
            path.write_bytes(b"value")
            self.assertEqual(
                TRACER.output_identity(path),
                {
                    "bytes": 5,
                    "sha256": hashlib.sha256(b"value").hexdigest(),
                },
            )
        trace = {
            "successful_regular_files": [
                {
                    "path": "/a",
                    "bytes": 1,
                    "mode": 0o644,
                    "sha256": "0" * 64,
                    "open_count": 1,
                    "syscalls": ["openat"],
                }
            ],
            "volatile_regular_paths": [],
        }
        self.assertTrue(
            PROBE.case_summary([trace, json.loads(json.dumps(trace))])[
                "repeated_records_identical"
            ]
        )
        changed = json.loads(json.dumps(trace))
        changed["successful_regular_files"][0]["open_count"] = 2
        with self.assertRaisesRegex(
            PROBE.AccessProbeError,
            "closures differ",
        ):
            PROBE.case_summary([trace, changed])
        with self.assertRaisesRegex(
            PROBE.AccessProbeError,
            "duplicate JSON key",
        ):
            PROBE.parse_json(b'{"a":1,"a":2}', "fixture")

    def test_document_preserves_exact_results_and_boundary(self):
        document = DOCUMENT_PATH.read_text(encoding="utf-8")
        for text in (
            "2,283",
            "73,560,058",
            "2,097",
            "138",
            "33",
            "PT_INTERP",
            "cold_cache_controlled=false",
            "page_residency_observed=false",
        ):
            self.assertIn(text, document)
        self.assertIn(
            hashlib.sha256(self.report_raw).hexdigest(),
            document,
        )


if __name__ == "__main__":
    unittest.main()
