import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "research" / "build_capability_coverage.py"
TRACEABILITY = (
    ROOT / "docs" / "research" / "data" / "capability-traceability.json"
)
REPORT = ROOT / "docs" / "research" / "data" / "capability-coverage.json"
SPEC = importlib.util.spec_from_file_location(
    "build_capability_coverage",
    SCRIPT,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class CapabilityCoverageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.traceability, cls.raw = MODULE.load_json(TRACEABILITY)
        cls.report = json.loads(REPORT.read_text(encoding="utf-8"))

    def test_committed_report_is_exact_generator_output(self):
        expected = MODULE.build_report(self.traceability, self.raw)
        self.assertEqual(self.report, expected)
        self.assertEqual(REPORT.read_bytes(), MODULE.serialize(expected))

    def test_all_capabilities_and_platform_cells_are_classified(self):
        summary = self.report["summary"]
        self.assertEqual(summary["capability_row_count"], 68)
        self.assertEqual(summary["platform_count"], 4)
        self.assertEqual(summary["cell_count"], 272)
        self.assertEqual(summary["unclassified_capability_row_count"], 0)
        self.assertEqual(summary["unclassified_cell_count"], 0)
        self.assertEqual(
            summary["with_gap_status_without_named_gap_count"],
            0,
        )
        self.assertFalse(summary["phase_0_coverage_complete"])

        traceability_ids = {
            item["id"] for item in self.traceability["capabilities"]
        }
        rows = self.report["rows"]
        self.assertEqual({row["id"] for row in rows}, traceability_ids)
        self.assertEqual(len(rows), len(traceability_ids))
        for row in rows:
            self.assertEqual(
                set(row["platform_status"]),
                set(self.report["target_platforms"]),
            )

    def test_linux_runtime_and_source_only_counts_are_not_conflated(self):
        counts = self.report["summary"]["status_counts_by_platform"]
        linux = counts["linux-x86_64-qt5"]
        self.assertEqual(linux["runtime_observed"], 43)
        self.assertEqual(linux["runtime_observed_with_corpus_gaps"], 20)
        self.assertEqual(
            linux["source_only_runtime_corpus_missing"],
            4,
        )
        self.assertEqual(linux["source_only_with_corpus_gaps"], 1)
        self.assertEqual(linux["platform_missing"], 0)

        for platform in (
            "linux-x86_64-qt6",
            "windows-x86_64-qt5",
            "macos-x86_64-qt5",
        ):
            self.assertEqual(counts[platform]["platform_missing"], 68)

        rows = {row["id"]: row for row in self.report["rows"]}
        for capability_id in (
            "CAP-CLI-MODE-005",
            "CAP-CLI-MODE-006",
            "CAP-DISPATCH-001",
            "CAP-DISPATCH-005",
            "CAP-DISPATCH-006",
            "CAP-DISPATCH-008",
            "CAP-RESULT-001",
            "CAP-RESULT-002",
            "CAP-RESULT-003",
            "CAP-RESULT-004",
            "CAP-RESULT-005",
            "CAP-RESULT-006",
        ):
            self.assertEqual(
                rows[capability_id]["platform_status"][
                    "linux-x86_64-qt5"
                ],
                "runtime_observed",
            )
            self.assertEqual(rows[capability_id]["corpus_gap_ids"], [])
        self.assertEqual(
            rows["CAP-DISPATCH-004"]["platform_status"][
                "linux-x86_64-qt5"
            ],
            "runtime_observed_with_corpus_gaps",
        )
        self.assertEqual(
            rows["CAP-DISPATCH-004"]["corpus_gap_ids"],
            ["CAP-GAP-006"],
        )
        self.assertEqual(
            rows["CAP-DISPATCH-007"]["platform_status"][
                "linux-x86_64-qt5"
            ],
            "runtime_observed_with_corpus_gaps",
        )
        self.assertEqual(
            rows["CAP-DISPATCH-007"]["corpus_gap_ids"],
            ["CAP-GAP-012"],
        )

    def test_every_declared_gap_maps_to_known_capabilities(self):
        row_ids = {row["id"] for row in self.report["rows"]}
        gap_ids = []
        for gap in self.report["coverage_gaps"]:
            gap_ids.append(gap["id"])
            self.assertTrue(gap["capability_ids"])
            self.assertLessEqual(set(gap["capability_ids"]), row_ids)
        self.assertEqual(
            gap_ids,
            [f"CAP-GAP-{index:03d}" for index in range(1, 13)],
        )

    def test_every_with_gaps_status_has_a_named_corpus_gap(self):
        for row in self.report["rows"]:
            status = row["platform_status"]["linux-x86_64-qt5"]
            if "with_corpus_gaps" in status:
                self.assertTrue(
                    row["corpus_gap_ids"],
                    msg=row["id"],
                )

    def test_strict_input_rejects_duplicate_keys_and_changed_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "traceability.json"
            path.write_text('{"schema_version":1,"schema_version":1}')
            with self.assertRaisesRegex(
                MODULE.CoverageError,
                "duplicate JSON key",
            ):
                MODULE.load_json(path)

        changed = dict(self.traceability)
        changed["platform_scope"] = [
            "linux-x86_64-qt5",
            "linux-x86_64-qt6",
        ]
        with self.assertRaisesRegex(
            MODULE.CoverageError,
            "platform scope",
        ):
            MODULE.build_report(changed, self.raw)


if __name__ == "__main__":
    unittest.main()
