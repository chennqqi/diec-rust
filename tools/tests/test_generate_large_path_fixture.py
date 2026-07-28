import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "corpus" / "generate_large_path_fixture.py"
MANIFEST_PATH = (
    ROOT / "docs" / "research" / "data" / "large-path-fixture.json"
)
SPEC = importlib.util.spec_from_file_location(
    "generate_large_path_fixture",
    SCRIPT,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class GenerateLargePathFixtureTest(unittest.TestCase):
    def test_committed_manifest_is_exact_generator_output(self) -> None:
        manifest = MODULE.build_manifest()
        self.assertEqual(
            MANIFEST_PATH.read_bytes(),
            MODULE.serialize(manifest),
        )
        self.assertEqual(
            json.loads(MANIFEST_PATH.read_text(encoding="utf-8")),
            manifest,
        )

    def test_case_matrix_and_counts_are_closed(self) -> None:
        manifest = MODULE.build_manifest()
        cases = {case["name"]: case for case in manifest["cases"]}
        self.assertEqual(
            set(cases),
            {
                "empty_0",
                "single_1",
                "flat_256",
                "flat_4096",
                "nested_4096",
            },
        )
        self.assertEqual(cases["flat_4096"]["file_count"], 4096)
        nested = cases["nested_4096"]
        self.assertEqual(
            nested["bucket_count"] * nested["files_per_bucket"],
            nested["file_count"],
        )
        self.assertEqual(nested["file_count"], 4096)

    def test_materialization_is_empty_and_creation_order_is_adversarial(self) -> None:
        materialization = MODULE.build_manifest()["materialization"]
        self.assertEqual(materialization["payload_size"], 0)
        self.assertEqual(
            materialization["payload_sha256"],
            MODULE.EMPTY_SHA256,
        )
        self.assertEqual(materialization["creation_order"], "descending")
        self.assertEqual(
            materialization["file_name_pattern"],
            "item-{index:06d}.empty",
        )

    def test_serialization_is_deterministic(self) -> None:
        first = MODULE.serialize(MODULE.build_manifest())
        second = MODULE.serialize(MODULE.build_manifest())
        self.assertEqual(first, second)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "manifest.json"
            output.write_bytes(first)
            self.assertEqual(output.read_bytes(), second)


if __name__ == "__main__":
    unittest.main()
