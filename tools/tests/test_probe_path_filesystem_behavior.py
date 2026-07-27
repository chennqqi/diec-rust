import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zlib


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT
    / "tools"
    / "upstream"
    / "probe_path_filesystem_behavior.py"
)
REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "path-filesystem-engine-qt5.json"
)
MANIFEST_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "path-filesystem-fixture.json"
)
DOCUMENT_PATH = (
    ROOT / "docs" / "research" / "path-filesystem-behavior.md"
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MODULE = load_module("probe_path_filesystem_behavior", MODULE_PATH)
BASELINE = load_module(
    "generate_baseline_for_path_filesystem_probe_tests",
    ROOT / "tools" / "corpus" / "generate_baseline_corpus.py",
)
GENERATOR = load_module(
    "generate_path_filesystem_fixture_for_probe_tests",
    ROOT / "tools" / "corpus" / "generate_path_filesystem_fixture.py",
)


class ProbePathFilesystemBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        cls.manifest = json.loads(
            MANIFEST_PATH.read_text(encoding="utf-8")
        )

    def test_report_passes_and_binds_fixed_identity(self):
        self.assertTrue(self.report["passed"])
        self.assertEqual(self.report["failures"], [])
        self.assertTrue(all(self.report["facts"].values()))
        self.assertEqual(
            self.report["upstream_commit"], MODULE.UPSTREAM_COMMIT
        )
        self.assertEqual(
            self.report["generator_sha256"],
            hashlib.sha256(MODULE_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            self.report["fixture"]["manifest_sha256"],
            hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(self.report["fixture"]["entry_count"], 79)
        self.assertEqual(set(self.report["images"]), set(MODULE.ORACLES))

    def test_all_cases_are_exact_and_qmake_cmake_equal(self):
        self.assertEqual(
            set(self.report["cases"]),
            {case.name for case in MODULE.CASES},
        )
        self.assertEqual(len(self.report["cases"]), 9)
        for name, case in self.report["cases"].items():
            expected = MODULE.EXPECTED_CASES[name]
            observations = case["observations"]
            with self.subTest(case=name):
                self.assertEqual(case["summary"], expected["summary"])
                self.assertEqual(
                    observations["qmake"]["exit_code"],
                    expected["exit_code"],
                )
                self.assertEqual(
                    observations["qmake"]["exit_code"],
                    observations["cmake"]["exit_code"],
                )
                self.assertEqual(
                    observations["qmake"]["stdout"],
                    observations["cmake"]["stdout"],
                )
                self.assertEqual(
                    observations["qmake"]["stderr"],
                    observations["cmake"]["stderr"],
                )
                self.assertEqual(
                    observations["cmake"]["stdout"]["sha256"],
                    expected["stdout_sha256"],
                )

    def test_symlink_permission_depth_and_cycle_semantics(self):
        cases = self.report["cases"]
        for name in (
            "direct_control",
            "file_symlink",
            "directory_symlink",
            "deep_64",
            "denied_as_root",
        ):
            with self.subTest(case=name):
                self.assertEqual(cases[name]["summary"]["pdf_root_count"], 1)
        self.assertEqual(
            cases["denied_as_nobody"]["summary"]["pdf_root_count"], 0
        )
        self.assertEqual(
            cases["denied_as_nobody"]["observations"]["cmake"][
                "stdout"
            ]["sha256"],
            MODULE.EMPTY_SHA256,
        )
        self.assertEqual(
            cases["dangling_symlink"]["summary"]["cannot_find_count"], 1
        )
        self.assertEqual(
            cases["symlink_tree"]["prefix_summary"]["paths"],
            [
                "/work/paths/symlink/dir-link/child.pdf",
                "/work/paths/symlink/dir-target/child.pdf",
                "/work/paths/symlink/file-link.pdf",
                "/work/paths/symlink/target.pdf",
            ],
        )
        cycle = cases["self_cycle"]
        self.assertEqual(
            cycle["prefix_summary"]["loop_depths"],
            list(range(40, -1, -1)),
        )
        self.assertEqual(cycle["summary"]["pdf_root_count"], 41)
        self.assertEqual(
            cycle["observations"]["cmake"]["exit_code"], 0
        )

    def test_extraction_preflight_proves_links_mode_and_depth(self):
        preflight = self.report["fixture"]["extraction_preflight"]
        self.assertEqual(preflight["file_link"], "target.pdf")
        self.assertEqual(preflight["dir_link"], "dir-target")
        self.assertEqual(preflight["dangling_link"], "missing.pdf")
        self.assertEqual(preflight["cycle_link"], ".")
        self.assertEqual(preflight["denied_mode"], 0)
        self.assertEqual(preflight["deep_component_count"], 64)
        self.assertTrue(preflight["file_link_is_symlink"])
        self.assertTrue(preflight["dir_link_is_symlink"])
        self.assertTrue(preflight["cycle_link_is_symlink"])

    def test_raw_artifacts_are_content_addressed_and_complete(self):
        referenced = set()
        for case in self.report["cases"].values():
            for observation in case["observations"].values():
                referenced.add(
                    observation["stdout"]["artifact_sha256"]
                )
                referenced.add(
                    observation["stderr"]["artifact_sha256"]
                )
        self.assertEqual(referenced, set(self.report["raw_artifacts"]))
        for digest, artifact in self.report["raw_artifacts"].items():
            with self.subTest(digest=digest):
                raw = zlib.decompress(
                    base64.b64decode(
                        artifact["base64"], validate=True
                    )
                )
                self.assertEqual(len(raw), artifact["bytes"])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), digest)

    def test_resource_and_source_contracts_are_fixed(self):
        self.assertEqual(
            self.report["resource_limits"],
            {
                "container_root": "read-only",
                "core_bytes": 0,
                "cpus": 1,
                "fixture_mount": "read-only",
                "memory_bytes": 512 * 1024 * 1024,
                "network": "none",
                "pids": 128,
                "timeout_seconds_default": 30,
                "timeout_seconds_self_cycle": 10,
                "work_tmpfs_bytes": 64 * 1024 * 1024,
            },
        )
        self.assertEqual(
            self.report["source_contract"]["path"],
            MODULE.SOURCE_PATH,
        )
        self.assertTrue(
            all(
                count >= 1
                for count in self.report["source_contract"][
                    "required_patterns"
                ].values()
            )
        )

    def test_fixture_loader_rejects_modified_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / "baseline"
            fixture = root / "fixture"
            BASELINE.generate(baseline)
            GENERATOR.generate(baseline, fixture)
            archive = fixture / GENERATOR.ARCHIVE_NAME
            archive.write_bytes(archive.read_bytes() + b"x")
            with self.assertRaisesRegex(
                MODULE.ProbeError, "archive bytes changed"
            ):
                MODULE.load_fixture(fixture, MANIFEST_PATH)

    def test_research_document_records_observed_boundaries(self):
        document = DOCUMENT_PATH.read_text(encoding="utf-8")
        for token in (
            "symlink",
            "41",
            "mode 000",
            "64",
            "CAP-GAP-003",
        ):
            self.assertIn(token, document)


if __name__ == "__main__":
    unittest.main()
