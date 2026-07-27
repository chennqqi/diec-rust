import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT / "tools" / "corpus" / "generate_archive_limit_fixture.py"
)
REFERENCE_PATH = (
    ROOT / "docs" / "research" / "data" / "archive-limit-corpus.json"
)
SPEC = importlib.util.spec_from_file_location(
    "generate_archive_limit_fixture", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def inspect_chain(data: bytes) -> tuple[int, int, bytes]:
    depth = 0
    cumulative = 0
    payload = data
    while payload.startswith(b"PK\x03\x04"):
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            infos = archive.infolist()
            if len(infos) != 1:
                raise AssertionError("fixture level is not single-member")
            info = infos[0]
            if info.compress_type != zipfile.ZIP_STORED:
                raise AssertionError("fixture member is compressed")
            payload = archive.read(info)
            cumulative += len(payload)
            depth += 1
    return depth, cumulative, payload


class GenerateArchiveLimitFixtureTests(unittest.TestCase):
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
                    name = sample["name"]
                    self.assertEqual(
                        (first / name).read_bytes(),
                        (second / name).read_bytes(),
                    )

    def test_every_level_has_one_stored_member_and_exact_accounting(self):
        with tempfile.TemporaryDirectory() as output_dir:
            root = Path(output_dir)
            manifest = MODULE.generate(root)
            for sample in manifest["samples"]:
                with self.subTest(sample=sample["name"]):
                    depth, cumulative, leaf = inspect_chain(
                        (root / sample["name"]).read_bytes()
                    )
                    self.assertEqual(depth, sample["depth"])
                    self.assertEqual(
                        cumulative,
                        sample["cumulative_expanded_bytes"],
                    )
                    self.assertEqual(len(leaf), sample["leaf_size"])
                    self.assertTrue(leaf.startswith(b"%PDF-1.4"))

    def test_series_isolate_depth_and_expanded_byte_dimensions(self):
        with tempfile.TemporaryDirectory() as output_dir:
            manifest = MODULE.generate(Path(output_dir))
        depth_series = [
            sample
            for sample in manifest["samples"]
            if sample["series"] == "depth"
        ]
        expanded_series = [
            sample
            for sample in manifest["samples"]
            if sample["series"] == "expanded_bytes"
        ]

        self.assertEqual(
            [sample["depth"] for sample in depth_series],
            list(MODULE.DEPTHS),
        )
        self.assertEqual(
            len({sample["leaf_size"] for sample in depth_series}),
            1,
        )
        self.assertEqual(
            {sample["depth"] for sample in expanded_series},
            {MODULE.EXPANDED_DEPTH},
        )
        self.assertEqual(
            [sample["leaf_size"] for sample in expanded_series],
            list(MODULE.EXPANDED_LEAF_SIZES),
        )
        self.assertTrue(
            all(
                left["cumulative_expanded_bytes"]
                < right["cumulative_expanded_bytes"]
                for left, right in zip(
                    expanded_series,
                    expanded_series[1:],
                )
            )
        )

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
