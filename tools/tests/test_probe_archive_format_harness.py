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
    / "archive-format-engine-qt5.json"
)
MANIFEST_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "archive-format-corpus.json"
)
PROBE_PATH = (
    ROOT / "tools" / "upstream" / "probe_archive_format_harness.py"
)
DOCUMENT_PATH = (
    ROOT / "docs" / "research" / "archive-format-behavior.md"
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ArchiveFormatHarnessProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report_bytes = REPORT_PATH.read_bytes()
        cls.report = json.loads(cls.report_bytes)

    def test_report_identity_and_scope_are_exact(self):
        report = self.report
        self.assertEqual(
            sha256(self.report_bytes),
            "acc82f0f3ed7bd63bb2214158b6a263165863dadba53cf1ded6f7b76abdca53e",
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
        self.assertEqual(report["remaining_gap"], "CAP-GAP-006")
        self.assertTrue(report["passed"])
        self.assertEqual(report["failures"], [])

    def test_fixture_and_local_sources_are_hash_bound(self):
        report = self.report
        self.assertEqual(
            report["fixture_manifest"],
            {
                "path": "docs/research/data/archive-format-corpus.json",
                "sample_count": 8,
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
            },
        )
        for source in report["local_sources"].values():
            with self.subTest(source=source["path"]):
                self.assertEqual(
                    source["sha256"],
                    sha256((ROOT / source["path"]).read_bytes()),
                )

    def test_oracle_image_binaries_and_sources_are_exact(self):
        report = self.report
        self.assertEqual(
            report["image"],
            {
                "id": (
                    "sha256:771b9094a2ad6ab4f6250dd89307ab727c07a1aae"
                    "885a894695abfa959bab5dc"
                ),
                "name": "diec-rust/upstream-archive-harness:74eaf505",
                "repo_digests": [
                    "diec-rust/upstream-archive-harness@sha256:"
                    "771b9094a2ad6ab4f6250dd89307ab727c07a1aae"
                    "885a894695abfa959bab5dc"
                ],
                "revision": "74eaf505c250ab47e709024e9dc41657cd8f2254",
            },
        )
        self.assertEqual(
            report["binaries"],
            {
                "harness": {
                    "path": (
                        "/opt/die-build/src/console/"
                        "diec-archive-harness"
                    ),
                    "sha256": (
                        "b7ea9b151b58b630c017e9989333fa035b7d86ffa"
                        "b366a5d3a1f74bab9f1e96e"
                    ),
                    "size": 8233888,
                },
                "release": {
                    "path": "/opt/die-build/src/console/diec",
                    "sha256": (
                        "da1fab49f7ba5970d1fc1c7fe3d4f380cf5e8775"
                        "dd8097207e7b3c30f08236cf"
                    ),
                    "size": 8248008,
                },
            },
        )
        expected_sources = {
            "cab": "a0ce130f4d81ba3aeb018e485a3ee8c046d4cbb570d6318f7aa8817aff28035b",
            "engine": "e088bebb7c8345ce5832cc51de712c05a8b239873d7f092db3ae5566a761b498",
            "iso9660": "d6e97c4ff2395b812b65da5ab480e937c6b365e6e6e8b0288ddf48b8fd398fb1",
            "rar": "23721187a6118edce8b9511680f34c404727f831ec8c7ed66e0ed0868260ccb8",
            "sevenzip": "d8da44bdcd1dfab07f1403ae19a0113238fd54620ef9b4307410097d7d8e5554",
            "sevenzip_methods": "d8da44bdcd1dfab07f1403ae19a0113238fd54620ef9b4307410097d7d8e5554",
        }
        self.assertEqual(
            {
                name: source["sha256"]
                for name, source in report["source_contract"].items()
            },
            expected_sources,
        )
        self.assertTrue(
            all(
                source["required_pattern_count"] >= 1
                for source in report["source_contract"].values()
            )
        )

    def test_raw_artifacts_reconstruct_every_execution(self):
        report = self.report
        artifacts = report["raw_artifacts"]
        self.assertEqual(len(artifacts), 17)
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
        for sample in report["cases"].values():
            for case in sample.values():
                for stream in ("stdout", "stderr"):
                    reference = case[stream]
                    artifact = artifacts[reference["artifact_sha256"]]
                    self.assertEqual(
                        reference["sha256"],
                        reference["artifact_sha256"],
                    )
                    self.assertEqual(reference["bytes"], artifact["bytes"])

    def test_modes_preserve_exact_roots_and_unpack_one_pdf(self):
        expected_roots = {
            "pdf-member.7z": ("Binary", ["7-Zip"]),
            "pdf-member-bzip2.7z": ("Binary", ["7-Zip"]),
            "pdf-member-deflate.7z": ("Binary", ["7-Zip"]),
            "pdf-member-lzma.7z": ("Binary", ["7-Zip"]),
            "pdf-member-lzma2.7z": ("Binary", ["7-Zip"]),
            "pdf-member.cab": ("Binary", ["CAB"]),
            "pdf-member.iso": ("ISO 9660", ["Unknown"]),
            "pdf-member.rar": ("RAR", ["Unknown"]),
        }
        for sample_name, (filetype, names) in expected_roots.items():
            cases = self.report["cases"][sample_name]
            self.assertEqual(
                set(cases),
                {
                    "archive",
                    "archive_aggressive",
                    "default",
                    "release_default",
                },
            )
            for mode, case in cases.items():
                with self.subTest(sample=sample_name, mode=mode):
                    summary = case["summary"]
                    self.assertEqual(summary["root_filetype"], filetype)
                    self.assertEqual(
                        summary["root_detection_names"],
                        names,
                    )
                    if mode in {"default", "release_default"}:
                        self.assertEqual(summary["stream_count"], 0)
                    else:
                        self.assertEqual(summary["stream_count"], 1)
                        self.assertEqual(
                            summary["stream_filetypes"],
                            ["PDF"],
                        )
                        self.assertEqual(
                            summary["stream_detection_names"],
                            ["PDF", "HeaderComment"],
                        )
                        self.assertEqual(
                            summary["stream_sizes"],
                            ["331"],
                        )
            self.assertEqual(
                cases["default"]["stdout"],
                cases["release_default"]["stdout"],
            )
            self.assertEqual(
                cases["archive"]["stdout"],
                cases["archive_aggressive"]["stdout"],
            )

    def test_limits_facts_and_document_are_explicit(self):
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
        self.assertTrue(all(self.report["facts"].values()))
        document = DOCUMENT_PATH.read_text(encoding="utf-8")
        for fact in self.report["facts"]:
            self.assertIn(fact, document)
        self.assertIn("CAP-GAP-006", document)
        self.assertIn("archive-format-engine-qt5.json", document)
        self.assertIn(
            "acc82f0f3ed7bd63bb2214158b6a263165863dadba53cf1ded6f7b76abdca53e",
            document,
        )


if __name__ == "__main__":
    unittest.main()
