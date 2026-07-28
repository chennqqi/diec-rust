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
    / "legacy-dispatch-linux-qt5-qt6.json"
)
QT5_REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "legacy-dispatch-linux-qt5.json"
)
MANIFEST_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "legacy-dispatch-corpus.json"
)
PROBE_PATH = (
    ROOT
    / "tools"
    / "upstream"
    / "probe_qt6_legacy_dispatch.py"
)
DOCUMENT_PATH = (
    ROOT / "docs" / "research" / "legacy-dispatch-oracle.md"
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_probe():
    spec = importlib.util.spec_from_file_location(
        "_test_qt6_legacy_dispatch",
        PROBE_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Qt6 legacy dispatch probe")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


PROBE = load_probe()


class Qt6LegacyDispatchProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report_bytes = REPORT_PATH.read_bytes()
        cls.report = json.loads(cls.report_bytes)
        cls.qt5 = json.loads(QT5_REPORT_PATH.read_bytes())

    def test_report_identity_is_exact(self):
        report = self.report
        self.assertEqual(
            sha256(self.report_bytes),
            "8ecbfe6502de89de58b56316cf5d27274cb9fecccc0f523aa9377d302a7bebfa",
        )
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["result"], "pass")
        self.assertEqual(report["failures"], [])
        self.assertEqual(
            report["upstream_commit"],
            "74eaf505c250ab47e709024e9dc41657cd8f2254",
        )
        self.assertEqual(
            report["rules_commit"],
            "c2c17dfa5ea4e078ba31eab55d87430c96622fb6",
        )
        self.assertEqual(
            report["formats_commit"],
            "1151e7254fdee3c0294ff7095edbdd7bfccf8201",
        )
        self.assertEqual(report["platform"], "linux-amd64-qt5-qt6")
        self.assertEqual(report["capability"], "CAP-DISPATCH-003")
        self.assertEqual(
            report["generator_sha256"],
            sha256(PROBE_PATH.read_bytes()),
        )
        self.assertEqual(
            report["closed_capability"],
            "CAP-DISPATCH-003",
        )

    def test_fixture_and_qt5_reference_are_exact(self):
        self.assertEqual(
            self.report["corpus_manifest"],
            {
                "path": (
                    "docs/research/data/"
                    "legacy-dispatch-corpus.json"
                ),
                "sample_count": 8,
                "sha256": sha256(MANIFEST_PATH.read_bytes()),
            },
        )
        self.assertEqual(
            self.report["qt5_reference"],
            {
                "oracle": "linux-qt5-cmake",
                "path": (
                    "docs/research/data/"
                    "legacy-dispatch-linux-qt5.json"
                ),
                "sha256": sha256(QT5_REPORT_PATH.read_bytes()),
            },
        )
        self.assertEqual(
            self.report["qt5_reference"]["sha256"],
            PROBE.QT5_REPORT_SHA256,
        )

    def test_qt6_oracle_and_sources_are_exact(self):
        oracle = self.report["qt6_oracle"]
        self.assertEqual(
            oracle["image_id"],
            "sha256:e015495c313d0715f0b80f395da983a113a439f2a135eb637e9f0638c225200b",
        )
        self.assertEqual(
            oracle["binary_sha256"],
            "e3321105af0349b29195325e79d5d2c7cc25ead2f28f84e242e3835b98f7283e",
        )
        self.assertEqual(
            oracle["source_sha256"],
            {
                "/opt/die-source/Formats/exec/xamigahunk.cpp": (
                    "7cee077d4e9d6ab66fde355e06f62908d835a8d1818c9d0a47b59b9269d3e8a1"
                ),
                "/opt/die-source/Formats/exec/xatarist.cpp": (
                    "7aeda5dda76eb0027bb735dbedd8925cb901f1049a0fcedeb2e2f01a443f1fd2"
                ),
                "/opt/die-source/Formats/xformats.cpp": (
                    "674eba0046eb6cc947e547d1ac0b93ac695cbb30f68e11f135e5551d81e0b115"
                ),
                "/opt/die-source/XScanEngine/xscanengine.cpp": (
                    "e088bebb7c8345ce5832cc51de712c05a8b239873d7f092db3ae5566a761b498"
                ),
            },
        )
        self.assertEqual(self.report["repetitions"], 2)

    def test_raw_artifacts_reconstruct_and_repetitions_are_equal(self):
        artifacts = self.report["raw_artifacts"]
        self.assertEqual(len(artifacts), 15)
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
        for case in self.report["cases"].values():
            executions = case["qt6_executions"]
            self.assertEqual(len(executions), 2)
            self.assertEqual(executions[0], executions[1])
            for execution in executions:
                for mode in ("scan", "detector_info"):
                    self.assertEqual(execution[mode]["exit_code"], 0)
                    for stream in ("stdout", "stderr"):
                        reference = execution[mode][stream]
                        self.assertEqual(
                            reference["sha256"],
                            reference["artifact_sha256"],
                        )
                        self.assertIn(
                            reference["artifact_sha256"],
                            artifacts,
                        )

    def test_dispatch_semantics_and_raw_equality_are_exact(self):
        cases = self.report["cases"]
        self.assertEqual(set(cases), set(self.qt5["cases"]))
        amiga = cases["minimal-amiga-hunk.bin"]
        atari = cases["minimal-atari-st.prg"]
        self.assertEqual(
            amiga["qt6_executions"][0]["detector_info"]["filetype"],
            "Amiga Hunk",
        )
        self.assertEqual(
            amiga["qt6_executions"][0]["scan"]["detect_tree"][0][
                "filetype"
            ],
            "Amiga Hunk",
        )
        self.assertEqual(
            atari["qt6_executions"][0]["detector_info"]["filetype"],
            "Atari ST",
        )
        self.assertEqual(
            atari["qt6_executions"][0]["scan"]["detect_tree"][0][
                "filetype"
            ],
            "Binary",
        )
        for name, case in cases.items():
            qt5_case = self.qt5["cases"][name]["oracles"][
                "linux-qt5-cmake"
            ]
            execution = case["qt6_executions"][0]
            self.assertEqual(
                execution["scan"]["detect_tree"],
                qt5_case["scan"]["detect_tree"],
            )
            self.assertEqual(
                execution["detector_info"]["filetype"],
                qt5_case["detector_info"]["filetype"],
            )
            self.assertEqual(
                case["comparison"],
                {
                    "raw_stream_differences": [],
                    "semantic_dispatch_equal": True,
                },
            )
        self.assertEqual(self.report["known_differences"], [])
        self.assertTrue(all(self.report["relationships"].values()))

    def test_document_binds_qt6_report(self):
        document = DOCUMENT_PATH.read_text(encoding="utf-8")
        self.assertIn(REPORT_PATH.name, document)
        self.assertIn(sha256(self.report_bytes), document)
        self.assertIn("CAP-DISPATCH-003", document)
        self.assertIn("Qt6", document)


if __name__ == "__main__":
    unittest.main()
