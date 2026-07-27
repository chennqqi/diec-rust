import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "research" / "build_source_only_closure.py"
COVERAGE = (
    ROOT / "docs" / "research" / "data" / "capability-coverage.json"
)
MANIFEST = (
    ROOT / "docs" / "research" / "data" / "source-only-closure.json"
)
SPEC = importlib.util.spec_from_file_location(
    "build_source_only_closure",
    SCRIPT,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class SourceOnlyClosureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.coverage, cls.raw = MODULE.load_json(COVERAGE)
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_committed_manifest_is_exact_generator_output(self):
        expected = MODULE.build_manifest(self.coverage, self.raw)
        self.assertEqual(self.manifest, expected)
        self.assertEqual(MANIFEST.read_bytes(), MODULE.serialize(expected))

    def test_manifest_is_the_exact_source_only_closed_set(self):
        expected_ids = {
            row["id"]
            for row in self.coverage["rows"]
            if row["platform_status"][MODULE.PLATFORM].startswith(
                "source_only"
            )
        }
        items = self.manifest["items"]
        self.assertEqual({item["id"] for item in items}, expected_ids)
        self.assertEqual(len(items), len(expected_ids))
        self.assertEqual(len(items), 1)

    def test_every_item_has_actionable_closure_evidence(self):
        for item in self.manifest["items"]:
            with self.subTest(capability=item["id"]):
                self.assertTrue(item["missing_evidence"])
                experiment = item["proposed_experiment"]
                self.assertTrue(experiment["fixture"])
                self.assertTrue(experiment["harness"])
                self.assertEqual(
                    experiment["platform"],
                    "linux-x86_64-qt5",
                )
                self.assertGreaterEqual(len(experiment["assertions"]), 3)
                self.assertTrue(item["acceptance"])
        summary = self.manifest["summary"]
        self.assertTrue(summary["all_items_have_missing_evidence"])
        self.assertTrue(summary["all_items_have_executable_assertions"])
        self.assertFalse(summary["phase_0_source_only_closed"])

    def test_negative_capabilities_keep_explicit_closure_kinds(self):
        items = {item["id"]: item for item in self.manifest["items"]}
        self.assertEqual(
            items["CAP-NEST-009"]["closure_kind"],
            "bounded_escalation_and_adr",
        )

    def test_catalog_drift_and_duplicate_json_are_rejected(self):
        changed = json.loads(json.dumps(self.coverage))
        for row in changed["rows"]:
            if row["id"] == "CAP-CLI-IN-001":
                row["platform_status"][MODULE.PLATFORM] = (
                    "source_only_runtime_corpus_missing"
                )
                break
        with self.assertRaisesRegex(MODULE.ClosureError, "catalog drift"):
            MODULE.build_manifest(changed, self.raw)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"schema_version":1,"schema_version":1}')
            with self.assertRaisesRegex(
                MODULE.ClosureError,
                "duplicate JSON key",
            ):
                MODULE.load_json(path)


if __name__ == "__main__":
    unittest.main()
