#!/usr/bin/env python3
"""Generate project-owned XBinary signature oracle vectors."""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path


SCHEMA_VERSION = 3
GENERATOR_VERSION = 12
UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
FORMATS_COMMIT = "1151e7254fdee3c0294ff7095edbdd7bfccf8201"
XSCANENGINE_COMMIT = "dfe4a419e4f491bb23688ba03c5a5bf39e34da83"


def mapped_pe32() -> bytes:
    image = bytearray(0x600)
    image[0:2] = b"MZ"
    struct.pack_into("<I", image, 0x3C, 0x80)
    image[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", image, 0x84, 0x14C, 2, 0, 0, 0, 224, 0x0102)
    optional = 0x98
    struct.pack_into("<H", image, optional, 0x10B)
    struct.pack_into("<I", image, optional + 16, 0x1000)
    struct.pack_into("<I", image, optional + 28, 0x400000)
    struct.pack_into("<II", image, optional + 32, 0x1000, 0x200)
    struct.pack_into("<II", image, optional + 56, 0x3000, 0x200)
    struct.pack_into("<H", image, optional + 68, 3)
    struct.pack_into("<I", image, optional + 92, 16)
    section = 0x178
    struct.pack_into(
        "<8sIIIIIIHHI",
        image,
        section,
        b".one\0\0\0\0",
        0x100,
        0x1000,
        0x200,
        0x200,
        0,
        0,
        0,
        0,
        0x60000020,
    )
    struct.pack_into(
        "<8sIIIIIIHHI",
        image,
        section + 40,
        b".two\0\0\0\0",
        0x100,
        0x2000,
        0x200,
        0x400,
        0,
        0,
        0,
        0,
        0x60000020,
    )
    image[0x200:0x205] = bytes.fromhex("e9fb0f0000")
    image[0x400] = 0x90
    return bytes(image)


def mapped_pe64() -> bytes:
    image = bytearray(0x600)
    image[0:2] = b"MZ"
    struct.pack_into("<I", image, 0x3C, 0x80)
    image[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", image, 0x84, 0x8664, 2, 0, 0, 0, 240, 0x0022)
    optional = 0x98
    struct.pack_into("<H", image, optional, 0x20B)
    struct.pack_into("<I", image, optional + 16, 0x1000)
    struct.pack_into("<Q", image, optional + 24, 0x140000000)
    struct.pack_into("<II", image, optional + 32, 0x1000, 0x200)
    struct.pack_into("<II", image, optional + 56, 0x3000, 0x200)
    struct.pack_into("<H", image, optional + 68, 3)
    struct.pack_into("<I", image, optional + 108, 16)
    section = 0x188
    for index, (name, virtual_address, raw_offset) in enumerate(
        ((b".one\0\0\0\0", 0x1000, 0x200), (b".two\0\0\0\0", 0x2000, 0x400))
    ):
        struct.pack_into(
            "<8sIIIIIIHHI",
            image,
            section + index * 40,
            name,
            0x100,
            virtual_address,
            0x200,
            raw_offset,
            0,
            0,
            0,
            0,
            0x60000020,
        )
    image[0x200:0x205] = bytes.fromhex("e9fb0f0000")
    image[0x400] = 0x90
    return bytes(image)


def mapped_pe32_with_overlay() -> bytes:
    image = bytearray(mapped_pe32())
    image.extend(bytes(0x200))
    image[0x200] = 0x41
    image[0x3FC:0x3FF] = b"AAA"
    image[0x600] = 0x41
    image[0x7FC:0x7FF] = b"AAA"
    return bytes(image)


def mapped_elf64() -> bytes:
    image = bytearray(0x200)
    ident = b"\x7fELF" + bytes((2, 1, 1, 0, 0)) + bytes(7)
    image[:64] = ident + struct.pack(
        "<HHIQQQIHHHHHH",
        3,
        62,
        1,
        0x400100,
        64,
        0,
        0,
        64,
        56,
        2,
        0,
        0,
        0,
    )
    struct.pack_into(
        "<IIQQQQQQ",
        image,
        64,
        1,
        5,
        0x100,
        0x400100,
        0x400100,
        0x20,
        0x20,
        1,
    )
    struct.pack_into(
        "<IIQQQQQQ",
        image,
        120,
        1,
        5,
        0x180,
        0x401000,
        0x401000,
        0x20,
        0x20,
        1,
    )
    image[0x100:0x105] = bytes.fromhex("e9fb0e0000")
    image[0x180] = 0x90
    return bytes(image)


def mapped_elf32() -> bytes:
    image = bytearray(0x200)
    ident = b"\x7fELF" + bytes((1, 1, 1, 0, 0)) + bytes(7)
    image[:52] = ident + struct.pack(
        "<HHIIIIIHHHHHH",
        3,
        3,
        1,
        0x8048100,
        52,
        0,
        0,
        52,
        32,
        2,
        0,
        0,
        0,
    )
    struct.pack_into(
        "<IIIIIIII",
        image,
        52,
        1,
        0x100,
        0x8048100,
        0x8048100,
        0x20,
        0x20,
        5,
        1,
    )
    struct.pack_into(
        "<IIIIIIII",
        image,
        84,
        1,
        0x180,
        0x8049000,
        0x8049000,
        0x20,
        0x20,
        5,
        1,
    )
    image[0x100:0x105] = bytes.fromhex("e9fb0e0000")
    image[0x180] = 0x90
    return bytes(image)


def mapped_macho64() -> bytes:
    image = bytearray(0x200)
    image[:32] = struct.pack(
        "<IiiIIIII",
        0xFEEDFACF,
        0x01000007,
        3,
        2,
        2,
        144,
        0,
        0,
    )
    image[32:104] = struct.pack(
        "<II16sQQQQiiII",
        0x19,
        72,
        b"__ONE" + bytes(11),
        0x100000100,
        0x20,
        0x100,
        0x20,
        7,
        5,
        0,
        1,
    )
    image[104:176] = struct.pack(
        "<II16sQQQQiiII",
        0x19,
        72,
        b"__TWO" + bytes(11),
        0x100001000,
        0x20,
        0x180,
        0x20,
        7,
        5,
        0,
        1,
    )
    image[0x100:0x109] = bytes.fromhex("680010000001000000")
    image[0x180] = 0x90
    return bytes(image)


def mapped_macho32() -> bytes:
    image = bytearray(0x200)
    image[:28] = struct.pack(
        "<IiiIIII",
        0xFEEDFACE,
        7,
        3,
        2,
        2,
        112,
        0,
    )
    image[28:84] = struct.pack(
        "<II16sIIIIiiII",
        1,
        56,
        b"__ONE" + bytes(11),
        0x01000100,
        0x20,
        0x100,
        0x20,
        7,
        5,
        0,
        1,
    )
    image[84:140] = struct.pack(
        "<II16sIIIIiiII",
        1,
        56,
        b"__TWO" + bytes(11),
        0x01001000,
        0x20,
        0x180,
        0x20,
        7,
        5,
        0,
        1,
    )
    image[0x100:0x105] = bytes.fromhex("6800100001")
    image[0x180] = 0x90
    return bytes(image)


def mapped_com() -> bytes:
    return bytes.fromhex("eb0090")


def mapped_msdos() -> bytes:
    image = bytearray(0x80)
    image[0:2] = b"MZ"
    struct.pack_into("<H", image, 2, 0x80)
    struct.pack_into("<H", image, 4, 1)
    struct.pack_into("<H", image, 8, 4)
    image[0x40:0x45] = bytes.fromhex("6803000200")
    image[0x63] = 0x90
    return bytes(image)


def mapped_amigahunk() -> bytes:
    words = [
        0x000003F3,
        0,
        1,
        0,
        0,
        4,
        0x000003E9,
        4,
        0xAA000400,
        0x00BB0000,
        0,
        0,
        0x000003F2,
    ]
    return b"".join(struct.pack(">I", word) for word in words)


def vectors() -> list[dict[str, object]]:
    return [
        {
            "id": "quoted_literal_and_wildcard_match",
            "pattern": " 7F 'ELF' ?? .. 01 ",
            "data_hex": "7f454c46aabb01",
        },
        {
            "id": "literal_mismatch",
            "pattern": "'MZ'",
            "data_hex": "4d00",
            "binary_script_find_signature": True,
            "binary_script_f_sig": True,
            "binary_script_is_signature_present": True,
        },
        {
            "id": "exact_match_at_eof",
            "pattern": "4142",
            "data_hex": "004142",
            "offset": 1,
        },
        {
            "id": "truncated_literal",
            "pattern": "4142",
            "data_hex": "41",
        },
        {
            "id": "all_byte_classes_match",
            "pattern": "**%%!%_%%&",
            "data_hex": "0141008037",
        },
        {
            "id": "decimal_class_rejects_letter",
            "pattern": "%&",
            "data_hex": "41",
        },
        {
            "id": "ansi_del_compare_find_divergence",
            "pattern": "%%",
            "data_hex": "7f",
        },
        {
            "id": "not_ansi_del_compare_find_divergence",
            "pattern": "!%",
            "data_hex": "7f",
        },
        {
            "id": "plain_find_clamps_oversized_range",
            "pattern": "41",
            "data_hex": "0041",
            "find_offset": 1,
            "find_size": 999,
            "binary_script_find_signature": True,
            "binary_script_f_sig": True,
            "binary_script_is_signature_present": True,
        },
        {
            "id": "binary_script_find_size_minus_one",
            "pattern": "4142",
            "data_hex": "00414200",
            "find_offset": 1,
            "find_size": -1,
            "binary_script_find_signature": True,
            "binary_script_f_sig": True,
            "binary_script_is_signature_present": True,
        },
        {
            "id": "sigbyte_fixed_anchor_rechecks_record_classes",
            "pattern": "%&%&%&414243",
            "data_hex": "414243414243",
        },
        {
            "id": "find_at_window_end",
            "pattern": "++'MZ'",
            "data_hex": ("00" * 64) + "4d5a",
            "binary_script_find_signature": True,
            "binary_script_f_sig": True,
            "binary_script_is_signature_present": True,
        },
        {
            "id": "find_outside_window",
            "pattern": "++'MZ'",
            "data_hex": ("00" * 65) + "4d5a",
        },
        {
            "id": "control_longest_literal_anchor",
            "pattern": "41....424344$$$$$$$$90",
            "data_hex": "4100004243440000000090",
        },
        {
            "id": "control_class_first_anchor",
            "pattern": "%&$$$$$$$$90",
            "data_hex": "370000000090",
        },
        {
            "id": "control_relative_first_fallback",
            "pattern": "$$$$$$$$90",
            "data_hex": "0000000090",
        },
        {
            "id": "relative_offset_little_endian",
            "pattern": "e9$$$$$$$$90",
            "data_hex": "e90000000090",
        },
        {
            "id": "absolute_address_identity_map",
            "pattern": "68########90",
            "data_hex": "680500000090",
        },
        {
            "id": "pe_relative_crosses_raw_gap",
            "pattern": "e9$$$$$$$$90",
            "data_hex": "e900000000" + ("00" * 11) + "90",
            "memory_map": {
                "file_type": "pe",
                "endian": "little",
                "records": [
                    {"offset": 0, "address": 0x401000, "size": 5},
                    {"offset": 16, "address": 0x401005, "size": 1},
                ],
            },
        },
        {
            "id": "elf_big_endian_relative_crosses_raw_gap",
            "pattern": "aa$$$$bb",
            "data_hex": "aa0002" + ("00" * 5) + "bb",
            "memory_map": {
                "file_type": "elf",
                "endian": "big",
                "records": [
                    {"offset": 0, "address": 0x1000, "size": 3},
                    {"offset": 8, "address": 0x1005, "size": 1},
                ],
            },
        },
        {
            "id": "macho_64_absolute_crosses_raw_gap",
            "pattern": "68################90",
            "data_hex": "680010000001000000" + ("00" * 7) + "90",
            "memory_map": {
                "file_type": "macho",
                "endian": "little",
                "records": [
                    {"offset": 0, "address": 0x100000000, "size": 9},
                    {"offset": 16, "address": 0x100001000, "size": 1},
                ],
            },
        },
        {
            "id": "com_relative_ignores_nonidentity_map",
            "pattern": "eb$$90",
            "data_hex": "00009000ebfc",
            "offset": 4,
            "memory_map": {
                "file_type": "com",
                "endian": "little",
                "records": [
                    {"offset": 2, "address": 0x2000, "size": 1},
                    {"offset": 4, "address": 0x1000, "size": 2},
                ],
            },
        },
        {
            "id": "msdos_absolute_word_adds_code_base",
            "pattern": "68####90",
            "data_hex": "681000" + ("00" * 5) + "90",
            "memory_map": {
                "file_type": "msdos",
                "endian": "little",
                "code_base": 0x100,
                "records": [
                    {"offset": 0, "address": 0, "size": 3},
                    {"offset": 8, "address": 0x110, "size": 1},
                ],
            },
        },
        {
            "id": "msdos_far_pointer_uses_segment_address",
            "pattern": "68########90",
            "data_hex": "6803000200" + ("00" * 34) + "90",
            "memory_map": {
                "file_type": "msdos",
                "endian": "little",
                "start_load_offset": 4,
                "records": [
                    {"offset": 0, "address": 0, "size": 40},
                ],
            },
        },
        {
            "id": "amigahunk_relative_word_omits_width_increment",
            "pattern": "aa$$$$bb",
            "data_hex": "aa0004" + ("00" * 5) + "bb",
            "memory_map": {
                "file_type": "amigahunk",
                "endian": "big",
                "records": [
                    {"offset": 0, "address": 0x1000, "size": 3},
                    {"offset": 8, "address": 0x1005, "size": 1},
                ],
            },
        },
        {
            "id": "pe32_parser_memory_map_relative_jump",
            "pattern": "e9$$$$$$$$90",
            "data_hex": mapped_pe32().hex(),
            "offset": 0x200,
            "format_parser": "pe",
        },
        {
            "id": "pe64_parser_memory_map_relative_jump",
            "pattern": "e9$$$$$$$$90",
            "data_hex": mapped_pe64().hex(),
            "offset": 0x200,
            "format_parser": "pe",
        },
        {
            "id": "elf64_parser_memory_map_relative_jump",
            "pattern": "e9$$$$$$$$90",
            "data_hex": mapped_elf64().hex(),
            "offset": 0x100,
            "format_parser": "elf",
        },
        {
            "id": "elf32_parser_memory_map_relative_jump",
            "pattern": "e9$$$$$$$$90",
            "data_hex": mapped_elf32().hex(),
            "offset": 0x100,
            "format_parser": "elf",
        },
        {
            "id": "macho64_parser_memory_map_absolute_jump",
            "pattern": "68################90",
            "data_hex": mapped_macho64().hex(),
            "offset": 0x100,
            "format_parser": "macho",
        },
        {
            "id": "macho32_parser_memory_map_absolute_jump",
            "pattern": "68########90",
            "data_hex": mapped_macho32().hex(),
            "offset": 0x100,
            "format_parser": "macho",
        },
        {
            "id": "com_parser_memory_map_relative_jump",
            "pattern": "eb$$90",
            "data_hex": mapped_com().hex(),
            "format_parser": "com",
        },
        {
            "id": "msdos_parser_memory_map_far_pointer",
            "pattern": "68########90",
            "data_hex": mapped_msdos().hex(),
            "offset": 0x40,
            "format_parser": "msdos",
        },
        {
            "id": "amigahunk_parser_memory_map_relative_jump",
            "pattern": "aa$$$$bb",
            "data_hex": mapped_amigahunk().hex(),
            "offset": 32,
            "format_parser": "amigahunk",
        },
        {
            "id": "address_markers_around_ignored_base",
            "pattern": "68##[5]##90",
            "data_hex": "680500000090",
        },
        {
            "id": "odd_hex_qbytearray_behavior",
            "pattern": "abc",
            "data_hex": "0abc",
        },
        {
            "id": "unterminated_quote_behavior",
            "pattern": "'AMX ",
            "data_hex": "414d5820",
        },
        {
            "id": "odd_hex_and_zero_width_wildcard",
            "pattern": "'RJP'3. 0000 0000",
            "data_hex": "0524a50300000000",
        },
        {
            "id": "single_wildcard_is_zero_width",
            "pattern": ".",
            "data_hex": "00",
        },
        {
            "id": "single_not_null_is_zero_width_but_fails",
            "pattern": "*",
            "data_hex": "01",
        },
        {
            "id": "invalid_suffix_partially_compares",
            "pattern": "41x",
            "data_hex": "41",
        },
        {
            "id": "binary_script_fast_path_invalid_suffix",
            "pattern": "41x",
            "data_hex": "41" + ("00" * 255),
            "binary_script_compare": True,
            "binary_script_overlay_info": True,
        },
        {
            "id": "binary_script_fast_path_before_strict_boundary",
            "pattern": "41x",
            "data_hex": ("00" * 252) + "41414100",
            "offset": 252,
            "binary_script_compare": True,
        },
        {
            "id": "binary_script_generic_at_strict_boundary",
            "pattern": "41x",
            "data_hex": ("00" * 252) + "41414100",
            "offset": 253,
            "binary_script_compare": True,
        },
        {
            "id": "binary_script_literal_before_strict_boundary",
            "pattern": "41",
            "data_hex": ("00" * 252) + "41414100",
            "offset": 253,
            "binary_script_compare": True,
        },
        {
            "id": "binary_script_literal_at_strict_boundary",
            "pattern": "41",
            "data_hex": ("00" * 252) + "41414100",
            "offset": 254,
            "binary_script_compare": True,
        },
        {
            "id": "binary_script_negative_offset_clamps_to_header_start",
            "pattern": "'COLL'",
            "data_hex": "434f4c4c" + ("00" * 252),
            "offset": -1,
            "binary_script_compare": True,
        },
        {
            "id": "binary_script_negative_offset_clamp_can_mismatch",
            "pattern": "'COLL'",
            "data_hex": "00434f4c4c" + ("00" * 251),
            "offset": -1,
            "binary_script_compare": True,
        },
        {
            "id": "binary_script_overlay_file_part_without_nested_overlay",
            "pattern": "41",
            "data_hex": "41",
            "binary_script_overlay_info": True,
            "binary_script_file_part": "overlay",
        },
        {
            "id": "binary_script_ep_fast_path_invalid_suffix",
            "pattern": "41x",
            "data_hex": mapped_pe32_with_overlay().hex(),
            "binary_script_parser": "pe",
            "binary_script_compare_ep": True,
        },
        {
            "id": "binary_script_ep_cache_overrun_fast_path",
            "pattern": "41",
            "data_hex": mapped_pe32_with_overlay().hex(),
            "offset": 508,
            "binary_script_parser": "pe",
            "binary_script_compare_ep": True,
        },
        {
            "id": "binary_script_ep_original_length_selects_generic",
            "pattern": " 41 ",
            "data_hex": mapped_pe32_with_overlay().hex(),
            "offset": 508,
            "binary_script_parser": "pe",
            "binary_script_compare_ep": True,
        },
        {
            "id": "binary_script_ep_before_strict_boundary",
            "pattern": "41",
            "data_hex": mapped_pe32_with_overlay().hex(),
            "offset": 509,
            "binary_script_parser": "pe",
            "binary_script_compare_ep": True,
        },
        {
            "id": "binary_script_ep_at_strict_boundary",
            "pattern": "41",
            "data_hex": mapped_pe32_with_overlay().hex(),
            "offset": 510,
            "binary_script_parser": "pe",
            "binary_script_compare_ep": True,
        },
        {
            "id": "binary_script_overlay_fast_path_invalid_suffix",
            "pattern": "41x",
            "data_hex": mapped_pe32_with_overlay().hex(),
            "binary_script_parser": "pe",
            "binary_script_compare_overlay": True,
            "binary_script_overlay_info": True,
        },
        {
            "id": "binary_script_overlay_cache_overrun_fast_path",
            "pattern": "41",
            "data_hex": mapped_pe32_with_overlay().hex(),
            "offset": 508,
            "binary_script_parser": "pe",
            "binary_script_compare_overlay": True,
        },
        {
            "id": "binary_script_overlay_original_length_selects_generic",
            "pattern": " 41 ",
            "data_hex": mapped_pe32_with_overlay().hex(),
            "offset": 508,
            "binary_script_parser": "pe",
            "binary_script_compare_overlay": True,
        },
        {
            "id": "binary_script_overlay_before_strict_boundary",
            "pattern": "41",
            "data_hex": mapped_pe32_with_overlay().hex(),
            "offset": 509,
            "binary_script_parser": "pe",
            "binary_script_compare_overlay": True,
        },
        {
            "id": "binary_script_overlay_at_strict_boundary",
            "pattern": "41",
            "data_hex": mapped_pe32_with_overlay().hex(),
            "offset": 510,
            "binary_script_parser": "pe",
            "binary_script_compare_overlay": True,
        },
        {
            "id": "binary_script_string_empty_unnamed_device",
            "pattern": "",
            "data_hex": "",
            "binary_script_string_info": True,
        },
        {
            "id": "binary_script_suffix_simple",
            "pattern": "41",
            "data_hex": "41",
            "binary_script_string_info": True,
            "file_name": "sample.bin",
        },
        {
            "id": "binary_script_suffix_last_component",
            "pattern": "41",
            "data_hex": "41",
            "binary_script_string_info": True,
            "file_name": "/tmp/archive.tar.gz",
        },
        {
            "id": "binary_script_suffix_hidden_file",
            "pattern": "41",
            "data_hex": "41",
            "binary_script_string_info": True,
            "file_name": ".bashrc",
        },
        {
            "id": "binary_script_suffix_trailing_dot",
            "pattern": "41",
            "data_hex": "41",
            "binary_script_string_info": True,
            "file_name": "sample.",
        },
        {
            "id": "binary_script_suffix_preserves_case",
            "pattern": "41",
            "data_hex": "41",
            "binary_script_string_info": True,
            "file_name": "SAMPLE.SG",
        },
        {
            "id": "binary_script_header_ascii",
            "pattern": "66",
            "data_hex": b"function test() {}\n".hex(),
            "binary_script_string_info": True,
            "file_name": "sample.c",
        },
        {
            "id": "binary_script_header_latin1",
            "pattern": "63",
            "data_hex": b"caf\xe9 text\n".hex(),
            "binary_script_string_info": True,
            "file_name": "sample.txt",
        },
        {
            "id": "binary_script_header_utf8_bom",
            "pattern": "efbbbf",
            "data_hex": (b"\xef\xbb\xbf" + "héllo\n".encode()).hex(),
            "binary_script_string_info": True,
            "file_name": "sample.txt",
        },
        {
            "id": "binary_script_header_utf8_without_bom",
            "pattern": "68",
            "data_hex": "hello café text\n".encode().hex(),
            "binary_script_string_info": True,
            "file_name": "sample.txt",
        },
        {
            "id": "binary_script_header_utf16le_bom",
            "pattern": "fffe",
            "data_hex": (b"\xff\xfe" + "Hello\n".encode("utf-16le")).hex(),
            "binary_script_string_info": True,
            "file_name": "sample.txt",
        },
        {
            "id": "binary_script_header_utf16be_bom",
            "pattern": "feff",
            "data_hex": (b"\xfe\xff" + "Hello\n".encode("utf-16be")).hex(),
            "binary_script_string_info": True,
            "file_name": "sample.txt",
        },
        {
            "id": "binary_script_header_utf16le_without_bom",
            "pattern": "4100",
            "data_hex": "Hello\n".encode("utf-16le").hex(),
            "binary_script_string_info": True,
            "file_name": "sample.txt",
        },
        {
            "id": "binary_script_header_utf16be_without_bom",
            "pattern": "0041",
            "data_hex": "Hello\n".encode("utf-16be").hex(),
            "binary_script_string_info": True,
            "file_name": "sample.txt",
        },
        {
            "id": "binary_script_header_binary_nul",
            "pattern": "4100",
            "data_hex": "4100420143",
            "binary_script_string_info": True,
            "file_name": "sample.bin",
        },
        {
            "id": "invalid_prefix_has_no_records",
            "pattern": "x41",
            "data_hex": "41",
        },
        {
            "id": "percent_only_has_no_records",
            "pattern": "%",
            "data_hex": "00",
        },
        {
            "id": "empty_pattern",
            "pattern": "",
            "data_hex": "",
        },
        {
            "id": "non_latin1_quote_becomes_zero",
            "pattern": "'€'",
            "data_hex": "00",
        },
        {
            "id": "tab_is_not_ignored",
            "pattern": "41\t42",
            "data_hex": "41",
        },
        {
            "id": "compare_strings_prefix",
            "pattern": "41",
            "base_signature": "4142",
            "data_hex": "",
        },
        {
            "id": "compare_strings_wildcard_on_base",
            "pattern": "4142",
            "base_signature": "41..",
            "data_hex": "",
        },
        {
            "id": "compare_strings_empty_pattern",
            "pattern": "",
            "base_signature": "4142",
            "data_hex": "",
        },
    ]


def manifest() -> dict[str, object]:
    cases = vectors()
    return {
        "schema_version": SCHEMA_VERSION,
        "generator": {
            "path": "tools/corpus/generate_signature_oracle_vectors.py",
            "version": GENERATOR_VERSION,
        },
        "upstream_commit": UPSTREAM_COMMIT,
        "formats_commit": FORMATS_COMMIT,
        "xscanengine_commit": XSCANENGINE_COMMIT,
        "license": "project-generated; no third-party sample or rule bytes",
        "case_count": len(cases),
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
