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
    / "generate_archive_truncation_fixture.py"
)
REFERENCE_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "archive-truncation-corpus.json"
)
SPEC = importlib.util.spec_from_file_location(
    "generate_archive_truncation_fixture",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class GenerateArchiveTruncationFixtureTests(unittest.TestCase):
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

    def test_each_ladder_is_an_exact_prefix_of_its_control(self):
        with tempfile.TemporaryDirectory() as output_dir:
            root = Path(output_dir)
            manifest = MODULE.generate(root)
            by_control = {}
            for sample in manifest["samples"]:
                by_control.setdefault(
                    sample["control_name"],
                    [],
                ).append(sample)

            self.assertEqual(set(by_control), set(MODULE.LADDERS))
            self.assertEqual(len(manifest["samples"]), 26)
            for control_name, samples in by_control.items():
                with self.subTest(control=control_name):
                    full = samples[-1]
                    full_data = (root / full["name"]).read_bytes()
                    self.assertEqual(full["boundary"], "full")
                    self.assertEqual(
                        [sample["cut_offset"] for sample in samples],
                        [
                            cut
                            for _boundary, cut in (
                                MODULE.LADDERS[control_name]
                            )
                        ],
                    )
                    for sample in samples:
                        data = (root / sample["name"]).read_bytes()
                        self.assertEqual(
                            data,
                            full_data[: sample["cut_offset"]],
                        )
                        self.assertEqual(
                            sample["full_sha256"],
                            full["sha256"],
                        )
                        self.assertEqual(
                            sample["full_size"],
                            full["size"],
                        )

    def test_full_controls_and_source_generator_are_fixed(self):
        expected_controls = {
            "sevenzip-full.7z": (
                427,
                (
                    "b5db3322be26f8693e15cfcd1d898e46"
                    "3f6ac20003274b90ffd75dd80788611d"
                ),
            ),
            "rar4-full.rar": (
                401,
                (
                    "1e988659f00088083708520b34d0fcd2"
                    "80af016d03f2d9d95b8449425bb01ab9"
                ),
            ),
            "cab-full.cab": (
                411,
                (
                    "9c96e5fc93766362d90940ef83606646"
                    "f255eaad408677675b510eebb2434708"
                ),
            ),
            "iso9660-full.iso": (
                43008,
                (
                    "d32df4410a94094ab990d9cb32fa4a2e"
                    "4e168d3173756962f6889902c18bb832"
                ),
            ),
        }
        manifest = json.loads(
            REFERENCE_PATH.read_text(encoding="utf-8")
        )
        controls = {
            sample["name"]: (sample["size"], sample["sha256"])
            for sample in manifest["samples"]
            if sample["boundary"] == "full"
        }
        self.assertEqual(controls, expected_controls)
        source_path = ROOT / manifest["source_generator"]["path"]
        self.assertEqual(
            hashlib.sha256(source_path.read_bytes()).hexdigest(),
            manifest["source_generator"]["sha256"],
        )


if __name__ == "__main__":
    unittest.main()
