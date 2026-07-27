import hashlib
import importlib.util
import json
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT / "tools" / "upstream" / "probe_rule_orchestration.py"
)
REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "rule-orchestration-linux-qt5.json"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_rule_orchestration",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ProbeRuleOrchestrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    def test_report_identity_is_fixed(self):
        self.assertEqual(self.report["schema_version"], 1)
        self.assertEqual(
            self.report["generator"],
            "tools/upstream/probe_rule_orchestration.py",
        )
        self.assertEqual(
            self.report["generator_sha256"],
            hashlib.sha256(MODULE_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            self.report["upstream_commit"],
            MODULE.UPSTREAM_COMMIT,
        )
        self.assertEqual(
            [oracle["name"] for oracle in self.report["oracles"]],
            ["linux-qt5-qmake", "linux-qt5-cmake"],
        )
        self.assertTrue(self.report["normalized_outputs_equal"])

    def test_combined_order_proves_layer_append_and_init_sort_defect(self):
        order = self.report["canonical_cases"]["combined"][
            "execution_order"
        ]
        self.assertEqual(
            order,
            [
                "DS.deep.2.sg",
                "HEUR.heuristic.3.sg",
                "EP.entrypoint.4.sg",
                "z_normal.1.sg",
                "a_extra.0.sg",
                "a_custom.0.sg",
            ],
        )
        relationships = self.report["relationships"]
        self.assertTrue(
            relationships["type_init_list_order_is_not_pure_priority"]
        )
        self.assertTrue(
            relationships[
                "database_layers_are_appended_main_extra_custom"
            ]
        )

    def test_priority_only_list_uses_declared_priority(self):
        case = self.report["canonical_cases"]["priority_only"]
        self.assertEqual(
            case["execution_order"],
            [
                "z_priority.1.sg",
                "a_priority.2.sg",
                "m_priority.4.sg",
            ],
        )
        self.assertTrue(
            self.report["relationships"][
                "priority_only_beats_lexical_name"
            ]
        )
        self.assertEqual(
            {detection["version"] for detection in case["detections"]},
            {"priority-only"},
        )

    def test_priority_comparator_edges_are_exact(self):
        cases = self.report["canonical_cases"]
        self.assertEqual(
            cases["equal_priority"]["execution_order"],
            ["a_equal.2.sg", "m_equal.2.sg", "z_equal.2.sg"],
        )
        self.assertEqual(
            cases["lexical_priority"]["execution_order"],
            ["z_ten.10.sg", "a_two.2.sg"],
        )
        self.assertEqual(
            cases["missing_priority"]["execution_order"],
            ["a_plain.sg", "z_ranked.1.sg"],
        )
        self.assertEqual(
            cases["empty_priority"]["execution_order"],
            ["a_empty..sg", "z_empty_ranked.1.sg"],
        )
        relationships = self.report["relationships"]
        for key in (
            "equal_priority_falls_back_to_name",
            "priority_segments_are_lexicographic",
            "missing_priority_disables_pairwise_priority",
            "empty_priority_disables_pairwise_priority",
        ):
            self.assertTrue(relationships[key])
        self.assertEqual(
            self.report["closed_corpus_gap"],
            "CAP-GAP-010",
        )

    def test_modes_filter_ds_ep_and_heur_independently(self):
        cases = self.report["canonical_cases"]
        self.assertNotIn(
            "DS.deep.2.sg",
            cases["default"]["execution_order"],
        )
        self.assertNotIn(
            "HEUR.heuristic.3.sg",
            cases["default"]["execution_order"],
        )
        self.assertIn(
            "DS.deep.2.sg",
            cases["deep"]["execution_order"],
        )
        self.assertIn(
            "EP.entrypoint.4.sg",
            cases["deep"]["execution_order"],
        )
        self.assertNotIn(
            "HEUR.heuristic.3.sg",
            cases["deep"]["execution_order"],
        )
        self.assertEqual(
            cases["heuristic"]["execution_order"],
            [
                "HEUR.heuristic.3.sg",
                "z_normal.1.sg",
                "a_extra.0.sg",
                "a_custom.0.sg",
            ],
        )

    def test_init_include_and_file_type_filter_are_observed(self):
        relationships = self.report["relationships"]
        for key in (
            "main_global_init_wins",
            "main_type_init_wins",
            "main_same_name_include_wins",
            "wrong_file_type_rule_never_executes",
        ):
            self.assertTrue(relationships[key])

        for name in MODULE.MODES:
            case = self.report["canonical_cases"][name]
            for detection in case["detections"]:
                self.assertEqual(
                    detection["version"],
                    "main-global:main-helper:main-type",
                )
                self.assertNotEqual(detection["name"], "PE decoy")

    def test_empty_database_adds_exact_unknown(self):
        self.assertEqual(
            self.report["canonical_cases"]["unknown"],
            {
                "execution_order": [],
                "detections": [
                    {
                        "type": "Unknown",
                        "name": "Unknown",
                        "version": "",
                        "info": "",
                    }
                ],
            },
        )

    def test_each_raw_artifact_has_identity_and_empty_stderr(self):
        for oracle in self.report["oracles"]:
            for name, case in oracle["cases"].items():
                with self.subTest(oracle=oracle["name"], case=name):
                    self.assertEqual(case["exit_code"], 0)
                    self.assertRegex(
                        case["raw_stdout_sha256"],
                        r"^[0-9a-f]{64}$",
                    )
                    self.assertGreater(case["raw_stdout_bytes"], 0)
                    self.assertEqual(case["raw_stderr_bytes"], 0)
                    self.assertEqual(
                        case["raw_stderr_sha256"],
                        MODULE.EMPTY_SHA256,
                    )


if __name__ == "__main__":
    unittest.main()
