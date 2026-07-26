import json
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).parents[2]
SCRIPT = (
    ROOT / "tools" / "rules" / "extract_static_signature_inventory.js"
)
PARSER = (
    ROOT
    / "upstream"
    / "Detect-It-Easy"
    / "autotools"
    / "dbcompiler"
    / "node_modules"
    / "uglify-js"
    / "tools"
    / "node.js"
)
UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254"
RULES = ROOT / "upstream" / "Detect-It-Easy"
DYNAMIC_INVENTORY = (
    ROOT / "docs" / "research" / "data" / "signature-pattern-inventory.json"
)
COMMITTED_INVENTORY = (
    ROOT / "docs" / "research" / "data" / "signature-static-inventory.json"
)


class StaticSignatureInventoryTests(unittest.TestCase):
    def run_extractor(
        self,
        rules_root: pathlib.Path,
        dynamic_inventory: pathlib.Path,
        output: pathlib.Path,
        *,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "node",
                str(SCRIPT),
                "--rules-root",
                str(rules_root),
                "--parser-module",
                str(PARSER),
                "--dynamic-inventory",
                str(dynamic_inventory),
                "--output",
                str(output),
            ],
            cwd=ROOT,
            check=check,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def fixture(self, root: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
        rules = root / "rules"
        (rules / "db").mkdir(parents=True)
        (rules / "db_extra").mkdir()
        (rules / "db" / "one.sg").write_text(
            """
function detect() {
    const fixed = "48";
    var stable = "49";
    var changing = "50";
    var iterated = "51";
    changing = "52";
    X.c("41");
    X.compare(fixed);
    X.compare(stable);
    X.compare(changing);
    for (iterated in table) {}
    X.compare(iterated);
    PE.compareEP(flag ? "42" : "43");
    PE.findSignature(0, 10, prefix + "44");
    PE.compareOverlay("4" + "5");
}
""".lstrip(),
            encoding="utf-8",
        )
        (rules / "db_extra" / "two.sg").write_text(
            """
function detect() {
    other.c("99");
    X.isSignaturePresent(0, 1, "46");
    X.isSignatureInSectionPresent(0, "47");
}
""".lstrip(),
            encoding="utf-8",
        )
        dynamic = root / "dynamic.json"
        dynamic.write_text(
            json.dumps(
                {
                    "upstream_commit": UPSTREAM_COMMIT,
                    "patterns": ["41", "runtime"],
                }
            ),
            encoding="utf-8",
        )
        return rules, dynamic

    def test_extracts_all_calls_and_keeps_dynamic_and_unknown_candidates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            rules, dynamic = self.fixture(root)
            output = root / "inventory.json"
            self.run_extractor(rules, dynamic, output)
            inventory = json.loads(output.read_text(encoding="utf-8"))

            self.assertEqual(inventory["rules"]["file_count"], 2)
            self.assertEqual(inventory["rules"]["parse_success_count"], 2)
            self.assertEqual(inventory["rules"]["parse_failure_count"], 0)
            self.assertEqual(inventory["call_site_count"], 11)
            self.assertEqual(inventory["known_host_call_site_count"], 10)
            self.assertEqual(inventory["unknown_receiver_call_site_count"], 1)
            self.assertEqual(inventory["dynamic_call_site_count"], 3)
            self.assertEqual(
                inventory["argument_kind_counts"],
                {
                    "dynamic": 3,
                    "literal": 3,
                    "static_expression": 4,
                },
            )
            self.assertEqual(
                inventory["static_patterns"],
                ["41", "42", "43", "45", "46", "47", "48", "49"],
            )
            self.assertEqual(
                inventory["dynamic_inventory_comparison"][
                    "dynamic_only_patterns"
                ],
                ["runtime"],
            )
            self.assertEqual(
                inventory["unknown_receiver_calls"][0]["receiver_root"],
                "other",
            )

    def test_output_is_byte_stable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            rules, dynamic = self.fixture(root)
            first = root / "first.json"
            second = root / "second.json"
            self.run_extractor(rules, dynamic, first)
            self.run_extractor(rules, dynamic, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_parse_failure_is_fatal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            rules, dynamic = self.fixture(root)
            (rules / "db" / "broken.sg").write_text(
                "function {",
                encoding="utf-8",
            )
            output = root / "inventory.json"
            result = self.run_extractor(
                rules,
                dynamic,
                output,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())

    def test_committed_inventory_matches_fixed_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "inventory.json"
            self.run_extractor(RULES, DYNAMIC_INVENTORY, output)
            self.assertEqual(
                output.read_bytes(),
                COMMITTED_INVENTORY.read_bytes(),
            )
            inventory = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(inventory["parser"]["version"], "3.19.3")
            self.assertEqual(inventory["parser"]["license"], "BSD-2-Clause")
            self.assertEqual(inventory["rules"]["file_count"], 2175)
            self.assertEqual(inventory["rules"]["parse_success_count"], 2175)
            self.assertEqual(inventory["rules"]["parse_failure_count"], 0)
            self.assertEqual(inventory["call_site_count"], 5968)
            self.assertEqual(inventory["known_host_call_site_count"], 5968)
            self.assertEqual(inventory["unknown_receiver_call_site_count"], 0)
            self.assertEqual(inventory["known_host_calling_file_count"], 1615)
            self.assertEqual(
                inventory["argument_kind_counts"],
                {
                    "dynamic": 73,
                    "literal": 5855,
                    "static_expression": 40,
                },
            )
            self.assertEqual(
                inventory["dynamic_expression_type_counts"],
                {
                    "Binary": 12,
                    "Call": 9,
                    "Sub": 7,
                    "SymbolRef": 45,
                },
            )
            self.assertEqual(inventory["static_pattern_count"], 5187)
            comparison = inventory["dynamic_inventory_comparison"]
            self.assertEqual(comparison["intersection_count"], 317)
            self.assertEqual(comparison["dynamic_only_count"], 0)
            self.assertEqual(comparison["static_only_count"], 4870)


if __name__ == "__main__":
    unittest.main()
