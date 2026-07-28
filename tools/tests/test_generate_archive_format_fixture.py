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
                    "pdf-member-lzma2-aes.7z",
                    "pdf-member-bcj2-lzma2-aes.7z",
                    "pdf-member-bcj-lzma2-aes.7z",
                    "pdf-member-arm64-lzma2-aes.7z",
                    "pdf-member-ppmd7.7z",
                    "pdf-member-bzip2.7z",
                    "pdf-member-deflate.7z",
                    "pdf-member-deflate64.7z",
                    "pdf-member-bcj-lzma2.7z",
                    "pdf-member-bcj2-lzma2.7z",
                    "pdf-member-bcj2-e8-lzma2.7z",
                    "pdf-member-bcj2-e9-lzma2.7z",
                    "pdf-member-bcj2-jcc-lzma2.7z",
                    "pdf-member-arm64-bcj-lzma2.7z",
                    "pdf-member.rar",
                    "pdf-member.cab",
                    "pdf-member-mszip.cab",
                    "pdf-member-lzx.cab",
                    "text-member-quantum.cab",
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
                        "dict_size": 1 << 12,
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

    def test_7z_lzma2_aes_fixture_is_fixed_and_opaque(self):
        module = load_module()
        data = module.make_7z_lzma2_aes(
            module.PAYLOAD_NAME,
            module.PDF,
        )
        self.assertEqual(len(data), 338)
        self.assertEqual(
            hashlib.sha256(data).hexdigest(),
            "07c1603dde5df154731333c94f8eba472f792a036bbb1cac566b2a9233afa21e",
        )
        self.assertTrue(data.startswith(b"7z\xbc\xaf\x27\x1c\x00\x04"))
        self.assertNotIn(module.PDF, data)
        self.assertEqual(data.count(b"\x06\xf1\x07\x01"), 1)
        self.assertIn(
            module.PAYLOAD_NAME.encode("utf-16le") + b"\0\0",
            data,
        )
        for name, payload in (
            ("other.pdf", module.PDF),
            (module.PAYLOAD_NAME, b"not-pdf"),
        ):
            with self.subTest(name=name, payload=payload):
                with self.assertRaisesRegex(
                    ValueError,
                    "7Z LZMA2\\+AES fixture requires the canonical PDF",
                ):
                    module.make_7z_lzma2_aes(name, payload)

    def test_7z_bcj2_lzma2_aes_fixture_is_fixed_and_opaque(self):
        module = load_module()
        data = module.make_7z_bcj2_lzma2_aes(
            module.PAYLOAD_NAME,
            module.PDF,
        )
        self.assertEqual(len(data), 466)
        self.assertEqual(
            hashlib.sha256(data).hexdigest(),
            "65acd90a7e2bc019e328d3084821bdcbaaa75404084773b1ac94b07c7989bd50",
        )
        self.assertTrue(data.startswith(b"7z\xbc\xaf\x27\x1c\x00\x04"))
        self.assertNotIn(module.PDF, data)
        self.assertEqual(data.count(b"\x06\xf1\x07\x01"), 4)
        self.assertEqual(data.count(module.SEVENZIP_CODER_IDS["BCJ2"]), 1)
        self.assertIn(
            module.PAYLOAD_NAME.encode("utf-16le") + b"\0\0",
            data,
        )
        for name, payload in (
            ("other.pdf", module.PDF),
            (module.PAYLOAD_NAME, b"not-pdf"),
        ):
            with self.subTest(name=name, payload=payload):
                with self.assertRaisesRegex(
                    ValueError,
                    (
                        "7Z BCJ2\\+LZMA2\\+AES fixture "
                        "requires the canonical PDF"
                    ),
                ):
                    module.make_7z_bcj2_lzma2_aes(name, payload)

    def test_7z_filter_lzma2_aes_fixtures_are_fixed_and_opaque(self):
        module = load_module()
        cases = (
            (
                "BCJ",
                module.make_7z_bcj_lzma2_aes,
                module.SEVENZIP_CODER_IDS["BCJ"],
                (
                    "7eed6f558d94ee89eba36b8e486d0945"
                    "83c31f1227d434af81a47d8c9c1ce857"
                ),
            ),
            (
                "ARM64",
                module.make_7z_arm64_lzma2_aes,
                module.SEVENZIP_CODER_IDS["ARM64-BCJ"],
                (
                    "dcc122a6019de6e1ea0d07bd853a88069"
                    "f88b5e709da684eb0647bdec43434ea"
                ),
            ),
        )
        for filter_name, factory, filter_id, expected_sha256 in cases:
            with self.subTest(filter_name=filter_name):
                data = factory(module.PAYLOAD_NAME, module.PDF)
                self.assertEqual(len(data), 354)
                self.assertEqual(
                    hashlib.sha256(data).hexdigest(),
                    expected_sha256,
                )
                self.assertTrue(
                    data.startswith(b"7z\xbc\xaf\x27\x1c\x00\x04")
                )
                self.assertNotIn(module.PDF, data)
                packed_size = int.from_bytes(data[12:20], "little")
                next_header = data[32 + packed_size :]
                self.assertEqual(
                    next_header.count(b"\x06\xf1\x07\x01"),
                    1,
                )
                self.assertEqual(
                    next_header.count(bytes((len(filter_id),)) + filter_id),
                    1,
                )
                self.assertIn(
                    module.PAYLOAD_NAME.encode("utf-16le") + b"\0\0",
                    data,
                )
                with self.assertRaisesRegex(
                    ValueError,
                    (
                        f"7Z {filter_name}\\+LZMA2\\+AES fixture "
                        "requires the canonical PDF"
                    ),
                ):
                    factory(module.PAYLOAD_NAME, b"not-pdf")

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

    def test_7z_bcj2_lzma2_control_round_trips_independently(self):
        module = load_module()
        self.assertFalse(module.has_bcj2_candidate(module.PDF))
        archive = module.make_7z_bcj2_lzma2_control(
            module.PAYLOAD_NAME,
            module.PDF,
        )
        packed_size = int.from_bytes(archive[12:20], "little")
        packed = archive[32 : 32 + packed_size]
        next_header = archive[32 + packed_size :]
        self.assertEqual(packed[-5:], b"\0" * 5)
        self.assertEqual(
            lzma.decompress(
                packed[:-5],
                format=lzma.FORMAT_RAW,
                filters=[
                    {
                        "id": lzma.FILTER_LZMA2,
                        "dict_size": module.SEVENZIP_DICTIONARY_SIZE,
                    }
                ],
            ),
            module.PDF,
        )
        self.assertIn(
            b"\x21\x21\x01\x00\x14\x03\x03\x01\x1b\x04\x01",
            next_header,
        )
        self.assertIn(module.SEVENZIP_CODER_IDS["BCJ2"], next_header)
        with self.assertRaisesRegex(
            ValueError,
            "BCJ2 control payload contains a branch candidate",
        ):
            module.make_7z_bcj2_lzma2_control(
                module.PAYLOAD_NAME,
                b"\xe8\0\0\0\0",
            )

    def test_7z_bcj2_e8_vector_round_trips_independently(self):
        module = load_module()
        main, call, jump, range_stream = module.encode_bcj2_streams(
            module.BCJ2_E8_PDF,
            "e8",
        )
        self.assertEqual(main, module.PDF + b"\xe8")
        self.assertEqual(call, b"\0\0\0\x10")
        self.assertEqual(jump, b"")
        self.assertEqual(range_stream, b"\x00\x7f\xff\xfc\x00")
        absolute = int.from_bytes(call, "big")
        relative = (
            absolute - (len(main) + 4)
        ) & 0xFFFFFFFF
        self.assertEqual(
            main + relative.to_bytes(4, "little"),
            module.BCJ2_E8_PDF,
        )
        archive = module.make_7z_bcj2_lzma2_e8(
            module.PAYLOAD_NAME,
            module.BCJ2_E8_PDF,
        )
        self.assertIn(module.SEVENZIP_CODER_IDS["BCJ2"], archive)
        with self.assertRaisesRegex(
            ValueError,
            "unexpected BCJ2 E8 payload",
        ):
            module.encode_bcj2_streams(module.PDF, "e8")
        with self.assertRaisesRegex(
            ValueError,
            "unsupported BCJ2 branch kind",
        ):
            module.encode_bcj2_streams(module.PDF, "unknown")

    def test_7z_bcj2_e9_and_jcc_vectors_round_trip_independently(
        self,
    ):
        module = load_module()
        cases = (
            (
                "e9",
                module.BCJ2_E9_PDF,
                module.PDF + b"\xe9",
                module.make_7z_bcj2_lzma2_e9,
            ),
            (
                "jcc",
                module.BCJ2_JCC_PDF,
                module.PDF + b"\x0f\x85",
                module.make_7z_bcj2_lzma2_jcc,
            ),
        )
        for branch_kind, payload, expected_main, factory in cases:
            with self.subTest(branch_kind=branch_kind):
                main, call, jump, range_stream = (
                    module.encode_bcj2_streams(
                        payload,
                        branch_kind,
                    )
                )
                self.assertEqual(main, expected_main)
                self.assertEqual(call, b"")
                self.assertEqual(jump, b"\0\0\0\x10")
                self.assertEqual(
                    range_stream,
                    b"\x00\x7f\xff\xfc\x00",
                )
                absolute = int.from_bytes(jump, "big")
                relative = (
                    absolute - (len(main) + 4)
                ) & 0xFFFFFFFF
                self.assertEqual(
                    main + relative.to_bytes(4, "little"),
                    payload,
                )
                archive = factory(module.PAYLOAD_NAME, payload)
                self.assertIn(
                    module.SEVENZIP_CODER_IDS["BCJ2"],
                    archive,
                )
        with self.assertRaisesRegex(
            ValueError,
            "unexpected BCJ2 E9 payload",
        ):
            module.encode_bcj2_streams(module.PDF, "e9")
        with self.assertRaisesRegex(
            ValueError,
            "unexpected BCJ2 JCC payload",
        ):
            module.encode_bcj2_streams(module.PDF, "jcc")

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
        lzx = module.make_cab_lzx15(
            module.PAYLOAD_NAME,
            module.PDF,
        )
        self.assertEqual(len(lzx), 330)
        self.assertEqual(
            hashlib.sha256(lzx).hexdigest(),
            "9fa90ae102f325edc1aaa127216f76a01e393c61b1878098b7179d4db00fa633",
        )
        lzx_data_offset = int.from_bytes(lzx[36:40], "little")
        self.assertEqual(
            int.from_bytes(lzx[42:44], "little"),
            0x0F03,
        )
        self.assertEqual(
            int.from_bytes(
                lzx[lzx_data_offset : lzx_data_offset + 4],
                "little",
            ),
            0x715EAFFD,
        )
        self.assertEqual(
            lzx[lzx_data_offset + 8 :],
            module.CAB_LZX15_PDF_STREAM,
        )
        with self.assertRaisesRegex(
            ValueError,
            "CAB LZX15 fixture requires the canonical PDF",
        ):
            module.make_cab_lzx15(module.PAYLOAD_NAME, b"not-pdf")
        quantum = module.make_cab_quantum18(
            module.QTM_PAYLOAD_NAME,
            module.QTM_PAYLOAD,
        )
        self.assertEqual(len(quantum), 124)
        self.assertEqual(
            hashlib.sha256(quantum).hexdigest(),
            "2c24e38765939ee6003125244650f32e46a1af760f98c28c79699fc88319945e",
        )
        self.assertEqual(
            int.from_bytes(quantum[42:44], "little"),
            0x1222,
        )
        quantum_data_offset = int.from_bytes(quantum[36:40], "little")
        self.assertEqual(quantum_data_offset, 68)
        self.assertEqual(
            int.from_bytes(
                quantum[
                    quantum_data_offset + 4 : quantum_data_offset + 6
                ],
                "little",
            ),
            len(module.CAB_QUANTUM18_TEXT_STREAM),
        )
        self.assertEqual(
            int.from_bytes(
                quantum[
                    quantum_data_offset + 6 : quantum_data_offset + 8
                ],
                "little",
            ),
            len(module.QTM_PAYLOAD),
        )
        self.assertEqual(
            quantum[quantum_data_offset + 8 :],
            module.CAB_QUANTUM18_TEXT_STREAM,
        )
        self.assertEqual(
            hashlib.sha256(
                module.CAB_QUANTUM18_TEXT_STREAM
            ).hexdigest(),
            "6131acbaf1867209d537751a567e4c0a72756e7731a166395433c65d1543c04d",
        )
        self.assertEqual(
            hashlib.md5(module.QTM_PAYLOAD).hexdigest(),
            "98fcfa4962a0f169a3c7fdbcb445cf17",
        )
        with self.assertRaisesRegex(
            ValueError,
            "CAB Quantum18 fixture requires the canonical text",
        ):
            module.make_cab_quantum18(
                module.QTM_PAYLOAD_NAME,
                b"not-canonical",
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
