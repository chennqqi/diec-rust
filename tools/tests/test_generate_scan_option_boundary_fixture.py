import hashlib
import importlib.util
import json
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "tools"
    / "corpus"
    / "generate_scan_option_boundary_fixture.py"
)
MANIFEST = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "scan-option-boundary-fixture.json"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "_scan_option_boundary_fixture",
        SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load fixture generator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ScanOptionBoundaryFixtureTests(unittest.TestCase):
    def test_generation_is_reproducible_and_matches_manifest(self):
        module = load_module()
        expected = json.loads(MANIFEST.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temporary:
            output = pathlib.Path(temporary)
            actual = module.generate(output)
            self.assertEqual(actual, expected)
            for entry in expected["entries"]:
                data = (output / entry["path"]).read_bytes()
                self.assertEqual(len(data), entry["size"])
                self.assertEqual(
                    hashlib.sha256(data).hexdigest(),
                    entry["sha256"],
                )

    def test_fixture_covers_exact_deep_and_resource_boundaries(self):
        module = load_module()
        files = {
            path: data for path, data, _purpose in module.FILES
        }
        self.assertIn(
            b"Binary deep",
            files["database/Binary/DS.deep.2.sg"],
        )
        self.assertIn(
            b"Binary entrypoint",
            files["database/Binary/EP.entrypoint.3.sg"],
        )
        self.assertEqual(
            files["input/pe-22-pdf.exe"].count(b"%PDF-1.4"),
            22,
        )
        self.assertGreater(
            len(files["input/pe-2002-unclassified.exe"]),
            90_000,
        )
        self.assertEqual(
            len(module.make_grouped_pe_resources((668, 667, 667), b"\0")),
            len(files["input/pe-2002-unclassified.exe"]),
        )
        with self.assertRaises(ValueError):
            module.make_grouped_pe_resources((1001,), b"\0")
        self.assertEqual(
            module.generate.__module__,
            "_scan_option_boundary_fixture",
        )

    def test_manifest_inventory_is_closed(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(
            manifest["generator"],
            "tools/corpus/generate_scan_option_boundary_fixture.py",
        )
        self.assertEqual(
            manifest["boundaries"],
            {
                "aggressive_resource_scan_count": 2001,
                "default_resource_scan_count": 21,
                "resource_enumeration_count": 10000,
            },
        )
        self.assertEqual(len(manifest["entries"]), 9)


if __name__ == "__main__":
    unittest.main()
