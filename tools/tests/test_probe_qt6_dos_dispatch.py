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
    / "dos-dispatch-linux-qt5-qt6.json"
)
QT5_REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "dos-dispatch-linux-qt5.json"
)
MANIFEST_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "dos-dispatch-corpus.json"
)
SOURCE_AUDIT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "dos-dispatch-source-audit.json"
)
PROBE_PATH = (
    ROOT / "tools" / "upstream" / "probe_qt6_dos_dispatch.py"
)
SHARED_PATH = (
    ROOT / "tools" / "upstream" / "probe_qt6_legacy_dispatch.py"
)
DOCUMENT_PATH = (
    ROOT / "docs" / "research" / "dos-dispatch-reachability.md"
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_probe():
    spec = importlib.util.spec_from_file_location(
        "_test_qt6_dos_dispatch",
        PROBE_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Qt6 DOS dispatch probe")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


PROBE = load_probe()


class Qt6DosDispatchProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report_bytes = REPORT_PATH.read_bytes()
        cls.report = json.loads(cls.report_bytes)
        cls.qt5 = json.loads(QT5_REPORT_PATH.read_bytes())

    def test_report_identity_and_inputs_are_exact(self):
        report = self.report
        self.assertEqual(
            sha256(self.report_bytes),
            "cb65823f885ce96b1356f6d9f657b7fba735891996009289f533060398c544f9",
        )
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["result"], "pass")
        self.assertEqual(report["failures"], [])
        self.assertEqual(report["capability"], "CAP-DISPATCH-002")
        self.assertEqual(report["repetitions"], 2)
        self.assertEqual(
            report["generator_sha256"],
            sha256(PROBE_PATH.read_bytes()),
        )
        self.assertEqual(
            report["shared_probe_sha256"],
            sha256(SHARED_PATH.read_bytes()),
        )
        self.assertEqual(
            report["corpus_manifest"]["sha256"],
            sha256(MANIFEST_PATH.read_bytes()),
        )
        self.assertEqual(report["corpus_manifest"]["sample_count"], 19)
        self.assertEqual(
            report["source_audit"]["sha256"],
            sha256(SOURCE_AUDIT_PATH.read_bytes()),
        )
        self.assertEqual(
            report["qt5_reference"]["sha256"],
            sha256(QT5_REPORT_PATH.read_bytes()),
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
                "/opt/die-source/Formats/xbinary.cpp": (
                    "d82bd21326bb7ba07eb343020d50af0ae2cf7e8e534d8e08d07ffa8129913c34"
                ),
                "/opt/die-source/Formats/xformats.cpp": (
                    "674eba0046eb6cc947e547d1ac0b93ac695cbb30f68e11f135e5551d81e0b115"
                ),
                "/opt/die-source/XScanEngine/xscanengine.cpp": (
                    "e088bebb7c8345ce5832cc51de712c05a8b239873d7f092db3ae5566a761b498"
                ),
            },
        )

    def test_raw_artifacts_reconstruct_every_reference(self):
        artifacts = self.report["raw_artifacts"]
        self.assertEqual(len(artifacts), 43)
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
            self.assertEqual(len(case["qt6_executions"]), 2)
            for execution in case["qt6_executions"]:
                self.assertEqual(execution["exit_code"], 0)
                for stream in ("stdout", "stderr", "diagnostics"):
                    reference = execution[stream]
                    self.assertEqual(
                        reference["sha256"],
                        reference["artifact_sha256"],
                    )
                    self.assertIn(reference["sha256"], artifacts)

    def test_public_dispatch_semantics_match_qt5(self):
        positives = {
            "minimal-msdos.exe": "MSDOS",
            "minimal-ne.exe": "NE",
            "minimal-le.exe": "LE",
            "minimal-lx.exe": "LX",
            "minimal-dos16m.exe": "DOS/16M",
            "minimal-dos4g.exe": "DOS/4G",
            "minimal.com": "COM",
        }
        cases = self.report["cases"]
        self.assertEqual(set(cases), set(self.qt5["cases"]))
        for name, case in cases.items():
            execution = case["qt6_executions"][0]
            qt5_case = self.qt5["cases"][name]["oracles"][
                "linux-qt5-cmake"
            ]
            self.assertEqual(
                execution["detect_tree"],
                qt5_case["detect_tree"],
            )
            if name in positives:
                self.assertIn(
                    positives[name],
                    PROBE.BASE.SHARED.observed_filetypes(
                        execution["detect_tree"]
                    ),
                )
        self.assertIn(
            "DOS/16M",
            PROBE.BASE.SHARED.observed_filetypes(
                cases["dos4g-near-nested-magic.exe"][
                    "qt6_executions"
                ][0]["detect_tree"]
            ),
        )
        self.assertNotIn(
            "COM",
            PROBE.BASE.SHARED.observed_filetypes(
                cases["com-oversized.com"]["qt6_executions"][0][
                    "detect_tree"
                ]
            ),
        )

    def test_formatter_and_diagnostics_differences_are_exact(self):
        differences = {
            item["case"]: item
            for item in self.report["known_differences"]
        }
        self.assertEqual(set(differences), set(self.report["cases"]))
        diagnostic_cases = {
            "minimal-msdos.exe",
            "ne-truncated.exe",
            "ne-near-magic.exe",
            "le-near-magic.exe",
            "lx-near-magic.exe",
            "dos16m-truncated.exe",
            "dos16m-near-bw.exe",
            "dos4g-truncated.exe",
        }
        for name, item in differences.items():
            self.assertIn("stdout_json_fields", item["streams"])
            self.assertEqual(len(item["qt6_formatter_extras"]), 3)
            if name in diagnostic_cases:
                self.assertIn(
                    "stdout_diagnostics",
                    item["streams"],
                )
                self.assertEqual(
                    item[
                        "normalized_stdout_diagnostics_sha256"
                    ],
                    "c6656b6859b2ae4f2f9db8bdddfa7129587757ec933bc89de232c84daade95c1",
                )
                self.assertIn(
                    "MSDOS_Script(0x<address>)",
                    item["normalized_stdout_diagnostics"],
                )
            else:
                self.assertEqual(
                    item["streams"],
                    ["stdout_json_fields"],
                )
                self.assertEqual(
                    item[
                        "normalized_stdout_diagnostics_sha256"
                    ],
                    sha256(b""),
                )
            for execution in self.report["cases"][name][
                "qt6_executions"
            ]:
                self.assertEqual(
                    execution["stderr"]["sha256"],
                    sha256(b""),
                )
        self.assertTrue(all(self.report["relationships"].values()))

    def test_document_binds_report_and_classified_differences(self):
        document = DOCUMENT_PATH.read_text(encoding="utf-8")
        self.assertIn(REPORT_PATH.name, document)
        self.assertIn(sha256(self.report_bytes), document)
        self.assertIn("CAP-DISPATCH-002", document)
        self.assertIn("c6656b6859b2", document)


if __name__ == "__main__":
    unittest.main()
