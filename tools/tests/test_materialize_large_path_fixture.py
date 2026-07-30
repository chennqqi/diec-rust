import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT / "tools/corpus/materialize_large_path_fixture.py"
)
MANIFEST = ROOT / "docs/research/data/large-path-fixture.json"
SPEC = importlib.util.spec_from_file_location(
    "materialize_large_path_fixture", SCRIPT
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class MaterializeLargePathFixtureTest(unittest.TestCase):
    def test_materialized_inventory_matches_fixed_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "fixture"
            report = MODULE.materialize(ROOT, MANIFEST, output)
            manifest = json.loads(MANIFEST.read_bytes())
            self.assertEqual(
                report["cases"],
                MODULE.validate_materialized(manifest, output),
            )
            self.assertEqual(
                report["cases"]["flat_4096"]["file_count"],
                4096,
            )
            self.assertEqual(
                report["cases"]["nested_4096"]["last_file"],
                "bucket-015/item-000255.empty",
            )

    def test_nonempty_output_and_tampering_fail_closed(self) -> None:
        manifest = json.loads(MANIFEST.read_bytes())
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "fixture"
            output.mkdir()
            (output / "unexpected").touch()
            with self.assertRaisesRegex(
                MODULE.FixtureError, "must be empty"
            ):
                MODULE.materialize(ROOT, MANIFEST, output)

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "fixture"
            MODULE.materialize(ROOT, MANIFEST, output)
            target = output / "flat_256" / "item-000000.empty"
            target.write_bytes(b"x")
            with self.assertRaisesRegex(
                MODULE.FixtureError, "payload is not empty"
            ):
                MODULE.validate_materialized(manifest, output)


if __name__ == "__main__":
    unittest.main()
