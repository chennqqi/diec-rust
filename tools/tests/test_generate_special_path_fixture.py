import importlib.util
import io
import pathlib
import sys
import tarfile
import tempfile
import unittest


TOOLS_DIR = pathlib.Path(__file__).parents[1]
ROOT = pathlib.Path(__file__).parents[2]


def load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BASELINE = load_module(
    "generate_baseline_corpus_for_special_path_tests",
    TOOLS_DIR / "corpus" / "generate_baseline_corpus.py",
)
MODULE = load_module(
    "generate_special_path_fixture",
    TOOLS_DIR / "corpus" / "generate_special_path_fixture.py",
)


class GenerateSpecialPathFixtureTests(unittest.TestCase):
    def _generate(self, root: pathlib.Path):
        baseline = root / "baseline"
        output = root / "output"
        BASELINE.generate(baseline)
        manifest = MODULE.generate(baseline, output)
        return baseline, output, manifest

    def test_archive_is_deterministic_and_matches_reference_manifest(self):
        with tempfile.TemporaryDirectory() as first_dir:
            with tempfile.TemporaryDirectory() as second_dir:
                _, first, first_manifest = self._generate(
                    pathlib.Path(first_dir)
                )
                _, second, second_manifest = self._generate(
                    pathlib.Path(second_dir)
                )
                self.assertEqual(first_manifest, second_manifest)
                self.assertEqual(
                    (first / MODULE.ARCHIVE_NAME).read_bytes(),
                    (second / MODULE.ARCHIVE_NAME).read_bytes(),
                )
                self.assertEqual(
                    (first / "manifest.json").read_bytes(),
                    (
                        ROOT
                        / "docs"
                        / "research"
                        / "data"
                        / "special-path-fixture.json"
                    ).read_bytes(),
                )

    def test_archive_names_and_payloads_round_trip_with_tarfile(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline, output, manifest = self._generate(
                pathlib.Path(directory)
            )
            payload = (baseline / MODULE.SOURCE_NAME).read_bytes()
            archive = (output / MODULE.ARCHIVE_NAME).read_bytes()
            with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
                members = tar.getmembers()
                self.assertEqual(
                    [member.name for member in members],
                    [
                        *(value.rstrip("/") for value in MODULE.DIRECTORIES),
                        *MODULE.FILES,
                    ],
                )
                for member in members[len(MODULE.DIRECTORIES) :]:
                    stream = tar.extractfile(member)
                    self.assertIsNotNone(stream)
                    assert stream is not None
                    self.assertEqual(stream.read(), payload)

            self.assertEqual(
                [entry["path"] for entry in manifest["files"]],
                list(MODULE.FILES),
            )

    def test_matrix_contains_distinct_unicode_and_special_names(self):
        names = set(MODULE.FILES)
        required = {
            "paths/special/é-nfc.pdf",
            "paths/special/e\u0301-nfd.pdf",
            "paths/special/中文.pdf",
            "paths/special/emoji-😀.pdf",
            "paths/special/ leading-space.pdf",
            "paths/special/trailing-space.pdf ",
            "paths/special/tab\tname.pdf",
            "paths/special/line\nbreak.pdf",
            "paths/special/colon:name.pdf",
            "paths/special/backslash\\name.pdf",
            "paths/special/--leading-dash.pdf",
            "paths/special/.hidden.pdf",
        }
        self.assertTrue(required.issubset(names))
        self.assertNotEqual(
            "é-nfc.pdf".encode("utf-8"),
            "e\u0301-nfd.pdf".encode("utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
