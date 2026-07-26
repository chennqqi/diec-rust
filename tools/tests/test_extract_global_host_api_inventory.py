import importlib.util
import json
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools/rules/extract_global_host_api_inventory.py"
SPEC = importlib.util.spec_from_file_location(
    "extract_global_host_api_inventory", SCRIPT
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class GlobalHostApiInventoryTests(unittest.TestCase):
    def test_slot_and_registration_parsers(self):
        header = """
class die_global_script : public QObject {
    Q_OBJECT
public slots:
    void alpha(const QString &text);
    bool beta();
signals:
    void done();
};
"""
        methods = MODULE.parse_global_slots(header, "fixture.h")
        self.assertEqual([item["name"] for item in methods], ["alpha", "beta"])
        registrations = MODULE.parse_registrations(
            """
_addFunction(alpha, "alpha");
globalObject().setProperty("alpha", valueGlobalScript.property("alpha"));
"""
        )
        self.assertEqual(
            registrations["qt5_qscriptengine"][0]["name"], "alpha"
        )
        self.assertEqual(
            registrations["qt6_qjsengine"][0]["name"], "alpha"
        )

    def test_call_classification_is_explicit(self):
        calls = [
            {"name": "native", "binding": "undeclared_global", "count": 2},
            {"name": "helper", "binding": "undeclared_global", "count": 3},
            {"name": "String", "binding": "undeclared_global", "count": 4},
            {"name": "typo", "binding": "undeclared_global", "count": 1},
            {"name": "local", "binding": "declared", "count": 8},
        ]
        report = MODULE.classify_undeclared_calls(
            calls, {"native"}, {"helper"}
        )
        categories = {
            item["name"]: item["classification"]
            for item in report["records"]
        }
        self.assertEqual(categories["native"], "native_engine_global")
        self.assertEqual(categories["helper"], "rule_top_level_function")
        self.assertEqual(categories["String"], "ecmascript_global")
        self.assertEqual(categories["typo"], "unclassified")
        self.assertNotIn("local", categories)

    def test_qt5_wrapper_parser_requires_matching_implementations(self):
        header = (
            "static QScriptValue alpha(QScriptContext *pContext, "
            "QScriptEngine *pEngine);\n"
        )
        implementation = (
            "QScriptValue DiE_ScriptEngine::alpha("
            "QScriptContext *pContext, QScriptEngine *pEngine)\n{}\n"
        )
        wrappers = MODULE.parse_qt5_wrappers(header, implementation)
        self.assertEqual(wrappers[0]["name"], "alpha")
        with self.assertRaisesRegex(ValueError, "differ"):
            MODULE.parse_qt5_wrappers(header, "")

    def test_committed_inventory_identities_and_findings(self):
        path = ROOT / "docs/research/data/global-host-api-inventory.json"
        inventory = json.loads(path.read_text(encoding="utf-8"))
        generator = inventory["generator"]
        self.assertEqual(
            MODULE.sha256_bytes(SCRIPT.read_bytes()), generator["sha256"]
        )
        native = inventory["native_global_api"]
        self.assertEqual(native["declared_slot_count"], 16)
        self.assertEqual(native["qt5_registered_count"], 15)
        self.assertEqual(native["qt6_registered_count"], 16)
        self.assertEqual(native["qt5_only_omission"], ["_getQtVersion"])
        self.assertEqual(len(native["qt5_custom_wrappers"]), 15)
        self.assertEqual(
            {item["name"] for item in native["qt5_custom_wrappers"]},
            {
                item["name"]
                for item in native["registration_evidence"][
                    "qt5_qscriptengine"
                ]
            },
        )
        rule_inventory = ROOT / inventory["rule_inventory"]["path"]
        self.assertEqual(
            MODULE.sha256_bytes(rule_inventory.read_bytes()),
            inventory["rule_inventory"]["sha256"],
        )
        classification = inventory[
            "undeclared_direct_call_classification"
        ]
        unclassified = [
            item["name"]
            for item in classification["records"]
            if item["classification"] == "unclassified"
        ]
        self.assertEqual(
            unclassified, ["get_DWRAF_vi", "xma2_pase_xma2_chunk"]
        )

    def test_wrong_checkout_is_rejected_before_reading_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "git rev-parse"):
                MODULE.build_inventory(
                    pathlib.Path(directory),
                    ROOT
                    / "docs/research/data/rule-syntax-inventory.json",
                )


if __name__ == "__main__":
    unittest.main()
