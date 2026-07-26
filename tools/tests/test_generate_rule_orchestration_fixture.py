import hashlib
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT
    / "tools"
    / "corpus"
    / "generate_rule_orchestration_fixture.py"
)
MANIFEST_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "rule-orchestration-fixture.json"
)
SPEC = importlib.util.spec_from_file_location(
    "generate_rule_orchestration_fixture",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class GenerateRuleOrchestrationFixtureTests(unittest.TestCase):
    def test_generation_is_deterministic_and_matches_manifest(self):
        expected = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as first_directory:
            with tempfile.TemporaryDirectory() as second_directory:
                first_root = pathlib.Path(first_directory)
                second_root = pathlib.Path(second_directory)
                first = MODULE.generate(first_root)
                second = MODULE.generate(second_root)

                self.assertEqual(first, expected)
                self.assertEqual(second, expected)
                for entry in expected["entries"]:
                    first_data = (
                        first_root / pathlib.PurePosixPath(entry["path"])
                    ).read_bytes()
                    second_data = (
                        second_root / pathlib.PurePosixPath(entry["path"])
                    ).read_bytes()
                    self.assertEqual(first_data, second_data)
                    self.assertEqual(len(first_data), entry["size"])
                    self.assertEqual(
                        hashlib.sha256(first_data).hexdigest(),
                        entry["sha256"],
                    )

    def test_fixture_covers_layers_filters_init_and_include(self):
        manifest = json.loads(
            MANIFEST_PATH.read_text(encoding="utf-8")
        )
        paths = {entry["path"] for entry in manifest["entries"]}
        self.assertTrue(
            {
                "main/_init",
                "extra/_init",
                "custom/_init",
                "main/shared_helper",
                "extra/shared_helper",
                "custom/shared_helper",
                "main/Binary/_init",
                "extra/Binary/_init",
                "custom/Binary/_init",
                "main/Binary/DS.deep.2.sg",
                "main/Binary/EP.entrypoint.4.sg",
                "main/Binary/HEUR.heuristic.3.sg",
                "main/PE/decoy.0.sg",
                "priority-main/Binary/z_priority.1.sg",
                "priority-main/Binary/a_priority.2.sg",
                "priority-main/Binary/m_priority.4.sg",
            }.issubset(paths)
        )
        self.assertEqual(
            manifest["mode_orders"]["combined"],
            [
                "DS.deep.2.sg",
                "HEUR.heuristic.3.sg",
                "EP.entrypoint.4.sg",
                "z_normal.1.sg",
                "a_extra.0.sg",
                "a_custom.0.sg",
            ],
        )
        self.assertEqual(
            manifest["priority_only_order"],
            [
                "z_priority.1.sg",
                "a_priority.2.sg",
                "m_priority.4.sg",
            ],
        )


if __name__ == "__main__":
    unittest.main()
