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
    ROOT / "tools" / "upstream" / "probe_qt6_path_boundaries.py"
)
REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "path-boundaries-linux-qt5-qt6.json"
)
DOCUMENT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "qt6-path-boundary-runtime-evidence.md"
)
BASELINES = {
    "special_path": "special-path-engine-qt5.json",
    "filesystem": "path-filesystem-engine-qt5.json",
    "large_directory": "large-path-engine-qt5.json",
    "toctou": "path-toctou-engine-qt5.json",
    "locale_filesystem": "path-locale-filesystem-engine-qt5.json",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_probe():
    spec = importlib.util.spec_from_file_location(
        "_test_qt6_path_boundaries",
        PROBE_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Qt6 path boundary probe")
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


class Qt6PathBoundaryProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report_bytes = REPORT_PATH.read_bytes()
        cls.report = json.loads(cls.report_bytes)

    def test_report_identity_and_all_baselines_are_exact(self):
        report = self.report
        self.assertEqual(
            sha256(self.report_bytes),
            "8dbe49bdd2be73a06950e3a9a36dc07b5c65debfdf62428a50a8425b2c296e76",
        )
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["capability"], "CAP-CLI-IN-003")
        self.assertEqual(
            report["upstream_commit"],
            PROBE.UPSTREAM_COMMIT,
        )
        self.assertEqual(report["generator_sha256"], sha256(PROBE_PATH.read_bytes()))
        self.assertTrue(report["passed"])
        self.assertEqual(report["failures"], [])
        self.assertEqual(report["suite_order"], list(BASELINES))
        self.assertEqual(set(report["suites"]), set(BASELINES))
        for suite_id, baseline_name in BASELINES.items():
            baseline_path = REPORT_PATH.parent / baseline_name
            comparison = report["suites"][suite_id]["comparison"]
            self.assertEqual(
                comparison["qt5_report_path"],
                f"docs/research/data/{baseline_name}",
            )
            self.assertEqual(
                comparison["qt5_report_sha256"],
                sha256(baseline_path.read_bytes()),
            )
            self.assertTrue(comparison["behavior_projection_equal"])

    def test_qt6_oracle_identity_and_repetitions_are_exact(self):
        for suite in self.report["suites"].values():
            qt6 = suite["qt6"]
            self.assertEqual(qt6["platform"], "linux-x86_64-qt6")
            self.assertEqual(
                qt6["qt6_oracle"]["id"],
                "sha256:e015495c313d0715f0b80f395da983a113a439f2a135eb637e9f0638c225200b",
            )
            self.assertEqual(
                qt6["qt6_binary"]["sha256"],
                "e3321105af0349b29195325e79d5d2c7cc25ead2f28f84e242e3835b98f7283e",
            )
            self.assertTrue(
                qt6["facts"]["qt6_repetitions_are_byte_equal"]
            )
            for reference in artifact_references(qt6):
                self.assertEqual(
                    reference["artifact_sha256"],
                    reference["sha256"],
                )

    def test_every_raw_artifact_reconstructs_and_is_referenced(self):
        for suite_id, suite in self.report["suites"].items():
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
                for reference in artifact_references(qt6)
            }
            with self.subTest(suite=suite_id):
                self.assertEqual(references, set(artifacts))

    def test_full_named_path_boundary_is_present(self):
        suites = self.report["suites"]
        self.assertEqual(len(suites["special_path"]["qt6"]["cases"]), 23)
        filesystem = suites["filesystem"]["qt6"]["cases"]
        self.assertEqual(len(filesystem), 9)
        self.assertEqual(
            filesystem["self_cycle"]["summary"]["pdf_root_count"],
            41,
        )
        large = suites["large_directory"]["qt6"]["cases"]
        self.assertEqual(len(large), 5)
        self.assertEqual(large["flat_4096"]["prefix_count"], 4096)
        self.assertEqual(
            large["nested_4096"]["entropy_document_count"],
            4096,
        )
        toctou = suites["toctou"]["qt6"]["cases"]
        self.assertEqual(len(toctou), 4)
        self.assertEqual(
            toctou["swap_old_to_new"]["stdout_sha256"],
            toctou["stable_new"]["stdout_sha256"],
        )
        self.assertNotEqual(
            toctou["swap_old_to_new"]["stdout_sha256"],
            toctou["stable_old"]["stdout_sha256"],
        )
        locale = suites["locale_filesystem"]["qt6"]["matrix"]
        self.assertEqual(len(locale), 6)
        self.assertFalse(
            suites["locale_filesystem"]["qt6"][
                "output_equivalence"
            ]["filesystem_stdout_byte_equal_within_locale"]
        )

    def test_driver_is_a_bounded_replay_not_a_probe_reimplementation(self):
        source = PROBE_PATH.read_text(encoding="utf-8")
        for module in (
            "probe_special_path_behavior.py",
            "probe_path_filesystem_behavior.py",
            "probe_large_path_behavior.py",
            "probe_path_toctou_behavior.py",
            "probe_path_locale_filesystem_behavior.py",
        ):
            self.assertIn(module, source)
        self.assertIn("module.ORACLES =", source)
        self.assertIn("behavior_projection(raw_qt6)", source)
        self.assertIn("COMPARISON_VOLATILE_FIELDS", source)
        self.assertNotIn("subprocess.run(", source)

    def test_document_binds_report_hash_and_scope(self):
        document = DOCUMENT_PATH.read_text(encoding="utf-8")
        self.assertIn(REPORT_PATH.name, document)
        self.assertIn(sha256(self.report_bytes), document)
        for token in (
            "CAP-CLI-IN-003",
            "23",
            "4096",
            "TOCTOU",
            "tmpfs",
            "volume",
            "device",
            "inode",
        ):
            self.assertIn(token, document)


if __name__ == "__main__":
    unittest.main()
