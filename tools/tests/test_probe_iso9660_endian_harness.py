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
    / "probe_iso9660_endian_harness.py"
)
REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "iso9660-endian-engine-qt5.json"
)
MANIFEST_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "iso9660-endian-corpus.json"
)
DOCUMENT_PATH = (
    ROOT / "docs" / "research" / "iso9660-endian-behavior.md"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_iso9660_endian_harness",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

GENERATOR_PATH = (
    ROOT
    / "tools"
    / "corpus"
    / "generate_iso9660_endian_fixture.py"
)
GENERATOR_SPEC = importlib.util.spec_from_file_location(
    "generate_iso9660_endian_fixture_for_probe_test",
    GENERATOR_PATH,
)
assert (
    GENERATOR_SPEC is not None
    and GENERATOR_SPEC.loader is not None
)
GENERATOR = importlib.util.module_from_spec(GENERATOR_SPEC)
sys.modules[GENERATOR_SPEC.name] = GENERATOR
GENERATOR_SPEC.loader.exec_module(GENERATOR)


class ProbeIso9660EndianHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = json.loads(
            REPORT_PATH.read_text(encoding="utf-8")
        )
        cls.manifest = json.loads(
            MANIFEST_PATH.read_text(encoding="utf-8")
        )

    def test_report_passes_and_binds_fixed_identity(self):
        self.assertTrue(self.report["passed"])
        self.assertEqual(self.report["failures"], [])
        self.assertTrue(all(self.report["facts"].values()))
        self.assertEqual(
            self.report["upstream_commit"],
            MODULE.UPSTREAM_COMMIT,
        )
        self.assertEqual(
            self.report["generator_sha256"],
            hashlib.sha256(MODULE_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            self.report["image"]["id"],
            (
                "sha256:"
                "771b9094a2ad6ab4f6250dd89307ab727c07a1aa"
                "e885a894695abfa959bab5dc"
            ),
        )
        self.assertEqual(
            self.report["fixture_manifest"]["sha256"],
            hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            self.report["fixture_manifest"]["sample_count"],
            35,
        )
        self.assertEqual(self.report["execution_count"], 140)
        self.assertEqual(
            self.report["remaining_gap"],
            "CAP-GAP-006",
        )

    def test_all_samples_have_four_exact_modes(self):
        self.assertEqual(
            set(self.report["cases"]),
            MODULE.EXPECTED_NAMES,
        )
        self.assertEqual(
            set(self.report["cases"]),
            {sample["name"] for sample in self.manifest["samples"]},
        )
        for sample_name, cases in self.report["cases"].items():
            with self.subTest(sample=sample_name):
                self.assertEqual(
                    set(cases),
                    {
                        "archive",
                        "archive_aggressive",
                        "default",
                        "release_default",
                    },
                )
                self.assertEqual(
                    cases["default"]["stdout"],
                    cases["release_default"]["stdout"],
                )
                self.assertEqual(
                    cases["default"]["stderr"],
                    cases["release_default"]["stderr"],
                )
                self.assertEqual(
                    cases["archive"]["stdout"],
                    cases["archive_aggressive"]["stdout"],
                )
                self.assertEqual(
                    cases["archive"]["stderr"],
                    cases["archive_aggressive"]["stderr"],
                )
                for mode, case in cases.items():
                    with self.subTest(
                        sample=sample_name,
                        mode=mode,
                    ):
                        self.assertEqual(case["exit_code"], 0)
                        self.assertEqual(case["stderr"]["bytes"], 0)
                        self.assertEqual(
                            case["summary"]["root_filetype"],
                            "ISO 9660",
                        )
                        self.assertEqual(
                            case["summary"][
                                "root_detection_names"
                            ],
                            ["Unknown"],
                        )
                        expected = MODULE.expected_streams(
                            sample_name,
                            mode,
                        )
                        self.assertEqual(
                            case["summary"]["streams"],
                            expected,
                        )
                        self.assertEqual(
                            case["summary"]["stream_count"],
                            len(expected),
                        )

    def test_little_and_big_endian_conflicts_are_exact(self):
        cases = self.report["cases"]
        for field in MODULE.FIELD_NAMES:
            with self.subTest(field=field, side="big"):
                name = f"iso9660-{field}-big-alternate.iso"
                self.assertEqual(
                    cases[name]["archive"]["summary"]["streams"],
                    [MODULE.PDF_331],
                )
        for field in MODULE.LITTLE_SUPPRESSED_FIELDS:
            with self.subTest(field=field, side="little"):
                name = f"iso9660-{field}-little-alternate.iso"
                self.assertEqual(
                    cases[name]["archive"]["summary"]["streams"],
                    [],
                )
        self.assertEqual(
            cases[
                "iso9660-payload-size-little-alternate.iso"
            ]["archive"]["summary"]["streams"],
            [MODULE.PDF_332],
        )

    def test_raw_artifacts_inflate_and_match_references(self):
        artifacts = self.report["raw_artifacts"]
        for artifact_sha, artifact in artifacts.items():
            with self.subTest(artifact=artifact_sha):
                self.assertEqual(
                    artifact["encoding"],
                    "zlib+base64",
                )
                compressed = base64.b64decode(
                    artifact["base64"],
                    validate=True,
                )
                self.assertEqual(
                    len(compressed),
                    artifact["compressed_bytes"],
                )
                raw = zlib.decompress(compressed)
                self.assertEqual(len(raw), artifact["bytes"])
                self.assertEqual(
                    hashlib.sha256(raw).hexdigest(),
                    artifact_sha,
                )
        for sample_cases in self.report["cases"].values():
            for case in sample_cases.values():
                for stream_name in ("stdout", "stderr"):
                    reference = case[stream_name]
                    self.assertIn(
                        reference["artifact_sha256"],
                        artifacts,
                    )
                    self.assertEqual(
                        reference["sha256"],
                        reference["artifact_sha256"],
                    )
                    self.assertEqual(
                        reference["bytes"],
                        artifacts[
                            reference["artifact_sha256"]
                        ]["bytes"],
                    )

    def test_fixture_loader_rejects_extra_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = GENERATOR.generate(root)
            manifest_path = root / "manifest.json"
            self.assertEqual(len(manifest["samples"]), 35)
            MODULE.load_fixture(root, manifest_path)
            (root / "unexpected.bin").write_bytes(b"x")
            with self.assertRaisesRegex(
                MODULE.ProbeError,
                "inventory mismatch",
            ):
                MODULE.load_fixture(root, manifest_path)

    def test_report_records_limits_sources_and_document(self):
        self.assertEqual(
            self.report["resource_limits"],
            {
                "container_root": "read-only",
                "cpus": 1,
                "fixture_mount": "read-only",
                "memory_bytes": 512 * 1024 * 1024,
                "network": "none",
                "pids": 128,
                "timeout_seconds_per_execution": 60,
            },
        )
        for source in self.report["local_sources"].values():
            source_path = ROOT / source["path"]
            self.assertEqual(
                source["sha256"],
                hashlib.sha256(source_path.read_bytes()).hexdigest(),
            )
        document = DOCUMENT_PATH.read_text(encoding="utf-8")
        self.assertIn("CAP-GAP-006", document)
        self.assertIn(
            hashlib.sha256(REPORT_PATH.read_bytes()).hexdigest(),
            document,
        )
        for fact in self.report["facts"]:
            self.assertIn(fact, document)


if __name__ == "__main__":
    unittest.main()
