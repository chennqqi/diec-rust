import importlib.util
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools/upstream/audit_component_licenses.py"
SPEC = importlib.util.spec_from_file_location(
    "audit_component_licenses", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class AuditComponentLicenseUnitTests(unittest.TestCase):
    def test_license_candidate_names_are_case_insensitive(self):
        for name in (
            "LICENSE",
            "LICENSE.TXT",
            "Copying",
            "NOTICE.md",
            "copyright",
        ):
            self.assertTrue(MODULE.is_license_candidate(pathlib.Path(name)))
        self.assertFalse(
            MODULE.is_license_candidate(pathlib.Path("licensing.cpp"))
        )

    def test_first_nonempty_line_is_utf8_lossy_and_bounded(self):
        self.assertEqual(
            MODULE.first_nonempty_line(b"\n \nMIT License\nrest"),
            "MIT License",
        )
        self.assertEqual(
            len(MODULE.first_nonempty_line(b"x" * 500)),
            200,
        )
        self.assertIn(
            "\ufffd", MODULE.first_nonempty_line(b"\xff license")
        )

    def test_license_record_uses_relative_path_and_raw_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            nested = root / "third_party"
            nested.mkdir()
            license_path = nested / "LICENSE"
            license_path.write_bytes(b"MIT License\n")
            record = MODULE.license_record(license_path, root)
        self.assertEqual(record["path"], "third_party/LICENSE")
        self.assertEqual(record["bytes"], 12)
        self.assertEqual(
            record["sha256"],
            "267f7a2e19dfa9df99af774520985a0e"
            "521925293ea5b7e767ab06969d06bf91",
        )
        self.assertEqual(record["first_nonempty_line"], "MIT License")


if __name__ == "__main__":
    unittest.main()
