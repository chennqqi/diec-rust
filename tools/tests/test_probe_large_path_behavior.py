import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zlib


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "upstream" / "probe_large_path_behavior.py"
REPORT_PATH = (
    ROOT / "docs" / "research" / "data" / "large-path-engine-qt5.json"
)
MANIFEST_PATH = (
    ROOT / "docs" / "research" / "data" / "large-path-fixture.json"
)
DOCUMENT_PATH = (
    ROOT / "docs" / "research" / "large-directory-behavior.md"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_large_path_behavior",
    SCRIPT,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ProbeLargePathBehaviorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        cls.manifest = json.loads(
            MANIFEST_PATH.read_text(encoding="utf-8")
        )

    def test_identity_and_generator_are_pinned(self) -> None:
        report = self.report
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["upstream_commit"], MODULE.UPSTREAM_COMMIT)
        self.assertEqual(report["platform"], "linux-x86_64-qt5")
        self.assertTrue(report["passed"])
        self.assertEqual(report["failures"], [])
        self.assertEqual(
            report["generator"],
            "tools/upstream/probe_large_path_behavior.py",
        )
        self.assertEqual(
            report["generator_sha256"],
            hashlib.sha256(SCRIPT.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            report["fixture"]["manifest_sha256"],
            hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(),
        )

    def test_case_matrix_emits_every_declared_file(self) -> None:
        cases = self.report["cases"]
        self.assertEqual(
            set(cases),
            {
                "empty_0",
                "single_1",
                "flat_256",
                "flat_4096",
                "nested_4096",
            },
        )
        expected_counts = {
            "empty_0": (0, 0),
            "single_1": (1, 0),
            "flat_256": (256, 256),
            "flat_4096": (4096, 4096),
            "nested_4096": (4096, 4096),
        }
        for name, (documents, prefixes) in expected_counts.items():
            case = cases[name]
            with self.subTest(case=name):
                self.assertEqual(case["entropy_document_count"], documents)
                self.assertEqual(case["prefix_count"], prefixes)
                self.assertEqual(case["file_count"], documents)
                self.assertEqual(
                    case["stdout_sha256"],
                    MODULE.EXPECTED_STDOUT_SHA256[name],
                )
                for oracle in ("qmake", "cmake"):
                    observation = case["observations"][oracle]
                    self.assertEqual(observation["exit_code"], 0)
                    self.assertEqual(observation["stderr"]["bytes"], 0)
                    self.assertGreater(
                        observation["usage"]["wall_elapsed_ns"],
                        0,
                    )
                    self.assertGreater(
                        observation["usage"]["max_rss_kib"],
                        0,
                    )

    def test_flat_and_nested_order_are_frozen(self) -> None:
        flat = self.report["cases"]["flat_4096"]
        self.assertEqual(
            flat["first_prefix"],
            "/work/case/item-000000.empty",
        )
        self.assertEqual(
            flat["last_prefix"],
            "/work/case/item-004095.empty",
        )
        nested = self.report["cases"]["nested_4096"]
        self.assertEqual(
            nested["first_prefix"],
            "/work/case/bucket-000/item-000000.empty",
        )
        self.assertEqual(
            nested["last_prefix"],
            "/work/case/bucket-015/item-000255.empty",
        )
        self.assertNotEqual(
            flat["prefixes_sha256"],
            nested["prefixes_sha256"],
        )

    def test_cli_cancellation_reachability_is_source_bound(self) -> None:
        facts = self.report["facts"]
        for fact in (
            "all_4096_flat_files_are_emitted",
            "all_4096_nested_files_are_emitted",
            "creation_order_does_not_override_qdir_name_order",
            "cli_find_files_uses_default_null_pdstruct",
            "cli_target_expansion_has_no_wired_cooperative_cancel",
            "find_files_optional_pdstruct_supports_cancel_checks",
            "qmake_and_cmake_outputs_are_byte_equal",
        ):
            self.assertTrue(facts[fact])
        source = self.report["source_contract"]
        self.assertEqual(set(source), set(MODULE.SOURCE_PATHS))
        for path, patterns in MODULE.SOURCE_PATTERNS.items():
            records = source[path]["required_patterns"]
            for pattern in patterns:
                self.assertGreaterEqual(records[pattern]["count"], 1)
                self.assertTrue(records[pattern]["lines"])

    def test_raw_artifacts_are_content_addressed_and_referenced(self) -> None:
        artifacts = self.report["raw_artifacts"]
        decoded = {}
        for digest, artifact in artifacts.items():
            compressed = base64.b64decode(
                artifact["base64"],
                validate=True,
            )
            raw = zlib.decompress(compressed)
            self.assertEqual(len(raw), artifact["bytes"])
            self.assertEqual(len(compressed), artifact["compressed_bytes"])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), digest)
            decoded[digest] = raw
        referenced = set()
        for case in self.report["cases"].values():
            for observation in case["observations"].values():
                for stream in ("stdout", "stderr"):
                    ref = observation[stream]
                    digest = ref["artifact_sha256"]
                    referenced.add(digest)
                    self.assertEqual(ref["sha256"], digest)
                    self.assertEqual(ref["bytes"], len(decoded[digest]))
        self.assertEqual(referenced, set(artifacts))

    def test_limits_and_fixture_plan_are_explicit(self) -> None:
        limits = self.report["resource_limits"]
        self.assertEqual(limits["memory_bytes"], 512 * 1024 * 1024)
        self.assertEqual(limits["work_tmpfs_bytes"], 64 * 1024 * 1024)
        self.assertEqual(limits["cpus"], 1)
        self.assertEqual(limits["pids"], 128)
        self.assertEqual(limits["timeout_seconds"], 60)
        self.assertEqual(limits["network"], "none")
        self.assertEqual(limits["container_root"], "read-only")
        self.assertEqual(
            self.manifest["materialization"]["creation_order"],
            "descending",
        )

    def test_strict_loader_rejects_duplicate_keys_and_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            duplicate = Path(directory) / "duplicate.json"
            duplicate.write_text(
                '{"schema_version":1,"schema_version":1}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                MODULE.ProbeError,
                "duplicate JSON key",
            ):
                MODULE.load_fixture(duplicate)

            changed = json.loads(json.dumps(self.manifest))
            changed["cases"][3]["file_count"] = 4095
            tampered = Path(directory) / "tampered.json"
            tampered.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(
                MODULE.ProbeError,
                "fixture case changed",
            ):
                MODULE.load_fixture(tampered)

    def test_document_records_scope_and_non_claims(self) -> None:
        document = DOCUMENT_PATH.read_text(encoding="utf-8")
        for token in (
            "4096",
            "PDSTRUCT",
            "nullptr",
            "cooperative cancellation",
            "TOCTOU",
            "CAP-GAP-003",
            "ADR 0014",
        ):
            self.assertIn(token, document)


if __name__ == "__main__":
    unittest.main()
