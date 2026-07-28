import base64
import hashlib
import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
REPORT_PATH = (
    ROOT / "docs/research/data/rar-compressed-engine-qt5.json"
)
TOOL_PATH = (
    ROOT / "tools/upstream/probe_rar_compressed_harness.py"
)
FIXTURE_REPORT_PATH = (
    ROOT / "docs/research/data/rar-compressed-fixture-source.json"
)


class RarCompressedEngineOracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    def test_report_identity_is_fixed(self):
        self.assertEqual(self.report["schema_version"], 1)
        self.assertEqual(
            self.report["generator"],
            "tools/upstream/probe_rar_compressed_harness.py",
        )
        self.assertEqual(
            self.report["generator_sha256"],
            hashlib.sha256(TOOL_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            self.report["upstream_commit"],
            "74eaf505c250ab47e709024e9dc41657cd8f2254",
        )
        self.assertEqual(
            self.report["fixture_source_commit"],
            "16b785c2b1b504e99fc307676e5369a26d3ce060",
        )
        self.assertEqual(
            self.report["fixture_report"]["sha256"],
            hashlib.sha256(FIXTURE_REPORT_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            self.report["source_image"]["image_id"],
            "sha256:adf8e09f3ed7c15a54f3486c482599e1bcb122"
            "308a0b27396de1baf2ee634daf",
        )
        self.assertTrue(all(self.report["relationships"].values()))

    def test_harness_and_rar_source_chain_are_content_bound(self):
        self.assertEqual(
            self.report["harness"]["binary"]["sha256"],
            "b7ea9b151b58b630c017e9989333fa035b7d86ff"
            "ab366a5d3a1f74bab9f1e96e",
        )
        source_hashes = {
            item["path"]: item["sha256"]
            for item in self.report["source_files"]
        }
        self.assertEqual(
            source_hashes[
                "/opt/die-source/XArchive/Algos/xrardecoder.cpp"
            ],
            "55f36d7b0188f5093ffad5723637fedafae32321"
            "b1fde3cf2f81ff5983e94026",
        )
        self.assertEqual(
            source_hashes[
                "/opt/die-source/XArchive/Algos/xrardecoder.h"
            ],
            "29e0f4e1091df88f992f2cf5688df044bfbb46e"
            "607cb6536cbd5b4e234665540",
        )
        self.assertEqual(len(source_hashes), 5)

    def test_case_matrix_and_output_hashes_are_exact(self):
        cases = {
            (case["id"], case["mode"]): case
            for case in self.report["cases"]
        }
        self.assertEqual(len(cases), 8)
        expected = {
            ("rar3_method35_single", "default"): (
                "8f184c8747b5d98db429a743595b5a74993f83f6"
                "e03bd0e81fe9ca37f6ca3fe2",
                [],
            ),
            ("rar3_method35_single", "aggressive"): (
                "27486f764197d26383c4d0ca92f02a317237e948"
                "2b67919a12bf54ae2a080f2a",
                [("Binary", 12)],
            ),
            ("rar3_method35_solid_pair", "default"): (
                "d1888c473d52f56da929da6df69650a84b768a34"
                "7d55f04796d81af8a26fb81f",
                [],
            ),
            ("rar3_method35_solid_pair", "aggressive"): (
                "4b5cf406d105898744ea16d11c4545861b9266e0"
                "126fd73e28daa08f14990d68",
                [("PNG", 87), ("JPEG", 220)],
            ),
            ("rar5_method5_mixed_pair", "default"): (
                "e88cecf96eb86fdd6de21db6d15f2420ccf06749"
                "66d24e3893526dac5baa79b8",
                [],
            ),
            ("rar5_method5_mixed_pair", "aggressive"): (
                "f63f75f9f34dc48bdfcc5edd86c802fb8d546309"
                "46e070930350622e8b6148f2",
                [("JPEG", 220), ("PNG", 87)],
            ),
            ("rar5_method5_solid_pair", "default"): (
                "f3e44f6d785f35c4818823d8845070d621e7dcce"
                "0c6a9acdd3c2f454683e0e5b",
                [],
            ),
            ("rar5_method5_solid_pair", "aggressive"): (
                "e4d9bd95dfe54243c383da98910c9349b1c15002"
                "392c9cd1b6e92cf2902be50c",
                [("JPEG", 220), ("PNG", 87)],
            ),
        }
        for key, (stdout_hash, children) in expected.items():
            case = cases[key]
            self.assertEqual(len(case["runs"]), 2)
            self.assertEqual(
                {run["stdout_sha256"] for run in case["runs"]},
                {stdout_hash},
            )
            self.assertEqual(
                [
                    (child["filetype"], child["size"])
                    for child in case["runs"][0]["projection"][
                        "children"
                    ]
                ],
                children,
            )

    def test_raw_outputs_are_retained_and_hash_valid(self):
        for case in self.report["cases"]:
            first = case["runs"][0]
            for run in case["runs"]:
                raw = base64.b64decode(run["stdout_base64"])
                self.assertEqual(
                    hashlib.sha256(raw).hexdigest(),
                    run["stdout_sha256"],
                )
                self.assertEqual(
                    run["stdout_base64"], first["stdout_base64"]
                )
                self.assertEqual(run["stderr_base64"], "")


if __name__ == "__main__":
    unittest.main()
