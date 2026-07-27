import importlib.util
import pathlib
import struct
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).parents[2]
MODULE_PATH = (
    ROOT / "tools" / "corpus" / "generate_dos_dispatch_corpus.py"
)
SPEC = importlib.util.spec_from_file_location(
    "generate_dos_dispatch_corpus", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class GenerateDosDispatchCorpusTests(unittest.TestCase):
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
            / "dos-dispatch-corpus.json"
        )
        with tempfile.TemporaryDirectory() as output_dir:
            generated_dir = pathlib.Path(output_dir)
            MODULE.generate(generated_dir)
            generated = (generated_dir / "manifest.json").read_bytes()
        self.assertEqual(generated, reference.read_bytes())

    def test_public_positive_set_is_exact_and_bw_is_excluded(self):
        with tempfile.TemporaryDirectory() as output_dir:
            manifest = MODULE.generate(pathlib.Path(output_dir))
        positives = {
            sample["target_filetype"]
            for sample in manifest["samples"]
            if sample["case_kind"] == "positive"
        }
        self.assertEqual(positives, set(MODULE.PUBLIC_FILETYPES))
        self.assertEqual(
            manifest["excluded_member"]["filetype"], "BW DOS16M"
        )
        self.assertNotIn("BW DOS16M", manifest["public_filetypes"])

    def test_linear_headers_cross_exact_magic_boundaries(self):
        for factory, signature in (
            (MODULE.make_ne, b"NE"),
            (MODULE.make_le, b"LE\0\0"),
            (MODULE.make_lx, b"LX\0\0"),
        ):
            data = factory()
            self.assertEqual(data[:2], b"MZ")
            self.assertEqual(
                struct.unpack_from("<I", data, 0x3C)[0],
                MODULE.NEW_HEADER_OFFSET,
            )
            self.assertEqual(
                data[
                    MODULE.NEW_HEADER_OFFSET :
                    MODULE.NEW_HEADER_OFFSET + len(signature)
                ],
                signature,
            )

    def test_dos16_chains_terminate_at_nested_mz(self):
        for factory, signature in (
            (MODULE.make_dos16m, b"NE"),
            (MODULE.make_dos4g, b"LE\0\0"),
        ):
            data = factory()
            self.assertGreater(len(data), 1024)
            self.assertEqual(data[:2], b"MZ")
            self.assertEqual(data[64:66], b"BW")
            nested = struct.unpack_from("<I", data, 64 + 28)[0]
            self.assertEqual(nested, 0x100)
            self.assertEqual(data[nested : nested + 2], b"MZ")
            lfanew = struct.unpack_from("<I", data, nested + 0x3C)[0]
            self.assertEqual(lfanew, 64)
            self.assertEqual(
                data[nested + lfanew : nested + lfanew + len(signature)],
                signature,
            )

    def test_controls_cover_length_suffix_and_adjacent_dispatch(self):
        with tempfile.TemporaryDirectory() as output_dir:
            root = pathlib.Path(output_dir)
            manifest = MODULE.generate(root)
            by_name = {
                sample["name"]: sample for sample in manifest["samples"]
            }
            self.assertEqual(
                by_name["dos16m-truncated.exe"]["size"], 1024
            )
            self.assertEqual(
                by_name["dos4g-truncated.exe"]["size"], 1024
            )
            self.assertEqual(
                by_name["com-max-size.com"]["size"],
                MODULE.COM_MAX_SIZE,
            )
            self.assertEqual(
                by_name["com-oversized.com"]["size"],
                MODULE.COM_MAX_SIZE + 1,
            )
            adjacent = by_name["dos4g-near-nested-magic.exe"]
            self.assertEqual(
                adjacent["expected_dispatch"]["present_filetypes"],
                ["DOS/16M"],
            )
            self.assertEqual(
                adjacent["expected_dispatch"]["absent_filetypes"],
                ["DOS/4G"],
            )
            self.assertEqual(
                (root / "com-wrong-suffix.bin").read_bytes(),
                MODULE.make_com(),
            )


if __name__ == "__main__":
    unittest.main()
