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
    ROOT
    / "docs/research/data/product-source-closure-linux-qt5.json"
)
TOOL_PATH = ROOT / "tools/upstream/audit_product_source_closure.py"
LOCK_PATH = ROOT / "upstream/components.lock.toml"
SPEC = importlib.util.spec_from_file_location(
    "audit_product_source_closure", TOOL_PATH
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ProductSourceClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(
            REPORT_PATH.read_text(encoding="utf-8")
        )

    def test_report_is_bound_to_generator_lock_image_and_priors(self):
        report = self.report
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(
            report["generator"],
            "tools/upstream/audit_product_source_closure.py",
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
            report["source_image"]["revision"],
            MODULE.UPSTREAM_COMMIT,
        )
        self.assertEqual(report["source_image"]["network"], "none")
        self.assertEqual(
            report["source_image"]["repository_mount"], "readonly"
        )
        self.assertEqual(
            set(report["prior_reports"]), set(MODULE.PRIOR_REPORTS)
        )
        for name, relative in MODULE.PRIOR_REPORTS.items():
            record = report["prior_reports"][name]
            self.assertEqual(record["path"], relative)
            self.assertEqual(
                record["sha256"],
                hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(),
            )

    def test_product_link_and_compile_source_counts_are_exact(self):
        report = self.report
        self.assertTrue(all(report["relationships"].values()))
        build = report["build"]
        self.assertEqual(build["direct_object_count"], 223)
        self.assertEqual(build["project_archive_count"], 8)
        self.assertEqual(
            build["built_project_archive_member_count"], 36
        )
        self.assertEqual(
            build["included_project_archive_member_count"], 14
        )
        self.assertEqual(
            build["excluded_project_archive_member_count"], 22
        )
        self.assertEqual(build["compile_source_count"], 237)
        self.assertEqual(
            build["artifact_sha256"],
            build["replayed_artifact_sha256"],
        )
        self.assertEqual(
            build["link_map_sha256"],
            (
                "9cdf167d355b6d0aad4d04c100a3602f"
                "9aa90139f78ac47be517b2518bf8f566"
            ),
        )
        self.assertEqual(
            report["direct_object_counts"],
            {
                "components": MODULE.EXPECTED_COMPONENT_DIRECT_COUNTS,
                "root": 2,
                "generated": 1,
            },
        )
        self.assertEqual(
            report["compile_source_counts"],
            MODULE.EXPECTED_COMPILE_SOURCE_COUNTS,
        )

    def test_all_compile_source_identities_and_hashes_are_closed(self):
        sources = self.report["compile_sources"]
        self.assertEqual(len(sources), 237)
        identities = {
            (
                record["component"],
                record["source"],
                record["linkage"],
            )
            for record in sources
        }
        self.assertEqual(len(identities), 237)
        counts = collections.Counter(
            record["component"] for record in sources
        )
        self.assertEqual(
            dict(counts), MODULE.EXPECTED_COMPILE_SOURCE_COUNTS
        )
        for record in sources:
            self.assertGreater(record["bytes"], 0)
            self.assertRegex(record["sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(record["dependency_file"])
        generated = [
            record
            for record in sources
            if record["source_kind"] == "cmake-automoc-generated"
        ]
        self.assertEqual(len(generated), 1)
        self.assertEqual(
            generated[0]["source"],
            "@build/src/console/diec_autogen/mocs_compilation.cpp",
        )

    def test_archive_build_and_inclusion_sets_are_exact(self):
        archives = {
            record["archive"]: record
            for record in self.report["archives"]
        }
        self.assertEqual(set(archives), set(MODULE.EXPECTED_ARCHIVES))
        for archive, config in MODULE.EXPECTED_ARCHIVES.items():
            record = archives[archive]
            self.assertEqual(record["component"], config["component"])
            self.assertEqual(
                record["built_member_count"], len(config["members"])
            )
            self.assertEqual(
                record["included_member_count"], len(config["included"])
            )
            self.assertEqual(
                set(record["excluded_members"]),
                config["members"] - config["included"],
            )
            self.assertRegex(record["sha256"], r"^[0-9a-f]{64}$")
        archive_sources = [
            record
            for record in self.report["compile_sources"]
            if record["linkage"].startswith("../")
        ]
        self.assertEqual(len(archive_sources), 14)
        self.assertEqual(
            {
                (
                    record["linkage"].split("(", 1)[0],
                    record["linkage"].split("(", 1)[1][:-1],
                )
                for record in archive_sources
            },
            {
                (archive, member)
                for archive, config in MODULE.EXPECTED_ARCHIVES.items()
                for member in config["included"]
            },
        )

    def test_automoc_and_root_license_closures_are_exact(self):
        self.assertEqual(
            set(self.report["generated_automoc"]["origin_components"]),
            MODULE.EXPECTED_GENERATED_ORIGINS,
        )
        licenses = self.report["root_license_evidence"]
        self.assertEqual(len(licenses), 14)
        self.assertEqual(
            {record["component"] for record in licenses},
            set(MODULE.EXPECTED_COMPONENT_DIRECT_COUNTS)
            | {"DIE-engine"},
        )
        for record in licenses:
            self.assertEqual(
                record["license_markers"], ["mit-permission"]
            )
            self.assertRegex(record["sha256"], r"^[0-9a-f]{64}$")
        root = next(
            record
            for record in licenses
            if record["component"] == "DIE-engine"
        )
        self.assertEqual(
            root["sha256"],
            (
                "be0fe2d727cd0a754fb0b2fdc579ead8"
                "f19ef575840b4daef221be201701eaad"
            ),
        )

    def test_marker_counts_and_xucl_gap_are_fail_closed(self):
        self.assertEqual(
            self.report["marker_counts"],
            {
                "gpl": 1,
                "llvm-ncsa": 4,
                "mit-permission": 212,
                "public-domain": 3,
            },
        )
        findings = self.report["notable_license_findings"]
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding["id"], "PRODUCT-LICENSE-GAP-001")
        self.assertEqual(
            finding["source"], "XArchive/Algos/xucldecoder.cpp"
        )
        self.assertEqual(finding["linkage"], "direct-object")
        self.assertEqual(finding["gpl_marker_lines"], [842])
        self.assertEqual(
            finding["referenced_license_file"], "ACC_LICENSE"
        )
        self.assertEqual(
            finding["matching_license_paths_in_component"], []
        )
        self.assertEqual(
            finding["source_sha256"],
            (
                "f2f2fe4e11beaa122c2474a44c7c1c97"
                "242e9d211eacc15d0c7f3c646b2a45cf"
            ),
        )
        xucl = [
            record
            for record in self.report["compile_sources"]
            if record["source"] == finding["source"]
        ]
        self.assertEqual(len(xucl), 1)
        self.assertEqual(
            xucl[0]["license_markers"], ["gpl", "mit-permission"]
        )

    def test_report_has_no_container_or_workspace_paths(self):
        serialized = REPORT_PATH.read_text(encoding="utf-8")
        self.assertNotIn("/opt/die-source", serialized)
        self.assertNotIn("/opt/die-build", serialized)
        self.assertNotIn(str(ROOT), serialized)

    def test_dependency_and_map_parsers_are_fail_closed(self):
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
        valid_map = (
            "Archive member included to satisfy reference by file (symbol)\n"
            "\n"
            "../XSIMD/libxsimd.a(xsimd.c.o)\n"
            " source.o (xsimd_init)\n"
            "\n"
            "Merging program properties\n"
        )
        self.assertEqual(
            MODULE.parse_project_archive_inclusions(valid_map),
            {
                (
                    "../XSIMD/libxsimd.a",
                    "xsimd.c.o",
                ): "source.o (xsimd_init)"
            },
        )
        with self.assertRaisesRegex(
            ValueError, "inclusion header is missing"
        ):
            MODULE.parse_project_archive_inclusions("invalid")


if __name__ == "__main__":
    unittest.main()
