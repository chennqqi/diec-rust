import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ANALYZER = ROOT / "tools/rules/analyze_include_graph.py"
REPORT = ROOT / "docs/research/data/include-graph-sizing.json"


def load_analyzer():
    spec = importlib.util.spec_from_file_location(
        "analyze_include_graph",
        ANALYZER,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class IncludeGraphSizingTests(unittest.TestCase):
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

    def test_fixed_rule_asset_identity_and_inventory_are_bound(self):
        assets = self.report["rule_assets"]
        self.assertEqual(
            assets,
            {
                "report": (
                    "docs/research/data/"
                    "runtime-rule-assets-license.json"
                ),
                "report_sha256": (
                    "c1d1fe07ccdd0ff74a4428372e9c18b4"
                    "f4dbda2f4a1dd0e3082b7702d8370dbb"
                ),
                "combined_tree_sha256": (
                    "20f2b74effc2bdaf069e3b2e13060432"
                    "b8890d38364511f5cde56a337348bfda"
                ),
                "program_file_count": 2235,
                "program_byte_count": 2_902_881,
            },
        )
        self.assertEqual(
            self.report["upstream_commit"],
            self.module.UPSTREAM_COMMIT,
        )
        self.assertEqual(
            self.report["rules_commit"],
            self.module.RULES_COMMIT,
        )

    def test_complete_literal_graph_is_closed_and_acyclic(self):
        graph = self.report["graph"]
        self.assertEqual(graph["literal_include_call_count"], 56)
        self.assertEqual(graph["unique_calling_file_count"], 48)
        self.assertEqual(graph["unique_resolved_helper_count"], 27)
        self.assertEqual(graph["non_literal_include_sites"], [])
        self.assertEqual(graph["missing_literal_includes"], [])
        self.assertEqual(graph["helper_cycles"], [])
        self.assertEqual(len(graph["calls"]), 56)
        self.assertTrue(
            all(item["resolved_path"] for item in graph["calls"])
        )

    def test_all_thirty_rule_scopes_have_exact_sizing(self):
        sizing = self.report["sizing"]
        self.assertEqual(sizing["scope_count"], 30)
        scopes = {item["scope"]: item for item in sizing["scopes"]}
        self.assertEqual(
            set(scopes),
            {
                "APK",
                "Amiga",
                "Archive",
                "AtariST",
                "Binary",
                "CFBF",
                "COM",
                "DEX",
                "DOS16M",
                "DOS4G",
                "ELF",
                "IPA",
                "ISO9660",
                "Image",
                "JAR",
                "JPEG",
                "JavaClass",
                "LE",
                "LX",
                "MACH",
                "MACHOFAT",
                "MSDOS",
                "NE",
                "NPM",
                "PDF",
                "PE",
                "PNG",
                "PYC",
                "RAR",
                "ZIP",
            },
        )
        self.assertEqual(
            sizing["maximum_transitive_include_evaluations"],
            30,
        )
        self.assertEqual(
            sizing["maximum_evaluation_scopes"],
            ["Binary", "PE"],
        )
        self.assertEqual(sizing["maximum_active_include_depth"], 2)
        self.assertEqual(
            sizing["maximum_depth_scopes"],
            ["Binary", "MSDOS", "PE"],
        )
        self.assertEqual(
            {
                name: (
                    scopes[name]["direct_include_call_count"],
                    scopes[name][
                        "transitive_include_evaluation_count"
                    ],
                    scopes[name]["maximum_active_include_depth"],
                )
                for name in ("Binary", "MSDOS", "PE")
            },
            {
                "Binary": (23, 30, 2),
                "MSDOS": (7, 10, 2),
                "PE": (25, 30, 2),
            },
        )

    def test_binary_static_count_matches_existing_dynamic_trace(self):
        self.assertEqual(
            self.report["sizing"]["binary_runtime_trace_continuity"],
            {
                "direct_calls": 23,
                "expected_dynamic_trace_evaluations": 30,
                "matches": True,
                "transitive_evaluations": 30,
            },
        )

    def test_cycle_nonliteral_and_missing_targets_fail_closed(self):
        self.assertEqual(
            self.module.find_cycles(
                {"a": ["b"], "b": ["c"], "c": ["a"]}
            ),
            [["a", "b", "c", "a"]],
        )
        with self.assertRaisesRegex(
            self.module.IncludeGraphError,
            "include cycle prevents sizing",
        ):
            self.module.expansion_metrics(
                "a",
                {"a": ["b"], "b": ["a"]},
            )

        with tempfile.TemporaryDirectory() as directory:
            literal = Path(directory) / "literal.sg"
            literal.write_text(
                'includeScript("read");\n',
                encoding="utf-8",
            )
            self.assertEqual(
                self.module.include_sites(literal),
                (["read"], 1),
            )
            dynamic = Path(directory) / "dynamic.sg"
            dynamic.write_text(
                "includeScript(name);\n",
                encoding="utf-8",
            )
            self.assertEqual(
                self.module.include_sites(dynamic),
                ([], 1),
            )

        records = [
            {
                "database": "db",
                "scope": "global",
                "name": "read",
            }
        ]
        self.assertIsNone(
            self.module.first_named(
                records,
                "missing",
                scope="global",
            )
        )

    def test_scope_statement_does_not_overclaim_runtime_coverage(self):
        scope = self.report["scope"]
        self.assertIn(
            "all fixed db/db_extra/db_custom program files",
            scope["covers"],
        )
        self.assertEqual(
            scope["does_not_prove"],
            [
                "production runtime memory or instruction limits",
                "future or user-supplied database include shape",
                "runtime behavior for dynamically computed include names",
            ],
        )


if __name__ == "__main__":
    unittest.main()
