import binascii
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT
    / "tools"
    / "corpus"
    / "generate_archive_multirecord_fixture.py"
)
REFERENCE_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "archive-multirecord-corpus.json"
)
SPEC = importlib.util.spec_from_file_location(
    "generate_archive_multirecord_fixture",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class GenerateArchiveMultirecordFixtureTests(unittest.TestCase):
    def test_generation_is_reproducible_and_matches_manifest(self):
        expected = json.loads(
            REFERENCE_PATH.read_text(encoding="utf-8")
        )
        with tempfile.TemporaryDirectory() as first_dir:
            with tempfile.TemporaryDirectory() as second_dir:
                first = Path(first_dir)
                second = Path(second_dir)
                first_manifest = MODULE.generate(first)
                second_manifest = MODULE.generate(second)
                self.assertEqual(first_manifest, expected)
                self.assertEqual(second_manifest, expected)
                self.assertEqual(
                    (first / "manifest.json").read_bytes(),
                    REFERENCE_PATH.read_bytes(),
                )
                self.assertEqual(
                    (first / "manifest.json").read_bytes(),
                    (second / "manifest.json").read_bytes(),
                )
                self.assertEqual(
                    {path.name for path in first.iterdir()},
                    {
                        "manifest.json",
                        *{
                            sample["name"]
                            for sample in expected["samples"]
                        },
                    },
                )
                for sample in expected["samples"]:
                    first_data = (first / sample["name"]).read_bytes()
                    second_data = (
                        second / sample["name"]
                    ).read_bytes()
                    self.assertEqual(first_data, second_data)
                    self.assertEqual(len(first_data), sample["size"])
                    self.assertEqual(
                        hashlib.sha256(first_data).hexdigest(),
                        sample["sha256"],
                    )

    def test_manifest_has_complete_format_case_product(self):
        manifest = json.loads(
            REFERENCE_PATH.read_text(encoding="utf-8")
        )
        self.assertEqual(len(manifest["samples"]), 16)
        self.assertEqual(
            {
                (sample["archive_format"], sample["order_case"])
                for sample in manifest["samples"]
            },
            {
                (archive_format, case_name)
                for _, archive_format, _, _ in MODULE.FORMATS
                for case_name, _ in MODULE.ENTRY_CASES
            },
        )
        expected_entries = {
            case_name: [
                {
                    "name": name,
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "size": len(payload),
                }
                for name, payload in entries
            ]
            for case_name, entries in MODULE.ENTRY_CASES
        }
        for sample in manifest["samples"]:
            with self.subTest(sample=sample["name"]):
                self.assertEqual(
                    sample["entries"],
                    expected_entries[sample["order_case"]],
                )

    def test_sevenzip_headers_bind_payload_and_two_names(self):
        with tempfile.TemporaryDirectory() as output_dir:
            root = Path(output_dir)
            manifest = MODULE.generate(root)
            samples = [
                sample
                for sample in manifest["samples"]
                if sample["archive_format"] == "7Z"
            ]
            for sample in samples:
                with self.subTest(sample=sample["name"]):
                    data = (root / sample["name"]).read_bytes()
                    self.assertEqual(data[:6], b"7z\xbc\xaf\x27\x1c")
                    self.assertEqual(
                        int.from_bytes(data[8:12], "little"),
                        binascii.crc32(data[12:32]) & 0xFFFFFFFF,
                    )
                    next_offset = int.from_bytes(
                        data[12:20],
                        "little",
                    )
                    next_size = int.from_bytes(
                        data[20:28],
                        "little",
                    )
                    next_header = data[
                        32 + next_offset :
                        32 + next_offset + next_size
                    ]
                    self.assertEqual(len(next_header), next_size)
                    self.assertEqual(
                        int.from_bytes(data[28:32], "little"),
                        binascii.crc32(next_header) & 0xFFFFFFFF,
                    )
                    self.assertEqual(
                        next_offset,
                        sum(
                            entry["size"]
                            for entry in sample["entries"]
                        ),
                    )
                    encoded_names = b"".join(
                        entry["name"].encode("utf-16le") + b"\0\0"
                        for entry in sample["entries"]
                    )
                    self.assertIn(encoded_names, next_header)

    def test_rar_cab_and_iso_declare_two_records(self):
        with tempfile.TemporaryDirectory() as output_dir:
            root = Path(output_dir)
            manifest = MODULE.generate(root)
            samples = {
                sample["name"]: (root / sample["name"]).read_bytes()
                for sample in manifest["samples"]
            }

            rar = samples["rar4-forward.rar"]
            offset = 7
            file_headers = 0
            while offset < len(rar):
                header_type = rar[offset + 2]
                header_size = int.from_bytes(
                    rar[offset + 5 : offset + 7],
                    "little",
                )
                if header_type == 0x74:
                    file_headers += 1
                    packed_size = int.from_bytes(
                        rar[offset + 7 : offset + 11],
                        "little",
                    )
                    offset += header_size + packed_size
                else:
                    offset += header_size
            self.assertEqual(file_headers, 2)
            self.assertEqual(offset, len(rar))

            cab = samples["cab-forward.cab"]
            self.assertEqual(cab[:4], b"MSCF")
            self.assertEqual(
                int.from_bytes(cab[26:28], "little"),
                1,
            )
            self.assertEqual(
                int.from_bytes(cab[28:30], "little"),
                2,
            )

            iso = samples["iso9660-forward.iso"]
            directory = iso[19 * 2048 : 20 * 2048]
            record_count = 0
            cursor = 0
            while directory[cursor]:
                cursor += directory[cursor]
                record_count += 1
            self.assertEqual(record_count, 4)

    def test_entry_validation_rejects_unsafe_shapes(self):
        for entries in (
            (("only.pdf", b""),),
            (("", b""), ("second.pdf", b"")),
            (("nul\0name", b""), ("second.pdf", b"")),
            (("non-ascii-\N{SNOWMAN}", b""), ("second.pdf", b"")),
            (("large.bin", b"x" * 65536), ("second.pdf", b"")),
        ):
            with self.subTest(entries=entries):
                with self.assertRaises(
                    (UnicodeEncodeError, ValueError)
                ):
                    MODULE.validate_entries(entries)

    def test_cli_can_write_a_separate_reference_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "fixture"
            reference = root / "reference.json"
            original_argv = sys.argv
            sys.argv = [
                str(MODULE_PATH),
                str(fixture),
                "--manifest-output",
                str(reference),
            ]
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(MODULE.main(), 0)
            finally:
                sys.argv = original_argv
            self.assertEqual(
                reference.read_bytes(),
                (fixture / "manifest.json").read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()
