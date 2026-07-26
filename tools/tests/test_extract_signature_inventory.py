import importlib.util
import json
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).parents[2]
MODULE_PATH = ROOT / "tools" / "rules" / "extract_signature_inventory.py"
SPEC = importlib.util.spec_from_file_location(
    "extract_signature_inventory", MODULE_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SignatureInventoryTests(unittest.TestCase):
    def trace(self):
        calls = ["'AB'", "41..", "'AB'"]
        return {
            "operation": (
                "diagnostic invocation of all fixed-order Binary detect functions"
            ),
            "attempted_detect_count": 292,
            "completed": True,
            "input": {"path": "sample.bin", "bytes": 4},
            "order_manifest": "order.json",
            "order_sha256": "abc",
            "unsupported_signature_call_total": len(calls),
            "unsupported_signature_patterns": ["'AB'", "41.."],
            "observations": [
                {
                    "name": "one.sg",
                    "unsupported_signature_call_count": len(calls),
                    "unsupported_signature_patterns": calls,
                    "unsupported_signature_patterns_truncated": False,
                }
            ],
        }

    def test_extracts_sorted_deduplicated_patterns_and_rules(self):
        inventory = MODULE.extract_inventory(self.trace())
        self.assertEqual(inventory["calling_rules"], ["one.sg"])
        self.assertEqual(inventory["pattern_call_count"], 3)
        self.assertEqual(inventory["patterns"], ["'AB'", "41.."])
        self.assertEqual(inventory["pattern_count"], 2)

    def test_rejects_truncated_capture(self):
        trace = self.trace()
        trace["observations"][0][
            "unsupported_signature_patterns_truncated"
        ] = True
        with self.assertRaisesRegex(ValueError, "truncated"):
            MODULE.extract_inventory(trace)

    def test_cli_writes_reproducible_json(self):
        trace = self.trace()
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            source = root / "trace.json"
            output = root / "inventory.json"
            source.write_text(json.dumps(trace), encoding="utf-8")
            argv = MODULE.argparse.ArgumentParser
            self.assertIsNotNone(argv)
            inventory = MODULE.extract_inventory(MODULE.load_json(source))
            output.write_text(
                json.dumps(inventory, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8")),
                inventory,
            )


if __name__ == "__main__":
    unittest.main()
