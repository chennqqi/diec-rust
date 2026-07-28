import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zlib


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "tools"
    / "upstream"
    / "probe_path_locale_filesystem_behavior.py"
)
REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "path-locale-filesystem-engine-qt5.json"
)
MANIFEST_PATH = (
    ROOT / "docs" / "research" / "data" / "path-locale-fixture.json"
)
DOCUMENT_PATH = (
    ROOT / "docs" / "research" / "path-locale-filesystem-behavior.md"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_path_locale_filesystem_behavior",
    SCRIPT,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ProbePathLocaleFilesystemBehaviorTest(unittest.TestCase):
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
        self.assertIsNone(report["remaining_gap"])
        self.assertEqual(
            report["generator"],
            (
                "tools/upstream/"
                "probe_path_locale_filesystem_behavior.py"
            ),
        )
        self.assertEqual(
            report["generator_sha256"],
            hashlib.sha256(SCRIPT.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            report["fixture"]["manifest_sha256"],
            hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(),
        )

    def test_matrix_covers_every_locale_filesystem_and_oracle(self) -> None:
        matrix = self.report["matrix"]
        self.assertEqual(
            set(matrix),
            {
                f"{locale_name}/{filesystem}"
                for locale_name in MODULE.LOCALES
                for filesystem in MODULE.FILESYSTEMS
            },
        )
        for key, record in matrix.items():
            with self.subTest(case=key):
                self.assertEqual(record["prefix_count"], 17)
                self.assertEqual(
                    record["stdout_sha256"],
                    MODULE.EXPECTED_STDOUT_SHA256[key],
                )
                self.assertEqual(
                    tuple(record["prefixes"]),
                    MODULE.EXPECTED_PREFIXES[key],
                )
                self.assertEqual(
                    record["preflight"]["filesystem_type"],
                    MODULE.FILESYSTEMS[record["filesystem"]][
                        "expected_type"
                    ],
                )
                for oracle in ("qmake", "cmake"):
                    observation = record["observations"][oracle]
                    self.assertEqual(observation["exit_code"], 0)
                    self.assertEqual(observation["stderr"]["bytes"], 0)
                    self.assertGreater(
                        observation["usage"]["wall_elapsed_ns"],
                        0,
                    )

    def test_locale_is_invariant_but_filesystem_changes_case_order(self) -> None:
        equivalence = self.report["output_equivalence"]
        self.assertFalse(equivalence["all_matrix_stdout_byte_equal"])
        self.assertFalse(
            equivalence["filesystem_stdout_byte_equal_within_locale"]
        )
        self.assertTrue(
            equivalence["locale_stdout_byte_equal_within_filesystem"]
        )
        self.assertEqual(
            MODULE.TMPFS_PREFIXES[4:6],
            (
                "/work/case/a-case.empty",
                "/work/case/A-case.empty",
            ),
        )
        self.assertEqual(
            MODULE.VOLUME_PREFIXES[4:6],
            (
                "/work/case/A-case.empty",
                "/work/case/a-case.empty",
            ),
        )
        self.assertEqual(
            MODULE.TMPFS_PREFIXES[:4] + MODULE.TMPFS_PREFIXES[6:],
            MODULE.VOLUME_PREFIXES[:4] + MODULE.VOLUME_PREFIXES[6:],
        )

    def test_filtering_source_and_environment_facts_are_explicit(self) -> None:
        for value in self.report["facts"].values():
            self.assertTrue(value)
        self.assertEqual(
            self.report["locale_inventory"],
            {
                "cmake": ["C", "C.utf8", "POSIX"],
                "qmake": ["C", "C.utf8", "POSIX"],
            },
        )
        for key, record in self.report["matrix"].items():
            expected_charmap = (
                "UTF-8" if key.startswith("C.utf8/") else "ANSI_X3.4-1968"
            )
            self.assertEqual(
                record["preflight"]["charmap"],
                expected_charmap,
            )
            self.assertEqual(
                record["preflight"]["name_count"],
                len(self.manifest["names"]),
            )
        self.assertEqual(
            set(self.report["source_contract"]),
            set(MODULE.SOURCE_PATHS),
        )
        for path, patterns in MODULE.SOURCE_PATTERNS.items():
            records = self.report["source_contract"][path][
                "required_patterns"
            ]
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
        for record in self.report["matrix"].values():
            for observation in record["observations"].values():
                for stream in ("stdout", "stderr"):
                    ref = observation[stream]
                    digest = ref["artifact_sha256"]
                    referenced.add(digest)
                    self.assertEqual(ref["sha256"], digest)
                    self.assertEqual(ref["bytes"], len(decoded[digest]))
        self.assertEqual(referenced, set(artifacts))

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
            changed["names"][0]["path_bytes_hex"] = "00"
            tampered = Path(directory) / "tampered.json"
            tampered.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(
                MODULE.ProbeError,
                "unsafe or duplicate raw name",
            ):
                MODULE.load_fixture(tampered)

    def test_document_records_scope_and_non_claims(self) -> None:
        document = DOCUMENT_PATH.read_text(encoding="utf-8")
        for token in (
            "C.utf8",
            "POSIX",
            "tmpfs",
            "ext2/ext3",
            "A-case",
            "a-case",
            "CAP-GAP-003",
            "CAP-GAP-007",
            "CAP-GAP-008",
        ):
            self.assertIn(token, document)


if __name__ == "__main__":
    unittest.main()
