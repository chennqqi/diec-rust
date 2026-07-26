#!/usr/bin/env node
"use strict";

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const SCHEMA_VERSION = 1;
const GENERATOR_VERSION = 1;
const RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6";
const UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254";
const RULE_PATH = "db/PE/__GenericHeuristicAnalysis_By_DosX.7.sg";
const RULE_SHA256 =
    "c84a375fdc66508c66ae10440ab46be23d345d602b2ae6d79e26e66393ebadde";
const MAX_VALUES = 4096;

function fail(message) {
    throw new Error(message);
}

function sha256(value) {
    return crypto.createHash("sha256").update(value).digest("hex");
}

function compareOrdinal(left, right) {
    return left < right ? -1 : left > right ? 1 : 0;
}

function uniqueSorted(values) {
    return [...new Set(values)].sort(compareOrdinal);
}

function parseArguments(argv) {
    const result = {};
    for (let index = 2; index < argv.length; index += 2) {
        const name = argv[index];
        const value = argv[index + 1];
        if (!name || !name.startsWith("--") || !value) {
            fail("arguments must be --name value pairs");
        }
        result[name.slice(2)] = value;
    }
    for (const required of ["rules-root", "parser-module", "output"]) {
        if (!result[required]) {
            fail(`missing --${required}`);
        }
    }
    return result;
}

function sourceSlice(source, node) {
    return source.slice(node.start.pos, node.end.endpos);
}

function findTopLevelFunction(uglify, ast, name) {
    let found = null;
    ast.walk(
        new uglify.TreeWalker(function (node) {
            if (
                node instanceof uglify.AST_Defun &&
                node.name &&
                node.name.name === name &&
                !this.find_parent(uglify.AST_Lambda)
            ) {
                if (found) {
                    fail(`duplicate top-level function: ${name}`);
                }
                found = node;
            }
        }),
    );
    if (!found) {
        fail(`missing top-level function: ${name}`);
    }
    return found;
}

function collectOpcodes(uglify, constructor) {
    const result = new Map();
    constructor.walk(
        new uglify.TreeWalker(function (node) {
            if (
                node instanceof uglify.AST_Assign &&
                node.operator === "=" &&
                node.left instanceof uglify.AST_Dot &&
                node.left.expression instanceof uglify.AST_This &&
                node.right instanceof uglify.AST_String
            ) {
                result.set(node.left.property, node.right.value);
            }
        }),
    );
    if (result.size < 150) {
        fail(`unexpected NetOpCodes property count: ${result.size}`);
    }
    return result;
}

function crossProduct(left, right, combine) {
    if (left.length * right.length > MAX_VALUES) {
        return null;
    }
    const values = [];
    for (const leftValue of left) {
        for (const rightValue of right) {
            const value = combine(leftValue, rightValue);
            if (value === null) {
                return null;
            }
            values.push(value);
        }
    }
    return values;
}

function strings(values) {
    return values && values.every((value) => typeof value === "string")
        ? values
        : null;
}

function evaluate(uglify, node, environment, opcodes, seen = new Set()) {
    if (!node || seen.has(node)) {
        return null;
    }
    if (node instanceof uglify.AST_String) {
        return [node.value];
    }
    if (node instanceof uglify.AST_Number) {
        return [node.value];
    }
    if (node instanceof uglify.AST_SymbolRef) {
        if (!node.thedef || !environment.has(node.thedef.id)) {
            return null;
        }
        return environment.get(node.thedef.id);
    }
    if (node instanceof uglify.AST_New) {
        if (
            node.expression instanceof uglify.AST_SymbolRef &&
            node.expression.name === "NetOpCodes" &&
            node.args.length === 0
        ) {
            return [{ kind: "opcodes" }];
        }
        return null;
    }
    if (node instanceof uglify.AST_Array) {
        const elements = [];
        for (const element of node.elements) {
            const values = evaluate(
                uglify,
                element,
                environment,
                opcodes,
                new Set(seen).add(node),
            );
            const staticStrings = strings(values);
            if (!staticStrings) {
                return null;
            }
            elements.push(...staticStrings);
        }
        return [{ kind: "array", elements }];
    }
    if (node instanceof uglify.AST_Dot) {
        const receivers = evaluate(
            uglify,
            node.expression,
            environment,
            opcodes,
            new Set(seen).add(node),
        );
        if (
            receivers &&
            receivers.length === 1 &&
            receivers[0].kind === "opcodes" &&
            opcodes.has(node.property)
        ) {
            return [opcodes.get(node.property)];
        }
        return null;
    }
    if (node instanceof uglify.AST_Sub) {
        const receivers = evaluate(
            uglify,
            node.expression,
            environment,
            opcodes,
            new Set(seen).add(node),
        );
        if (
            !receivers ||
            receivers.length !== 1 ||
            receivers[0].kind !== "array"
        ) {
            return null;
        }
        const indexes = evaluate(
            uglify,
            node.property,
            environment,
            opcodes,
            new Set(seen).add(node),
        );
        if (!indexes) {
            return receivers[0].elements;
        }
        const selected = indexes
            .filter(Number.isInteger)
            .map((index) => receivers[0].elements[index])
            .filter((value) => value !== undefined);
        return selected.length ? selected : null;
    }
    if (
        node instanceof uglify.AST_Binary &&
        node.operator === "+"
    ) {
        const left = strings(
            evaluate(
                uglify,
                node.left,
                environment,
                opcodes,
                new Set(seen).add(node),
            ),
        );
        const right = strings(
            evaluate(
                uglify,
                node.right,
                environment,
                opcodes,
                new Set(seen).add(node),
            ),
        );
        return left && right
            ? crossProduct(left, right, (a, b) => a + b)
            : null;
    }
    if (node instanceof uglify.AST_Conditional) {
        const consequent = evaluate(
            uglify,
            node.consequent,
            environment,
            opcodes,
            new Set(seen).add(node),
        );
        const alternative = evaluate(
            uglify,
            node.alternative,
            environment,
            opcodes,
            new Set(seen).add(node),
        );
        return consequent && alternative
            ? [...consequent, ...alternative]
            : null;
    }
    if (node instanceof uglify.AST_Call) {
        let method = null;
        let isOpcodeMethod = false;
        if (node.expression instanceof uglify.AST_Dot) {
            method = node.expression.property;
            const receiver = evaluate(
                uglify,
                node.expression.expression,
                environment,
                opcodes,
                new Set(seen).add(node),
            );
            isOpcodeMethod = Boolean(
                receiver &&
                    receiver.length === 1 &&
                    receiver[0].kind === "opcodes",
            );
        } else if (
            node.expression instanceof uglify.AST_SymbolRef
        ) {
            method = node.expression.name;
        }
        const argumentValues = node.args.map((argument) =>
            strings(
                evaluate(
                    uglify,
                    argument,
                    environment,
                    opcodes,
                    new Set(seen).add(node),
                ),
            ),
        );
        if (argumentValues.some((values) => !values)) {
            return null;
        }
        if (isOpcodeMethod && method === "setStrict") {
            return crossProduct(
                argumentValues[0],
                argumentValues[1],
                (opcode, value) => {
                    const cleanOpcode = opcode.replace(/\s+/g, "");
                    const cleanValue = value.replace(/\s+/g, "");
                    const wildcard = cleanOpcode.indexOf("??");
                    const body =
                        wildcard === -1
                            ? cleanOpcode
                            : cleanOpcode.substring(0, wildcard);
                    if (
                        wildcard !== -1 &&
                        cleanOpcode.substring(body.length).length !==
                            cleanValue.length
                    ) {
                        return null;
                    }
                    return body + cleanValue;
                },
            );
        }
        if (isOpcodeMethod && method === "setNullValue") {
            return argumentValues[0].map((value) =>
                value.split("??").join("00"),
            );
        }
        if (
            isOpcodeMethod &&
            method === "joinNoBodyAndValue"
        ) {
            return crossProduct(
                argumentValues[0],
                argumentValues[1],
                (opcode, value) =>
                    opcode + value.replace(/\s+/g, ""),
            );
        }
        if (method === "replaceAllInString") {
            const first = crossProduct(
                argumentValues[0],
                argumentValues[1],
                (input, search) => ({ input, search }),
            );
            return first
                ? crossProduct(
                      first,
                      argumentValues[2],
                      (pair, replacement) =>
                          pair.input
                              .split(pair.search)
                              .join(replacement),
                  )
                : null;
        }
    }
    return null;
}

function main() {
    const options = parseArguments(process.argv);
    const uglify = require(path.resolve(options["parser-module"]));
    const rulePath = path.join(
        path.resolve(options["rules-root"]),
        ...RULE_PATH.split("/"),
    );
    const bytes = fs.readFileSync(rulePath);
    const ruleHash = sha256(bytes);
    if (ruleHash !== RULE_SHA256) {
        fail(
            `rule source hash mismatch: expected ${RULE_SHA256}, got ${ruleHash}`,
        );
    }
    const source = bytes.toString("utf8");
    const ast = uglify.parse(source, { filename: RULE_PATH });
    ast.figure_out_scope();
    const constructor = findTopLevelFunction(
        uglify,
        ast,
        "NetOpCodes",
    );
    const scan = findTopLevelFunction(
        uglify,
        ast,
        "scanForObfuscations_NET",
    );
    const opcodes = collectOpcodes(uglify, constructor);
    const environment = new Map();
    const mutableDefinitions = new Set();
    scan.walk(
        new uglify.TreeWalker(function (node) {
            if (
                (node instanceof uglify.AST_UnaryPrefix ||
                    node instanceof uglify.AST_UnaryPostfix) &&
                (node.operator === "++" || node.operator === "--") &&
                node.expression instanceof uglify.AST_SymbolRef &&
                node.expression.thedef
            ) {
                mutableDefinitions.add(node.expression.thedef.id);
            }
            if (
                node instanceof uglify.AST_Assign &&
                node.left instanceof uglify.AST_SymbolRef &&
                node.left.thedef
            ) {
                mutableDefinitions.add(node.left.thedef.id);
            }
        }),
    );
    scan.walk(
        new uglify.TreeWalker(function (node) {
            if (
                !(node instanceof uglify.AST_VarDef) ||
                !node.name ||
                !node.name.thedef ||
                !node.value ||
                mutableDefinitions.has(node.name.thedef.id)
            ) {
                return;
            }
            const values = evaluate(
                uglify,
                node.value,
                environment,
                opcodes,
            );
            if (values) {
                environment.set(node.name.thedef.id, values);
            }
        }),
    );
    const calls = [];
    scan.walk(
        new uglify.TreeWalker(function (node) {
            if (
                !(node instanceof uglify.AST_Call) ||
                !(node.expression instanceof uglify.AST_SymbolRef) ||
                node.expression.name !== "validateNetByteCode"
            ) {
                return;
            }
            const patterns = strings(
                evaluate(
                    uglify,
                    node.args[0],
                    environment,
                    opcodes,
                ),
            );
            if (!patterns || patterns.length === 0) {
                fail(
                    `cannot statically evaluate validateNetByteCode at line ${node.start.line}`,
                );
            }
            calls.push({
                line: node.start.line,
                argument_expression: sourceSlice(
                    source,
                    node.args[0],
                ),
                pattern_count: uniqueSorted(patterns).length,
                patterns: uniqueSorted(patterns),
            });
        }),
    );
    if (calls.length !== 33) {
        fail(`unexpected validateNetByteCode call count: ${calls.length}`);
    }
    const patterns = uniqueSorted(
        calls.flatMap((call) => call.patterns),
    );
    const patternBytes = Buffer.from(patterns.join("\n"), "utf8");
    const output = {
        schema_version: SCHEMA_VERSION,
        generator: {
            path: "tools/rules/extract_net_bytecode_patterns.js",
            version: GENERATOR_VERSION,
        },
        upstream_commit: UPSTREAM_COMMIT,
        rules_commit: RULES_COMMIT,
        source: {
            path: RULE_PATH,
            sha256: ruleHash,
        },
        scope:
            "finite string values passed to all validateNetByteCode call sites in scanForObfuscations_NET",
        proof_boundary:
            "hash-pinned AST evaluation of NetOpCodes string properties, three pure opcode methods, replaceAllInString, concatenation, and finite array indexing; no rule code is executed",
        opcode_property_count: opcodes.size,
        call_site_count: calls.length,
        expanded_call_count: calls.reduce(
            (total, call) => total + call.pattern_count,
            0,
        ),
        pattern_count: patterns.length,
        patterns_lf_sha256: sha256(patternBytes),
        patterns_lf_hash_contract:
            "UTF-8 of ordinally sorted unique patterns joined by LF without trailing LF",
        calls,
        patterns,
    };
    const outputPath = path.resolve(options.output);
    fs.mkdirSync(path.dirname(outputPath), { recursive: true });
    fs.writeFileSync(
        outputPath,
        JSON.stringify(output, null, 2) + "\n",
        "utf8",
    );
}

main();
