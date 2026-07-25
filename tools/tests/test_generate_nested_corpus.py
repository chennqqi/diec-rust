import importlib.util
import io
import pathlib
import sys
import tempfile
import unittest
import zipfile


MODULE_PATH = (
    pathlib.Path(__file__).parents[1]
    / "corpus"
    / "generate_nested_corpus.py"
)
SPEC = importlib.util.spec_from_file_location(
    "generate_nested_corpus", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class GenerateNestedCorpusTests(unittest.TestCase):
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

    def test_nested_zip_has_expected_safe_depth(self):
        with tempfile.TemporaryDirectory() as output_dir:
            root = pathlib.Path(output_dir)
            MODULE.generate(root)

            with zipfile.ZipFile(root / "nested-zip.zip") as outer:
                self.assertEqual(outer.namelist(), ["inner.zip"])
                inner_bytes = outer.read("inner.zip")
            with zipfile.ZipFile(io.BytesIO(inner_bytes)) as inner:
                self.assertEqual(inner.namelist(), ["embedded.pdf"])
                self.assertTrue(inner.read("embedded.pdf").startswith(b"%PDF"))

    def test_overlay_begins_at_pe_size_of_headers(self):
        with tempfile.TemporaryDirectory() as output_dir:
            root = pathlib.Path(output_dir)
            MODULE.generate(root)

            pdf_overlay = (root / "pe-pdf-overlay.exe").read_bytes()
            zip_overlay = (root / "pe-zip-overlay.exe").read_bytes()

        self.assertEqual(pdf_overlay[512:517], b"%PDF-")
        self.assertEqual(zip_overlay[512:516], b"PK\x03\x04")

    def test_resource_payload_is_at_declared_rva(self):
        with tempfile.TemporaryDirectory() as output_dir:
            root = pathlib.Path(output_dir)
            MODULE.generate(root)
            resource_pe = (root / "pe-pdf-resource.exe").read_bytes()

        self.assertEqual(resource_pe[0x260:0x265], b"%PDF-")
        self.assertEqual(resource_pe[0x178:0x180], b".rsrc\0\0\0")

    def test_matches_versioned_reference_manifest(self):
        reference_path = (
            pathlib.Path(__file__).parents[2]
            / "docs"
            / "research"
            / "data"
            / "nested-corpus.json"
        )
        with tempfile.TemporaryDirectory() as output_dir:
            MODULE.generate(pathlib.Path(output_dir))
            generated = (
                pathlib.Path(output_dir) / "manifest.json"
            ).read_bytes()

        self.assertEqual(generated, reference_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
