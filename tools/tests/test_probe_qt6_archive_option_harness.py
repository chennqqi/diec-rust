import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT / "tools" / "upstream" / "probe_qt6_archive_option_harness.py"
)
UNDERLYING_PATH = (
    ROOT / "tools" / "upstream" / "probe_archive_harness.py"
)
REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "archive-option-engine-qt5-qt6.json"
)
REPORT_SHA256 = (
    "5cdadeb09d97a0afd03b2f73ebbb5eb4ffd227b9a21973d34d5a3db739bb8d65"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_qt6_archive_option_harness",
    MODULE_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ProbeQt6ArchiveOptionHarnessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = REPORT_PATH.read_bytes()
        cls.report = json.loads(cls.raw)

    def test_report_probe_and_oracle_identities_are_fixed(self):
        self.assertEqual(
            hashlib.sha256(self.raw).hexdigest(),
            REPORT_SHA256,
        )
        self.assertEqual(self.report["generator"], MODULE.GENERATOR)
        self.assertEqual(
            self.report["generator_sha256"],
            hashlib.sha256(MODULE_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            self.report["underlying_probe"],
            {
                "path": MODULE.UNDERLYING_PROBE,
                "sha256": hashlib.sha256(
                    UNDERLYING_PATH.read_bytes()
                ).hexdigest(),
            },
        )
        self.assertEqual(self.report["oracles"], {
            name: {
                "harness": {
                    "image": oracle["harness_image"],
                    "image_id": oracle["harness_image_id"],
                    "revision": MODULE.UPSTREAM_COMMIT,
                    "binary": MODULE.HARNESS_BINARY,
                    "binary_sha256": oracle[
                        "harness_binary_sha256"
                    ],
                },
                "release": {
                    "image": oracle["release_image"],
                    "image_id": oracle["release_image_id"],
                    "revision": MODULE.UPSTREAM_COMMIT,
                    "binary": MODULE.RELEASE_BINARY,
                    "binary_sha256": oracle[
                        "release_binary_sha256"
                    ],
                },
            }
            for name, oracle in MODULE.ORACLES.items()
        })

    def test_content_addressed_raw_catalog_is_complete(self):
        raw_streams = self.report["raw_streams"]
        for stream_hash, item in raw_streams.items():
            stream = base64.b64decode(item["base64"], validate=True)
            self.assertEqual(len(stream), item["bytes"])
            self.assertEqual(
                hashlib.sha256(stream).hexdigest(),
                stream_hash,
            )

        trees = self.report["detection_trees"]
        for tree_hash, tree in trees.items():
            encoded = json.dumps(
                tree,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
            self.assertEqual(
                hashlib.sha256(encoded).hexdigest(),
                tree_hash,
            )

        observation_count = 0
        for sample_cases in self.report["cases"].values():
            for case in sample_cases.values():
                groups = [case["observations"]]
                if "release_control" in case:
                    groups.append(
                        case["release_control"]["observations"]
                    )
                for group in groups:
                    for observation in group.values():
                        observation_count += 1
                        self.assertIn(
                            observation["stdout_sha256"],
                            raw_streams,
                        )
                        self.assertIn(
                            observation["stderr_sha256"],
                            raw_streams,
                        )
                        self.assertIn(
                            observation["detect_tree_sha256"],
                            trees,
                        )
        self.assertEqual(observation_count, 192)

    def test_engine_only_archive_option_contract_matches_qt5(self):
        self.assertEqual(self.report["case_count"], 64)
        self.assertEqual(self.report["release_control_count"], 32)
        self.assertEqual(len(self.report["relationships"]), 11)
        self.assertTrue(all(self.report["relationships"].values()))
        for sample_name, sample_cases in self.report["cases"].items():
            expected_qt6_stderr = (
                hashlib.sha256(MODULE.QT6_WARNING).hexdigest()
                if sample_name.startswith("pe-")
                else hashlib.sha256(b"").hexdigest()
            )
            for case_name, case in sample_cases.items():
                with self.subTest(
                    sample=sample_name,
                    case=case_name,
                ):
                    qt5 = case["observations"]["qt5"]
                    qt6 = case["observations"]["qt6"]
                    self.assertEqual(
                        qt5["stdout_sha256"],
                        qt6["stdout_sha256"],
                    )
                    self.assertEqual(
                        qt5["detect_tree_sha256"],
                        qt6["detect_tree_sha256"],
                    )
                    self.assertEqual(
                        qt5["stderr_sha256"],
                        hashlib.sha256(b"").hexdigest(),
                    )
                    self.assertEqual(
                        qt6["stderr_sha256"],
                        expected_qt6_stderr,
                    )
                    if "release_control" in case:
                        release = case["release_control"][
                            "observations"
                        ]
                        for oracle_name in ("qt5", "qt6"):
                            self.assertEqual(
                                release[oracle_name]["stdout_sha256"],
                                case["observations"][oracle_name][
                                    "stdout_sha256"
                                ],
                            )
                            self.assertEqual(
                                release[oracle_name]["stderr_sha256"],
                                case["observations"][oracle_name][
                                    "stderr_sha256"
                                ],
                            )

    def test_known_warning_and_scope_limits_are_explicit(self):
        self.assertEqual(
            self.report["known_difference"],
            {
                "scope": "Qt6 PE rule runtime warning",
                "affected_samples": [
                    "pe-manifest-resource.exe",
                    "pe-many-pdf-resources.exe",
                    "pe-pdf-overlay.exe",
                    "pe-pdf-resource.exe",
                    "pe-zip-overlay.exe",
                ],
                "harness_invocations": 40,
                "release_invocations": 20,
                "stderr_bytes_per_invocation": 80,
                "stderr_sha256_per_invocation": (
                    "b303e6913e76b70a6f0d6a4d3ccd389b"
                    "c342589e45e1615873a37334dea8c51b"
                ),
                "lines_per_invocation": 4,
                "all_stdout_equal": True,
            },
        )
        limitations = "\n".join(self.report["limitations"])
        self.assertIn("do not close the 100000", limitations)
        self.assertIn("separate limit harness", limitations)


if __name__ == "__main__":
    unittest.main()
