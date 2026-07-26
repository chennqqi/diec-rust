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
VALIDATE_REFERENCES_FUNCTION = """function validateReferences(isPositive, references) {
    for (var i = 0; i < references.length; i++) {
        var sign = "00'" + references[i] + "'00";
        if (isPositive == true) {
            if (!PE.isSignatureInSectionPresent(0, sign)) {
                return true;
            }
        } else { // negative
            if (PE.isSignatureInSectionPresent(0, sign)) {
                return true;
            }
        }
    }
    return false;
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

    def test_array_parameter_requires_verified_helper_and_exact_call_shape(
        self,
    ):
        cases = {
            "safe": (
                """
function detect() {
    validateReferences(
        isPositive = true,
        references = ["60", "61"]
    );
}
""".lstrip(),
                VALIDATE_REFERENCES_FUNCTION,
                "static_expression",
            ),
            "changed_source": (
                """
function detect() {
    validateReferences(
        isPositive = true,
        references = ["60", "61"]
    );
}
""".lstrip(),
                VALIDATE_REFERENCES_FUNCTION.replace(
                    "// negative",
                    "// changed",
                ),
                "dynamic",
            ),
            "direct_array": (
                """
function detect() {
    validateReferences(true, ["60", "61"]);
}
""".lstrip(),
                VALIDATE_REFERENCES_FUNCTION,
                "dynamic",
            ),
            "escaped": (
                """
function detect() {
    var callback = validateReferences;
    callback(true, ["60", "61"]);
}
""".lstrip(),
                VALIDATE_REFERENCES_FUNCTION,
                "dynamic",
            ),
        }
        for name, (detect, helper, expected_kind) in cases.items():
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as directory:
                    root = pathlib.Path(directory)
                    rules = root / "rules"
                    target = (
                        rules
                        / "db"
                        / "PE"
                        / "cryptor_LimeCrypter.2.sg"
                    )
                    target.parent.mkdir(parents=True)
                    (rules / "db_extra").mkdir()
                    target.write_bytes(
                        (detect + "\n" + helper + "\n").encode(
                            "utf-8"
                        )
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
                        [
                            call["argument_kind"]
                            for call in inventory["calls"]
                        ],
                        [expected_kind, expected_kind],
                    )
                    self.assertEqual(
                        inventory["static_patterns"],
                        (
                            ["00'60'00", "00'61'00"]
                            if expected_kind == "static_expression"
                            else []
                        ),
                    )
                    self.assertEqual(
                        len(
                            inventory[
                                "finite_array_parameter_values"
                            ]
                        ),
                        1
                        if expected_kind == "static_expression"
                        else 0,
                    )
                    audit = inventory[
                        "static_array_parameter_function_audit"
                    ]
                    self.assertEqual(
                        audit["safe_definition_count"],
                        1
                        if name in {"safe", "direct_array"}
                        else 0,
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
    X.isVerbose();
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
    X.isVerbose();
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
                        "function_line": 20,
                        "symbol": "signature",
                        "assignment_line": 22,
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

    def test_adjacent_assignment_is_limited_to_next_safe_statement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            rules = root / "rules"
            (rules / "db").mkdir(parents=True)
            (rules / "db_extra").mkdir()
            (rules / "db" / "adjacent.sg").write_text(
                """
function safe(index) {
    var patterns = ["60", "61"];
    var signature;
    signature = "00" + patterns[index];
    if (X.compare(signature)) {
    }
    X.compare(signature);
}

function unknownCall() {
    var signature;
    signature = "62";
    if (touch() && X.compare(signature)) {
    }
}

function gap() {
    var signature;
    signature = "63";
    X.isVerbose();
    X.compare(signature);
}

function targetWrite() {
    var signature;
    signature = "64";
    if ((signature = "65") && X.compare(signature)) {
    }
}

function conditionalWrite(flag) {
    var signature;
    if (flag) signature = "66";
    X.compare(signature);
}

function capturedByHostCallback() {
    var signature;
    signature = "67";
    if (PE.callback(function () {
        signature = "68";
    }) && X.compare(signature)) {
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
                    "dynamic",
                    "dynamic",
                    "dynamic",
                ],
            )
            self.assertEqual(
                inventory["calls"][0]["static_patterns"],
                ["0060", "0061"],
            )
            self.assertEqual(
                inventory["finite_adjacent_assignments"],
                [
                    {
                        "path": "db/adjacent.sg",
                        "function": "safe",
                        "function_line": 1,
                        "symbol": "signature",
                        "assignment_line": 4,
                        "use_lines": [5],
                        "invalidation_line": 6,
                        "static_values": ["0060", "0061"],
                    }
                ],
            )

    def test_object_array_element_assignment_requires_pure_non_escaping_shape(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            rules = root / "rules"
            (rules / "db").mkdir(parents=True)
            (rules / "db_extra").mkdir()
            (rules / "db" / "object_elements.sg").write_text(
                """
function safe(k) {
    var pattern, signature;
    for (var j = 0; j < 1; j++) {}
    var rows = [
        {edition: undefined, references: ["60", "61"], enabled: true},
        {edition: "two", references: ["62"], enabled: true}
    ];
    for (var j = 0; j < rows.length; j++) {
        pattern = rows[j];
        for (var k = 0; k < pattern.references.length; k++) {
            signature = "00" + pattern.references[k];
            if (X.compare(signature)) {}
        }
        if (pattern.edition) {}
    }
}

function escaped(k) {
    var pattern;
    var rows = [{references: ["63"]}];
    for (var j = 0; j < rows.length; j++) {
        pattern = rows[j];
        touch(pattern.references);
        X.compare(pattern.references[k]);
    }
}

function impure(k) {
    var pattern;
    var rows = [{references: ["64"], label: touch()}];
    for (var j = 0; j < rows.length; j++) {
        pattern = rows[j];
        X.compare(pattern.references[k]);
    }
}

function nonzero(k) {
    var pattern;
    var rows = [{references: ["65"]}];
    for (var j = 1; j < rows.length; j++) {
        pattern = rows[j];
        X.compare(pattern.references[k]);
    }
}

function captured(k) {
    var pattern;
    var callback = function () { return pattern.references[0]; };
    var rows = [{references: ["66"]}];
    for (var j = 0; j < rows.length; j++) {
        pattern = rows[j];
        X.compare(pattern.references[k]);
    }
    callback();
}

function propertyWrite(k) {
    var pattern;
    var rows = [{references: ["67"]}];
    for (var j = 0; j < rows.length; j++) {
        pattern = rows[j];
        pattern.references[0] = "68";
        X.compare(pattern.references[k]);
    }
}

function lengthWrite(k) {
    var pattern;
    var rows = [{references: ["69"]}];
    for (var j = 0; j < rows.length; j++) {
        pattern = rows[j];
        pattern.references.length = 0;
        X.compare(pattern.references[k]);
    }
}

function deleted(k) {
    var pattern;
    var rows = [{edition: "x", references: ["70"]}];
    for (var j = 0; j < rows.length; j++) {
        pattern = rows[j];
        delete pattern.edition;
        X.compare(pattern.references[k]);
    }
}

function sourceAlias(k) {
    var pattern;
    var rows = [{references: ["71"]}];
    for (var j = 0; j < rows.length; j++) {
        pattern = rows[j];
        var alias = rows[0];
        X.compare(pattern.references[k]);
    }
}

function notFirst(k) {
    var pattern;
    var rows = [{references: ["72"]}];
    for (var j = 0; j < rows.length; j++) {
        X.isVerbose();
        pattern = rows[j];
        X.compare(pattern.references[k]);
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
                    "dynamic",
                    "dynamic",
                    "dynamic",
                    "dynamic",
                    "dynamic",
                    "dynamic",
                ],
            )
            self.assertEqual(
                inventory["calls"][0]["static_patterns"],
                ["0060", "0061", "0062"],
            )
            self.assertEqual(
                inventory["finite_object_element_assignments"],
                [
                    {
                        "path": "db/object_elements.sg",
                        "function": "safe",
                        "function_line": 1,
                        "source": "rows",
                        "target": "pattern",
                        "loop_index": "j",
                        "loop_line": 8,
                        "assignment_line": 9,
                        "element_count": 2,
                        "invalidation_line": 15,
                    }
                ],
            )
            self.assertEqual(
                inventory["finite_adjacent_assignments"],
                [
                    {
                        "path": "db/object_elements.sg",
                        "function": "safe",
                        "function_line": 1,
                        "symbol": "signature",
                        "assignment_line": 11,
                        "use_lines": [12],
                        "invalidation_line": 12,
                        "static_values": ["0060", "0061", "0062"],
                    }
                ],
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
                inventory[
                    "static_array_parameter_function_audit"
                ],
                {
                    "configured_spec_count": 3,
                    "verified_definition_count": 3,
                    "safe_definition_count": 3,
                    "unsafe_reference_count": 0,
                    "verified_definitions": [
                        {
                            "path": (
                                "db/PE/"
                                "cryptor_LimeCrypter.2.sg"
                            ),
                            "name": "validateReferences",
                            "line": 39,
                            "source_sha256": (
                                "aee17a5bf77037e78a05883d33a50eda"
                                "bfe0e5b4eb1126ba515f11767193f71d"
                            ),
                            "parameter": "references",
                            "parameter_index": 1,
                        },
                        {
                            "path": "db/PE/cryptor_PEUnion.2.sg",
                            "name": "validateReferences",
                            "line": 86,
                            "source_sha256": (
                                "ceb0109b92a60190e3cc926a6678acac"
                                "7d36d5ea0d35020351db5186c5460c05"
                            ),
                            "parameter": "references",
                            "parameter_index": 1,
                        },
                        {
                            "path": (
                                "db_extra/PE/"
                                "cryptor_njCrypter.2.sg"
                            ),
                            "name": "validateReferences",
                            "line": 33,
                            "source_sha256": (
                                "aee17a5bf77037e78a05883d33a50eda"
                                "bfe0e5b4eb1126ba515f11767193f71d"
                            ),
                            "parameter": "references",
                            "parameter_index": 1,
                        },
                    ],
                    "unsafe_references": [],
                    "safety_contract": (
                        "configured top-level helpers match path, "
                        "name, and source hash; every same-name "
                        "reference in db/db_extra is a direct call "
                        "bound to a verified definition in the same "
                        "evaluated rule"
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
                [
                    (
                        item["path"],
                        item["function"],
                        item["parameter"],
                        item["element_count"],
                    )
                    for item in inventory[
                        "finite_array_parameter_values"
                    ]
                ],
                [
                    (
                        "db/PE/cryptor_LimeCrypter.2.sg",
                        "validateReferences",
                        "references",
                        4,
                    ),
                    (
                        "db/PE/cryptor_PEUnion.2.sg",
                        "validateReferences",
                        "references",
                        14,
                    ),
                    (
                        (
                            "db_extra/PE/"
                            "cryptor_njCrypter.2.sg"
                        ),
                        "validateReferences",
                        "references",
                        8,
                    ),
                ],
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
                inventory["finite_object_element_assignments"],
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
                        "source": "maliciousImportPatterns",
                        "target": "pattern",
                        "loop_index": "j",
                        "loop_line": 6363,
                        "assignment_line": 6364,
                        "element_count": 12,
                        "invalidation_line": 6391,
                    }
                ],
            )
            self.assertEqual(
                inventory["finite_adjacent_assignments"],
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
                        "symbol": "importSignature",
                        "assignment_line": 6219,
                        "use_lines": [6220],
                        "invalidation_line": 6222,
                        "static_values": [
                            "00'System.Diagnostics'00",
                            "00'System.IO.Compression'00",
                            "00'kernel32'00",
                            "00'ntdll'00",
                            "00'user32'00",
                        ],
                    },
                    {
                        "path": (
                            "db/PE/"
                            "__GenericHeuristicAnalysis_By_DosX.7.sg"
                        ),
                        "function": (
                            "scanForMaliciousCode_NET_and_Native"
                        ),
                        "function_line": 6178,
                        "symbol": "importSignature",
                        "assignment_line": 6368,
                        "use_lines": [6369],
                        "invalidation_line": 6371,
                        "static_values": [
                            "00'A'00",
                            "00'DestroyWindow'00",
                            "00'EmptyWorkingSet'00",
                            "00'EnumChildWindows'00",
                            "00'GetAsyncKeyState'00",
                            "00'GetForegroundWindow'00",
                            "00'GetKeyboardState'00",
                            "00'GetWindowText'00",
                            "00'GetWindowTextA'00",
                            "00'GetWindowTextLength'00",
                            "00'GetWindowTextLengthA'00",
                            "00'KERNEL32.DLL'00",
                            "00'Kernel32.dll'00",
                            "00'MapVirtualKey'00",
                            "00'Microsoft.CSharp'00",
                            "00'NtSetInformationProcess'00",
                            "00'NtsetInformationProcess'00",
                            "00'OK'00",
                            "00'RtlSetProcessIsCritical'00",
                            "00'SendMessage'00",
                            "00'SetThreadExecutionState'00",
                            "00'SetWindowPos'00",
                            "00'Stub'00",
                            "00'System.Core'00",
                            "00'System.Drawing'00",
                            "00'System.Management'00",
                            (
                                "00'System.Runtime."
                                "InteropServices'00"
                            ),
                            (
                                "00'System.Security."
                                "Cryptography'00"
                            ),
                            "00'System.Windows.Forms'00",
                            "00'ToUnicodeEx'00",
                            "00'USB'00",
                            "00'avicap32.dll'00",
                            "00'capCreateCaptureWindowA'00",
                            "00'capGetDriverDescriptionA'00",
                            "00'k'00",
                            "00'kernel32'00",
                            "00'kernel32.dll'00",
                            "00'kl'00",
                            "00'ntdll'00",
                            "00'ntdll.dll'00",
                            "00'psapi'00",
                            "00'user32'00",
                            "00'user32.dll'00",
                            "00'w'00",
                            "00'winmm.dll'00",
                            "00'wintrust.dll'00",
                        ],
                    },
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
                    "dynamic": 5,
                    "literal": 5855,
                    "static_expression": 108,
                },
            )
            self.assertEqual(
                inventory["dynamic_expression_type_counts"],
                {
                    "Binary": 3,
                    "SymbolRef": 2,
                },
            )
            self.assertEqual(inventory["static_pattern_count"], 5628)
            comparison = inventory["dynamic_inventory_comparison"]
            self.assertEqual(comparison["intersection_count"], 317)
            self.assertEqual(comparison["dynamic_only_count"], 0)
            self.assertEqual(comparison["static_only_count"], 5311)


if __name__ == "__main__":
    unittest.main()
