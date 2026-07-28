import binascii
import hashlib
import importlib.util
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
    / "generate_archive_structure_fixture.py"
)
REFERENCE_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "archive-structure-corpus.json"
)
SPEC = importlib.util.spec_from_file_location(
    "generate_archive_structure_fixture",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class GenerateArchiveStructureFixtureTests(unittest.TestCase):
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

    def test_manifest_changed_ranges_match_control_bytes(self):
        with tempfile.TemporaryDirectory() as output_dir:
            root = Path(output_dir)
            manifest = MODULE.generate(root)
            controls = MODULE.controls()
            self.assertEqual(len(manifest["samples"]), 33)
            self.assertEqual(
                {
                    sample["control_name"]
                    for sample in manifest["samples"]
                },
                {"sevenzip", "rar4", "cab", "iso9660"},
            )
            for sample in manifest["samples"]:
                with self.subTest(sample=sample["name"]):
                    control = controls[sample["control_name"]]
                    data = (root / sample["name"]).read_bytes()
                    self.assertEqual(len(data), len(control))
                    self.assertEqual(
                        sample["control_sha256"],
                        hashlib.sha256(control).hexdigest(),
                    )
                    changed = [
                        index
                        for index, pair in enumerate(
                            zip(control, data, strict=True)
                        )
                        if pair[0] != pair[1]
                    ]
                    self.assertEqual(
                        len(changed),
                        sample["changed_byte_count"],
                    )
                    self.assertEqual(
                        min(changed) if changed else None,
                        sample["changed_offset_min"],
                    )
                    self.assertEqual(
                        max(changed) if changed else None,
                        sample["changed_offset_max"],
                    )
                    self.assertEqual(
                        bool(changed),
                        sample["field"] != "control",
                    )

    def test_7z_outer_crc_is_valid_except_targeted_crc(self):
        with tempfile.TemporaryDirectory() as output_dir:
            root = Path(output_dir)
            manifest = MODULE.generate(root)
            samples = {
                sample["field"]: (root / sample["name"]).read_bytes()
                for sample in manifest["samples"]
                if sample["control_name"] == "sevenzip"
            }
            for field, data in samples.items():
                with self.subTest(field=field):
                    actual_start_crc = int.from_bytes(
                        data[8:12],
                        "little",
                    )
                    expected_start_crc = (
                        binascii.crc32(data[12:32]) & 0xFFFFFFFF
                    )
                    self.assertEqual(
                        actual_start_crc == expected_start_crc,
                        field != "start-header-crc",
                    )

            for field in (
                "control",
                "packed-crc",
                "unpacked-size",
            ):
                data = samples[field]
                offset = 32 + int.from_bytes(
                    data[12:20],
                    "little",
                )
                size = int.from_bytes(data[20:28], "little")
                self.assertEqual(
                    int.from_bytes(data[28:32], "little"),
                    binascii.crc32(data[offset : offset + size])
                    & 0xFFFFFFFF,
                )

            data = samples["next-header-crc"]
            offset = 32 + int.from_bytes(data[12:20], "little")
            size = int.from_bytes(data[20:28], "little")
            self.assertNotEqual(
                int.from_bytes(data[28:32], "little"),
                binascii.crc32(data[offset : offset + size])
                & 0xFFFFFFFF,
            )

    def test_rar_mutations_preserve_non_target_header_crc(self):
        with tempfile.TemporaryDirectory() as output_dir:
            root = Path(output_dir)
            manifest = MODULE.generate(root)
            samples = {
                sample["field"]: (root / sample["name"]).read_bytes()
                for sample in manifest["samples"]
                if sample["control_name"] == "rar4"
            }

            def crc_valid(data: bytes, offset: int) -> bool:
                size = int.from_bytes(
                    data[offset + 5 : offset + 7],
                    "little",
                )
                return int.from_bytes(
                    data[offset : offset + 2],
                    "little",
                ) == (
                    binascii.crc32(data[offset + 2 : offset + size])
                    & 0xFFFF
                )

            for field, data in samples.items():
                with self.subTest(field=field):
                    self.assertEqual(
                        crc_valid(data, 7),
                        field != "main-header-crc",
                    )
                    self.assertEqual(
                        crc_valid(data, 20),
                        field != "file-header-crc",
                    )

    def test_mutated_fields_have_exact_declared_values(self):
        with tempfile.TemporaryDirectory() as output_dir:
            root = Path(output_dir)
            manifest = MODULE.generate(root)
            samples = {
                sample["name"]: (root / sample["name"]).read_bytes()
                for sample in manifest["samples"]
            }
            self.assertEqual(
                int.from_bytes(
                    samples["rar4-packed-size-plus-one.rar"][27:31],
                    "little",
                ),
                len(MODULE.FORMAT.PDF) + 1,
            )
            self.assertEqual(
                int.from_bytes(
                    samples[
                        "cab-compressed-size-plus-one.cab"
                    ][76:78],
                    "little",
                ),
                len(MODULE.FORMAT.PDF) + 1,
            )
            self.assertEqual(
                int.from_bytes(
                    samples[
                        "iso9660-logical-block-size-set-1024.iso"
                    ][MODULE.ISO_PVD + 128 : MODULE.ISO_PVD + 130],
                    "little",
                ),
                1024,
            )
            payload_size = samples[
                "iso9660-payload-size-plus-one.iso"
            ]
            self.assertEqual(
                int.from_bytes(
                    payload_size[
                        MODULE.ISO_PAYLOAD_RECORD
                        + 10 : MODULE.ISO_PAYLOAD_RECORD
                        + 14
                    ],
                    "little",
                ),
                len(MODULE.FORMAT.PDF) + 1,
            )


if __name__ == "__main__":
    unittest.main()
