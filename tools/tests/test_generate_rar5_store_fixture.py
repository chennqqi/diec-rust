import binascii
import hashlib
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
GENERATOR_PATH = (
    ROOT / "tools" / "corpus" / "generate_rar5_store_fixture.py"
)
MANIFEST_PATH = (
    ROOT / "docs" / "research" / "data" / "rar5-store-corpus.json"
)
SPEC = importlib.util.spec_from_file_location(
    "generate_rar5_store_fixture_test",
    GENERATOR_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def decode_uleb128(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    shift = 0
    start = offset
    while offset < len(data):
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, offset - start
        shift += 7
        if shift >= 70:
            break
    raise ValueError("invalid ULEB128")


def parse_headers(data: bytes):
    offset = len(MODULE.RAR5_SIGNATURE)
    headers = []
    while offset < len(data):
        header_offset = offset
        crc32 = int.from_bytes(data[offset : offset + 4], "little")
        offset += 4
        body_size, size_bytes = decode_uleb128(data, offset)
        protected_start = offset
        offset += size_bytes
        body_end = offset + body_size
        header_type, consumed = decode_uleb128(data, offset)
        offset += consumed
        common_flags, consumed = decode_uleb128(data, offset)
        offset += consumed
        data_size = 0
        if common_flags & MODULE.RAR5_COMMON_DATA:
            data_size, consumed = decode_uleb128(data, offset)
            offset += consumed
        headers.append(
            {
                "crc32": crc32,
                "data_size": data_size,
                "header_offset": header_offset,
                "protected": data[protected_start:body_end],
                "type": header_type,
            }
        )
        offset = body_end + data_size
        if header_type == MODULE.RAR5_HEADER_END:
            break
    if offset != len(data):
        raise ValueError("trailing or truncated RAR5 data")
    return headers


class Rar5StoreFixtureTests(unittest.TestCase):
    def test_generation_is_exact_and_reproducible(self):
        expected = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temporary:
            output = pathlib.Path(temporary)
            actual = MODULE.generate(output)
            self.assertEqual(actual, expected)
            self.assertEqual(
                {path.name for path in output.iterdir()},
                {
                    "manifest.json",
                    "rar5-store-single.rar",
                    "rar5-store-solid-pair.rar",
                },
            )
            for sample in actual["samples"]:
                data = (output / sample["name"]).read_bytes()
                self.assertEqual(len(data), sample["size"])
                self.assertEqual(
                    hashlib.sha256(data).hexdigest(),
                    sample["sha256"],
                )

    def test_headers_have_exact_crc_and_inventory(self):
        for fixture in MODULE.FIXTURES:
            with self.subTest(name=fixture["name"]):
                data = MODULE.make_rar5_store(
                    fixture["members"],
                    solid=fixture["solid"],
                )
                self.assertTrue(data.startswith(MODULE.RAR5_SIGNATURE))
                headers = parse_headers(data)
                self.assertEqual(
                    [header["type"] for header in headers],
                    [
                        MODULE.RAR5_HEADER_MAIN,
                        *(
                            MODULE.RAR5_HEADER_FILE
                            for _ in fixture["members"]
                        ),
                        MODULE.RAR5_HEADER_END,
                    ],
                )
                for header in headers:
                    self.assertEqual(
                        header["crc32"],
                        binascii.crc32(header["protected"])
                        & 0xFFFFFFFF,
                    )
                self.assertEqual(
                    [
                        header["data_size"]
                        for header in headers
                        if header["type"] == MODULE.RAR5_HEADER_FILE
                    ],
                    [
                        len(payload)
                        for _, payload, _ in fixture["members"]
                    ],
                )

    def test_payloads_names_and_solid_bits_are_project_controlled(self):
        single = MODULE.make_rar5_store(
            MODULE.FIXTURES[0]["members"],
            solid=False,
        )
        pair = MODULE.make_rar5_store(
            MODULE.FIXTURES[1]["members"],
            solid=True,
        )
        self.assertEqual(single.count(MODULE.PDF), 1)
        self.assertEqual(pair.count(MODULE.PDF), 2)
        self.assertIn(b"payload.pdf", single)
        self.assertIn(b"first.pdf", pair)
        self.assertIn(b"second.pdf", pair)
        self.assertIn(
            MODULE.encode_uleb128(MODULE.RAR5_MAIN_SOLID),
            pair,
        )
        self.assertIn(
            MODULE.encode_uleb128(MODULE.RAR5_COMP_SOLID),
            pair,
        )
        self.assertEqual(
            MODULE.make_rar5_store(
                MODULE.FIXTURES[0]["members"],
                solid=False,
            ),
            single,
        )

    def test_invalid_solid_and_uleb_inputs_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "at least one member"):
            MODULE.make_rar5_store((), solid=False)
        with self.assertRaisesRegex(ValueError, "solid member"):
            MODULE.make_rar5_store(
                (("payload.pdf", MODULE.PDF, True),),
                solid=False,
            )
        with self.assertRaisesRegex(ValueError, "non-negative"):
            MODULE.encode_uleb128(-1)


if __name__ == "__main__":
    unittest.main()
