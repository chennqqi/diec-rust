//! `xtask` is the diec-rust build/sync/oracle/corpus/release tooling binary.
//!
//! It is not part of the runtime dependency graph and must not be depended on
//! by any runtime crate. The first implemented subcommand is `check-deps`,
//! which enforces the workspace dependency DAG defined in
//! `docs/design/architecture.md` section 6.

#![forbid(unsafe_code)]

use std::collections::{BTreeMap, BTreeSet};
use std::process::{Command, ExitCode};

const RUNTIME_CRATES: &[&str] = &[
    "diec-core",
    "diec-formats",
    "diec-rules",
    "diec-engine",
    "diec-output",
    "diec-cli",
    "diec-ffi",
];

/// Allowed workspace dependencies for each runtime crate, mirroring
/// `docs/design/architecture.md` section 5/6. Any edge not listed here is a
/// violation.
fn allowed_deps() -> BTreeMap<&'static str, BTreeSet<&'static str>> {
    let mut m: BTreeMap<&'static str, BTreeSet<&'static str>> = BTreeMap::new();
    m.insert("diec-core", BTreeSet::new());
    m.insert("diec-formats", ["diec-core"].into_iter().collect());
    m.insert("diec-rules", ["diec-core"].into_iter().collect());
    m.insert(
        "diec-engine",
        ["diec-core", "diec-formats", "diec-rules"]
            .into_iter()
            .collect(),
    );
    m.insert("diec-output", ["diec-core"].into_iter().collect());
    m.insert(
        "diec-cli",
        ["diec-engine", "diec-output"].into_iter().collect(),
    );
    m.insert(
        "diec-ffi",
        ["diec-engine", "diec-output"].into_iter().collect(),
    );
    m
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().collect();
    let cmd = args.get(1).map(String::as_str).unwrap_or("");
    match cmd {
        "check-deps" => check_deps(),
        "" | "help" | "-h" | "--help" => {
            eprintln!("xtask <check-deps>");
            ExitCode::SUCCESS
        }
        other => {
            eprintln!("unknown xtask command: {other}");
            ExitCode::from(2)
        }
    }
}

/// Run `cargo metadata --no-deps`, build the workspace-internal dependency
/// graph and verify it against the allowed DAG.
fn check_deps() -> ExitCode {
    let output = Command::new("cargo")
        .args(["metadata", "--format-version", "1", "--no-deps"])
        .output();
    let output = match output {
        Ok(o) if o.status.success() => o.stdout,
        Ok(o) => {
            eprintln!(
                "cargo metadata failed: {}",
                String::from_utf8_lossy(&o.stderr)
            );
            return ExitCode::from(3);
        }
        Err(e) => {
            eprintln!("failed to run cargo metadata: {e}");
            return ExitCode::from(3);
        }
    };

    let json: serde_json::Value = match serde_json::from_slice(&output) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("failed to parse cargo metadata: {e}");
            return ExitCode::from(3);
        }
    };

    let members: BTreeSet<String> = json["workspace_members"]
        .as_array()
        .into_iter()
        .flatten()
        .filter_map(|v| v.as_str().map(String::from))
        .collect();

    let packages = json["packages"]
        .as_array()
        .into_iter()
        .flatten()
        .filter(|p| {
            p["name"]
                .as_str()
                .map(|n| members.iter().any(|m| m.starts_with(n)))
                .unwrap_or(false)
        });

    // Map crate name -> set of workspace-internal dependency names.
    let mut graph: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    for p in packages {
        let name = match p["name"].as_str() {
            Some(n) => n.to_string(),
            None => continue,
        };
        let mut deps: BTreeSet<String> = BTreeSet::new();
        if let Some(arr) = p["dependencies"].as_array() {
            for d in arr {
                if let Some(dname) = d["name"].as_str()
                    && (dname.starts_with("diec-") || dname == "xtask")
                {
                    deps.insert(dname.to_string());
                }
            }
        }
        graph.insert(name, deps);
    }

    let allowed = allowed_deps();
    let mut violations = 0usize;

    for &crate_name in RUNTIME_CRATES.iter().chain(std::iter::once(&"xtask")) {
        let actual = graph.get(crate_name).cloned().unwrap_or_default();
        let allowed_for: BTreeSet<&str> = if crate_name == "xtask" {
            BTreeSet::new()
        } else {
            allowed
                .get(crate_name)
                .cloned()
                .unwrap_or_else(|| panic!("no allowed-deps entry for {crate_name}"))
                .into_iter()
                .collect()
        };

        // Forbidden edges: actual deps not in allowed set.
        for dep in &actual {
            if !allowed_for.contains(dep.as_str()) {
                eprintln!(
                    "dependency violation: {crate_name} depends on {dep}, which is not allowed"
                );
                violations += 1;
            }
        }
        // Missing required edges are not enforced here; architecture only
        // forbids edges, it does not require every allowed edge to exist.
    }

    // No runtime crate may depend on xtask; xtask may not depend on runtime
    // crates. Covered above by empty allowed set for xtask and xtask not being
    // in any allowed set.

    if violations == 0 {
        println!("check-deps: workspace dependency DAG OK");
        ExitCode::SUCCESS
    } else {
        eprintln!("check-deps: {violations} violation(s)");
        ExitCode::from(1)
    }
}
