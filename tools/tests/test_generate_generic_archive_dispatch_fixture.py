import gzip
import hashlib
import importlib.util
import json
import pathlib
import sys
import tarfile
import tempfile
import unittest
import zipfile


ROOT = pathlib.Path(__file__).parents[2]
GENERATOR_PATH = (
    ROOT
    / "tools"
    / "corpus"
    / "generate_generic_archive_dispatch_fixture.py"
)
MANIFEST_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "generic-archive-dispatch-fixture.json"
)
SPEC = importlib.util.spec_from_file_location(
    "generate_generic_archive_dispatch_fixture",
    GENERATOR_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


class GenerateGenericArchiveDispatchFixtureTests(unittest.TestCase):
    def test_generation_matches_manifest_and_is_reproducible(self):
        expected = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as first_dir:
            with tempfile.TemporaryDirectory() as second_dir:
                first = pathlib.Path(first_dir)
                second = pathlib.Path(second_dir)
                self.assertEqual(MODULE.generate(first), expected)
                self.assertEqual(MODULE.generate(second), expected)
                self.assertEqual(
                    (first / "manifest.json").read_bytes(),
                    MANIFEST_PATH.read_bytes(),
                )
                for sample in expected["samples"]:
                    first_data = (first / sample["name"]).read_bytes()
                    second_data = (second / sample["name"]).read_bytes()
                    self.assertEqual(first_data, second_data)
                    self.assertEqual(len(first_data), sample["size"])
                    self.assertEqual(sha256(first_data), sample["sha256"])

    def test_standard_library_parses_each_archive_and_payload(self):
        expected_payload = MODULE.BASELINE.PAYLOAD
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            MODULE.generate(root)
            with zipfile.ZipFile(root / "payload.zip") as archive:
                self.assertEqual(archive.namelist(), ["payload.txt"])
                self.assertEqual(
                    archive.read("payload.txt"),
                    expected_payload,
                )
            with tarfile.open(root / "payload.tar", mode="r:") as archive:
                self.assertEqual(archive.getnames(), ["payload.txt"])
                member = archive.extractfile("payload.txt")
                assert member is not None
                self.assertEqual(member.read(), expected_payload)
                info = archive.getmember("payload.txt")
                self.assertEqual(info.mtime, 0)
                self.assertEqual(info.uid, 0)
                self.assertEqual(info.gid, 0)
            gzip_data = (root / "payload.txt.gz").read_bytes()
            self.assertEqual(
                gzip_data[:10],
                bytes.fromhex("1f8b08000000000000ff"),
            )
            self.assertEqual(gzip.decompress(gzip_data), expected_payload)

    def test_manifest_payload_identity_is_exact(self):
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        payload_digest = sha256(MODULE.BASELINE.PAYLOAD)
        self.assertEqual(
            [sample["archive_format"] for sample in manifest["samples"]],
            ["ZIP", "TAR", "GZIP"],
        )
        self.assertTrue(
            all(
                sample["expected_payload_sha256"] == payload_digest
                for sample in manifest["samples"]
            )
        )


if __name__ == "__main__":
    unittest.main()
