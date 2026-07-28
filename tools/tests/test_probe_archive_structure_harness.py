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
    / "probe_archive_structure_harness.py"
)
REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "archive-structure-engine-qt5.json"
)
MANIFEST_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "archive-structure-corpus.json"
)
DOCUMENT_PATH = (
    ROOT / "docs" / "research" / "archive-structure-behavior.md"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_archive_structure_harness",
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
    / "generate_archive_structure_fixture.py"
)
GENERATOR_SPEC = importlib.util.spec_from_file_location(
    "generate_archive_structure_fixture_for_probe_test",
    GENERATOR_PATH,
)
assert (
    GENERATOR_SPEC is not None
    and GENERATOR_SPEC.loader is not None
)
GENERATOR = importlib.util.module_from_spec(GENERATOR_SPEC)
sys.modules[GENERATOR_SPEC.name] = GENERATOR
GENERATOR_SPEC.loader.exec_module(GENERATOR)


class ProbeArchiveStructureHarnessTests(unittest.TestCase):
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
            56,
        )
        self.assertEqual(self.report["execution_count"], 224)

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
                aggressive_only = (
                    sample_name in MODULE.AGGRESSIVE_ONLY_CHILDREN
                )
                self.assertEqual(
                    cases["archive"]["stdout"]
                    != cases["archive_aggressive"]["stdout"],
                    aggressive_only,
                )
                for mode, case in cases.items():
                    with self.subTest(
                        sample=sample_name,
                        mode=mode,
                    ):
                        self.assertEqual(case["exit_code"], 0)
                        self.assertEqual(
                            case["stderr"]["bytes"],
                            len(
                                MODULE.expected_stderr(
                                    sample_name,
                                    mode,
                                )
                            ),
                        )
                        root_filetype, root_names = (
                            MODULE.expected_root(sample_name)
                        )
                        self.assertEqual(
                            case["summary"]["root_filetype"],
                            root_filetype,
                        )
                        self.assertEqual(
                            case["summary"][
                                "root_detection_names"
                            ],
                            root_names,
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

    def test_crc_and_declared_size_quirks_are_exact(self):
        cases = self.report["cases"]
        for sample in (
            "sevenzip-start-header-crc-bit-flip.7z",
            "sevenzip-next-header-crc-bit-flip.7z",
            "sevenzip-packed-crc-bit-flip.7z",
            "rar4-main-header-crc-bit-flip.rar",
            "rar4-file-header-crc-bit-flip.rar",
        ):
            with self.subTest(sample=sample):
                self.assertEqual(
                    cases[sample]["archive"]["summary"]["streams"],
                    [MODULE.PDF_331],
                )
        self.assertEqual(
            cases["rar4-data-crc-bit-flip.rar"]["archive"][
                "summary"
            ]["streams"],
            [],
        )
        self.assertEqual(
            cases["iso9660-payload-size-plus-one.iso"]["archive"][
                "summary"
            ]["streams"],
            [MODULE.PDF_332],
        )

    def test_aggressive_cab_outputs_are_exact(self):
        cases = self.report["cases"]
        self.assertEqual(
            cases["cab-files-offset-plus-one.cab"][
                "archive_aggressive"
            ]["summary"]["streams"],
            [MODULE.BINARY_1],
        )
        self.assertEqual(
            cases["cab-method-unknown-0xffff.cab"][
                "archive_aggressive"
            ]["summary"]["streams"],
            [MODULE.BINARY_331],
        )
        for sample in MODULE.AGGRESSIVE_ONLY_CHILDREN:
            self.assertEqual(
                cases[sample]["archive"]["summary"]["streams"],
                [],
            )

    def test_zero_and_max_extrema_are_exact(self):
        cases = self.report["cases"]
        for sample in (
            "sevenzip-next-header-offset-zero.7z",
            "sevenzip-next-header-offset-max-u64.7z",
            "sevenzip-next-header-size-zero.7z",
            "sevenzip-next-header-size-max-u64.7z",
            "rar4-packed-size-zero.rar",
            "rar4-unpacked-size-max-u32.rar",
            "cab-file-size-max-u32.cab",
            "cab-compressed-size-zero.cab",
            "cab-compressed-size-max-u16.cab",
            "iso9660-logical-block-size-zero.iso",
            "iso9660-logical-block-size-max-u16.iso",
            "iso9660-payload-size-max-u32.iso",
        ):
            with self.subTest(sample=sample):
                self.assertEqual(
                    cases[sample]["archive"]["summary"]["streams"],
                    [],
                )

        for sample in (
            "rar4-packed-size-max-u32.rar",
            "rar4-name-size-zero.rar",
            "rar4-name-size-max-u16.rar",
            "cab-cabinet-size-zero.cab",
            "cab-cabinet-size-max-u32.cab",
            "iso9660-payload-record-length-max-u8.iso",
        ):
            with self.subTest(sample=sample):
                self.assertEqual(
                    cases[sample]["archive"]["summary"]["streams"],
                    [MODULE.PDF_331],
                )

        for sample in (
            "rar4-unpacked-size-zero.rar",
            "cab-file-size-zero.cab",
            "iso9660-payload-size-zero.iso",
        ):
            with self.subTest(sample=sample):
                self.assertEqual(
                    cases[sample]["archive"]["summary"]["streams"],
                    [],
                )
                self.assertEqual(
                    cases[sample]["archive_aggressive"]["summary"][
                        "streams"
                    ],
                    [MODULE.EMPTY_0],
                )

        for sample in (
            "iso9660-payload-extent-zero.iso",
            "iso9660-payload-extent-max-u32.iso",
        ):
            with self.subTest(sample=sample):
                self.assertEqual(
                    cases[sample]["archive"]["summary"]["streams"],
                    [],
                )
                self.assertEqual(
                    cases[sample]["archive_aggressive"]["summary"][
                        "streams"
                    ],
                    [MODULE.BINARY_331],
                )

    def test_iso_max_extent_stderr_is_exact(self):
        cases = self.report["cases"][
            "iso9660-payload-extent-max-u32.iso"
        ]
        expected_digest = hashlib.sha256(
            MODULE.ISO_MAX_EXTENT_STDERR
        ).hexdigest()
        for mode in ("archive", "archive_aggressive"):
            reference = cases[mode]["stderr"]
            self.assertEqual(reference["sha256"], expected_digest)
            artifact = self.report["raw_artifacts"][expected_digest]
            raw = zlib.decompress(
                base64.b64decode(
                    artifact["base64"],
                    validate=True,
                )
            )
            self.assertEqual(raw, MODULE.ISO_MAX_EXTENT_STDERR)

    def test_raw_artifacts_are_content_addressed_and_exact(self):
        for digest, artifact in self.report["raw_artifacts"].items():
            with self.subTest(digest=digest):
                self.assertEqual(
                    artifact["encoding"],
                    "zlib+base64",
                )
                compressed = base64.b64decode(
                    artifact["base64"],
                    validate=True,
                )
                raw = zlib.decompress(compressed)
                self.assertEqual(
                    len(compressed),
                    artifact["compressed_bytes"],
                )
                self.assertEqual(len(raw), artifact["bytes"])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), digest)

    def test_source_contract_and_resource_limits_are_fixed(self):
        self.assertEqual(
            set(self.report["source_contract"]),
            set(MODULE.SOURCE_PATHS),
        )
        self.assertTrue(
            all(
                record["required_pattern_count"] >= 1
                for record in self.report[
                    "source_contract"
                ].values()
            )
        )
        expected_local_sources = {
            "fixture_generator": MODULE.FIXTURE_GENERATOR,
            "source_generator": MODULE.SOURCE_GENERATOR,
            "probe_base": MODULE.PROBE_BASE,
            "harness_dockerfile": MODULE.HARNESS_DOCKERFILE,
            "harness_source": MODULE.HARNESS_SOURCE,
        }
        self.assertEqual(
            set(self.report["local_sources"]),
            set(expected_local_sources),
        )
        for name, path in expected_local_sources.items():
            with self.subTest(source=name):
                record = self.report["local_sources"][name]
                self.assertEqual(record["path"], path)
                self.assertEqual(
                    record["sha256"],
                    hashlib.sha256(
                        (ROOT / path).read_bytes()
                    ).hexdigest(),
                )
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

    def test_fixture_loader_rejects_extra_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            GENERATOR.generate(root)
            (root / "extra.bin").write_bytes(b"extra")
            with self.assertRaisesRegex(
                MODULE.ProbeError,
                "inventory mismatch",
            ):
                MODULE.load_fixture(root, MANIFEST_PATH)

    def test_research_document_binds_report_and_facts(self):
        document = DOCUMENT_PATH.read_text(encoding="utf-8")
        report_sha256 = hashlib.sha256(
            REPORT_PATH.read_bytes()
        ).hexdigest()
        self.assertIn(report_sha256, document)
        self.assertIn("CAP-GAP-006", document)
        for fact in self.report["facts"]:
            self.assertIn(fact, document)


if __name__ == "__main__":
    unittest.main()
