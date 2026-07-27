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
    / "probe_archive_adversarial_harness.py"
)
REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "archive-adversarial-engine-qt5.json"
)
MANIFEST_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "archive-adversarial-corpus.json"
)
DOCUMENT_PATH = (
    ROOT / "docs" / "research" / "archive-adversarial-behavior.md"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_archive_adversarial_harness",
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
    / "generate_archive_adversarial_fixture.py"
)
GENERATOR_SPEC = importlib.util.spec_from_file_location(
    "generate_archive_adversarial_fixture_for_probe_test",
    GENERATOR_PATH,
)
assert (
    GENERATOR_SPEC is not None
    and GENERATOR_SPEC.loader is not None
)
GENERATOR = importlib.util.module_from_spec(GENERATOR_SPEC)
sys.modules[GENERATOR_SPEC.name] = GENERATOR
GENERATOR_SPEC.loader.exec_module(GENERATOR)


class ProbeArchiveAdversarialHarnessTests(unittest.TestCase):
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
        self.assertRegex(
            self.report["image"]["id"],
            r"^sha256:[0-9a-f]{64}$",
        )
        self.assertEqual(
            self.report["fixture_manifest"]["sha256"],
            hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            self.report["fixture_manifest"]["sample_count"],
            len(self.manifest["samples"]),
        )

    def test_all_samples_have_four_modes_and_fixed_defaults(self):
        self.assertEqual(
            set(self.report["cases"]),
            {sample["name"] for sample in self.manifest["samples"]},
        )
        for name, cases in self.report["cases"].items():
            with self.subTest(sample=name):
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
                    cases["default"]["summary"]["stream_count"],
                    0,
                )

    def test_compressed_encrypted_and_malformed_semantics(self):
        cases = self.report["cases"]
        self.assertEqual(
            cases["deflate-valid.zip"]["archive"]["summary"][
                "streams"
            ][0]["filetype"],
            "PDF",
        )
        self.assertEqual(
            cases["deflate-high-ratio.zip"]["archive"]["summary"][
                "streams"
            ][0]["size"],
            "1048576",
        )
        for name in (
            "zipcrypto-stored.zip",
            "stored-bad-crc.zip",
            "deflate-corrupt.zip",
            "deflate-truncated.zip",
            "stored-invalid-local-offset.zip",
            "unsupported-method-99.zip",
        ):
            with self.subTest(sample=name):
                self.assertEqual(
                    cases[name]["archive"]["summary"][
                        "stream_count"
                    ],
                    0,
                )
        self.assertEqual(
            cases["stored-local-only.zip"]["archive"]["summary"][
                "streams"
            ][0]["filetype"],
            "PDF",
        )
        self.assertEqual(
            cases["mixed-members.zip"]["archive"]["summary"][
                "stream_count"
            ],
            1,
        )
        self.assertEqual(
            cases["mixed-members.zip"]["archive_aggressive"][
                "summary"
            ]["stream_count"],
            2,
        )

    def test_invalid_offset_warning_and_raw_artifacts_are_exact(self):
        warning_ref = self.report["cases"][
            "stored-invalid-local-offset.zip"
        ]["archive"]["stderr"]
        warning_artifact = self.report["raw_artifacts"][
            warning_ref["artifact_sha256"]
        ]
        warning = zlib.decompress(
            base64.b64decode(
                warning_artifact["base64"],
                validate=True,
            )
        )
        self.assertEqual(warning.decode(), MODULE.INVALID_OFFSET_STDERR)

        for digest, artifact in self.report["raw_artifacts"].items():
            with self.subTest(digest=digest):
                raw = zlib.decompress(
                    base64.b64decode(
                        artifact["base64"],
                        validate=True,
                    )
                )
                self.assertEqual(len(raw), artifact["bytes"])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), digest)
                self.assertEqual(
                    len(base64.b64decode(artifact["base64"])),
                    artifact["compressed_bytes"],
                )

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

    def test_research_document_records_observed_boundaries(self):
        document = DOCUMENT_PATH.read_text(encoding="utf-8")
        for token in (
            "ZipCrypto",
            "843.58",
            "local-header fallback",
            "QBuffer::seek",
            "CAP-GAP-006",
        ):
            self.assertIn(token, document)


if __name__ == "__main__":
    unittest.main()
