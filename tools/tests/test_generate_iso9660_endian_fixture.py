import contextlib
import hashlib
import importlib.util
import io
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
    / "generate_iso9660_endian_fixture.py"
)
REFERENCE_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "iso9660-endian-corpus.json"
)
SPEC = importlib.util.spec_from_file_location(
    "generate_iso9660_endian_fixture",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class GenerateIso9660EndianFixtureTests(unittest.TestCase):
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

    def test_manifest_has_complete_field_side_product(self):
        manifest = json.loads(
            REFERENCE_PATH.read_text(encoding="utf-8")
        )
        self.assertEqual(len(manifest["samples"]), 35)
        controls = [
            sample
            for sample in manifest["samples"]
            if sample["field"] == "control"
        ]
        self.assertEqual(len(controls), 1)
        self.assertEqual(
            {
                (sample["field"], sample["mutated_side"])
                for sample in manifest["samples"]
                if sample["field"] != "control"
            },
            {
                (field.name, side)
                for field in MODULE.FIELDS
                for side in MODULE.SIDES
            },
        )

    def test_each_mutation_changes_only_selected_half(self):
        with tempfile.TemporaryDirectory() as output_dir:
            root = Path(output_dir)
            manifest = MODULE.generate(root)
            base = MODULE.control()
            fields = {field.name: field for field in MODULE.FIELDS}
            for sample in manifest["samples"]:
                if sample["field"] == "control":
                    continue
                with self.subTest(sample=sample["name"]):
                    field = fields[sample["field"]]
                    output = (root / sample["name"]).read_bytes()
                    changed = {
                        index
                        for index, pair in enumerate(
                            zip(base, output, strict=True)
                        )
                        if pair[0] != pair[1]
                    }
                    half_start = field.offset + (
                        field.width
                        if sample["mutated_side"] == "big"
                        else 0
                    )
                    self.assertTrue(changed)
                    self.assertLessEqual(
                        changed,
                        set(
                            range(
                                half_start,
                                half_start + field.width,
                            )
                        ),
                    )
                    self.assertEqual(
                        len(changed),
                        sample["changed_byte_count"],
                    )
                    self.assertEqual(
                        min(changed),
                        sample["changed_offset_min"],
                    )
                    self.assertEqual(
                        max(changed),
                        sample["changed_offset_max"],
                    )

    def test_mutated_and_opposite_values_are_exact(self):
        with tempfile.TemporaryDirectory() as output_dir:
            root = Path(output_dir)
            manifest = MODULE.generate(root)
            fields = {field.name: field for field in MODULE.FIELDS}
            for sample in manifest["samples"]:
                if sample["field"] == "control":
                    continue
                with self.subTest(sample=sample["name"]):
                    field = fields[sample["field"]]
                    data = (root / sample["name"]).read_bytes()
                    side = sample["mutated_side"]
                    other = "big" if side == "little" else "little"
                    self.assertEqual(
                        MODULE.read_side(data, field, side),
                        field.alternate,
                    )
                    self.assertEqual(
                        MODULE.read_side(data, field, other),
                        field.control,
                    )

    def test_control_has_expected_iso_layout(self):
        data = MODULE.control()
        self.assertEqual(len(data), 21 * 2048)
        self.assertEqual(
            data[MODULE.PVD : MODULE.PVD + 7],
            b"\x01CD001\x01",
        )
        self.assertEqual(
            data[17 * 2048 : 17 * 2048 + 7],
            b"\xffCD001\x01",
        )
        self.assertEqual(data[MODULE.DOT_RECORD], 34)
        self.assertEqual(data[MODULE.DOTDOT_RECORD], 34)
        self.assertGreater(data[MODULE.PAYLOAD_RECORD], 0)
        self.assertEqual(
            data[20 * 2048 : 20 * 2048 + len(MODULE.FORMAT.PDF)],
            MODULE.FORMAT.PDF,
        )

    def test_cli_can_write_a_separate_reference_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "fixture"
            reference = root / "reference.json"
            original_argv = sys.argv
            sys.argv = [
                str(MODULE_PATH),
                str(fixture),
                "--manifest-output",
                str(reference),
            ]
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(MODULE.main(), 0)
            finally:
                sys.argv = original_argv
            self.assertEqual(
                reference.read_bytes(),
                (fixture / "manifest.json").read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()
