import base64
import hashlib
import json
import pathlib
import unittest
import zlib


ROOT = pathlib.Path(__file__).resolve().parents[2]
REPORT_PATH = (
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
    ROOT / "tools" / "upstream" / "probe_scan_option_boundaries.py"
)
DOCUMENT_PATH = ROOT / "docs" / "research" / "scan-option-boundaries.md"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ScanOptionBoundaryProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report_bytes = REPORT_PATH.read_bytes()
        cls.report = json.loads(cls.report_bytes)

    def test_report_identity_and_fixture_are_exact(self):
        report = self.report
        self.assertEqual(
            sha256(self.report_bytes),
            "f193a9f308b04a89dd7ceeda52a658eda2ef13eb82b9c0662c66215248bbf49d",
        )
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(
            report["upstream_commit"],
            "74eaf505c250ab47e709024e9dc41657cd8f2254",
        )
        self.assertEqual(report["platform"], "linux-x86_64-qt5")
        self.assertEqual(
            report["generator_sha256"],
            sha256(PROBE_PATH.read_bytes()),
        )
        self.assertEqual(
            report["fixture_manifest"]["sha256"],
            sha256(MANIFEST_PATH.read_bytes()),
        )
        self.assertEqual(report["fixture_manifest"]["entry_count"], 9)
        self.assertEqual(report["closed_corpus_gap"], "CAP-GAP-005")
        self.assertTrue(report["passed"])
        self.assertEqual(report["failures"], [])

    def test_local_sources_and_limits_are_bound(self):
        report = self.report
        self.assertEqual(
            report["resource_limits"],
            {
                "container_root": "read-only",
                "cpus": 1,
                "fixture_mount": "read-only",
                "memory_bytes": 536870912,
                "network": "none",
                "pids": 128,
                "timeout_seconds_per_execution": 180,
            },
        )
        for source in report["local_sources"].values():
            data = (ROOT / source["path"]).read_bytes()
            self.assertEqual(source["sha256"], sha256(data))

    def test_oracle_images_binaries_and_sources_are_exact(self):
        observations = self.report["observations"]
        expected = {
            "linux-qt5-qmake": (
                "sha256:cc5561a5d256c7912227a8ecf4ba9c6b9178c99911e471017d3c3988bac964ab",
                "721ec846507a8567aae07e91dcd1f576182481ae0dc1595b1f19e4a3e859b79d",
            ),
            "linux-qt5-cmake": (
                "sha256:466102628c3a94b7ab1048f0c24261b1920e61a40029b128763cf79370255040",
                "da1fab49f7ba5970d1fc1c7fe3d4f380cf5e8775dd8097207e7b3c30f08236cf",
            ),
        }
        self.assertEqual(set(observations), set(expected))
        for name, (image_id, binary_sha256) in expected.items():
            oracle = observations[name]
            self.assertEqual(oracle["image_id"], image_id)
            self.assertEqual(oracle["binary_sha256"], binary_sha256)
            self.assertEqual(
                oracle["resource_source_sha256"],
                "e088bebb7c8345ce5832cc51de712c05a8b239873d7f092db3ae5566a761b498",
            )
            self.assertEqual(
                oracle["pe_source_sha256"],
                "bfad885df2569b03bc33c040852a884bfe40d781a58bef5f6d8c53c16b488a0c",
            )
            self.assertEqual(
                oracle["console_source_sha256"],
                "ebb82a94fdd0f54722ea36589d6a35694ec4022bc9179030dae6a85e7a9d7e8f",
            )

    def test_raw_artifacts_reconstruct_every_execution(self):
        artifacts = self.report["raw_artifacts"]
        self.assertEqual(len(artifacts), 8)
        for digest, artifact in artifacts.items():
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
        observations = list(self.report["observations"].values())
        for case_name in observations[0]["cases"]:
            for stream_name in ("stdout", "stderr"):
                left = observations[0]["cases"][case_name][stream_name]
                right = observations[1]["cases"][case_name][stream_name]
                self.assertEqual(left, right)
                artifact = artifacts[left["artifact_sha256"]]
                self.assertEqual(left["bytes"], artifact["bytes"])
                self.assertEqual(left["sha256"], left["artifact_sha256"])

    def test_deep_and_aggressive_relations_are_exact(self):
        cases = self.report["observations"]["linux-qt5-qmake"]["cases"]
        self.assertEqual(
            cases["deep_default"]["summary"]["detection_names"],
            ["Binary normal"],
        )
        self.assertEqual(
            cases["deep_enabled"]["summary"]["detection_names"],
            ["Binary normal", "Binary deep", "Binary entrypoint"],
        )
        for name in (
            "aggressive_without_recursive",
            "recursive_unclassified",
        ):
            self.assertEqual(cases[name]["summary"]["resource_count"], 0)
        self.assertEqual(
            cases["recursive_aggressive_unclassified"]["summary"][
                "resource_count"
            ],
            1,
        )

    def test_resource_count_boundaries_and_order_are_exact(self):
        cases = self.report["observations"]["linux-qt5-qmake"]["cases"]
        expected = {
            "recursive_pdf_22": 21,
            "recursive_aggressive_pdf_22": 22,
            "recursive_aggressive_unclassified_2002": 2001,
        }
        for name, count in expected.items():
            summary = cases[name]["summary"]
            self.assertEqual(summary["resource_count"], count)
            self.assertTrue(
                summary["resource_offsets_strictly_increasing"]
            )
        self.assertEqual(
            cases["recursive_pdf_22"]["summary"]["resource_sizes"],
            [331],
        )
        self.assertEqual(
            cases["recursive_aggressive_unclassified_2002"]["summary"][
                "resource_sizes"
            ],
            [1],
        )

    def test_source_audit_and_document_cover_all_facts(self):
        audit = self.report["source_audit"]
        self.assertEqual(
            audit["required_pattern_counts"]["resource"],
            {
                "aggressive_gate": 2,
                "aggressive_limit": 1,
                "default_limit": 2,
                "file_part_enumeration_limit": 1,
                "inclusive_limit": 1,
                "scanable_gate": 2,
            },
        )
        self.assertTrue(all(self.report["facts"].values()))
        document = DOCUMENT_PATH.read_text(encoding="utf-8")
        for fact in self.report["facts"]:
            self.assertIn(fact, document)
        self.assertIn("CAP-GAP-005", document)
        self.assertIn(
            "scan-option-boundaries-linux-qt5.json",
            document,
        )
        self.assertIn(
            "f193a9f308b04a89dd7ceeda52a658eda2ef13eb82b9c0662c66215248bbf49d",
            document,
        )


if __name__ == "__main__":
    unittest.main()
