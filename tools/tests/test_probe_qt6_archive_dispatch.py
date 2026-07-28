import base64
import hashlib
import importlib.util
import json
import pathlib
import sys
import unittest
import zlib


ROOT = pathlib.Path(__file__).resolve().parents[2]
PROBE_PATH = (
    ROOT / "tools" / "upstream" / "probe_qt6_archive_dispatch.py"
)
REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "archive-dispatch-linux-qt5-qt6.json"
)
PUBLIC_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "cli-output-matrix-linux-qt5-qt6.json"
)
ARCHIVE_GAP_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "archive-gap-closure.json"
)
DOCUMENT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "qt6-archive-dispatch-runtime-evidence.md"
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_probe():
    spec = importlib.util.spec_from_file_location(
        "_test_qt6_archive_dispatch",
        PROBE_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Qt6 archive dispatch probe")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


PROBE = load_probe()


def artifact_references(value):
    if isinstance(value, dict):
        if set(value) >= {"artifact_sha256", "bytes", "sha256"}:
            yield value
        for child in value.values():
            yield from artifact_references(child)
    elif isinstance(value, list):
        for child in value:
            yield from artifact_references(child)


class Qt6ArchiveDispatchProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report_bytes = REPORT_PATH.read_bytes()
        cls.report = json.loads(cls.report_bytes)

    def test_report_identity_and_closed_scope_are_exact(self):
        report = self.report
        self.assertEqual(
            sha256(self.report_bytes),
            "7f4492a0ab48714d5654f5d244266de822c2268c766a2eb75a9de066cc1cb52b",
        )
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["capability"], "CAP-DISPATCH-004")
        self.assertEqual(report["upstream_commit"], PROBE.UPSTREAM_COMMIT)
        self.assertEqual(report["generator_sha256"], sha256(PROBE_PATH.read_bytes()))
        self.assertEqual(report["failures"], [])
        self.assertTrue(report["passed"])
        self.assertEqual(report["named_members"], list(PROBE.NAMED_MEMBERS))
        self.assertTrue(all(report["facts"].values()))
        self.assertEqual(
            report["public_dispatch"]["report_sha256"],
            sha256(PUBLIC_PATH.read_bytes()),
        )
        self.assertEqual(
            report["archive_gap_reference"]["report_sha256"],
            sha256(ARCHIVE_GAP_PATH.read_bytes()),
        )

    def test_public_dispatch_and_generic_controls_are_exact(self):
        cases = self.report["public_dispatch"]["cases"]
        self.assertEqual(set(cases), set(PROBE.PUBLIC_CASES))
        for name, expected_filetype in PROBE.PUBLIC_CASES.items():
            case = cases[name]
            self.assertEqual(case["qt5"], case["qt6"])
            self.assertEqual(len(case["detect_tree"]), 1)
            self.assertEqual(
                case["detect_tree"][0]["filetype"],
                expected_filetype,
            )
        self.assertEqual(
            self.report["archive_gap_reference"][
                "engine_extraction_families"
            ],
            ["ZIP", "7Z", "RAR", "CAB", "ISO9660"],
        )

    def test_private_qt6_oracle_identity_and_source_bindings(self):
        expected = {
            "npm": {
                "image": (
                    "sha256:8c6311d4740eb15055cb8bf474b1c3c36ede78fe9f2293ce5673b86c12957f64"
                ),
                "harness": (
                    "b623930bca7301706edad4ab66ebef4718012d112015da7a1b2dae76ea70416f"
                ),
                "projection": (
                    "ca5a01ab0178e877089e0a584f8f3649da48dd4ae49dfb49c0bf314592073911"
                ),
            },
            "generic_archive": {
                "image": (
                    "sha256:384844c09790b019a388381ed8beee2f160e6d3bd405f19b88cea9b87662095f"
                ),
                "harness": (
                    "0969dd12914d20964b2d60d660e904f7706c1b4857f66314589386cddf615be7"
                ),
                "projection": (
                    "ff2d7f5810f766e629486eeb35f91ca8c2c9b8699bb97524b417e4343b672da6"
                ),
            },
        }
        for suite_id, identity in expected.items():
            suite = self.report["private_suites"][suite_id]
            qt6 = suite["qt6"]
            self.assertTrue(
                suite["comparison"]["behavior_projection_equal"]
            )
            self.assertEqual(
                suite["comparison"]["behavior_projection_sha256"],
                identity["projection"],
            )
            self.assertEqual(qt6["qt6_image"]["id"], identity["image"])
            self.assertEqual(
                qt6["qt6_binaries"]["harness"]["sha256"],
                identity["harness"],
            )
            self.assertEqual(
                qt6["qt6_binaries"]["release"]["sha256"],
                "e3321105af0349b29195325e79d5d2c7cc25ead2f28f84e242e3835b98f7283e",
            )
            dockerfile = qt6["local_sources"]["harness_dockerfile"]
            path = ROOT / dockerfile["path"]
            self.assertEqual(dockerfile["sha256"], sha256(path.read_bytes()))

    def test_private_branch_semantics_match_qt5(self):
        npm = self.report["private_suites"]["npm"]["qt6"]["cases"]
        self.assertEqual(len(npm), 4)
        self.assertTrue(npm["npm-valid.tgz"]["harness"]["output"]["direct_npm_valid"])
        self.assertTrue(
            npm["npm-invalid-json.tgz"]["harness"]["output"][
                "direct_npm_valid"
            ]
        )
        for name in ("root-package-json.tgz", "case-package-json.tgz"):
            self.assertFalse(
                npm[name]["harness"]["output"]["direct_npm_valid"]
            )
        for case in npm.values():
            output = case["harness"]["output"]
            self.assertEqual(output["automatic"]["initial_filetype"], "Binary")
            self.assertEqual(output["forced_npm"]["initial_filetype"], "NPM")
            self.assertEqual(
                case["release_repetition_1"],
                case["release_repetition_2"],
            )

        generic = self.report["private_suites"]["generic_archive"][
            "qt6"
        ]["cases"]
        self.assertEqual(set(generic), {"payload.zip", "payload.tar", "payload.txt.gz"})
        for case in generic.values():
            output = case["harness"]["output"]
            self.assertNotEqual(
                output["automatic_quiet"]["initial_filetype"],
                "Archive",
            )
            self.assertEqual(
                output["forced_archive_quiet"]["records"][0]["name"],
                "Unknown",
            )
            self.assertNotEqual(
                output["forced_archive_verbose"]["records"][0]["name"],
                "Unknown",
            )
            self.assertEqual(
                case["release_repetition_1_quiet"],
                case["release_repetition_2_quiet"],
            )
            self.assertEqual(
                case["release_repetition_1_verbose"],
                case["release_repetition_2_verbose"],
            )

    def test_all_private_raw_artifacts_reconstruct_and_are_referenced(self):
        for suite_id, suite in self.report["private_suites"].items():
            qt6 = suite["qt6"]
            artifacts = qt6["raw_artifacts"]
            for digest, artifact in artifacts.items():
                compressed = base64.b64decode(
                    artifact["base64"],
                    validate=True,
                )
                raw = zlib.decompress(compressed)
                self.assertEqual(len(raw), artifact["bytes"])
                self.assertEqual(sha256(raw), digest)
            references = {
                reference["artifact_sha256"]
                for reference in artifact_references(qt6["cases"])
            }
            with self.subTest(suite=suite_id):
                self.assertEqual(references, set(artifacts))

    def test_driver_reuses_pinned_probes_and_document_binds_report(self):
        source = PROBE_PATH.read_text(encoding="utf-8")
        self.assertIn("probe_npm_dispatch_harness.py", source)
        self.assertIn(
            "probe_generic_archive_dispatch_harness.py",
            source,
        )
        self.assertIn("module.HARNESS_IMAGE =", source)
        self.assertNotIn("subprocess.run(", source)
        document = DOCUMENT_PATH.read_text(encoding="utf-8")
        self.assertIn(REPORT_PATH.name, document)
        self.assertIn(sha256(self.report_bytes), document)
        for token in (
            "CAP-DISPATCH-004",
            "NPM",
            "generic Archive",
            "APK",
            "IPA",
            "JAR",
            "ISO9660",
        ):
            self.assertIn(token, document)


if __name__ == "__main__":
    unittest.main()
