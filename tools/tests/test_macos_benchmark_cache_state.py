import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
PROBE_PATH = (
    ROOT / "tools/benchmark/probe_macos_file_content_cache.c"
)
COLLECTOR_PATH = (
    ROOT / "tools/benchmark/collect_macos_cache_state_candidate.py"
)
VALIDATOR_PATH = (
    ROOT / "tools/benchmark/validate_macos_cache_state_candidate.py"
)
PLAN_SCRIPT = (
    ROOT / "tools/research/build_macos_cache_state_plan.py"
)
PLAN_PATH = (
    ROOT
    / "docs/research/data/"
    "macos-benchmark-cache-state-plan.json"
)
DOCUMENT_PATH = (
    ROOT / "docs/research/macos-benchmark-cache-state.md"
)
ADR_PATH = (
    ROOT
    / "docs/design/decisions/"
    "0015-benchmark-cache-state-model.md"
)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


VALIDATOR = load_module(
    "validate_macos_cache_state_candidate_test",
    VALIDATOR_PATH,
)
COLLECTOR = load_module(
    "collect_macos_cache_state_candidate_test",
    COLLECTOR_PATH,
)
PLAN = load_module(
    "build_macos_cache_state_plan_test",
    PLAN_SCRIPT,
)


def observation(after_msync=0):
    return {
        "schema_version": 1,
        "page_size": 4096,
        "fixture_bytes": 16 * 1024 * 1024,
        "logical_pages": 4096,
        "warm_resident_pages": 4096,
        "after_f_nocache_resident_pages": 4096,
        "msync_flags": 18,
        "after_msync_invalidate_resident_pages": after_msync,
        "checksum": 69632,
        "temporary_fixture_unlinked_before_probe": 1,
        "benchmark_files_touched": 0,
        "system_cache_flush_executed": 0,
    }


def candidate_report(after_msync=0):
    first = observation(after_msync)
    equivalent = after_msync == 0
    return {
        "schema_version": 1,
        "result": "candidate",
        "platform": VALIDATOR.PLATFORM,
        "generated_at": "2026-07-30",
        "upstream_commit": (
            "74eaf505c250ab47e709024e9dc41657cd8f2254"
        ),
        "darwin_source": {
            "xnu_commit": VALIDATOR.XNU_COMMIT,
            "fcntl_header_sha256": VALIDATOR.XNU_FCNTL_SHA256,
            "kern_descrip_sha256": (
                VALIDATOR.XNU_KERN_DESCRIP_SHA256
            ),
        },
        "probe": {
            "source_sha256": hashlib.sha256(
                PROBE_PATH.read_bytes()
            ).hexdigest(),
            "binary_sha256": "3" * 64,
            "collector_sha256": hashlib.sha256(
                COLLECTOR_PATH.read_bytes()
            ).hexdigest(),
            "validator_sha256": hashlib.sha256(
                VALIDATOR_PATH.read_bytes()
            ).hexdigest(),
            "compiler_arguments": [
                "-std=c11",
                "-O2",
                "-Wall",
                "-Wextra",
                "-Werror",
            ],
        },
        "host": {
            "machine": "x86_64",
            "macos_product_version": "15.5",
            "macos_build_version": "24F74",
            "darwin_release": "24.5.0",
            "temporary_filesystem": "apfs",
            "clang_version": ["Apple clang version 17.0.0"],
        },
        "observations": [first, copy.deepcopy(first)],
        "relationships": {
            "two_observations_identical": True,
            "all_pages_warm_before_control": True,
            "f_nocache_toggle_alone_evicted_all_pages": False,
            "msync_invalidate_produced_zero_resident_pages": equivalent,
            "linux_file_content_semantic_candidate": equivalent,
        },
        "admission": {
            "cache_state_admitted": False,
            "reason": "candidate evidence only",
        },
        "scope": {
            "temporary_unlinked_fixture_only": True,
            "benchmark_files_touched": False,
            "system_cache_flush_executed": False,
            "performance_baseline": False,
            "runtime_candidate_only": True,
        },
    }


class MacosBenchmarkCacheStateTests(unittest.TestCase):
    def test_plan_is_exact_generator_output_and_source_bound(self):
        report = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
        expected = PLAN.build_plan(ROOT)
        self.assertEqual(report, expected)
        self.assertEqual(PLAN_PATH.read_bytes(), PLAN.serialize(expected))
        for relative, digest in report["sources"].items():
            self.assertEqual(
                hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(),
                digest,
            )

    def test_plan_pins_apple_contract_and_keeps_admission_closed(self):
        report = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
        darwin = report["darwin_contract"]
        self.assertEqual(darwin["xnu_commit"], VALIDATOR.XNU_COMMIT)
        self.assertEqual(
            darwin["xnu_sources"]["bsd/sys/fcntl.h"]["sha256"],
            COLLECTOR.XNU_FCNTL_SHA256,
        )
        self.assertEqual(
            darwin["xnu_sources"][
                "bsd/kern/kern_descrip.c"
            ]["sha256"],
            COLLECTOR.XNU_KERN_DESCRIP_SHA256,
        )
        self.assertEqual(len(darwin["official_manuals"]), 4)
        self.assertTrue(report["admission"]["warm_admitted"])
        self.assertFalse(
            report["admission"]["file_content_state_admitted"]
        )
        self.assertFalse(
            report["admission"]["system_cold_admitted"]
        )
        self.assertEqual(
            report["strategy"][
                "file_content_nonresident_metadata_warm"
            ]["status"],
            "runtime_candidate_not_admitted",
        )

    def test_c_probe_has_narrow_temporary_fixture_boundary(self):
        source = PROBE_PATH.read_text(encoding="utf-8")
        for required in (
            "#ifndef __APPLE__",
            "FIXTURE_BYTES (16U * 1024U * 1024U)",
            "mkstemp(template_path)",
            "unlink(template_path)",
            "fcntl(descriptor, F_NOCACHE, 1)",
            "msync(mapping, length, msync_flags)",
            "mincore(mapping, length",
            'printf("benchmark_files_touched\\t0\\n")',
            'printf("system_cache_flush_executed\\t0\\n")',
        ):
            self.assertIn(required, source)
        self.assertLess(
            source.index("unlink(template_path)"),
            source.index("fcntl(descriptor, F_NOCACHE, 1)"),
        )
        for forbidden in ("system(", "popen(", "purge", "sudo"):
            self.assertNotIn(forbidden, source)

    def test_candidate_validator_accepts_both_runtime_outcomes(self):
        VALIDATOR.validate_report(candidate_report(0))
        VALIDATOR.validate_report(candidate_report(4096))

    def test_candidate_validator_rejects_admission_and_safety_drift(self):
        changed = candidate_report()
        changed["admission"]["cache_state_admitted"] = True
        with self.assertRaisesRegex(
            VALIDATOR.ReportError,
            "must not admit",
        ):
            VALIDATOR.validate_report(changed)

        changed = candidate_report()
        changed["observations"][0][
            "system_cache_flush_executed"
        ] = 1
        with self.assertRaisesRegex(
            VALIDATOR.ReportError,
            "safety boundary",
        ):
            VALIDATOR.validate_report(changed)

        changed = candidate_report()
        changed["observations"][1]["checksum"] += 1
        with self.assertRaisesRegex(
            VALIDATOR.ReportError,
            "observations differ",
        ):
            VALIDATOR.validate_report(changed)

    def test_candidate_loader_and_tsv_parser_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidate.json"
            path.write_text(
                '{"schema_version":1,"schema_version":1}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                VALIDATOR.ReportError,
                "duplicate JSON key",
            ):
                VALIDATOR.load_report(path)
        with self.assertRaisesRegex(
            COLLECTOR.CollectionError,
            "duplicate TSV",
        ):
            COLLECTOR.parse_observation(
                "schema_version\t1\nschema_version\t1\n"
            )
        with self.assertRaisesRegex(
            COLLECTOR.CollectionError,
            "not decimal",
        ):
            COLLECTOR.parse_observation("schema_version\tNaN\n")

    def test_current_host_cannot_fabricate_darwin_report(self):
        if sys.platform == "darwin" and platform.machine() == "x86_64":
            self.skipTest("this assertion is for non-Darwin CI")
        with self.assertRaisesRegex(
            COLLECTOR.CollectionError,
            "requires native Darwin x86_64",
        ):
            COLLECTOR.build_report(ROOT)

    def test_document_adr_and_plan_are_aligned(self):
        document = DOCUMENT_PATH.read_text(encoding="utf-8")
        adr = ADR_PATH.read_text(encoding="utf-8")
        for text in (
            VALIDATOR.XNU_COMMIT,
            "`F_NOCACHE`",
            "`MS_INVALIDATE`",
            "`mincore`",
            "runtime candidate",
        ):
            self.assertIn(text, document)
        self.assertIn("macOS 策略评审输入", adr)
        self.assertIn(
            "runtime_candidate_not_admitted",
            PLAN_PATH.read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
