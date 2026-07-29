import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = ROOT / "docs/research/data/xucl-origin.json"
TOOL_PATH = ROOT / "tools/upstream/audit_xucl_origin.py"
LOCK_PATH = ROOT / "upstream/components.lock.toml"
PRIOR_PATH = (
    ROOT / "docs/research/data/product-source-closure-linux-qt5.json"
)
SPEC = importlib.util.spec_from_file_location(
    "audit_xucl_origin", TOOL_PATH
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class XuclOriginTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    def test_report_is_bound_to_generator_lock_prior_and_image(self):
        report = self.report
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(
            report["generator"],
            "tools/upstream/audit_xucl_origin.py",
        )
        self.assertEqual(
            report["generator_sha256"],
            hashlib.sha256(TOOL_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            report["component_lock"]["sha256"],
            hashlib.sha256(LOCK_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            report["prior_product_source_closure"]["sha256"],
            hashlib.sha256(PRIOR_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(report["upstream_commit"], MODULE.UPSTREAM_COMMIT)
        self.assertEqual(report["xarchive_commit"], MODULE.XARCHIVE_COMMIT)
        self.assertEqual(
            report["source_image"]["revision"], MODULE.UPSTREAM_COMMIT
        )
        self.assertEqual(report["source_image"]["network"], "none")
        self.assertEqual(
            report["source_image"]["repository_mount"], "readonly"
        )
        self.assertEqual(
            report["source_image"]["official_archive_mount"], "readonly"
        )

    def test_official_release_and_license_evidence_are_exact(self):
        release = self.report["official_release"]
        self.assertEqual(
            release,
            {
                "archive_bytes": 534881,
                "archive_root": "ucl-1.03",
                "archive_sha1": MODULE.OFFICIAL_ARCHIVE_SHA1,
                "archive_sha256": MODULE.OFFICIAL_ARCHIVE_SHA256,
                "archive_url": MODULE.OFFICIAL_ARCHIVE_URL,
                "copyright_holder":
                    "Markus Franz Xaver Johannes Oberhumer",
                "indexed_source_file_count": 62,
                "name": "UCL",
                "regular_file_count": 622,
                "release_page": MODULE.OFFICIAL_RELEASE_PAGE,
                "released_on": "2004-07-20",
                "version": "1.03",
            },
        )
        evidence = {
            record["path"]: record
            for record in self.report["official_license_evidence"]
        }
        self.assertEqual(set(evidence), {"README", "COPYING", "acc/ACC_LICENSE"})
        self.assertEqual(
            evidence["COPYING"]["sha256"],
            "70439f6e2b47057a408d2390ed6663b9875f5a08066a06a060a357ef1df89a8c",
        )
        self.assertEqual(
            evidence["acc/ACC_LICENSE"], evidence["COPYING"] | {
                "path": "acc/ACC_LICENSE"
            }
        )

    def test_embedded_identity_and_shingle_coverage_are_exact(self):
        self.assertTrue(all(self.report["relationships"].values()))
        self.assertEqual(
            self.report["embedded_files"],
            [
                {
                    "bytes": 129921,
                    "path": "Algos/xucldecoder.cpp",
                    "sha256":
                        "f2f2fe4e11beaa122c2474a44c7c1c97242e9d211eacc15d0c7f3c646b2a45cf",
                },
                {
                    "bytes": 86349,
                    "path": "Algos/xucldecoder_acc.h",
                    "sha256":
                        "f53d934a8efdb4f1b483e7fddf5ffe749d6914a2830bbaf7d68428b91fecc669",
                },
            ],
        )
        combined = self.report["combined_shingle_evidence"]
        self.assertEqual(
            [
                (
                    item["shingle_length"],
                    item["embedded_token_count"],
                    item["covered_token_count"],
                    item["coverage"],
                    item["unique_origin_file_count"],
                )
                for item in combined
            ],
            [
                (12, 36567, 34652, 0.9476303771159789, 35),
                (64, 36567, 32575, 0.8908305302595236, 30),
            ],
        )
        per_file = self.report["per_file_shingle_evidence"]
        self.assertEqual(
            [item["coverage"] for item in per_file["Algos/xucldecoder.cpp"]],
            [0.9330023761031908, 0.8537423625254582],
        )
        self.assertEqual(
            [
                item["coverage"]
                for item in per_file["Algos/xucldecoder_acc.h"]
            ],
            [0.9741518578352181, 0.9580736979767674],
        )

    def test_license_classification_remains_fail_closed(self):
        classification = self.report["license_classification"]
        self.assertEqual(
            classification["technical_spdx_expression"],
            "GPL-2.0-or-later",
        )
        self.assertFalse(classification["copy_or_translation_approved"])
        self.assertFalse(classification["legal_review_complete"])
        self.assertFalse(
            classification[
                "special_or_commercial_license_evidence_in_xarchive"
            ]
        )
        self.assertIn(
            "do not copy or translate XUCL into Rust before release/legal "
            "review resolves the upstream MIT/GPL combination",
            self.report["distribution_requirements"],
        )

    def test_report_has_no_container_or_workspace_paths(self):
        serialized = REPORT_PATH.read_text(encoding="utf-8")
        self.assertNotIn("/opt/die-source", serialized)
        self.assertNotIn("/input/ucl-1.03.tar.gz", serialized)
        self.assertNotIn(str(ROOT), serialized)

    def test_tokenizer_and_archive_reader_are_fail_closed(self):
        self.assertEqual(
            MODULE.tokenize_c(b"/* ignored */ int x = 1; // ignored\nx++;"),
            ["int", "x", "=", "1", ";", "x", "++", ";"],
        )
        evidence = MODULE.shingle_evidence(
            ["a", "b", "c"], {"one.c": b"a b c"}, 2
        )
        self.assertEqual(evidence["covered_token_count"], 3)
        self.assertEqual(evidence["unique_origin_file_count"], 1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unsafe.tar.gz"
            with tarfile.open(path, "w:gz") as archive:
                info = tarfile.TarInfo("../escape")
                payload = b"unsafe"
                info.size = len(payload)
                archive.addfile(info, io.BytesIO(payload))
            with self.assertRaisesRegex(
                ValueError, "unsafe official archive member"
            ):
                MODULE.read_archive(path)


if __name__ == "__main__":
    unittest.main()
