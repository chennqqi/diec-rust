import importlib.util
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools/upstream/audit_yara_license_closure.py"
SPEC = importlib.util.spec_from_file_location(
    "audit_yara_license_closure",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class AuditYaraLicenseClosureUnitTests(unittest.TestCase):
    def test_find_markers_is_case_insensitive_and_sorted(self):
        data = (
            b"Redistribution and use in SOURCE and binary forms; "
            b"AS A SPECIAL EXCEPTION"
        )
        self.assertEqual(
            MODULE.find_markers(data),
            ["bison-special-exception", "yara-bsd"],
        )

    def test_parse_dependency_file_handles_continuations(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "source.o.d"
            path.write_text(
                "source.o: /src/source.c \\\n"
                " /src/header.h\n",
                encoding="utf-8",
            )
            dependencies = MODULE.parse_dependency_file(path)
        self.assertEqual(
            dependencies,
            [
                pathlib.Path("/src/source.c"),
                pathlib.Path("/src/header.h"),
            ],
        )

    def test_official_hash_file_mapping_is_explicit(self):
        self.assertEqual(
            MODULE.official_yara_path("_hash.c"),
            "hash.c",
        )
        self.assertEqual(
            MODULE.official_yara_path("scan.c"),
            "scan.c",
        )

    def test_parse_version_requires_all_three_parts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "libyara.h"
            path.write_text(
                "#define YR_MAJOR_VERSION 4\n"
                "#define YR_MINOR_VERSION 5\n"
                "#define YR_MICRO_VERSION 2\n",
                encoding="utf-8",
            )
            self.assertEqual(MODULE.parse_version(path), "4.5.2")

    def test_warning_parser_keeps_semantic_fields(self):
        stderr = (
            "$YARA_SOURCE/src/atoms.c:730:33: warning: "
            "writing 1 byte into a region of size 0 "
            "[-Wstringop-overflow=]\n"
        )
        self.assertEqual(
            MODULE.warning_records(stderr),
            [
                {
                    "path": "src/atoms.c",
                    "line": 730,
                    "message": (
                        "writing 1 byte into a region of size 0"
                    ),
                    "option": "-Wstringop-overflow=",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
