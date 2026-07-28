#!/usr/bin/env python3
"""Generate benign stored 7Z, RAR4, CAB, and ISO9660 archives."""

from __future__ import annotations

import argparse
import binascii
import bz2
import hashlib
import importlib.metadata
import importlib.util
import json
import lzma
import pathlib
import struct
import sys
import zlib


GENERATOR = "tools/corpus/generate_archive_format_fixture.py"
PAYLOAD_NAME = "payload.pdf"
PYPPMD_VERSION = "1.3.1"
INFLATE64_VERSION = "1.0.4"
PPMD7_ORDER = 6
PPMD7_MEMORY_SIZE = 1 << 20
DEFLATE64_DISTANCE = 32769
QTM_PAYLOAD_NAME = "qtm.txt"
QTM_PAYLOAD = (
    b"If you can read this, the Quantum decompressor is working!\n"
)
LIBMSPACK_COMMIT = "55d501976171397ccd5d5a7a1ca7da065b1d9a06"
LIBMSPACK_QTM_SOURCE_PATH = (
    "libmspack/test/test_files/cabd/mszip_lzx_qtm.cab"
)
LIBMSPACK_QTM_SOURCE_SHA256 = (
    "0ce0b55fe705b744d41bb361170c0467db30da0c7f9bdd386d5dade71a78e171"
)
LIBMSPACK_QTM_STREAM_OFFSET = 331
SEVENZIP_AES_PASSWORD = "DetectItEasy"
SEVENZIP_2602_ARCHIVE_SHA256 = (
    "41aaba7b1235304ab5aa0624530c67ae829496cd29e875925271efdccc28c03e"
)
SEVENZIP_2602_BINARY_SHA256 = (
    "1676a968815b92e865bc0ffeecee3fa284ba4402bf23dc2bec2412c4b502e922"
)


def _load_baseline_module():
    module_path = pathlib.Path(__file__).with_name(
        "generate_baseline_corpus.py"
    )
    spec = importlib.util.spec_from_file_location(
        "_diec_archive_format_baseline",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load baseline corpus builders")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BASELINE = _load_baseline_module()
PDF = BASELINE.make_pdf()
ARM64_PDF = (
    (PDF + b"\n" + struct.pack("<I", 0x94000002)).ljust(4096, b"\0")
    + struct.pack("<I", 0x90000001)
)
DEFLATE64_PDF = PDF.ljust(DEFLATE64_DISTANCE, b"\0") + PDF[:3]
BCJ2_E8_PDF = PDF + b"\xe8\xc0\xfe\xff\xff"
BCJ2_E9_PDF = PDF + b"\xe9\xc0\xfe\xff\xff"
BCJ2_JCC_PDF = PDF + b"\x0f\x85\xbf\xfe\xff\xff"
CAB_LZX15_PDF_STREAM = bytes.fromhex(
    "5b80808d0010b11400000000334300600f567e2b0d0674e2ebb7aa750e2a94ee"
    "25223c59a328eb7291176b7464a1ffff04b1a4f4e1fc00000000553300000b34"
    "3d7070a9e2aa4f5c2e94c22441901064f440139860020b5c7b9df0fd00200000"
    "00006600410019bf7e8dfbfd04f3c687e00e51b04e13faac03046864f3f2ef13"
    "8b8d71f9679d9481486cbec26113033de06b1de2229bf23cdb7cd355a6facd2d"
    "cc22fd0d7f8c46a8d449ad30eab644fc9e9fa9ff878b6392a277c69fb033a337"
    "4bfe3c4f5e94bcc0b91bb86e6ee3510eccfa831e4fde74b460b52a689314884d"
    "e8e9e9f56bb3e82a8e90f6a14201958c0874781e2544b0ab0008"
)
CAB_QUANTUM18_TEXT_STREAM = bytes.fromhex(
    "d606690bcb47f02c2a3a8f2cabbb3cb933018bd8584b7b01ba6f6d516e3ac367"
    "424beb023643d66656ca9e72cc300000"
)
SEVENZIP_LZMA2_AES_PDF_ARCHIVE = bytes.fromhex(
    "377abcaf271c00043660593cd00000000000000062000000000000004ec3e97d"
    "8b2b15a6a56edbdfd3c2937fffec76f3bbefb6c5d45004d210fb8d8d9035471a"
    "da282261b02e909bbe42ee3e883a4de8ea228a98c29d2532d0f28bd8822b26cd"
    "7a52184c2ff00873438a93fab694f1535e3724d13892cb884e5d8ad184760854"
    "2d6485debe4c9f5b5bad745c48fe1a7b6a2ab061341a2c3c6d2534f8a30a8af"
    "b9f66e93bcb749578486a376208a5b5fc87f13f33dfd969eee024a1f04040f8"
    "a4a2986e10c85ceb3e1be06561c14409821827263fa56c61e68690d7e766037d"
    "4f9aa4d387933e232e421b06b3d92720ad01040600010980d000070b01000224"
    "06f1070112530fb21799a5163453efc1ebc1b74d73b6002121010001000c80cb"
    "814b00080a0116f95a33000005011119007000610079006c006f00610064002e"
    "007000640066000000150601002080a4810000"
)
SEVENZIP_BCJ2_LZMA2_AES_PDF_ARCHIVE = bytes.fromhex(
    "377abcaf271c0004e2779571e000000000000000d2000000000000007b81ff2d"
    "271d80bd84e67940230ce881987969ef89cac1f1b6cc44fed48ef888f8ddde48"
    "c1391841bb6fa45b602f30d266ceea9071e7b1fe508c9e5da985faf143a3a9e"
    "9dd4db3bc82386f874c841fbe0a33cfed7ebc5d15d5309f0d90d6757d66801e"
    "8efab42f44c80d415a72ac11c3103c68f795f29285ea41f360dc8b2b224ef9a"
    "c22729e3c96e4171d5ce649f126c605d6b8e37bce70b662b971f412ea096474"
    "2245ae364aa7a18a84e1d0e2acdde8c7336516f76b1c4666f58e4c8086ab674"
    "99ce76f70fcb3579fb8e02ad7db6525c106149664ba87f07b76f8c869d5a653"
    "c230b101040600040980d000001000070b0100062406f1070112530f91e7abdf"
    "c21e75124901166870a852102406f1070112530f6e69975e08eb10a12d29ee33"
    "22e830012406f1070112530fc9ad8c649d7cf2a37d72652113a0e88e2406f107"
    "0112530ff65c7c87baa3e960f4540b36fe096b4e21210100140303011b040108"
    "000701060204030504030201000c05000080cb814b814b00080a0116f95a3300"
    "000501190b00000000000000000000001119007000610079006c006f00610064"
    "002e007000640066000000150601002080ff810000"
)
SEVENZIP_BCJ_LZMA2_AES_PDF_ARCHIVE = bytes.fromhex(
    "377abcaf271c0004829b37dbd0000000000000007200000000000000ffa8883d"
    "6d643210d3096897bd759810152953f82c1c62bfd83d97d41fc2687a20780e02"
    "85252ea5bd9e5f92cce0ae9703177a6cc5962317d3faa07018a92611d6db7dc1"
    "2f3ddaa994e6a044cc1acf90f7979be6d2fc712525bb8889d6e12344d4f3fc6c"
    "0290e1a3187dece255f5b16bef190711589dc9ab7234e13c36705521e1d50713"
    "3da97db67fad04aa378e70cb8ac6e2fbce06fca7a8a2f1ebe7ef3f01f3c63a5"
    "e96507463b372d801895358af9efaf6114cecea7c415bc1e5107348f38da9a75"
    "96adba72c4dbfeb389dfc238b5751f1c801040600010980d000070b0100032406"
    "f1070112530ffca572406a6b2d01b53530ba0a07469721210100040303010301"
    "0002010c80cb814b814b00080a0116f95a330000050119050000000000111900"
    "7000610079006c006f00610064002e007000640066000000150601002080ff81"
    "0000"
)
SEVENZIP_ARM64_LZMA2_AES_PDF_ARCHIVE = bytes.fromhex(
    "377abcaf271c0004f6f7eef4d00000000000000072000000000000003ce2b410"
    "a516be0c8cf6d693f0d8893a0c7235db18fdc32e427954c2a85b2c87bac85bb5"
    "4fc3564d889cf9c0d0a4f9aa4d21e71eb02f1be3797c594a0cc60c9b13ab33de"
    "74b5ade3d00694635554f7b51ada0e0e29da0658a79028b196b946f7ec9d0618"
    "42bafdad763c5e8b225fbd07eabb9233b0ee17c615e57888346ce35e0232080f"
    "39b176465ede7dc221b1baf8a90c2f5b13307b47f1c39a582a6c9602db90309e"
    "897f6d3512c2be4203c85bb9bc71d76636256bba55d8d803d7b77da2717c0236"
    "3f7f7d97715532c5560a7569e96b01a901040600010980d000070b0100032406"
    "f1070112530f001323accc765f02fa4b617dfc027b0821210100010a01000201"
    "0c80cb814b814b00080a0116f95a330000050119080000000000000000111900"
    "7000610079006c006f00610064002e007000640066000000150601002080ff81"
    "0000"
)
SEVENZIP_BASE_AES_PDF_ARCHIVES = {
    "Copy": bytes.fromhex(
        "377abcaf271c00044f06ed8550010000000000006200000000000000e0660d1d"
        "5d63646cef57ce6dc1e61d0812516dc49c316d5456a867f1d134fb1e00eb23b8"
        "46a65efa3fbf91000a0e9b06b5b8e3dee8b3d29545e4c28a0c79950956caa58"
        "bef756c233b9eceddf6a6aeadf7e26a7ebe0b0016ce618baab954f5e4fa8b634"
        "c68f540a1e6ba4cbed125db092bbd6bebdba4b1119ed901c353d49c6f24acc60"
        "b31186323ea7f21e88b54e9f300a139d74700752688868fc00366b75df5e5512"
        "8e14e9b5c70e6295879f34959e68b9b6e49b9b36bd5de7d00928fc2239e5f28"
        "2359bf88d1e4109d6eb4a0bed8f1aa800e6c5049d19dc084023e44bfe1de2d14"
        "3ff4f414b7386e40b8eedc8cb5c2e1fc6d808dc3332e8d445d32ea72912bff57"
        "2b5d14d8976bcfbc6b61526fda2f06a22a6a284d547d5f03b4191ef6a5a8506"
        "54a9e7a4daa7286901fadbe7e716fce57671da132aa8a9d0000d99792c7acc2f"
        "57d82fcdd6442199803b2cfbd4fc77bf43b010406000109815000070b01000224"
        "06f1070112530febbfef5979d92046f0785417a0954755010001000c814b814b"
        "00080a0116f95a330000050119001119007000610079006c006f00610064002e"
        "007000640066000000150601002080ff810000"
    ),
    "LZMA": bytes.fromhex(
        "377abcaf271c000426ea63c7d000000000000000720000000000000098615e2f"
        "64f42eaf452dcf92ea89505a0b4f65edce6fb3728e325315373e8fd72472dfc8"
        "d41f4f0b056b0b78220e5d6d16d04e0b89363c718831b1cbcf248bb70ee8d296"
        "a3211574d0f9bb6e3c54b538ee2e2cec266bcb07b7474245b4b8935c086a481c"
        "4dec9c1220bd4a15e2e3297523878fde3057d8c6763e712ac9565e7b7adcbb05"
        "4b8be24d91d1c00ba394dd30e5dba9537dea05e4eb752af58ed774d2f3d9512"
        "be2667c81f99f7146263ab02dec0d6198fa83bc8b50e3cdec024e503689ee9b6"
        "4918106e961adffc1c2a43f05ba14c8af01040600010980d000070b0100022406"
        "f1070112530f6694b6bc7ad61eb4482669515ed396a623030101055d00100000"
        "01000c80c4814b00080a0116f95a330000050119080000000000000000111900"
        "7000610079006c006f00610064002e007000640066000000150601002080ff81"
        "0000"
    ),
    "PPMd7": bytes.fromhex(
        "377abcaf271c000497dc5f5ab0000000000000007200000000000000ff37ad47"
        "9026df5f6934a50dd91dd91beb231cec8e86aa87a0c82a491531113b6f0237ff"
        "1bf26d20ecc5d2f3d0dd6326f59d8a253e7bd914eb45f88df46d16c7c5bfc14"
        "d878e496015a0b6a157a32431b8e042d2e484c7b6cecb14f6fc851a89c3e32a"
        "133514690ceb9425496af36acf0d6f1792839e63b5739101924c443a59ecff794"
        "5d5dd97e64daefd872899ee5943204a54c33624e59eddef0c27ce210554e1093"
        "d061360975c21a31e7239abea56929d5401040600010980b000070b0100022406"
        "f1070112530fe2af0407bf4fe1e86fff5bdffe4cb89c23030401052000000100"
        "01000c80ac814b00080a0116f95a330000050119080000000000000000111900"
        "7000610079006c006f00610064002e007000640066000000150601002080ff81"
        "0000"
    ),
    "BZip2": bytes.fromhex(
        "377abcaf271c00047aabd98ff00000000000000062000000000000005e7b7915"
        "2745c196c2a0d8f4b580861e878de2de0b1b72be381b0f999c2a5df09b00d273"
        "3a152a56fb93b8068fde45f8e87fb8dabe86dd57d454af10e25211b585fdb7e2"
        "5ab1c7699726ffe63b55afcdf261eda10dfb720f8b784e812936d0b564eae661"
        "05702b92f87dac2d5cfb4fd2f2e1df53abc12a166e19f052668472fc76ca6e98"
        "3feded0eaebf01cc0883a745b2d617a629d70e89a549db848473a459b61d4560"
        "57c20a118b1b48d0724567a1ce893d205bcc83bea501825da6d9b645013d9e97"
        "e2c7fabda62e06e62c3ce3619ee9e9b86dcf5db541e67ecd330ce0c76f95253"
        "80ff7463a3140b8dd9c543712079c93cf01040600010980f000070b0100022406"
        "f1070112530f8c6425d1f4b6b4d43fab81f6f6986cc90304020201000c80ef81"
        "4b00080a0116f95a33000005011119007000610079006c006f00610064002e00"
        "7000640066000000150601002080ff810000"
    ),
    "Deflate": bytes.fromhex(
        "377abcaf271c000430e5466fd0000000000000006200000000000000f613a639"
        "f291aad736bf83c5ff91401f1e083028bff8ee9f687b3fe80af7104e00b3e6eb"
        "5974f129cf5d025fd4709460eaac8e465b11efc769d2b4e3e73c6685274e838c"
        "36d83b9ebd39ef66d618de4405b8f20c74350b9241dee033835288a24bbfcb66"
        "aa71942635042651e8939808c6d83cdca553cee7d36baa065c0fd3688905adabe"
        "952c36f12c3328bc8af4e4bc1a5ae1670c18d6c5649af08550b1dca96bdda44"
        "a6b79d23bbc8b75cb3a11786a567a0e3d52288dc5acd86924fb4097aa519c444"
        "0d4afe601c1c0d7f5303dfe36f8e6a5e01040600010980d000070b0100022406"
        "f1070112530f9d87d4793fc7faa04aff94933c0066250304010801000c80c481"
        "4b00080a0116f95a33000005011119007000610079006c006f00610064002e00"
        "7000640066000000150601002080ff810000"
    ),
    "Deflate64": bytes.fromhex(
        "377abcaf271c00041f660d3fd00000000000000062000000000000008f5ed6e2"
        "0445fd98a93cd3b62236769054d7cf40aaecd080e47be77aad5f72f042c535d0"
        "63ab3329b9c64e6ba4ab5d4ac710b74f5b99879a8ce2b305bd5301cb7c31c552"
        "494f29f3794860f555f4496bbc67444eddcaba0c6042de3abf979c13396311bf"
        "27394ac9687c257b131bad81d3025acf2d5f56a942187b6b225244fac13456b0"
        "9ebef977efd9315bf6789097755b9e5ea08bf113ab27949a72cb843bc445c8cdb"
        "f31a115184d787ad45b1a8ccbeed73cb40ea47a192e9651096c7df6579b7e515"
        "1c1fe99ef724118cca356423e61319101040600010980d000070b0100022406f1"
        "070112530f69fb0bba324831d240737239244f7a980304010901000c80c4814b"
        "00080a0116f95a33000005011119007000610079006c006f00610064002e0070"
        "00640066000000150601002080ff810000"
    ),
}


def sevenzip_uint64(value: int) -> bytes:
    if not 0 <= value <= 0xFFFFFFFFFFFFFFFF:
        raise ValueError("7Z UINT64 is out of range")
    for extra_bytes in range(8):
        value_bits = 7 + 7 * extra_bytes
        if value < (1 << value_bits):
            prefix = (0xFF << (8 - extra_bytes)) & 0xFF
            high = value >> (8 * extra_bytes)
            first = prefix | high
            low = value & ((1 << (8 * extra_bytes)) - 1)
            return bytes((first,)) + low.to_bytes(extra_bytes, "little")
    return b"\xff" + value.to_bytes(8, "little")


SEVENZIP_DICTIONARY_SIZE = 1 << 20
SEVENZIP_CODER_IDS = {
    "Copy": b"\x00",
    "LZMA": b"\x03\x01\x01",
    "LZMA2": b"\x21",
    "PPMd7": b"\x03\x04\x01",
    "BZip2": b"\x04\x02\x02",
    "Deflate": b"\x04\x01\x08",
    "Deflate64": b"\x04\x01\x09",
    "BCJ": b"\x03\x03\x01\x03",
    "BCJ2": b"\x03\x03\x01\x1b",
    "ARM64-BCJ": b"\x0a",
}


class BitWriter:
    def __init__(self) -> None:
        self._value = 0
        self._count = 0
        self._output = bytearray()

    def write(self, value: int, count: int) -> None:
        self._value |= value << self._count
        self._count += count
        while self._count >= 8:
            self._output.append(self._value & 0xFF)
            self._value >>= 8
            self._count -= 8

    def finish(self) -> bytes:
        if self._count:
            self._output.append(self._value & 0xFF)
        return bytes(self._output)


def reverse_bits(value: int, count: int) -> int:
    result = 0
    for _ in range(count):
        result = (result << 1) | (value & 1)
        value >>= 1
    return result


def fixed_literal_code(symbol: int) -> tuple[int, int]:
    if 0 <= symbol <= 143:
        return reverse_bits(0x30 + symbol, 8), 8
    if 144 <= symbol <= 255:
        return reverse_bits(0x190 + symbol - 144, 9), 9
    if 256 <= symbol <= 279:
        return reverse_bits(symbol - 256, 7), 7
    if 280 <= symbol <= 287:
        return reverse_bits(0xC0 + symbol - 280, 8), 8
    raise ValueError("fixed Huffman symbol is out of range")


def encode_deflate64_distance_vector(payload: bytes) -> bytes:
    prefix = payload[:DEFLATE64_DISTANCE]
    if (
        len(payload) != DEFLATE64_DISTANCE + 3
        or payload[DEFLATE64_DISTANCE:] != prefix[:3]
    ):
        raise ValueError("unexpected Deflate64 distance vector payload")

    writer = BitWriter()
    writer.write(1, 1)  # BFINAL
    writer.write(1, 2)  # BTYPE=fixed Huffman
    for value in prefix:
        code, count = fixed_literal_code(value)
        writer.write(code, count)

    code, count = fixed_literal_code(257)  # length 3
    writer.write(code, count)
    writer.write(reverse_bits(30, 5), 5)
    writer.write(0, 14)  # distance code 30 base: 32769
    code, count = fixed_literal_code(256)  # end of block
    writer.write(code, count)
    packed = writer.finish()

    try:
        import inflate64
    except ImportError as error:
        raise RuntimeError(
            "Deflate64 fixture generation requires "
            "tools/corpus/requirements-archive-format.txt"
        ) from error
    actual_version = importlib.metadata.version("inflate64")
    if actual_version != INFLATE64_VERSION:
        raise RuntimeError(
            f"expected inflate64 {INFLATE64_VERSION}, "
            f"got {actual_version}"
        )
    decoder = inflate64.Inflater()
    if decoder.inflate(packed) != payload or not decoder.eof:
        raise RuntimeError("generated Deflate64 vector did not round-trip")
    return packed


def encode_ppmd7(payload: bytes) -> tuple[bytes, bytes]:
    try:
        import pyppmd
    except ImportError as error:
        raise RuntimeError(
            "PPMd7 fixture generation requires "
            "tools/corpus/requirements-archive-format.txt"
        ) from error
    actual_version = importlib.metadata.version("pyppmd")
    if actual_version != PYPPMD_VERSION:
        raise RuntimeError(
            f"expected pyppmd {PYPPMD_VERSION}, got {actual_version}"
        )
    encoder = pyppmd.Ppmd7Encoder(
        PPMD7_ORDER,
        PPMD7_MEMORY_SIZE,
    )
    packed = encoder.encode(payload) + encoder.flush()
    properties = bytes((PPMD7_ORDER,)) + struct.pack(
        "<I",
        PPMD7_MEMORY_SIZE,
    )
    return packed, properties


def encode_7z_payload(
    method: str,
    payload: bytes,
) -> tuple[bytes, bytes]:
    if method == "Copy":
        return payload, b""
    if method == "LZMA":
        properties = b"\x5d" + struct.pack(
            "<I",
            SEVENZIP_DICTIONARY_SIZE,
        )
        packed = lzma.compress(
            payload,
            format=lzma.FORMAT_RAW,
            filters=[
                {
                    "id": lzma.FILTER_LZMA1,
                    "dict_size": SEVENZIP_DICTIONARY_SIZE,
                    "lc": 3,
                    "lp": 0,
                    "pb": 2,
                }
            ],
        )
        return packed, properties
    if method == "LZMA2":
        packed = lzma.compress(
            payload,
            format=lzma.FORMAT_RAW,
            filters=[
                {
                    "id": lzma.FILTER_LZMA2,
                    "dict_size": SEVENZIP_DICTIONARY_SIZE,
                }
            ],
        )
        return packed, b"\x10"
    if method == "PPMd7":
        return encode_ppmd7(payload)
    if method == "BZip2":
        return bz2.compress(payload, compresslevel=9), b""
    if method == "Deflate":
        compressor = zlib.compressobj(level=9, wbits=-15)
        return compressor.compress(payload) + compressor.flush(), b""
    if method == "Deflate64":
        return encode_deflate64_distance_vector(payload), b""
    raise ValueError(f"unsupported 7Z method: {method}")


def make_7z_single(name: str, payload: bytes, method: str) -> bytes:
    encoded_name = name.encode("utf-16le") + b"\0\0"
    payload_crc = binascii.crc32(payload) & 0xFFFFFFFF
    packed, properties = encode_7z_payload(method, payload)
    packed_crc = binascii.crc32(packed) & 0xFFFFFFFF
    method_id = SEVENZIP_CODER_IDS[method]
    coder = bytes(
        (len(method_id) | (0x20 if properties else 0),)
    ) + method_id
    if properties:
        coder += sevenzip_uint64(len(properties)) + properties

    pack_info = (
        b"\x06"
        + sevenzip_uint64(0)
        + sevenzip_uint64(1)
        + b"\x09"
        + sevenzip_uint64(len(packed))
        + b"\x0a\x01"
        + struct.pack("<I", packed_crc)
        + b"\x00"
    )
    unpack_info = (
        b"\x07\x0b"
        + sevenzip_uint64(1)
        + b"\x00"
        + sevenzip_uint64(1)
        + coder
        + b"\x0c"
        + sevenzip_uint64(len(payload))
        + b"\x0a\x01"
        + struct.pack("<I", payload_crc)
        + b"\x00"
    )
    main_streams = b"\x04" + pack_info + unpack_info + b"\x00"
    name_property = b"\x00" + encoded_name
    files_info = (
        b"\x05"
        + sevenzip_uint64(1)
        + b"\x11"
        + sevenzip_uint64(len(name_property))
        + name_property
        + b"\x00"
    )
    next_header = b"\x01" + main_streams + files_info + b"\x00"
    start_header = struct.pack(
        "<QQI",
        len(packed),
        len(next_header),
        binascii.crc32(next_header) & 0xFFFFFFFF,
    )
    return (
        b"7z\xbc\xaf\x27\x1c"
        + b"\x00\x04"
        + struct.pack(
            "<I",
            binascii.crc32(start_header) & 0xFFFFFFFF,
        )
        + start_header
        + packed
        + next_header
    )


def make_7z_stored(name: str, payload: bytes) -> bytes:
    return make_7z_single(name, payload, "Copy")


def arm64_bcj_encode(payload: bytes) -> bytes:
    result = bytearray(payload)
    aligned_size = len(result) & ~3
    flag = 1 << 20
    mask = (1 << 24) - (flag << 1)
    for offset in range(0, aligned_size, 4):
        value = int.from_bytes(result[offset : offset + 4], "little")
        if ((value - 0x94000000) & 0xFC000000) == 0:
            value = (
                ((value + (offset >> 2)) & 0x03FFFFFF)
                | 0x94000000
            )
            result[offset : offset + 4] = value.to_bytes(4, "little")
            continue
        transformed = (value - 0x90000000) & 0xFFFFFFFF
        if (transformed & 0x9F000000) != 0:
            continue
        transformed = (transformed + flag) & 0xFFFFFFFF
        if transformed & mask:
            continue
        packed = (
            (transformed & 0xFFFFFFE0) | (transformed >> 26)
        )
        packed = (packed + ((offset >> 9) & ~7)) & 0xFFFFFFFF
        value = value & 0x1F
        value |= 0x90000000
        value |= (packed << 26) & 0xFFFFFFFF
        value |= 0x00FFFFE0 & (
            ((packed & ((flag << 1) - 1)) - flag)
            & 0xFFFFFFFF
        )
        result[offset : offset + 4] = (
            value & 0xFFFFFFFF
        ).to_bytes(4, "little")
    return bytes(result)


def arm64_bcj_decode(payload: bytes) -> bytes:
    result = bytearray(payload)
    aligned_size = len(result) & ~3
    flag = 1 << 20
    mask = (1 << 24) - (flag << 1)
    for offset in range(0, aligned_size, 4):
        value = int.from_bytes(result[offset : offset + 4], "little")
        if ((value - 0x94000000) & 0xFC000000) == 0:
            value = (
                ((value - (offset >> 2)) & 0x03FFFFFF)
                | 0x94000000
            )
            result[offset : offset + 4] = value.to_bytes(4, "little")
            continue
        transformed = (value - 0x90000000) & 0xFFFFFFFF
        if (transformed & 0x9F000000) != 0:
            continue
        transformed = (transformed + flag) & 0xFFFFFFFF
        if transformed & mask:
            continue
        packed = (
            (transformed & 0xFFFFFFE0) | (transformed >> 26)
        )
        packed = (packed - ((offset >> 9) & ~7)) & 0xFFFFFFFF
        value = value & 0x1F
        value |= 0x90000000
        value |= (packed << 26) & 0xFFFFFFFF
        value |= 0x00FFFFE0 & (
            ((packed & ((flag << 1) - 1)) - flag)
            & 0xFFFFFFFF
        )
        result[offset : offset + 4] = (
            value & 0xFFFFFFFF
        ).to_bytes(4, "little")
    return bytes(result)


def make_7z_filter_lzma2(
    name: str,
    payload: bytes,
    filter_method: str,
) -> bytes:
    encoded_name = name.encode("utf-16le") + b"\0\0"
    payload_crc = binascii.crc32(payload) & 0xFFFFFFFF
    if filter_method == "BCJ":
        packed = lzma.compress(
            payload,
            format=lzma.FORMAT_RAW,
            filters=[
                {"id": lzma.FILTER_X86},
                {
                    "id": lzma.FILTER_LZMA2,
                    "dict_size": SEVENZIP_DICTIONARY_SIZE,
                },
            ],
        )
    elif filter_method == "ARM64-BCJ":
        filtered = arm64_bcj_encode(payload)
        packed = lzma.compress(
            filtered,
            format=lzma.FORMAT_RAW,
            filters=[
                {
                    "id": lzma.FILTER_LZMA2,
                    "dict_size": SEVENZIP_DICTIONARY_SIZE,
                },
            ],
        )
    else:
        raise ValueError(f"unsupported 7Z filter: {filter_method}")
    packed_crc = binascii.crc32(packed) & 0xFFFFFFFF

    lzma2_id = SEVENZIP_CODER_IDS["LZMA2"]
    lzma2_coder = (
        bytes((len(lzma2_id) | 0x20,))
        + lzma2_id
        + sevenzip_uint64(1)
        + b"\x10"
    )
    filter_id = SEVENZIP_CODER_IDS[filter_method]
    filter_coder = bytes((len(filter_id),)) + filter_id
    folder = (
        sevenzip_uint64(2)
        + lzma2_coder
        + filter_coder
        # Filter input stream 1 is bound to LZMA2 output stream 0.
        + sevenzip_uint64(1)
        + sevenzip_uint64(0)
    )

    pack_info = (
        b"\x06"
        + sevenzip_uint64(0)
        + sevenzip_uint64(1)
        + b"\x09"
        + sevenzip_uint64(len(packed))
        + b"\x0a\x01"
        + struct.pack("<I", packed_crc)
        + b"\x00"
    )
    unpack_info = (
        b"\x07\x0b"
        + sevenzip_uint64(1)
        + b"\x00"
        + folder
        + b"\x0c"
        + sevenzip_uint64(len(payload))
        + sevenzip_uint64(len(payload))
        + b"\x0a\x01"
        + struct.pack("<I", payload_crc)
        + b"\x00"
    )
    main_streams = b"\x04" + pack_info + unpack_info + b"\x00"
    name_property = b"\x00" + encoded_name
    files_info = (
        b"\x05"
        + sevenzip_uint64(1)
        + b"\x11"
        + sevenzip_uint64(len(name_property))
        + name_property
        + b"\x00"
    )
    next_header = b"\x01" + main_streams + files_info + b"\x00"
    start_header = struct.pack(
        "<QQI",
        len(packed),
        len(next_header),
        binascii.crc32(next_header) & 0xFFFFFFFF,
    )
    return (
        b"7z\xbc\xaf\x27\x1c"
        + b"\x00\x04"
        + struct.pack(
            "<I",
            binascii.crc32(start_header) & 0xFFFFFFFF,
        )
        + start_header
        + packed
        + next_header
    )


def make_7z_bcj_lzma2(name: str, payload: bytes) -> bytes:
    return make_7z_filter_lzma2(name, payload, "BCJ")


def has_bcj2_candidate(payload: bytes) -> bool:
    previous = 0
    for value in payload:
        if (
            value in (0xE8, 0xE9)
            or (previous == 0x0F and (value & 0xF0) == 0x80)
        ):
            return True
        previous = value
    return False


def encode_bcj2_streams(
    payload: bytes,
    branch_kind: str,
) -> tuple[bytes, bytes, bytes, bytes]:
    if branch_kind == "control":
        if has_bcj2_candidate(payload):
            raise ValueError(
                "BCJ2 control payload contains a branch candidate"
            )
        return payload, b"", b"", b"\0" * 5
    if branch_kind in ("e8", "e9"):
        prefix = payload[:-5]
        opcode = 0xE8 if branch_kind == "e8" else 0xE9
        if (
            len(payload) < 5
            or has_bcj2_candidate(prefix)
            or payload[-5] != opcode
        ):
            raise ValueError(
                f"unexpected BCJ2 {branch_kind.upper()} payload"
            )
        relative = int.from_bytes(payload[-4:], "little")
        output_position_after_opcode = len(prefix) + 1
        absolute = (
            relative + output_position_after_opcode + 4
        ) & 0xFFFFFFFF
        address = absolute.to_bytes(4, "big")
        return (
            prefix + bytes((opcode,)),
            address if branch_kind == "e8" else b"",
            address if branch_kind == "e9" else b"",
            b"\x00\x7f\xff\xfc\x00",
        )
    if branch_kind == "jcc":
        prefix = payload[:-6]
        opcodes = payload[-6:-4]
        if (
            len(payload) < 6
            or has_bcj2_candidate(prefix)
            or len(opcodes) != 2
            or opcodes[0] != 0x0F
            or (opcodes[1] & 0xF0) != 0x80
        ):
            raise ValueError("unexpected BCJ2 JCC payload")
        relative = int.from_bytes(payload[-4:], "little")
        output_position_after_opcodes = len(prefix) + 2
        absolute = (
            relative + output_position_after_opcodes + 4
        ) & 0xFFFFFFFF
        return (
            prefix + opcodes,
            b"",
            absolute.to_bytes(4, "big"),
            b"\x00\x7f\xff\xfc\x00",
        )
    raise ValueError(f"unsupported BCJ2 branch kind: {branch_kind}")


def make_7z_bcj2_lzma2(
    name: str,
    payload: bytes,
    branch_kind: str,
) -> bytes:
    encoded_name = name.encode("utf-16le") + b"\0\0"
    payload_crc = binascii.crc32(payload) & 0xFFFFFFFF
    main, call, jump, range_stream = encode_bcj2_streams(
        payload,
        branch_kind,
    )
    main_packed = lzma.compress(
        main,
        format=lzma.FORMAT_RAW,
        filters=[
            {
                "id": lzma.FILTER_LZMA2,
                "dict_size": 1 << 12,
            }
        ],
    )
    packed_streams = (
        main_packed,
        call,
        jump,
        range_stream,
    )
    packed = b"".join(packed_streams)

    bcj2_id = SEVENZIP_CODER_IDS["BCJ2"]
    bcj2_coder = (
        bytes((0x10 | len(bcj2_id),))
        + bcj2_id
        + sevenzip_uint64(4)
        + sevenzip_uint64(1)
    )
    lzma2_id = SEVENZIP_CODER_IDS["LZMA2"]
    lzma2_coder = (
        bytes((len(lzma2_id) | 0x20,))
        + lzma2_id
        + sevenzip_uint64(1)
        + b"\x00"
    )
    folder = (
        sevenzip_uint64(2)
        + lzma2_coder
        + bcj2_coder
        # BCJ2 main input 1 is produced by LZMA2 output 0.
        + sevenzip_uint64(1)
        + sevenzip_uint64(0)
        # Packed inputs 0, 2, 3, 4: LZMA2 main, call, jump, range.
        + sevenzip_uint64(0)
        + sevenzip_uint64(2)
        + sevenzip_uint64(3)
        + sevenzip_uint64(4)
    )

    pack_info = (
        b"\x06"
        + sevenzip_uint64(0)
        + sevenzip_uint64(len(packed_streams))
        + b"\x09"
        + b"".join(
            sevenzip_uint64(len(stream))
            for stream in packed_streams
        )
        + b"\x00"
    )
    unpack_info = (
        b"\x07\x0b"
        + sevenzip_uint64(1)
        + b"\x00"
        + folder
        + b"\x0c"
        + sevenzip_uint64(len(main))
        + sevenzip_uint64(len(payload))
        + b"\x00"
    )
    substreams_info = (
        b"\x08\x0a\x01"
        + struct.pack("<I", payload_crc)
        + b"\x00"
    )
    main_streams = (
        b"\x04" + pack_info + unpack_info + substreams_info + b"\x00"
    )
    name_property = b"\x00" + encoded_name
    files_info = (
        b"\x05"
        + sevenzip_uint64(1)
        + b"\x11"
        + sevenzip_uint64(len(name_property))
        + name_property
        + b"\x00"
    )
    next_header = b"\x01" + main_streams + files_info + b"\x00"
    start_header = struct.pack(
        "<QQI",
        len(packed),
        len(next_header),
        binascii.crc32(next_header) & 0xFFFFFFFF,
    )
    return (
        b"7z\xbc\xaf\x27\x1c"
        + b"\x00\x04"
        + struct.pack(
            "<I",
            binascii.crc32(start_header) & 0xFFFFFFFF,
        )
        + start_header
        + packed
        + next_header
    )


def make_7z_bcj2_lzma2_control(name: str, payload: bytes) -> bytes:
    return make_7z_bcj2_lzma2(
        name,
        payload,
        "control",
    )


def make_7z_bcj2_lzma2_e8(name: str, payload: bytes) -> bytes:
    return make_7z_bcj2_lzma2(
        name,
        payload,
        "e8",
    )


def make_7z_bcj2_lzma2_e9(name: str, payload: bytes) -> bytes:
    return make_7z_bcj2_lzma2(
        name,
        payload,
        "e9",
    )


def make_7z_bcj2_lzma2_jcc(name: str, payload: bytes) -> bytes:
    return make_7z_bcj2_lzma2(
        name,
        payload,
        "jcc",
    )


def make_7z_arm64_bcj_lzma2(name: str, payload: bytes) -> bytes:
    return make_7z_filter_lzma2(name, payload, "ARM64-BCJ")


def make_7z_lzma2_aes(name: str, payload: bytes) -> bytes:
    if name != PAYLOAD_NAME or payload != PDF:
        raise ValueError(
            "7Z LZMA2+AES fixture requires the canonical PDF"
        )
    return SEVENZIP_LZMA2_AES_PDF_ARCHIVE


def make_7z_bcj2_lzma2_aes(name: str, payload: bytes) -> bytes:
    if name != PAYLOAD_NAME or payload != PDF:
        raise ValueError(
            "7Z BCJ2+LZMA2+AES fixture requires the canonical PDF"
        )
    return SEVENZIP_BCJ2_LZMA2_AES_PDF_ARCHIVE


def make_7z_bcj_lzma2_aes(name: str, payload: bytes) -> bytes:
    if name != PAYLOAD_NAME or payload != PDF:
        raise ValueError(
            "7Z BCJ+LZMA2+AES fixture requires the canonical PDF"
        )
    return SEVENZIP_BCJ_LZMA2_AES_PDF_ARCHIVE


def make_7z_arm64_lzma2_aes(name: str, payload: bytes) -> bytes:
    if name != PAYLOAD_NAME or payload != PDF:
        raise ValueError(
            "7Z ARM64+LZMA2+AES fixture requires the canonical PDF"
        )
    return SEVENZIP_ARM64_LZMA2_AES_PDF_ARCHIVE


def make_7z_base_aes(name: str, payload: bytes, method: str) -> bytes:
    if method not in SEVENZIP_BASE_AES_PDF_ARCHIVES:
        raise ValueError(f"unsupported 7Z AES base method: {method}")
    if name != PAYLOAD_NAME or payload != PDF:
        raise ValueError(
            f"7Z {method}+AES fixture requires the canonical PDF"
        )
    return SEVENZIP_BASE_AES_PDF_ARCHIVES[method]


def make_7z_copy_aes(name: str, payload: bytes) -> bytes:
    return make_7z_base_aes(name, payload, "Copy")


def make_7z_lzma_aes(name: str, payload: bytes) -> bytes:
    return make_7z_base_aes(name, payload, "LZMA")


def make_7z_ppmd7_aes(name: str, payload: bytes) -> bytes:
    return make_7z_base_aes(name, payload, "PPMd7")


def make_7z_bzip2_aes(name: str, payload: bytes) -> bytes:
    return make_7z_base_aes(name, payload, "BZip2")


def make_7z_deflate_aes(name: str, payload: bytes) -> bytes:
    return make_7z_base_aes(name, payload, "Deflate")


def make_7z_deflate64_aes(name: str, payload: bytes) -> bytes:
    return make_7z_base_aes(name, payload, "Deflate64")


def rar4_header(block_type: int, flags: int, body: bytes) -> bytes:
    header_size = 7 + len(body)
    protected = struct.pack("<BHH", block_type, flags, header_size) + body
    crc16 = binascii.crc32(protected) & 0xFFFF
    return struct.pack("<H", crc16) + protected


def make_rar4_stored(name: str, payload: bytes) -> bytes:
    encoded_name = name.encode("ascii")
    signature = b"Rar!\x1a\x07\x00"
    main = rar4_header(0x73, 0, b"\0" * 6)
    file_body = struct.pack(
        "<IIBIIBBHI",
        len(payload),
        len(payload),
        3,
        binascii.crc32(payload) & 0xFFFFFFFF,
        0,
        20,
        0x30,
        len(encoded_name),
        0x20,
    ) + encoded_name
    file_header = rar4_header(0x74, 0x8000, file_body)
    end = rar4_header(0x7B, 0, b"")
    return signature + main + file_header + payload + end


def make_cab_single(
    name: str,
    payload: bytes,
    method: str,
) -> bytes:
    encoded_name = name.encode("ascii") + b"\0"
    data_checksum = 0
    file_date = 0x0021
    file_time = 0
    set_id = 0xD1EC
    if method == "Store":
        compressed = payload
        compression_type = 0
    elif method == "MSZIP":
        compressor = zlib.compressobj(level=9, wbits=-15)
        compressed = b"CK" + (
            compressor.compress(payload) + compressor.flush()
        )
        compression_type = 1
    elif method == "LZX15":
        if payload != PDF:
            raise ValueError("CAB LZX15 fixture requires the canonical PDF")
        compressed = CAB_LZX15_PDF_STREAM
        compression_type = 0x0F03
        data_checksum = 0x715EAFFD
        file_date = 0x5022
        file_time = 0x1883
        set_id = 0
    elif method == "Quantum18":
        if payload != QTM_PAYLOAD:
            raise ValueError(
                "CAB Quantum18 fixture requires the canonical text"
            )
        compressed = CAB_QUANTUM18_TEXT_STREAM
        compression_type = 0x1222
    else:
        raise ValueError(f"unsupported CAB method: {method}")
    header_size = 36
    folder_size = 8
    file_entry = struct.pack(
        "<IIHHHH",
        len(payload),
        0,
        0,
        file_date,
        file_time,
        0x20,
    ) + encoded_name
    files_offset = header_size + folder_size
    data_offset = files_offset + len(file_entry)
    data_block = struct.pack(
        "<IHH",
        data_checksum,
        len(compressed),
        len(payload),
    ) + compressed
    cabinet_size = data_offset + len(data_block)
    header = struct.pack(
        "<4sIIIIIBBHHHHH",
        b"MSCF",
        0,
        cabinet_size,
        0,
        files_offset,
        0,
        3,
        1,
        1,
        1,
        0,
        set_id,
        0,
    )
    folder = struct.pack(
        "<IHH",
        data_offset,
        1,
        compression_type,
    )
    return header + folder + file_entry + data_block


def make_cab_stored(name: str, payload: bytes) -> bytes:
    return make_cab_single(name, payload, "Store")


def make_cab_mszip(name: str, payload: bytes) -> bytes:
    return make_cab_single(name, payload, "MSZIP")


def make_cab_lzx15(name: str, payload: bytes) -> bytes:
    return make_cab_single(name, payload, "LZX15")


def make_cab_quantum18(name: str, payload: bytes) -> bytes:
    return make_cab_single(name, payload, "Quantum18")


def both16(value: int) -> bytes:
    return struct.pack("<H", value) + struct.pack(">H", value)


def both32(value: int) -> bytes:
    return struct.pack("<I", value) + struct.pack(">I", value)


def iso_directory_record(
    extent: int,
    size: int,
    name: bytes,
    *,
    directory: bool,
) -> bytes:
    length = 33 + len(name)
    if len(name) % 2 == 0:
        length += 1
    record = bytearray(length)
    record[0] = length
    record[2:10] = both32(extent)
    record[10:18] = both32(size)
    record[18:25] = bytes((126, 1, 1, 0, 0, 0, 0))
    record[25] = 0x02 if directory else 0
    record[28:32] = both16(1)
    record[32] = len(name)
    record[33 : 33 + len(name)] = name
    return bytes(record)


def make_iso9660_stored(name: str, payload: bytes) -> bytes:
    block_size = 2048
    volume_blocks = 21
    root_block = 19
    payload_block = 20
    image = bytearray(volume_blocks * block_size)

    pvd = memoryview(image)[16 * block_size : 17 * block_size]
    pvd[0] = 1
    pvd[1:6] = b"CD001"
    pvd[6] = 1
    pvd[8:40] = b"DIEC-RUST".ljust(32, b" ")
    pvd[40:72] = b"ARCHIVE-FORMAT".ljust(32, b" ")
    pvd[80:88] = both32(volume_blocks)
    pvd[120:124] = both16(1)
    pvd[124:128] = both16(1)
    pvd[128:132] = both16(block_size)
    pvd[132:140] = both32(10)
    pvd[140:144] = struct.pack("<I", 18)
    pvd[148:152] = struct.pack(">I", 18)
    root_record = iso_directory_record(
        root_block,
        block_size,
        b"\0",
        directory=True,
    )
    pvd[156 : 156 + len(root_record)] = root_record
    pvd[881] = 1

    terminator = memoryview(image)[17 * block_size : 18 * block_size]
    terminator[0] = 255
    terminator[1:6] = b"CD001"
    terminator[6] = 1

    path_table = memoryview(image)[18 * block_size : 19 * block_size]
    path_table[0:10] = (
        b"\x01\x00"
        + struct.pack("<I", root_block)
        + struct.pack("<H", 1)
        + b"\0\0"
    )

    directory = memoryview(image)[
        root_block * block_size : (root_block + 1) * block_size
    ]
    records = (
        root_record,
        iso_directory_record(
            root_block,
            block_size,
            b"\x01",
            directory=True,
        ),
        iso_directory_record(
            payload_block,
            len(payload),
            (name.upper() + ";1").encode("ascii"),
            directory=False,
        ),
    )
    cursor = 0
    for record in records:
        directory[cursor : cursor + len(record)] = record
        cursor += len(record)
    image[
        payload_block * block_size :
        payload_block * block_size + len(payload)
    ] = payload
    return bytes(image)


FIXTURES = (
    (
        "pdf-member.7z",
        "7Z Copy-method archive containing one PDF",
        "Copy",
        make_7z_stored,
    ),
    (
        "pdf-member-lzma.7z",
        "7Z LZMA-method archive containing one PDF",
        "LZMA",
        lambda name, payload: make_7z_single(
            name,
            payload,
            "LZMA",
        ),
    ),
    (
        "pdf-member-lzma2.7z",
        "7Z LZMA2-method archive containing one PDF",
        "LZMA2",
        lambda name, payload: make_7z_single(
            name,
            payload,
            "LZMA2",
        ),
    ),
    (
        "pdf-member-lzma2-aes.7z",
        "7Z LZMA2 plus 7zAES archive containing one PDF",
        "LZMA2+7zAES",
        make_7z_lzma2_aes,
    ),
    (
        "pdf-member-copy-aes.7z",
        "7Z Copy plus 7zAES archive containing one PDF",
        "Copy+7zAES",
        make_7z_copy_aes,
    ),
    (
        "pdf-member-lzma-aes.7z",
        "7Z LZMA plus 7zAES archive containing one PDF",
        "LZMA+7zAES",
        make_7z_lzma_aes,
    ),
    (
        "pdf-member-ppmd7-aes.7z",
        "7Z PPMd7 plus 7zAES archive containing one PDF",
        "PPMd7+7zAES",
        make_7z_ppmd7_aes,
    ),
    (
        "pdf-member-bzip2-aes.7z",
        "7Z BZip2 plus 7zAES archive containing one PDF",
        "BZip2+7zAES",
        make_7z_bzip2_aes,
    ),
    (
        "pdf-member-deflate-aes.7z",
        "7Z Deflate plus 7zAES archive containing one PDF",
        "Deflate+7zAES",
        make_7z_deflate_aes,
    ),
    (
        "pdf-member-deflate64-aes.7z",
        "7Z Deflate64 plus 7zAES archive containing one PDF",
        "Deflate64+7zAES",
        make_7z_deflate64_aes,
    ),
    (
        "pdf-member-bcj2-lzma2-aes.7z",
        "7Z BCJ2 plus LZMA2 plus 7zAES archive containing one PDF",
        "BCJ2+LZMA2+7zAES",
        make_7z_bcj2_lzma2_aes,
    ),
    (
        "pdf-member-bcj-lzma2-aes.7z",
        "7Z x86 BCJ plus LZMA2 plus 7zAES archive containing one PDF",
        "BCJ+LZMA2+7zAES",
        make_7z_bcj_lzma2_aes,
    ),
    (
        "pdf-member-arm64-lzma2-aes.7z",
        "7Z ARM64 plus LZMA2 plus 7zAES archive containing one PDF",
        "ARM64+LZMA2+7zAES",
        make_7z_arm64_lzma2_aes,
    ),
    (
        "pdf-member-ppmd7.7z",
        "7Z PPMd7-method archive containing one PDF",
        "PPMd7",
        lambda name, payload: make_7z_single(
            name,
            payload,
            "PPMd7",
        ),
    ),
    (
        "pdf-member-bzip2.7z",
        "7Z BZip2-method archive containing one PDF",
        "BZip2",
        lambda name, payload: make_7z_single(
            name,
            payload,
            "BZip2",
        ),
    ),
    (
        "pdf-member-deflate.7z",
        "7Z Deflate-method archive containing one PDF",
        "Deflate",
        lambda name, payload: make_7z_single(
            name,
            payload,
            "Deflate",
        ),
    ),
    (
        "pdf-member-deflate64.7z",
        "7Z Deflate64 distance-32769 archive containing one PDF",
        "Deflate64",
        lambda name, payload: make_7z_single(
            name,
            payload,
            "Deflate64",
        ),
    ),
    (
        "pdf-member-bcj-lzma2.7z",
        "7Z x86 BCJ plus LZMA2 archive containing one PDF",
        "BCJ+LZMA2",
        make_7z_bcj_lzma2,
    ),
    (
        "pdf-member-bcj2-lzma2.7z",
        "7Z BCJ2 plus LZMA2 no-branch control containing one PDF",
        "BCJ2+LZMA2",
        make_7z_bcj2_lzma2_control,
    ),
    (
        "pdf-member-bcj2-e8-lzma2.7z",
        "7Z BCJ2 E8 plus LZMA2 archive containing one PDF",
        "BCJ2-E8+LZMA2",
        make_7z_bcj2_lzma2_e8,
    ),
    (
        "pdf-member-bcj2-e9-lzma2.7z",
        "7Z BCJ2 E9 plus LZMA2 archive containing one PDF",
        "BCJ2-E9+LZMA2",
        make_7z_bcj2_lzma2_e9,
    ),
    (
        "pdf-member-bcj2-jcc-lzma2.7z",
        "7Z BCJ2 JCC plus LZMA2 archive containing one PDF",
        "BCJ2-JCC+LZMA2",
        make_7z_bcj2_lzma2_jcc,
    ),
    (
        "pdf-member-arm64-bcj-lzma2.7z",
        "7Z ARM64 BCJ plus LZMA2 archive containing one PDF",
        "ARM64-BCJ+LZMA2",
        make_7z_arm64_bcj_lzma2,
    ),
    (
        "pdf-member.rar",
        "RAR4 store archive containing one PDF",
        "Store",
        make_rar4_stored,
    ),
    (
        "pdf-member.cab",
        "CAB store archive containing one PDF",
        "Store",
        make_cab_stored,
    ),
    (
        "pdf-member-mszip.cab",
        "CAB MSZIP archive containing one PDF",
        "MSZIP",
        make_cab_mszip,
    ),
    (
        "pdf-member-lzx.cab",
        "CAB LZX window-15 archive containing one PDF",
        "LZX15",
        make_cab_lzx15,
    ),
    (
        "text-member-quantum.cab",
        "CAB Quantum level/window 18 archive containing benign text",
        "Quantum18",
        make_cab_quantum18,
    ),
    (
        "pdf-member.iso",
        "ISO9660 image containing one PDF",
        "Store",
        make_iso9660_stored,
    ),
)


def sevenzip_aes_generation_provenance(
    archive_name: str,
    method_options: tuple[str, ...],
) -> dict[str, object]:
    return {
        "command": [
            "7zz",
            "a",
            archive_name,
            "payload.pdf",
            "-t7z",
            *method_options,
            "-pDetectItEasy",
            "-mhe=off",
            "-mtm=off",
            "-mtc=off",
            "-mta=off",
        ],
        "password": SEVENZIP_AES_PASSWORD,
        "payload_sha256": hashlib.sha256(PDF).hexdigest(),
        "tool": "7zz",
        "tool_archive_sha256": SEVENZIP_2602_ARCHIVE_SHA256,
        "tool_binary_sha256": SEVENZIP_2602_BINARY_SHA256,
        "tool_license": (
            "LGPL-2.1-or-later; unRAR restriction; "
            "BSD-2-Clause and BSD-3-Clause components"
        ),
        "tool_source": (
            "https://www.7-zip.org/a/7z2602-linux-x64.tar.xz"
        ),
        "tool_version": "26.02",
    }


def generate(output_dir: pathlib.Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    samples = []
    for name, purpose, compression_method, factory in FIXTURES:
        member_name = (
            QTM_PAYLOAD_NAME
            if compression_method == "Quantum18"
            else PAYLOAD_NAME
        )
        payload = (
            QTM_PAYLOAD
            if compression_method == "Quantum18"
            else (
                ARM64_PDF
                if compression_method == "ARM64-BCJ+LZMA2"
                else (
                    {
                        "BCJ2-E8+LZMA2": BCJ2_E8_PDF,
                        "BCJ2-E9+LZMA2": BCJ2_E9_PDF,
                        "BCJ2-JCC+LZMA2": BCJ2_JCC_PDF,
                    }[compression_method]
                    if compression_method
                    in {
                        "BCJ2-E8+LZMA2",
                        "BCJ2-E9+LZMA2",
                        "BCJ2-JCC+LZMA2",
                    }
                    else (
                        DEFLATE64_PDF
                        if compression_method == "Deflate64"
                        else PDF
                    )
                )
            )
        )
        data = factory(member_name, payload)
        (output_dir / name).write_bytes(data)
        samples.append(
            {
                "archive_format": name.rsplit(".", 1)[1].upper(),
                "compression_method": compression_method,
                "expected_member_name": member_name,
                "expected_payload_sha256": hashlib.sha256(payload).hexdigest(),
                "name": name,
                "purpose": purpose,
                "sha256": hashlib.sha256(data).hexdigest(),
                "size": len(data),
            }
        )
    manifest: dict[str, object] = {
        "schema_version": 3,
        "generator": GENERATOR,
        "generator_dependencies": {
            "inflate64": {
                "license": "LGPL-2.1-or-later",
                "version": INFLATE64_VERSION,
            },
            "pyppmd": {
                "license": "LGPL-2.1-or-later",
                "version": PYPPMD_VERSION,
            }
        },
        "license": (
            "project-generated except the attributed CAB Quantum "
            "compressed stream"
        ),
        "generation_provenance": {
            "sevenzip_bzip2_aes_archive": (
                sevenzip_aes_generation_provenance(
                    "pdf-member-bzip2-aes.7z",
                    ("-m0=BZip2", "-mx=9"),
                )
            ),
            "sevenzip_copy_aes_archive": (
                sevenzip_aes_generation_provenance(
                    "pdf-member-copy-aes.7z",
                    ("-m0=Copy",),
                )
            ),
            "sevenzip_deflate_aes_archive": (
                sevenzip_aes_generation_provenance(
                    "pdf-member-deflate-aes.7z",
                    ("-m0=Deflate", "-mx=9"),
                )
            ),
            "sevenzip_deflate64_aes_archive": (
                sevenzip_aes_generation_provenance(
                    "pdf-member-deflate64-aes.7z",
                    ("-m0=Deflate64", "-mx=9"),
                )
            ),
            "sevenzip_lzma_aes_archive": (
                sevenzip_aes_generation_provenance(
                    "pdf-member-lzma-aes.7z",
                    ("-m0=LZMA", "-mx=9"),
                )
            ),
            "sevenzip_ppmd7_aes_archive": (
                sevenzip_aes_generation_provenance(
                    "pdf-member-ppmd7-aes.7z",
                    ("-m0=PPMd", "-mx=9"),
                )
            ),
            "sevenzip_arm64_lzma2_aes_archive": {
                "command": [
                    "7zz",
                    "a",
                    "pdf-member-arm64-lzma2-aes.7z",
                    "payload.pdf",
                    "-t7z",
                    "-m0=ARM64",
                    "-m1=LZMA2",
                    "-mx=9",
                    "-pDetectItEasy",
                    "-mhe=off",
                    "-mtm=off",
                    "-mtc=off",
                    "-mta=off",
                ],
                "password": SEVENZIP_AES_PASSWORD,
                "payload_sha256": hashlib.sha256(PDF).hexdigest(),
                "tool": "7zz",
                "tool_archive_sha256": SEVENZIP_2602_ARCHIVE_SHA256,
                "tool_binary_sha256": SEVENZIP_2602_BINARY_SHA256,
                "tool_license": (
                    "LGPL-2.1-or-later; unRAR restriction; "
                    "BSD-2-Clause and BSD-3-Clause components"
                ),
                "tool_source": (
                    "https://www.7-zip.org/a/"
                    "7z2602-linux-x64.tar.xz"
                ),
                "tool_version": "26.02",
            },
            "sevenzip_bcj_lzma2_aes_archive": {
                "command": [
                    "7zz",
                    "a",
                    "pdf-member-bcj-lzma2-aes.7z",
                    "payload.pdf",
                    "-t7z",
                    "-m0=BCJ",
                    "-m1=LZMA2",
                    "-mx=9",
                    "-pDetectItEasy",
                    "-mhe=off",
                    "-mtm=off",
                    "-mtc=off",
                    "-mta=off",
                ],
                "password": SEVENZIP_AES_PASSWORD,
                "payload_sha256": hashlib.sha256(PDF).hexdigest(),
                "tool": "7zz",
                "tool_archive_sha256": SEVENZIP_2602_ARCHIVE_SHA256,
                "tool_binary_sha256": SEVENZIP_2602_BINARY_SHA256,
                "tool_license": (
                    "LGPL-2.1-or-later; unRAR restriction; "
                    "BSD-2-Clause and BSD-3-Clause components"
                ),
                "tool_source": (
                    "https://www.7-zip.org/a/"
                    "7z2602-linux-x64.tar.xz"
                ),
                "tool_version": "26.02",
            },
            "sevenzip_bcj2_lzma2_aes_archive": {
                "command": [
                    "7zz",
                    "a",
                    "pdf-member-bcj2-lzma2-aes.7z",
                    "payload.pdf",
                    "-t7z",
                    "-m0=BCJ2",
                    "-m1=LZMA2",
                    "-mx=9",
                    "-pDetectItEasy",
                    "-mhe=off",
                    "-mtm=off",
                    "-mtc=off",
                    "-mta=off",
                ],
                "password": SEVENZIP_AES_PASSWORD,
                "payload_sha256": hashlib.sha256(PDF).hexdigest(),
                "tool": "7zz",
                "tool_archive_sha256": SEVENZIP_2602_ARCHIVE_SHA256,
                "tool_binary_sha256": SEVENZIP_2602_BINARY_SHA256,
                "tool_license": (
                    "LGPL-2.1-or-later; unRAR restriction; "
                    "BSD-2-Clause and BSD-3-Clause components"
                ),
                "tool_source": (
                    "https://www.7-zip.org/a/"
                    "7z2602-linux-x64.tar.xz"
                ),
                "tool_version": "26.02",
            },
            "sevenzip_lzma2_aes_archive": {
                "command": [
                    "7zz",
                    "a",
                    "pdf-member-lzma2-aes.7z",
                    "payload.pdf",
                    "-t7z",
                    "-m0=LZMA2",
                    "-mx=9",
                    "-pDetectItEasy",
                    "-mhe=off",
                    "-mtm=off",
                    "-mtc=off",
                    "-mta=off",
                ],
                "password": SEVENZIP_AES_PASSWORD,
                "payload_sha256": hashlib.sha256(PDF).hexdigest(),
                "tool": "7zz",
                "tool_archive_sha256": SEVENZIP_2602_ARCHIVE_SHA256,
                "tool_binary_sha256": SEVENZIP_2602_BINARY_SHA256,
                "tool_license": (
                    "LGPL-2.1-or-later; unRAR restriction; "
                    "BSD-2-Clause and BSD-3-Clause components"
                ),
                "tool_source": (
                    "https://www.7-zip.org/a/"
                    "7z2602-linux-x64.tar.xz"
                ),
                "tool_version": "26.02",
            }
        },
        "third_party_inputs": {
            "cab_quantum_stream": {
                "commit": LIBMSPACK_COMMIT,
                "license": "LGPL-2.1-only",
                "path": LIBMSPACK_QTM_SOURCE_PATH,
                "repository": "https://github.com/kyz/libmspack",
                "source_sha256": LIBMSPACK_QTM_SOURCE_SHA256,
                "source_size": 379,
                "stream_offset": LIBMSPACK_QTM_STREAM_OFFSET,
                "stream_sha256": hashlib.sha256(
                    CAB_QUANTUM18_TEXT_STREAM
                ).hexdigest(),
                "stream_size": len(CAB_QUANTUM18_TEXT_STREAM),
            }
        },
        "samples": samples,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=pathlib.Path)
    args = parser.parse_args()
    manifest = generate(args.output_dir.resolve())
    sys.stdout.buffer.write(
        (
            json.dumps(manifest, indent=2, sort_keys=True)
            + "\n"
        ).encode("utf-8")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
