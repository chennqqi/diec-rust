import hashlib
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "corpus" / "generate_path_toctou_fixture.py"
MANIFEST_PATH = (
    ROOT / "docs" / "research" / "data" / "path-toctou-fixture.json"
)
SPEC = importlib.util.spec_from_file_location(
    "generate_path_toctou_fixture",
    SCRIPT,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class GeneratePathToctouFixtureTest(unittest.TestCase):
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

    def test_cases_have_stable_controls_and_two_mutations(self) -> None:
        cases = MODULE.build_manifest()["cases"]
        self.assertEqual(
            [case["name"] for case in cases],
            [
                "stable_old",
                "stable_new",
                "swap_old_to_new",
                "remove_old_after_enumeration",
            ],
        )
        self.assertEqual(
            [case["expected_open_target"] for case in cases],
            ["old", "new", "new", "missing"],
        )
        self.assertEqual(
            [case["action"] for case in cases],
            [
                "none",
                "none",
                "replace_symlink_with_new_target",
                "unlink_symlink",
            ],
        )

    def test_payloads_and_sync_point_are_deterministic(self) -> None:
        manifest = MODULE.build_manifest()
        materialization = manifest["materialization"]
        self.assertEqual(
            materialization["blocker"]["size"],
            32 * 1024 * 1024,
        )
        self.assertEqual(
            materialization["blocker"]["sha256"],
            MODULE.zero_sha256(32 * 1024 * 1024),
        )
        self.assertEqual(materialization["old_target"]["size"], 0)
        self.assertEqual(
            materialization["new_target"]["size"],
            len(MODULE.NEW_PAYLOAD),
        )
        self.assertEqual(
            materialization["new_target"]["sha256"],
            hashlib.sha256(MODULE.NEW_PAYLOAD).hexdigest(),
        )
        synchronization = manifest["synchronization"]
        self.assertEqual(synchronization["stdout"], "stdbuf -oL")
        self.assertEqual(synchronization["stop_signal"], "SIGSTOP")
        self.assertEqual(synchronization["resume_signal"], "SIGCONT")
        self.assertIn("WUNTRACED", synchronization["mutation"])


if __name__ == "__main__":
    unittest.main()
