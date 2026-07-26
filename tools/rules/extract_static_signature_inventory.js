#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const SCHEMA_VERSION = 1;
const GENERATOR_VERSION = 1;
const MAX_STATIC_VALUES_PER_EXPRESSION = 4096;
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

const STATIC_TRANSFORM_SPECS = new Map([
    [
        "db/PE/__GenericHeuristicAnalysis_By_DosX.7.sg\0" +
            "convertStringToUnicodeSignature",
        {
            sha256:
                "3c056d3048e21c54c20476f49deb81126a52edf6b7ce6a17848960f726cdc1d9",
            semantics: "UTF-16 code units to uppercase little-endian hex",
            transform(value) {
                let result = "";
                for (let index = 0; index < value.length; index += 1) {
                    const code = value.charCodeAt(index);
                    result += (code & 0xff)
                        .toString(16)
                        .toUpperCase()
                        .padStart(2, "0");
                    result += ((code >> 8) & 0xff)
                        .toString(16)
                        .toUpperCase()
                        .padStart(2, "0");
                }
                return result;
            },
        },
    ],
    [
        "db/PE/protector_VMProtect_NET.2.sg\0" +
            "generateUnicodeSignatureMask",
        {
            sha256:
                "1dab6af286316c2cccda2a3a3bc6698b287df9e2ab872f8b9b7ebbe69cfec4af",
            semantics:
                "UTF-16 code units as quoted signature literals separated by 00",
            transform(value) {
                let result = "";
                for (let index = 0; index < value.length; index += 1) {
                    result +=
                        (index === 0 ? "" : "00") +
                        "'" +
                        value[index] +
                        "'";
                }
                return result;
            },
        },
    ],
    [
        "db_extra/PE/protector_Protection_Plus_SDK.2.sg\0" +
            "toUtf16LE",
        {
            sha256:
                "2039971c64346d49c427088f7f58b8c62f58104886bc06d7084ad37e91117d5b",
            semantics:
                "UTF-16 code units as lowercase hex followed by 00",
            transform(value) {
                let result = "";
                for (let index = 0; index < value.length; index += 1) {
                    result +=
                        value
                            .charCodeAt(index)
                            .toString(16)
                            .padStart(2, "0") + "00";
                }
                return result;
            },
        },
    ],
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

function boundedUniqueSorted(values) {
    const result = uniqueSorted(values);
    return result.length <= MAX_STATIC_VALUES_PER_EXPRESSION
        ? result
        : null;
}

function initializerFor(
    expression,
    constantInitializers,
    resolving,
    usePosition,
) {
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
    return {
        expression: initializer.value,
        resolving: nextResolving,
        usePosition: initializer.position,
    };
}

function indexedNodes(
    uglify,
    expression,
    constantInitializers,
    resolving,
    usePosition,
    staticTransforms,
) {
    let collections;
    if (expression.expression instanceof uglify.AST_Sub) {
        collections = indexedNodes(
            uglify,
            expression.expression,
            constantInitializers,
            resolving,
            usePosition,
            staticTransforms,
        );
    } else if (
        expression.expression instanceof uglify.AST_SymbolRef
    ) {
        const initializer = initializerFor(
            expression.expression,
            constantInitializers,
            resolving,
            usePosition,
        );
        collections =
            initializer &&
            initializer.expression instanceof uglify.AST_Array
                ? [initializer.expression]
                : null;
    } else if (expression.expression instanceof uglify.AST_Array) {
        collections = [expression.expression];
    } else {
        collections = null;
    }
    if (!collections) {
        return null;
    }

    const indices = staticValues(
        uglify,
        expression.property,
        constantInitializers,
        resolving,
        usePosition,
        staticTransforms,
    );
    const selected = [];
    for (const collection of collections) {
        if (!(collection instanceof uglify.AST_Array)) {
            return null;
        }
        if (!indices) {
            selected.push(
                ...collection.elements.filter((element) => element),
            );
            if (
                selected.length >
                MAX_STATIC_VALUES_PER_EXPRESSION
            ) {
                return null;
            }
            continue;
        }
        for (const index of indices) {
            const numericIndex = Number(index);
            if (
                !Number.isSafeInteger(numericIndex) ||
                numericIndex < 0 ||
                String(numericIndex) !== String(index)
            ) {
                return null;
            }
            const element = collection.elements[numericIndex];
            if (element) {
                selected.push(element);
                if (
                    selected.length >
                    MAX_STATIC_VALUES_PER_EXPRESSION
                ) {
                    return null;
                }
            }
        }
    }
    return selected;
}

function staticValues(
    uglify,
    expression,
    constantInitializers = new Map(),
    resolving = new Set(),
    usePosition = Number.POSITIVE_INFINITY,
    staticTransforms = new Map(),
) {
    if (expression instanceof uglify.AST_String) {
        return [expression.value];
    }
    if (expression instanceof uglify.AST_Number) {
        return [expression.value];
    }
    if (expression instanceof uglify.AST_SymbolRef) {
        const staticSymbolValues =
            constantInitializers.static_symbol_values;
        if (
            staticSymbolValues &&
            expression.thedef &&
            staticSymbolValues.has(expression.thedef.id)
        ) {
            return staticSymbolValues.get(expression.thedef.id);
        }
        const initializer = initializerFor(
            expression,
            constantInitializers,
            resolving,
            usePosition,
        );
        if (!initializer) {
            return null;
        }
        return staticValues(
            uglify,
            initializer.expression,
            constantInitializers,
            initializer.resolving,
            initializer.usePosition,
            staticTransforms,
        );
    }
    if (expression instanceof uglify.AST_Sub) {
        const nodes = indexedNodes(
            uglify,
            expression,
            constantInitializers,
            resolving,
            usePosition,
            staticTransforms,
        );
        if (!nodes) {
            return null;
        }
        const values = [];
        for (const node of nodes) {
            const nodeValues = staticValues(
                uglify,
                node,
                constantInitializers,
                resolving,
                usePosition,
                staticTransforms,
            );
            if (!nodeValues) {
                return null;
            }
            values.push(...nodeValues);
        }
        return boundedUniqueSorted(values);
    }
    if (expression instanceof uglify.AST_Conditional) {
        const consequent = staticValues(
            uglify,
            expression.consequent,
            constantInitializers,
            resolving,
            usePosition,
            staticTransforms,
        );
        const alternative = staticValues(
            uglify,
            expression.alternative,
            constantInitializers,
            resolving,
            usePosition,
            staticTransforms,
        );
        if (!consequent || !alternative) {
            return null;
        }
        return boundedUniqueSorted([...consequent, ...alternative]);
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
                  staticTransforms,
              )
            : null;
    }
    if (
        expression instanceof uglify.AST_Call &&
        expression.expression instanceof uglify.AST_SymbolRef &&
        expression.expression.name === "String" &&
        expression.expression.thedef &&
        expression.expression.thedef.undeclared
    ) {
        if (expression.args.length === 0) {
            return [""];
        }
        if (expression.args.length === 1) {
            const values = staticValues(
                uglify,
                expression.args[0],
                constantInitializers,
                resolving,
                usePosition,
                staticTransforms,
            );
            return values
                ? boundedUniqueSorted(values.map((value) => String(value)))
                : null;
        }
        return null;
    }
    if (
        expression instanceof uglify.AST_Call &&
        expression.expression instanceof uglify.AST_SymbolRef &&
        expression.expression.thedef &&
        staticTransforms.has(expression.expression.thedef.id)
    ) {
        const transform = staticTransforms.get(
            expression.expression.thedef.id,
        );
        const argumentValues = [];
        for (const argument of expression.args) {
            const values = staticValues(
                uglify,
                argument,
                constantInitializers,
                resolving,
                usePosition,
                staticTransforms,
            );
            if (!values) {
                return null;
            }
            argumentValues.push(values);
        }
        if (
            argumentValues.length !== 1 ||
            argumentValues[0].length >
                MAX_STATIC_VALUES_PER_EXPRESSION
        ) {
            return null;
        }
        return boundedUniqueSorted(
            argumentValues[0].map((value) =>
                transform(String(value)),
            ),
        );
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
            staticTransforms,
        );
        const right = staticValues(
            uglify,
            expression.right,
            constantInitializers,
            resolving,
            usePosition,
            staticTransforms,
        );
        if (!left || !right) {
            return null;
        }
        if (
            left.length * right.length >
            MAX_STATIC_VALUES_PER_EXPRESSION
        ) {
            return null;
        }
        const values = [];
        for (const leftValue of left) {
            for (const rightValue of right) {
                values.push(leftValue + rightValue);
            }
        }
        return boundedUniqueSorted(values);
    }
    return null;
}

function sourceSlice(source, node) {
    if (!node || !node.start || !node.end) {
        return null;
    }
    return source.slice(node.start.pos, node.end.endpos);
}

function inspectFile(
    uglify,
    rulesRoot,
    file,
    safeTopLevelFunctions = new Set(),
) {
    const source = fs.readFileSync(file, "utf8");
    const relativePath = toPosix(path.relative(rulesRoot, file));
    const ast = uglify.parse(source, { filename: relativePath });
    ast.figure_out_scope();
    const staticTransforms = new Map();
    const verifiedStaticTransforms = [];
    const staticTransformVerificationFailures = [];
    ast.walk(
        new uglify.TreeWalker((node) => {
            if (
                !(node instanceof uglify.AST_Defun) ||
                !node.name ||
                !node.name.thedef
            ) {
                return;
            }
            const key = `${relativePath}\0${node.name.name}`;
            if (!STATIC_TRANSFORM_SPECS.has(key)) {
                return;
            }
            const spec = STATIC_TRANSFORM_SPECS.get(key);
            const sourceSha256 = sha256Bytes(
                Buffer.from(sourceSlice(source, node), "utf8"),
            );
            const identity = {
                path: relativePath,
                name: node.name.name,
                source_sha256: sourceSha256,
                expected_source_sha256: spec.sha256,
                semantics: spec.semantics,
            };
            if (sourceSha256 === spec.sha256) {
                staticTransforms.set(
                    node.name.thedef.id,
                    spec.transform,
                );
                verifiedStaticTransforms.push(identity);
            } else {
                staticTransformVerificationFailures.push(identity);
            }
        }),
    );
    const initializerCandidates = new Map();
    const mutatedDefinitions = new Set();
    const unsafeArrayDefinitions = new Set();
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
    ast.walk(
        new uglify.TreeWalker(function (node) {
            if (
                !(node instanceof uglify.AST_SymbolRef) ||
                !node.thedef ||
                !initializerCandidates.has(node.thedef.id)
            ) {
                return;
            }
            const initializer = initializerCandidates.get(
                node.thedef.id,
            ).value;
            if (!(initializer instanceof uglify.AST_Array)) {
                return;
            }
            const parent = this.parent();
            const isIndexRead =
                parent instanceof uglify.AST_Sub &&
                parent.expression === node;
            const isLengthRead =
                parent instanceof uglify.AST_Dot &&
                parent.expression === node &&
                parent.property === "length";
            if (!isIndexRead && !isLengthRead) {
                unsafeArrayDefinitions.add(node.thedef.id);
            }
        }),
    );
    const constantInitializers = new Map(
        [...initializerCandidates].filter(
            ([definitionId]) =>
                !mutatedDefinitions.has(definitionId) &&
                !unsafeArrayDefinitions.has(definitionId),
        ),
    );
    const functionInfos = new Map();
    ast.walk(
        new uglify.TreeWalker(function (node) {
            if (
                node instanceof uglify.AST_Defun &&
                node.name &&
                node.name.thedef
            ) {
                const topLevel =
                    !this.find_parent(uglify.AST_Lambda);
                functionInfos.set(node.name.thedef.id, {
                    definition: node.name.thedef,
                    name: node.name.name,
                    line: node.start.line,
                    top_level: topLevel,
                    parameters: node.argnames,
                    calls: [],
                    escaped: false,
                });
            }
        }),
    );
    ast.walk(
        new uglify.TreeWalker(function (node) {
            if (
                node instanceof uglify.AST_Call &&
                node.expression instanceof uglify.AST_SymbolRef &&
                node.expression.thedef &&
                functionInfos.has(node.expression.thedef.id)
            ) {
                functionInfos
                    .get(node.expression.thedef.id)
                    .calls.push(node);
            }
            if (
                !(node instanceof uglify.AST_SymbolRef) ||
                !node.thedef
            ) {
                return;
            }
            const parent = this.parent();
            if (functionInfos.has(node.thedef.id)) {
                const isDirectCall =
                    parent instanceof uglify.AST_Call &&
                    parent.expression === node;
                if (!isDirectCall) {
                    functionInfos.get(node.thedef.id).escaped = true;
                }
            }
        }),
    );
    const staticSymbolValues = new Map();
    constantInitializers.static_symbol_values = staticSymbolValues;
    const finiteParameterValues = new Map();
    for (
        let iteration = 0;
        iteration < functionInfos.size;
        iteration += 1
    ) {
        let changed = false;
        for (const info of functionInfos.values()) {
            if (
                info.escaped ||
                info.calls.length === 0 ||
                (info.top_level &&
                    !safeTopLevelFunctions.has(
                        `${relativePath}\0${info.name}`,
                    ))
            ) {
                continue;
            }
            for (
                let parameterIndex = 0;
                parameterIndex < info.parameters.length;
                parameterIndex += 1
            ) {
                const parameter = info.parameters[parameterIndex];
                if (!parameter || !parameter.thedef) {
                    continue;
                }
                const values = [];
                let complete = true;
                for (const call of info.calls) {
                    const argument = call.args[parameterIndex];
                    const argumentValues = argument
                        ? staticValues(
                              uglify,
                              argument,
                              constantInitializers,
                              new Set(),
                              call.start.pos,
                              staticTransforms,
                          )
                        : null;
                    if (!argumentValues) {
                        complete = false;
                        break;
                    }
                    values.push(...argumentValues);
                    if (
                        values.length >
                        MAX_STATIC_VALUES_PER_EXPRESSION
                    ) {
                        complete = false;
                        break;
                    }
                }
                if (!complete) {
                    continue;
                }
                const staticValuesForParameter =
                    boundedUniqueSorted(values);
                if (!staticValuesForParameter) {
                    continue;
                }
                const definitionId = parameter.thedef.id;
                const previous = staticSymbolValues.get(definitionId);
                if (
                    !previous ||
                    previous.length !==
                        staticValuesForParameter.length ||
                    previous.some(
                        (value, index) =>
                            value !== staticValuesForParameter[index],
                    )
                ) {
                    staticSymbolValues.set(
                        definitionId,
                        staticValuesForParameter,
                    );
                    finiteParameterValues.set(definitionId, {
                        function: info.name,
                        function_line: info.line,
                        parameter: parameter.name,
                        parameter_index: parameterIndex,
                        direct_call_site_count: info.calls.length,
                        static_values: staticValuesForParameter,
                    });
                    changed = true;
                }
            }
        }
        if (!changed) {
            break;
        }
    }
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
                      staticTransforms,
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
    return {
        path: relativePath,
        calls,
        finite_parameter_values: [...finiteParameterValues.values()],
        verified_static_transforms: verifiedStaticTransforms,
        static_transform_verification_failures:
            staticTransformVerificationFailures,
    };
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

function auditTopLevelFunctions(uglify, rulesRoot, ruleFiles) {
    const definitions = [];
    const definitionCounts = new Map();
    const unresolvedDirectCallNames = new Set();
    for (const file of ruleFiles) {
        const source = fs.readFileSync(file, "utf8");
        const relativePath = toPosix(path.relative(rulesRoot, file));
        const ast = uglify.parse(source, { filename: relativePath });
        ast.figure_out_scope();
        ast.walk(
            new uglify.TreeWalker(function (node) {
                if (
                    node instanceof uglify.AST_Defun &&
                    node.name &&
                    !this.find_parent(uglify.AST_Lambda)
                ) {
                    definitions.push({
                        path: relativePath,
                        name: node.name.name,
                    });
                    definitionCounts.set(
                        node.name.name,
                        (definitionCounts.get(node.name.name) || 0) + 1,
                    );
                }
                if (
                    node instanceof uglify.AST_Call &&
                    node.expression instanceof uglify.AST_SymbolRef &&
                    node.expression.thedef &&
                    node.expression.thedef.undeclared
                ) {
                    unresolvedDirectCallNames.add(
                        node.expression.name,
                    );
                }
            }),
        );
    }
    const safeDefinitions = definitions.filter(
        (definition) =>
            definitionCounts.get(definition.name) === 1 &&
            !unresolvedDirectCallNames.has(definition.name),
    );
    return {
        safe_keys: new Set(
            safeDefinitions.map(
                (definition) =>
                    `${definition.path}\0${definition.name}`,
            ),
        ),
        evidence: {
            top_level_definition_count: definitions.length,
            unique_name_count: [...definitionCounts.values()].filter(
                (count) => count === 1,
            ).length,
            duplicate_name_count: [...definitionCounts.values()].filter(
                (count) => count > 1,
            ).length,
            unresolved_direct_call_name_count:
                unresolvedDirectCallNames.size,
            safe_definition_count: safeDefinitions.length,
            safety_contract:
                "top-level name is unique across db/db_extra and has no unresolved direct call in another parsed rule; nested functions use lexical scope",
        },
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
    const topLevelFunctionAudit = auditTopLevelFunctions(
        uglify,
        rulesRoot,
        ruleFiles,
    );
    const fileResults = ruleFiles.map((file) =>
        inspectFile(
            uglify,
            rulesRoot,
            file,
            topLevelFunctionAudit.safe_keys,
        ),
    );
    const calls = fileResults.flatMap((result) => result.calls);
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
        max_static_values_per_expression:
            MAX_STATIC_VALUES_PER_EXPRESSION,
        top_level_function_audit: topLevelFunctionAudit.evidence,
        verified_static_transforms: fileResults.flatMap(
            (result) => result.verified_static_transforms,
        ),
        finite_parameter_values: fileResults.flatMap((result) =>
            result.finite_parameter_values.map((item) => ({
                path: result.path,
                ...item,
            })),
        ),
        static_transform_verification_failures: fileResults.flatMap(
            (result) =>
                result.static_transform_verification_failures,
        ),
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
            "unverified function calls, loops, unresolved symbols, and mutable data flow remain dynamic",
            "only path/name/source-hash verified pure string transforms are evaluated",
            "function parameters are enumerated only when a named function does not escape and every direct call argument is static",
            "static expression enumeration is limited to literals, finite non-escaping arrays with statically enumerable elements, single-initializer unmodified symbol references, +, conditionals, and sequences",
            "expressions exceeding the fixed static-value budget remain dynamic",
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
