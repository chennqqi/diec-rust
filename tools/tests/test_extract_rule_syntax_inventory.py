import json
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).parents[2]
SCRIPT = ROOT / "tools" / "rules" / "extract_rule_syntax_inventory.js"
RULES = ROOT / "upstream" / "Detect-It-Easy"
PARSER = (
    RULES
    / "autotools"
    / "dbcompiler"
    / "node_modules"
    / "uglify-js"
    / "tools"
    / "node.js"
)
COMMITTED = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "rule-syntax-inventory.json"
)


class RuleSyntaxInventoryTests(unittest.TestCase):
    def run_extractor(
        self, rules: pathlib.Path, output: pathlib.Path
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "node",
                str(SCRIPT),
                "--rules-root",
                str(rules),
                "--parser-module",
                str(PARSER),
                "--output",
                str(output),
            ],
            cwd=ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def test_selection_and_call_classification_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "db").mkdir()
            (root / "db_extra").mkdir()
            (root / "db" / "one.sg").write_text(
                """
function helper(value) {
    return value + 1;
}
function detect() {
    var index = 0;
    PE.compare("41", index);
    PE.section[".text"] = true;
    log(logType.any, helper(index));
}
""",
                encoding="utf-8",
            )
            (root / "db" / "_init").write_text(
                "X.c('42');\n", encoding="utf-8"
            )
            (root / "db_extra" / "two.sg").write_text(
                "function detect() { return Binary.readByte(0); }\n",
                encoding="utf-8",
            )
            (root / "db_extra" / "ignored.txt").write_text(
                "not JavaScript", encoding="utf-8"
            )
            output = root / "inventory.json"
            self.run_extractor(root, output)
            inventory = json.loads(output.read_text(encoding="utf-8"))

            self.assertEqual(inventory["files"]["count"], 3)
            self.assertEqual(inventory["files"]["parse_failure_count"], 0)
            self.assertNotIn(
                "=", inventory["operator_counts"]["binary"]
            )
            self.assertEqual(
                inventory["operator_counts"]["assignment"]["="], 1
            )
            host_calls = {
                (item["receiver_root"], item["method"]): item
                for item in inventory["calls"]["known_host"]
            }
            self.assertEqual(
                host_calls[("PE", "compare")]["arity_counts"], {"2": 1}
            )
            self.assertEqual(
                host_calls[("X", "c")]["arity_counts"], {"1": 1}
            )
            self.assertEqual(
                host_calls[("Binary", "readByte")]["arity_counts"],
                {"1": 1},
            )
            globals_by_name = {
                item["name"]: item
                for item in inventory["undeclared_globals"]
            }
            self.assertEqual(globals_by_name["log"]["direct_call_count"], 1)
            self.assertEqual(
                globals_by_name["logType"]["member_receiver_count"], 1
            )
            members = {
                (item["receiver_root"], item["member"]): item
                for item in inventory["known_host_first_level_members"]
            }
            self.assertEqual(
                members[("PE", "section")]["write_target_count"], 0
            )
            self.assertEqual(
                members[("PE", "compare")]["call_target_count"], 1
            )

    def test_committed_inventory_is_reproducible(self):
        with tempfile.TemporaryDirectory() as directory:
            generated = pathlib.Path(directory) / "inventory.json"
            self.run_extractor(RULES, generated)
            inventory = json.loads(generated.read_text(encoding="utf-8"))

            self.assertEqual(inventory["files"]["count"], 2235)
            self.assertEqual(
                inventory["files"]["parse_success_count"], 2235
            )
            self.assertEqual(
                generated.read_bytes(), COMMITTED.read_bytes()
            )


if __name__ == "__main__":
    unittest.main()
