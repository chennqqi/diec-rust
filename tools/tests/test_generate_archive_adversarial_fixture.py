import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT
    / "tools"
    / "corpus"
    / "generate_archive_adversarial_fixture.py"
)
REFERENCE_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "archive-adversarial-corpus.json"
)
SPEC = importlib.util.spec_from_file_location(
    "generate_archive_adversarial_fixture",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class GenerateArchiveAdversarialFixtureTests(unittest.TestCase):
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

    def test_valid_archives_are_independently_readable(self):
        with tempfile.TemporaryDirectory() as output_dir:
            root = Path(output_dir)
            manifest = MODULE.generate(root)
            readable = {
                sample["name"]: sample
                for sample in manifest["samples"]
                if sample["zipfile_readable"]
            }
            self.assertEqual(
                set(readable),
                {
                    "stored-valid.zip",
                    "deflate-valid.zip",
                    "deflate-high-ratio.zip",
                    "zipcrypto-stored.zip",
                    "stored-traversal-name.zip",
                    "mixed-members.zip",
                },
            )
            for name in readable:
                with self.subTest(sample=name):
                    with zipfile.ZipFile(root / name) as archive:
                        payloads = [
                            archive.read(
                                info,
                                pwd=(
                                    MODULE.PASSWORD
                                    if info.flag_bits & 1
                                    else None
                                ),
                            )
                            for info in archive.infolist()
                        ]
                    self.assertTrue(payloads[0].startswith(b"%PDF-1.4"))

    def test_high_ratio_encryption_and_mixed_controls_are_exact(self):
        with tempfile.TemporaryDirectory() as output_dir:
            root = Path(output_dir)
            MODULE.generate(root)
            with zipfile.ZipFile(
                root / "deflate-high-ratio.zip"
            ) as archive:
                info = archive.infolist()[0]
                payload = archive.read(info)
                self.assertEqual(len(payload), 1024 * 1024)
                self.assertGreater(
                    info.file_size / info.compress_size,
                    800,
                )
            with zipfile.ZipFile(
                root / "zipcrypto-stored.zip"
            ) as archive:
                with self.assertRaises(RuntimeError):
                    archive.read(archive.infolist()[0])
                self.assertEqual(
                    archive.read(
                        archive.infolist()[0],
                        pwd=MODULE.PASSWORD,
                    ),
                    MODULE.PDF,
                )
            with zipfile.ZipFile(
                root / "mixed-members.zip"
            ) as archive:
                self.assertEqual(
                    [info.filename for info in archive.infolist()],
                    ["payload.pdf", "note.bin"],
                )
                self.assertEqual(
                    [archive.read(info) for info in archive.infolist()],
                    [MODULE.PDF, b"A"],
                )

    def test_malformed_controls_are_rejected_independently(self):
        expected_exception = {
            "stored-bad-crc.zip": zipfile.BadZipFile,
            "deflate-corrupt.zip": zipfile.BadZipFile,
            "deflate-truncated.zip": zipfile.BadZipFile,
            "stored-local-only.zip": zipfile.BadZipFile,
            "stored-invalid-local-offset.zip": zipfile.BadZipFile,
            "unsupported-method-99.zip": NotImplementedError,
        }
        with tempfile.TemporaryDirectory() as output_dir:
            root = Path(output_dir)
            manifest = MODULE.generate(root)
            malformed = {
                sample["name"]
                for sample in manifest["samples"]
                if not sample["zipfile_readable"]
            }
            self.assertEqual(malformed, set(expected_exception))
            for name, exception in expected_exception.items():
                with self.subTest(sample=name):
                    with self.assertRaises(exception):
                        with zipfile.ZipFile(root / name) as archive:
                            for info in archive.infolist():
                                archive.read(info)

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
