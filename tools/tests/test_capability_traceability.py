import json
from pathlib import Path
import re
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = ROOT / "docs" / "research" / "capability-matrix.md"
MANIFEST_PATH = (
    ROOT / "docs" / "research" / "data" / "capability-traceability.json"
)
LOCK_PATH = ROOT / "upstream" / "components.lock.toml"
CAPABILITY_ID = re.compile(
    r"CAP-(?:(?:CLI|ENG)-[A-Z]+-\d{3}|(?:RULE|DISPATCH|NEST|RESULT)-\d{3})"
)


def reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


class CapabilityTraceabilityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.matrix = MATRIX_PATH.read_text(encoding="utf-8")
        cls.manifest = json.loads(
            MANIFEST_PATH.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicate_keys,
        )
        with LOCK_PATH.open("rb") as stream:
            cls.upstream_lock = tomllib.load(stream)

    def test_identity_matches_pinned_component_lock(self):
        self.assertEqual(self.manifest["schema_version"], 1)
        self.assertEqual(
            self.manifest["upstream_commit"],
            self.upstream_lock["baseline"]["commit"],
        )
        self.assertEqual(
            self.manifest["rules_commit"],
            self.upstream_lock["gitlink"]["Detect-It-Easy"]["commit"],
        )
        self.assertEqual(
            self.manifest["matrix"],
            "docs/research/capability-matrix.md",
        )

    def test_matrix_and_manifest_capability_ids_are_exact_closed_sets(self):
        matrix_ids = CAPABILITY_ID.findall(self.matrix)
        capabilities = self.manifest["capabilities"]
        manifest_ids = [capability["id"] for capability in capabilities]
        self.assertEqual(len(matrix_ids), len(set(matrix_ids)))
        self.assertEqual(len(manifest_ids), len(set(manifest_ids)))
        self.assertEqual(set(matrix_ids), set(manifest_ids))
        self.assertEqual(len(manifest_ids), 68)
        self.assertIn("`CAP-*` 是兼容范围的稳定标识", self.matrix)

    def test_each_capability_has_known_state_and_existing_evidence(self):
        states = set(self.manifest["verification_states"])
        evidence_sets = self.manifest["evidence_sets"]
        referenced_evidence = set()
        for capability in self.manifest["capabilities"]:
            with self.subTest(capability=capability["id"]):
                self.assertRegex(capability["id"], rf"^{CAPABILITY_ID.pattern}$")
                self.assertTrue(capability["name"])
                self.assertIn(capability["verification"], states)
                self.assertIn(capability["evidence_set"], evidence_sets)
                referenced_evidence.add(capability["evidence_set"])
        self.assertEqual(referenced_evidence, set(evidence_sets))
        for evidence_id, evidence in evidence_sets.items():
            self.assertIn(
                evidence["kind"],
                {"experiment", "source", "source_and_experiment"},
            )
            self.assertTrue(evidence["paths"])
            for relative in evidence["paths"]:
                with self.subTest(evidence=evidence_id, path=relative):
                    self.assertTrue((ROOT / relative).is_file())

    def test_summary_is_derived_and_does_not_claim_complete_coverage(self):
        summary = self.manifest["summary"]
        by_state = {
            state: sum(
                capability["verification"] == state
                for capability in self.manifest["capabilities"]
            )
            for state in self.manifest["verification_states"]
        }
        self.assertEqual(
            summary["capability_count"],
            len(self.manifest["capabilities"]),
        )
        for state, count in by_state.items():
            self.assertEqual(summary[state], count)
        self.assertEqual(
            summary["coverage_gap_count"],
            len(self.manifest["coverage_gaps"]),
        )
        self.assertFalse(summary["phase_0_coverage_complete"])

    def test_coverage_gaps_are_unique_and_keep_platform_absence_explicit(self):
        gaps = self.manifest["coverage_gaps"]
        gap_ids = [gap["id"] for gap in gaps]
        self.assertEqual(
            gap_ids,
            [
                "CAP-GAP-003",
                "CAP-GAP-006",
                "CAP-GAP-007",
                "CAP-GAP-008",
            ],
        )
        self.assertEqual(len(gap_ids), len(set(gap_ids)))
        for gap in gaps:
            self.assertTrue(gap["scope"])
            self.assertTrue(gap["platforms"])
        platform_scope = set(self.manifest["platform_scope"])
        self.assertEqual(platform_scope, {"linux-x86_64-qt5"})
        missing_platforms = {
            platform
            for gap in gaps
            for platform in gap["platforms"]
            if platform not in platform_scope
        }
        self.assertEqual(
            missing_platforms,
            {"windows-x86_64-qt5", "macos-x86_64-qt5", "linux-x86_64-qt6"},
        )


if __name__ == "__main__":
    unittest.main()
