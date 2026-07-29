import collections
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = (
    ROOT / "docs/research/data/xsimd-license-closure-linux.json"
)
TOOL_PATH = ROOT / "tools/upstream/audit_xsimd_license_closure.py"
LOCK_PATH = ROOT / "upstream/components.lock.toml"
SPEC = importlib.util.spec_from_file_location(
    "audit_xsimd_license_closure", TOOL_PATH
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class XsimdLicenseClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(
            REPORT_PATH.read_text(encoding="utf-8")
        )

    def test_report_is_bound_to_generator_lock_component_and_image(self):
        report = self.report
        lock = tomllib.loads(LOCK_PATH.read_text(encoding="utf-8"))
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(
            report["generator"],
            "tools/upstream/audit_xsimd_license_closure.py",
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
            report["upstream_commit"], MODULE.UPSTREAM_COMMIT
        )
        self.assertEqual(
            report["formats_commit"],
            lock["gitlink"]["Formats"]["commit"],
        )
        self.assertEqual(
            report["source_image"]["revision"],
            MODULE.UPSTREAM_COMMIT,
        )
        self.assertEqual(report["source_image"]["network"], "none")
        self.assertEqual(
            report["source_image"]["repository_mount"], "readonly"
        )

    def test_all_three_archive_members_contribute_to_final_elf(self):
        report = self.report
        self.assertTrue(all(report["relationships"].values()))
        self.assertEqual(report["build"]["archive_count"], 3)
        self.assertEqual(
            report["build"]["extracted_archive_member_count"], 3
        )
        self.assertEqual(
            set(report["build"]["linked_archives"]),
            set(MODULE.ARCHIVES),
        )
        self.assertEqual(len(report["archives"]), 3)
        expected_archive_hashes = {
            "../XSIMD/libxsimd.a": (
                "191e4d13d5b522459f77df9f492d7d9a"
                "6a146c603d7a5c3acc97e8e117e1a77b"
            ),
            "../XSIMD/libxsimd_avx2.a": (
                "03b5de490217c929903691b545d13922a"
                "ba4903c7b5491d46bf29f884d572e9e"
            ),
            "../XSIMD/libxsimd_sse2.a": (
                "eab901e6c823ab49dc86ad4d744348cf"
                "5a92f1732e084eee102bde897e273a15"
            ),
        }
        for record in report["archives"]:
            self.assertEqual(
                record["member"],
                MODULE.ARCHIVES[record["archive"]]["member"],
            )
            self.assertTrue(record["extracted_into_final_elf"])
            self.assertTrue(record["final_elf_symbol_witnesses"])
            self.assertEqual(
                record["archive_sha256"],
                expected_archive_hashes[record["archive"]],
            )

    def test_compile_and_dependency_closure_is_exact(self):
        report = self.report
        self.assertEqual(report["compile_source_count"], 3)
        self.assertEqual(report["closure_file_count"], 6)
        self.assertEqual(len(report["compile_units"]), 3)
        self.assertEqual(
            {unit["source"] for unit in report["compile_units"]},
            {
                "xsimd/src/xsimd.c",
                "xsimd/src/xsimd_avx2.c",
                "xsimd/src/xsimd_sse2.c",
            },
        )
        linkage_counts = collections.Counter(
            unit["linkage"] for unit in report["compile_units"]
        )
        self.assertEqual(
            linkage_counts,
            collections.Counter({token: 1 for token in MODULE.ARCHIVES}),
        )
        paths = {record["path"] for record in report["files"]}
        self.assertEqual(
            paths,
            {
                "xsimd/src/xsimd.c",
                "xsimd/src/xsimd.h",
                "xsimd/src/xsimd_avx2.c",
                "xsimd/src/xsimd_avx2.h",
                "xsimd/src/xsimd_sse2.c",
                "xsimd/src/xsimd_sse2.h",
            },
        )
        self.assertNotIn("xsimd/src/xsimd_cuda.cu", paths)
        self.assertNotIn("xsimd/src/xsimd_cuda.h", paths)

    def test_license_markers_and_retained_text_are_exact(self):
        self.assertEqual(
            self.report["marker_counts"],
            {"hors-copyright": 6, "mit-permission": 6},
        )
        for record in self.report["files"]:
            self.assertEqual(
                record["license_markers"],
                ["hors-copyright", "mit-permission"],
            )
            self.assertRegex(record["sha256"], r"^[0-9a-f]{64}$")
        evidence = self.report["license_evidence_files"]
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]["path"], "LICENSE")
        self.assertEqual(
            evidence[0]["license_markers"],
            ["hors-copyright", "mit-permission"],
        )
        self.assertEqual(
            evidence[0]["sha256"],
            (
                "5f1133d595966880a5c4af69f448d5cc"
                "6ebbad6989033bb2f8c2c874e861c5ca"
            ),
        )
        self.assertEqual(len(self.report["distribution_requirements"]), 1)

    def test_report_has_no_container_or_workspace_paths(self):
        serialized = REPORT_PATH.read_text(encoding="utf-8")
        self.assertNotIn("/opt/die-source", serialized)
        self.assertNotIn("/opt/die-build", serialized)
        self.assertNotIn(str(ROOT), serialized)

    def test_dependency_and_nm_parsers_are_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.o.d"
            path.write_text(
                "sample.o: /src/sample.c \\\n /src/sample.h\n",
                encoding="utf-8",
            )
            self.assertEqual(
                MODULE.parse_dependency_file(path),
                [Path("/src/sample.c"), Path("/src/sample.h")],
            )
        self.assertEqual(
            MODULE.parse_nm_defined_symbols(
                "00000000 T alpha\n"
                "         U external\n"
                "00000010 t local_symbol\n"
            ),
            {"alpha"},
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.o.d"
            path.write_text("no dependency separator")
            with self.assertRaisesRegex(
                ValueError, "invalid dependency file"
            ):
                MODULE.parse_dependency_file(path)


if __name__ == "__main__":
    unittest.main()
