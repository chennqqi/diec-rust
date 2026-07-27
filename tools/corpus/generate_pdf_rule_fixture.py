#!/usr/bin/env python3
"""Generate project-owned PDF inputs for the fixed Tools rule oracle."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SCHEMA_VERSION = 1
GENERATOR_VERSION = 1
UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
XPDF_COMMIT = "cdcee54dce97f566f2c023f400a457f4e6278de2"
XSCANENGINE_COMMIT = "dfe4a419e4f491bb23688ba03c5a5bf39e34da83"
RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6"
RULE_PATH = "PDF/format_Tools.2.sg"
RULE_SHA256 = "982869432394292415be6c3c2ef9408ac1943c4d7571e19f767ffe87314c23da"


def case(case_id: str, data: bytes) -> dict[str, object]:
    return {
        "id": case_id,
        "data_hex": data.hex(),
        "data_sha256": hashlib.sha256(data).hexdigest(),
    }


def manifest() -> dict[str, object]:
    tools = (
        b"%PDF-1.7\n"
        b"%\xe2\xe3\xcf\xd3\n"
        b"1 0 obj\n"
        b"<< /Creator (Tool A) /Producer (Prod One) >>\n"
        b"endobj\n"
        b"2 0 obj\n"
        b"<< /Creator (Tool A) /Creator (Tool\\)B) "
        b"/Producer <486578> >>\n"
        b"endobj\n"
    )
    non_string_values = (
        b"%PDF-1.4\n"
        b"%ASCII\n"
        b"1 0 obj\n"
        b"<< /Creator <546f6f6c> /Producer /NamedProducer >>\n"
        b"endobj\n"
    )
    missing_endobj = (
        b"%PDF-1.4\n"
        b"%\xff\xfe\n"
        b"1 0 obj\n"
        b"<< /Creator (Hidden) /Producer (Hidden Prod) >>\n"
    )
    cases = [
        case("tools_string_values", tools),
        case("tools_non_string_values", non_string_values),
        case("tools_missing_endobj", missing_endobj),
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "generator": {
            "path": "tools/corpus/generate_pdf_rule_fixture.py",
            "version": GENERATOR_VERSION,
        },
        "license": "project-generated; no third-party sample bytes",
        "upstream_commit": UPSTREAM_COMMIT,
        "xpdf_commit": XPDF_COMMIT,
        "xscanengine_commit": XSCANENGINE_COMMIT,
        "rules_commit": RULES_COMMIT,
        "rule": {
            "path": RULE_PATH,
            "sha256": RULE_SHA256,
            "preservation": "loaded byte-for-byte from the pinned rules subtree",
        },
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
