import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ANALYZER = ROOT / "tools/rules/analyze_database_load_sizing.py"
REPORT = ROOT / "docs/research/data/database-load-sizing.json"


def load_analyzer():
    spec = importlib.util.spec_from_file_location(
        "analyze_database_load_sizing",
        ANALYZER,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class DatabaseLoadSizingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_analyzer()
        cls.report = json.loads(REPORT.read_text(encoding="utf-8"))

    def test_committed_report_is_exactly_reproducible(self):
        expected = self.module.serialize(
            self.module.build_report(ROOT)
        )
        self.assertEqual(REPORT.read_bytes(), expected)
        completed = subprocess.run(
            [sys.executable, str(ANALYZER), "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_fixed_bundle_inventory_and_extrema_are_exact(self):
        observed = self.report["observed_fixed_bundle"]
        self.assertEqual(observed["source_count"], 3)
        self.assertEqual(observed["entry_count"], 2268)
        self.assertEqual(observed["total_entry_bytes"], 2_909_316)
        self.assertEqual(observed["program_entry_count"], 2235)
        self.assertEqual(observed["program_entry_bytes"], 2_902_881)
        self.assertEqual(
            observed["maximum_single_entry_bytes"], 603_640
        )
        self.assertEqual(observed["maximum_path_components"], 3)
        self.assertGreater(observed["total_logical_path_bytes"], 0)
        self.assertGreater(
            observed["maximum_single_container_bytes"],
            max(layer["byte_count"] for layer in observed["layers"]),
        )
        self.assertEqual(
            [layer["database"] for layer in observed["layers"]],
            ["db", "db_extra", "db_custom"],
        )

    def test_candidates_follow_declared_formula_and_are_bounded(self):
        observed = self.report["observed_fixed_bundle"]
        profiles = self.report["profiles"]
        modern = profiles["modern_default"]
        legacy = profiles["legacy_high_resource"]
        field_map = {
            "maximum_sources": "source_count",
            "maximum_entries": "entry_count",
            "maximum_single_entry_bytes": (
                "maximum_single_entry_bytes"
            ),
            "maximum_total_entry_bytes": "total_entry_bytes",
            "maximum_single_container_bytes": (
                "maximum_single_container_bytes"
            ),
            "maximum_total_container_bytes": "total_container_bytes",
            "maximum_single_logical_path_bytes": (
                "maximum_single_logical_path_bytes"
            ),
            "maximum_total_logical_path_bytes": (
                "total_logical_path_bytes"
            ),
            "maximum_cache_records": "entry_count",
        }
        for limit, measurement in field_map.items():
            self.assertEqual(
                modern[limit],
                self.module.headroom(observed[measurement], 8),
            )
            self.assertEqual(
                legacy[limit],
                self.module.headroom(observed[measurement], 64),
            )
        self.assertEqual(
            modern["maximum_cache_bytes"],
            modern["maximum_total_entry_bytes"] * 2,
        )
        self.assertEqual(
            legacy["maximum_cache_bytes"],
            legacy["maximum_total_entry_bytes"] * 2,
        )
        self.assertFalse(legacy["default_for_any_adapter"])
        self.assertEqual(
            {modern["status"], legacy["status"]},
            {"review_candidate_not_admitted"},
        )
        self.assertTrue(
            all(
                value > 0
                for key, value in modern.items()
                if key != "status"
            )
        )

    def test_source_bindings_are_current(self):
        bindings = self.report["source_bindings"]
        self.assertEqual(set(bindings), set(self.module.SOURCES))
        for name, relative in self.module.SOURCES.items():
            self.assertEqual(bindings[name]["path"], relative)
            self.assertEqual(
                bindings[name]["sha256"],
                hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(),
            )

    def test_asset_or_behavior_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in self.module.SOURCES.values():
                destination = root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, destination)
            cache_path = root / self.module.SOURCES["cache_behavior"]
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
            cache["relationships"][
                "canceled_miss_saves_empty_cache"
            ] = False
            cache_path.write_text(
                json.dumps(cache, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                self.module.DatabaseSizingError,
                "cache behavior relationships drift",
            ):
                self.module.build_report(root)

    def test_docs_keep_candidate_unadmitted(self):
        research = (
            ROOT / "docs/research/database-load-sizing.md"
        ).read_text(encoding="utf-8")
        design = (
            ROOT / "docs/design/resource-limit-policy.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Status: In Review", research)
        self.assertIn(
            f"Upstream: `horsicq/DIE-engine@{self.module.UPSTREAM_COMMIT}`",
            research,
        )
        self.assertIn("review_candidate_not_admitted", research)
        self.assertIn("database load", design)


if __name__ == "__main__":
    unittest.main()
