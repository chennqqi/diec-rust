#!/usr/bin/env python3
"""Generate project-owned XBinary signature oracle vectors."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


SCHEMA_VERSION = 1
GENERATOR_VERSION = 1
UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
FORMATS_COMMIT = "1151e7254fdee3c0294ff7095edbdd7bfccf8201"


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
            "id": "find_at_window_end",
            "pattern": "++'MZ'",
            "data_hex": ("00" * 64) + "4d5a",
        },
        {
            "id": "find_outside_window",
            "pattern": "++'MZ'",
            "data_hex": ("00" * 65) + "4d5a",
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
