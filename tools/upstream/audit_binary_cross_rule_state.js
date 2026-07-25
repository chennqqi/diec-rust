#!/usr/bin/env node
"use strict";

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const UPSTREAM_COMMIT = "74eaf505c250ab47e709024e9dc41657cd8f2254";
const RULES_COMMIT = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6";
const ORDER_SHA256 =
  "27138d68ed788dd2609b7c533fecf540593fa2e4ddb7195adc26b1a9ff0e1ff3";

function fail(message) {
  throw new Error(message);
}

function sha256(data) {
  return crypto.createHash("sha256").update(data).digest("hex");
}

function classifyReference(node, parent) {
  if (parent && parent.TYPE === "Assign" && parent.left === node) {
    return parent.operator === "=" ? "write" : "read_write";
  }
  if (
    parent &&
    (parent.TYPE === "UnaryPrefix" || parent.TYPE === "UnaryPostfix") &&
    (parent.operator === "++" || parent.operator === "--")
  ) {
    return "read_write";
  }
  return "read";
}

function main(argv) {
  if (argv.length !== 5) {
    fail(
      "usage: audit_binary_cross_rule_state.js " +
        "<db-root> <order-json> <uglify-js-module> <output-json>",
    );
  }
  const [dbRoot, orderPath, uglifyModule, outputPath] = argv.slice(1);
  const UglifyJS = require(path.resolve(uglifyModule));
  const orderBytes = fs.readFileSync(orderPath);
  const orderDocument = JSON.parse(orderBytes);
  if (orderDocument.upstream_commit !== UPSTREAM_COMMIT) {
    fail("Binary order upstream commit mismatch");
  }
  if (orderDocument.rules_commit !== RULES_COMMIT) {
    fail("Binary order rules commit mismatch");
  }
  if (orderDocument.order_sha256 !== ORDER_SHA256) {
    fail("Binary order SHA-256 mismatch");
  }

  const packagePath = path.join(path.resolve(uglifyModule), "package.json");
  const packageBytes = fs.readFileSync(packagePath);
  const packageDocument = JSON.parse(packageBytes);
  if (packageDocument.version !== "3.19.3") {
    fail(`unexpected UglifyJS version: ${packageDocument.version}`);
  }

  const providers = new Map();
  const files = [];
  const dependencies = [];
  for (let index = 0; index < orderDocument.order.length; index += 1) {
    const name = orderDocument.order[index];
    if (path.basename(name) !== name) {
      fail(`unsafe Binary rule name: ${name}`);
    }
    const rulePath = path.join(dbRoot, "Binary", name);
    const source = fs.readFileSync(rulePath);
    let ast;
    try {
      ast = UglifyJS.parse(source.toString("utf8"), { filename: name });
      ast.figure_out_scope();
    } catch (error) {
      fail(`cannot parse ${name}: ${error.message}`);
    }

    const persistentDeclarations = [];
    const lexicalDeclarations = [];
    ast.variables.each((definition, symbolName) => {
      const kinds = [...new Set(definition.orig.map((node) => node.TYPE))].sort();
      const record = { name: symbolName, kinds };
      if (kinds.some((kind) => kind === "SymbolVar" || kind === "SymbolDefun")) {
        persistentDeclarations.push(record);
      } else {
        lexicalDeclarations.push(record);
      }
    });
    persistentDeclarations.sort((left, right) => left.name.localeCompare(right.name));
    lexicalDeclarations.sort((left, right) => left.name.localeCompare(right.name));

    const globalAccess = new Map();
    ast.walk(
      new UglifyJS.TreeWalker(function visit(node) {
        if (!(node instanceof UglifyJS.AST_SymbolRef) || !ast.globals.has(node.name)) {
          return;
        }
        const kind = classifyReference(node, this.parent());
        if (!globalAccess.has(node.name)) {
          globalAccess.set(node.name, new Set());
        }
        globalAccess.get(node.name).add(kind);
      }),
    );

    const accesses = [...globalAccess.entries()]
      .map(([symbolName, kinds]) => ({
        name: symbolName,
        kinds: [...kinds].sort(),
      }))
      .sort((left, right) => left.name.localeCompare(right.name));
    for (const access of accesses) {
      const provider = providers.get(access.name);
      if (provider) {
        dependencies.push({
          name: access.name,
          provider_index: provider.index,
          provider_rule: provider.rule,
          provider_kind: provider.kind,
          consumer_index: index,
          consumer_rule: name,
          access_kinds: access.kinds,
        });
      }
    }

    for (const declaration of persistentDeclarations) {
      providers.set(declaration.name, {
        index,
        rule: name,
        kind: "var_or_function_declaration",
      });
    }
    for (const access of accesses) {
      if (access.kinds.includes("write") || access.kinds.includes("read_write")) {
        providers.set(access.name, {
          index,
          rule: name,
          kind: "implicit_or_global_write",
        });
      }
    }
    files.push({
      index,
      name,
      bytes: source.length,
      sha256: sha256(source),
      persistent_declarations: persistentDeclarations,
      lexical_declarations: lexicalDeclarations,
      global_accesses: accesses,
    });
  }

  const report = {
    schema_version: 1,
    generator: "tools/upstream/audit_binary_cross_rule_state.js",
    method:
      "UglifyJS scope analysis; candidate dependency means a later rule has an " +
      "unresolved global access to a name previously provided by a top-level " +
      "var/function declaration or global write",
    limitations: [
      "static candidate analysis does not prove the access executes",
      "dynamic property names and eval-generated bindings are not resolved",
      "init/include-provided names are outside the cross-rule provider set",
    ],
    upstream_commit: UPSTREAM_COMMIT,
    rules_commit: RULES_COMMIT,
    order_manifest: "docs/research/data/binary-rule-order-linux-qt5.json",
    order_manifest_sha256: sha256(orderBytes),
    order_sha256: ORDER_SHA256,
    parser: {
      name: "uglify-js",
      version: packageDocument.version,
      license: packageDocument.license,
      package_json_sha256: sha256(packageBytes),
      source: "fixed upstream bundled node_modules",
    },
    file_count: files.length,
    analyzed_source_bytes: files.reduce((total, file) => total + file.bytes, 0),
    persistent_declaration_count: files.reduce(
      (total, file) => total + file.persistent_declarations.length,
      0,
    ),
    lexical_declaration_count: files.reduce(
      (total, file) => total + file.lexical_declarations.length,
      0,
    ),
    distinct_global_access_count: files.reduce(
      (total, file) => total + file.global_accesses.length,
      0,
    ),
    prior_state_access_candidate_count: dependencies.length,
    wrapper_loss_candidate_count: dependencies.filter(
      (dependency) =>
        dependency.provider_kind === "var_or_function_declaration",
    ).length,
    wrapper_loss_candidates: dependencies.filter(
      (dependency) =>
        dependency.provider_kind === "var_or_function_declaration",
    ),
  };
  fs.writeFileSync(outputPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
}

main(process.argv.slice(1));
