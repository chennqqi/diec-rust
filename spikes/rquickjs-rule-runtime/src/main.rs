use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::ExitCode;
use std::sync::Arc;
use std::sync::Mutex;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::Instant;

use rquickjs::{
    CatchResultExt, Context, Function, Object, Runtime, context::EvalOptions, function::Opt,
};
use serde_json::{Value, json};

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
const AUDIO_RULE_SUFFIX: &str = "Binary/audio.1.sg";
const AUDIO_RULE_BYTES: usize = 603_640;
const AUDIO_RULE_SHA256: &str = "998c2476ddc07a88c83598192faf1ffb4b35d60c4b2d6c1fafcfa4b153a9892f";
const AUDIO_CONST_DEBUG_DECLARATION: &[u8] = b"const debug = 0;";
const AUDIO_COMPAT_DEBUG_DECLARATION: &[u8] = b"var   debug = 0;";
const EXTENSIONS_RULE_SUFFIX: &str = "Binary/__MiniExtensionsHeuristic_By_DosX.7.sg";
const EXTENSIONS_RULE_BYTES: usize = 21_958;
const EXTENSIONS_RULE_SHA256: &str =
    "e8eac22087d7814bdb6c80fd3626b1dbad721c16a5ce4ab290b9eedcc165c12d";
const EXTENSIONS_CONST_DETECT_DECLARATION: &[u8] = b"const detect = main;";
const EXTENSIONS_COMPAT_DETECT_DECLARATION: &[u8] = b"var   detect = main;";
const UPSTREAM_COMMIT: &str = "74eaf505c250ab47e709024e9dc41657cd8f2254";
const RULES_COMMIT: &str = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6";
const LINUX_QT5_BINARY_ORDER_SHA256: &str =
    "27138d68ed788dd2609b7c533fecf540593fa2e4ddb7195adc26b1a9ff0e1ff3";
const BINARY_SIGNATURE_COUNT: usize = 292;

type Detection = (String, String, String, String);
type SharedDetections = Arc<Mutex<Vec<Detection>>>;

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

fn apply_exact_lifecycle_overlay(
    path: &Path,
    source: &[u8],
    suffix: &str,
    expected_bytes: usize,
    declaration: &[u8],
    replacement: &[u8],
    id: &'static str,
) -> Result<(Vec<u8>, Option<&'static str>), String> {
    if !normalized_path(path).ends_with(suffix) {
        return Ok((source.to_vec(), None));
    }
    if source.len() != expected_bytes {
        return Err(format!(
            "refusing {id} overlay: expected {expected_bytes} bytes, got {}",
            source.len()
        ));
    }
    if declaration.len() != replacement.len() {
        return Err(format!("invalid {id} overlay: replacement length differs"));
    }
    let matches = source
        .windows(declaration.len())
        .enumerate()
        .filter_map(|(offset, window)| (window == declaration).then_some(offset))
        .collect::<Vec<_>>();
    if matches.len() != 1 {
        return Err(format!(
            "refusing {id} overlay: expected one declaration, got {}",
            matches.len()
        ));
    }
    let mut transformed = source.to_vec();
    let start = matches[0];
    transformed[start..start + declaration.len()].copy_from_slice(replacement);
    Ok((transformed, Some(id)))
}

fn apply_binary_lifecycle_overlay(
    path: &Path,
    source: &[u8],
) -> Result<(Vec<u8>, Option<&'static str>), String> {
    let (transformed, nintendo_applied) = apply_compatibility_overlay(path, source)?;
    if nintendo_applied {
        return Ok((transformed, Some("nintendo-unused-var-tp-v1")));
    }
    let (transformed, audio_id) = apply_exact_lifecycle_overlay(
        path,
        source,
        AUDIO_RULE_SUFFIX,
        AUDIO_RULE_BYTES,
        AUDIO_CONST_DEBUG_DECLARATION,
        AUDIO_COMPAT_DEBUG_DECLARATION,
        "audio-global-const-debug-v1",
    )?;
    if audio_id.is_some() {
        return Ok((transformed, audio_id));
    }
    apply_exact_lifecycle_overlay(
        path,
        source,
        EXTENSIONS_RULE_SUFFIX,
        EXTENSIONS_RULE_BYTES,
        EXTENSIONS_CONST_DETECT_DECLARATION,
        EXTENSIONS_COMPAT_DETECT_DECLARATION,
        "extensions-global-const-detect-v1",
    )
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

fn read_unsigned(data: &[u8], offset: usize, width: usize, big_endian: bool) -> f64 {
    let Some(bytes) = data.get(offset..offset.saturating_add(width)) else {
        return 0.0;
    };
    let value = if big_endian {
        bytes
            .iter()
            .fold(0_u64, |value, byte| (value << 8) | u64::from(*byte))
    } else {
        bytes
            .iter()
            .rev()
            .fold(0_u64, |value, byte| (value << 8) | u64::from(*byte))
    };
    value as f64
}

fn signature_matches(data: &[u8], pattern: &str, offset: usize) -> bool {
    match pattern {
        "'SCE'00" => data.get(offset..offset.saturating_add(4)) == Some(b"SCE\0"),
        "0000 0002" => data.get(offset..offset.saturating_add(4)) == Some(b"\0\0\0\x02"),
        "0300 0000" => data.get(offset..offset.saturating_add(4)) == Some(b"\x03\0\0\0"),
        "7F 'ELF' .. .. 01" => data
            .get(offset..offset.saturating_add(7))
            .is_some_and(|bytes| bytes[0] == 0x7f && &bytes[1..4] == b"ELF" && bytes[6] == 1),
        _ => false,
    }
}

fn install_nintendo_host(
    context: &Context,
    data: Arc<Vec<u8>>,
    detections: SharedDetections,
) -> Result<(), String> {
    context.with(|ctx| {
        let globals = ctx.globals();
        let x = Object::new(ctx.clone()).map_err(|error| error.to_string())?;

        let c_data = Arc::clone(&data);
        x.set(
            "c",
            Function::new(ctx.clone(), move |pattern: String, offset: Opt<usize>| {
                signature_matches(&c_data, &pattern, offset.0.unwrap_or(0))
            })
            .map_err(|error| error.to_string())?,
        )
        .map_err(|error| error.to_string())?;

        for (name, width) in [("U16", 2_usize), ("U32", 4), ("U64", 8)] {
            let integer_data = Arc::clone(&data);
            x.set(
                name,
                Function::new(ctx.clone(), move |offset: usize, big_endian: bool| {
                    read_unsigned(&integer_data, offset, width, big_endian)
                })
                .map_err(|error| error.to_string())?,
            )
            .map_err(|error| error.to_string())?;
        }

        let size = data.len() as f64;
        x.set(
            "Sz",
            Function::new(ctx.clone(), move || size).map_err(|error| error.to_string())?,
        )
        .map_err(|error| error.to_string())?;
        x.set(
            "isHeuristicScan",
            Function::new(ctx.clone(), || false).map_err(|error| error.to_string())?,
        )
        .map_err(|error| error.to_string())?;
        x.set(
            "isVerbose",
            Function::new(ctx.clone(), || false).map_err(|error| error.to_string())?,
        )
        .map_err(|error| error.to_string())?;
        globals
            .set("Binary", x.clone())
            .map_err(|error| error.to_string())?;
        globals.set("X", x).map_err(|error| error.to_string())?;
        globals
            .set(
                "_log",
                Function::new(ctx.clone(), |_message: String| {})
                    .map_err(|error| error.to_string())?,
            )
            .map_err(|error| error.to_string())?;
        globals
            .set(
                "_isResultPresent",
                Function::new(ctx.clone(), |_kind: String, _name: String| false)
                    .map_err(|error| error.to_string())?,
            )
            .map_err(|error| error.to_string())?;
        globals
            .set(
                "_getNumberOfResults",
                Function::new(ctx.clone(), |_kind: Opt<String>| 0_i32)
                    .map_err(|error| error.to_string())?,
            )
            .map_err(|error| error.to_string())?;
        globals
            .set(
                "_removeResult",
                Function::new(ctx.clone(), |_kind: String, _name: String| {})
                    .map_err(|error| error.to_string())?,
            )
            .map_err(|error| error.to_string())?;
        globals
            .set(
                "_setLang",
                Function::new(ctx.clone(), |_language: String, _version: Opt<String>| {})
                    .map_err(|error| error.to_string())?,
            )
            .map_err(|error| error.to_string())?;
        let result_detections = Arc::clone(&detections);
        globals
            .set(
                "_setResult",
                Function::new(
                    ctx.clone(),
                    move |kind: String, name: String, version: String, info: String| {
                        result_detections
                            .lock()
                            .expect("Nintendo fixture result mutex poisoned")
                            .push((kind, name, version, info));
                    },
                )
                .map_err(|error| error.to_string())?,
            )
            .map_err(|error| error.to_string())?;
        Ok(())
    })
}

fn install_main_include_registry(context: &Context, rule_root: &Path) -> Result<(), String> {
    let mut helpers = serde_json::Map::new();
    let entries = fs::read_dir(rule_root)
        .map_err(|error| format!("cannot read {}: {error}", rule_root.display()))?;
    for entry in entries {
        let entry =
            entry.map_err(|error| format!("cannot enumerate {}: {error}", rule_root.display()))?;
        let path = entry.path();
        let file_type = entry
            .file_type()
            .map_err(|error| format!("cannot inspect {}: {error}", path.display()))?;
        if !file_type.is_file()
            || !(path.extension().is_none()
                || path.extension().is_some_and(|extension| extension == "sg"))
        {
            continue;
        }
        let name = path
            .file_name()
            .and_then(|name| name.to_str())
            .ok_or_else(|| format!("non-UTF-8 helper name: {}", path.display()))?
            .to_uppercase();
        let source = fs::read_to_string(&path)
            .map_err(|error| format!("cannot read {}: {error}", path.display()))?;
        helpers.entry(name).or_insert(Value::String(source));
    }
    let registry = serde_json::to_string(&helpers)
        .map_err(|error| format!("cannot serialize include registry: {error}"))?;
    let program = format!(
        r#"
        globalThis.__helperSources = {registry};
        globalThis.__includeTrace = [];
        function includeScript(name) {{
            var key = String(name).toUpperCase();
            if (!Object.prototype.hasOwnProperty.call(__helperSources, key)) {{
                throw new Error("Cannot find: " + name);
            }}
            __includeTrace.push(String(name));
            (0, eval)(__helperSources[key]);
        }}
        "#
    );
    eval_unit(context, program.as_bytes())
}

fn parse_binary_order(document: &Value) -> Result<Vec<String>, String> {
    if document.get("upstream_commit").and_then(Value::as_str) != Some(UPSTREAM_COMMIT) {
        return Err("Binary order upstream commit mismatch".to_owned());
    }
    if document.get("rules_commit").and_then(Value::as_str) != Some(RULES_COMMIT) {
        return Err("Binary order rules commit mismatch".to_owned());
    }
    if document.get("order_sha256").and_then(Value::as_str) != Some(LINUX_QT5_BINARY_ORDER_SHA256) {
        return Err("Binary order SHA-256 mismatch".to_owned());
    }
    let order = document
        .get("order")
        .and_then(Value::as_array)
        .ok_or_else(|| "Binary order array is missing".to_owned())?
        .iter()
        .map(|value| {
            value
                .as_str()
                .map(str::to_owned)
                .ok_or_else(|| "Binary order contains a non-string".to_owned())
        })
        .collect::<Result<Vec<_>, _>>()?;
    if order.len() != BINARY_SIGNATURE_COUNT {
        return Err(format!(
            "expected {BINARY_SIGNATURE_COUNT} Binary signatures, got {}",
            order.len()
        ));
    }
    let mut unique = order.clone();
    unique.sort();
    unique.dedup();
    if unique.len() != order.len() {
        return Err("Binary order contains duplicate names".to_owned());
    }
    for name in &order {
        let path = Path::new(name);
        if path.file_name().and_then(|value| value.to_str()) != Some(name.as_str()) {
            return Err(format!("invalid Binary signature name: {name}"));
        }
    }
    Ok(order)
}

fn run_binary_lifecycle(
    rule_root: &Path,
    order_path: &Path,
    compatibility_overlays: bool,
) -> Result<bool, String> {
    let order_document: Value = serde_json::from_slice(
        &fs::read(order_path)
            .map_err(|error| format!("cannot read {}: {error}", order_path.display()))?,
    )
    .map_err(|error| format!("cannot parse {}: {error}", order_path.display()))?;
    let order = parse_binary_order(&order_document)?;
    let started = Instant::now();
    let runtime = new_runtime()?;
    let interrupt_ticks = Arc::new(AtomicUsize::new(0));
    let interrupt_ticks_for_handler = Arc::clone(&interrupt_ticks);
    runtime.set_interrupt_handler(Some(Box::new(move || {
        interrupt_ticks_for_handler.fetch_add(1, Ordering::Relaxed) >= 1_000_000
    })));
    let context = new_context(&runtime)?;
    install_host_shim(&context)?;
    install_main_include_registry(&context, rule_root)?;

    for relative in ["_init", "Binary/_init"] {
        let path = rule_root.join(relative);
        let source =
            fs::read(&path).map_err(|error| format!("cannot read {}: {error}", path.display()))?;
        eval_unit(&context, &source)
            .map_err(|error| format!("cannot eval {}: {error}", path.display()))?;
    }

    let mut errors = Vec::new();
    let mut total_bytes = 0_u64;
    let mut overlay_paths = Vec::new();
    for (index, name) in order.iter().enumerate() {
        let path = rule_root.join("Binary").join(name);
        let source =
            fs::read(&path).map_err(|error| format!("cannot read {}: {error}", path.display()))?;
        total_bytes = total_bytes
            .checked_add(source.len() as u64)
            .ok_or_else(|| "Binary rule byte count overflow".to_owned())?;
        let (evaluated, overlay_id) = if compatibility_overlays {
            apply_binary_lifecycle_overlay(&path, &source)?
        } else {
            (source, None)
        };
        if let Some(id) = overlay_id {
            overlay_paths.push(json!({
                "id": id,
                "path": normalized_path(&path),
            }));
        }
        interrupt_ticks.store(0, Ordering::Relaxed);
        if let Err(error) = eval_unit(&context, &evaluated) {
            errors.push(json!({
                "index": index,
                "name": name,
                "error": error,
            }));
        }
    }
    let include_trace_text = eval_string(&context, b"JSON.stringify(__includeTrace)")?;
    let include_trace: Value = serde_json::from_str(&include_trace_text)
        .map_err(|error| format!("cannot parse include trace: {error}"))?;
    let overlay_ok = if compatibility_overlays {
        overlay_paths.len() == 3
            && overlay_paths[0]["id"] == "audio-global-const-debug-v1"
            && overlay_paths[1]["id"] == "nintendo-unused-var-tp-v1"
            && overlay_paths[2]["id"] == "extensions-global-const-detect-v1"
    } else {
        overlay_paths.is_empty()
    };
    let passed = errors.is_empty() && overlay_ok;
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({
            "schema_version": 1,
            "operation": if compatibility_overlays {
                "fixed Linux Qt5 Binary top-level lifecycle eval with compatibility overlays"
            } else {
                "fixed Linux Qt5 Binary top-level lifecycle eval without compatibility overlays"
            },
            "runtime": "rquickjs 0.12.1 / QuickJS-NG 0.15.1",
            "upstream_commit": UPSTREAM_COMMIT,
            "rules_commit": RULES_COMMIT,
            "order_manifest": normalized_path(order_path),
            "order_sha256": LINUX_QT5_BINARY_ORDER_SHA256,
            "init_sequence": ["_init", "Binary/_init"],
            "include_trace": include_trace,
            "files": order.len(),
            "bytes": total_bytes,
            "compatibility_overlay": {
                "enabled": compatibility_overlays,
                "applied_paths": overlay_paths,
                "expected_count": if compatibility_overlays { 3 } else { 0 },
                "applied_exactly": overlay_ok,
                "source_sha256": {
                    "audio-global-const-debug-v1": AUDIO_RULE_SHA256,
                    "nintendo-unused-var-tp-v1": NINTENDO_RULE_SHA256,
                    "extensions-global-const-detect-v1": EXTENSIONS_RULE_SHA256,
                },
            },
            "eval_errors": errors,
            "eval_error_count": errors.len(),
            "elapsed_ms": started.elapsed().as_millis(),
            "passed": passed,
            "scope": "top-level eval only; detect functions are not called",
        }))
        .map_err(|error| format!("cannot serialize report: {error}"))?
    );
    Ok(passed)
}

fn run_nintendo_rule(rule_root: &Path, data: Vec<u8>) -> Result<Vec<Detection>, String> {
    let runtime = new_runtime()?;
    let context = new_context(&runtime)?;
    let detections = Arc::new(Mutex::new(Vec::new()));
    install_nintendo_host(&context, Arc::new(data), Arc::clone(&detections))?;
    install_main_include_registry(&context, rule_root)?;

    for relative in ["_init", "Binary/_init"] {
        let path = rule_root.join(relative);
        let bytes =
            fs::read(&path).map_err(|error| format!("cannot read {}: {error}", path.display()))?;
        eval_unit(&context, &bytes)
            .map_err(|error| format!("cannot eval {}: {error}", path.display()))?;
    }
    let include_trace = eval_string(&context, b"JSON.stringify(__includeTrace)")?;
    if include_trace != r#"["_debug","_runtime_helpers","language","read"]"# {
        return Err(format!("unexpected init include trace: {include_trace}"));
    }

    let rule_path = rule_root
        .join("Binary")
        .join("format_bin.Nintendo-certified-file.1.sg");
    let source = fs::read(&rule_path)
        .map_err(|error| format!("cannot read {}: {error}", rule_path.display()))?;
    let (transformed, applied) = apply_compatibility_overlay(&rule_path, &source)?;
    if !applied {
        return Err("Nintendo compatibility overlay was not applied".to_owned());
    }
    eval_unit(&context, &transformed)?;
    let detected = eval_string(&context, b"String(detect())")?;
    if detected != "true" {
        let probe = eval_string(
            &context,
            br#"JSON.stringify([
                X.c("'SCE'00"),
                X.U16(8, X.c("0000 0002", 4) ? _BE : _LE),
                X.U16(0xA, X.c("0000 0002", 4) ? _BE : _LE),
                X.U64(0x10, X.c("0000 0002", 4) ? _BE : _LE),
                X.Sz()
            ])"#,
        )?;
        return Err(format!(
            "Nintendo detect returned {detected}; probe={probe}"
        ));
    }

    let result = detections
        .lock()
        .map_err(|_| "Nintendo fixture result mutex poisoned".to_owned())?
        .clone();
    Ok(result)
}

fn run_nintendo_corpus(
    rule_root: &Path,
    corpus_root: &Path,
    baseline_path: &Path,
) -> Result<bool, String> {
    let baseline: Value = serde_json::from_slice(
        &fs::read(baseline_path)
            .map_err(|error| format!("cannot read {}: {error}", baseline_path.display()))?,
    )
    .map_err(|error| format!("cannot parse {}: {error}", baseline_path.display()))?;
    let samples = baseline
        .get("samples")
        .and_then(Value::as_object)
        .ok_or_else(|| "Nintendo baseline has no samples object".to_owned())?;
    let mut names = samples.keys().cloned().collect::<Vec<_>>();
    names.sort();
    let mut reports = Vec::new();
    let mut all_match = true;

    for name in names {
        let sample = &samples[&name];
        let expected = sample
            .get("detections")
            .and_then(Value::as_array)
            .and_then(|detections| detections.first())
            .and_then(Value::as_array)
            .ok_or_else(|| format!("Nintendo baseline sample {name} has no detection"))?;
        let expected_tuple = (
            expected[0].as_str().unwrap_or_default().to_owned(),
            expected[1].as_str().unwrap_or_default().to_owned(),
            expected[2].as_str().unwrap_or_default().to_owned(),
            "fSELF".to_owned(),
        );
        let input_path = corpus_root.join(&name);
        let actual = run_nintendo_rule(
            rule_root,
            fs::read(&input_path)
                .map_err(|error| format!("cannot read {}: {error}", input_path.display()))?,
        )
        .map_err(|error| format!("{name}: {error}"))?;
        let matches = actual == [expected_tuple.clone()];
        all_match &= matches;
        reports.push(json!({
            "name": name,
            "expected": expected_tuple,
            "actual": actual,
            "matches": matches,
        }));
    }

    println!(
        "{}",
        serde_json::to_string_pretty(&json!({
            "schema_version": 1,
            "operation": "Nintendo rule detect with Rust byte HostApi",
            "runtime": "rquickjs 0.12.1 / QuickJS-NG 0.15.1",
            "compatibility_overlay": "nintendo-unused-var-tp-v1",
            "init_sequence": ["_init", "Binary/_init"],
            "include_trace": ["_debug", "_runtime_helpers", "language", "read"],
            "host_methods": [
                "X.c", "X.U16", "X.U32", "X.U64", "X.Sz",
                "X.isHeuristicScan", "X.isVerbose", "_setResult"
            ],
            "samples": reports,
            "sample_count": samples.len(),
            "matched_count": reports.iter().filter(|item| item["matches"] == true).count(),
            "all_match": all_match,
        }))
        .map_err(|error| format!("cannot serialize report: {error}"))?
    );
    Ok(all_match)
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
         diec-rquickjs-rule-runtime-spike fixture <main-rule-root>\n       \
         diec-rquickjs-rule-runtime-spike \
         <eval-binary-lifecycle|eval-binary-lifecycle-raw> \
         <main-rule-root> <binary-order-json>\n       \
         diec-rquickjs-rule-runtime-spike detect-nintendo \
         <main-rule-root> <corpus-dir> <baseline-json>"
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
    } else if command == "eval-binary-lifecycle" && roots.len() == 2 {
        run_binary_lifecycle(&roots[0], &roots[1], true)
    } else if command == "eval-binary-lifecycle-raw" && roots.len() == 2 {
        run_binary_lifecycle(&roots[0], &roots[1], false)
    } else if command == "detect-nintendo" && roots.len() == 3 {
        run_nintendo_corpus(&roots[0], &roots[1], &roots[2])
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
        apply_compatibility_overlay, apply_exact_lifecycle_overlay, collect_rule_files,
        normalized_path, read_unsigned, signature_matches,
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

    #[test]
    fn exact_lifecycle_overlay_is_path_size_and_declaration_guarded() {
        let path = PathBuf::from("db/Binary/example.sg");
        let source = b"const value = 1;";
        let (transformed, id) = apply_exact_lifecycle_overlay(
            &path,
            source,
            "Binary/example.sg",
            source.len(),
            b"const",
            b"var  ",
            "example-v1",
        )
        .expect("exact overlay should apply");
        assert_eq!(id, Some("example-v1"));
        assert_eq!(transformed, b"var   value = 1;");

        let error = apply_exact_lifecycle_overlay(
            &path,
            source,
            "Binary/example.sg",
            source.len() + 1,
            b"const",
            b"var  ",
            "example-v1",
        )
        .expect_err("size drift must be rejected");
        assert!(error.contains("expected 17 bytes"));
    }

    #[test]
    fn nintendo_host_reads_both_endiannesses() {
        let bytes = [0x12, 0x34, 0x56, 0x78];
        assert_eq!(read_unsigned(&bytes, 0, 2, true), 0x1234 as f64);
        assert_eq!(read_unsigned(&bytes, 0, 2, false), 0x3412 as f64);
        assert_eq!(read_unsigned(&bytes, 0, 4, true), 0x12345678 as f64);
        assert_eq!(read_unsigned(&bytes, 3, 2, true), 0.0);
    }

    #[test]
    fn nintendo_host_matches_only_supported_signatures() {
        let mut bytes = vec![0_u8; 32];
        bytes[0..8].copy_from_slice(b"SCE\0\0\0\0\x02");
        bytes[16..23].copy_from_slice(b"\x7fELF\0\0\x01");
        assert!(signature_matches(&bytes, "'SCE'00", 0));
        assert!(signature_matches(&bytes, "0000 0002", 4));
        assert!(signature_matches(&bytes, "7F 'ELF' .. .. 01", 16));
        assert!(!signature_matches(&bytes, "0300 0000", 4));
        assert!(!signature_matches(&bytes, "unsupported", 0));
    }
}
