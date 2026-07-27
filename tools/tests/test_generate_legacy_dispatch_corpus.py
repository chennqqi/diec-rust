import importlib.util
import pathlib
import struct
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).parents[2]
MODULE_PATH = (
    ROOT / "tools" / "corpus" / "generate_legacy_dispatch_corpus.py"
)
SPEC = importlib.util.spec_from_file_location(
    "generate_legacy_dispatch_corpus", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class GenerateLegacyDispatchCorpusTests(unittest.TestCase):
    def test_generates_identical_manifest_and_bytes_twice(self):
        with tempfile.TemporaryDirectory() as first_dir:
            with tempfile.TemporaryDirectory() as second_dir:
                first = pathlib.Path(first_dir)
                second = pathlib.Path(second_dir)
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

    def test_manifest_matches_versioned_reference(self):
        reference = (
            ROOT
            / "docs"
            / "research"
            / "data"
            / "legacy-dispatch-corpus.json"
        )
        with tempfile.TemporaryDirectory() as output_dir:
            generated_dir = pathlib.Path(output_dir)
            MODULE.generate(generated_dir)
            generated = (generated_dir / "manifest.json").read_bytes()
        self.assertEqual(generated, reference.read_bytes())

    def test_positive_headers_match_pinned_validity_constants(self):
        amiga = MODULE.make_amiga_hunk()
        atari = MODULE.make_atari_st()
        self.assertGreater(len(amiga), 8)
        self.assertEqual(struct.unpack_from(">I", amiga)[0], 0x000003F3)
        self.assertEqual(len(atari), 32)
        self.assertEqual(struct.unpack_from(">H", atari)[0], 0x601A)
        self.assertEqual(atari[28:], b"\x00" * 4)

    def test_each_target_has_positive_and_three_negative_controls(self):
        with tempfile.TemporaryDirectory() as output_dir:
            manifest = MODULE.generate(pathlib.Path(output_dir))

        self.assertEqual(len(manifest["samples"]), 8)
        for target in MODULE.TARGET_FILETYPES:
            cases = {
                sample["case_kind"]: sample
                for sample in manifest["samples"]
                if sample["target_filetype"] == target
            }
            self.assertEqual(
                set(cases),
                {"positive", "truncated", "wrong_endian", "near_magic"},
            )
            self.assertEqual(
                cases["positive"]["expected_dispatch"]["info_filetype"],
                target,
            )
            expected_scanner = [target] if target == "Amiga Hunk" else []
            self.assertEqual(
                cases["positive"]["expected_dispatch"]["present_filetypes"],
                expected_scanner,
            )
            for case_kind in ("truncated", "wrong_endian", "near_magic"):
                self.assertEqual(
                    cases[case_kind]["expected_dispatch"][
                        "present_filetypes"
                    ],
                    [],
                )
                self.assertEqual(
                    set(
                        cases[case_kind]["expected_dispatch"][
                            "absent_filetypes"
                        ]
                    ),
                    set(MODULE.TARGET_FILETYPES),
                )
                self.assertEqual(
                    cases[case_kind]["expected_dispatch"]["info_filetype"],
                    "Binary",
                )

    def test_controls_cross_exact_upstream_validity_boundaries(self):
        by_name = {
            name: factory()
            for name, _kind, _target, factory in MODULE.GENERATORS
        }
        self.assertEqual(len(by_name["amiga-hunk-truncated.bin"]), 8)
        self.assertEqual(
            by_name["amiga-hunk-wrong-endian.bin"][:4],
            bytes.fromhex("f3030000"),
        )
        self.assertEqual(
            by_name["amiga-hunk-near-magic.bin"][:4],
            bytes.fromhex("000003f4"),
        )
        self.assertEqual(len(by_name["atari-st-truncated.prg"]), 31)
        self.assertEqual(
            by_name["atari-st-wrong-endian.prg"][:2],
            bytes.fromhex("1a60"),
        )
        self.assertEqual(
            by_name["atari-st-near-magic.prg"][:2],
            bytes.fromhex("601b"),
        )


if __name__ == "__main__":
    unittest.main()
