import binascii
import bz2
import hashlib
import importlib.util
import json
import lzma
import pathlib
import tempfile
import unittest
import zlib

import inflate64
import pyppmd


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
                    "pdf-member.7z",
                    "pdf-member-lzma.7z",
                    "pdf-member-lzma2.7z",
                    "pdf-member-ppmd7.7z",
                    "pdf-member-bzip2.7z",
                    "pdf-member-deflate.7z",
                    "pdf-member-deflate64.7z",
                    "pdf-member-bcj-lzma2.7z",
                    "pdf-member-arm64-bcj-lzma2.7z",
                    "pdf-member.rar",
                    "pdf-member.cab",
                    "pdf-member-mszip.cab",
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

    def test_7z_copy_header_crcs_and_payload_are_deterministic(self):
        module = load_module()
        data = module.make_7z_stored(module.PAYLOAD_NAME, module.PDF)
        self.assertTrue(data.startswith(b"7z\xbc\xaf\x27\x1c\x00\x04"))
        self.assertEqual(data.count(module.PDF), 1)
        start_header = data[12:32]
        self.assertEqual(
            int.from_bytes(data[8:12], "little"),
            binascii.crc32(start_header) & 0xFFFFFFFF,
        )
        next_header_offset = int.from_bytes(
            start_header[0:8],
            "little",
        )
        next_header_size = int.from_bytes(
            start_header[8:16],
            "little",
        )
        next_header = data[
            32 + next_header_offset :
            32 + next_header_offset + next_header_size
        ]
        self.assertEqual(
            int.from_bytes(start_header[16:20], "little"),
            binascii.crc32(next_header) & 0xFFFFFFFF,
        )
        self.assertEqual(next_header[0], 0x01)
        self.assertIn(
            module.PAYLOAD_NAME.encode("utf-16le") + b"\0\0",
            next_header,
        )

    def test_7z_compressed_payloads_round_trip_independently(self):
        module = load_module()
        decoders = {
            "Copy": lambda value: value,
            "LZMA": lambda value: lzma.decompress(
                value,
                format=lzma.FORMAT_RAW,
                filters=[
                    {
                        "id": lzma.FILTER_LZMA1,
                        "dict_size": module.SEVENZIP_DICTIONARY_SIZE,
                        "lc": 3,
                        "lp": 0,
                        "pb": 2,
                    }
                ],
            ),
            "LZMA2": lambda value: lzma.decompress(
                value,
                format=lzma.FORMAT_RAW,
                filters=[
                    {
                        "id": lzma.FILTER_LZMA2,
                        "dict_size": module.SEVENZIP_DICTIONARY_SIZE,
                    }
                ],
            ),
            "PPMd7": lambda value: pyppmd.Ppmd7Decoder(
                module.PPMD7_ORDER,
                module.PPMD7_MEMORY_SIZE,
            ).decode(value, len(module.PDF)),
            "BZip2": bz2.decompress,
            "Deflate": lambda value: zlib.decompress(value, wbits=-15),
            "Deflate64": lambda value: inflate64.Inflater().inflate(
                value
            ),
        }
        expected_properties = {
            "Copy": b"",
            "LZMA": b"\x5d\x00\x00\x10\x00",
            "LZMA2": b"\x10",
            "PPMd7": b"\x06\x00\x00\x10\x00",
            "BZip2": b"",
            "Deflate": b"",
            "Deflate64": b"",
        }
        for method, decoder in decoders.items():
            with self.subTest(method=method):
                payload = (
                    module.DEFLATE64_PDF
                    if method == "Deflate64"
                    else module.PDF
                )
                packed, properties = module.encode_7z_payload(
                    method,
                    payload,
                )
                self.assertEqual(
                    properties,
                    expected_properties[method],
                )
                self.assertEqual(decoder(packed), payload)
                archive = module.make_7z_single(
                    module.PAYLOAD_NAME,
                    payload,
                    method,
                )
                self.assertTrue(
                    archive.startswith(b"7z\xbc\xaf\x27\x1c\x00\x04")
                )
                self.assertIn(
                    module.SEVENZIP_CODER_IDS[method],
                    archive,
                )

        with self.assertRaisesRegex(ValueError, "unsupported 7Z method"):
            module.encode_7z_payload("Unknown", module.PDF)

    def test_deflate64_vector_requires_the_extended_distance_code(self):
        module = load_module()
        self.assertEqual(
            len(module.DEFLATE64_PDF),
            module.DEFLATE64_DISTANCE + 3,
        )
        self.assertEqual(
            module.DEFLATE64_PDF[-3:],
            module.DEFLATE64_PDF[:3],
        )
        packed, properties = module.encode_7z_payload(
            "Deflate64",
            module.DEFLATE64_PDF,
        )
        self.assertEqual(properties, b"")
        decoder = inflate64.Inflater()
        self.assertEqual(
            decoder.inflate(packed),
            module.DEFLATE64_PDF,
        )
        self.assertTrue(decoder.eof)
        with self.assertRaises(zlib.error):
            zlib.decompress(packed, wbits=-15)
        with self.assertRaisesRegex(
            ValueError,
            "unexpected Deflate64 distance vector payload",
        ):
            module.encode_7z_payload("Deflate64", module.PDF)

    def test_7z_bcj_lzma2_chain_round_trips_independently(self):
        module = load_module()
        filters = [
            {"id": lzma.FILTER_X86},
            {
                "id": lzma.FILTER_LZMA2,
                "dict_size": module.SEVENZIP_DICTIONARY_SIZE,
            },
        ]
        archive = module.make_7z_bcj_lzma2(
            module.PAYLOAD_NAME,
            module.PDF,
        )
        start_header = archive[12:32]
        packed_size = int.from_bytes(
            start_header[0:8],
            "little",
        )
        packed = archive[32 : 32 + packed_size]
        self.assertEqual(
            lzma.decompress(
                packed,
                format=lzma.FORMAT_RAW,
                filters=filters,
            ),
            module.PDF,
        )
        next_header = archive[32 + packed_size :]
        self.assertIn(
            module.SEVENZIP_CODER_IDS["LZMA2"],
            next_header,
        )
        self.assertIn(
            module.SEVENZIP_CODER_IDS["BCJ"],
            next_header,
        )
        self.assertIn(b"\x02\x21\x21\x01\x10\x04\x03\x03\x01\x03", next_header)

    def test_7z_arm64_bcj_lzma2_vectors_round_trip(self):
        module = load_module()
        self.assertEqual(len(module.ARM64_PDF), 4100)
        self.assertEqual(
            int.from_bytes(module.ARM64_PDF[332:336], "little"),
            0x94000002,
        )
        self.assertEqual(
            int.from_bytes(module.ARM64_PDF[4096:4100], "little"),
            0x90000001,
        )
        encoded = module.arm64_bcj_encode(module.ARM64_PDF)
        self.assertEqual(
            int.from_bytes(encoded[332:336], "little"),
            0x94000055,
        )
        self.assertEqual(
            int.from_bytes(encoded[4096:4100], "little"),
            0xB0000001,
        )
        self.assertNotEqual(encoded, module.ARM64_PDF)
        self.assertEqual(
            module.arm64_bcj_decode(encoded),
            module.ARM64_PDF,
        )

        archive = module.make_7z_arm64_bcj_lzma2(
            module.PAYLOAD_NAME,
            module.ARM64_PDF,
        )
        packed_size = int.from_bytes(archive[12:20], "little")
        packed = archive[32 : 32 + packed_size]
        filtered = lzma.decompress(
            packed,
            format=lzma.FORMAT_RAW,
            filters=[
                {
                    "id": lzma.FILTER_LZMA2,
                    "dict_size": module.SEVENZIP_DICTIONARY_SIZE,
                },
            ],
        )
        self.assertEqual(filtered, encoded)
        self.assertEqual(
            module.arm64_bcj_decode(filtered),
            module.ARM64_PDF,
        )
        next_header = archive[32 + packed_size :]
        self.assertIn(b"\x02\x21\x21\x01\x10\x01\x0a", next_header)

        with self.assertRaisesRegex(
            ValueError,
            "unsupported 7Z filter",
        ):
            module.make_7z_filter_lzma2(
                module.PAYLOAD_NAME,
                module.PDF,
                "Unknown",
            )

    def test_7z_uint64_boundary_encodings_are_canonical(self):
        module = load_module()
        expected = {
            0: b"\x00",
            0x7F: b"\x7f",
            0x80: b"\x80\x80",
            0x14B: b"\x81\x4b",
            0x3FFF: b"\xbf\xff",
            0x4000: b"\xc0\x00\x40",
            0xFFFFFFFFFFFFFFFF: b"\xff" * 9,
        }
        for value, encoded in expected.items():
            with self.subTest(value=value):
                self.assertEqual(module.sevenzip_uint64(value), encoded)
        with self.assertRaises(ValueError):
            module.sevenzip_uint64(-1)
        with self.assertRaises(ValueError):
            module.sevenzip_uint64(0x10000000000000000)

    def test_cab_methods_and_iso_store_are_deterministic(self):
        module = load_module()
        cab = module.make_cab_stored(module.PAYLOAD_NAME, module.PDF)
        self.assertEqual(cab[0:4], b"MSCF")
        self.assertEqual(
            int.from_bytes(cab[8:12], "little"),
            len(cab),
        )
        self.assertEqual(cab.count(module.PDF), 1)

        mszip = module.make_cab_mszip(
            module.PAYLOAD_NAME,
            module.PDF,
        )
        self.assertEqual(mszip[0:4], b"MSCF")
        self.assertEqual(
            int.from_bytes(mszip[8:12], "little"),
            len(mszip),
        )
        folder_offset = 36
        data_offset = int.from_bytes(
            mszip[folder_offset : folder_offset + 4],
            "little",
        )
        self.assertEqual(
            int.from_bytes(
                mszip[folder_offset + 6 : folder_offset + 8],
                "little",
            ),
            1,
        )
        compressed_size = int.from_bytes(
            mszip[data_offset + 4 : data_offset + 6],
            "little",
        )
        uncompressed_size = int.from_bytes(
            mszip[data_offset + 6 : data_offset + 8],
            "little",
        )
        compressed = mszip[
            data_offset + 8 : data_offset + 8 + compressed_size
        ]
        self.assertEqual(compressed[:2], b"CK")
        self.assertEqual(uncompressed_size, len(module.PDF))
        self.assertEqual(
            zlib.decompress(compressed[2:], wbits=-15),
            module.PDF,
        )
        with self.assertRaisesRegex(ValueError, "unsupported CAB method"):
            module.make_cab_single(
                module.PAYLOAD_NAME,
                module.PDF,
                "Unknown",
            )

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
