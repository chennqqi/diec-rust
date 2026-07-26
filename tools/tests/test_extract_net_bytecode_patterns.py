import json
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).parents[2]
SCRIPT = ROOT / "tools" / "rules" / "extract_net_bytecode_patterns.js"
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
    / "net-bytecode-patterns.json"
)


class NetByteCodePatternTests(unittest.TestCase):
    def run_extractor(
        self, output: pathlib.Path
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "node",
                str(SCRIPT),
                "--rules-root",
                str(RULES),
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

    def test_all_call_sites_are_finite_and_inventory_is_reproducible(self):
        with tempfile.TemporaryDirectory() as directory:
            generated = pathlib.Path(directory) / "inventory.json"
            self.run_extractor(generated)
            inventory = json.loads(generated.read_text(encoding="utf-8"))

            self.assertEqual(inventory["call_site_count"], 33)
            self.assertGreater(inventory["expanded_call_count"], 33)
            self.assertEqual(len(inventory["calls"]), 33)
            self.assertEqual(
                generated.read_bytes(),
                COMMITTED.read_bytes(),
            )

    def test_loop_patterns_are_exhaustively_expanded(self):
        inventory = json.loads(COMMITTED.read_text(encoding="utf-8"))
        by_line = {call["line"]: call for call in inventory["calls"]}

        self.assertEqual(by_line[965]["pattern_count"], 6)
        self.assertEqual(by_line[969]["pattern_count"], 60)
        self.assertIn(
            "20????????20????????58FE0E????",
            by_line[969]["patterns"],
        )
        self.assertIn(
            "20????????20????????5FFE0E????",
            by_line[969]["patterns"],
        )


if __name__ == "__main__":
    unittest.main()
