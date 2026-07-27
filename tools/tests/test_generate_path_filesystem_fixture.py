import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
REFERENCE = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "path-filesystem-fixture.json"
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BASELINE = load_module(
    "generate_baseline_for_path_filesystem_tests",
    TOOLS / "corpus" / "generate_baseline_corpus.py",
)
MODULE = load_module(
    "generate_path_filesystem_fixture",
    TOOLS / "corpus" / "generate_path_filesystem_fixture.py",
)


class GeneratePathFilesystemFixtureTests(unittest.TestCase):
    def generate(self, root: Path):
        baseline = root / "baseline"
        fixture = root / "fixture"
        BASELINE.generate(baseline)
        manifest = MODULE.generate(baseline, fixture)
        return baseline, fixture, manifest

    def test_fixture_is_deterministic_and_matches_reference(self):
        with tempfile.TemporaryDirectory() as first_directory:
            with tempfile.TemporaryDirectory() as second_directory:
                _, first, first_manifest = self.generate(
                    Path(first_directory)
                )
                _, second, second_manifest = self.generate(
                    Path(second_directory)
                )
                self.assertEqual(first_manifest, second_manifest)
                self.assertEqual(
                    (first / MODULE.ARCHIVE_NAME).read_bytes(),
                    (second / MODULE.ARCHIVE_NAME).read_bytes(),
                )
                self.assertEqual(
                    (first / "manifest.json").read_bytes(),
                    REFERENCE.read_bytes(),
                )

    def test_tar_members_preserve_modes_links_depth_and_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline, fixture, manifest = self.generate(Path(directory))
            payload = (baseline / MODULE.SOURCE_NAME).read_bytes()
            archive = (fixture / MODULE.ARCHIVE_NAME).read_bytes()
            with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
                members = tar.getmembers()
                self.assertEqual(
                    [member.name for member in members],
                    [
                        entry["path"].rstrip("/")
                        for entry in manifest["entries"]
                    ],
                )
                for member, record in zip(
                    members, manifest["entries"], strict=True
                ):
                    with self.subTest(path=record["path"]):
                        self.assertEqual(member.mode, record["mode"])
                        if record["type"] == "file":
                            stream = tar.extractfile(member)
                            self.assertIsNotNone(stream)
                            assert stream is not None
                            data = stream.read()
                            self.assertEqual(data, payload)
                            self.assertEqual(
                                hashlib.sha256(data).hexdigest(),
                                record["sha256"],
                            )
                        elif record["type"] == "symlink":
                            self.assertTrue(member.issym())
                            self.assertEqual(
                                member.linkname, record["target"]
                            )
                        else:
                            self.assertTrue(member.isdir())

    def test_matrix_has_file_dir_dangling_cycle_permission_and_depth(self):
        records = {entry["path"]: entry for entry in MODULE.entries()}
        self.assertEqual(
            records["paths/symlink/file-link.pdf"]["target"],
            "target.pdf",
        )
        self.assertEqual(
            records["paths/symlink/dir-link"]["target"],
            "dir-target",
        )
        self.assertEqual(
            records["paths/symlink/dangling.pdf"]["target"],
            "missing.pdf",
        )
        self.assertEqual(records["paths/cycle/loop"]["target"], ".")
        self.assertEqual(records["paths/denied/"]["mode"], 0)
        deep_directories = [
            entry
            for entry in records.values()
            if (
                entry["type"] == "directory"
                and entry["path"].startswith("paths/deep/level-")
            )
        ]
        self.assertEqual(len(deep_directories), MODULE.DEEP_LEVELS)

    def test_loader_rejects_modified_baseline_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / "baseline"
            BASELINE.generate(baseline)
            path = baseline / MODULE.SOURCE_NAME
            path.write_bytes(path.read_bytes() + b"x")
            with self.assertRaisesRegex(
                ValueError, "baseline corpus sample mismatch"
            ):
                MODULE.generate(baseline, root / "fixture")


if __name__ == "__main__":
    unittest.main()
