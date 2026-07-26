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

const STATIC_ARRAY_PARAMETER_SPECS = new Map([
    [
        "db/PE/cryptor_LimeCrypter.2.sg\0validateReferences",
        {
            sha256:
                "aee17a5bf77037e78a05883d33a50edabfe0e5b4eb1126ba515f11767193f71d",
            parameter: "references",
            parameter_index: 1,
            named_argument: "references",
        },
    ],
    [
        "db/PE/cryptor_PEUnion.2.sg\0validateReferences",
        {
            sha256:
                "ceb0109b92a60190e3cc926a6678acac7d36d5ea0d35020351db5186c5460c05",
            parameter: "references",
            parameter_index: 1,
            named_argument: "references",
        },
    ],
    [
        "db_extra/PE/cryptor_njCrypter.2.sg\0validateReferences",
        {
            sha256:
                "aee17a5bf77037e78a05883d33a50edabfe0e5b4eb1126ba515f11767193f71d",
            parameter: "references",
            parameter_index: 1,
            named_argument: "references",
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

function isExactSelfAssignment(uglify, node) {
    return (
        node instanceof uglify.AST_Assign &&
        node.operator === "=" &&
        node.left instanceof uglify.AST_SymbolRef &&
        node.right instanceof uglify.AST_SymbolRef &&
        node.left.thedef &&
        node.right.thedef &&
        node.left.thedef.scope instanceof uglify.AST_Lambda &&
        node.left.thedef.id === node.right.thedef.id
    );
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

function boundedUniqueNodes(nodes) {
    const result = [...new Set(nodes)];
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

function finiteExpressionNodes(
    uglify,
    expression,
    constantInitializers,
    resolving,
    usePosition,
    staticTransforms,
) {
    if (
        expression instanceof uglify.AST_Array ||
        expression instanceof uglify.AST_Object ||
        expression instanceof uglify.AST_String ||
        expression instanceof uglify.AST_Number
    ) {
        return [expression];
    }
    if (expression instanceof uglify.AST_SymbolRef) {
        const reachingExpressionValues =
            constantInitializers.reaching_expression_values;
        const staticExpressionNodes =
            constantInitializers.static_expression_nodes;
        const currentLambda = constantInitializers.current_lambda;
        if (
            reachingExpressionValues &&
            currentLambda &&
            expression.thedef &&
            reachingExpressionValues.has(currentLambda)
        ) {
            const intervals =
                reachingExpressionValues
                    .get(currentLambda)
                    .get(expression.thedef.id) || [];
            for (let index = intervals.length - 1; index >= 0; index--) {
                const interval = intervals[index];
                if (
                    expression.start.pos >=
                        interval.assignment_end_position &&
                    expression.start.pos <
                        interval.invalidation_position
                ) {
                    return interval.expression_nodes;
                }
            }
        }
        if (
            staticExpressionNodes &&
            expression.thedef &&
            staticExpressionNodes.has(expression.thedef.id)
        ) {
            return staticExpressionNodes.get(expression.thedef.id);
        }
        const initializer = initializerFor(
            expression,
            constantInitializers,
            resolving,
            usePosition,
        );
        return initializer
            ? finiteExpressionNodes(
                  uglify,
                  initializer.expression,
                  constantInitializers,
                  initializer.resolving,
                  initializer.usePosition,
                  staticTransforms,
              )
            : null;
    }
    if (expression instanceof uglify.AST_Sub) {
        return indexedNodes(
            uglify,
            expression,
            constantInitializers,
            resolving,
            usePosition,
            staticTransforms,
        );
    }
    if (expression instanceof uglify.AST_Dot) {
        const objects = finiteExpressionNodes(
            uglify,
            expression.expression,
            constantInitializers,
            resolving,
            usePosition,
            staticTransforms,
        );
        if (!objects) {
            return null;
        }
        const selected = [];
        for (const object of objects) {
            if (!(object instanceof uglify.AST_Object)) {
                return null;
            }
            const properties = object.properties.filter(
                (property) =>
                    property instanceof uglify.AST_ObjectKeyVal &&
                    property.key === expression.property,
            );
            if (properties.length !== 1) {
                return null;
            }
            selected.push(properties[0].value);
        }
        return boundedUniqueNodes(selected);
    }
    return null;
}

function indexedNodes(
    uglify,
    expression,
    constantInitializers,
    resolving,
    usePosition,
    staticTransforms,
) {
    const collections = finiteExpressionNodes(
        uglify,
        expression.expression,
        constantInitializers,
        resolving,
        usePosition,
        staticTransforms,
    );
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
        const reachingSymbolValues =
            constantInitializers.reaching_symbol_values;
        const scopedSymbolValues =
            constantInitializers.scoped_symbol_values;
        const currentLambda = constantInitializers.current_lambda;
        if (
            reachingSymbolValues &&
            currentLambda &&
            expression.thedef &&
            reachingSymbolValues.has(currentLambda)
        ) {
            const intervals =
                reachingSymbolValues
                    .get(currentLambda)
                    .get(expression.thedef.id) || [];
            for (let index = intervals.length - 1; index >= 0; index--) {
                const interval = intervals[index];
                if (
                    expression.start.pos >=
                        interval.assignment_end_position &&
                    expression.start.pos <
                        interval.invalidation_position
                ) {
                    return interval.static_values;
                }
            }
        }
        if (
            scopedSymbolValues &&
            currentLambda &&
            expression.thedef &&
            scopedSymbolValues.has(currentLambda)
        ) {
            const scopedValues = scopedSymbolValues
                .get(currentLambda)
                .get(expression.thedef.id);
            if (
                scopedValues &&
                expression.start.pos >=
                    scopedValues.assignment_end_position &&
                expression.start.pos <
                    scopedValues.invalidation_position
            ) {
                return scopedValues.static_values;
            }
        }
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
    plainObjectEnumerationSafe = true,
    safeStaticArrayParameterFunctions = new Set(),
) {
    const source = fs.readFileSync(file, "utf8");
    const relativePath = toPosix(path.relative(rulesRoot, file));
    const ast = uglify.parse(source, { filename: relativePath });
    ast.figure_out_scope();
    const parentByNode = new WeakMap();
    ast.walk(
        new uglify.TreeWalker(function (node) {
            parentByNode.set(node, this.parent());
        }),
    );
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
    const unsafeObjectDefinitions = new Set();
    const valuePreservingSelfAssignments = [];
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
        new uglify.TreeWalker(function (node) {
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
                        node,
                        value: node.value,
                        position: node.end.endpos,
                    });
                }
            }
            if (node instanceof uglify.AST_Assign) {
                if (isExactSelfAssignment(uglify, node)) {
                    const lambda = this.find_parent(
                        uglify.AST_Lambda,
                    );
                    valuePreservingSelfAssignments.push({
                        function:
                            lambda &&
                            lambda.name &&
                            lambda.name.name
                                ? lambda.name.name
                                : "<anonymous>",
                        function_line: lambda
                            ? lambda.start.line
                            : null,
                        symbol: node.left.name,
                        assignment_line: node.start.line,
                    });
                } else {
                    markDefinitions(node.left);
                }
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
            if (
                !(initializer instanceof uglify.AST_Array) &&
                !(initializer instanceof uglify.AST_Object)
            ) {
                return;
            }
            const parent = this.parent();
            if (initializer instanceof uglify.AST_Object) {
                const isForInRead =
                    parent instanceof uglify.AST_ForIn &&
                    parent.object === node;
                const isIndexRead =
                    parent instanceof uglify.AST_Sub &&
                    parent.expression === node;
                if (!isForInRead && !isIndexRead) {
                    unsafeObjectDefinitions.add(node.thedef.id);
                }
                return;
            }
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
                !unsafeArrayDefinitions.has(definitionId) &&
                !unsafeObjectDefinitions.has(definitionId),
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
    const staticExpressionNodes = new Map();
    const finiteArrayParameterValues = [];
    constantInitializers.static_expression_nodes =
        staticExpressionNodes;
    for (const info of functionInfos.values()) {
        const key = `${relativePath}\0${info.name}`;
        const spec = STATIC_ARRAY_PARAMETER_SPECS.get(key);
        if (
            !spec ||
            !safeStaticArrayParameterFunctions.has(key) ||
            info.escaped ||
            info.calls.length === 0
        ) {
            continue;
        }
        const parameter = info.parameters[spec.parameter_index];
        if (
            !parameter ||
            !parameter.thedef ||
            parameter.name !== spec.parameter
        ) {
            continue;
        }
        const arrays = [];
        let complete = true;
        for (const call of info.calls) {
            const argument = call.args[spec.parameter_index];
            if (
                !(argument instanceof uglify.AST_Assign) ||
                argument.operator !== "=" ||
                !(argument.left instanceof
                    uglify.AST_SymbolRef) ||
                argument.left.name !== spec.named_argument ||
                !argument.left.thedef ||
                !argument.left.thedef.undeclared ||
                !(argument.right instanceof uglify.AST_Array) ||
                argument.right.elements.length === 0 ||
                argument.right.elements.some(
                    (element) =>
                        !(element instanceof uglify.AST_String),
                )
            ) {
                complete = false;
                break;
            }
            arrays.push(argument.right);
        }
        const elementCount = arrays.reduce(
            (count, array) => count + array.elements.length,
            0,
        );
        if (
            !complete ||
            arrays.length === 0 ||
            arrays.length >
                MAX_STATIC_VALUES_PER_EXPRESSION ||
            elementCount > MAX_STATIC_VALUES_PER_EXPRESSION
        ) {
            continue;
        }
        const values = boundedUniqueSorted(
            arrays.flatMap((array) =>
                array.elements.map((element) => element.value),
            ),
        );
        if (!values) {
            continue;
        }
        staticExpressionNodes.set(parameter.thedef.id, arrays);
        finiteArrayParameterValues.push({
            function: info.name,
            function_line: info.line,
            parameter: parameter.name,
            parameter_index: spec.parameter_index,
            direct_call_site_count: info.calls.length,
            array_count: arrays.length,
            element_count: elementCount,
            static_values: values,
        });
    }
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
    const scopedWrites = new Map();
    const capturedDefinitions = new Set();
    function addScopedWrite(lambda, definitionId, write) {
        if (!lambda || !definitionId) {
            return;
        }
        if (!scopedWrites.has(lambda)) {
            scopedWrites.set(lambda, new Map());
        }
        const writesByDefinition = scopedWrites.get(lambda);
        if (!writesByDefinition.has(definitionId)) {
            writesByDefinition.set(definitionId, []);
        }
        writesByDefinition.get(definitionId).push(write);
    }
    ast.walk(
        new uglify.TreeWalker(function (node) {
            if (
                node instanceof uglify.AST_SymbolRef &&
                node.thedef &&
                node.thedef.scope instanceof uglify.AST_Lambda
            ) {
                const referenceLambda = this.find_parent(
                    uglify.AST_Lambda,
                );
                if (
                    referenceLambda &&
                    referenceLambda !== node.thedef.scope
                ) {
                    capturedDefinitions.add(node.thedef.id);
                }
            }
            const lambda = this.find_parent(uglify.AST_Lambda);
            if (
                node instanceof uglify.AST_Assign &&
                !isExactSelfAssignment(uglify, node) &&
                node.left instanceof uglify.AST_SymbolRef &&
                node.left.thedef
            ) {
                addScopedWrite(lambda, node.left.thedef.id, {
                    node,
                    kind: "assign",
                    direct_top_level:
                        this.parent() instanceof
                            uglify.AST_SimpleStatement &&
                        lambda &&
                        lambda.body.includes(this.parent()),
                });
            }
            if (
                (node instanceof uglify.AST_UnaryPrefix ||
                    node instanceof uglify.AST_UnaryPostfix) &&
                (node.operator === "++" || node.operator === "--") &&
                node.expression instanceof uglify.AST_SymbolRef &&
                node.expression.thedef
            ) {
                addScopedWrite(lambda, node.expression.thedef.id, {
                    node,
                    kind: "update",
                    direct_top_level: false,
                });
            }
            if (node instanceof uglify.AST_ForIn) {
                node.init.walk(
                    new uglify.TreeWalker((symbol) => {
                        if (
                            symbol instanceof uglify.AST_Symbol &&
                            symbol.thedef
                        ) {
                            addScopedWrite(lambda, symbol.thedef.id, {
                                node,
                                kind: "for_in",
                                direct_top_level: false,
                            });
                        }
                    }),
                );
            }
        }),
    );
    const directSymbolCallsByLambda = new Map();
    ast.walk(
        new uglify.TreeWalker(function (node) {
            if (
                !(node instanceof uglify.AST_Call) ||
                !(node.expression instanceof uglify.AST_SymbolRef)
            ) {
                return;
            }
            const lambda = this.find_parent(uglify.AST_Lambda);
            if (!lambda) {
                return;
            }
            if (!directSymbolCallsByLambda.has(lambda)) {
                directSymbolCallsByLambda.set(lambda, []);
            }
            directSymbolCallsByLambda.get(lambda).push(node);
        }),
    );
    const scopedSymbolValues = new Map();
    const finiteScopedAssignments = [];
    const finiteObjectKeyIterations = [];
    constantInitializers.scoped_symbol_values = scopedSymbolValues;
    if (plainObjectEnumerationSafe) {
        ast.walk(
            new uglify.TreeWalker(function (node) {
                if (
                    !(node instanceof uglify.AST_ForIn) ||
                    !(node.init instanceof uglify.AST_Var) ||
                    node.init.definitions.length !== 1 ||
                    !(node.object instanceof
                        uglify.AST_SymbolRef) ||
                    !node.object.thedef
                ) {
                    return;
                }
                const lambda = this.find_parent(
                    uglify.AST_Lambda,
                );
                const keyDefinition = node.init.definitions[0];
                if (
                    !lambda ||
                    !keyDefinition.name ||
                    !keyDefinition.name.thedef ||
                    keyDefinition.value
                ) {
                    return;
                }
                const objectInitializer =
                    constantInitializers.get(
                        node.object.thedef.id,
                    );
                if (
                    !objectInitializer ||
                    objectInitializer.position > node.start.pos ||
                    !(objectInitializer.value instanceof
                        uglify.AST_Object)
                ) {
                    return;
                }
                const declaration = parentByNode.get(
                    initializerCandidates.get(
                        node.object.thedef.id,
                    ).node,
                );
                const statementContainer = parentByNode.get(node);
                const statements =
                    statementContainer instanceof
                    uglify.AST_BlockStatement
                        ? statementContainer.body
                        : statementContainer === lambda
                          ? lambda.body
                          : null;
                if (
                    !(declaration instanceof uglify.AST_Var) ||
                    declaration.definitions.length !== 1 ||
                    !statements ||
                    parentByNode.get(declaration) !==
                        statementContainer ||
                    statements.indexOf(declaration) < 0 ||
                    statements.indexOf(declaration) >=
                        statements.indexOf(node)
                ) {
                    return;
                }
                const properties =
                    objectInitializer.value.properties;
                if (
                    properties.length === 0 ||
                    properties.length >
                        MAX_STATIC_VALUES_PER_EXPRESSION ||
                    properties.some(
                        (property) =>
                            !(
                                property instanceof
                                    uglify.AST_ObjectKeyVal
                            ) ||
                            typeof property.key !== "string" ||
                            property.key === "__proto__" ||
                            !(
                                property.value instanceof
                                uglify.AST_String
                            ),
                    )
                ) {
                    return;
                }
                const writes =
                    scopedWrites.get(lambda) &&
                    scopedWrites
                        .get(lambda)
                        .get(keyDefinition.name.thedef.id);
                if (
                    !writes ||
                    writes.length !== 1 ||
                    writes[0].kind !== "for_in" ||
                    writes[0].node !== node
                ) {
                    return;
                }
                const values = boundedUniqueSorted(
                    properties.map((property) => property.key),
                );
                if (!values) {
                    return;
                }
                if (!scopedSymbolValues.has(lambda)) {
                    scopedSymbolValues.set(lambda, new Map());
                }
                scopedSymbolValues
                    .get(lambda)
                    .set(keyDefinition.name.thedef.id, {
                        assignment_end_position:
                            node.body.start.pos,
                        invalidation_position: node.end.endpos,
                        static_values: values,
                    });
                finiteObjectKeyIterations.push({
                    function:
                        lambda.name && lambda.name.name
                            ? lambda.name.name
                            : "<anonymous>",
                    function_line: lambda.start.line,
                    object: node.object.name,
                    key: keyDefinition.name.name,
                    loop_line: node.start.line,
                    static_values: values,
                });
            }),
        );
    }
    for (const [lambda, writesByDefinition] of scopedWrites) {
        for (const [definitionId, writes] of writesByDefinition) {
            if (writes.length !== 1) {
                continue;
            }
            const write = writes[0];
            if (
                write.kind !== "assign" ||
                write.node.operator !== "=" ||
                !write.direct_top_level ||
                !(lambda.body[0] instanceof
                    uglify.AST_SimpleStatement) ||
                lambda.body[0].body !== write.node
            ) {
                continue;
            }
            constantInitializers.current_lambda = lambda;
            const values = staticValues(
                uglify,
                write.node.right,
                constantInitializers,
                new Set(),
                write.node.start.pos,
                staticTransforms,
            );
            constantInitializers.current_lambda = null;
            if (!values) {
                continue;
            }
            const calls = directSymbolCallsByLambda.get(lambda) || [];
            const barrier = calls
                .filter(
                    (call) =>
                        call.start.pos > write.node.end.endpos,
                )
                .reduce(
                    (position, call) =>
                        Math.min(position, call.start.pos),
                    Number.POSITIVE_INFINITY,
                );
            if (!scopedSymbolValues.has(lambda)) {
                scopedSymbolValues.set(lambda, new Map());
            }
            scopedSymbolValues.get(lambda).set(definitionId, {
                assignment_end_position: write.node.end.endpos,
                invalidation_position: barrier,
                static_values: values,
            });
            finiteScopedAssignments.push({
                function:
                    lambda.name && lambda.name.name
                        ? lambda.name.name
                        : "<anonymous>",
                function_line: lambda.start.line,
                symbol: write.node.left.name,
                assignment_line: write.node.start.line,
                invalidation_line: Number.isFinite(barrier)
                    ? calls.find((call) => call.start.pos === barrier)
                          .start.line
                    : null,
                static_values: values,
            });
        }
    }
    const finiteLoopAccumulations = [];
    ast.walk(
        new uglify.TreeWalker(function (node) {
            if (!(node instanceof uglify.AST_For)) {
                return;
            }
            const lambda = this.find_parent(uglify.AST_Lambda);
            if (
                !lambda ||
                !(node.init instanceof uglify.AST_Var) ||
                node.init.definitions.length !== 1 ||
                !(node.condition instanceof uglify.AST_Binary) ||
                node.condition.operator !== "<" ||
                !(
                    node.condition.left instanceof
                    uglify.AST_SymbolRef
                ) ||
                !(
                    node.step instanceof uglify.AST_UnaryPostfix
                ) ||
                node.step.operator !== "++" ||
                !(
                    node.step.expression instanceof
                    uglify.AST_SymbolRef
                ) ||
                !(node.body instanceof uglify.AST_BlockStatement) ||
                node.body.body.length !== 1 ||
                !(
                    node.body.body[0] instanceof
                    uglify.AST_SimpleStatement
                ) ||
                !(node.body.body[0].body instanceof uglify.AST_Assign)
            ) {
                return;
            }
            const loopVariable = node.init.definitions[0];
            const append = node.body.body[0].body;
            if (
                !loopVariable.name ||
                !loopVariable.name.thedef ||
                !loopVariable.value ||
                !node.condition.left.thedef ||
                node.condition.left.thedef.id !==
                    loopVariable.name.thedef.id ||
                !node.step.expression.thedef ||
                node.step.expression.thedef.id !==
                    loopVariable.name.thedef.id ||
                append.operator !== "+=" ||
                !(append.left instanceof uglify.AST_SymbolRef) ||
                !append.left.thedef
            ) {
                return;
            }
            const targetDefinitionId = append.left.thedef.id;
            const initializer = initializerCandidates.get(
                targetDefinitionId,
            );
            const writes =
                scopedWrites.get(lambda) &&
                scopedWrites.get(lambda).get(targetDefinitionId);
            if (
                !initializer ||
                !writes ||
                writes.length !== 1 ||
                writes[0].node !== append
            ) {
                return;
            }
            const declaration = parentByNode.get(initializer.node);
            const statementContainer = parentByNode.get(node);
            const statements =
                statementContainer instanceof
                uglify.AST_BlockStatement
                    ? statementContainer.body
                    : statementContainer === lambda
                      ? lambda.body
                      : null;
            if (
                !(declaration instanceof uglify.AST_Var) ||
                declaration.definitions.length !== 1 ||
                declaration.definitions[0] !== initializer.node ||
                !statements ||
                parentByNode.get(declaration) !==
                    statementContainer
            ) {
                return;
            }
            const declarationIndex = statements.indexOf(declaration);
            if (
                declarationIndex < 0 ||
                statements[declarationIndex + 1] !== node
            ) {
                return;
            }
            constantInitializers.current_lambda = lambda;
            const startValues = staticValues(
                uglify,
                loopVariable.value,
                constantInitializers,
                new Set(),
                node.start.pos,
                staticTransforms,
            );
            const limitValues = staticValues(
                uglify,
                node.condition.right,
                constantInitializers,
                new Set(),
                node.start.pos,
                staticTransforms,
            );
            const initialValues = staticValues(
                uglify,
                initializer.value,
                constantInitializers,
                new Set(),
                node.start.pos,
                staticTransforms,
            );
            const appendValues = staticValues(
                uglify,
                append.right,
                constantInitializers,
                new Set(),
                append.start.pos,
                staticTransforms,
            );
            constantInitializers.current_lambda = null;
            if (
                !startValues ||
                startValues.length !== 1 ||
                !limitValues ||
                limitValues.length !== 1 ||
                !initialValues ||
                !appendValues ||
                initialValues.some(
                    (value) => typeof value !== "string",
                ) ||
                appendValues.some(
                    (value) => typeof value !== "string",
                )
            ) {
                return;
            }
            const start = startValues[0];
            const limit = limitValues[0];
            if (
                !Number.isSafeInteger(start) ||
                !Number.isSafeInteger(limit) ||
                start < 0 ||
                limit < start ||
                limit - start >
                    MAX_STATIC_VALUES_PER_EXPRESSION ||
                initialValues.length * appendValues.length >
                    MAX_STATIC_VALUES_PER_EXPRESSION
            ) {
                return;
            }
            const iterations = limit - start;
            const values = boundedUniqueSorted(
                initialValues.flatMap((initialValue) =>
                    appendValues.map(
                        (appendValue) =>
                            initialValue +
                            appendValue.repeat(iterations),
                    ),
                ),
            );
            if (!values) {
                return;
            }
            const calls = directSymbolCallsByLambda.get(lambda) || [];
            const barrier = calls
                .filter((call) => call.start.pos > node.end.endpos)
                .reduce(
                    (position, call) =>
                        Math.min(position, call.start.pos),
                    Number.POSITIVE_INFINITY,
                );
            if (!scopedSymbolValues.has(lambda)) {
                scopedSymbolValues.set(lambda, new Map());
            }
            scopedSymbolValues.get(lambda).set(targetDefinitionId, {
                assignment_end_position: node.end.endpos,
                invalidation_position: barrier,
                static_values: values,
            });
            finiteLoopAccumulations.push({
                function:
                    lambda.name && lambda.name.name
                        ? lambda.name.name
                        : "<anonymous>",
                function_line: lambda.start.line,
                symbol: append.left.name,
                loop_line: node.start.line,
                iterations,
                invalidation_line: Number.isFinite(barrier)
                    ? calls.find((call) => call.start.pos === barrier)
                          .start.line
                    : null,
                static_values: values,
            });
        }),
    );
    const reachingExpressionValues = new Map();
    const finiteObjectElementAssignments = [];
    constantInitializers.reaching_expression_values =
        reachingExpressionValues;
    function objectPropertyMap(object) {
        if (
            !(object instanceof uglify.AST_Object) ||
            object.properties.length === 0
        ) {
            return null;
        }
        const properties = new Map();
        for (const property of object.properties) {
            if (
                !(property instanceof uglify.AST_ObjectKeyVal) ||
                typeof property.key !== "string" ||
                property.key === "__proto__" ||
                property.key === "constructor" ||
                properties.has(property.key)
            ) {
                return null;
            }
            const value = property.value;
            const primitive =
                value instanceof uglify.AST_String ||
                value instanceof uglify.AST_Number ||
                value instanceof uglify.AST_True ||
                value instanceof uglify.AST_False ||
                value instanceof uglify.AST_Null ||
                (value instanceof uglify.AST_SymbolRef &&
                    value.name === "undefined" &&
                    value.thedef &&
                    value.thedef.undeclared);
            const stringArray =
                value instanceof uglify.AST_Array &&
                value.elements.length > 0 &&
                value.elements.every(
                    (element) =>
                        element instanceof uglify.AST_String,
                );
            if (!primitive && !stringArray) {
                return null;
            }
            properties.set(property.key, value);
        }
        return properties;
    }
    function targetObjectReadsAreSafe(
        definitionId,
        assignment,
        objectPropertyMaps,
    ) {
        function memberIsWritten(member) {
            const parent = parentByNode.get(member);
            return (
                (parent instanceof uglify.AST_Assign &&
                    parent.left === member) ||
                (parent instanceof uglify.AST_UnaryPrefix &&
                    (parent.operator === "++" ||
                        parent.operator === "--" ||
                        parent.operator === "delete")) ||
                (parent instanceof uglify.AST_UnaryPostfix &&
                    (parent.operator === "++" ||
                        parent.operator === "--"))
            );
        }
        let safe = true;
        ast.walk(
            new uglify.TreeWalker(function (node) {
                if (
                    !safe ||
                    !(node instanceof uglify.AST_SymbolRef) ||
                    !node.thedef ||
                    node.thedef.id !== definitionId
                ) {
                    return;
                }
                const parent = this.parent();
                if (
                    parent === assignment &&
                    assignment.left === node
                ) {
                    return;
                }
                if (
                    !(parent instanceof uglify.AST_Dot) ||
                    parent.expression !== node
                ) {
                    safe = false;
                    return;
                }
                const propertyValues = objectPropertyMaps.map(
                    (properties) => properties.get(parent.property),
                );
                if (propertyValues.some((value) => !value)) {
                    safe = false;
                    return;
                }
                const arrays = propertyValues.filter(
                    (value) => value instanceof uglify.AST_Array,
                );
                if (
                    arrays.length !== 0 &&
                    arrays.length !== propertyValues.length
                ) {
                    safe = false;
                    return;
                }
                const propertyParent = parentByNode.get(parent);
                if (arrays.length !== 0) {
                    const isLengthRead =
                        propertyParent instanceof uglify.AST_Dot &&
                        propertyParent.expression === parent &&
                        propertyParent.property === "length";
                    const isIndexRead =
                        propertyParent instanceof uglify.AST_Sub &&
                        propertyParent.expression === parent;
                    if (!isLengthRead && !isIndexRead) {
                        safe = false;
                        return;
                    }
                    if (memberIsWritten(propertyParent)) {
                        safe = false;
                    }
                    return;
                }
                if (memberIsWritten(parent)) {
                    safe = false;
                }
            }),
        );
        return safe;
    }
    function sourceReferencesAreExact(
        definitionId,
        conditionReference,
        elementReference,
    ) {
        const expected = new Set([
            conditionReference,
            elementReference,
        ]);
        let safe = true;
        ast.walk(
            new uglify.TreeWalker(function (node) {
                if (
                    !safe ||
                    !(node instanceof uglify.AST_SymbolRef) ||
                    !node.thedef ||
                    node.thedef.id !== definitionId
                ) {
                    return;
                }
                if (!expected.delete(node)) {
                    safe = false;
                }
            }),
        );
        return safe && expected.size === 0;
    }
    ast.walk(
        new uglify.TreeWalker(function (node) {
            if (
                !(node instanceof uglify.AST_For) ||
                !(node.init instanceof uglify.AST_Var) ||
                node.init.definitions.length !== 1 ||
                !(node.condition instanceof uglify.AST_Binary) ||
                node.condition.operator !== "<" ||
                !(
                    node.condition.left instanceof
                    uglify.AST_SymbolRef
                ) ||
                !(node.condition.right instanceof uglify.AST_Dot) ||
                node.condition.right.property !== "length" ||
                !(
                    node.condition.right.expression instanceof
                    uglify.AST_SymbolRef
                ) ||
                !(
                    node.step instanceof uglify.AST_UnaryPostfix
                ) ||
                node.step.operator !== "++" ||
                !(
                    node.step.expression instanceof
                    uglify.AST_SymbolRef
                ) ||
                !(node.body instanceof uglify.AST_BlockStatement) ||
                node.body.body.length === 0 ||
                !(
                    node.body.body[0] instanceof
                    uglify.AST_SimpleStatement
                ) ||
                !(
                    node.body.body[0].body instanceof
                    uglify.AST_Assign
                )
            ) {
                return;
            }
            const lambda = this.find_parent(uglify.AST_Lambda);
            const loopVariable = node.init.definitions[0];
            const assignment = node.body.body[0].body;
            if (
                !lambda ||
                !loopVariable.name ||
                !loopVariable.name.thedef ||
                !(loopVariable.value instanceof
                    uglify.AST_Number) ||
                loopVariable.value.value !== 0 ||
                !node.condition.left.thedef ||
                node.condition.left.thedef.id !==
                    loopVariable.name.thedef.id ||
                !node.step.expression.thedef ||
                node.step.expression.thedef.id !==
                    loopVariable.name.thedef.id ||
                !node.condition.right.expression.thedef ||
                assignment.operator !== "=" ||
                !(assignment.left instanceof
                    uglify.AST_SymbolRef) ||
                !assignment.left.thedef ||
                assignment.left.thedef.scope !== lambda ||
                capturedDefinitions.has(assignment.left.thedef.id) ||
                !(assignment.right instanceof uglify.AST_Sub) ||
                !(
                    assignment.right.expression instanceof
                    uglify.AST_SymbolRef
                ) ||
                !assignment.right.expression.thedef ||
                assignment.right.expression.thedef.id !==
                    node.condition.right.expression.thedef.id ||
                !(
                    assignment.right.property instanceof
                    uglify.AST_SymbolRef
                ) ||
                !assignment.right.property.thedef ||
                assignment.right.property.thedef.id !==
                    loopVariable.name.thedef.id
            ) {
                return;
            }
            const sourceDefinitionId =
                assignment.right.expression.thedef.id;
            const sourceInitializer =
                constantInitializers.get(sourceDefinitionId);
            if (
                !sourceInitializer ||
                sourceInitializer.position > node.start.pos ||
                !(sourceInitializer.value instanceof
                    uglify.AST_Array) ||
                sourceInitializer.value.elements.length === 0 ||
                sourceInitializer.value.elements.length >
                    MAX_STATIC_VALUES_PER_EXPRESSION ||
                sourceInitializer.value.elements.some(
                    (element) =>
                        !(element instanceof uglify.AST_Object),
                ) ||
                !sourceReferencesAreExact(
                    sourceDefinitionId,
                    node.condition.right.expression,
                    assignment.right.expression,
                )
            ) {
                return;
            }
            const declaration = parentByNode.get(
                initializerCandidates.get(sourceDefinitionId).node,
            );
            const statementContainer = parentByNode.get(node);
            const statements =
                statementContainer instanceof
                uglify.AST_BlockStatement
                    ? statementContainer.body
                    : statementContainer === lambda
                      ? lambda.body
                      : null;
            if (
                !(declaration instanceof uglify.AST_Var) ||
                declaration.definitions.length !== 1 ||
                !statements ||
                parentByNode.get(declaration) !==
                    statementContainer ||
                statements.indexOf(declaration) < 0 ||
                statements[statements.indexOf(declaration) + 1] !==
                    node
            ) {
                return;
            }
            const targetDefinitionId = assignment.left.thedef.id;
            const writes =
                scopedWrites.get(lambda) &&
                scopedWrites.get(lambda).get(targetDefinitionId);
            const loopVariableWrites =
                (scopedWrites.get(lambda) &&
                    scopedWrites
                        .get(lambda)
                        .get(loopVariable.name.thedef.id)) ||
                [];
            const loopVariableWritesInLoop =
                loopVariableWrites.filter(
                    (write) =>
                        write.node.start.pos >= node.start.pos &&
                        write.node.end.endpos <= node.end.endpos,
                );
            if (
                !writes ||
                writes.length !== 1 ||
                writes[0].kind !== "assign" ||
                writes[0].node !== assignment ||
                loopVariableWritesInLoop.length !== 1 ||
                loopVariableWritesInLoop[0].kind !== "update" ||
                loopVariableWritesInLoop[0].node !== node.step
            ) {
                return;
            }
            const objectPropertyMaps =
                sourceInitializer.value.elements.map(
                    objectPropertyMap,
                );
            if (
                objectPropertyMaps.some(
                    (properties) => !properties,
                ) ||
                !targetObjectReadsAreSafe(
                    targetDefinitionId,
                    assignment,
                    objectPropertyMaps,
                )
            ) {
                return;
            }
            if (!reachingExpressionValues.has(lambda)) {
                reachingExpressionValues.set(lambda, new Map());
            }
            reachingExpressionValues
                .get(lambda)
                .set(targetDefinitionId, [
                    {
                        assignment_end_position:
                            assignment.end.endpos,
                        invalidation_position: node.end.endpos,
                        expression_nodes:
                            sourceInitializer.value.elements,
                    },
                ]);
            finiteObjectElementAssignments.push({
                function:
                    lambda.name && lambda.name.name
                        ? lambda.name.name
                        : "<anonymous>",
                function_line: lambda.start.line,
                source: assignment.right.expression.name,
                target: assignment.left.name,
                loop_index: loopVariable.name.name,
                loop_line: node.start.line,
                assignment_line: assignment.start.line,
                element_count:
                    sourceInitializer.value.elements.length,
                invalidation_line: node.end.line,
            });
        }),
    );
    const reachingSymbolValues = new Map();
    const finiteAdjacentAssignments = [];
    constantInitializers.reaching_symbol_values =
        reachingSymbolValues;
    ast.walk(
        new uglify.TreeWalker(function (node) {
            if (
                !(node instanceof uglify.AST_Assign) ||
                node.operator !== "=" ||
                isExactSelfAssignment(uglify, node) ||
                !(node.left instanceof uglify.AST_SymbolRef) ||
                !node.left.thedef ||
                !(this.parent() instanceof
                    uglify.AST_SimpleStatement)
            ) {
                return;
            }
            const lambda = this.find_parent(uglify.AST_Lambda);
            if (
                !lambda ||
                node.left.thedef.scope !== lambda ||
                capturedDefinitions.has(node.left.thedef.id)
            ) {
                return;
            }
            const statement = this.parent();
            const statementContainer = parentByNode.get(statement);
            const statements =
                statementContainer instanceof
                uglify.AST_BlockStatement
                    ? statementContainer.body
                    : statementContainer === lambda
                      ? lambda.body
                      : null;
            if (!statements) {
                return;
            }
            const statementIndex = statements.indexOf(statement);
            const nextStatement = statements[statementIndex + 1];
            if (statementIndex < 0 || !nextStatement) {
                return;
            }
            let unsafeCall = false;
            let targetWrite = false;
            const signatureUseLines = [];
            nextStatement.walk(
                new uglify.TreeWalker(function (candidate) {
                    if (candidate instanceof uglify.AST_Lambda) {
                        return true;
                    }
                    if (
                        candidate instanceof uglify.AST_Assign &&
                        candidate.left instanceof
                            uglify.AST_SymbolRef &&
                        candidate.left.thedef &&
                        candidate.left.thedef.id ===
                            node.left.thedef.id
                    ) {
                        targetWrite = true;
                    }
                    if (
                        (candidate instanceof
                            uglify.AST_UnaryPrefix ||
                            candidate instanceof
                                uglify.AST_UnaryPostfix) &&
                        (candidate.operator === "++" ||
                            candidate.operator === "--") &&
                        candidate.expression instanceof
                            uglify.AST_SymbolRef &&
                        candidate.expression.thedef &&
                        candidate.expression.thedef.id ===
                            node.left.thedef.id
                    ) {
                        targetWrite = true;
                    }
                    if (!(candidate instanceof uglify.AST_Call)) {
                        return;
                    }
                    const member = memberName(
                        uglify,
                        candidate.expression,
                    );
                    const root =
                        member &&
                        receiverRoot(uglify, member.receiver);
                    if (!root || !KNOWN_HOST_RECEIVERS.has(root)) {
                        unsafeCall = true;
                        return;
                    }
                    const argumentIndex =
                        METHOD_ARGUMENT_INDEX.get(member.method);
                    const argument =
                        argumentIndex === undefined
                            ? null
                            : candidate.args[argumentIndex];
                    if (
                        argument instanceof
                            uglify.AST_SymbolRef &&
                        argument.thedef &&
                        argument.thedef.id ===
                            node.left.thedef.id
                    ) {
                        signatureUseLines.push(
                            candidate.start.line,
                        );
                    }
                }),
            );
            if (
                unsafeCall ||
                targetWrite ||
                signatureUseLines.length === 0
            ) {
                return;
            }
            constantInitializers.current_lambda = lambda;
            const values = staticValues(
                uglify,
                node.right,
                constantInitializers,
                new Set(),
                node.start.pos,
                staticTransforms,
            );
            constantInitializers.current_lambda = null;
            if (
                !values ||
                values.some((value) => typeof value !== "string")
            ) {
                return;
            }
            if (!reachingSymbolValues.has(lambda)) {
                reachingSymbolValues.set(lambda, new Map());
            }
            const byDefinition = reachingSymbolValues.get(lambda);
            if (!byDefinition.has(node.left.thedef.id)) {
                byDefinition.set(node.left.thedef.id, []);
            }
            byDefinition.get(node.left.thedef.id).push({
                assignment_end_position: node.end.endpos,
                invalidation_position:
                    nextStatement.end.endpos,
                static_values: values,
            });
            finiteAdjacentAssignments.push({
                function:
                    lambda.name && lambda.name.name
                        ? lambda.name.name
                        : "<anonymous>",
                function_line: lambda.start.line,
                symbol: node.left.name,
                assignment_line: node.start.line,
                use_lines: signatureUseLines,
                invalidation_line: nextStatement.end.line,
                static_values: values,
            });
        }),
    );
    const calls = [];
    ast.walk(
        new uglify.TreeWalker(function (node) {
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
            constantInitializers.current_lambda =
                this.find_parent(uglify.AST_Lambda);
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
            constantInitializers.current_lambda = null;
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
        value_preserving_self_assignments:
            valuePreservingSelfAssignments,
        finite_parameter_values: [...finiteParameterValues.values()],
        finite_array_parameter_values: finiteArrayParameterValues,
        finite_scoped_assignments: finiteScopedAssignments,
        finite_object_key_iterations: finiteObjectKeyIterations,
        finite_loop_accumulations: finiteLoopAccumulations,
        finite_object_element_assignments:
            finiteObjectElementAssignments,
        finite_adjacent_assignments: finiteAdjacentAssignments,
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

function auditStaticArrayParameterFunctions(
    uglify,
    rulesRoot,
    ruleFiles,
) {
    const specNames = new Set(
        [...STATIC_ARRAY_PARAMETER_SPECS.keys()].map(
            (key) => key.split("\0")[1],
        ),
    );
    const verifiedDefinitions = [];
    const unsafeReferences = [];
    for (const file of ruleFiles) {
        const source = fs.readFileSync(file, "utf8");
        const relativePath = toPosix(path.relative(rulesRoot, file));
        const ast = uglify.parse(source, { filename: relativePath });
        ast.figure_out_scope();
        const verifiedByDefinitionId = new Map();
        ast.walk(
            new uglify.TreeWalker(function (node) {
                if (
                    !(node instanceof uglify.AST_Defun) ||
                    !node.name ||
                    !node.name.thedef ||
                    !specNames.has(node.name.name) ||
                    this.find_parent(uglify.AST_Lambda)
                ) {
                    return;
                }
                const key = `${relativePath}\0${node.name.name}`;
                const spec = STATIC_ARRAY_PARAMETER_SPECS.get(key);
                const sourceSha256 = sha256Bytes(
                    Buffer.from(sourceSlice(source, node), "utf8"),
                );
                if (!spec || sourceSha256 !== spec.sha256) {
                    unsafeReferences.push({
                        path: relativePath,
                        line: node.start.line,
                        name: node.name.name,
                        kind: spec
                            ? "source hash mismatch"
                            : "unexpected definition",
                        source_sha256: sourceSha256,
                        expected_source_sha256: spec
                            ? spec.sha256
                            : null,
                    });
                    return;
                }
                verifiedByDefinitionId.set(node.name.thedef.id, key);
                verifiedDefinitions.push({
                    path: relativePath,
                    name: node.name.name,
                    line: node.start.line,
                    source_sha256: sourceSha256,
                    parameter: spec.parameter,
                    parameter_index: spec.parameter_index,
                });
            }),
        );
        ast.walk(
            new uglify.TreeWalker(function (node) {
                if (
                    !(node instanceof uglify.AST_SymbolRef) ||
                    !specNames.has(node.name)
                ) {
                    return;
                }
                const parent = this.parent();
                const isVerifiedDirectCall =
                    parent instanceof uglify.AST_Call &&
                    parent.expression === node &&
                    node.thedef &&
                    verifiedByDefinitionId.has(node.thedef.id);
                if (!isVerifiedDirectCall) {
                    unsafeReferences.push({
                        path: relativePath,
                        line: node.start.line,
                        name: node.name,
                        kind: "non-local or non-direct reference",
                        source_sha256: null,
                        expected_source_sha256: null,
                    });
                }
            }),
        );
    }
    const unsafeNames = new Set(
        unsafeReferences.map((reference) => reference.name),
    );
    const safeDefinitions = verifiedDefinitions.filter(
        (definition) => !unsafeNames.has(definition.name),
    );
    return {
        safe_keys: new Set(
            safeDefinitions.map(
                (definition) =>
                    `${definition.path}\0${definition.name}`,
            ),
        ),
        evidence: {
            configured_spec_count:
                STATIC_ARRAY_PARAMETER_SPECS.size,
            verified_definition_count:
                verifiedDefinitions.length,
            safe_definition_count: safeDefinitions.length,
            unsafe_reference_count: unsafeReferences.length,
            verified_definitions: verifiedDefinitions,
            unsafe_references: unsafeReferences,
            safety_contract:
                "configured top-level helpers match path, name, and source hash; every same-name reference in db/db_extra is a direct call bound to a verified definition in the same evaluated rule",
        },
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

function auditPlainObjectEnumeration(uglify, rulesRoot, ruleFiles) {
    const unsafeReferences = [];
    let objectReferenceCount = 0;
    let safeHasOwnPropertyCallCount = 0;
    for (const file of ruleFiles) {
        const relativePath = toPosix(
            path.relative(rulesRoot, file),
        );
        const source = fs.readFileSync(file, "utf8");
        const ast = uglify.parse(source, {
            filename: relativePath,
        });
        ast.figure_out_scope();
        const parentByNode = new WeakMap();
        ast.walk(
            new uglify.TreeWalker(function (node) {
                parentByNode.set(node, this.parent());
            }),
        );
        ast.walk(
            new uglify.TreeWalker(function (node) {
                if (
                    node instanceof uglify.AST_SymbolRef &&
                    node.name === "Object"
                ) {
                    objectReferenceCount += 1;
                    const prototype = parentByNode.get(node);
                    const hasOwnProperty =
                        prototype &&
                        parentByNode.get(prototype);
                    const callProperty =
                        hasOwnProperty &&
                        parentByNode.get(hasOwnProperty);
                    const call =
                        callProperty &&
                        parentByNode.get(callProperty);
                    const isSafeHasOwnPropertyCall =
                        node.thedef &&
                        node.thedef.undeclared &&
                        node.thedef.global &&
                        prototype instanceof uglify.AST_Dot &&
                        prototype.expression === node &&
                        prototype.property === "prototype" &&
                        hasOwnProperty instanceof
                            uglify.AST_Dot &&
                        hasOwnProperty.expression === prototype &&
                        hasOwnProperty.property ===
                            "hasOwnProperty" &&
                        callProperty instanceof uglify.AST_Dot &&
                        callProperty.expression ===
                            hasOwnProperty &&
                        callProperty.property === "call" &&
                        call instanceof uglify.AST_Call &&
                        call.expression === callProperty;
                    if (isSafeHasOwnPropertyCall) {
                        safeHasOwnPropertyCallCount += 1;
                    } else {
                        unsafeReferences.push({
                            path: relativePath,
                            line: node.start.line,
                            kind: "Object reference",
                        });
                    }
                }
                if (
                    node instanceof uglify.AST_SymbolRef &&
                    (node.name === "globalThis" ||
                        node.name === "eval" ||
                        node.name === "Function")
                ) {
                    unsafeReferences.push({
                        path: relativePath,
                        line: node.start.line,
                        kind: `${node.name} reference`,
                    });
                }
                if (
                    node instanceof uglify.AST_Dot &&
                    (node.property === "__proto__" ||
                        node.property === "constructor")
                ) {
                    unsafeReferences.push({
                        path: relativePath,
                        line: node.start.line,
                        kind: `${node.property} property`,
                    });
                }
                if (
                    node instanceof uglify.AST_Sub &&
                    node.property instanceof uglify.AST_String &&
                    (node.property.value === "__proto__" ||
                        node.property.value === "constructor")
                ) {
                    unsafeReferences.push({
                        path: relativePath,
                        line: node.start.line,
                        kind: `${node.property.value} property`,
                    });
                }
            }),
        );
    }
    return {
        safe: unsafeReferences.length === 0,
        evidence: {
            object_reference_count: objectReferenceCount,
            safe_has_own_property_call_count:
                safeHasOwnPropertyCallCount,
            unsafe_reference_count: unsafeReferences.length,
            unsafe_references: unsafeReferences,
            safety_contract:
                "all Object references resolve to the undeclared global built-in and are direct Object.prototype.hasOwnProperty.call uses, with no globalThis/eval/Function or __proto__/constructor access in db/db_extra",
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
    const staticArrayParameterFunctionAudit =
        auditStaticArrayParameterFunctions(
            uglify,
            rulesRoot,
            ruleFiles,
        );
    const plainObjectEnumerationAudit =
        auditPlainObjectEnumeration(
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
            plainObjectEnumerationAudit.safe,
            staticArrayParameterFunctionAudit.safe_keys,
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
        static_array_parameter_function_audit:
            staticArrayParameterFunctionAudit.evidence,
        plain_object_enumeration_audit:
            plainObjectEnumerationAudit.evidence,
        verified_static_transforms: fileResults.flatMap(
            (result) => result.verified_static_transforms,
        ),
        value_preserving_self_assignments: fileResults.flatMap(
            (result) =>
                result.value_preserving_self_assignments.map(
                    (item) => ({
                        path: result.path,
                        ...item,
                    }),
                ),
        ),
        finite_parameter_values: fileResults.flatMap((result) =>
            result.finite_parameter_values.map((item) => ({
                path: result.path,
                ...item,
            })),
        ),
        finite_array_parameter_values: fileResults.flatMap((result) =>
            result.finite_array_parameter_values.map((item) => ({
                path: result.path,
                ...item,
            })),
        ),
        finite_scoped_assignments: fileResults.flatMap((result) =>
            result.finite_scoped_assignments.map((item) => ({
                path: result.path,
                ...item,
            })),
        ),
        finite_object_key_iterations: fileResults.flatMap((result) =>
            result.finite_object_key_iterations.map((item) => ({
                path: result.path,
                ...item,
            })),
        ),
        finite_loop_accumulations: fileResults.flatMap((result) =>
            result.finite_loop_accumulations.map((item) => ({
                path: result.path,
                ...item,
            })),
        ),
        finite_object_element_assignments: fileResults.flatMap(
            (result) =>
                result.finite_object_element_assignments.map(
                    (item) => ({
                        path: result.path,
                        ...item,
                    }),
                ),
        ),
        finite_adjacent_assignments: fileResults.flatMap((result) =>
            result.finite_adjacent_assignments.map((item) => ({
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
            "an exact function-local x = x assignment is treated as value preserving; top-level, cross-symbol, and compound assignments remain mutations",
            "function-scoped assignment values require one direct first-statement write and expire at the first direct symbol call",
            "for-in keys are enumerated only for same-block non-escaping string-valued object literals under a corpus-wide plain-object prototype safety audit",
            "loop accumulation requires an adjacent initializer and canonical finite for-loop with one string += body",
            "an uncaptured assignment target with a static string value reaches only an immediately following statement containing a known-host signature use and no unknown call or target write",
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
