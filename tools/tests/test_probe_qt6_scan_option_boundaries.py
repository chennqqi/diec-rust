import base64
import hashlib
import importlib.util
import json
import pathlib
import sys
import unittest
import zlib


ROOT = pathlib.Path(__file__).resolve().parents[2]
REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "scan-option-boundaries-linux-qt6.json"
)
QT5_REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "scan-option-boundaries-linux-qt5.json"
)
MANIFEST_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "scan-option-boundary-fixture.json"
)
PROBE_PATH = (
    ROOT
    / "tools"
    / "upstream"
    / "probe_qt6_scan_option_boundaries.py"
)
DOCUMENT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "qt6-count-boundary-runtime-evidence.md"
)
CAPABILITY_MATRIX_PATH = (
    ROOT / "docs" / "research" / "capability-matrix.md"
)
QT6_ITERATION_REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "archive-iteration-boundary-engine-qt6.json"
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_probe():
    spec = importlib.util.spec_from_file_location(
        "_test_qt6_scan_option_boundaries",
        PROBE_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Qt6 scan-option probe")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


PROBE = load_probe()


class Qt6ScanOptionBoundaryProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report_bytes = REPORT_PATH.read_bytes()
        cls.report = json.loads(cls.report_bytes)
        cls.qt5_report = json.loads(QT5_REPORT_PATH.read_bytes())

    def test_report_identity_is_exact(self):
        report = self.report
        self.assertEqual(
            sha256(self.report_bytes),
            "4f9f4e1c249ebc7b8b6277544ba4c5790bbab3a5ed2158580b79dd6356b6841f",
        )
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(
            report["upstream_commit"],
            "74eaf505c250ab47e709024e9dc41657cd8f2254",
        )
        self.assertEqual(report["platform"], "linux-x86_64-qt6")
        self.assertEqual(
            report["generator_sha256"],
            sha256(PROBE_PATH.read_bytes()),
        )
        self.assertTrue(report["passed"])
        self.assertEqual(report["failures"], [])
        self.assertEqual(report["closed_capability"], "CAP-NEST-004")

    def test_fixture_and_qt5_reference_are_exact(self):
        report = self.report
        self.assertEqual(
            report["fixture_manifest"],
            {
                "entry_count": 9,
                "path": (
                    "docs/research/data/"
                    "scan-option-boundary-fixture.json"
                ),
                "sha256": sha256(MANIFEST_PATH.read_bytes()),
            },
        )
        self.assertEqual(
            report["qt5_reference"],
            {
                "oracle": "linux-qt5-cmake",
                "path": (
                    "docs/research/data/"
                    "scan-option-boundaries-linux-qt5.json"
                ),
                "sha256": sha256(QT5_REPORT_PATH.read_bytes()),
            },
        )
        self.assertEqual(
            report["qt5_reference"]["sha256"],
            "f193a9f308b04a89dd7ceeda52a658eda2ef13eb82b9c0662c66215248bbf49d",
        )

    def test_oracle_and_sources_are_exact(self):
        observation = self.report["observation"]
        self.assertEqual(
            observation["image_id"],
            "sha256:e015495c313d0715f0b80f395da983a113a439f2a135eb637e9f0638c225200b",
        )
        self.assertEqual(
            observation["binary_sha256"],
            "e3321105af0349b29195325e79d5d2c7cc25ead2f28f84e242e3835b98f7283e",
        )
        self.assertEqual(
            observation["resource_source_sha256"],
            "e088bebb7c8345ce5832cc51de712c05a8b239873d7f092db3ae5566a761b498",
        )
        self.assertEqual(
            observation["console_source_sha256"],
            "ebb82a94fdd0f54722ea36589d6a35694ec4022bc9179030dae6a85e7a9d7e8f",
        )
        self.assertEqual(
            observation["pe_source_sha256"],
            "bfad885df2569b03bc33c040852a884bfe40d781a58bef5f6d8c53c16b488a0c",
        )
        self.assertEqual(observation["repetitions"], 2)
        for source in self.report["local_sources"].values():
            self.assertEqual(
                source["sha256"],
                sha256((ROOT / source["path"]).read_bytes()),
            )

    def test_two_repetitions_reconstruct_and_are_raw_equal(self):
        artifacts = self.report["raw_artifacts"]
        for digest, artifact in artifacts.items():
            compressed = base64.b64decode(
                artifact["base64"],
                validate=True,
            )
            self.assertEqual(
                len(compressed),
                artifact["compressed_bytes"],
            )
            data = zlib.decompress(compressed)
            self.assertEqual(len(data), artifact["bytes"])
            self.assertEqual(sha256(data), digest)
        for case in self.report["observation"]["cases"].values():
            self.assertEqual(len(case["executions"]), 2)
            self.assertEqual(
                case["executions"][0],
                case["executions"][1],
            )
            for execution in case["executions"]:
                self.assertEqual(execution["exit_code"], 0)
                for stream in ("stdout", "stderr"):
                    reference = execution[stream]
                    self.assertEqual(
                        reference["sha256"],
                        reference["artifact_sha256"],
                    )
                    self.assertIn(reference["sha256"], artifacts)

    def test_qt5_qt6_summaries_and_boundaries_are_exact(self):
        qt6_cases = self.report["observation"]["cases"]
        qt5_cases = self.qt5_report["observations"][
            "linux-qt5-cmake"
        ]["cases"]
        expected_counts = {
            "aggressive_without_recursive": 0,
            "deep_default": 0,
            "deep_enabled": 0,
            "recursive_aggressive_pdf_22": 22,
            "recursive_aggressive_unclassified": 1,
            "recursive_aggressive_unclassified_2002": 2001,
            "recursive_pdf_22": 21,
            "recursive_unclassified": 0,
        }
        self.assertEqual(set(qt6_cases), set(expected_counts))
        for name, expected_count in expected_counts.items():
            summary = qt6_cases[name]["summary"]
            self.assertEqual(summary, qt5_cases[name]["summary"])
            self.assertEqual(
                summary["resource_count"],
                expected_count,
            )
            if expected_count > 1:
                self.assertTrue(
                    summary[
                        "resource_offsets_strictly_increasing"
                    ]
                )

    def test_diagnostics_and_source_audit_are_classified(self):
        diagnostic = self.report["known_qt6_diagnostic"]
        self.assertEqual(diagnostic["affected_cases"], [])
        self.assertEqual(
            diagnostic["stderr_bytes_per_affected_execution"],
            80,
        )
        self.assertEqual(
            diagnostic["stderr_sha256_per_affected_execution"],
            sha256(PROBE.QT6_WARNING),
        )
        empty_sha256 = sha256(b"")
        for case in self.report["observation"]["cases"].values():
            for execution in case["executions"]:
                self.assertEqual(
                    execution["stderr"]["sha256"],
                    empty_sha256,
                )
        self.assertEqual(
            self.report["source_audit"][
                "required_pattern_counts"
            ],
            self.qt5_report["source_audit"][
                "required_pattern_counts"
            ],
        )
        self.assertTrue(all(self.report["facts"].values()))

    def test_documents_bind_report_and_capability(self):
        document = DOCUMENT_PATH.read_text(encoding="utf-8")
        matrix = CAPABILITY_MATRIX_PATH.read_text(encoding="utf-8")
        self.assertIn("CAP-NEST-004", document)
        self.assertIn("CAP-NEST-004", matrix)
        self.assertIn(REPORT_PATH.name, document)
        self.assertIn(sha256(self.report_bytes), document)
        self.assertIn(
            sha256(QT6_ITERATION_REPORT_PATH.read_bytes()),
            document,
        )
        self.assertIn("21/2001", document)
        self.assertIn("99999/100000/100001", document)


if __name__ == "__main__":
    unittest.main()
