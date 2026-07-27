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
    / "generate_database_fixture.py"
)
SPEC = importlib.util.spec_from_file_location(
    "generate_database_fixture", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class GenerateDatabaseFixtureTests(unittest.TestCase):
    def test_generates_same_manifest_and_files_twice(self):
        with tempfile.TemporaryDirectory() as first_directory:
            with tempfile.TemporaryDirectory() as second_directory:
                first = pathlib.Path(first_directory)
                second = pathlib.Path(second_directory)

                first_manifest = MODULE.generate(first)
                second_manifest = MODULE.generate(second)

                self.assertEqual(first_manifest, second_manifest)
                self.assertEqual(
                    (first / "manifest.json").read_bytes(),
                    (second / "manifest.json").read_bytes(),
                )
                for entry in first_manifest["entries"]:
                    path = pathlib.PurePosixPath(entry["path"])
                    self.assertEqual(
                        (first / path).read_bytes(),
                        (second / path).read_bytes(),
                    )

    def test_covers_directory_and_archive_database_states(self):
        paths = {entry[0] for entry in MODULE.FILES}
        self.assertIn("not-a-database.bin", paths)
        self.assertIn("malformed-main/Binary/broken.1.sg", paths)
        self.assertIn("throwing-main/Binary/throw.1.sg", paths)
        self.assertIn("valid-main/Binary/fixture.1.sg", paths)
        self.assertIn("valid-main.zip", paths)
        self.assertIn("empty-main.zip", paths)
        self.assertIn("truncated-main.zip", paths)
        self.assertIn("local-only-main.zip", paths)
        self.assertIn("payload-truncated-main.zip", paths)
        self.assertIn("payload-structure-truncated-main.zip", paths)
        self.assertIn("local-header-truncated-main.zip", paths)
        self.assertIn("duplicate-main.zip", paths)
        self.assertIn("traversal-main.zip", paths)
        self.assertIn("prefixed-main.zip", paths)
        self.assertIn("empty-main", MODULE.DIRECTORIES)

    def test_zip_fixtures_are_deterministic_and_structurally_distinct(self):
        with zipfile.ZipFile(
            io.BytesIO(MODULE.VALID_ZIP),
            mode="r",
        ) as archive:
            self.assertEqual(
                archive.namelist(),
                ["Binary/fixture.1.sg"],
            )
            self.assertEqual(
                archive.read("Binary/fixture.1.sg"),
                MODULE.VALID_RULE,
            )

        with zipfile.ZipFile(
            io.BytesIO(MODULE.DUPLICATE_ZIP),
            mode="r",
        ) as archive:
            self.assertEqual(
                archive.namelist(),
                [
                    "Binary/duplicate.1.sg",
                    "Binary/duplicate.1.sg",
                ],
            )

        with zipfile.ZipFile(
            io.BytesIO(MODULE.TRAVERSAL_ZIP),
            mode="r",
        ) as archive:
            self.assertEqual(
                archive.namelist(),
                ["Binary/../traversal.1.sg"],
            )

        for truncated in (
            MODULE.EOCD_TRUNCATED_ZIP,
            MODULE.CENTRAL_DIRECTORY_TRUNCATED_ZIP,
            MODULE.PAYLOAD_TRUNCATED_ZIP,
            MODULE.PAYLOAD_STRUCTURE_TRUNCATED_ZIP,
            MODULE.LOCAL_HEADER_TRUNCATED_ZIP,
        ):
            with self.subTest(size=len(truncated)):
                self.assertLess(len(truncated), len(MODULE.VALID_ZIP))
                with self.assertRaises(zipfile.BadZipFile):
                    zipfile.ZipFile(io.BytesIO(truncated), mode="r")

    def test_matches_versioned_reference_manifest(self):
        reference_path = (
            pathlib.Path(__file__).parents[2]
            / "docs"
            / "research"
            / "data"
            / "database-fixture.json"
        )
        with tempfile.TemporaryDirectory() as output_directory:
            output = pathlib.Path(output_directory)
            MODULE.generate(output)
            generated = (output / "manifest.json").read_bytes()

        self.assertEqual(generated, reference_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
