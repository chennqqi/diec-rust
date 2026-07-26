import hashlib
import importlib.util
import io
import pathlib
import struct
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

    def test_many_member_zip_has_exactly_22_stored_pdfs(self):
        with tempfile.TemporaryDirectory() as output_dir:
            root = pathlib.Path(output_dir)
            MODULE.generate(root)

            with zipfile.ZipFile(root / "many-pdf-members.zip") as archive:
                infos = archive.infolist()
                self.assertEqual(len(infos), 22)
                self.assertTrue(
                    all(
                        info.compress_type == zipfile.ZIP_STORED
                        for info in infos
                    )
                )
                self.assertEqual(infos[0].filename, "member-00.pdf")
                self.assertEqual(infos[-1].filename, "member-21.pdf")

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

    def test_many_resource_pe_contains_22_pdf_payloads(self):
        with tempfile.TemporaryDirectory() as output_dir:
            root = pathlib.Path(output_dir)
            MODULE.generate(root)
            resource_pe = (
                root / "pe-many-pdf-resources.exe"
            ).read_bytes()

        self.assertEqual(resource_pe.count(b"%PDF-1.4"), 22)

    def test_manifest_resource_has_type_id_and_unclassified_payload(self):
        with tempfile.TemporaryDirectory() as output_dir:
            root = pathlib.Path(output_dir)
            MODULE.generate(root)
            resource_pe = (
                root / "pe-manifest-resource.exe"
            ).read_bytes()

        resource_offset = 0x200
        resource_type = struct.unpack_from(
            "<I", resource_pe, resource_offset + 0x10
        )[0]
        data_rva, data_size = struct.unpack_from(
            "<II", resource_pe, resource_offset + 0x48
        )
        payload_offset = resource_offset + data_rva - 0x1000

        self.assertEqual(resource_type, 24)
        self.assertEqual(data_size, len(MODULE.MANIFEST_RESOURCE_PAYLOAD))
        self.assertEqual(
            resource_pe[payload_offset : payload_offset + data_size],
            MODULE.MANIFEST_RESOURCE_PAYLOAD,
        )

    def test_existing_resource_fixtures_keep_reference_hashes(self):
        expected = {
            "pe-pdf-resource.exe": (
                "679124ef09b88eeb9edc29e2ee7165f"
                "3dbaf4e17b9d988b548c51cf8d4d1482b"
            ),
            "pe-many-pdf-resources.exe": (
                "1eea60ef127f55f19a82568262ed14098"
                "972c7f50f462448eb209106592cf568"
            ),
        }
        with tempfile.TemporaryDirectory() as output_dir:
            root = pathlib.Path(output_dir)
            MODULE.generate(root)
            actual = {
                name: hashlib.sha256(
                    (root / name).read_bytes()
                ).hexdigest()
                for name in expected
            }

        self.assertEqual(actual, expected)

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
