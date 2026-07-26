#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const SCHEMA_VERSION = 1;
const GENERATOR_VERSION = 1;
const RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6";
const UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254";
const FORMATS_COMMIT = "1151e7254fdee3c0294ff7095edbdd7bfccf8201";
const XSCANENGINE_COMMIT =
    "dfe4a419e4f491bb23688ba03c5a5bf39e34da83";

const METHOD_ARGUMENT_INDEX = new Map([
    ["compare", 0],
    ["c", 0],
    ["compareEP", 0],
    ["compareOverlay", 0],
    ["findSignature", 2],
    ["fSig", 2],
    ["isSignaturePresent", 2],
    ["isSignatureInSectionPresent", 1],
]);

const KNOWN_HOST_RECEIVERS = new Set([
    "Amiga",
    "APK",
    "Archive",
    "Binary",
    "COM",
    "DEX",
    "ELF",
    "File",
    "ISO9660",
    "JAR",
    "JPEG",
    "LE",
    "LX",
    "MACH",
    "MSDOS",
    "NE",
    "NPM",
    "PDF",
    "PE",
    "PNG",
    "PYC",
    "X",
]);

function fail(message) {
    throw new Error(message);
}

function parseArguments(argv) {
    const result = {};
    for (let index = 2; index < argv.length; index += 1) {
        const argument = argv[index];
        if (!argument.startsWith("--")) {
            fail(`unexpected positional argument: ${argument}`);
        }
        const name = argument.slice(2);
        const value = argv[index + 1];
        if (!value || value.startsWith("--")) {
            fail(`missing value for --${name}`);
        }
        result[name] = value;
        index += 1;
    }
    for (const required of [
        "rules-root",
        "output",
        "dynamic-inventory",
    ]) {
        if (!result[required]) {
            fail(`missing --${required}`);
        }
    }
    if (!result["parser-module"]) {
        result["parser-module"] = path.join(
            result["rules-root"],
            "autotools",
            "dbcompiler",
            "node_modules",
            "uglify-js",
            "tools",
            "node.js",
        );
    }
    return result;
}

function toPosix(value) {
    return value.split(path.sep).join("/");
}

function compareOrdinal(left, right) {
    if (left < right) {
        return -1;
    }
    if (left > right) {
        return 1;
    }
    return 0;
}

function sha256Bytes(value) {
    return crypto.createHash("sha256").update(value).digest("hex");
}

function listFiles(root, predicate) {
    const result = [];
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
            } else if (entry.isFile() && predicate(target)) {
                result.push(target);
            }
        }
    }
    visit(root);
    return result;
}

function sourceManifest(root, files) {
    const records = files.map((file) => {
        const bytes = fs.readFileSync(file);
        return {
            path: toPosix(path.relative(root, file)),
            bytes: bytes.length,
            sha256: sha256Bytes(bytes),
        };
    });
    const contract = records
        .map((record) => `${record.path}\0${record.sha256}\n`)
        .join("");
    return {
        file_count: records.length,
        byte_count: records.reduce(
            (total, record) => total + record.bytes,
            0,
        ),
        manifest_sha256: sha256Bytes(Buffer.from(contract, "utf8")),
        manifest_hash_contract:
            "ordinal path + NUL + lowercase file SHA-256 + LF",
    };
}

function parserIdentity(parserModule) {
    const packageRoot = path.resolve(
        path.dirname(parserModule),
        "..",
    );
    const packageJsonPath = path.join(packageRoot, "package.json");
    const packageJson = JSON.parse(
        fs.readFileSync(packageJsonPath, "utf8"),
    );
    const files = listFiles(packageRoot, () => true);
    return {
        name: packageJson.name,
        version: packageJson.version,
        license: packageJson.license,
        module: "autotools/dbcompiler/node_modules/uglify-js/tools/node.js",
        ...sourceManifest(packageRoot, files),
    };
}

function memberName(uglify, expression) {
    if (expression instanceof uglify.AST_Dot) {
        return {
            receiver: expression.expression,
            method: expression.property,
        };
    }
    if (
        expression instanceof uglify.AST_Sub &&
        expression.property instanceof uglify.AST_String
    ) {
        return {
            receiver: expression.expression,
            method: expression.property.value,
        };
    }
    return null;
}

function receiverRoot(uglify, expression) {
    if (expression instanceof uglify.AST_SymbolRef) {
        return expression.name;
    }
    if (
        expression instanceof uglify.AST_Dot ||
        expression instanceof uglify.AST_Sub
    ) {
        return receiverRoot(uglify, expression.expression);
    }
    return null;
}

function uniqueSorted(values) {
    return [...new Set(values)].sort();
}

function staticValues(
    uglify,
    expression,
    constantInitializers = new Map(),
    resolving = new Set(),
    usePosition = Number.POSITIVE_INFINITY,
) {
    if (expression instanceof uglify.AST_String) {
        return [expression.value];
    }
    if (expression instanceof uglify.AST_Number) {
        return [expression.value];
    }
    if (expression instanceof uglify.AST_SymbolRef) {
        const definition = expression.thedef;
        if (
            !definition ||
            !constantInitializers.has(definition.id) ||
            resolving.has(definition.id)
        ) {
            return null;
        }
        const initializer = constantInitializers.get(definition.id);
        if (initializer.position > usePosition) {
            return null;
        }
        const nextResolving = new Set(resolving);
        nextResolving.add(definition.id);
        return staticValues(
            uglify,
            initializer.value,
            constantInitializers,
            nextResolving,
            initializer.position,
        );
    }
    if (expression instanceof uglify.AST_Conditional) {
        const consequent = staticValues(
            uglify,
            expression.consequent,
            constantInitializers,
            resolving,
            usePosition,
        );
        const alternative = staticValues(
            uglify,
            expression.alternative,
            constantInitializers,
            resolving,
            usePosition,
        );
        if (!consequent || !alternative) {
            return null;
        }
        return uniqueSorted([...consequent, ...alternative]);
    }
    if (expression instanceof uglify.AST_Sequence) {
        const last = expression.expressions.at(-1);
        return last
            ? staticValues(
                  uglify,
                  last,
                  constantInitializers,
                  resolving,
                  usePosition,
              )
            : null;
    }
    if (
        expression instanceof uglify.AST_Binary &&
        expression.operator === "+"
    ) {
        const left = staticValues(
            uglify,
            expression.left,
            constantInitializers,
            resolving,
            usePosition,
        );
        const right = staticValues(
            uglify,
            expression.right,
            constantInitializers,
            resolving,
            usePosition,
        );
        if (!left || !right) {
            return null;
        }
        const values = [];
        for (const leftValue of left) {
            for (const rightValue of right) {
                values.push(leftValue + rightValue);
            }
        }
        return uniqueSorted(values);
    }
    return null;
}

function sourceSlice(source, node) {
    if (!node || !node.start || !node.end) {
        return null;
    }
    return source.slice(node.start.pos, node.end.endpos);
}

function inspectFile(uglify, rulesRoot, file) {
    const source = fs.readFileSync(file, "utf8");
    const relativePath = toPosix(path.relative(rulesRoot, file));
    const ast = uglify.parse(source, { filename: relativePath });
    ast.figure_out_scope();
    const initializerCandidates = new Map();
    const mutatedDefinitions = new Set();
    function markDefinitions(node) {
        if (!node) {
            return;
        }
        node.walk(
            new uglify.TreeWalker((child) => {
                if (
                    child instanceof uglify.AST_Symbol &&
                    child.thedef
                ) {
                    mutatedDefinitions.add(child.thedef.id);
                }
            }),
        );
    }
    ast.walk(
        new uglify.TreeWalker((node) => {
            if (
                node instanceof uglify.AST_VarDef &&
                node.name &&
                node.name.thedef &&
                node.value
            ) {
                const definitionId = node.name.thedef.id;
                if (initializerCandidates.has(definitionId)) {
                    mutatedDefinitions.add(definitionId);
                } else {
                    initializerCandidates.set(definitionId, {
                        value: node.value,
                        position: node.end.endpos,
                    });
                }
            }
            if (node instanceof uglify.AST_Assign) {
                markDefinitions(node.left);
            }
            if (node instanceof uglify.AST_ForIn) {
                markDefinitions(node.init);
            }
            if (
                (node instanceof uglify.AST_UnaryPrefix ||
                    node instanceof uglify.AST_UnaryPostfix) &&
                (node.operator === "++" || node.operator === "--") &&
                node.expression instanceof uglify.AST_SymbolRef &&
                node.expression.thedef
            ) {
                mutatedDefinitions.add(node.expression.thedef.id);
            }
        }),
    );
    const constantInitializers = new Map(
        [...initializerCandidates].filter(
            ([definitionId]) => !mutatedDefinitions.has(definitionId),
        ),
    );
    const calls = [];
    ast.walk(
        new uglify.TreeWalker((node) => {
            if (!(node instanceof uglify.AST_Call)) {
                return;
            }
            const member = memberName(uglify, node.expression);
            if (!member || !METHOD_ARGUMENT_INDEX.has(member.method)) {
                return;
            }
            const argumentIndex = METHOD_ARGUMENT_INDEX.get(member.method);
            const argument = node.args[argumentIndex];
            const root = receiverRoot(uglify, member.receiver);
            const values = argument
                ? staticValues(
                      uglify,
                      argument,
                      constantInitializers,
                      new Set(),
                      node.start.pos,
                  )
                : null;
            const stringValues = values
                ? values.filter((value) => typeof value === "string")
                : [];
            let argumentKind = "dynamic";
            if (!argument) {
                argumentKind = "missing";
            } else if (argument instanceof uglify.AST_String) {
                argumentKind = "literal";
            } else if (
                values &&
                stringValues.length === values.length &&
                stringValues.length > 0
            ) {
                argumentKind = "static_expression";
            }
            calls.push({
                path: relativePath,
                line: node.start.line,
                column: node.start.col,
                receiver: member.receiver.print_to_string(),
                receiver_root: root,
                known_host_receiver:
                    root !== null && KNOWN_HOST_RECEIVERS.has(root),
                method: member.method,
                argument_index: argumentIndex,
                argument_kind: argumentKind,
                argument_ast_type: argument ? argument.TYPE : null,
                argument_expression: sourceSlice(source, argument),
                static_patterns:
                    argumentKind === "literal" ||
                    argumentKind === "static_expression"
                        ? uniqueSorted(stringValues)
                        : [],
            });
        }),
    );
    return calls;
}

function countBy(records, key) {
    const counts = {};
    for (const record of records) {
        const value = String(record[key]);
        counts[value] = (counts[value] || 0) + 1;
    }
    return Object.fromEntries(
        Object.entries(counts).sort(([left], [right]) =>
            compareOrdinal(left, right),
        ),
    );
}

function loadDynamicComparison(inventoryPath, staticPatterns) {
    const bytes = fs.readFileSync(inventoryPath);
    const inventory = JSON.parse(bytes.toString("utf8"));
    if (inventory.upstream_commit !== UPSTREAM_COMMIT) {
        fail("dynamic inventory upstream commit does not match");
    }
    if (!Array.isArray(inventory.patterns)) {
        fail("dynamic inventory patterns are missing");
    }
    const dynamicPatterns = uniqueSorted(inventory.patterns);
    const staticSet = new Set(staticPatterns);
    const dynamicSet = new Set(dynamicPatterns);
    return {
        path: "docs/research/data/signature-pattern-inventory.json",
        sha256: sha256Bytes(bytes),
        dynamic_pattern_count: dynamicPatterns.length,
        static_pattern_count: staticPatterns.length,
        intersection_count: dynamicPatterns.filter((value) =>
            staticSet.has(value),
        ).length,
        dynamic_only_count: dynamicPatterns.filter(
            (value) => !staticSet.has(value),
        ).length,
        static_only_count: staticPatterns.filter(
            (value) => !dynamicSet.has(value),
        ).length,
        dynamic_only_patterns: dynamicPatterns.filter(
            (value) => !staticSet.has(value),
        ),
    };
}

function buildInventory(options) {
    const rulesRoot = path.resolve(options["rules-root"]);
    const parserModule = path.resolve(options["parser-module"]);
    const uglify = require(parserModule);
    const ruleFiles = ["db", "db_extra"].flatMap((directory) =>
        listFiles(
            path.join(rulesRoot, directory),
            (file) => file.endsWith(".sg"),
        ),
    );
    ruleFiles.sort((left, right) =>
        compareOrdinal(
            toPosix(path.relative(rulesRoot, left)),
            toPosix(path.relative(rulesRoot, right)),
        ),
    );
    const calls = ruleFiles.flatMap((file) =>
        inspectFile(uglify, rulesRoot, file),
    );
    calls.sort(
        (left, right) =>
            compareOrdinal(left.path, right.path) ||
            left.line - right.line ||
            left.column - right.column ||
            compareOrdinal(left.method, right.method),
    );
    const knownCalls = calls.filter((call) => call.known_host_receiver);
    const unknownCalls = calls.filter(
        (call) => !call.known_host_receiver,
    );
    const staticPatterns = uniqueSorted(
        knownCalls.flatMap((call) => call.static_patterns),
    );
    const dynamicCalls = knownCalls.filter(
        (call) =>
            call.argument_kind === "dynamic" ||
            call.argument_kind === "missing",
    );
    const rulesIdentity = sourceManifest(rulesRoot, ruleFiles);
    return {
        schema_version: SCHEMA_VERSION,
        generator: {
            path: "tools/rules/extract_static_signature_inventory.js",
            version: GENERATOR_VERSION,
        },
        upstream_commit: UPSTREAM_COMMIT,
        rules_commit: RULES_COMMIT,
        formats_commit: FORMATS_COMMIT,
        xscanengine_commit: XSCANENGINE_COMMIT,
        scope:
            "all syntactic calls to fixed Binary_Script signature API names " +
            "in db/db_extra .sg files; static values are conservative and " +
            "dynamic expressions remain explicit",
        parser: parserIdentity(parserModule),
        rules: {
            roots: ["db", "db_extra"],
            parse_success_count: ruleFiles.length,
            parse_failure_count: 0,
            ...rulesIdentity,
        },
        method_argument_indices: Object.fromEntries(
            [...METHOD_ARGUMENT_INDEX.entries()].sort(([left], [right]) =>
                compareOrdinal(left, right),
            ),
        ),
        known_host_receivers: [...KNOWN_HOST_RECEIVERS].sort(),
        call_site_count: calls.length,
        known_host_call_site_count: knownCalls.length,
        unknown_receiver_call_site_count: unknownCalls.length,
        known_host_calling_file_count: new Set(
            knownCalls.map((call) => call.path),
        ).size,
        method_counts: countBy(knownCalls, "method"),
        argument_kind_counts: countBy(knownCalls, "argument_kind"),
        static_pattern_count: staticPatterns.length,
        static_patterns: staticPatterns,
        dynamic_call_site_count: dynamicCalls.length,
        dynamic_expression_type_counts: countBy(
            dynamicCalls,
            "argument_ast_type",
        ),
        dynamic_calls: dynamicCalls,
        unknown_receiver_calls: unknownCalls,
        dynamic_inventory_comparison: loadDynamicComparison(
            path.resolve(options["dynamic-inventory"]),
            staticPatterns,
        ),
        calls,
        limitations: [
            "computed method names are not attributable to a signature API",
            "function calls, loops, unresolved symbols, and mutable data flow remain dynamic",
            "static expression enumeration is limited to literals, single-initializer unmodified symbol references, +, conditionals, and sequences",
            "same-named methods on unknown receivers are retained as audit candidates",
        ],
    };
}

function main() {
    const options = parseArguments(process.argv);
    const inventory = buildInventory(options);
    const output = path.resolve(options.output);
    fs.mkdirSync(path.dirname(output), { recursive: true });
    fs.writeFileSync(
        output,
        `${JSON.stringify(inventory, null, 2)}\n`,
        "utf8",
    );
}

if (require.main === module) {
    try {
        main();
    } catch (error) {
        console.error(error && error.stack ? error.stack : String(error));
        process.exitCode = 1;
    }
}

module.exports = {
    buildInventory,
    inspectFile,
    staticValues,
};
