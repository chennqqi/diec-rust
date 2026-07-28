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
    / "probe_archive_truncation_harness.py"
)
REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "archive-truncation-engine-qt5.json"
)
MANIFEST_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "archive-truncation-corpus.json"
)
DOCUMENT_PATH = (
    ROOT / "docs" / "research" / "archive-truncation-behavior.md"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_archive_truncation_harness",
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
    / "generate_archive_truncation_fixture.py"
)
GENERATOR_SPEC = importlib.util.spec_from_file_location(
    "generate_archive_truncation_fixture_for_probe_test",
    GENERATOR_PATH,
)
assert (
    GENERATOR_SPEC is not None
    and GENERATOR_SPEC.loader is not None
)
GENERATOR = importlib.util.module_from_spec(GENERATOR_SPEC)
sys.modules[GENERATOR_SPEC.name] = GENERATOR
GENERATOR_SPEC.loader.exec_module(GENERATOR)


class ProbeArchiveTruncationHarnessTests(unittest.TestCase):
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
            26,
        )
        self.assertEqual(self.report["execution_count"], 104)

    def test_all_samples_have_four_exact_modes(self):
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
                        expected_root = MODULE.EXPECTED_ROOTS[
                            sample_name
                        ]
                        self.assertEqual(
                            case["summary"]["root_filetype"],
                            expected_root[0],
                        )
                        self.assertEqual(
                            case["summary"][
                                "root_detection_names"
                            ],
                            expected_root[1],
                        )

    def test_truncation_child_boundaries_are_exact(self):
        for sample_name, cases in self.report["cases"].items():
            for mode, case in cases.items():
                with self.subTest(sample=sample_name, mode=mode):
                    expected_streams = (
                        [MODULE.EXPECTED_CHILD]
                        if (
                            mode
                            not in {"default", "release_default"}
                            and sample_name in MODULE.CHILD_SAMPLES
                        )
                        else []
                    )
                    self.assertEqual(
                        case["summary"]["streams"],
                        expected_streams,
                    )
                    self.assertEqual(
                        case["summary"]["stream_count"],
                        len(expected_streams),
                    )

        cases = self.report["cases"]
        self.assertEqual(
            cases["sevenzip-full-minus-one.7z"]["archive"][
                "summary"
            ]["stream_count"],
            0,
        )
        self.assertEqual(
            cases["cab-full-minus-one.cab"]["archive"]["summary"][
                "stream_count"
            ],
            0,
        )
        self.assertEqual(
            cases["rar4-payload.rar"]["archive"]["summary"][
                "streams"
            ],
            [MODULE.EXPECTED_CHILD],
        )
        self.assertEqual(
            cases["iso9660-full-minus-one.iso"]["archive"][
                "summary"
            ]["streams"],
            [MODULE.EXPECTED_CHILD],
        )

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
