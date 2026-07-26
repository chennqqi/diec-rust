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
VM_PROTECT_TRANSFORM = """function generateUnicodeSignatureMask(inputString) {
    var output = "";
    for (var c = 0; c < inputString.length; c++) { output += (c != 0 ? "00" : "") + "'" + inputString[c] + "'"; }
    return output;
}"""


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
    const rows = [["53", "54"], ["55", "56"]];
    const mutableRows = [["57"]];
    mutableRows.push(["58"]);
    changing = "52";
    X.c("41");
    X.compare(fixed);
    X.compare(stable);
    X.compare(changing);
    for (iterated in table) {}
    X.compare(iterated);
    X.compare(rows[index][1]);
    X.compare(mutableRows[index][0]);
    X.compare(host[index]);
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
            self.assertEqual(inventory["call_site_count"], 14)
            self.assertEqual(inventory["known_host_call_site_count"], 13)
            self.assertEqual(inventory["unknown_receiver_call_site_count"], 1)
            self.assertEqual(inventory["dynamic_call_site_count"], 5)
            self.assertEqual(
                inventory["argument_kind_counts"],
                {
                    "dynamic": 5,
                    "literal": 3,
                    "static_expression": 5,
                },
            )
            self.assertEqual(
                inventory["static_patterns"],
                [
                    "41",
                    "42",
                    "43",
                    "45",
                    "46",
                    "47",
                    "48",
                    "49",
                    "54",
                    "56",
                ],
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

    def test_pure_transform_requires_exact_path_name_and_source_hash(self):
        for changed, expected_kind in ((False, "static_expression"), (True, "dynamic")):
            with self.subTest(changed=changed):
                with tempfile.TemporaryDirectory() as directory:
                    root = pathlib.Path(directory)
                    rules = root / "rules"
                    target = (
                        rules
                        / "db"
                        / "PE"
                        / "protector_VMProtect_NET.2.sg"
                    )
                    target.parent.mkdir(parents=True)
                    (rules / "db_extra").mkdir()
                    transform = VM_PROTECT_TRANSFORM
                    if changed:
                        transform = transform.replace(
                            'var output = "";',
                            'var output = "changed";',
                        )
                    target.write_bytes(
                        (
                            transform
                            + "\nfunction detect() {\n"
                            + '    PE.isSignaturePresent(0, 1, '
                            + 'generateUnicodeSignatureMask("AB"));\n'
                            + "}\n"
                        ).encode("utf-8")
                    )
                    dynamic = root / "dynamic.json"
                    dynamic.write_text(
                        json.dumps(
                            {
                                "upstream_commit": UPSTREAM_COMMIT,
                                "patterns": [],
                            }
                        ),
                        encoding="utf-8",
                    )
                    output = root / "inventory.json"
                    self.run_extractor(rules, dynamic, output)
                    inventory = json.loads(
                        output.read_text(encoding="utf-8")
                    )

                    self.assertEqual(
                        inventory["calls"][0]["argument_kind"],
                        expected_kind,
                    )
                    self.assertEqual(
                        len(inventory["verified_static_transforms"]),
                        0 if changed else 1,
                    )
                    self.assertEqual(
                        len(
                            inventory[
                                "static_transform_verification_failures"
                            ]
                        ),
                        1 if changed else 0,
                    )
                    self.assertEqual(
                        inventory["calls"][0]["static_patterns"],
                        [] if changed else ["'A'00'B'"],
                    )

    def test_parameter_values_require_all_direct_calls_and_no_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            rules = root / "rules"
            (rules / "db").mkdir(parents=True)
            (rules / "db_extra").mkdir()
            (rules / "db" / "params.sg").write_text(
                """
function safe(pattern) {
    X.compare(pattern);
}
safe("59");
safe(flag ? "5A" : "5B");

function partial(pattern) {
    X.compare(pattern);
}
partial("5C");
partial(runtime);

function escaped(pattern) {
    X.compare(pattern);
}
register(escaped);
escaped("5D");
""".lstrip(),
                encoding="utf-8",
            )
            dynamic = root / "dynamic.json"
            dynamic.write_text(
                json.dumps(
                    {
                        "upstream_commit": UPSTREAM_COMMIT,
                        "patterns": [],
                    }
                ),
                encoding="utf-8",
            )
            output = root / "inventory.json"
            self.run_extractor(rules, dynamic, output)
            inventory = json.loads(output.read_text(encoding="utf-8"))

            self.assertEqual(
                inventory["calls"][0]["static_patterns"],
                ["59", "5A", "5B"],
            )
            self.assertEqual(
                [
                    call["argument_kind"]
                    for call in inventory["calls"]
                ],
                ["static_expression", "dynamic", "dynamic"],
            )
            self.assertEqual(
                inventory["finite_parameter_values"],
                [
                    {
                        "path": "db/params.sg",
                        "function": "safe",
                        "function_line": 1,
                        "parameter": "pattern",
                        "parameter_index": 0,
                        "direct_call_site_count": 2,
                        "static_values": ["59", "5A", "5B"],
                    }
                ],
            )

    def test_top_level_parameter_values_reject_duplicate_or_external_names(self):
        cases = {
            "duplicate": """
function shared(value) {
    return value;
}
""",
            "external_call": """
shared("5A");
""",
        }
        for name, second_source in cases.items():
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as directory:
                    root = pathlib.Path(directory)
                    rules = root / "rules"
                    (rules / "db").mkdir(parents=True)
                    (rules / "db_extra").mkdir()
                    (rules / "db" / "one.sg").write_text(
                        """
function shared(pattern) {
    X.compare(pattern);
}
shared("59");
""".lstrip(),
                        encoding="utf-8",
                    )
                    (rules / "db_extra" / "two.sg").write_text(
                        second_source.lstrip(),
                        encoding="utf-8",
                    )
                    dynamic = root / "dynamic.json"
                    dynamic.write_text(
                        json.dumps(
                            {
                                "upstream_commit": UPSTREAM_COMMIT,
                                "patterns": [],
                            }
                        ),
                        encoding="utf-8",
                    )
                    output = root / "inventory.json"
                    self.run_extractor(rules, dynamic, output)
                    inventory = json.loads(
                        output.read_text(encoding="utf-8")
                    )

                    self.assertEqual(
                        inventory["calls"][0]["argument_kind"],
                        "dynamic",
                    )
                    self.assertEqual(
                        inventory["finite_parameter_values"],
                        [],
                    )

    def test_scoped_assignment_requires_first_unique_write_and_call_barrier(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            rules = root / "rules"
            (rules / "db").mkdir(parents=True)
            (rules / "db_extra").mkdir()
            (rules / "db" / "scoped.sg").write_text(
                """
var shared;

function safe() {
    shared = "65";
    X.compare(shared);
}

function barrier() {
    shared = "66";
    mutate();
    X.compare(shared);
}

function conditional() {
    if (flag) shared = "67";
    X.compare(shared);
}

function reassigned() {
    shared = "68";
    shared = "69";
    X.compare(shared);
}
""".lstrip(),
                encoding="utf-8",
            )
            dynamic = root / "dynamic.json"
            dynamic.write_text(
                json.dumps(
                    {
                        "upstream_commit": UPSTREAM_COMMIT,
                        "patterns": [],
                    }
                ),
                encoding="utf-8",
            )
            output = root / "inventory.json"
            self.run_extractor(rules, dynamic, output)
            inventory = json.loads(output.read_text(encoding="utf-8"))

            self.assertEqual(
                [
                    call["argument_kind"]
                    for call in inventory["calls"]
                ],
                ["static_expression", "dynamic", "dynamic", "dynamic"],
            )
            self.assertEqual(
                inventory["calls"][0]["static_patterns"],
                ["65"],
            )
            self.assertEqual(
                inventory["finite_scoped_assignments"],
                [
                    {
                        "path": "db/scoped.sg",
                        "function": "safe",
                        "function_line": 3,
                        "symbol": "shared",
                        "assignment_line": 4,
                        "invalidation_line": None,
                        "static_values": ["65"],
                    },
                    {
                        "path": "db/scoped.sg",
                        "function": "barrier",
                        "function_line": 8,
                        "symbol": "shared",
                        "assignment_line": 9,
                        "invalidation_line": 10,
                        "static_values": ["66"],
                    },
                ],
            )

    def test_loop_accumulation_requires_canonical_adjacent_finite_loop(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            rules = root / "rules"
            (rules / "db").mkdir(parents=True)
            (rules / "db_extra").mkdir()
            (rules / "db" / "loops.sg").write_text(
                """
function safe() {
    var signature = "60";
    for (var i = 0; i < 3; i++) {
        signature += "61";
    }
    X.compare(signature);
}

function dynamicLimit(limit) {
    var signature = "62";
    for (var i = 0; i < limit; i++) {
        signature += "63";
    }
    X.compare(signature);
}

function extraBody() {
    var signature = "64";
    for (var i = 0; i < 2; i++) {
        signature += "65";
        touch();
    }
    X.compare(signature);
}

function nonAdjacent() {
    var signature = "66";
    touch();
    for (var i = 0; i < 2; i++) {
        signature += "67";
    }
    X.compare(signature);
}
""".lstrip(),
                encoding="utf-8",
            )
            dynamic = root / "dynamic.json"
            dynamic.write_text(
                json.dumps(
                    {
                        "upstream_commit": UPSTREAM_COMMIT,
                        "patterns": [],
                    }
                ),
                encoding="utf-8",
            )
            output = root / "inventory.json"
            self.run_extractor(rules, dynamic, output)
            inventory = json.loads(output.read_text(encoding="utf-8"))

            self.assertEqual(
                [
                    call["argument_kind"]
                    for call in inventory["calls"]
                ],
                [
                    "static_expression",
                    "dynamic",
                    "dynamic",
                    "dynamic",
                ],
            )
            self.assertEqual(
                inventory["calls"][0]["static_patterns"],
                ["60616161"],
            )
            self.assertEqual(
                inventory["finite_loop_accumulations"],
                [
                    {
                        "path": "db/loops.sg",
                        "function": "safe",
                        "function_line": 1,
                        "symbol": "signature",
                        "loop_line": 3,
                        "iterations": 3,
                        "invalidation_line": None,
                        "static_values": ["60616161"],
                    }
                ],
            )

    def test_exact_self_assignment_is_not_a_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            rules = root / "rules"
            (rules / "db").mkdir(parents=True)
            (rules / "db_extra").mkdir()
            (rules / "db" / "self_assignment.sg").write_text(
                """
function safe() {
    var signature = "60";
    signature = signature;
    X.compare(signature);
}

function differentSymbol() {
    var signature = "61", replacement = "62";
    signature = replacement;
    X.compare(signature);
}

function compound() {
    var signature = "63";
    signature += "";
    X.compare(signature);
}

function laterWrite() {
    var signature = "64";
    signature = signature;
    signature = "65";
    X.compare(signature);
}

var globalSignature = "66";
globalSignature = globalSignature;
X.compare(globalSignature);
""".lstrip(),
                encoding="utf-8",
            )
            dynamic = root / "dynamic.json"
            dynamic.write_text(
                json.dumps(
                    {
                        "upstream_commit": UPSTREAM_COMMIT,
                        "patterns": [],
                    }
                ),
                encoding="utf-8",
            )
            output = root / "inventory.json"
            self.run_extractor(rules, dynamic, output)
            inventory = json.loads(output.read_text(encoding="utf-8"))

            self.assertEqual(
                [
                    call["argument_kind"]
                    for call in inventory["calls"]
                ],
                [
                    "static_expression",
                    "dynamic",
                    "dynamic",
                    "dynamic",
                    "dynamic",
                ],
            )
            self.assertEqual(
                inventory["calls"][0]["static_patterns"],
                ["60"],
            )
            self.assertEqual(
                inventory["value_preserving_self_assignments"],
                [
                    {
                        "path": "db/self_assignment.sg",
                        "function": "safe",
                        "function_line": 1,
                        "symbol": "signature",
                        "assignment_line": 3,
                    },
                    {
                        "path": "db/self_assignment.sg",
                        "function": "laterWrite",
                        "function_line": 19,
                        "symbol": "signature",
                        "assignment_line": 21,
                    },
                ],
            )

    def test_for_in_keys_require_safe_string_object_literal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            rules = root / "rules"
            (rules / "db").mkdir(parents=True)
            (rules / "db_extra").mkdir()
            (rules / "db" / "object_keys.sg").write_text(
                """
function safe() {
    var refs = {"61": "one", "60": "zero"};
    for (var key in refs) {
        X.compare(key);
    }
}

function escaped() {
    var refs = {"62": "two"};
    touch(refs);
    for (var key in refs) {
        X.compare(key);
    }
}

function mutated() {
    var refs = {"63": "three"};
    refs["extra"] = "four";
    for (var key in refs) {
        X.compare(key);
    }
}

function specialPrototypeKey() {
    var refs = {"__proto__": "five"};
    for (var key in refs) {
        X.compare(key);
    }
}
""".lstrip(),
                encoding="utf-8",
            )
            dynamic = root / "dynamic.json"
            dynamic.write_text(
                json.dumps(
                    {
                        "upstream_commit": UPSTREAM_COMMIT,
                        "patterns": [],
                    }
                ),
                encoding="utf-8",
            )
            output = root / "inventory.json"
            self.run_extractor(rules, dynamic, output)
            inventory = json.loads(output.read_text(encoding="utf-8"))

            self.assertEqual(
                [
                    call["argument_kind"]
                    for call in inventory["calls"]
                ],
                [
                    "static_expression",
                    "dynamic",
                    "dynamic",
                    "dynamic",
                ],
            )
            self.assertEqual(
                inventory["calls"][0]["static_patterns"],
                ["60", "61"],
            )
            self.assertEqual(
                inventory["finite_object_key_iterations"],
                [
                    {
                        "path": "db/object_keys.sg",
                        "function": "safe",
                        "function_line": 1,
                        "object": "refs",
                        "key": "key",
                        "loop_line": 3,
                        "static_values": ["60", "61"],
                    }
                ],
            )
            self.assertEqual(
                inventory["plain_object_enumeration_audit"][
                    "unsafe_reference_count"
                ],
                0,
            )

            (rules / "db" / "prototype_mutation.sg").write_text(
                """
Object.prototype.extra = "65";
function shadowedObject() {
    var Object = {prototype: {hasOwnProperty: {call: touch}}};
    Object.prototype.hasOwnProperty.call();
}
function poisoned() {
    var refs = {"66": "six"};
    for (var key in refs) {
        X.compare(key);
    }
}
""".lstrip(),
                encoding="utf-8",
            )
            poisoned_output = root / "poisoned.json"
            self.run_extractor(rules, dynamic, poisoned_output)
            poisoned = json.loads(
                poisoned_output.read_text(encoding="utf-8")
            )
            self.assertEqual(
                poisoned["finite_object_key_iterations"],
                [],
            )
            self.assertEqual(
                poisoned["argument_kind_counts"],
                {"dynamic": 5},
            )
            self.assertEqual(
                poisoned["plain_object_enumeration_audit"][
                    "unsafe_reference_count"
                ],
                2,
            )

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
            self.assertEqual(
                inventory["max_static_values_per_expression"],
                4096,
            )
            self.assertEqual(
                [
                    (
                        item["path"],
                        item["name"],
                        item["source_sha256"],
                    )
                    for item in inventory["verified_static_transforms"]
                ],
                [
                    (
                        "db/PE/__GenericHeuristicAnalysis_By_DosX.7.sg",
                        "convertStringToUnicodeSignature",
                        "3c056d3048e21c54c20476f49deb81126a52edf6b7ce6a17848960f726cdc1d9",
                    ),
                    (
                        "db/PE/protector_VMProtect_NET.2.sg",
                        "generateUnicodeSignatureMask",
                        "1dab6af286316c2cccda2a3a3bc6698b287df9e2ab872f8b9b7ebbe69cfec4af",
                    ),
                    (
                        "db_extra/PE/protector_Protection_Plus_SDK.2.sg",
                        "toUtf16LE",
                        "2039971c64346d49c427088f7f58b8c62f58104886bc06d7084ad37e91117d5b",
                    ),
                ],
            )
            self.assertEqual(
                inventory["value_preserving_self_assignments"],
                [
                    {
                        "path": (
                            "db/PE/"
                            "__GenericHeuristicAnalysis_By_DosX.7.sg"
                        ),
                        "function": (
                            "scanForMaliciousCode_NET_and_Native"
                        ),
                        "function_line": 6178,
                        "symbol": "njRatDataSeparatorPattern",
                        "assignment_line": 6194,
                    }
                ],
            )
            self.assertEqual(
                inventory["static_transform_verification_failures"],
                [],
            )
            self.assertEqual(
                inventory["top_level_function_audit"],
                {
                    "top_level_definition_count": 2290,
                    "unique_name_count": 95,
                    "duplicate_name_count": 7,
                    "unresolved_direct_call_name_count": 72,
                    "safe_definition_count": 95,
                    "safety_contract": (
                        "top-level name is unique across db/db_extra and "
                        "has no unresolved direct call in another parsed "
                        "rule; nested functions use lexical scope"
                    ),
                },
            )
            self.assertEqual(
                inventory["plain_object_enumeration_audit"],
                {
                    "object_reference_count": 1,
                    "safe_has_own_property_call_count": 1,
                    "unsafe_reference_count": 0,
                    "unsafe_references": [],
                    "safety_contract": (
                        "all Object references resolve to the "
                        "undeclared global built-in and are direct "
                        "Object.prototype.hasOwnProperty.call uses, "
                        "with no globalThis/eval/Function or "
                        "__proto__/constructor access in db/db_extra"
                    ),
                },
            )
            self.assertEqual(
                len(inventory["finite_parameter_values"]),
                26,
            )
            self.assertEqual(
                len(inventory["finite_scoped_assignments"]),
                5,
            )
            self.assertEqual(
                inventory["finite_object_key_iterations"],
                [
                    {
                        "path": "db/Binary/format_PDB.1.sg",
                        "function": "detect",
                        "function_line": 13,
                        "object": "refs",
                        "key": "key",
                        "loop_line": 34,
                        "static_values": [
                            "%%%%%%%%%%'.cs'00",
                            "'$'11'@P:FSharp.Core'00",
                            (
                                "'$'11'@P:"
                                "Microsoft.VisualBasic'00"
                            ),
                            "'std::'%%%%%%",
                        ],
                    }
                ],
            )
            self.assertEqual(
                [
                    (
                        item["path"],
                        item["symbol"],
                        item["iterations"],
                        item["loop_line"],
                        item["invalidation_line"],
                    )
                    for item in inventory["finite_loop_accumulations"]
                ],
                [
                    (
                        "db/PE/protector_NetReactor.2.sg",
                        "signatureToScan",
                        5,
                        50,
                        83,
                    ),
                    (
                        "db/PE/protector_VMProtect_NET.2.sg",
                        "globalBigPattern",
                        12,
                        27,
                        41,
                    ),
                ],
            )
            self.assertIn(
                {
                    "path": "db/Binary/audio.1.sg",
                    "function": "isAVP",
                    "function_line": 10850,
                    "symbol": "d1",
                    "assignment_line": 10852,
                    "invalidation_line": None,
                    "static_values": ["48E7FCFE"],
                },
                inventory["finite_scoped_assignments"],
            )
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
                    "dynamic": 13,
                    "literal": 5855,
                    "static_expression": 100,
                },
            )
            self.assertEqual(
                inventory["dynamic_expression_type_counts"],
                {
                    "Binary": 3,
                    "SymbolRef": 10,
                },
            )
            self.assertEqual(inventory["static_pattern_count"], 5569)
            comparison = inventory["dynamic_inventory_comparison"]
            self.assertEqual(comparison["intersection_count"], 317)
            self.assertEqual(comparison["dynamic_only_count"], 0)
            self.assertEqual(comparison["static_only_count"], 5252)


if __name__ == "__main__":
    unittest.main()
