import binascii
import hashlib
import importlib.util
import json
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "corpus" / "generate_archive_format_fixture.py"
MANIFEST = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "archive-format-corpus.json"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "_archive_format_fixture",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load archive format generator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ArchiveFormatFixtureTests(unittest.TestCase):
    def test_generation_is_reproducible_and_matches_manifest(self):
        module = load_module()
        expected = json.loads(MANIFEST.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temporary:
            output = pathlib.Path(temporary)
            actual = module.generate(output)
            self.assertEqual(actual, expected)
            self.assertEqual(
                {path.name for path in output.iterdir()},
                {
                    "manifest.json",
                    "pdf-member.rar",
                    "pdf-member.cab",
                    "pdf-member.iso",
                },
            )
            for sample in expected["samples"]:
                data = (output / sample["name"]).read_bytes()
                self.assertEqual(len(data), sample["size"])
                self.assertEqual(
                    hashlib.sha256(data).hexdigest(),
                    sample["sha256"],
                )

    def test_rar4_headers_and_payload_are_deterministic(self):
        module = load_module()
        data = module.make_rar4_stored(module.PAYLOAD_NAME, module.PDF)
        self.assertTrue(data.startswith(b"Rar!\x1a\x07\x00"))
        self.assertIn(module.PAYLOAD_NAME.encode("ascii"), data)
        self.assertEqual(data.count(module.PDF), 1)
        offset = 7
        for expected_type in (0x73, 0x74):
            crc16 = int.from_bytes(data[offset : offset + 2], "little")
            header_type = data[offset + 2]
            header_size = int.from_bytes(
                data[offset + 5 : offset + 7],
                "little",
            )
            self.assertEqual(header_type, expected_type)
            self.assertEqual(
                crc16,
                binascii.crc32(
                    data[offset + 2 : offset + header_size]
                )
                & 0xFFFF,
            )
            offset += header_size
            if expected_type == 0x74:
                offset += len(module.PDF)

    def test_cab_and_iso_store_payload_once(self):
        module = load_module()
        cab = module.make_cab_stored(module.PAYLOAD_NAME, module.PDF)
        self.assertEqual(cab[0:4], b"MSCF")
        self.assertEqual(
            int.from_bytes(cab[8:12], "little"),
            len(cab),
        )
        self.assertEqual(cab.count(module.PDF), 1)

        iso = module.make_iso9660_stored(
            module.PAYLOAD_NAME,
            module.PDF,
        )
        self.assertEqual(iso[0x8001:0x8006], b"CD001")
        self.assertEqual(
            int.from_bytes(iso[0x8000 + 128 : 0x8000 + 130], "little"),
            2048,
        )
        self.assertEqual(iso.count(module.PDF), 1)


if __name__ == "__main__":
    unittest.main()
