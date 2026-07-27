import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT
    / "tools"
    / "corpus"
    / "generate_archive_iteration_boundary_fixture.py"
)
REFERENCE_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "archive-iteration-boundary-corpus.json"
)
SPEC = importlib.util.spec_from_file_location(
    "generate_archive_iteration_boundary_fixture",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def inspect_records(data: bytes) -> list[tuple[bytes, int, int]]:
    pvd = data[16 * MODULE.BLOCK_SIZE : 17 * MODULE.BLOCK_SIZE]
    assert pvd[1:6] == b"CD001"
    root_extent = struct.unpack_from("<I", pvd, 156 + 2)[0]
    root_size = struct.unpack_from("<I", pvd, 156 + 10)[0]
    offset = root_extent * MODULE.BLOCK_SIZE
    end = offset + root_size
    records: list[tuple[bytes, int, int]] = []
    while offset < end:
        record_length = data[offset]
        if record_length == 0:
            offset = (
                (offset // MODULE.BLOCK_SIZE) + 1
            ) * MODULE.BLOCK_SIZE
            continue
        name_length = data[offset + 32]
        name = data[offset + 33 : offset + 33 + name_length]
        extent = struct.unpack_from("<I", data, offset + 2)[0]
        size = struct.unpack_from("<I", data, offset + 10)[0]
        if name not in (b"\0", b"\1"):
            records.append((name, extent, size))
        offset += record_length
    return records


class GenerateArchiveIterationBoundaryFixtureTests(unittest.TestCase):
    def test_generates_identical_manifest_and_bytes_twice(self):
        with tempfile.TemporaryDirectory() as first_dir:
            with tempfile.TemporaryDirectory() as second_dir:
                first = Path(first_dir)
                second = Path(second_dir)
                first_manifest = MODULE.generate(first)
                second_manifest = MODULE.generate(second)
                self.assertEqual(first_manifest, second_manifest)
                self.assertEqual(
                    (first / "manifest.json").read_bytes(),
                    (second / "manifest.json").read_bytes(),
                )
                for sample in first_manifest["samples"]:
                    self.assertEqual(
                        (first / sample["name"]).read_bytes(),
                        (second / sample["name"]).read_bytes(),
                    )

    def test_each_fixture_has_one_valid_pdf_at_exact_ordinal(self):
        with tempfile.TemporaryDirectory() as output_dir:
            root = Path(output_dir)
            manifest = MODULE.generate(root)
            for sample in manifest["samples"]:
                with self.subTest(sample=sample["name"]):
                    data = (root / sample["name"]).read_bytes()
                    records = inspect_records(data)
                    self.assertEqual(
                        len(records),
                        MODULE.RECORD_COUNT,
                    )
                    valid = [
                        (ordinal, record)
                        for ordinal, record in enumerate(
                            records, start=1
                        )
                        if (
                            record[1] * MODULE.BLOCK_SIZE
                            + record[2]
                            <= len(data)
                        )
                    ]
                    self.assertEqual(len(valid), 1)
                    ordinal, (_, extent, size) = valid[0]
                    self.assertEqual(
                        ordinal,
                        sample["sentinel_ordinal"],
                    )
                    payload_offset = extent * MODULE.BLOCK_SIZE
                    self.assertTrue(
                        data[
                            payload_offset : payload_offset + size
                        ].startswith(b"%PDF-1.4")
                    )

    def test_matches_versioned_reference_manifest(self):
        with tempfile.TemporaryDirectory() as output_dir:
            MODULE.generate(Path(output_dir))
            generated = (
                Path(output_dir) / "manifest.json"
            ).read_bytes()
        self.assertEqual(
            json.loads(generated),
            json.loads(REFERENCE_PATH.read_bytes()),
        )
        self.assertEqual(generated, REFERENCE_PATH.read_bytes())


if __name__ == "__main__":
    unittest.main()
