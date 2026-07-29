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
    / "docs/research/data/xarchive-final-link-closure-linux.json"
)
PRIOR_REPORT_PATH = (
    ROOT / "docs/research/data/xarchive-license-closure-linux.json"
)
TOOL_PATH = (
    ROOT / "tools/upstream/audit_xarchive_final_link_closure.py"
)
LOCK_PATH = ROOT / "upstream/components.lock.toml"
SPEC = importlib.util.spec_from_file_location(
    "audit_xarchive_final_link_closure", TOOL_PATH
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class XArchiveFinalLinkClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(
            REPORT_PATH.read_text(encoding="utf-8")
        )

    def test_report_is_bound_to_generator_prior_lock_and_image(self):
        report = self.report
        lock = tomllib.loads(LOCK_PATH.read_text(encoding="utf-8"))
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(
            report["generator"],
            "tools/upstream/audit_xarchive_final_link_closure.py",
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
            report["prior_build_closure"]["sha256"],
            hashlib.sha256(PRIOR_REPORT_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            report["upstream_commit"], MODULE.UPSTREAM_COMMIT
        )
        self.assertEqual(
            report["xarchive_commit"],
            lock["gitlink"]["XArchive"]["commit"],
        )
        self.assertEqual(
            report["source_image"]["revision"],
            MODULE.UPSTREAM_COMMIT,
        )
        self.assertEqual(report["source_image"]["network"], "none")
        self.assertEqual(
            report["source_image"]["repository_mount"], "readonly"
        )

    def test_link_map_proves_only_lzmadec_is_included(self):
        report = self.report
        self.assertTrue(all(report["relationships"].values()))
        self.assertEqual(
            report["build"]["direct_xarchive_object_count"], 84
        )
        self.assertEqual(
            report["build"]["built_archive_member_count"], 22
        )
        self.assertEqual(
            report["build"]["included_archive_member_count"], 1
        )
        self.assertEqual(
            report["build"]["excluded_archive_member_count"], 21
        )
        self.assertEqual(
            report["build"]["final_xarchive_compile_source_count"], 85
        )
        self.assertEqual(
            report["build"]["artifact_sha256"],
            report["build"]["replayed_artifact_sha256"],
        )
        self.assertEqual(
            report["build"]["link_map_sha256"],
            (
                "91dc73e22c7e22226b6a354f6ac5e7e2"
                "2743f10c16a718af915d895fafeecd70"
            ),
        )
        included = [
            member
            for member in report["members"]
            if member["included_by_link_map"]
        ]
        self.assertEqual(len(included), 1)
        self.assertEqual(
            (
                included[0]["archive"],
                included[0]["member"],
                included[0]["inclusion_reason"],
            ),
            (
                "../XArchive/3rdparty/lzma/liblzma.a",
                "LzmaDec.c.o",
                (
                    "CMakeFiles/diec.dir/__/__/XStaticUnpacker/"
                    "xnsis.cpp.o (LzmaDec_Init)"
                ),
            ),
        )

    def test_all_built_archive_members_and_hashes_are_exact(self):
        archive_hashes = {
            "../XArchive/3rdparty/bzip2/libbzip2.a": (
                "bf586b5a049514b66507fccadce0fd345"
                "68287917be46a6611c38590d59f8305"
            ),
            "../XArchive/3rdparty/lzma/liblzma.a": (
                "b00a2ef5ef4a83076bc0f26294f0276b"
                "bfa4a594832e2eb200713087ecb785de"
            ),
            "../XArchive/3rdparty/ppmd/libppmd.a": (
                "34dd0bc1fb8b7f92f934334e89805b4d"
                "3d56980c19c963bb40ad0d7904e64307"
            ),
            "../XArchive/3rdparty/zlib/libzlib.a": (
                "d306537c392978554ddc10d47c5c5731"
                "81aedd8b26760e6950af791a53f14d4b"
            ),
        }
        archives = {
            record["archive"]: record
            for record in self.report["archives"]
        }
        self.assertEqual(set(archives), set(MODULE.EXPECTED_ARCHIVES))
        for archive, expected_members in MODULE.EXPECTED_ARCHIVES.items():
            record = archives[archive]
            self.assertEqual(
                record["built_member_count"], len(expected_members)
            )
            self.assertEqual(record["sha256"], archive_hashes[archive])
        members = {
            (record["archive"], record["member"])
            for record in self.report["members"]
        }
        self.assertEqual(
            members,
            {
                (archive, member)
                for archive, expected in MODULE.EXPECTED_ARCHIVES.items()
                for member in expected
            },
        )

    def test_extracted_lzma_dependency_closure_is_exact(self):
        report = self.report
        self.assertEqual(
            report["included_member_dependency_file_count"], 5
        )
        records = {
            record["path"]: record
            for record in report["included_member_dependency_files"]
        }
        self.assertEqual(
            set(records),
            {
                "3rdparty/lzma/src/7zTypes.h",
                "3rdparty/lzma/src/Compiler.h",
                "3rdparty/lzma/src/LzmaDec.c",
                "3rdparty/lzma/src/LzmaDec.h",
                "3rdparty/lzma/src/Precomp.h",
            },
        )
        expected_hashes = {
            "3rdparty/lzma/src/7zTypes.h": (
                "e3636de033274b264be8c66ded3443a79"
                "e45171492fcb4626ca3cb894738b186"
            ),
            "3rdparty/lzma/src/Compiler.h": (
                "e4b14a798e6c01bc885966249afa6b50"
                "61a5dd10c723ce86b254e89ae650de7f"
            ),
            "3rdparty/lzma/src/LzmaDec.c": (
                "6e96899def1c643f24435563c96b1cff"
                "e9be589ffecaa3f663d6cab77845e3e6"
            ),
            "3rdparty/lzma/src/LzmaDec.h": (
                "3aaf07b4ae4173a2d103179455dc7089"
                "b5ddbc7fc3db3c0e40964a7499c69266"
            ),
            "3rdparty/lzma/src/Precomp.h": (
                "3850ffe13cb2207dba1c037fe41a80330"
                "3883aaeec1407052f6038c4e6722ace"
            ),
        }
        for path, record in records.items():
            self.assertEqual(
                record["license_markers"],
                ["igor-pavlov", "public-domain"],
            )
            self.assertEqual(record["sha256"], expected_hashes[path])

    def test_symbol_intersection_false_positive_boundary_is_exact(self):
        report = self.report
        boundary = report["symbol_intersection_boundary"]
        self.assertEqual(
            boundary["excluded_members_with_nonempty_intersections"], 8
        )
        misleading = {
            (member["archive"], member["member"])
            for member in report["members"]
            if (
                not member["included_by_link_map"]
                and member["final_elf_symbol_name_intersections"]
            )
        }
        self.assertEqual(
            misleading,
            {
                (
                    "../XArchive/3rdparty/bzip2/libbzip2.a",
                    "bzip2.c.o",
                ),
                (
                    "../XArchive/3rdparty/bzip2/libbzip2.a",
                    "bzlib.c.o",
                ),
                (
                    "../XArchive/3rdparty/bzip2/libbzip2.a",
                    "crctable.c.o",
                ),
                (
                    "../XArchive/3rdparty/bzip2/libbzip2.a",
                    "decompress.c.o",
                ),
                (
                    "../XArchive/3rdparty/bzip2/libbzip2.a",
                    "huffman.c.o",
                ),
                (
                    "../XArchive/3rdparty/bzip2/libbzip2.a",
                    "randtable.c.o",
                ),
                (
                    "../XArchive/3rdparty/zlib/libzlib.a",
                    "deflate.c.o",
                ),
                (
                    "../XArchive/3rdparty/zlib/libzlib.a",
                    "inflate.c.o",
                ),
            },
        )
        self.assertIn("not proof", boundary["interpretation"])

    def test_report_has_no_container_or_workspace_paths(self):
        serialized = REPORT_PATH.read_text(encoding="utf-8")
        self.assertNotIn("/opt/die-source", serialized)
        self.assertNotIn("/opt/die-build", serialized)
        self.assertNotIn(str(ROOT), serialized)

    def test_parsers_are_fail_closed(self):
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
        valid_map = (
            "Archive member included to satisfy reference by file (symbol)\n"
            "\n"
            "../XArchive/3rdparty/lzma/liblzma.a(LzmaDec.c.o)\n"
            " source.o (LzmaDec_Init)\n"
            "\n"
            "Merging program properties\n"
        )
        self.assertEqual(
            MODULE.parse_archive_inclusions(valid_map),
            {
                (
                    "../XArchive/3rdparty/lzma/liblzma.a",
                    "LzmaDec.c.o",
                ): "source.o (LzmaDec_Init)"
            },
        )
        with self.assertRaisesRegex(
            ValueError, "inclusion header is missing"
        ):
            MODULE.parse_archive_inclusions("no map header")


if __name__ == "__main__":
    unittest.main()
