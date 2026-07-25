import importlib.util
import pathlib
import struct
import sys
import tempfile
import unittest


MODULE_PATH = (
    pathlib.Path(__file__).parents[1]
    / "corpus"
    / "generate_nintendo_certified_corpus.py"
)
SPEC = importlib.util.spec_from_file_location(
    "generate_nintendo_certified_corpus", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class GenerateNintendoCertifiedCorpusTests(unittest.TestCase):
    def test_generates_same_manifest_and_bytes_twice(self):
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
                    name = sample["name"]
                    self.assertEqual(
                        (first / name).read_bytes(),
                        (second / name).read_bytes(),
                    )

    def test_covers_two_endiannesses_and_all_rule_branches(self):
        with tempfile.TemporaryDirectory() as output_dir:
            manifest = MODULE.generate(pathlib.Path(output_dir))
        names = {sample["name"] for sample in manifest["samples"]}
        self.assertEqual(len(names), 14)
        for platform in ("ps3", "vita"):
            for type_id in range(1, 7):
                self.assertTrue(
                    any(
                        name.startswith(f"{platform}-type-{type_id}-")
                        for name in names
                    )
                )

    def test_headers_match_rule_endianness_discriminators(self):
        big = MODULE.make_certified_file("big", 2)
        little = MODULE.make_certified_file("little", 2)
        self.assertEqual(big[:8], b"SCE\0\0\0\0\2")
        self.assertEqual(little[:8], b"SCE\0\3\0\0\0")
        self.assertEqual(struct.unpack_from(">H", big, 0xA)[0], 2)
        self.assertEqual(struct.unpack_from("<H", little, 0xA)[0], 2)
        self.assertEqual(struct.unpack_from(">Q", big, 0x10)[0], 0x20)
        self.assertEqual(struct.unpack_from("<Q", little, 0x10)[0], 0x30)

    def test_type_one_has_valid_pointer_relationships(self):
        for byte_order, endian, payload_start in (
            ("big", ">", 0x20),
            ("little", "<", 0x30),
        ):
            data = MODULE.make_certified_file(
                byte_order, 1, elf_header=True
            )
            program_id, elf_header, program_header, section_header = (
                struct.unpack_from(
                    f"{endian}QQQQ", data, payload_start + 8
                )
            )
            self.assertEqual(program_id + 0x20, elf_header)
            self.assertEqual(elf_header + 0x40, program_header)
            self.assertGreater(section_header, program_header)
            self.assertEqual(data[elf_header : elf_header + 7], b"\x7fELF\0\0\1")

    def test_rejects_invalid_parameters(self):
        with self.assertRaises(ValueError):
            MODULE.make_certified_file("middle", 2)
        with self.assertRaises(ValueError):
            MODULE.make_certified_file("big", 7)
        with self.assertRaises(ValueError):
            MODULE.make_certified_file("big", 2, elf_header=True)

    def test_matches_versioned_reference_manifest(self):
        reference_path = (
            pathlib.Path(__file__).parents[2]
            / "docs"
            / "research"
            / "data"
            / "nintendo-certified-corpus.json"
        )
        with tempfile.TemporaryDirectory() as output_dir:
            MODULE.generate(pathlib.Path(output_dir))
            generated = (
                pathlib.Path(output_dir) / "manifest.json"
            ).read_bytes()
        self.assertEqual(generated, reference_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
