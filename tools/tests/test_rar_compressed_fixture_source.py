import hashlib
import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
REPORT_PATH = (
    ROOT / "docs/research/data/rar-compressed-fixture-source.json"
)
TOOL_PATH = (
    ROOT / "tools/corpus/audit_rar_compressed_fixture_source.py"
)


class RarCompressedFixtureSourceReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    def test_report_identity_and_relationships_are_fixed(self):
        self.assertEqual(self.report["schema_version"], 1)
        self.assertEqual(
            self.report["generator"],
            "tools/corpus/audit_rar_compressed_fixture_source.py",
        )
        self.assertEqual(
            self.report["generator_sha256"],
            hashlib.sha256(TOOL_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            self.report["source"]["commit"],
            "16b785c2b1b504e99fc307676e5369a26d3ce060",
        )
        self.assertEqual(
            self.report["source"]["remote"],
            "https://github.com/ssokolow/rar-test-files.git",
        )
        self.assertTrue(all(self.report["relationships"].values()))

    def test_selected_sample_hashes_are_exact(self):
        samples = {
            sample["path"]: sample
            for sample in self.report["selection"]["samples"]
        }
        self.assertEqual(
            {
                path: (sample["bytes"], sample["sha256"])
                for path, sample in samples.items()
            },
            {
                "build/testfile.rar3.rar": (
                    98,
                    "dce342bc0c2852fcaa36a03da5e55abb"
                    "7dd69c045bbd812faebebc1a3844f5a4",
                ),
                "build/testfile.rar3.solid.cbr": (
                    381,
                    "610376cfa11ec11bf55cd117f5d5b83dd"
                    "11dded6aad2f825b41dbe84d7f3098d",
                ),
                "build/testfile.rar5.cbr": (
                    410,
                    "e8b106048f18e6fb9a5f8ec6a95346e"
                    "76906e7e4e9ca15ec97e4f926159cb398",
                ),
                "build/testfile.rar5.solid.cbr": (
                    407,
                    "23ef370c58b7646d527106829410700ac"
                    "314d86380b9c968a37066f39fe6c70b",
                ),
            },
        )
        self.assertTrue(
            self.report["selection"]["external_storage"]
        )
        self.assertFalse(
            self.report["selection"]["binary_files_committed_to_project"]
        )

    def test_parsed_method_and_solid_matrix_is_exact(self):
        actual = {}
        for sample in self.report["selection"]["samples"]:
            actual[sample["path"]] = {
                "format": sample["format"],
                "archive_solid": sample["archive_solid"],
                "members": [
                    (
                        member["name"],
                        member["packed_size"],
                        member["unpacked_size"],
                        member["method"],
                        member["solid"],
                    )
                    for member in sample["members"]
                ],
            }
        self.assertEqual(
            actual,
            {
                "build/testfile.rar3.rar": {
                    "format": "RAR3",
                    "archive_solid": False,
                    "members": [
                        ("testfile.txt", 27, 12, 0x35, False)
                    ],
                },
                "build/testfile.rar3.solid.cbr": {
                    "format": "RAR3",
                    "archive_solid": True,
                    "members": [
                        ("testfile.png", 84, 87, 0x35, False),
                        ("testfile.jpg", 182, 220, 0x35, True),
                    ],
                },
                "build/testfile.rar5.cbr": {
                    "format": "RAR5",
                    "archive_solid": False,
                    "members": [
                        ("testfile.jpg", 214, 220, 5, False),
                        ("testfile.png", 87, 87, 0, False),
                    ],
                },
                "build/testfile.rar5.solid.cbr": {
                    "format": "RAR5",
                    "archive_solid": True,
                    "members": [
                        ("testfile.jpg", 236, 220, 5, False),
                        ("testfile.png", 62, 87, 5, True),
                    ],
                },
            },
        )

    def test_redistribution_is_not_silently_approved(self):
        review = self.report["redistribution_review"]
        self.assertTrue(review["creator_license_claim_present"])
        self.assertTrue(review["creator_purchase_evidence_present"])
        self.assertTrue(review["creator_owned_content_cc0"])
        self.assertFalse(review["project_legal_review_complete"])
        self.assertFalse(review["project_redistribution_approved"])


if __name__ == "__main__":
    unittest.main()
