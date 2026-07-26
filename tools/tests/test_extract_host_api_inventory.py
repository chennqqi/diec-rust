import importlib.util
import hashlib
import json
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).parents[2]
MODULE_PATH = ROOT / "tools" / "rules" / "extract_host_api_inventory.py"
SPEC = importlib.util.spec_from_file_location(
    "extract_host_api_inventory", MODULE_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
COMMITTED = (
    ROOT / "docs" / "research" / "data" / "host-api-inventory.json"
)
RULE_INVENTORY = (
    ROOT / "docs" / "research" / "data" / "rule-syntax-inventory.json"
)


class HostApiInventoryTests(unittest.TestCase):
    def test_committed_inventory_identity_and_coverage(self):
        inventory = json.loads(COMMITTED.read_text(encoding="utf-8"))
        self.assertEqual(
            inventory["xscanengine"]["commit"],
            MODULE.XSCANENGINE_COMMIT,
        )
        self.assertEqual(
            inventory["xscanengine"]["license_sha256"],
            MODULE.XSCANENGINE_LICENSE_SHA256,
        )
        self.assertEqual(inventory["declarations"]["class_count"], 30)
        self.assertEqual(
            inventory["declarations"]["direct_slot_method_count"], 337
        )
        coverage = inventory["observed_call_coverage"]
        self.assertEqual(coverage["observed_receiver_method_count"], 429)
        self.assertEqual(coverage["observed_arity_shape_count"], 464)
        self.assertEqual(coverage["covered_arity_shape_count"], 460)
        self.assertEqual(coverage["uncovered_arity_shape_count"], 4)
        self.assertEqual(coverage["missing_method_record_count"], 1)
        self.assertEqual(
            inventory["generator"]["sha256"],
            hashlib.sha256(MODULE_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            inventory["rule_inventory"]["sha256"],
            hashlib.sha256(RULE_INVENTORY.read_bytes()).hexdigest(),
        )

    def test_comments_defaults_inheritance_and_rule_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            modules = root / "modules"
            modules.mkdir()
            (modules / "binary_script.h").write_text(
                """
class Binary_Script : public QObject {
public slots:
    bool compare(const QString &signature, qint64 offset = 0);
    // ignored(int value);
    QString value();
};
""",
                encoding="utf-8",
            )
            (modules / "pe_script.h").write_text(
                """
class PE_Script : public Binary_Script {
public slots:
    virtual QString value();
    bool exact(qint64 offset, bool strict = false);
private:
    int hidden();
};
""",
                encoding="utf-8",
            )
            rule_inventory = {
                "rules_commit": MODULE.RULES_COMMIT,
                "known_receiver_script_extensions": [
                    {
                        "receiver_root": "PE",
                        "member": "scriptOnly",
                        "definition_count": 1,
                        "parameter_count_counts": {"1": 1},
                    }
                ],
                "calls": {
                    "known_host": [
                        {
                            "receiver_root": "PE",
                            "method": "compare",
                            "arity_counts": {"1": 2, "2": 1},
                            "first_location": {
                                "path": "db/PE/a.sg",
                                "line": 1,
                                "column": 0,
                            },
                        },
                        {
                            "receiver_root": "PE",
                            "method": "scriptOnly",
                            "arity_counts": {"0": 1, "2": 1},
                            "first_location": {
                                "path": "db/PE/a.sg",
                                "line": 4,
                                "column": 0,
                            },
                        },
                        {
                            "receiver_root": "PE",
                            "method": "exact",
                            "arity_counts": {"1": 1, "3": 1},
                            "first_location": {
                                "path": "db/PE/a.sg",
                                "line": 2,
                                "column": 0,
                            },
                        },
                        {
                            "receiver_root": "X",
                            "method": "value",
                            "arity_counts": {"0": 1},
                            "first_location": {
                                "path": "db/PE/a.sg",
                                "line": 3,
                                "column": 0,
                            },
                        },
                    ]
                },
            }
            rule_path = root / "rules.json"
            rule_path.write_text(json.dumps(rule_inventory), encoding="utf-8")

            inventory = MODULE.build_inventory(
                root, rule_path, enforce_identity=False
            )

            declarations = inventory["declarations"]
            self.assertEqual(declarations["class_count"], 2)
            self.assertEqual(declarations["direct_slot_method_count"], 4)
            classes = {
                item["name"]: item for item in declarations["classes"]
            }
            self.assertEqual(
                classes["PE_Script"]["lineage"],
                ["PE_Script", "Binary_Script", "QObject"],
            )
            compare = next(
                method
                for method in classes["Binary_Script"]["methods"]
                if method["name"] == "compare"
            )
            self.assertEqual(compare["minimum_arity"], 1)
            self.assertEqual(compare["maximum_arity"], 2)
            self.assertEqual(compare["parameters"][1]["default"], "0")

            coverage = inventory["observed_call_coverage"]
            self.assertEqual(coverage["observed_arity_shape_count"], 7)
            self.assertEqual(coverage["covered_arity_shape_count"], 6)
            self.assertEqual(coverage["uncovered_arity_shape_count"], 1)
            self.assertEqual(
                coverage[
                    "script_extension_covered_arity_shape_count"
                ],
                2,
            )
            exact = next(
                item
                for item in coverage["records"]
                if item["method"] == "exact"
            )
            self.assertEqual(exact["uncovered_arities"], [3])

    def test_rejects_unparseable_slot(self):
        source = """
class Broken_Script : public QObject {
public slots:
    nonsense;
};
"""
        with self.assertRaisesRegex(ValueError, "cannot parse slot"):
            MODULE.parse_header(source, "modules/broken_script.h")


if __name__ == "__main__":
    unittest.main()
