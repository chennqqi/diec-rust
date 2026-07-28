import importlib.util
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
AUDITOR_PATH = (
    ROOT / "tools/corpus/audit_rar_compressed_fixture_source.py"
)
RAR4_GENERATOR_PATH = (
    ROOT / "tools/corpus/generate_archive_format_fixture.py"
)
RAR5_GENERATOR_PATH = (
    ROOT / "tools/corpus/generate_rar5_store_fixture.py"
)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


AUDITOR = load("audit_rar_compressed_fixture_source", AUDITOR_PATH)
RAR4 = load("rar4_for_fixture_audit", RAR4_GENERATOR_PATH)
RAR5 = load("rar5_for_fixture_audit", RAR5_GENERATOR_PATH)


class RarCompressedFixtureSourceAuditTests(unittest.TestCase):
    def test_vint_boundaries_and_failures(self):
        self.assertEqual(AUDITOR.read_vint(b"\x00", 0), (0, 1))
        self.assertEqual(AUDITOR.read_vint(b"\x80\x01", 0), (128, 2))
        with self.assertRaisesRegex(
            AUDITOR.FixtureAuditError, "truncated"
        ):
            AUDITOR.read_vint(b"\x80", 0)
        with self.assertRaisesRegex(
            AUDITOR.FixtureAuditError, "oversized"
        ):
            AUDITOR.read_vint(b"\x80" * 10, 0)

    def test_project_generated_rar4_store_is_parsed(self):
        archive = RAR4.make_rar4_stored("payload.pdf", RAR4.PDF)
        parsed = AUDITOR.parse_rar3(archive)
        self.assertEqual(parsed["format"], "RAR3")
        self.assertFalse(parsed["archive_solid"])
        self.assertEqual(
            [
                (
                    member["name"],
                    member["method"],
                    member["unpacked_size"],
                )
                for member in parsed["members"]
            ],
            [("payload.pdf", 0x30, len(RAR4.PDF))],
        )

    def test_project_generated_rar5_store_is_parsed(self):
        archive = RAR5.make_rar5_store(
            [("payload.pdf", RAR5.PDF, False)],
            solid=False,
        )
        parsed = AUDITOR.parse_rar5(archive)
        self.assertEqual(parsed["format"], "RAR5")
        self.assertFalse(parsed["archive_solid"])
        self.assertEqual(
            [
                (
                    member["name"],
                    member["method"],
                    member["unpacked_size"],
                )
                for member in parsed["members"]
            ],
            [("payload.pdf", 0, len(RAR5.PDF))],
        )

    def test_header_crc_corruption_is_rejected(self):
        archive = bytearray(
            RAR5.make_rar5_store(
                [("payload.pdf", RAR5.PDF, False)],
                solid=False,
            )
        )
        archive[len(AUDITOR.RAR5_SIGNATURE)] ^= 1
        with self.assertRaisesRegex(
            AUDITOR.FixtureAuditError, "header CRC"
        ):
            AUDITOR.parse_rar5(bytes(archive))

    def test_path_traversal_is_rejected(self):
        with self.assertRaisesRegex(
            AUDITOR.FixtureAuditError, "unsafe"
        ):
            AUDITOR.decode_name(b"../payload.pdf")


if __name__ == "__main__":
    unittest.main()
