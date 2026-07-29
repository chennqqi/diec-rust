import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT / "tools/corpus/generate_windows_path_closure_fixture.py"
)
MANIFEST = (
    ROOT / "docs/research/data/windows-path-closure-fixture.json"
)
SPEC = importlib.util.spec_from_file_location(
    "generate_windows_path_closure_fixture",
    SCRIPT,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class GenerateWindowsPathClosureFixtureTests(unittest.TestCase):
    def test_manifest_covers_every_named_closure_profile(self):
        manifest = MODULE.build_manifest()
        self.assertEqual(manifest["capability"], "CAP-CLI-IN-003")
        self.assertEqual(
            manifest["large_directory"]["cases"],
            [
                "empty_0",
                "single_1",
                "flat_256",
                "flat_4096",
                "nested_4096",
            ],
        )
        self.assertEqual(len(manifest["reparse"]["cases"]), 3)
        self.assertEqual(len(manifest["toctou"]["cases"]), 4)
        self.assertEqual(len(manifest["unc"]["cases"]), 8)
        self.assertEqual(len(manifest["acl"]["cases"]), 3)
        self.assertEqual(
            manifest["toctou"]["blocker_count"],
            128,
        )

    def test_committed_manifest_is_reproducible(self):
        expected = MODULE.serialize(MODULE.build_manifest())
        self.assertEqual(MANIFEST.read_bytes(), expected)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "manifest.json"
            subprocess.run(
                [sys.executable, str(SCRIPT), "--output", str(output)],
                check=True,
                capture_output=True,
            )
            self.assertEqual(output.read_bytes(), expected)

    def test_payload_and_toctou_hashes_are_exact(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(
            manifest["payload"]["sha256"],
            MODULE.PDF_SHA256,
        )
        self.assertEqual(
            manifest["toctou"]["new_target"]["sha256"],
            hashlib.sha256(MODULE.TOCTOU_NEW_PAYLOAD).hexdigest(),
        )


if __name__ == "__main__":
    unittest.main()
