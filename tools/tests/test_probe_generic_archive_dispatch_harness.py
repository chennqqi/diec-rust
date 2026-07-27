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
    ROOT
    / "tools"
    / "upstream"
    / "probe_generic_archive_dispatch_harness.py"
)
REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "generic-archive-dispatch-engine-qt5.json"
)
MANIFEST_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "generic-archive-dispatch-fixture.json"
)
DOCUMENT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "generic-archive-dispatch-reachability.md"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_generic_archive_dispatch_harness",
    PROBE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


class ProbeGenericArchiveDispatchHarnessTests(unittest.TestCase):
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
            "960fca28122af3bddb2fcd22706f5350ee8f4753a79a61cc2338aba7d1f53c04",
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
                "path": (
                    "docs/research/data/"
                    "generic-archive-dispatch-fixture.json"
                ),
                "sample_count": 3,
                "sha256": sha256(MANIFEST_PATH.read_bytes()),
            },
        )
        self.assertEqual(
            set(report["local_sources"]),
            {
                "baseline_generator",
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
            "sha256:8676a288d390aa2b806997fd6c32550ac3ffa6a837386faf9636acb3d092555c",
        )
        self.assertEqual(
            report["images"]["release_qmake"]["id"],
            "sha256:cc5561a5d256c7912227a8ecf4ba9c6b9178c99911e471017d3c3988bac964ab",
        )
        self.assertEqual(
            {
                name: (binary["sha256"], binary["size"])
                for name, binary in report["binaries"].items()
            },
            {
                "harness": (
                    "387ad8e6f3b64e027798fd04c384f2bcbbca6860274da4704cdabd3028735621",
                    8238504,
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
                "archive_rule": (
                    "97202e19118514bcd33ef40c2dea69822249406092eddcb61f56e3410278ec86"
                ),
                "binary_archive_rule": (
                    "b148ae0ba8e64f58f5285c16b0812dd014cb6230550bf9df9bdc290387802255"
                ),
                "formats": (
                    "674eba0046eb6cc947e547d1ac0b93ac695cbb30f68e11f135e5551d81e0b115"
                ),
                "scan_engine": (
                    "e088bebb7c8345ce5832cc51de712c05a8b239873d7f092db3ae5566a761b498"
                ),
                "script_engine": (
                    "f9b9d69a17dc930556c7308fce46d3287d18dd9f927c91d6733ce994594fcb72"
                ),
                "zip_rule": (
                    "0c35cbe87bfa82bbeb5d5880ae4ebec9e1d48b7dadad04cfc8eee365d776e7a7"
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
        self.assertEqual(len(artifacts), 8)
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
            self.assertEqual(len(sample), 5)
            for execution in sample.values():
                for stream in ("stdout", "stderr"):
                    reference = execution[stream]
                    artifact = artifacts[reference["artifact_sha256"]]
                    self.assertEqual(
                        reference["sha256"],
                        reference["artifact_sha256"],
                    )
                    self.assertEqual(reference["bytes"], artifact["bytes"])

    def test_automatic_and_forced_archive_layers_are_distinct(self):
        for name, case in self.report["cases"].items():
            with self.subTest(sample=name):
                output = case["harness"]["output"]
                expected = MODULE.EXPECTED[name]
                for mode in (
                    "automatic_quiet",
                    "automatic_verbose",
                ):
                    scan = output[mode]
                    self.assertEqual(
                        scan["detected_filetypes"],
                        expected["detected"],
                    )
                    self.assertEqual(
                        scan["initial_filetype"],
                        expected["initial"],
                    )
                    self.assertNotEqual(
                        scan["initial_filetype"],
                        "Archive",
                    )
                quiet = output["forced_archive_quiet"]
                self.assertEqual(quiet["detected_filetypes"], "ARCHIVE")
                self.assertEqual(quiet["initial_filetype"], "Archive")
                self.assertTrue(quiet["records"][0]["unknown"])
                verbose = output["forced_archive_verbose"]
                self.assertEqual(
                    verbose["records"][0]["name"],
                    expected["forced_name"],
                )
                self.assertEqual(
                    verbose["records"][0]["signature"],
                    "_Archive.0.sg",
                )

    def test_both_release_builds_match_each_automatic_mode(self):
        for name, case in self.report["cases"].items():
            output = case["harness"]["output"]
            for release_mode, harness_mode in (
                ("quiet", "automatic_quiet"),
                ("verbose", "automatic_verbose"),
            ):
                with self.subTest(sample=name, mode=release_mode):
                    cmake = case[f"cmake_release_{release_mode}"]
                    qmake = case[f"qmake_release_{release_mode}"]
                    self.assertEqual(cmake["stdout"], qmake["stdout"])
                    self.assertEqual(cmake["stderr"], qmake["stderr"])
                    self.assertEqual(
                        cmake["summary"]["filetype"],
                        output[harness_mode]["initial_filetype"],
                    )
                    self.assertEqual(
                        cmake["summary"]["names"],
                        [
                            record["name"]
                            for record in output[harness_mode]["records"]
                        ],
                    )

    def test_validation_rejects_public_and_forced_drift(self):
        sample = self.samples["payload.tar"]
        document = copy.deepcopy(
            self.report["cases"]["payload.tar"]["harness"]["output"]
        )
        document["automatic_quiet"]["initial_filetype"] = "Archive"
        with self.assertRaisesRegex(
            MODULE.ProbeError,
            "automatic Archive",
        ):
            MODULE.validate_harness(document, sample)

        sample = self.samples["payload.txt.gz"]
        document = copy.deepcopy(
            self.report["cases"]["payload.txt.gz"]["harness"]["output"]
        )
        document["forced_archive_verbose"]["records"][0][
            "name"
        ] = "ZIP"
        with self.assertRaisesRegex(
            MODULE.ProbeError,
            "forced verbose Archive",
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
        self.assertIn(
            'buffer.setProperty("filetypes", "ARCHIVE")',
            source,
        )
        document = DOCUMENT_PATH.read_text(encoding="utf-8")
        for fact in self.report["facts"]:
            self.assertIn(fact, document)
        self.assertIn("CAP-GAP-006", document)
        self.assertIn(
            "generic-archive-dispatch-engine-qt5.json",
            document,
        )
        self.assertIn(
            "960fca28122af3bddb2fcd22706f5350ee8f4753a79a61cc2338aba7d1f53c04",
            document,
        )


if __name__ == "__main__":
    unittest.main()
