#!/usr/bin/env node
"use strict";

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const SCHEMA_VERSION = 1;
const GENERATOR_VERSION = 1;
const RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6";
const UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254";

const KNOWN_HOST_RECEIVERS = new Set([
    "Amiga",
    "APK",
    "Archive",
    "AtariST",
    "Binary",
    "CFBF",
    "COM",
    "DEX",
    "DOS16M",
    "DOS4G",
    "ELF",
    "File",
    "IPA",
    "ISO9660",
    "JAR",
    "JavaClass",
    "JPEG",
    "LE",
    "LX",
    "MACH",
    "MACHOFAT",
    "MSDOS",
    "NE",
    "NPM",
    "PDF",
    "PE",
    "PNG",
    "PYC",
    "RAR",
    "X",
    "ZIP",
]);

function fail(message) {
    throw new Error(message);
}

function sha256(value) {
    return crypto.createHash("sha256").update(value).digest("hex");
}

function compareOrdinal(left, right) {
    return left < right ? -1 : left > right ? 1 : 0;
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

function toPosix(value) {
    return value.split(path.sep).join("/");
}

function listRuleFiles(root) {
    const files = [];
    function visit(directory) {
        const entries = fs
            .readdirSync(directory, { withFileTypes: true })
            .sort((left, right) =>
                compareOrdinal(left.name, right.name),
            );
        for (const entry of entries) {
            const target = path.join(directory, entry.name);
            if (entry.isDirectory()) {
                visit(target);
            } else if (
                entry.isFile() &&
                (entry.name.endsWith(".sg") ||
                    path.extname(entry.name) === "")
            ) {
                files.push(target);
            }
        }
    }
    for (const directory of ["db", "db_extra"]) {
        const target = path.join(root, directory);
        if (!fs.existsSync(target)) {
            fail(`missing rules directory: ${directory}`);
        }
        visit(target);
    }
    return files;
}

function increment(map, key, amount = 1) {
    map.set(key, (map.get(key) || 0) + amount);
}

function sortedCounts(map) {
    return Object.fromEntries(
        [...map.entries()].sort(([left], [right]) =>
            compareOrdinal(left, right),
        ),
    );
}

function rootSymbolNode(uglify, expression) {
    let current = expression;
    while (
        current instanceof uglify.AST_Dot ||
        current instanceof uglify.AST_Sub
    ) {
        current = current.expression;
    }
    return current instanceof uglify.AST_SymbolRef
        ? current
        : null;
}

function staticMemberName(uglify, expression) {
    if (expression instanceof uglify.AST_Dot) {
        return expression.property;
    }
    if (
        expression instanceof uglify.AST_Sub &&
        expression.property instanceof uglify.AST_String
    ) {
        return expression.property.value;
    }
    return null;
}

function memberDepth(uglify, expression) {
    let depth = 0;
    let current = expression;
    while (
        current instanceof uglify.AST_Dot ||
        current instanceof uglify.AST_Sub
    ) {
        depth += 1;
        current = current.expression;
    }
    return depth;
}

function aggregateRecord(records, key, initial) {
    if (!records.has(key)) {
        records.set(key, {
            ...initial,
            count: 0,
            files: new Set(),
            arities: new Map(),
            first_location: null,
        });
    }
    return records.get(key);
}

function observeCall(record, relativePath, node) {
    record.count += 1;
    record.files.add(relativePath);
    increment(record.arities, String(node.args.length));
    if (!record.first_location) {
        record.first_location = {
            path: relativePath,
            line: node.start.line,
            column: node.start.col,
        };
    }
}

function finalizeCallRecords(records) {
    return [...records.values()]
        .sort((left, right) => {
            const leftKey = `${left.receiver_root || ""}\0${
                left.name || left.method || ""
            }\0${left.member_depth || 0}`;
            const rightKey = `${right.receiver_root || ""}\0${
                right.name || right.method || ""
            }\0${right.member_depth || 0}`;
            return compareOrdinal(leftKey, rightKey);
        })
        .map((record) => ({
            ...Object.fromEntries(
                Object.entries(record).filter(
                    ([key]) =>
                        key !== "files" && key !== "arities",
                ),
            ),
            file_count: record.files.size,
            arity_counts: sortedCounts(record.arities),
        }));
}

function finalizeGlobalRecords(records) {
    return [...records.values()]
        .sort((left, right) =>
            compareOrdinal(left.name, right.name),
        )
        .map((record) => ({
            name: record.name,
            count: record.count,
            file_count: record.files.size,
            direct_call_count: record.direct_call_count,
            member_receiver_count: record.member_receiver_count,
            write_count: record.write_count,
            first_location: record.first_location,
        }));
}

function finalizeHostMembers(records) {
    return [...records.values()]
        .sort((left, right) => {
            const byRoot = compareOrdinal(
                left.receiver_root,
                right.receiver_root,
            );
            return byRoot || compareOrdinal(left.member, right.member);
        })
        .map((record) => ({
            receiver_root: record.receiver_root,
            member: record.member,
            count: record.count,
            file_count: record.files.size,
            call_target_count: record.call_target_count,
            write_target_count: record.write_target_count,
            first_location: record.first_location,
        }));
}

function finalizeScriptExtensions(records) {
    return [...records.values()]
        .sort((left, right) => {
            const byRoot = compareOrdinal(
                left.receiver_root,
                right.receiver_root,
            );
            return byRoot || compareOrdinal(left.member, right.member);
        })
        .map((record) => ({
            receiver_root: record.receiver_root,
            member: record.member,
            definition_count: record.definition_count,
            file_count: record.files.size,
            parameter_count_counts: sortedCounts(
                record.parameter_counts,
            ),
            definition_kind_counts: sortedCounts(
                record.definition_kinds,
            ),
            first_location: record.first_location,
        }));
}

function observeTopLevelFunction(
    records,
    name,
    parameterCount,
    kind,
    relativePath,
    node,
) {
    if (!records.has(name)) {
        records.set(name, {
            name,
            definition_count: 0,
            files: new Set(),
            parameter_counts: new Map(),
            definition_kinds: new Map(),
            first_location: null,
        });
    }
    const record = records.get(name);
    record.definition_count += 1;
    record.files.add(relativePath);
    increment(record.parameter_counts, String(parameterCount));
    increment(record.definition_kinds, kind);
    if (!record.first_location) {
        record.first_location = {
            path: relativePath,
            line: node.start.line,
            column: node.start.col,
        };
    }
}

function collectTopLevelFunctions(uglify, ast, relativePath, records) {
    for (const statement of ast.body) {
        if (statement instanceof uglify.AST_Defun) {
            observeTopLevelFunction(
                records,
                statement.name.name,
                statement.argnames.length,
                "function_declaration",
                relativePath,
                statement,
            );
            continue;
        }
        if (statement instanceof uglify.AST_Var) {
            for (const definition of statement.definitions) {
                if (definition.value instanceof uglify.AST_Function) {
                    observeTopLevelFunction(
                        records,
                        definition.name.name,
                        definition.value.argnames.length,
                        "variable_function",
                        relativePath,
                        definition,
                    );
                }
            }
            continue;
        }
        if (
            statement instanceof uglify.AST_SimpleStatement &&
            statement.body instanceof uglify.AST_Assign &&
            statement.body.operator === "=" &&
            statement.body.left instanceof uglify.AST_SymbolRef &&
            statement.body.right instanceof uglify.AST_Function
        ) {
            observeTopLevelFunction(
                records,
                statement.body.left.name,
                statement.body.right.argnames.length,
                "assignment_function",
                relativePath,
                statement.body,
            );
        }
    }
}

function finalizeTopLevelFunctions(records) {
    return [...records.values()]
        .sort((left, right) => compareOrdinal(left.name, right.name))
        .map((record) => ({
            name: record.name,
            definition_count: record.definition_count,
            file_count: record.files.size,
            parameter_count_counts: sortedCounts(
                record.parameter_counts,
            ),
            definition_kind_counts: sortedCounts(
                record.definition_kinds,
            ),
            first_location: record.first_location,
        }));
}

function main() {
    const options = parseArguments(process.argv);
    const rulesRoot = path.resolve(options["rules-root"]);
    const uglify = require(path.resolve(options["parser-module"]));
    const files = listRuleFiles(rulesRoot);
    const manifest = [];
    const astTypes = new Map();
    const binaryOperators = new Map();
    const unaryPrefixOperators = new Map();
    const unaryPostfixOperators = new Map();
    const assignmentOperators = new Map();
    const directCalls = new Map();
    const memberCalls = new Map();
    const knownHostCalls = new Map();
    const globals = new Map();
    const hostMembers = new Map();
    const scriptExtensions = new Map();
    const topLevelFunctions = new Map();
    let totalBytes = 0;
    let callCount = 0;

    for (const file of files) {
        const bytes = fs.readFileSync(file);
        const relativePath = toPosix(
            path.relative(rulesRoot, file),
        );
        totalBytes += bytes.length;
        manifest.push({
            path: relativePath,
            bytes: bytes.length,
            sha256: sha256(bytes),
        });
        let ast;
        try {
            ast = uglify.parse(bytes.toString("utf8"), {
                filename: relativePath,
            });
            ast.figure_out_scope();
        } catch (error) {
            fail(
                `parse failed for ${relativePath}: ${
                    error && error.message ? error.message : error
                }`,
            );
        }
        collectTopLevelFunctions(
            uglify,
            ast,
            relativePath,
            topLevelFunctions,
        );
        ast.walk(
            new uglify.TreeWalker(function (node) {
                increment(astTypes, node.TYPE);
                if (
                    node instanceof uglify.AST_Binary &&
                    !(node instanceof uglify.AST_Assign)
                ) {
                    increment(binaryOperators, node.operator);
                }
                if (node instanceof uglify.AST_UnaryPrefix) {
                    increment(unaryPrefixOperators, node.operator);
                }
                if (node instanceof uglify.AST_UnaryPostfix) {
                    increment(unaryPostfixOperators, node.operator);
                }
                if (node instanceof uglify.AST_Assign) {
                    increment(assignmentOperators, node.operator);
                }
                if (
                    node instanceof uglify.AST_Assign &&
                    node.operator === "=" &&
                    (node.left instanceof uglify.AST_Dot ||
                        node.left instanceof uglify.AST_Sub) &&
                    node.left.expression instanceof
                        uglify.AST_SymbolRef &&
                    KNOWN_HOST_RECEIVERS.has(
                        node.left.expression.name,
                    ) &&
                    node.right instanceof uglify.AST_Function
                ) {
                    observeScriptExtension(
                        scriptExtensions,
                        node.left.expression.name,
                        staticMemberName(uglify, node.left) ||
                            "<computed>",
                        node.right.argnames.length,
                        "member_assignment",
                        relativePath,
                        node,
                    );
                }
                if (
                    node instanceof uglify.AST_VarDef &&
                    node.name &&
                    KNOWN_HOST_RECEIVERS.has(node.name.name) &&
                    node.value instanceof uglify.AST_Object
                ) {
                    for (const property of node.value.properties) {
                        if (
                            property instanceof
                                uglify.AST_ObjectKeyVal &&
                            typeof property.key === "string" &&
                            property.value instanceof
                                uglify.AST_Function
                        ) {
                            observeScriptExtension(
                                scriptExtensions,
                                node.name.name,
                                property.key,
                                property.value.argnames.length,
                                "object_literal",
                                relativePath,
                                property,
                            );
                        }
                    }
                }
                if (
                    node instanceof uglify.AST_SymbolRef &&
                    node.thedef &&
                    node.thedef.undeclared
                ) {
                    const name = node.name;
                    if (!globals.has(name)) {
                        globals.set(name, {
                            name,
                            count: 0,
                            files: new Set(),
                            direct_call_count: 0,
                            member_receiver_count: 0,
                            write_count: 0,
                            first_location: null,
                        });
                    }
                    const record = globals.get(name);
                    record.count += 1;
                    record.files.add(relativePath);
                    if (!record.first_location) {
                        record.first_location = {
                            path: relativePath,
                            line: node.start.line,
                            column: node.start.col,
                        };
                    }
                    const parent = this.parent();
                    if (
                        parent instanceof uglify.AST_Call &&
                        parent.expression === node
                    ) {
                        record.direct_call_count += 1;
                    }
                    if (
                        (parent instanceof uglify.AST_Dot ||
                            parent instanceof uglify.AST_Sub) &&
                        parent.expression === node
                    ) {
                        record.member_receiver_count += 1;
                    }
                    if (
                        parent instanceof uglify.AST_Assign &&
                        parent.left === node
                    ) {
                        record.write_count += 1;
                    }
                    if (
                        (parent instanceof
                            uglify.AST_UnaryPrefix ||
                            parent instanceof
                                uglify.AST_UnaryPostfix) &&
                        (parent.operator === "++" ||
                            parent.operator === "--") &&
                        parent.expression === node
                    ) {
                        record.write_count += 1;
                    }
                }
                if (
                    (node instanceof uglify.AST_Dot ||
                        node instanceof uglify.AST_Sub) &&
                    node.expression instanceof
                        uglify.AST_SymbolRef &&
                    KNOWN_HOST_RECEIVERS.has(
                        node.expression.name,
                    ) &&
                    node.expression.thedef &&
                    node.expression.thedef.undeclared
                ) {
                    const receiver = node.expression.name;
                    const member =
                        staticMemberName(uglify, node) ||
                        "<computed>";
                    const key = `${receiver}\0${member}`;
                    if (!hostMembers.has(key)) {
                        hostMembers.set(key, {
                            receiver_root: receiver,
                            member,
                            count: 0,
                            files: new Set(),
                            call_target_count: 0,
                            write_target_count: 0,
                            first_location: null,
                        });
                    }
                    const record = hostMembers.get(key);
                    record.count += 1;
                    record.files.add(relativePath);
                    if (!record.first_location) {
                        record.first_location = {
                            path: relativePath,
                            line: node.start.line,
                            column: node.start.col,
                        };
                    }
                    const parent = this.parent();
                    if (
                        parent instanceof uglify.AST_Call &&
                        parent.expression === node
                    ) {
                        record.call_target_count += 1;
                    }
                    if (
                        parent instanceof uglify.AST_Assign &&
                        parent.left === node
                    ) {
                        record.write_target_count += 1;
                    }
                }
                if (
                    !(node instanceof uglify.AST_Call) ||
                    node instanceof uglify.AST_New
                ) {
                    return;
                }
                callCount += 1;
                if (
                    node.expression instanceof
                        uglify.AST_SymbolRef
                ) {
                    const name = node.expression.name;
                    const declared = Boolean(
                        node.expression.thedef &&
                            !node.expression.thedef.undeclared,
                    );
                    const key = `${declared ? "declared" : "global"}\0${name}`;
                    const record = aggregateRecord(
                        directCalls,
                        key,
                        {
                            name,
                            binding: declared
                                ? "declared"
                                : "undeclared_global",
                        },
                    );
                    observeCall(record, relativePath, node);
                    return;
                }
                if (
                    node.expression instanceof uglify.AST_Dot ||
                    node.expression instanceof uglify.AST_Sub
                ) {
                    const receiverSymbol = rootSymbolNode(
                        uglify,
                        node.expression,
                    );
                    const receiver = receiverSymbol
                        ? receiverSymbol.name
                        : null;
                    const method =
                        staticMemberName(
                            uglify,
                            node.expression,
                        ) || "<computed>";
                    const depth = memberDepth(
                        uglify,
                        node.expression,
                    );
                    const key = `${
                        receiver || "<expression>"
                    }\0${method}\0${depth}`;
                    const record = aggregateRecord(
                        memberCalls,
                        key,
                        {
                            receiver_root:
                                receiver || "<expression>",
                            method,
                            member_depth: depth,
                        },
                    );
                    observeCall(record, relativePath, node);
                    if (
                        receiver &&
                        KNOWN_HOST_RECEIVERS.has(receiver) &&
                        depth === 1 &&
                        receiverSymbol.thedef &&
                        receiverSymbol.thedef.undeclared
                    ) {
                        const hostRecord = aggregateRecord(
                            knownHostCalls,
                            key,
                            {
                                receiver_root: receiver,
                                method,
                                member_depth: depth,
                            },
                        );
                        observeCall(
                            hostRecord,
                            relativePath,
                            node,
                        );
                    }
                    return;
                }
                const key = node.expression.TYPE;
                const record = aggregateRecord(
                    memberCalls,
                    `<${key}>\0<call>`,
                    {
                        receiver_root: `<${key}>`,
                        method: "<call>",
                        member_depth: 0,
                    },
                );
                observeCall(record, relativePath, node);
            }),
        );
    }

    const manifestContract = Buffer.from(
        manifest
            .map(
                (record) =>
                    `${record.path}\0${record.bytes}\0${record.sha256}`,
            )
            .join("\n"),
        "utf8",
    );
    const output = {
        schema_version: SCHEMA_VERSION,
        generator: {
            path: "tools/rules/extract_rule_syntax_inventory.js",
            version: GENERATOR_VERSION,
            sha256: sha256(fs.readFileSync(__filename)),
        },
        upstream_commit: UPSTREAM_COMMIT,
        rules_commit: RULES_COMMIT,
        scope:
            "all .sg and extensionless files recursively selected from db and db_extra",
        parser: {
            name: "UglifyJS",
            source:
                "fixed Detect-It-Easy autotools/dbcompiler/node_modules/uglify-js/tools/node.js",
        },
        files: {
            count: manifest.length,
            bytes: totalBytes,
            parse_success_count: manifest.length,
            parse_failure_count: 0,
            manifest_sha256: sha256(manifestContract),
            manifest_hash_contract:
                "UTF-8 path NUL byte-count NUL sha256 records joined by LF without trailing LF, ordinal traversal",
            manifest,
        },
        ast_node_type_counts: sortedCounts(astTypes),
        operator_counts: {
            binary: sortedCounts(binaryOperators),
            unary_prefix: sortedCounts(unaryPrefixOperators),
            unary_postfix: sortedCounts(unaryPostfixOperators),
            assignment: sortedCounts(assignmentOperators),
        },
        calls: {
            count: callCount,
            direct: finalizeCallRecords(directCalls),
            member: finalizeCallRecords(memberCalls),
            known_host: finalizeCallRecords(knownHostCalls),
        },
        undeclared_globals: finalizeGlobalRecords(globals),
        known_host_first_level_members:
            finalizeHostMembers(hostMembers),
        known_receiver_script_extensions:
            finalizeScriptExtensions(scriptExtensions),
        top_level_function_definitions:
            finalizeTopLevelFunctions(topLevelFunctions),
        classification_boundary:
            "known_host records require an undeclared statically named receiver root and a direct first-level member call; deeper chains remain in member records because their final method belongs to an intermediate value; top_level_function_definitions contain only direct AST_Toplevel function declarations, function-valued var definitions, and simple identifier assignments; undeclared globals retain JS built-ins, runtime globals, rule-created globals, and HostApi globals for later source-backed classification",
    };
    const outputPath = path.resolve(options.output);
    fs.mkdirSync(path.dirname(outputPath), { recursive: true });
    fs.writeFileSync(
        outputPath,
        JSON.stringify(output, null, 2) + "\n",
        "utf8",
    );
}

function observeScriptExtension(
    records,
    receiver,
    member,
    parameterCount,
    kind,
    relativePath,
    node,
) {
    const key = `${receiver}\0${member}`;
    if (!records.has(key)) {
        records.set(key, {
            receiver_root: receiver,
            member,
            definition_count: 0,
            files: new Set(),
            parameter_counts: new Map(),
            definition_kinds: new Map(),
            first_location: null,
        });
    }
    const record = records.get(key);
    record.definition_count += 1;
    record.files.add(relativePath);
    increment(record.parameter_counts, String(parameterCount));
    increment(record.definition_kinds, kind);
    if (!record.first_location) {
        record.first_location = {
            path: relativePath,
            line: node.start.line,
            column: node.start.col,
        };
    }
}

main();
