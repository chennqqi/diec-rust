use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::ExitCode;
use std::sync::Arc;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::Instant;

use rquickjs::{CatchResultExt, Context, Function, Runtime, context::EvalOptions};
use serde_json::json;

const HOST_SHIM: &[u8] = br#"
    var included = [];
    function meta(type, name) {
        globalThis.metaType = type;
        globalThis.metaName = name;
    }
    function includeScript(name) { included.push(name); }
    var __hostStub;
    __hostStub = new Proxy(function () { return __hostStub; }, {
        apply: function () { return __hostStub; },
        get: function (_target, property) {
            if (property === "length") return 0;
            if (property === Symbol.toPrimitive) return function () { return 0; };
            return __hostStub;
        },
        set: function () { return true; }
    });
    var APK = __hostStub, Amiga = __hostStub, Archive = __hostStub;
    var AtariST = __hostStub, Binary = __hostStub, CFBF = __hostStub;
    var COM = __hostStub, DEX = __hostStub, DOS16M = __hostStub;
    var DOS4G = __hostStub, ELF = __hostStub, IPA = __hostStub;
    var ISO9660 = __hostStub, Image = __hostStub, JAR = __hostStub;
    var JavaClass = __hostStub, Jpeg = __hostStub, LE = __hostStub;
    var LX = __hostStub, MACH = __hostStub, MACHOFAT = __hostStub;
    var MSDOS = __hostStub, NE = __hostStub, NPM = __hostStub;
    var PDF = __hostStub, PE = __hostStub, PNG = __hostStub;
    var PYC = __hostStub, RAR = __hostStub, ZIP = __hostStub;
    var bBorlandC = 0;
"#;

const NINTENDO_RULE_SUFFIX: &str = "Binary/format_bin.Nintendo-certified-file.1.sg";
const NINTENDO_RULE_BYTES: usize = 1_994;
const NINTENDO_RULE_SHA256: &str =
    "1f7485b8b0c9c211932fdcc31529ea37588c176e46a1ff06230fc376df5ad0f5";
const NINTENDO_VAR_DECLARATION: &[u8] = b"        var tp, e;";
const NINTENDO_COMPAT_DECLARATION: &[u8] = b"        var     e;";

fn collect_rule_files(root: &Path, output: &mut Vec<PathBuf>) -> Result<(), String> {
    let entries =
        fs::read_dir(root).map_err(|error| format!("cannot read {}: {error}", root.display()))?;
    for entry in entries {
        let entry =
            entry.map_err(|error| format!("cannot enumerate {}: {error}", root.display()))?;
        let path = entry.path();
        let file_type = entry
            .file_type()
            .map_err(|error| format!("cannot inspect {}: {error}", path.display()))?;
        if file_type.is_dir() {
            collect_rule_files(&path, output)?;
        } else if file_type.is_file()
            && (path.extension().is_none()
                || path.extension().is_some_and(|extension| extension == "sg"))
        {
            output.push(path);
        }
    }
    Ok(())
}

fn normalized_path(path: &Path) -> String {
    path.to_string_lossy().replace('\\', "/")
}

fn apply_compatibility_overlay(path: &Path, source: &[u8]) -> Result<(Vec<u8>, bool), String> {
    let normalized = normalized_path(path);
    if !normalized.ends_with(NINTENDO_RULE_SUFFIX) {
        return Ok((source.to_vec(), false));
    }
    if source.len() != NINTENDO_RULE_BYTES {
        return Err(format!(
            "refusing Nintendo compatibility overlay: expected {NINTENDO_RULE_BYTES} bytes, got {}",
            source.len()
        ));
    }
    let matches = source
        .windows(NINTENDO_VAR_DECLARATION.len())
        .enumerate()
        .filter_map(|(offset, window)| (window == NINTENDO_VAR_DECLARATION).then_some(offset))
        .collect::<Vec<_>>();
    if matches.len() != 1 {
        return Err(format!(
            "refusing Nintendo compatibility overlay: expected one declaration, got {}",
            matches.len()
        ));
    }
    debug_assert_eq!(
        NINTENDO_VAR_DECLARATION.len(),
        NINTENDO_COMPAT_DECLARATION.len()
    );
    let mut transformed = source.to_vec();
    let start = matches[0];
    let end = start + NINTENDO_VAR_DECLARATION.len();
    transformed[start..end].copy_from_slice(NINTENDO_COMPAT_DECLARATION);
    Ok((transformed, true))
}

fn new_runtime() -> Result<Runtime, String> {
    Runtime::new().map_err(|error| error.to_string())
}

fn new_context(runtime: &Runtime) -> Result<Context, String> {
    Context::full(runtime).map_err(|error| error.to_string())
}

fn eval_unit(context: &Context, source: &[u8]) -> Result<(), String> {
    context.with(|ctx| {
        let mut options = EvalOptions::default();
        options.strict = false;
        ctx.eval_with_options::<(), _>(source.to_vec(), options)
            .catch(&ctx)
            .map_err(|error| error.to_string())
    })
}

fn install_host_shim(context: &Context) -> Result<(), String> {
    eval_unit(context, HOST_SHIM)
}

fn eval_string(context: &Context, source: &[u8]) -> Result<String, String> {
    context.with(|ctx| {
        let mut options = EvalOptions::default();
        options.strict = false;
        ctx.eval_with_options::<String, _>(source.to_vec(), options)
            .catch(&ctx)
            .map_err(|error| error.to_string())
    })
}

fn evaluate_corpus(
    roots: &[PathBuf],
    shared_realm: bool,
    compatibility_overlay: bool,
) -> Result<bool, String> {
    let mut files = Vec::new();
    for root in roots {
        collect_rule_files(root, &mut files)?;
    }
    files.sort_by_key(|path| normalized_path(path));

    let started = Instant::now();
    let runtime = new_runtime()?;
    let interrupt_ticks = Arc::new(AtomicUsize::new(0));
    let interrupt_ticks_for_handler = Arc::clone(&interrupt_ticks);
    runtime.set_interrupt_handler(Some(Box::new(move || {
        interrupt_ticks_for_handler.fetch_add(1, Ordering::Relaxed) >= 1_000_000
    })));
    let shared_context = if shared_realm {
        let context = new_context(&runtime)?;
        install_host_shim(&context)?;
        Some(context)
    } else {
        None
    };
    let mut errors = Vec::new();
    let mut overlays_applied = Vec::new();
    let mut total_bytes = 0_u64;

    for path in &files {
        let original_bytes =
            fs::read(path).map_err(|error| format!("cannot read {}: {error}", path.display()))?;
        total_bytes = total_bytes
            .checked_add(original_bytes.len() as u64)
            .ok_or_else(|| "rule byte count overflow".to_owned())?;
        let (evaluated_bytes, overlay_applied) = if compatibility_overlay {
            apply_compatibility_overlay(path, &original_bytes)?
        } else {
            (original_bytes, false)
        };
        if overlay_applied {
            overlays_applied.push(normalized_path(path));
        }
        interrupt_ticks.store(0, Ordering::Relaxed);
        let isolated_context;
        let context = if let Some(context) = &shared_context {
            context
        } else {
            isolated_context = new_context(&runtime)?;
            install_host_shim(&isolated_context)?;
            &isolated_context
        };
        if let Err(error) = eval_unit(context, &evaluated_bytes) {
            errors.push(json!({
                "path": normalized_path(path),
                "error": error,
            }));
        }
    }

    let report = json!({
        "schema_version": 1,
        "runtime": {
            "crate": "rquickjs",
            "version": "0.12.1",
            "default_features": false,
            "features": ["std"],
            "engine": "QuickJS-NG",
        },
        "realm_mode": if shared_realm { "shared" } else { "isolated" },
        "operation": if compatibility_overlay {
            "sloppy eval with explicit host proxy and manifest-pinned compatibility overlay"
        } else {
            "sloppy eval with explicit host proxy"
        },
        "compatibility_overlay": {
            "enabled": compatibility_overlay,
            "id": "nintendo-unused-var-tp-v1",
            "expected_source_sha256": NINTENDO_RULE_SHA256,
            "expected_source_bytes": NINTENDO_RULE_BYTES,
            "preserves_source_file": true,
            "preserves_evaluated_length": true,
            "applied_paths": overlays_applied,
        },
        "interrupt_handler_call_limit_per_file": 1_000_000,
        "selection": "recursive files with .sg or no extension",
        "roots": roots
            .iter()
            .map(|path| normalized_path(path))
            .collect::<Vec<_>>(),
        "files": files.len(),
        "bytes": total_bytes,
        "eval_errors": errors,
        "eval_error_count": errors.len(),
        "elapsed_ms": started.elapsed().as_millis(),
    });
    println!(
        "{}",
        serde_json::to_string_pretty(&report)
            .map_err(|error| format!("cannot serialize report: {error}"))?
    );
    Ok(errors.is_empty())
}

fn run_fixture(rule_root: &Path) -> Result<bool, String> {
    let started = Instant::now();
    let runtime = new_runtime()?;
    let context = new_context(&runtime)?;
    context.with(|ctx| {
        let host_add = Function::new(ctx.clone(), |left: i32, right: i32| {
            left.saturating_add(right)
        })
        .map_err(|error| error.to_string())?;
        ctx.globals()
            .set("hostAdd", host_add)
            .map_err(|error| error.to_string())
    })?;
    let host_result = eval_string(&context, br#"String(hostAdd(20, 22))"#)?;

    let helper_path = rule_root.join("_runtime_helpers");
    let helper_bytes = fs::read(&helper_path)
        .map_err(|error| format!("cannot read {}: {error}", helper_path.display()))?;
    eval_unit(&context, &helper_bytes)?;
    let helper_result = eval_string(
        &context,
        br#""a".append("b").appendS("c", "/") + "|" + (7).padStart(3, "0")"#,
    )?;

    let audio_runtime = new_runtime()?;
    let audio_context = new_context(&audio_runtime)?;
    install_host_shim(&audio_context)?;
    let audio_path = rule_root.join("Binary").join("audio.1.sg");
    let audio_bytes = fs::read(&audio_path)
        .map_err(|error| format!("cannot read {}: {error}", audio_path.display()))?;
    let audio_eval = eval_unit(&audio_context, &audio_bytes);
    let audio_result = if audio_eval.is_ok() {
        eval_string(
            &audio_context,
            br#"metaType + "|" + metaName + "|" + included.join(",") + "|" + typeof detect"#,
        )?
    } else {
        String::new()
    };

    let redeclaration_runtime = new_runtime()?;
    let redeclaration_context = new_context(&redeclaration_runtime)?;
    let invalid_redeclaration = eval_unit(
        &redeclaration_context,
        b"function detect() { var value, other; const first = 1, value = 2; }",
    );

    let shared_runtime = new_runtime()?;
    let shared_context = new_context(&shared_runtime)?;
    eval_unit(&shared_context, b"const sharedName = 1;")?;
    let shared_lexical_redeclaration = eval_unit(&shared_context, b"const sharedName = 2;");

    let nintendo_runtime = new_runtime()?;
    let nintendo_context = new_context(&nintendo_runtime)?;
    install_host_shim(&nintendo_context)?;
    let nintendo_path = rule_root
        .join("Binary")
        .join("format_bin.Nintendo-certified-file.1.sg");
    let nintendo_bytes = fs::read(&nintendo_path)
        .map_err(|error| format!("cannot read {}: {error}", nintendo_path.display()))?;
    let nintendo_eval = eval_unit(&nintendo_context, &nintendo_bytes);
    let (nintendo_compat_bytes, nintendo_overlay_applied) =
        apply_compatibility_overlay(&nintendo_path, &nintendo_bytes)?;
    let nintendo_compat_runtime = new_runtime()?;
    let nintendo_compat_context = new_context(&nintendo_compat_runtime)?;
    install_host_shim(&nintendo_compat_context)?;
    let nintendo_compat_eval = eval_unit(&nintendo_compat_context, &nintendo_compat_bytes);

    let interrupt_count = Arc::new(AtomicUsize::new(0));
    let interrupt_count_for_handler = Arc::clone(&interrupt_count);
    let limited_runtime = new_runtime()?;
    limited_runtime.set_interrupt_handler(Some(Box::new(move || {
        interrupt_count_for_handler.fetch_add(1, Ordering::Relaxed) >= 16
    })));
    let limited_context = new_context(&limited_runtime)?;
    let interrupt_error = eval_unit(&limited_context, b"for (;;) {}").err();

    let memory_runtime = new_runtime()?;
    memory_runtime.set_memory_limit(4 * 1024 * 1024);
    let memory_context = new_context(&memory_runtime)?;
    let memory_limit_error = eval_unit(
        &memory_context,
        b"globalThis.large = new ArrayBuffer(16 * 1024 * 1024);",
    )
    .err();

    let passed = host_result == "42"
        && helper_result == "a, b/c|007"
        && audio_eval.is_ok()
        && audio_result == "audio||chunkparsers,soundchips,bytecodeparsers|function"
        && invalid_redeclaration.is_err()
        && shared_lexical_redeclaration.is_err()
        && nintendo_eval.is_err()
        && nintendo_overlay_applied
        && nintendo_compat_eval.is_ok()
        && interrupt_error.is_some()
        && memory_limit_error.is_some();
    let compatible = nintendo_eval.is_ok();
    let report = json!({
        "schema_version": 1,
        "runtime": {
            "crate": "rquickjs",
            "version": "0.12.1",
            "default_features": false,
            "features": ["std"],
            "engine": "QuickJS-NG",
        },
        "host_function_result": host_result,
        "runtime_helpers_result": helper_result,
        "audio_rule": {
            "path": normalized_path(&audio_path),
            "bytes": audio_bytes.len(),
            "eval_accepted": audio_eval.is_ok(),
            "eval_error": audio_eval.err(),
            "result": audio_result,
        },
        "invalid_var_const_redeclaration": {
            "eval_accepted": invalid_redeclaration.is_ok(),
            "eval_error": invalid_redeclaration.err(),
        },
        "shared_const_redeclaration": {
            "second_eval_accepted": shared_lexical_redeclaration.is_ok(),
            "second_eval_error": shared_lexical_redeclaration.err(),
        },
        "nintendo_rule": {
            "path": normalized_path(&nintendo_path),
            "bytes": fs::metadata(&nintendo_path)
                .map_err(|error| error.to_string())?
                .len(),
            "eval_accepted": nintendo_eval.is_ok(),
            "eval_error": nintendo_eval.err(),
            "source_sha256": NINTENDO_RULE_SHA256,
            "compatibility_overlay": {
                "id": "nintendo-unused-var-tp-v1",
                "applied": nintendo_overlay_applied,
                "evaluated_length_unchanged": nintendo_compat_bytes.len() == nintendo_bytes.len(),
                "eval_accepted": nintendo_compat_eval.is_ok(),
                "eval_error": nintendo_compat_eval.err(),
            },
        },
        "interrupt": {
            "handler_calls": interrupt_count.load(Ordering::Relaxed),
            "error": interrupt_error,
        },
        "memory_limit": {
            "bytes": 4 * 1024 * 1024,
            "error": memory_limit_error,
        },
        "elapsed_ms": started.elapsed().as_millis(),
        "candidate_compatible_with_fixed_rules": compatible,
        "passed": passed,
    });
    println!(
        "{}",
        serde_json::to_string_pretty(&report)
            .map_err(|error| format!("cannot serialize report: {error}"))?
    );
    Ok(passed)
}

fn usage() -> ExitCode {
    eprintln!(
        "usage: diec-rquickjs-rule-runtime-spike \
         <eval-isolated|eval-isolated-compat|eval-shared> <rule-root>...\n       \
         diec-rquickjs-rule-runtime-spike fixture <main-rule-root>"
    );
    ExitCode::from(2)
}

fn main() -> ExitCode {
    let mut arguments = env::args_os();
    let _program = arguments.next();
    let Some(command) = arguments.next() else {
        return usage();
    };
    let roots = arguments.map(PathBuf::from).collect::<Vec<_>>();
    if roots.is_empty() {
        return usage();
    }

    let result = if command == "eval-isolated" {
        evaluate_corpus(&roots, false, false)
    } else if command == "eval-isolated-compat" {
        evaluate_corpus(&roots, false, true)
    } else if command == "eval-shared" {
        evaluate_corpus(&roots, true, false)
    } else if command == "fixture" && roots.len() == 1 {
        run_fixture(&roots[0])
    } else {
        return usage();
    };
    match result {
        Ok(true) => ExitCode::SUCCESS,
        Ok(false) => ExitCode::FAILURE,
        Err(error) => {
            eprintln!("{error}");
            ExitCode::FAILURE
        }
    }
}

#[cfg(test)]
mod tests {
    use super::{
        NINTENDO_COMPAT_DECLARATION, NINTENDO_RULE_BYTES, NINTENDO_VAR_DECLARATION,
        apply_compatibility_overlay, collect_rule_files, normalized_path,
    };
    use std::fs;
    use std::path::PathBuf;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn temporary_directory() -> PathBuf {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system clock should follow Unix epoch")
            .as_nanos();
        std::env::temp_dir().join(format!(
            "diec-rquickjs-spike-{}-{nonce}",
            std::process::id()
        ))
    }

    #[test]
    fn corpus_selection_keeps_sg_and_extensionless_files_only() {
        let root = temporary_directory();
        let nested = root.join("PE");
        fs::create_dir_all(&nested).expect("temporary tree should be created");
        fs::write(root.join("_init"), b"init").expect("helper should be written");
        fs::write(nested.join("rule.sg"), b"rule").expect("rule should be written");
        fs::write(nested.join("notes.txt"), b"notes").expect("non-rule should be written");

        let mut files = Vec::new();
        collect_rule_files(&root, &mut files).expect("tree should be readable");
        files.sort();
        let relative = files
            .iter()
            .map(|path| {
                normalized_path(
                    path.strip_prefix(&root)
                        .expect("selected path should remain under root"),
                )
            })
            .collect::<Vec<_>>();

        fs::remove_dir_all(&root).expect("temporary tree should be removed");
        assert_eq!(relative, ["PE/rule.sg", "_init"]);
    }

    #[test]
    fn path_normalization_uses_forward_slashes() {
        assert_eq!(
            normalized_path(&PathBuf::from(r"db\Binary\audio.1.sg")),
            "db/Binary/audio.1.sg"
        );
    }

    #[test]
    fn compatibility_overlay_is_exact_and_length_preserving() {
        let mut source = vec![b' '; NINTENDO_RULE_BYTES];
        let offset = 100;
        source[offset..offset + NINTENDO_VAR_DECLARATION.len()]
            .copy_from_slice(NINTENDO_VAR_DECLARATION);
        let path = PathBuf::from("db/Binary/format_bin.Nintendo-certified-file.1.sg");
        let (transformed, applied) =
            apply_compatibility_overlay(&path, &source).expect("known rule shape should transform");
        assert!(applied);
        assert_eq!(transformed.len(), source.len());
        assert_eq!(
            &transformed[offset..offset + NINTENDO_COMPAT_DECLARATION.len()],
            NINTENDO_COMPAT_DECLARATION
        );
        assert_eq!(
            &transformed[..offset],
            &source[..offset],
            "prefix must remain byte-identical"
        );
    }

    #[test]
    fn compatibility_overlay_refuses_drift() {
        let path = PathBuf::from("db/Binary/format_bin.Nintendo-certified-file.1.sg");
        let error = apply_compatibility_overlay(&path, b"var tp, e;")
            .expect_err("unexpected source identity must be rejected");
        assert!(error.contains("expected 1994 bytes"));
    }
}
