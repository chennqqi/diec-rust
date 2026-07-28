import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT / "tools" / "upstream" / "probe_qt6_binary_rule_order.py"
)
UNDERLYING_PATH = (
    ROOT / "tools" / "upstream" / "probe_binary_rule_order.py"
)
REPORT_PATH = (
    ROOT
    / "docs"
    / "research"
    / "data"
    / "binary-rule-order-linux-qt5-qt6.json"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_qt6_binary_rule_order",
    MODULE_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ProbeQt6BinaryRuleOrderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    def test_report_and_underlying_identity_are_fixed(self):
        self.assertEqual(self.report["schema_version"], 1)
        self.assertEqual(self.report["generator"], MODULE.GENERATOR)
        self.assertEqual(
            self.report["generator_sha256"],
            hashlib.sha256(MODULE_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            self.report["underlying_probe"],
            {
                "path": MODULE.UNDERLYING_PROBE,
                "sha256": hashlib.sha256(
                    UNDERLYING_PATH.read_bytes()
                ).hexdigest(),
            },
        )
        self.assertEqual(self.report["result"], "equal")

    def test_both_oracles_have_complete_equal_order(self):
        self.assertTrue(self.report["orders_equal"])
        self.assertEqual(self.report["order_count"], 292)
        self.assertEqual(len(self.report["order"]), 292)
        self.assertEqual(len(set(self.report["order"])), 292)
        self.assertEqual(
            [oracle["name"] for oracle in self.report["oracles"]],
            ["linux-qt5-cmake", "linux-qt6-cmake"],
        )
        for oracle in self.report["oracles"]:
            with self.subTest(oracle=oracle["name"]):
                self.assertEqual(oracle["exit_code"], 0)
                self.assertEqual(oracle["raw_stderr_bytes"], 0)
                self.assertEqual(
                    oracle["order_count"],
                    self.report["order_count"],
                )
                self.assertEqual(
                    oracle["order_sha256"],
                    self.report["order_sha256"],
                )

    def test_order_is_bound_to_lifecycle_inventory(self):
        lifecycle = json.loads(
            (
                ROOT
                / "docs"
                / "research"
                / "data"
                / "binary-rule-lifecycle.json"
            ).read_text(encoding="utf-8")
        )
        names = {
            record["name"]
            for database in ("db", "db_extra", "db_custom")
            for record in lifecycle["binary"]["records_by_database"][
                database
            ]
            if record["name"] != "_init"
        }
        self.assertEqual(set(self.report["order"]), names)
        canonical = "".join(
            f"{name}\n" for name in self.report["order"]
        ).encode()
        self.assertEqual(
            hashlib.sha256(canonical).hexdigest(),
            self.report["order_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
