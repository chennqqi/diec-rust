import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
PROBE_PATH = (
    ROOT / "tools/benchmark/probe_upstream_benchmark_page_cache.py"
)
CONTROLLER_PATH = (
    ROOT / "tools/benchmark/control_linux_page_cache.c"
)
REPORT_PATH = (
    ROOT
    / "docs/research/data/"
    "upstream-benchmark-linux-qt5-page-cache.json"
)
ACCESS_PATH = (
    ROOT
    / "docs/research/data/"
    "upstream-benchmark-linux-qt5-file-access.json"
)
DOCUMENT_PATH = (
    ROOT / "docs/research/upstream-benchmark-page-cache.md"
)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


PROBE = load_module("probe_upstream_benchmark_page_cache_test", PROBE_PATH)


class UpstreamBenchmarkPageCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report_raw = REPORT_PATH.read_bytes()
        cls.report = json.loads(cls.report_raw)
        cls.access = json.loads(ACCESS_PATH.read_bytes())

    def test_report_binds_generator_inputs_and_static_controller(self):
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
        self.assertEqual(
            report["successful_file_access"]["sha256"],
            PROBE.EXPECTED_ACCESS_SHA256,
        )
        controller = report["controller"]
        self.assertEqual(
            controller["source_sha256"],
            hashlib.sha256(CONTROLLER_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(controller["binary_bytes"], 799_536)
        self.assertEqual(
            controller["binary_sha256"],
            (
                "cea2a08a79f4f276fd4ad6524f095aff"
                "0a4908957cae6372e927afdadfb97852"
            ),
        )
        self.assertTrue(controller["statically_linked"])
        self.assertFalse(controller["pt_interp_present"])
        self.assertFalse(controller["pt_dynamic_present"])
        self.assertEqual(
            report["environment"]["page_size"],
            PROBE.EXPECTED_PAGE_SIZE,
        )
        self.assertEqual(report["repetitions_per_case"], 2)

    def test_case_page_residency_vectors_are_exact(self):
        expected = {
            "upstream.archive-depth16.v1": (
                2254,
                65_263_871,
                17_832,
                7_985,
                (
                    "ebe6d4ab24adacb3f3b47c666ef589ff"
                    "638a6237a28f79ebd470479c84858c29"
                ),
            ),
            "upstream.cli-baseline-batch-json.v1": (
                2281,
                65_319_431,
                17_869,
                8_331,
                (
                    "df94486899ae800bd409ee7eb5f365f4"
                    "7dce70bda02e76e7140d6958902bf71d"
                ),
            ),
            "upstream.cli-pe32-json.v1": (
                2255,
                65_271_878,
                17_835,
                8_101,
                (
                    "8cfcccf1e7e0360c9549087b607f6e61"
                    "03c79d5254de34b998809a37e03c5a2e"
                ),
            ),
            "upstream.database-load.v1": (
                2253,
                65_261_596,
                17_831,
                7_345,
                (
                    "69b6a3168d10a055fc5bb138b4d1460b"
                    "ebe18679ab8ccd25e456c7bfad3d573e"
                ),
            ),
            "upstream.qt-process-control.v1": (
                18,
                62_358_715,
                15_231,
                4_343,
                (
                    "71b121cac78e156c44fab0742c96766e0"
                    "0d17d630d78d5f915fed68812ea8929"
                ),
            ),
        }
        self.assertEqual(set(self.report["cases"]), set(expected))
        for benchmark_id, values in expected.items():
            files, size, pages, after_run, digest = values
            case = self.report["cases"][benchmark_id]
            self.assertEqual(case["file_count"], files)
            self.assertEqual(case["file_bytes"], size)
            self.assertEqual(case["unique_device_inode_count"], files)
            self.assertEqual(case["logical_pages"], pages)
            self.assertEqual(case["resident_pages_after_warm"], pages)
            self.assertEqual(case["resident_pages_after_evict"], 0)
            self.assertEqual(
                case["resident_pages_after_run"],
                after_run,
            )
            self.assertEqual(case["post_run_records_sha256"], digest)
            self.assertEqual(
                hashlib.sha256(
                    PROBE.canonical_json(case["post_run_records"])
                ).hexdigest(),
                digest,
            )
            self.assertTrue(case["repeated_observations_identical"])

    def test_case_manifests_project_access_closure_exactly(self):
        for benchmark_id, case in self.report["cases"].items():
            records = PROBE.case_records(self.access, benchmark_id)
            with tempfile.TemporaryDirectory() as directory:
                manifest = Path(directory) / "manifest"
                raw = PROBE.write_manifest(manifest, records)
            self.assertEqual(
                hashlib.sha256(raw).hexdigest(),
                case["manifest_sha256"],
            )
            self.assertEqual(len(raw), case["manifest_bytes"])
            self.assertEqual(len(records), case["file_count"])

    def test_scope_keeps_non_file_cache_and_cold_claims_false(self):
        self.assertTrue(all(self.report["relationships"].values()))
        scope = self.report["scope"]
        for field in (
            "successful_regular_file_page_residency_observed",
            "posix_fadvise_dontneed_executed",
            "all_candidate_pages_observed_nonresident_before_run",
        ):
            self.assertTrue(scope[field])
        for field in (
            "directory_and_metadata_cache_controlled",
            "failed_lookup_cache_controlled",
            "overlayfs_host_cache_isolation_proven",
            "cold_cache_controlled",
            "cold_benchmark_collected",
            "performance_timings_collected",
        ):
            self.assertFalse(scope[field])

    def test_elf_and_controller_output_validators_fail_closed(self):
        elf = bytearray(120)
        elf[:6] = b"\x7fELF\x02\x01"
        struct.pack_into("<H", elf, 18, 62)
        struct.pack_into("<Q", elf, 32, 64)
        struct.pack_into("<H", elf, 54, 56)
        struct.pack_into("<H", elf, 56, 1)
        struct.pack_into("<I", elf, 64, 1)
        self.assertTrue(PROBE.validate_static_elf(bytes(elf))["statically_linked"])
        struct.pack_into("<I", elf, 64, 3)
        with self.assertRaisesRegex(
            PROBE.PageCacheProbeError,
            "PT_DYNAMIC or PT_INTERP",
        ):
            PROBE.validate_static_elf(bytes(elf))
        source = [{"path": "/a", "bytes": 4097}]
        valid = (
            b"page_size\t4096\n"
            b"exit_code\t0\n"
            b"file\t/a\t4097\t2\t2\t0\t1\t1\t2\n"
        )
        parsed = PROBE.parse_controller_output(valid, source)
        self.assertEqual(parsed["resident_pages_after_evict"], 0)
        invalid = valid.replace(b"\t0\t1\t1\t2", b"\t1\t1\t1\t2")
        with self.assertRaisesRegex(
            PROBE.PageCacheProbeError,
            "page residency invariant failed",
        ):
            PROBE.parse_controller_output(invalid, source)

    def test_controller_source_preserves_observer_and_watchdog_contract(self):
        source = CONTROLLER_PATH.read_text(encoding="utf-8")
        for text in (
            "POSIX_FADV_DONTNEED",
            "mincore(",
            "mmap(NULL",
            "PROT_NONE",
            "pread(",
            "SIGKILL",
            "120000",
        ):
            self.assertIn(text, source)
        self.assertNotIn("system(", source)

    def test_document_and_report_are_portable_and_hash_bound(self):
        document = DOCUMENT_PATH.read_text(encoding="utf-8")
        for text in (
            "17,869",
            "resident_pages_after_evict=0",
            "PT_INTERP",
            "PT_DYNAMIC",
            "cold_cache_controlled=false",
            "overlayfs_host_cache_isolation_proven=false",
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
