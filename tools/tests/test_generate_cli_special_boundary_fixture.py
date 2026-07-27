import hashlib
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "tools"
    / "corpus"
    / "generate_cli_special_boundary_fixture.py"
)
COMMITTED = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "cli-special-boundary-fixture.json"
)
SPEC = importlib.util.spec_from_file_location(
    "generate_cli_special_boundary_fixture",
    SCRIPT,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def entropy(data: bytes) -> float:
    counts = [0] * 256
    for value in data:
        counts[value] += 1
    result = 0.0
    for count in counts:
        if count:
            probability = count / len(data)
            result -= probability * math.log2(probability)
    return result


class GenerateCliSpecialBoundaryFixtureTest(unittest.TestCase):
    def test_committed_manifest_is_exact_generator_output(self):
        manifest, _ = MODULE.build_fixture()
        self.assertEqual(COMMITTED.read_bytes(), MODULE.serialize(manifest))

    def test_generated_files_match_manifest_and_entropy_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = MODULE.write_fixture(root)
            entries = manifest["entries"]
            self.assertEqual(len(entries), 7)
            entropy_entries = entries[:3]
            self.assertEqual(
                [
                    entry["expected_status"]
                    for entry in entropy_entries
                ],
                ["not packed", "not packed", "packed"],
            )
            self.assertEqual(
                [
                    entry["theoretical_entropy"]
                    for entry in entropy_entries
                ],
                [6.484375, 6.5, 6.515625],
            )
            for entry in entries:
                data = (root / entry["name"]).read_bytes()
                self.assertEqual(len(data), entry["size"])
                self.assertEqual(
                    hashlib.sha256(data).hexdigest(),
                    entry["sha256"],
                )
            for entry in entropy_entries:
                data = (root / entry["name"]).read_bytes()
                self.assertEqual(
                    entropy(data),
                    entry["theoretical_entropy"],
                )
            dependency = manifest["dependencies"][0]
            self.assertEqual(
                dependency["sha256"],
                hashlib.sha256(
                    (ROOT / dependency["path"]).read_bytes()
                ).hexdigest(),
            )
            self.assertEqual(
                json.loads((root / "manifest.json").read_text()),
                manifest,
            )

    def test_nonempty_output_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "existing").write_text("sentinel")
            with self.assertRaisesRegex(
                ValueError, "absent or empty"
            ):
                MODULE.write_fixture(root)


if __name__ == "__main__":
    unittest.main()
