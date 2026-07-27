import base64
import copy
import hashlib
import importlib.util
import json
import pathlib
import sys
import unittest
import zlib


ROOT = pathlib.Path(__file__).resolve().parents[2]
PROBE_PATH = (
    ROOT / "tools" / "upstream" / "probe_npm_dispatch_harness.py"
)
REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "npm-dispatch-engine-qt5.json"
)
MANIFEST_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "npm-dispatch-fixture.json"
)
DOCUMENT_PATH = (
    ROOT / "docs" / "research" / "npm-dispatch-reachability.md"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_npm_dispatch_harness",
    PROBE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


class ProbeNpmDispatchHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report_bytes = REPORT_PATH.read_bytes()
        cls.report = json.loads(cls.report_bytes)
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        cls.samples = {
            sample["name"]: sample
            for sample in cls.manifest["samples"]
        }

    def test_report_identity_and_scope_are_exact(self):
        report = self.report
        self.assertEqual(
            sha256(self.report_bytes),
            "d23168aff29696f46d3579f6d914353865035bd02a8bbbcf9af065475c036ce7",
        )
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["upstream_commit"], MODULE.UPSTREAM_COMMIT)
        self.assertEqual(report["platform"], "linux-x86_64-qt5")
        self.assertEqual(
            report["generator_sha256"],
            sha256(PROBE_PATH.read_bytes()),
        )
        self.assertEqual(report["remaining_gap"], "CAP-GAP-006")
        self.assertTrue(report["passed"])
        self.assertEqual(report["failures"], [])

    def test_fixture_and_local_sources_are_hash_bound(self):
        report = self.report
        self.assertEqual(
            report["fixture_manifest"],
            {
                "path": "docs/research/data/npm-dispatch-fixture.json",
                "sample_count": 4,
                "sha256": sha256(MANIFEST_PATH.read_bytes()),
            },
        )
        self.assertEqual(
            set(report["local_sources"]),
            {
                "fixture_generator",
                "harness_dockerfile",
                "harness_source",
                "probe",
            },
        )
        for source in report["local_sources"].values():
            with self.subTest(source=source["path"]):
                self.assertEqual(
                    source["sha256"],
                    sha256((ROOT / source["path"]).read_bytes()),
                )

    def test_oracle_images_binaries_components_and_sources_are_exact(self):
        report = self.report
        self.assertEqual(report["component_commits"], MODULE.COMPONENT_COMMITS)
        self.assertEqual(
            report["images"]["harness_cmake"]["id"],
            "sha256:714270cf7bf3e3428c854ff63457754132e55c90a8a6ae9061b6cbdec9c1ca77",
        )
        self.assertEqual(
            report["images"]["release_qmake"]["id"],
            "sha256:cc5561a5d256c7912227a8ecf4ba9c6b9178c99911e471017d3c3988bac964ab",
        )
        self.assertEqual(
            {
                name: (
                    binary["sha256"],
                    binary["size"],
                )
                for name, binary in report["binaries"].items()
            },
            {
                "harness": (
                    "0cc39eba0761eaaecaa22a25cf486ac2cad728deb94debee3b8f62921e7c5671",
                    8238488,
                ),
                "release_cmake": (
                    "da1fab49f7ba5970d1fc1c7fe3d4f380cf5e8775dd8097207e7b3c30f08236cf",
                    8248008,
                ),
                "release_qmake": (
                    "721ec846507a8567aae07e91dcd1f576182481ae0dc1595b1f19e4a3e859b79d",
                    7684384,
                ),
            },
        )
        self.assertEqual(
            {
                name: source["sha256"]
                for name, source in report["source_contract"].items()
            },
            {
                "formats": (
                    "674eba0046eb6cc947e547d1ac0b93ac695cbb30f68e11f135e5551d81e0b115"
                ),
                "npm": (
                    "7ef5f9cdf7c50a047802cd25d2b71a919a5a50ca9f6fcbbeb2bc1cb9b7441b91"
                ),
                "npm_format_rule": (
                    "dfddb12106e7e5e659340bc63b85e80ac336d5434368e1ef248025c15f2c3e24"
                ),
                "npm_javascript_rule": (
                    "ea5c8c8980e3228a36d537745abf691145460f6e42de0198e919c7ec8ba8aafd"
                ),
                "npm_package_rule": (
                    "0aeb63c01b0132d733565b79c7b678cd8f099d9280ff1f5082e4c91c9da36e5a"
                ),
                "npm_typescript_rule": (
                    "69b2ab4d8c1a654d7b43f602c8993b79bdbeeec561f3b49e5605d5977251e976"
                ),
                "scan_engine": (
                    "e088bebb7c8345ce5832cc51de712c05a8b239873d7f092db3ae5566a761b498"
                ),
                "script_engine": (
                    "f9b9d69a17dc930556c7308fce46d3287d18dd9f927c91d6733ce994594fcb72"
                ),
            },
        )
        for source in report["source_contract"].values():
            self.assertTrue(
                all(
                    pattern["count"] >= 1
                    for pattern in source["required_patterns"]
                )
            )

    def test_raw_artifacts_reconstruct_every_execution(self):
        artifacts = self.report["raw_artifacts"]
        self.assertEqual(len(artifacts), 6)
        for digest, artifact in artifacts.items():
            with self.subTest(digest=digest):
                self.assertEqual(artifact["encoding"], "zlib+base64")
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
        for sample in self.report["cases"].values():
            for execution in sample.values():
                for stream in ("stdout", "stderr"):
                    reference = execution[stream]
                    artifact = artifacts[reference["artifact_sha256"]]
                    self.assertEqual(
                        reference["sha256"],
                        reference["artifact_sha256"],
                    )
                    self.assertEqual(reference["bytes"], artifact["bytes"])

    def test_detector_dispatch_and_forced_rule_layers_are_distinct(self):
        cases = self.report["cases"]
        self.assertEqual(set(cases), set(self.samples))
        for name, case in cases.items():
            with self.subTest(sample=name):
                output = case["harness"]["output"]
                self.assertEqual(
                    output["direct_npm_valid"],
                    self.samples[name]["expected_npm"],
                )
                self.assertEqual(
                    output["automatic"]["detected_filetypes"],
                    "BINARY|ARCHIVE|GZIP",
                )
                self.assertEqual(
                    output["automatic"]["initial_filetype"],
                    "Binary",
                )
                self.assertEqual(
                    output["automatic"]["records"][0]["name"],
                    "Unknown",
                )
                self.assertEqual(
                    output["forced_npm"]["detected_filetypes"],
                    "NPM",
                )
                self.assertEqual(
                    output["forced_npm"]["initial_filetype"],
                    "NPM",
                )
                self.assertEqual(
                    [
                        (record["name"], record["signature"])
                        for record in output["forced_npm"]["records"]
                    ],
                    MODULE.EXPECTED_FORCED_RECORDS[name],
                )
                self.assertEqual(
                    case["cmake_release"]["stdout"],
                    case["qmake_release"]["stdout"],
                )
                self.assertEqual(
                    case["cmake_release"]["summary"],
                    {
                        "filetype": "Binary",
                        "names": ["Unknown"],
                        "offset": "0",
                        "parentfilepart": "Header",
                        "size": "3095",
                    },
                )

    def test_validation_rejects_false_positive_and_public_npm_drift(self):
        sample = self.samples["root-package-json.tgz"]
        document = copy.deepcopy(
            self.report["cases"]["root-package-json.tgz"]["harness"][
                "output"
            ]
        )
        document["direct_npm_valid"] = True
        with self.assertRaisesRegex(
            MODULE.ProbeError,
            "direct NPM detector",
        ):
            MODULE.validate_harness(document, sample)

        sample = self.samples["npm-valid.tgz"]
        document = copy.deepcopy(
            self.report["cases"]["npm-valid.tgz"]["harness"]["output"]
        )
        document["automatic"]["initial_filetype"] = "NPM"
        with self.assertRaisesRegex(
            MODULE.ProbeError,
            "automatic NPM dispatch",
        ):
            MODULE.validate_harness(document, sample)

    def test_facts_limits_harness_and_document_are_explicit(self):
        self.assertTrue(all(self.report["facts"].values()))
        self.assertEqual(
            self.report["resource_limits"],
            {
                "container_root": "read-only",
                "cpus": 1,
                "fixture_mount": "read-only",
                "memory_bytes": 536870912,
                "network": "none",
                "pids": 128,
                "timeout_seconds_per_execution": 60,
            },
        )
        source = (ROOT / MODULE.HARNESS_SOURCE).read_text(
            encoding="utf-8"
        )
        self.assertEqual(source.count('setProperty("filetypes"'), 1)
        self.assertIn('buffer.setProperty("filetypes", "NPM")', source)
        document = DOCUMENT_PATH.read_text(encoding="utf-8")
        for fact in self.report["facts"]:
            self.assertIn(fact, document)
        self.assertIn("CAP-GAP-006", document)
        self.assertIn("npm-dispatch-engine-qt5.json", document)
        self.assertIn(
            "d23168aff29696f46d3579f6d914353865035bd02a8bbbcf9af065475c036ce7",
            document,
        )


if __name__ == "__main__":
    unittest.main()
