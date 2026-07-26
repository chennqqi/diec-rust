use std::collections::BTreeSet;
use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::ExitCode;
use std::sync::Arc;
use std::sync::Mutex;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::thread;
use std::time::{Duration, Instant};

use diec_signature_parser_spike::Pattern;
use rquickjs::{
    CatchResultExt, Context, Error, Function, Object, Runtime, context::EvalOptions, function::Opt,
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

const HOST_FALLBACK_SHIM: &[u8] = br#"
    globalThis.__fallbackCalls = [];
    function __makeFallback(path) {
        var stub;
        stub = new Proxy(function () {
            __fallbackCalls.push(path);
            return stub;
        }, {
            get: function (_target, property) {
                if (property === Symbol.toPrimitive) return function () { return 0; };
                return __makeFallback(path + "." + String(property));
            }
        });
        return stub;
    }
    Binary = new Proxy(Binary, {
        get: function (target, property) {
            if (property in target) return target[property];
            return __makeFallback("Binary." + String(property));
        }
    });
    X = Binary;
    Util = new Proxy(Util, {
        get: function (target, property) {
            if (property in target) return target[property];
            return __makeFallback("Util." + String(property));
        }
    });
"#;

const DIAGNOSTIC_HOST_FALLBACK_SHIM: &[u8] = br#"
    globalThis.__fallbackCalls = [];
    globalThis.__fallbackTotal = 0;
    function __makeDiagnosticFallback(path) {
        var stub;
        stub = new Proxy(function () {
            __fallbackTotal++;
            if (__fallbackCalls.length < 256) __fallbackCalls.push(path);
            return stub;
        }, {
            get: function (_target, property) {
                if (property === Symbol.toPrimitive) return function () { return 0; };
                return __makeDiagnosticFallback(path + "." + String(property));
            }
        });
        return stub;
    }
    Binary = new Proxy(Binary, {
        get: function (target, property) {
            if (property in target) return target[property];
            return __makeDiagnosticFallback("Binary." + String(property));
        }
    });
    X = Binary;
    Util = new Proxy(Util, {
        get: function (target, property) {
            if (property in target) return target[property];
            return __makeDiagnosticFallback("Util." + String(property));
        }
    });
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
type NintendoLifecycleResult = (Vec<Detection>, Vec<String>, usize, Vec<String>);
type SharedDetections = Arc<Mutex<Vec<Detection>>>;
type SharedHostTrace = Arc<HostTrace>;

#[derive(Default)]
struct HostTrace {
    calls: AtomicUsize,
    fast_paths: AtomicUsize,
    generic_paths: AtomicUsize,
    quirks: AtomicUsize,
    errors: AtomicUsize,
    unique_quirks: Mutex<BTreeSet<String>>,
    unique_errors: Mutex<BTreeSet<String>>,
    search_calls: AtomicUsize,
    find_signature_calls: AtomicUsize,
    f_sig_calls: AtomicUsize,
    is_signature_present_calls: AtomicUsize,
    search_matches: AtomicUsize,
    search_quirks: AtomicUsize,
    search_errors: AtomicUsize,
    search_unique_quirks: Mutex<BTreeSet<String>>,
    search_unique_errors: Mutex<BTreeSet<String>>,
    is_overlay_calls: AtomicUsize,
    get_overlay_offset_calls: AtomicUsize,
    get_overlay_size_calls: AtomicUsize,
    is_overlay_present_calls: AtomicUsize,
    get_file_suffix_calls: AtomicUsize,
    get_header_string_calls: AtomicUsize,
    is_plain_text_calls: AtomicUsize,
    is_utf8_text_calls: AtomicUsize,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum HostFilePart {
    Header,
    Overlay,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct BinaryHostContext {
    file_part: HostFilePart,
    overlay_offset: i64,
    overlay_size: i64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum TextUnicodeType {
    None,
    Little,
    Big,
}

#[derive(Clone, Debug, Eq, PartialEq)]
struct BinaryStringContext {
    file_suffix: String,
    header_string: String,
    is_plain_text: bool,
    is_utf8_text: bool,
    unicode_type: TextUnicodeType,
}

impl BinaryStringContext {
    fn from_file_name(data: &[u8], file_name: &str) -> Self {
        let is_plain_text = is_plain_text_type(data);
        let is_utf8_text = is_utf8_text_type(data);
        let unicode_type = detect_unicode_type(data);
        let header_string = match unicode_type {
            TextUnicodeType::Little => read_utf16_header(data, false),
            TextUnicodeType::Big => read_utf16_header(data, true),
            TextUnicodeType::None if is_utf8_text => read_utf8_header(data),
            TextUnicodeType::None if is_plain_text => read_latin1_header(data),
            TextUnicodeType::None => String::new(),
        };
        Self {
            file_suffix: qt_file_suffix(file_name),
            header_string,
            is_plain_text,
            is_utf8_text,
            unicode_type,
        }
    }
}

impl BinaryHostContext {
    fn new(
        file_part: HostFilePart,
        overlay_offset: i64,
        overlay_size: i64,
    ) -> Result<Self, String> {
        if overlay_size < 0 {
            return Err("Binary overlay size must be non-negative".to_owned());
        }
        Ok(Self {
            file_part,
            overlay_offset,
            overlay_size,
        })
    }

    fn identity_header(data_len: usize) -> Result<Self, String> {
        Self::new(
            HostFilePart::Header,
            i64::try_from(data_len)
                .map_err(|_| "Binary input length does not fit qint64".to_owned())?,
            0,
        )
    }

    fn is_overlay(self) -> bool {
        self.file_part == HostFilePart::Overlay
    }

    fn is_overlay_present(self) -> bool {
        self.overlay_size != 0
    }
}

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

fn install_host_fallbacks(context: &Context) -> Result<(), String> {
    eval_unit(context, HOST_FALLBACK_SHIM)
}

fn install_diagnostic_host_fallbacks(context: &Context) -> Result<(), String> {
    eval_unit(context, DIAGNOSTIC_HOST_FALLBACK_SHIM)
}

fn install_selected_host_trace(context: &Context) -> Result<(), String> {
    eval_unit(
        context,
        br#"
        globalThis.__selectedHostTrace = [];
        ["c", "U8", "U16", "U32", "U64", "SA", "Sz", "isDeepScan", "isHeuristicScan", "isVerbose"]
            .forEach(function (name) {
                var original = X[name];
                X[name] = function () {
                    var args = Array.prototype.slice.call(arguments);
                    var value = original.apply(X, args);
                    __selectedHostTrace.push([name, args, value]);
                    return value;
                };
            });
        "#,
    )
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

fn eval_rule_lexical(
    context: &Context,
    source: &[u8],
    invoke_detect: bool,
) -> Result<String, String> {
    let suffix = if invoke_detect {
        b"\nreturn typeof detect === 'function' ? String(detect()) : 'not-function';\n}).call(globalThis)\n"
            .as_slice()
    } else {
        b"\nreturn typeof detect;\n}).call(globalThis)\n".as_slice()
    };
    let prefix = b"(function () {\n";
    let capacity = prefix
        .len()
        .checked_add(source.len())
        .and_then(|size| size.checked_add(suffix.len()))
        .ok_or_else(|| "lexical wrapper size overflow".to_owned())?;
    let mut wrapped = Vec::with_capacity(capacity);
    wrapped.extend_from_slice(prefix);
    wrapped.extend_from_slice(source);
    wrapped.extend_from_slice(suffix);
    eval_string(context, &wrapped)
}

fn read_unsigned_bits(data: &[u8], offset: usize, width: usize, big_endian: bool) -> u64 {
    let Some(bytes) = data.get(offset..offset.saturating_add(width)) else {
        return 0;
    };
    if big_endian {
        bytes
            .iter()
            .fold(0_u64, |value, byte| (value << 8) | u64::from(*byte))
    } else {
        bytes
            .iter()
            .rev()
            .fold(0_u64, |value, byte| (value << 8) | u64::from(*byte))
    }
}

fn read_unsigned(data: &[u8], offset: usize, width: usize, big_endian: bool) -> f64 {
    read_unsigned_bits(data, offset, width, big_endian) as f64
}

fn read_signed(data: &[u8], offset: usize, width: usize, big_endian: bool) -> f64 {
    let unsigned = read_unsigned_bits(data, offset, width, big_endian);
    let shift = 64_u32.saturating_sub((width as u32).saturating_mul(8));
    ((unsigned << shift) as i64 >> shift) as f64
}

fn shift_right_unsigned(value: f64, bits: u32) -> rquickjs::Result<f64> {
    const MAX_SAFE_INTEGER: f64 = 9_007_199_254_740_991.0;
    if !value.is_finite() || value < 0.0 || value.fract() != 0.0 || value > MAX_SAFE_INTEGER {
        return Err(Error::new_from_js_message(
            "number",
            "quint64",
            "shru64 spike accepts only non-negative safe integers",
        ));
    }
    if bits >= 64 {
        return Err(Error::new_from_js_message(
            "number",
            "quint64 shift",
            "shru64 shift must be less than 64",
        ));
    }
    Ok(((value as u64) >> bits) as f64)
}

fn nonnegative_index(value: i64) -> Option<usize> {
    usize::try_from(value).ok()
}

fn read_ascii(data: &[u8], offset: usize, size: usize) -> String {
    let Some(bytes) = read_byte_slice(data, offset, size) else {
        return String::new();
    };
    bytes
        .iter()
        .take_while(|byte| **byte != 0)
        .map(|byte| char::from(*byte))
        .collect()
}

fn read_byte_slice(data: &[u8], offset: usize, size: usize) -> Option<&[u8]> {
    if offset > data.len() {
        return None;
    }
    let end = offset.saturating_add(size).min(data.len());
    data.get(offset..end)
}

fn percentage_at_least(value: usize, total: usize, percent: usize) -> bool {
    (value as u128) * 100 >= (total as u128) * (percent as u128)
}

fn percentage_at_most(value: usize, total: usize, percent: usize) -> bool {
    (value as u128) * 100 <= (total as u128) * (percent as u128)
}

fn is_plain_text_type(data: &[u8]) -> bool {
    let sample = &data[..data.len().min(0x8000)];
    if sample.is_empty()
        || sample.starts_with(&[0xef, 0xbb, 0xbf])
        || sample.starts_with(&[0xff, 0xfe])
        || sample.starts_with(&[0xfe, 0xff])
    {
        return false;
    }

    let mut control = 0_usize;
    let mut printable = 0_usize;
    let mut extended = 0_usize;
    for byte in sample {
        match *byte {
            0 => return false,
            1..=8 => control += 1,
            9 | 10 | 13 | 0x20..=0x7e => printable += 1,
            0x80..=0xff => extended += 1,
            _ => control += 1,
        }
    }
    percentage_at_least(printable + extended, sample.len(), 85)
        && percentage_at_most(control, sample.len(), 5)
        && percentage_at_most(extended, sample.len(), 50)
}

fn is_utf8_text_type(data: &[u8]) -> bool {
    let sample = &data[..data.len().min(0x2000)];
    if sample.is_empty() {
        return false;
    }
    let has_bom = sample.starts_with(&[0xef, 0xbb, 0xbf]);
    let mut index = usize::from(has_bom) * 3;
    let mut valid_chars = 0_usize;
    let mut multibyte_chars = 0_usize;
    let mut printable_chars = 0_usize;
    while index < sample.len() {
        let byte = sample[index];
        if byte == 0 {
            return false;
        }
        if byte < 0x80 {
            printable_chars += usize::from(byte >= 0x20 || matches!(byte, 9 | 10 | 13));
            valid_chars += 1;
            index += 1;
            continue;
        }
        if byte & 0xe0 == 0xc0 {
            if index + 1 >= sample.len() || sample[index + 1] & 0xc0 != 0x80 || byte < 0xc2 {
                return false;
            }
            multibyte_chars += 1;
            valid_chars += 1;
            index += 2;
            continue;
        }
        if byte & 0xf0 == 0xe0 {
            if index + 2 >= sample.len()
                || sample[index + 1] & 0xc0 != 0x80
                || sample[index + 2] & 0xc0 != 0x80
                || (byte == 0xe0 && sample[index + 1] < 0xa0)
            {
                return false;
            }
            multibyte_chars += 1;
            valid_chars += 1;
            index += 3;
            continue;
        }
        if byte & 0xf8 == 0xf0 {
            if index + 3 >= sample.len()
                || sample[index + 1] & 0xc0 != 0x80
                || sample[index + 2] & 0xc0 != 0x80
                || sample[index + 3] & 0xc0 != 0x80
                || (byte == 0xf0 && sample[index + 1] < 0x90)
                || byte > 0xf4
                || (byte == 0xf4 && sample[index + 1] > 0x8f)
            {
                return false;
            }
            multibyte_chars += 1;
            valid_chars += 1;
            index += 4;
            continue;
        }
        return false;
    }

    if has_bom {
        valid_chars != 0
    } else {
        valid_chars != 0
            && (multibyte_chars as u128) * 100 > (valid_chars as u128) * 5
            && percentage_at_least(printable_chars, valid_chars, 70)
    }
}

fn detect_unicode_type(data: &[u8]) -> TextUnicodeType {
    let sample = &data[..data.len().min(0x1000)];
    if sample.starts_with(&[0xff, 0xfe]) {
        return TextUnicodeType::Little;
    }
    if sample.starts_with(&[0xfe, 0xff]) {
        return TextUnicodeType::Big;
    }
    if sample.len() < 4 {
        return TextUnicodeType::None;
    }

    let analyzed = &sample[..sample.len().min(512)];
    let mut nulls = 0_usize;
    let mut even_nulls = 0_usize;
    let mut odd_nulls = 0_usize;
    let mut printable = 0_usize;
    for (index, byte) in analyzed.iter().enumerate() {
        if *byte == 0 {
            nulls += 1;
            if index % 2 == 0 {
                even_nulls += 1;
            } else {
                odd_nulls += 1;
            }
        } else if (0x20..=0x7e).contains(byte) {
            printable += 1;
        }
    }
    if nulls == 0
        || analyzed.len() <= 4
        || !percentage_at_least(nulls, analyzed.len(), 30)
        || !percentage_at_least(printable, analyzed.len(), 30)
    {
        return TextUnicodeType::None;
    }
    if even_nulls > odd_nulls.saturating_mul(2) {
        return TextUnicodeType::Little;
    }
    if odd_nulls > even_nulls.saturating_mul(2) {
        return TextUnicodeType::Big;
    }

    let mut little_pairs = 0_usize;
    let mut big_pairs = 0_usize;
    for pair in analyzed.chunks_exact(2) {
        let little = u16::from_le_bytes([pair[0], pair[1]]);
        if little & 0xff00 == 0 && (0x20..=0x7e).contains(&(little & 0xff)) {
            little_pairs += 1;
        }
        let big = u16::from_be_bytes([pair[0], pair[1]]);
        if big & 0xff00 == 0 && (0x20..=0x7e).contains(&(big & 0xff)) {
            big_pairs += 1;
        }
    }
    if little_pairs > big_pairs {
        TextUnicodeType::Little
    } else if big_pairs > little_pairs {
        TextUnicodeType::Big
    } else {
        TextUnicodeType::None
    }
}

fn nul_terminated(bytes: &[u8]) -> &[u8] {
    let length = bytes
        .iter()
        .position(|byte| *byte == 0)
        .unwrap_or(bytes.len());
    &bytes[..length]
}

fn read_latin1_header(data: &[u8]) -> String {
    nul_terminated(&data[..data.len().min(0x1000)])
        .iter()
        .map(|byte| char::from(*byte))
        .collect()
}

fn read_utf8_header(data: &[u8]) -> String {
    let max_size = data.len().min(0x1000);
    let bytes = data
        .get(3..3_usize.saturating_add(max_size).min(data.len()))
        .unwrap_or_default();
    String::from_utf8_lossy(nul_terminated(bytes)).into_owned()
}

fn read_utf16_header(data: &[u8], big_endian: bool) -> String {
    let max_words = data.len().min(0x1000);
    let bytes = data.get(2..).unwrap_or_default();
    let mut words = Vec::with_capacity((bytes.len() / 2).min(max_words));
    for pair in bytes.chunks_exact(2).take(max_words) {
        let word = if big_endian {
            u16::from_be_bytes([pair[0], pair[1]])
        } else {
            u16::from_le_bytes([pair[0], pair[1]])
        };
        if word == 0 {
            break;
        }
        words.push(word);
    }
    String::from_utf16_lossy(&words)
}

fn qt_file_suffix(file_name: &str) -> String {
    if file_name.is_empty() {
        return String::new();
    }
    #[cfg(windows)]
    let base_name = file_name.rsplit(['/', '\\']).next().unwrap_or(file_name);
    #[cfg(not(windows))]
    let base_name = file_name.rsplit('/').next().unwrap_or(file_name);
    base_name
        .rfind('.')
        .map_or_else(String::new, |dot| base_name[dot + 1..].to_owned())
}

fn read_byte_array(data: &[u8], offset: i64, size: i64, replace_zero: bool) -> Vec<u8> {
    let Some((offset, size)) = nonnegative_index(offset).zip(nonnegative_index(size)) else {
        return Vec::new();
    };
    read_byte_slice(data, offset, size)
        .unwrap_or_default()
        .iter()
        .map(|byte| {
            if replace_zero && *byte == 0 {
                b' '
            } else {
                *byte
            }
        })
        .collect()
}

fn search_signature(
    data: &[u8],
    trace: &HostTrace,
    host_name: &'static str,
    offset: i64,
    size: i64,
    pattern: &str,
) -> rquickjs::Result<Option<usize>> {
    trace.search_calls.fetch_add(1, Ordering::Relaxed);
    match Pattern::find_binary_wrapper(pattern, data, offset, size) {
        Ok(report) => {
            trace
                .search_matches
                .fetch_add(usize::from(report.found.is_some()), Ordering::Relaxed);
            trace
                .search_quirks
                .fetch_add(report.quirks.len(), Ordering::Relaxed);
            if !report.quirks.is_empty() {
                trace
                    .search_unique_quirks
                    .lock()
                    .map_err(|_| {
                        Error::new_from_js_message(
                            host_name,
                            "signature search result",
                            "signature search quirk mutex poisoned",
                        )
                    })?
                    .extend(report.quirks.iter().map(|quirk| format!("{quirk:?}")));
            }
            Ok(report.found.map(|found| found.offset))
        }
        Err(error) => {
            trace.search_errors.fetch_add(1, Ordering::Relaxed);
            let message = error.to_string();
            trace
                .search_unique_errors
                .lock()
                .map_err(|_| {
                    Error::new_from_js_message(
                        host_name,
                        "signature search result",
                        "signature search error mutex poisoned",
                    )
                })?
                .insert(message.clone());
            Err(Error::new_from_js_message(
                host_name,
                "signature search result",
                message,
            ))
        }
    }
}

fn install_nintendo_host(
    context: &Context,
    data: Arc<Vec<u8>>,
    detections: SharedDetections,
) -> Result<SharedHostTrace, String> {
    let host_context = BinaryHostContext::identity_header(data.len())?;
    let string_context = BinaryStringContext::from_file_name(&data, "");
    install_nintendo_host_with_context_and_strings(
        context,
        data,
        detections,
        host_context,
        string_context,
    )
}

fn install_nintendo_host_for_path(
    context: &Context,
    data: Arc<Vec<u8>>,
    detections: SharedDetections,
    input_path: &Path,
) -> Result<SharedHostTrace, String> {
    let host_context = BinaryHostContext::identity_header(data.len())?;
    let file_name = input_path.as_os_str().to_string_lossy();
    let string_context = BinaryStringContext::from_file_name(&data, &file_name);
    install_nintendo_host_with_context_and_strings(
        context,
        data,
        detections,
        host_context,
        string_context,
    )
}

#[cfg(test)]
fn install_nintendo_host_with_context(
    context: &Context,
    data: Arc<Vec<u8>>,
    detections: SharedDetections,
    host_context: BinaryHostContext,
) -> Result<SharedHostTrace, String> {
    let string_context = BinaryStringContext::from_file_name(&data, "");
    install_nintendo_host_with_context_and_strings(
        context,
        data,
        detections,
        host_context,
        string_context,
    )
}

fn install_nintendo_host_with_context_and_strings(
    context: &Context,
    data: Arc<Vec<u8>>,
    detections: SharedDetections,
    host_context: BinaryHostContext,
    string_context: BinaryStringContext,
) -> Result<SharedHostTrace, String> {
    let signature_trace = Arc::new(HostTrace::default());
    let signature_trace_for_context = Arc::clone(&signature_trace);
    context.with(|ctx| {
        let globals = ctx.globals();
        let x = Object::new(ctx.clone()).map_err(|error| error.to_string())?;

        for name in ["c", "compare"] {
            let compare_data = Arc::clone(&data);
            let compare_trace = Arc::clone(&signature_trace_for_context);
            x.set(
                name,
                Function::new(ctx.clone(), move |pattern: String, offset: Opt<i64>| {
                    compare_trace.calls.fetch_add(1, Ordering::Relaxed);
                    match Pattern::compare_binary_wrapper(
                        &pattern,
                        &compare_data,
                        offset.0.unwrap_or(0),
                    ) {
                        Ok(report) => {
                            if report.header_fast_path {
                                compare_trace.fast_paths.fetch_add(1, Ordering::Relaxed);
                            } else {
                                compare_trace.generic_paths.fetch_add(1, Ordering::Relaxed);
                            }
                            compare_trace
                                .quirks
                                .fetch_add(report.quirks.len(), Ordering::Relaxed);
                            if !report.quirks.is_empty() {
                                let mut unique =
                                    compare_trace.unique_quirks.lock().map_err(|_| {
                                        Error::new_from_js_message(
                                            "Binary.compare",
                                            "boolean",
                                            "signature quirk mutex poisoned",
                                        )
                                    })?;
                                unique
                                    .extend(report.quirks.iter().map(|quirk| format!("{quirk:?}")));
                            }
                            Ok(report.matched)
                        }
                        Err(error) => {
                            compare_trace.errors.fetch_add(1, Ordering::Relaxed);
                            let message = error.to_string();
                            compare_trace
                                .unique_errors
                                .lock()
                                .map_err(|_| {
                                    Error::new_from_js_message(
                                        "Binary.compare",
                                        "boolean",
                                        "signature error mutex poisoned",
                                    )
                                })?
                                .insert(message.clone());
                            Err(Error::new_from_js_message(
                                "Binary.compare",
                                "boolean",
                                message,
                            ))
                        }
                    }
                })
                .map_err(|error| error.to_string())?,
            )
            .map_err(|error| error.to_string())?;
        }

        {
            let search_data = Arc::clone(&data);
            let search_trace = Arc::clone(&signature_trace_for_context);
            x.set(
                "findSignature",
                Function::new(
                    ctx.clone(),
                    move |offset: i64, size: i64, pattern: String| {
                        search_trace
                            .find_signature_calls
                            .fetch_add(1, Ordering::Relaxed);
                        search_signature(
                            &search_data,
                            &search_trace,
                            "Binary.findSignature",
                            offset,
                            size,
                            &pattern,
                        )
                        .map(|found| {
                            found
                                .and_then(|offset| i64::try_from(offset).ok())
                                .unwrap_or(-1)
                        })
                    },
                )
                .map_err(|error| error.to_string())?,
            )
            .map_err(|error| error.to_string())?;
        }
        {
            let search_data = Arc::clone(&data);
            let search_trace = Arc::clone(&signature_trace_for_context);
            x.set(
                "fSig",
                Function::new(
                    ctx.clone(),
                    move |offset: i64, size: i64, pattern: String| {
                        search_trace.f_sig_calls.fetch_add(1, Ordering::Relaxed);
                        search_signature(
                            &search_data,
                            &search_trace,
                            "Binary.fSig",
                            offset,
                            size,
                            &pattern,
                        )
                        .map(|found| {
                            found
                                .and_then(|offset| i64::try_from(offset).ok())
                                .unwrap_or(-1)
                        })
                    },
                )
                .map_err(|error| error.to_string())?,
            )
            .map_err(|error| error.to_string())?;
        }
        {
            let search_data = Arc::clone(&data);
            let search_trace = Arc::clone(&signature_trace_for_context);
            x.set(
                "isSignaturePresent",
                Function::new(
                    ctx.clone(),
                    move |offset: i64, size: i64, pattern: String| {
                        search_trace
                            .is_signature_present_calls
                            .fetch_add(1, Ordering::Relaxed);
                        search_signature(
                            &search_data,
                            &search_trace,
                            "Binary.isSignaturePresent",
                            offset,
                            size,
                            &pattern,
                        )
                        .map(|found| found.is_some())
                    },
                )
                .map_err(|error| error.to_string())?,
            )
            .map_err(|error| error.to_string())?;
        }

        {
            let overlay_trace = Arc::clone(&signature_trace_for_context);
            x.set(
                "isOverlay",
                Function::new(ctx.clone(), move || {
                    overlay_trace
                        .is_overlay_calls
                        .fetch_add(1, Ordering::Relaxed);
                    host_context.is_overlay()
                })
                .map_err(|error| error.to_string())?,
            )
            .map_err(|error| error.to_string())?;
        }
        {
            let overlay_trace = Arc::clone(&signature_trace_for_context);
            x.set(
                "getOverlayOffset",
                Function::new(ctx.clone(), move || {
                    overlay_trace
                        .get_overlay_offset_calls
                        .fetch_add(1, Ordering::Relaxed);
                    host_context.overlay_offset
                })
                .map_err(|error| error.to_string())?,
            )
            .map_err(|error| error.to_string())?;
        }
        {
            let overlay_trace = Arc::clone(&signature_trace_for_context);
            x.set(
                "getOverlaySize",
                Function::new(ctx.clone(), move || {
                    overlay_trace
                        .get_overlay_size_calls
                        .fetch_add(1, Ordering::Relaxed);
                    host_context.overlay_size
                })
                .map_err(|error| error.to_string())?,
            )
            .map_err(|error| error.to_string())?;
        }
        {
            let overlay_trace = Arc::clone(&signature_trace_for_context);
            x.set(
                "isOverlayPresent",
                Function::new(ctx.clone(), move || {
                    overlay_trace
                        .is_overlay_present_calls
                        .fetch_add(1, Ordering::Relaxed);
                    host_context.is_overlay_present()
                })
                .map_err(|error| error.to_string())?,
            )
            .map_err(|error| error.to_string())?;
        }
        {
            let value = string_context.file_suffix.clone();
            let string_trace = Arc::clone(&signature_trace_for_context);
            x.set(
                "getFileSuffix",
                Function::new(ctx.clone(), move || {
                    string_trace
                        .get_file_suffix_calls
                        .fetch_add(1, Ordering::Relaxed);
                    value.clone()
                })
                .map_err(|error| error.to_string())?,
            )
            .map_err(|error| error.to_string())?;
        }
        {
            let value = string_context.header_string.clone();
            let string_trace = Arc::clone(&signature_trace_for_context);
            x.set(
                "getHeaderString",
                Function::new(ctx.clone(), move || {
                    string_trace
                        .get_header_string_calls
                        .fetch_add(1, Ordering::Relaxed);
                    value.clone()
                })
                .map_err(|error| error.to_string())?,
            )
            .map_err(|error| error.to_string())?;
        }
        {
            let value = string_context.is_plain_text;
            let string_trace = Arc::clone(&signature_trace_for_context);
            x.set(
                "isPlainText",
                Function::new(ctx.clone(), move || {
                    string_trace
                        .is_plain_text_calls
                        .fetch_add(1, Ordering::Relaxed);
                    value
                })
                .map_err(|error| error.to_string())?,
            )
            .map_err(|error| error.to_string())?;
        }
        {
            let value = string_context.is_utf8_text;
            let string_trace = Arc::clone(&signature_trace_for_context);
            x.set(
                "isUTF8Text",
                Function::new(ctx.clone(), move || {
                    string_trace
                        .is_utf8_text_calls
                        .fetch_add(1, Ordering::Relaxed);
                    value
                })
                .map_err(|error| error.to_string())?,
            )
            .map_err(|error| error.to_string())?;
        }

        for (name, width) in [
            ("U16", 2_usize),
            ("readWord", 2),
            ("read_uint16", 2),
            ("U24", 3),
            ("read_uint24", 3),
            ("U32", 4),
            ("readDword", 4),
            ("read_uint32", 4),
            ("U64", 8),
            ("readQword", 8),
            ("read_uint64", 8),
        ] {
            let integer_data = Arc::clone(&data);
            x.set(
                name,
                Function::new(ctx.clone(), move |offset: i64, big_endian: Opt<bool>| {
                    nonnegative_index(offset).map_or(0.0, |offset| {
                        read_unsigned(&integer_data, offset, width, big_endian.0.unwrap_or(false))
                    })
                })
                .map_err(|error| error.to_string())?,
            )
            .map_err(|error| error.to_string())?;
        }
        for name in ["U8", "readByte", "read_uint8"] {
            let byte_data = Arc::clone(&data);
            x.set(
                name,
                Function::new(ctx.clone(), move |offset: i64| {
                    nonnegative_index(offset)
                        .and_then(|offset| byte_data.get(offset))
                        .copied()
                        .unwrap_or(0)
                })
                .map_err(|error| error.to_string())?,
            )
            .map_err(|error| error.to_string())?;
        }
        for (name, width) in [
            ("I8", 1_usize),
            ("readSByte", 1),
            ("read_int8", 1),
            ("I16", 2),
            ("readSWord", 2),
            ("read_int16", 2),
            ("I32", 4),
            ("readSDword", 4),
            ("read_int32", 4),
            ("I64", 8),
            ("readSQword", 8),
            ("read_int64", 8),
        ] {
            let integer_data = Arc::clone(&data);
            x.set(
                name,
                Function::new(ctx.clone(), move |offset: i64, big_endian: Opt<bool>| {
                    nonnegative_index(offset).map_or(0.0, |offset| {
                        read_signed(&integer_data, offset, width, big_endian.0.unwrap_or(false))
                    })
                })
                .map_err(|error| error.to_string())?,
            )
            .map_err(|error| error.to_string())?;
        }
        for name in ["SA", "getString", "read_ansiString"] {
            let string_data = Arc::clone(&data);
            x.set(
                name,
                Function::new(ctx.clone(), move |offset: i64, size: Opt<i64>| {
                    nonnegative_index(offset)
                        .zip(nonnegative_index(size.0.unwrap_or(50)))
                        .map_or_else(String::new, |(offset, size)| {
                            read_ascii(&string_data, offset, size)
                        })
                })
                .map_err(|error| error.to_string())?,
            )
            .map_err(|error| error.to_string())?;
        }
        for name in ["readBytes", "BA"] {
            let array_data = Arc::clone(&data);
            x.set(
                name,
                Function::new(
                    ctx.clone(),
                    move |offset: i64, size: i64, replace_zero: Opt<bool>| {
                        read_byte_array(&array_data, offset, size, replace_zero.0.unwrap_or(false))
                    },
                )
                .map_err(|error| error.to_string())?,
            )
            .map_err(|error| error.to_string())?;
        }

        let size = data.len() as f64;
        for name in ["Sz", "getSize"] {
            x.set(
                name,
                Function::new(ctx.clone(), move || size).map_err(|error| error.to_string())?,
            )
            .map_err(|error| error.to_string())?;
        }
        x.set(
            "isHeuristicScan",
            Function::new(ctx.clone(), || false).map_err(|error| error.to_string())?,
        )
        .map_err(|error| error.to_string())?;
        x.set(
            "isDeepScan",
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
        let util = Object::new(ctx.clone()).map_err(|error| error.to_string())?;
        util.set(
            "shlu64",
            Function::new(ctx.clone(), |value: f64, bits: u32| {
                value * 2_f64.powi(i32::try_from(bits).unwrap_or(i32::MAX))
            })
            .map_err(|error| error.to_string())?,
        )
        .map_err(|error| error.to_string())?;
        util.set(
            "shru64",
            Function::new(ctx.clone(), shift_right_unsigned).map_err(|error| error.to_string())?,
        )
        .map_err(|error| error.to_string())?;
        util.set(
            "div64",
            Function::new(ctx.clone(), |dividend: i64, divisor: i64| {
                if divisor == 0 {
                    -1
                } else {
                    dividend.overflowing_div(divisor).0
                }
            })
            .map_err(|error| error.to_string())?,
        )
        .map_err(|error| error.to_string())?;
        globals
            .set("Util", util)
            .map_err(|error| error.to_string())?;
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
        Ok::<(), String>(())
    })?;
    Ok(signature_trace)
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
    lexical_wrapper: bool,
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
    let mut non_function_detects = Vec::new();
    let mut total_bytes = 0_u64;
    let mut overlay_paths = Vec::new();
    for (index, name) in order.iter().enumerate() {
        let path = rule_root.join("Binary").join(name);
        let source =
            fs::read(&path).map_err(|error| format!("cannot read {}: {error}", path.display()))?;
        total_bytes = total_bytes
            .checked_add(source.len() as u64)
            .ok_or_else(|| "Binary rule byte count overflow".to_owned())?;
        let (evaluated, overlay_id) = if lexical_wrapper {
            let (evaluated, applied) = apply_compatibility_overlay(&path, &source)?;
            (evaluated, applied.then_some("nintendo-unused-var-tp-v1"))
        } else if compatibility_overlays {
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
        let eval_result = if lexical_wrapper {
            eval_rule_lexical(&context, &evaluated, false).map(|detect_type| {
                if detect_type != "function" {
                    non_function_detects.push(json!({
                        "index": index,
                        "name": name,
                        "type": detect_type,
                    }));
                }
            })
        } else {
            eval_unit(&context, &evaluated)
        };
        if let Err(error) = eval_result {
            errors.push(json!({"index": index, "name": name, "error": error}));
        }
    }
    let include_trace_text = eval_string(&context, b"JSON.stringify(__includeTrace)")?;
    let include_trace: Value = serde_json::from_str(&include_trace_text)
        .map_err(|error| format!("cannot parse include trace: {error}"))?;
    let overlay_ok = if lexical_wrapper {
        overlay_paths.len() == 1 && overlay_paths[0]["id"] == "nintendo-unused-var-tp-v1"
    } else if compatibility_overlays {
        overlay_paths.len() == 3
            && overlay_paths[0]["id"] == "audio-global-const-debug-v1"
            && overlay_paths[1]["id"] == "nintendo-unused-var-tp-v1"
            && overlay_paths[2]["id"] == "extensions-global-const-detect-v1"
    } else {
        overlay_paths.is_empty()
    };
    let passed = errors.is_empty() && non_function_detects.is_empty() && overlay_ok;
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({
            "schema_version": 1,
            "operation": if lexical_wrapper {
                "fixed Linux Qt5 Binary lifecycle eval with per-rule lexical wrapper and Nintendo overlay"
            } else if compatibility_overlays {
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
                "enabled": compatibility_overlays || lexical_wrapper,
                "applied_paths": overlay_paths,
                "expected_count": if lexical_wrapper {
                    1
                } else if compatibility_overlays {
                    3
                } else {
                    0
                },
                "applied_exactly": overlay_ok,
                "source_sha256": {
                    "audio-global-const-debug-v1": AUDIO_RULE_SHA256,
                    "nintendo-unused-var-tp-v1": NINTENDO_RULE_SHA256,
                    "extensions-global-const-detect-v1": EXTENSIONS_RULE_SHA256,
                },
            },
            "eval_errors": errors,
            "eval_error_count": errors.len(),
            "detect_function_count": order.len() - non_function_detects.len(),
            "non_function_detects": non_function_detects,
            "elapsed_ms": started.elapsed().as_millis(),
            "passed": passed,
            "scope": if lexical_wrapper {
                "per-rule function lexical wrapper; detect is resolved but not called"
            } else {
                "top-level eval only; detect functions are not called"
            },
        }))
        .map_err(|error| format!("cannot serialize report: {error}"))?
    );
    Ok(passed)
}

fn parse_scope_fixture_order(document: &Value) -> Result<Vec<String>, String> {
    let generator = document.get("generator").and_then(Value::as_str);
    if !matches!(
        generator,
        Some(
            "tools/corpus/generate_script_scope_fixture.py"
                | "tools/corpus/generate_script_state_fixture.py"
        )
    ) {
        return Err("unexpected script semantics fixture generator".to_owned());
    }
    let order = document
        .get("rule_order")
        .and_then(Value::as_array)
        .ok_or_else(|| "script-scope rule_order is missing".to_owned())?
        .iter()
        .map(|value| {
            value
                .as_str()
                .map(str::to_owned)
                .ok_or_else(|| "script-scope rule_order contains a non-string".to_owned())
        })
        .collect::<Result<Vec<_>, _>>()?;
    if order.len() != 7 {
        return Err(format!(
            "expected 7 script-scope rules, got {}",
            order.len()
        ));
    }
    for name in &order {
        let path = Path::new(name);
        if path.file_name().and_then(|value| value.to_str()) != Some(name.as_str()) {
            return Err(format!("invalid script-scope rule name: {name}"));
        }
    }
    Ok(order)
}

fn parse_scope_detections(document: &Value) -> Result<Vec<Detection>, String> {
    document
        .get("detections")
        .and_then(Value::as_array)
        .ok_or_else(|| "Qt5 script-scope detections are missing".to_owned())?
        .iter()
        .map(|detection| {
            let field = |name| {
                detection
                    .get(name)
                    .and_then(Value::as_str)
                    .map(str::to_owned)
                    .ok_or_else(|| format!("Qt5 script-scope detection field is missing: {name}"))
            };
            Ok((
                field("type")?,
                field("name")?,
                field("version")?,
                field("info")?,
            ))
        })
        .collect()
}

fn run_scope_fixture(
    fixture_root: &Path,
    manifest_path: &Path,
    qt5_baseline_path: &Path,
    lexical_wrapper: bool,
) -> Result<bool, String> {
    let manifest: Value = serde_json::from_slice(
        &fs::read(manifest_path)
            .map_err(|error| format!("cannot read {}: {error}", manifest_path.display()))?,
    )
    .map_err(|error| format!("cannot parse {}: {error}", manifest_path.display()))?;
    let order = parse_scope_fixture_order(&manifest)?;
    let qt5_baseline: Value = serde_json::from_slice(
        &fs::read(qt5_baseline_path)
            .map_err(|error| format!("cannot read {}: {error}", qt5_baseline_path.display()))?,
    )
    .map_err(|error| format!("cannot parse {}: {error}", qt5_baseline_path.display()))?;
    let qt5_detections = parse_scope_detections(&qt5_baseline)?;
    let runtime = new_runtime()?;
    let context = new_context(&runtime)?;
    let detections = Arc::new(Mutex::new(Vec::new()));
    install_nintendo_host(&context, Arc::new(Vec::new()), Arc::clone(&detections))?;

    let mut observations = Vec::new();
    for name in &order {
        let path = fixture_root.join("main").join("Binary").join(name);
        let source =
            fs::read(&path).map_err(|error| format!("cannot read {}: {error}", path.display()))?;
        let before = detections
            .lock()
            .map_err(|_| "script-scope result mutex poisoned".to_owned())?
            .len();
        let lexical_result = if lexical_wrapper {
            Some(eval_rule_lexical(&context, &source, true))
        } else {
            None
        };
        let eval_result = if lexical_wrapper {
            lexical_result
                .as_ref()
                .expect("lexical result should be present")
                .as_ref()
                .map(|_| ())
                .map_err(Clone::clone)
        } else {
            eval_unit(&context, &source)
        };
        let detect_result = if lexical_wrapper {
            lexical_result
        } else if eval_result.is_ok() {
            Some(eval_string(
                &context,
                b"typeof detect === 'function' ? String(detect()) : 'not-function'",
            ))
        } else {
            None
        };
        let emitted = detections
            .lock()
            .map_err(|_| "script-scope result mutex poisoned".to_owned())?[before..]
            .to_vec();
        observations.push(json!({
            "name": name,
            "eval_accepted": eval_result.is_ok(),
            "eval_error": eval_result.err(),
            "detect_result": detect_result.map(|result| match result {
                Ok(value) => json!({"accepted": true, "value": value}),
                Err(error) => json!({"accepted": false, "error": error}),
            }),
            "detections": emitted,
        }));
    }

    let all_detections = detections
        .lock()
        .map_err(|_| "script-scope result mutex poisoned".to_owned())?
        .clone();
    let errors = observations
        .iter()
        .filter(|observation| observation["eval_accepted"] == false)
        .count();
    let matches_qt5_oracle = all_detections == qt5_detections;
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({
            "schema_version": 1,
            "operation": if lexical_wrapper {
                "shared host/global context with per-rule lexical wrapper and immediate detect invocation"
            } else {
                "shared-context sequential sloppy eval and detect invocation"
            },
            "runtime": "rquickjs 0.12.1 / QuickJS-NG 0.15.1",
            "fixture_manifest": normalized_path(manifest_path),
            "qt5_baseline": normalized_path(qt5_baseline_path),
            "rule_order": order,
            "observations": observations,
            "eval_error_count": errors,
            "detections": all_detections,
            "matches_qt5_oracle": matches_qt5_oracle,
            "passed": true,
        }))
        .map_err(|error| format!("cannot serialize report: {error}"))?
    );
    Ok(true)
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

fn run_nintendo_lifecycle_rule(
    rule_root: &Path,
    order: &[String],
    data: Vec<u8>,
) -> Result<NintendoLifecycleResult, String> {
    let expect_ea_xa = data.get(4..8) == Some(b"\x03\0\0\0");
    let runtime = new_runtime()?;
    let context = new_context(&runtime)?;
    let detections = Arc::new(Mutex::new(Vec::new()));
    install_nintendo_host(&context, Arc::new(data), Arc::clone(&detections))?;
    install_host_fallbacks(&context)?;
    install_main_include_registry(&context, rule_root)?;
    for relative in ["_init", "Binary/_init"] {
        let path = rule_root.join(relative);
        let source =
            fs::read(&path).map_err(|error| format!("cannot read {}: {error}", path.display()))?;
        eval_unit(&context, &source)
            .map_err(|error| format!("cannot eval {}: {error}", path.display()))?;
    }
    install_selected_host_trace(&context)?;

    let selected = [
        "archive_DEFLATE.1.sg",
        "audio_EXA.1.sg",
        "format_bin.Nintendo-certified-file.1.sg",
    ];
    let mut invoked = Vec::new();
    let mut overlay_count = 0;
    for name in order {
        let path = rule_root.join("Binary").join(name);
        let source =
            fs::read(&path).map_err(|error| format!("cannot read {}: {error}", path.display()))?;
        let (evaluated, applied) = apply_compatibility_overlay(&path, &source)?;
        overlay_count += usize::from(applied);
        let invoke = selected.contains(&name.as_str());
        let fallback_before = if invoke {
            eval_unit(&context, b"__selectedHostTrace = [];")?;
            Some(eval_string(&context, b"String(__fallbackCalls.length)")?)
        } else {
            None
        };
        let detect_result = eval_rule_lexical(&context, &evaluated, invoke)
            .map_err(|error| format!("cannot eval {name}: {error}"))?;
        if invoke {
            let fallback_after = eval_string(&context, b"String(__fallbackCalls.length)")?;
            if fallback_before.as_deref() != Some(fallback_after.as_str()) {
                let calls = eval_string(&context, b"JSON.stringify(__fallbackCalls)")?;
                return Err(format!(
                    "{name}: selected detect used fallback HostApi: {calls}"
                ));
            }
            if name == "audio_EXA.1.sg" && (detect_result == "true") != expect_ea_xa {
                let trace = eval_string(&context, b"JSON.stringify(__selectedHostTrace)")?;
                return Err(format!(
                    "{name}: expected detect={expect_ea_xa}, got {detect_result}; trace={trace}"
                ));
            }
            invoked.push(name.clone());
        }
    }
    if invoked != selected {
        return Err(format!("unexpected selected rule order: {invoked:?}"));
    }
    let include_trace_text = eval_string(&context, b"JSON.stringify(__includeTrace)")?;
    let include_trace: Vec<String> = serde_json::from_str(&include_trace_text)
        .map_err(|error| format!("cannot parse include trace: {error}"))?;
    let result = detections
        .lock()
        .map_err(|_| "Nintendo lifecycle result mutex poisoned".to_owned())?
        .clone();
    let fallback_calls_text = eval_string(&context, b"JSON.stringify(__fallbackCalls)")?;
    let fallback_calls = serde_json::from_str(&fallback_calls_text)
        .map_err(|error| format!("cannot parse fallback calls: {error}"))?;
    Ok((result, include_trace, overlay_count, fallback_calls))
}

fn run_nintendo_lifecycle_corpus(
    rule_root: &Path,
    corpus_root: &Path,
    baseline_path: &Path,
    order_path: &Path,
) -> Result<bool, String> {
    let baseline: Value = serde_json::from_slice(
        &fs::read(baseline_path)
            .map_err(|error| format!("cannot read {}: {error}", baseline_path.display()))?,
    )
    .map_err(|error| format!("cannot parse {}: {error}", baseline_path.display()))?;
    let order_document: Value = serde_json::from_slice(
        &fs::read(order_path)
            .map_err(|error| format!("cannot read {}: {error}", order_path.display()))?,
    )
    .map_err(|error| format!("cannot parse {}: {error}", order_path.display()))?;
    let order = parse_binary_order(&order_document)?;
    let samples = baseline
        .get("samples")
        .and_then(Value::as_object)
        .ok_or_else(|| "Nintendo baseline has no samples object".to_owned())?;
    let mut names = samples.keys().cloned().collect::<Vec<_>>();
    names.sort();
    let mut reports = Vec::new();
    let mut all_match = true;
    let mut common_include_trace: Option<Vec<String>> = None;

    for name in names {
        let expected = samples[&name]
            .get("detections")
            .and_then(Value::as_array)
            .ok_or_else(|| format!("Nintendo baseline sample {name} has no detections"))?
            .iter()
            .map(|detection| {
                let fields = detection
                    .as_array()
                    .ok_or_else(|| format!("invalid baseline detection for {name}"))?;
                Ok((
                    fields[0].as_str().unwrap_or_default().to_owned(),
                    fields[1].as_str().unwrap_or_default().to_owned(),
                    fields[2].as_str().unwrap_or_default().to_owned(),
                ))
            })
            .collect::<Result<Vec<_>, String>>()?;
        let input_path = corpus_root.join(&name);
        let (actual, include_trace, overlay_count, fallback_calls) = run_nintendo_lifecycle_rule(
            rule_root,
            &order,
            fs::read(&input_path)
                .map_err(|error| format!("cannot read {}: {error}", input_path.display()))?,
        )
        .map_err(|error| format!("{name}: {error}"))?;
        if include_trace.len() != 30 {
            return Err(format!(
                "{name}: expected 30 includes, got {}",
                include_trace.len()
            ));
        }
        if let Some(common) = &common_include_trace {
            if common != &include_trace {
                return Err(format!("{name}: include trace differs between samples"));
            }
        } else {
            common_include_trace = Some(include_trace);
        }
        if overlay_count != 1 {
            return Err(format!(
                "{name}: expected one Nintendo overlay, got {overlay_count}"
            ));
        }
        let execution_order = actual
            .iter()
            .map(|(kind, detection_name, version, _)| {
                (kind.clone(), detection_name.clone(), version.clone())
            })
            .collect::<Vec<_>>();
        let mut output_order = execution_order.clone();
        output_order.sort_by_key(|(kind, _, _)| match kind.as_str() {
            "format" => 0,
            "audio" => 1,
            _ => 2,
        });
        let nintendo_info_ok = actual
            .iter()
            .filter(|(kind, _, _, _)| kind == "format")
            .all(|(_, _, _, info)| info == "fSELF");
        let matches = output_order == expected && nintendo_info_ok;
        all_match &= matches;
        reports.push(json!({
            "name": name,
            "expected_output_order": expected,
            "actual_execution_order": execution_order,
            "actual_output_order": output_order,
            "nintendo_info_ok": nintendo_info_ok,
            "non_target_top_level_fallback_calls": fallback_calls,
            "matches": matches,
        }));
    }
    let include_trace = common_include_trace.unwrap_or_default();
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({
            "schema_version": 1,
            "operation": "fixed 292-rule Binary load with selected shared-state, EA-XA, and Nintendo detect invocation",
            "runtime": "rquickjs 0.12.1 / QuickJS-NG 0.15.1",
            "compatibility_overlay": "nintendo-unused-var-tp-v1",
            "order_manifest": normalized_path(order_path),
            "order_sha256": LINUX_QT5_BINARY_ORDER_SHA256,
            "rule_count": order.len(),
            "selected_rules": [
                "archive_DEFLATE.1.sg",
                "audio_EXA.1.sg",
                "format_bin.Nintendo-certified-file.1.sg"
            ],
            "include_trace": include_trace,
            "include_call_count": include_trace.len(),
            "output_projection": "target-only type order: format, audio",
            "samples": reports,
            "sample_count": samples.len(),
            "matched_count": reports.iter().filter(|item| item["matches"] == true).count(),
            "all_match": all_match,
        }))
        .map_err(|error| format!("cannot serialize report: {error}"))?
    );
    Ok(all_match)
}

fn trace_binary_detects(
    rule_root: &Path,
    input_path: &Path,
    order_path: &Path,
) -> Result<bool, String> {
    let order_document: Value = serde_json::from_slice(
        &fs::read(order_path)
            .map_err(|error| format!("cannot read {}: {error}", order_path.display()))?,
    )
    .map_err(|error| format!("cannot parse {}: {error}", order_path.display()))?;
    let order = parse_binary_order(&order_document)?;
    let data = fs::read(input_path)
        .map_err(|error| format!("cannot read {}: {error}", input_path.display()))?;
    let input_size = data.len();
    let runtime = new_runtime()?;
    let interrupt_ticks = Arc::new(AtomicUsize::new(0));
    let interrupt_ticks_for_handler = Arc::clone(&interrupt_ticks);
    runtime.set_interrupt_handler(Some(Box::new(move || {
        interrupt_ticks_for_handler.fetch_add(1, Ordering::Relaxed) >= 1_000_000
    })));
    let context = new_context(&runtime)?;
    let detections = Arc::new(Mutex::new(Vec::new()));
    let signature_trace = install_nintendo_host_for_path(
        &context,
        Arc::new(data),
        Arc::clone(&detections),
        input_path,
    )?;
    install_diagnostic_host_fallbacks(&context)?;
    install_main_include_registry(&context, rule_root)?;
    for relative in ["_init", "Binary/_init"] {
        let path = rule_root.join(relative);
        let source =
            fs::read(&path).map_err(|error| format!("cannot read {}: {error}", path.display()))?;
        eval_unit(&context, &source)
            .map_err(|error| format!("cannot eval {}: {error}", path.display()))?;
    }

    let started = Instant::now();
    let mut observations = Vec::with_capacity(order.len());
    let mut overlay_count = 0;
    let mut error_count = 0;
    let mut fallback_rule_count = 0;
    let mut fallback_call_total = 0_u64;
    let mut fallback_paths = BTreeSet::new();
    for (index, name) in order.iter().enumerate() {
        let path = rule_root.join("Binary").join(name);
        let source =
            fs::read(&path).map_err(|error| format!("cannot read {}: {error}", path.display()))?;
        let (evaluated, applied) = apply_compatibility_overlay(&path, &source)?;
        overlay_count += usize::from(applied);
        eval_unit(&context, b"__fallbackCalls = []; __fallbackTotal = 0;")?;
        let detections_before = detections
            .lock()
            .map_err(|_| "Binary trace result mutex poisoned".to_owned())?
            .len();
        let signature_calls_before = signature_trace.calls.load(Ordering::Relaxed);
        let signature_fast_paths_before = signature_trace.fast_paths.load(Ordering::Relaxed);
        let signature_generic_paths_before = signature_trace.generic_paths.load(Ordering::Relaxed);
        let signature_quirks_before = signature_trace.quirks.load(Ordering::Relaxed);
        let signature_errors_before = signature_trace.errors.load(Ordering::Relaxed);
        let signature_search_calls_before = signature_trace.search_calls.load(Ordering::Relaxed);
        let signature_find_signature_calls_before =
            signature_trace.find_signature_calls.load(Ordering::Relaxed);
        let signature_f_sig_calls_before = signature_trace.f_sig_calls.load(Ordering::Relaxed);
        let signature_is_signature_present_calls_before = signature_trace
            .is_signature_present_calls
            .load(Ordering::Relaxed);
        let signature_search_matches_before =
            signature_trace.search_matches.load(Ordering::Relaxed);
        let signature_search_quirks_before = signature_trace.search_quirks.load(Ordering::Relaxed);
        let signature_search_errors_before = signature_trace.search_errors.load(Ordering::Relaxed);
        let is_overlay_calls_before = signature_trace.is_overlay_calls.load(Ordering::Relaxed);
        let get_overlay_offset_calls_before = signature_trace
            .get_overlay_offset_calls
            .load(Ordering::Relaxed);
        let get_overlay_size_calls_before = signature_trace
            .get_overlay_size_calls
            .load(Ordering::Relaxed);
        let is_overlay_present_calls_before = signature_trace
            .is_overlay_present_calls
            .load(Ordering::Relaxed);
        let get_file_suffix_calls_before = signature_trace
            .get_file_suffix_calls
            .load(Ordering::Relaxed);
        let get_header_string_calls_before = signature_trace
            .get_header_string_calls
            .load(Ordering::Relaxed);
        let is_plain_text_calls_before =
            signature_trace.is_plain_text_calls.load(Ordering::Relaxed);
        let is_utf8_text_calls_before = signature_trace.is_utf8_text_calls.load(Ordering::Relaxed);
        interrupt_ticks.store(0, Ordering::Relaxed);
        let detect_result = eval_rule_lexical(&context, &evaluated, true);
        let signature_call_count = signature_trace
            .calls
            .load(Ordering::Relaxed)
            .saturating_sub(signature_calls_before);
        let signature_fast_path_count = signature_trace
            .fast_paths
            .load(Ordering::Relaxed)
            .saturating_sub(signature_fast_paths_before);
        let signature_generic_path_count = signature_trace
            .generic_paths
            .load(Ordering::Relaxed)
            .saturating_sub(signature_generic_paths_before);
        let signature_quirk_count = signature_trace
            .quirks
            .load(Ordering::Relaxed)
            .saturating_sub(signature_quirks_before);
        let signature_error_count = signature_trace
            .errors
            .load(Ordering::Relaxed)
            .saturating_sub(signature_errors_before);
        let signature_search_call_count = signature_trace
            .search_calls
            .load(Ordering::Relaxed)
            .saturating_sub(signature_search_calls_before);
        let signature_find_signature_call_count = signature_trace
            .find_signature_calls
            .load(Ordering::Relaxed)
            .saturating_sub(signature_find_signature_calls_before);
        let signature_f_sig_call_count = signature_trace
            .f_sig_calls
            .load(Ordering::Relaxed)
            .saturating_sub(signature_f_sig_calls_before);
        let signature_is_signature_present_call_count = signature_trace
            .is_signature_present_calls
            .load(Ordering::Relaxed)
            .saturating_sub(signature_is_signature_present_calls_before);
        let signature_search_match_count = signature_trace
            .search_matches
            .load(Ordering::Relaxed)
            .saturating_sub(signature_search_matches_before);
        let signature_search_quirk_count = signature_trace
            .search_quirks
            .load(Ordering::Relaxed)
            .saturating_sub(signature_search_quirks_before);
        let signature_search_error_count = signature_trace
            .search_errors
            .load(Ordering::Relaxed)
            .saturating_sub(signature_search_errors_before);
        let is_overlay_call_count = signature_trace
            .is_overlay_calls
            .load(Ordering::Relaxed)
            .saturating_sub(is_overlay_calls_before);
        let get_overlay_offset_call_count = signature_trace
            .get_overlay_offset_calls
            .load(Ordering::Relaxed)
            .saturating_sub(get_overlay_offset_calls_before);
        let get_overlay_size_call_count = signature_trace
            .get_overlay_size_calls
            .load(Ordering::Relaxed)
            .saturating_sub(get_overlay_size_calls_before);
        let is_overlay_present_call_count = signature_trace
            .is_overlay_present_calls
            .load(Ordering::Relaxed)
            .saturating_sub(is_overlay_present_calls_before);
        let get_file_suffix_call_count = signature_trace
            .get_file_suffix_calls
            .load(Ordering::Relaxed)
            .saturating_sub(get_file_suffix_calls_before);
        let get_header_string_call_count = signature_trace
            .get_header_string_calls
            .load(Ordering::Relaxed)
            .saturating_sub(get_header_string_calls_before);
        let is_plain_text_call_count = signature_trace
            .is_plain_text_calls
            .load(Ordering::Relaxed)
            .saturating_sub(is_plain_text_calls_before);
        let is_utf8_text_call_count = signature_trace
            .is_utf8_text_calls
            .load(Ordering::Relaxed)
            .saturating_sub(is_utf8_text_calls_before);
        let interrupt_handler_calls = interrupt_ticks.load(Ordering::Relaxed);
        let fallback_text = eval_string(
            &context,
            b"JSON.stringify({calls: __fallbackCalls, total: __fallbackTotal})",
        )?;
        let fallback: Value = serde_json::from_str(&fallback_text)
            .map_err(|error| format!("cannot parse fallback report for {name}: {error}"))?;
        let fallback_total = fallback
            .get("total")
            .and_then(Value::as_u64)
            .ok_or_else(|| format!("fallback total is missing for {name}"))?;
        let calls = fallback
            .get("calls")
            .and_then(Value::as_array)
            .ok_or_else(|| format!("fallback calls are missing for {name}"))?;
        for call in calls {
            if let Some(path) = call.as_str() {
                fallback_paths.insert(path.to_owned());
            }
        }
        fallback_call_total = fallback_call_total
            .checked_add(fallback_total)
            .ok_or_else(|| "fallback call total overflow".to_owned())?;
        fallback_rule_count += usize::from(fallback_total != 0);
        let detect_accepted = detect_result.is_ok();
        error_count += usize::from(!detect_accepted);
        let (detect_value, detect_error) = match detect_result {
            Ok(value) => (Some(value), None),
            Err(error) => (None, Some(error)),
        };
        let emitted = detections
            .lock()
            .map_err(|_| "Binary trace result mutex poisoned".to_owned())?[detections_before..]
            .to_vec();
        observations.push(json!({
            "index": index,
            "name": name,
            "accepted": detect_accepted,
            "detect_result": detect_value,
            "error": detect_error,
            "fallback_call_count": fallback_total,
            "fallback_calls": calls,
            "fallback_calls_truncated": fallback_total > calls.len() as u64,
            "signature_compare_call_count": signature_call_count,
            "signature_compare_fast_path_count": signature_fast_path_count,
            "signature_compare_generic_path_count": signature_generic_path_count,
            "signature_compare_quirk_count": signature_quirk_count,
            "signature_compare_error_count": signature_error_count,
            "signature_search_call_count": signature_search_call_count,
            "signature_find_signature_call_count": signature_find_signature_call_count,
            "signature_f_sig_call_count": signature_f_sig_call_count,
            "signature_is_signature_present_call_count":
                signature_is_signature_present_call_count,
            "signature_search_match_count": signature_search_match_count,
            "signature_search_quirk_count": signature_search_quirk_count,
            "signature_search_error_count": signature_search_error_count,
            "overlay_host_calls": {
                "is_overlay": is_overlay_call_count,
                "get_overlay_offset": get_overlay_offset_call_count,
                "get_overlay_size": get_overlay_size_call_count,
                "is_overlay_present": is_overlay_present_call_count,
            },
            "string_host_calls": {
                "get_file_suffix": get_file_suffix_call_count,
                "get_header_string": get_header_string_call_count,
                "is_plain_text": is_plain_text_call_count,
                "is_utf8_text": is_utf8_text_call_count,
            },
            "interrupt_handler_calls": interrupt_handler_calls,
            "detections": emitted,
        }));
    }
    let all_detections = detections
        .lock()
        .map_err(|_| "Binary trace result mutex poisoned".to_owned())?
        .clone();
    let include_trace_text = eval_string(&context, b"JSON.stringify(__includeTrace)")?;
    let include_trace: Value = serde_json::from_str(&include_trace_text)
        .map_err(|error| format!("cannot parse include trace: {error}"))?;
    let include_call_count = include_trace.as_array().map_or(0, Vec::len);
    let signature_unique_quirks = signature_trace
        .unique_quirks
        .lock()
        .map_err(|_| "signature quirk mutex poisoned".to_owned())?
        .clone();
    let signature_unique_errors = signature_trace
        .unique_errors
        .lock()
        .map_err(|_| "signature error mutex poisoned".to_owned())?
        .clone();
    let signature_search_unique_quirks = signature_trace
        .search_unique_quirks
        .lock()
        .map_err(|_| "signature search quirk mutex poisoned".to_owned())?
        .clone();
    let signature_search_unique_errors = signature_trace
        .search_unique_errors
        .lock()
        .map_err(|_| "signature search error mutex poisoned".to_owned())?
        .clone();
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({
            "schema_version": 1,
            "operation": "diagnostic invocation of all fixed-order Binary detect functions",
            "scope": "fallback-tolerant gap inventory; detections are not compatibility evidence",
            "runtime": "rquickjs 0.12.1 / QuickJS-NG 0.15.1",
            "input": {
                "path": normalized_path(input_path),
                "bytes": input_size,
            },
            "order_manifest": normalized_path(order_path),
            "order_sha256": LINUX_QT5_BINARY_ORDER_SHA256,
            "rule_count": order.len(),
            "attempted_detect_count": observations.len(),
            "accepted_detect_count": observations.len() - error_count,
            "detect_error_count": error_count,
            "compatibility_overlay_count": overlay_count,
            "include_trace": include_trace,
            "include_call_count": include_call_count,
            "fallback_rule_count": fallback_rule_count,
            "fallback_call_total": fallback_call_total,
            "fallback_paths": fallback_paths,
            "signature_compare_call_total": signature_trace.calls.load(Ordering::Relaxed),
            "signature_compare_fast_path_total":
                signature_trace.fast_paths.load(Ordering::Relaxed),
            "signature_compare_generic_path_total":
                signature_trace.generic_paths.load(Ordering::Relaxed),
            "signature_compare_quirk_total": signature_trace.quirks.load(Ordering::Relaxed),
            "signature_compare_error_total": signature_trace.errors.load(Ordering::Relaxed),
            "signature_compare_unique_quirks": signature_unique_quirks,
            "signature_compare_unique_errors": signature_unique_errors,
            "signature_search_call_total": signature_trace.search_calls.load(Ordering::Relaxed),
            "signature_find_signature_call_total":
                signature_trace.find_signature_calls.load(Ordering::Relaxed),
            "signature_f_sig_call_total": signature_trace.f_sig_calls.load(Ordering::Relaxed),
            "signature_is_signature_present_call_total":
                signature_trace.is_signature_present_calls.load(Ordering::Relaxed),
            "signature_search_match_total":
                signature_trace.search_matches.load(Ordering::Relaxed),
            "signature_search_quirk_total":
                signature_trace.search_quirks.load(Ordering::Relaxed),
            "signature_search_error_total":
                signature_trace.search_errors.load(Ordering::Relaxed),
            "signature_search_unique_quirks": signature_search_unique_quirks,
            "signature_search_unique_errors": signature_search_unique_errors,
            "overlay_host_call_totals": {
                "is_overlay": signature_trace.is_overlay_calls.load(Ordering::Relaxed),
                "get_overlay_offset":
                    signature_trace.get_overlay_offset_calls.load(Ordering::Relaxed),
                "get_overlay_size":
                    signature_trace.get_overlay_size_calls.load(Ordering::Relaxed),
                "is_overlay_present":
                    signature_trace.is_overlay_present_calls.load(Ordering::Relaxed),
            },
            "string_host_call_totals": {
                "get_file_suffix":
                    signature_trace.get_file_suffix_calls.load(Ordering::Relaxed),
                "get_header_string":
                    signature_trace.get_header_string_calls.load(Ordering::Relaxed),
                "is_plain_text":
                    signature_trace.is_plain_text_calls.load(Ordering::Relaxed),
                "is_utf8_text":
                    signature_trace.is_utf8_text_calls.load(Ordering::Relaxed),
            },
            "detection_count": all_detections.len(),
            "detections": all_detections,
            "observations": observations,
            "interrupt_handler_call_limit_per_rule": 1_000_000,
            "elapsed_ms": started.elapsed().as_millis(),
            "completed": true,
        }))
        .map_err(|error| format!("cannot serialize report: {error}"))?
    );
    Ok(true)
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

    const EXTERNAL_CANCEL_HARD_STOP_CALLS: usize = 1_000_000;
    let cancel_requested = Arc::new(AtomicBool::new(false));
    let cancel_handler_seen = Arc::new(AtomicBool::new(false));
    let cancel_handler_calls = Arc::new(AtomicUsize::new(0));
    let cancel_requested_for_handler = Arc::clone(&cancel_requested);
    let cancel_handler_seen_for_handler = Arc::clone(&cancel_handler_seen);
    let cancel_handler_calls_for_handler = Arc::clone(&cancel_handler_calls);
    let cancel_runtime = new_runtime()?;
    cancel_runtime.set_interrupt_handler(Some(Box::new(move || {
        let calls = cancel_handler_calls_for_handler.fetch_add(1, Ordering::Relaxed) + 1;
        cancel_handler_seen_for_handler.store(true, Ordering::Release);
        cancel_requested_for_handler.load(Ordering::Acquire)
            || calls >= EXTERNAL_CANCEL_HARD_STOP_CALLS
    })));
    let cancel_context = new_context(&cancel_runtime)?;
    let cancel_requested_for_worker = Arc::clone(&cancel_requested);
    let cancel_handler_seen_for_worker = Arc::clone(&cancel_handler_seen);
    let cancel_worker = thread::spawn(move || {
        while !cancel_handler_seen_for_worker.load(Ordering::Acquire) {
            thread::yield_now();
        }
        cancel_requested_for_worker.store(true, Ordering::Release);
    });
    let external_cancel_error = eval_unit(&cancel_context, b"for (;;) {}").err();
    cancel_worker
        .join()
        .map_err(|_| "external cancellation worker panicked".to_owned())?;
    let external_cancel_requested = cancel_requested.load(Ordering::Acquire);
    let external_cancel_handler_calls = cancel_handler_calls.load(Ordering::Relaxed);
    let external_cancel_hard_stop_reached =
        external_cancel_handler_calls >= EXTERNAL_CANCEL_HARD_STOP_CALLS;
    cancel_requested.store(false, Ordering::Release);
    cancel_handler_calls.store(0, Ordering::Relaxed);
    let external_cancel_recovery = eval_string(&cancel_context, b"String(40 + 2)");
    let external_cancel_recovered = external_cancel_recovery.as_deref() == Ok("42");

    const NATIVE_CANCEL_HARD_STOP_ITERATIONS: i32 = 1_000_000;
    let native_cancel_requested = Arc::new(AtomicBool::new(false));
    let native_host_entered = Arc::new(AtomicBool::new(false));
    let native_host_finished = Arc::new(AtomicBool::new(false));
    let native_cancel_requested_for_host = Arc::clone(&native_cancel_requested);
    let native_host_entered_for_host = Arc::clone(&native_host_entered);
    let native_cancel_runtime = new_runtime()?;
    let native_cancel_context = new_context(&native_cancel_runtime)?;
    native_cancel_context.with(|ctx| {
        let cooperative_host_loop = Function::new(ctx.clone(), move || {
            native_host_entered_for_host.store(true, Ordering::Release);
            let mut iterations = 0;
            loop {
                iterations += 1;
                if native_cancel_requested_for_host.load(Ordering::Acquire)
                    || iterations >= NATIVE_CANCEL_HARD_STOP_ITERATIONS
                {
                    return iterations;
                }
                thread::yield_now();
            }
        })
        .map_err(|error| error.to_string())?;
        ctx.globals()
            .set("cooperativeHostLoop", cooperative_host_loop)
            .map_err(|error| error.to_string())
    })?;
    let native_cancel_requested_for_worker = Arc::clone(&native_cancel_requested);
    let native_host_entered_for_worker = Arc::clone(&native_host_entered);
    let native_host_finished_for_worker = Arc::clone(&native_host_finished);
    let native_cancel_worker = thread::spawn(move || {
        while !native_host_entered_for_worker.load(Ordering::Acquire)
            && !native_host_finished_for_worker.load(Ordering::Acquire)
        {
            thread::yield_now();
        }
        if native_host_entered_for_worker.load(Ordering::Acquire) {
            native_cancel_requested_for_worker.store(true, Ordering::Release);
        }
    });
    let native_cancel_result =
        eval_string(&native_cancel_context, b"String(cooperativeHostLoop())");
    native_host_finished.store(true, Ordering::Release);
    native_cancel_worker
        .join()
        .map_err(|_| "native cancellation worker panicked".to_owned())?;
    let native_cancel_requested_observed = native_cancel_requested.load(Ordering::Acquire);
    let native_cancel_iterations = native_cancel_result
        .as_deref()
        .ok()
        .and_then(|value| value.parse::<i32>().ok());
    let native_cancel_hard_stop_reached =
        native_cancel_iterations == Some(NATIVE_CANCEL_HARD_STOP_ITERATIONS);

    const WALL_CLOCK_DEADLINE_MS: u64 = 25;
    const WALL_CLOCK_DEADLINE_HARD_STOP_CALLS: usize = 1_000_000;
    let wall_clock_deadline_started = Arc::new(Mutex::new(None::<Instant>));
    let wall_clock_deadline_calls = Arc::new(AtomicUsize::new(0));
    let wall_clock_deadline_started_for_handler = Arc::clone(&wall_clock_deadline_started);
    let wall_clock_deadline_calls_for_handler = Arc::clone(&wall_clock_deadline_calls);
    let wall_clock_deadline_runtime = new_runtime()?;
    wall_clock_deadline_runtime.set_interrupt_handler(Some(Box::new(move || {
        let calls = wall_clock_deadline_calls_for_handler.fetch_add(1, Ordering::Relaxed) + 1;
        let now = Instant::now();
        let expired = match wall_clock_deadline_started_for_handler.lock() {
            Ok(mut started) => {
                let started = *started.get_or_insert(now);
                now.duration_since(started) >= Duration::from_millis(WALL_CLOCK_DEADLINE_MS)
            }
            Err(_) => true,
        };
        expired || calls >= WALL_CLOCK_DEADLINE_HARD_STOP_CALLS
    })));
    let wall_clock_deadline_context = new_context(&wall_clock_deadline_runtime)?;
    let wall_clock_deadline_error = eval_unit(&wall_clock_deadline_context, b"for (;;) {}").err();
    let wall_clock_deadline_calls_observed = wall_clock_deadline_calls.load(Ordering::Relaxed);
    let wall_clock_deadline_hard_stop_reached =
        wall_clock_deadline_calls_observed >= WALL_CLOCK_DEADLINE_HARD_STOP_CALLS;
    let wall_clock_deadline_expired = wall_clock_deadline_started
        .lock()
        .map_err(|_| "wall-clock deadline state mutex poisoned".to_owned())?
        .is_some_and(|started| started.elapsed() >= Duration::from_millis(WALL_CLOCK_DEADLINE_MS));
    wall_clock_deadline_runtime.set_interrupt_handler(None);
    let wall_clock_deadline_recovery = eval_string(&wall_clock_deadline_context, b"String(21 * 2)");

    const NATIVE_DEADLINE_HARD_STOP_ITERATIONS: i32 = 10_000_000;
    let native_deadline = Arc::new(Mutex::new(None::<Instant>));
    let native_deadline_for_host = Arc::clone(&native_deadline);
    let native_deadline_runtime = new_runtime()?;
    let native_deadline_context = new_context(&native_deadline_runtime)?;
    native_deadline_context.with(|ctx| {
        let deadline_host_loop = Function::new(ctx.clone(), move || {
            let deadline = native_deadline_for_host
                .lock()
                .ok()
                .and_then(|deadline| *deadline);
            let Some(deadline) = deadline else {
                return -1;
            };
            let mut iterations = 0;
            loop {
                iterations += 1;
                if Instant::now() >= deadline || iterations >= NATIVE_DEADLINE_HARD_STOP_ITERATIONS
                {
                    return iterations;
                }
                thread::yield_now();
            }
        })
        .map_err(|error| error.to_string())?;
        ctx.globals()
            .set("deadlineHostLoop", deadline_host_loop)
            .map_err(|error| error.to_string())
    })?;
    let native_deadline_at = Instant::now() + Duration::from_millis(WALL_CLOCK_DEADLINE_MS);
    *native_deadline
        .lock()
        .map_err(|_| "native deadline state mutex poisoned".to_owned())? = Some(native_deadline_at);
    let native_deadline_result =
        eval_string(&native_deadline_context, b"String(deadlineHostLoop())");
    let native_deadline_iterations = native_deadline_result
        .as_deref()
        .ok()
        .and_then(|value| value.parse::<i32>().ok());
    let native_deadline_expired = Instant::now() >= native_deadline_at;
    let native_deadline_hard_stop_reached =
        native_deadline_iterations == Some(NATIVE_DEADLINE_HARD_STOP_ITERATIONS);
    let native_deadline_recovery = eval_string(&native_deadline_context, b"String(21 * 2)");

    let numeric_runtime = new_runtime()?;
    let numeric_context = new_context(&numeric_runtime)?;
    install_nintendo_host(
        &numeric_context,
        Arc::new(vec![b'A', b'B', b'C', 0, 0x12, 0x34, 0x56]),
        Arc::new(Mutex::new(Vec::new())),
    )?;
    let numeric_result_text = eval_string(
        &numeric_context,
        br#"JSON.stringify([
            X.U24(4),
            X.U24(4, true),
            X.read_uint24(4, true),
            Util.shru64(4294967295, 0),
            Util.shru64(4294967295, 4),
            Util.shru64(4294967295, 32)
        ])"#,
    )?;
    let numeric_result: Value = serde_json::from_str(&numeric_result_text)
        .map_err(|error| format!("cannot parse numeric HostApi fixture: {error}"))?;
    let numeric_expected = json!([
        0x563412_u64,
        0x123456_u64,
        0x123456_u64,
        0xFFFFFFFF_u64,
        0x0FFFFFFF_u64,
        0_u64,
    ]);

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
        && external_cancel_error.is_some()
        && external_cancel_requested
        && !external_cancel_hard_stop_reached
        && external_cancel_recovered
        && native_cancel_requested_observed
        && native_cancel_iterations.is_some_and(|iterations| {
            (1..NATIVE_CANCEL_HARD_STOP_ITERATIONS).contains(&iterations)
        })
        && !native_cancel_hard_stop_reached
        && wall_clock_deadline_error.is_some()
        && wall_clock_deadline_expired
        && !wall_clock_deadline_hard_stop_reached
        && wall_clock_deadline_recovery.as_deref() == Ok("42")
        && native_deadline_iterations.is_some_and(|iterations| {
            (1..NATIVE_DEADLINE_HARD_STOP_ITERATIONS).contains(&iterations)
        })
        && native_deadline_expired
        && !native_deadline_hard_stop_reached
        && native_deadline_recovery.as_deref() == Ok("42")
        && numeric_result == numeric_expected
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
        "external_cancel": {
            "requested": external_cancel_requested,
            "handler_calls": external_cancel_handler_calls,
            "hard_stop_handler_call_limit": EXTERNAL_CANCEL_HARD_STOP_CALLS,
            "hard_stop_reached": external_cancel_hard_stop_reached,
            "error": external_cancel_error,
            "same_context_recovery": {
                "accepted": external_cancel_recovery.is_ok(),
                "result": external_cancel_recovery.as_deref().ok(),
                "error": external_cancel_recovery.as_ref().err(),
            },
        },
        "native_host_cooperative_cancel": {
            "requested": native_cancel_requested_observed,
            "result": native_cancel_result.as_deref().ok(),
            "error": native_cancel_result.as_ref().err(),
            "iterations": native_cancel_iterations,
            "hard_stop_iteration_limit": NATIVE_CANCEL_HARD_STOP_ITERATIONS,
            "hard_stop_reached": native_cancel_hard_stop_reached,
        },
        "wall_clock_deadline": {
            "milliseconds": WALL_CLOCK_DEADLINE_MS,
            "handler_calls": wall_clock_deadline_calls_observed,
            "expired": wall_clock_deadline_expired,
            "hard_stop_handler_call_limit": WALL_CLOCK_DEADLINE_HARD_STOP_CALLS,
            "hard_stop_reached": wall_clock_deadline_hard_stop_reached,
            "error": wall_clock_deadline_error,
            "same_context_recovery": {
                "result": wall_clock_deadline_recovery.as_deref().ok(),
                "error": wall_clock_deadline_recovery.as_ref().err(),
            },
        },
        "native_host_cooperative_deadline": {
            "milliseconds": WALL_CLOCK_DEADLINE_MS,
            "expired": native_deadline_expired,
            "result": native_deadline_result.as_deref().ok(),
            "error": native_deadline_result.as_ref().err(),
            "iterations": native_deadline_iterations,
            "hard_stop_iteration_limit": NATIVE_DEADLINE_HARD_STOP_ITERATIONS,
            "hard_stop_reached": native_deadline_hard_stop_reached,
            "same_context_recovery": {
                "result": native_deadline_recovery.as_deref().ok(),
                "error": native_deadline_recovery.as_ref().err(),
            },
        },
        "numeric_host_api": {
            "methods": ["X.U24", "X.read_uint24", "Util.shru64"],
            "result": numeric_result,
            "expected": numeric_expected,
            "matches_qt5_qt6_oracle": numeric_result == numeric_expected,
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
         <eval-binary-lifecycle|eval-binary-lifecycle-raw|eval-binary-lifecycle-lexical> \
         <main-rule-root> <binary-order-json>\n       \
         diec-rquickjs-rule-runtime-spike \
         <eval-scope-fixture|eval-scope-fixture-lexical> \
         <fixture-root> <fixture-manifest-json> <qt5-baseline-json>\n       \
         diec-rquickjs-rule-runtime-spike detect-nintendo \
         <main-rule-root> <corpus-dir> <baseline-json>\n       \
         diec-rquickjs-rule-runtime-spike detect-nintendo-lifecycle \
         <main-rule-root> <corpus-dir> <baseline-json> <binary-order-json>\n       \
         diec-rquickjs-rule-runtime-spike trace-binary-detects \
         <main-rule-root> <input-file> <binary-order-json>"
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
        run_binary_lifecycle(&roots[0], &roots[1], true, false)
    } else if command == "eval-binary-lifecycle-raw" && roots.len() == 2 {
        run_binary_lifecycle(&roots[0], &roots[1], false, false)
    } else if command == "eval-binary-lifecycle-lexical" && roots.len() == 2 {
        run_binary_lifecycle(&roots[0], &roots[1], false, true)
    } else if command == "eval-scope-fixture" && roots.len() == 3 {
        run_scope_fixture(&roots[0], &roots[1], &roots[2], false)
    } else if command == "eval-scope-fixture-lexical" && roots.len() == 3 {
        run_scope_fixture(&roots[0], &roots[1], &roots[2], true)
    } else if command == "detect-nintendo" && roots.len() == 3 {
        run_nintendo_corpus(&roots[0], &roots[1], &roots[2])
    } else if command == "detect-nintendo-lifecycle" && roots.len() == 4 {
        run_nintendo_lifecycle_corpus(&roots[0], &roots[1], &roots[2], &roots[3])
    } else if command == "trace-binary-detects" && roots.len() == 3 {
        trace_binary_detects(&roots[0], &roots[1], &roots[2])
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
        BinaryHostContext, BinaryStringContext, HostFilePart, NINTENDO_COMPAT_DECLARATION,
        NINTENDO_RULE_BYTES, NINTENDO_VAR_DECLARATION, TextUnicodeType,
        apply_compatibility_overlay, apply_exact_lifecycle_overlay, collect_rule_files,
        eval_rule_lexical, eval_string, eval_unit, install_diagnostic_host_fallbacks,
        install_nintendo_host, install_nintendo_host_with_context,
        install_nintendo_host_with_context_and_strings, new_context, new_runtime,
        nonnegative_index, normalized_path, parse_scope_detections, parse_scope_fixture_order,
        read_ascii, read_byte_array, read_signed, read_unsigned, shift_right_unsigned,
    };
    use std::fs;
    use std::path::PathBuf;
    use std::sync::atomic::Ordering;
    use std::sync::{Arc, Mutex};
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

    fn decode_hex(value: &str) -> Vec<u8> {
        assert_eq!(value.len() % 2, 0, "hex fixture must have complete bytes");
        value
            .as_bytes()
            .chunks_exact(2)
            .map(|pair| {
                let text = std::str::from_utf8(pair).expect("hex fixture must be ASCII");
                u8::from_str_radix(text, 16).expect("hex fixture must contain digits")
            })
            .collect()
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
        assert_eq!(read_unsigned(&bytes, 0, 3, true), 0x123456 as f64);
        assert_eq!(read_unsigned(&bytes, 0, 3, false), 0x563412 as f64);
        assert_eq!(read_unsigned(&bytes, 0, 4, true), 0x12345678 as f64);
        assert_eq!(read_unsigned(&bytes, 3, 2, true), 0.0);
    }

    #[test]
    fn unsigned_shift_accepts_defined_safe_integer_range() {
        assert_eq!(
            shift_right_unsigned(0xFFFFFFFF_u64 as f64, 0).expect("zero shift should succeed"),
            0xFFFFFFFF_u64 as f64
        );
        assert_eq!(
            shift_right_unsigned(0xFFFFFFFF_u64 as f64, 4).expect("four-bit shift should succeed"),
            0x0FFFFFFF_u64 as f64
        );
        assert_eq!(
            shift_right_unsigned(0xFFFFFFFF_u64 as f64, 32).expect("32-bit shift should succeed"),
            0.0
        );
        assert!(shift_right_unsigned(-1.0, 1).is_err());
        assert!(shift_right_unsigned(1.5, 1).is_err());
        assert!(shift_right_unsigned(f64::NAN, 1).is_err());
        assert!(shift_right_unsigned(1.0, 64).is_err());
    }

    #[test]
    fn signature_adapter_exposes_compare_search_and_explicit_diagnostics() {
        let runtime = new_runtime().expect("runtime should be created");
        let context = new_context(&runtime).expect("context should be created");
        let mut bytes = vec![0_u8; 300];
        bytes[0..8].copy_from_slice(b"SCE\0\0\0\0\x02");
        bytes[16..23].copy_from_slice(b"\x7fELF\0\0\x01");
        bytes[253] = b'A';
        let trace =
            install_nintendo_host(&context, Arc::new(bytes), Arc::new(Mutex::new(Vec::new())))
                .expect("host should be installed");

        assert_eq!(
            eval_string(
                &context,
                br#"String(X.c("'SCE'00", 0)) + "|" +
                    String(Binary.compare("41x", 253)) + "|" +
                    String(Binary.findSignature(0, -1, "'SCE'")) + "|" +
                    String(X.fSig(1, 10, "4345")) + "|" +
                    String(Binary.isSignaturePresent(0, 8, "'ELF'"))"#,
            )
            .expect("supported signatures should be evaluated"),
            "true|true|0|1|false"
        );
        eval_unit(&context, b"Binary.compare('unsupported', 253)")
            .expect_err("unknown syntax must be an explicit diagnostic");
        eval_unit(&context, b"Binary.findSignature(0, -1, 'unsupported')")
            .expect_err("unknown search syntax must be an explicit diagnostic");
        assert_eq!(trace.calls.load(Ordering::Relaxed), 3);
        assert_eq!(trace.fast_paths.load(Ordering::Relaxed), 1);
        assert_eq!(trace.generic_paths.load(Ordering::Relaxed), 1);
        assert_eq!(trace.quirks.load(Ordering::Relaxed), 1);
        assert_eq!(trace.errors.load(Ordering::Relaxed), 1);
        assert_eq!(trace.search_calls.load(Ordering::Relaxed), 4);
        assert_eq!(trace.find_signature_calls.load(Ordering::Relaxed), 2);
        assert_eq!(trace.f_sig_calls.load(Ordering::Relaxed), 1);
        assert_eq!(trace.is_signature_present_calls.load(Ordering::Relaxed), 1);
        assert_eq!(trace.search_matches.load(Ordering::Relaxed), 2);
        assert_eq!(trace.search_quirks.load(Ordering::Relaxed), 0);
        assert_eq!(trace.search_errors.load(Ordering::Relaxed), 1);
    }

    #[test]
    fn overlay_host_context_keeps_file_part_and_nested_overlay_independent() {
        let cases = [
            (
                vec![0_u8; 256],
                BinaryHostContext::new(HostFilePart::Header, 256, 0)
                    .expect("fixed context should be valid"),
                "false|256|0|false",
            ),
            (
                vec![0_u8; 1],
                BinaryHostContext::new(HostFilePart::Overlay, 1, 0)
                    .expect("fixed context should be valid"),
                "true|1|0|false",
            ),
            (
                vec![0_u8; 2048],
                BinaryHostContext::new(HostFilePart::Header, 1536, 512)
                    .expect("fixed context should be valid"),
                "false|1536|512|true",
            ),
        ];
        for (bytes, host_context, expected) in cases {
            let runtime = new_runtime().expect("runtime should be created");
            let context = new_context(&runtime).expect("context should be created");
            let trace = install_nintendo_host_with_context(
                &context,
                Arc::new(bytes),
                Arc::new(Mutex::new(Vec::new())),
                host_context,
            )
            .expect("host should be installed");
            assert_eq!(
                eval_string(
                    &context,
                    br#"String(Binary.isOverlay()) + "|" +
                        String(Binary.getOverlayOffset()) + "|" +
                        String(Binary.getOverlaySize()) + "|" +
                        String(Binary.isOverlayPresent())"#,
                )
                .expect("overlay HostApi should be callable"),
                expected
            );
            assert_eq!(trace.is_overlay_calls.load(Ordering::Relaxed), 1);
            assert_eq!(trace.get_overlay_offset_calls.load(Ordering::Relaxed), 1);
            assert_eq!(trace.get_overlay_size_calls.load(Ordering::Relaxed), 1);
            assert_eq!(trace.is_overlay_present_calls.load(Ordering::Relaxed), 1);
        }
        assert!(BinaryHostContext::new(HostFilePart::Header, 0, -1).is_err());
    }

    #[test]
    fn string_context_matches_pinned_qt5_oracle() {
        let oracle: serde_json::Value = serde_json::from_str(include_str!(
            "../../../docs/research/data/signature-oracle-qt5.json"
        ))
        .expect("Qt5 signature oracle should be valid JSON");
        let cases = oracle["cases"]
            .as_array()
            .expect("Qt5 signature oracle should contain cases");
        let mut checked = 0_usize;
        for case in cases {
            if case["binary_script_string_info"].as_bool() != Some(true) {
                continue;
            }
            checked += 1;
            let id = case["id"].as_str().expect("oracle case should have an id");
            let data = decode_hex(
                case["data_hex"]
                    .as_str()
                    .expect("oracle case should have data"),
            );
            let file_name = case["file_name"].as_str().unwrap_or("");
            let actual = BinaryStringContext::from_file_name(&data, file_name);
            assert_eq!(
                actual.file_suffix,
                case["binary_script_get_file_suffix_result"]
                    .as_str()
                    .expect("oracle suffix should be a string"),
                "suffix mismatch for {id}"
            );
            assert_eq!(
                actual.header_string,
                case["binary_script_get_header_string_result"]
                    .as_str()
                    .expect("oracle header should be a string"),
                "header mismatch for {id}"
            );
            assert_eq!(
                actual.is_plain_text,
                case["binary_script_is_plain_text_result"]
                    .as_bool()
                    .expect("oracle plain-text flag should be a bool"),
                "plain-text mismatch for {id}"
            );
            assert_eq!(
                actual.is_utf8_text,
                case["binary_script_is_utf8_text_result"]
                    .as_bool()
                    .expect("oracle UTF-8 flag should be a bool"),
                "UTF-8 mismatch for {id}"
            );
            let expected_unicode = match case["x_binary_unicode_type_result"]
                .as_str()
                .expect("oracle Unicode type should be a string")
            {
                "none" => TextUnicodeType::None,
                "little" => TextUnicodeType::Little,
                "big" => TextUnicodeType::Big,
                other => panic!("unexpected oracle Unicode type: {other}"),
            };
            assert_eq!(
                actual.unicode_type, expected_unicode,
                "Unicode type mismatch for {id}"
            );
        }
        assert_eq!(checked, 15);
    }

    #[test]
    fn string_context_is_exposed_as_native_host_api() {
        let runtime = new_runtime().expect("runtime should be created");
        let context = new_context(&runtime).expect("context should be created");
        let bytes = Arc::new(b"function test() {}\n".to_vec());
        let host_context =
            BinaryHostContext::identity_header(bytes.len()).expect("fixed context should be valid");
        let string_context = BinaryStringContext::from_file_name(&bytes, "sample.C");
        let trace = install_nintendo_host_with_context_and_strings(
            &context,
            bytes,
            Arc::new(Mutex::new(Vec::new())),
            host_context,
            string_context,
        )
        .expect("host should be installed");
        assert_eq!(
            eval_string(
                &context,
                br#"Binary.getFileSuffix() + "|" +
                    Binary.getHeaderString() + "|" +
                    String(Binary.isPlainText()) + "|" +
                    String(Binary.isUTF8Text())"#,
            )
            .expect("string HostApi should be callable"),
            "C|function test() {}\n|true|false"
        );
        assert_eq!(trace.get_file_suffix_calls.load(Ordering::Relaxed), 1);
        assert_eq!(trace.get_header_string_calls.load(Ordering::Relaxed), 1);
        assert_eq!(trace.is_plain_text_calls.load(Ordering::Relaxed), 1);
        assert_eq!(trace.is_utf8_text_calls.load(Ordering::Relaxed), 1);
    }

    #[test]
    fn ascii_host_read_is_nul_terminated_and_bounds_checked() {
        let bytes = b"SC\0trailing";
        assert_eq!(read_ascii(bytes, 0, bytes.len()), "SC");
        assert_eq!(read_ascii(bytes, 3, 4), "trai");
        assert_eq!(read_ascii(b"abc", 1, 50), "bc");
        assert_eq!(read_ascii(bytes, bytes.len(), 1), "");
    }

    #[test]
    fn signed_and_byte_array_host_reads_are_bounded() {
        assert_eq!(read_signed(&[0xff], 0, 1, false), -1.0);
        assert_eq!(read_signed(&[0x80, 0x00], 0, 2, true), -32768.0);
        assert_eq!(read_signed(&[0x80], 1, 1, false), 0.0);
        assert_eq!(read_byte_array(b"a\0b", 0, 20, false), b"a\0b");
        assert_eq!(read_byte_array(b"a\0b", 0, 20, true), b"a b");
        assert!(read_byte_array(b"abc", -1, 1, false).is_empty());
        assert!(read_byte_array(b"abc", 0, -1, false).is_empty());
    }

    #[test]
    fn host_offsets_reject_negative_values_without_conversion_errors() {
        assert_eq!(nonnegative_index(-1), None);
        assert_eq!(nonnegative_index(0), Some(0));
        assert_eq!(nonnegative_index(128), Some(128));
    }

    #[test]
    fn diagnostic_fallback_counts_all_calls_and_caps_captured_paths() {
        let runtime = new_runtime().expect("runtime should be created");
        let context = new_context(&runtime).expect("context should be created");
        eval_unit(
            &context,
            b"var Binary = { c: function () { return false; } }; var Util = {};",
        )
        .expect("fallback globals should be initialized");
        install_diagnostic_host_fallbacks(&context).expect("fallback should be installed");
        eval_unit(&context, b"for (var i = 0; i < 300; i++) Binary.missing();")
            .expect("fallback calls should complete");
        assert_eq!(
            eval_string(
                &context,
                b"String(__fallbackTotal) + '|' + String(__fallbackCalls.length)",
            )
            .expect("fallback counters should be readable"),
            "300|256"
        );
    }

    #[test]
    fn scope_fixture_order_rejects_wrong_inventory() {
        let document = serde_json::json!({
            "generator": "tools/corpus/generate_script_scope_fixture.py",
            "rule_order": ["only-one.sg"],
        });
        let error = parse_scope_fixture_order(&document)
            .expect_err("incomplete scope fixture must be rejected");
        assert!(error.contains("expected 7"));
    }

    #[test]
    fn scope_detections_parse_qt5_shape() {
        let document = serde_json::json!({
            "detections": [{
                "type": "format",
                "name": "Scope",
                "version": "2",
                "info": "",
            }],
        });
        assert_eq!(
            parse_scope_detections(&document).expect("fixed shape should parse"),
            [(
                "format".to_owned(),
                "Scope".to_owned(),
                "2".to_owned(),
                String::new(),
            )]
        );
    }

    #[test]
    fn lexical_wrapper_isolates_rule_bindings_and_returns_detect() {
        let runtime = new_runtime().expect("runtime should be created");
        let context = new_context(&runtime).expect("context should be created");
        assert_eq!(
            eval_rule_lexical(
                &context,
                b"const value = 1; function detect() { return value; }",
                true,
            )
            .expect("first rule should evaluate"),
            "1"
        );
        assert_eq!(
            eval_rule_lexical(
                &context,
                b"value = 2; function detect() { return value; }",
                true,
            )
            .expect("prior const must not make this assignment read-only"),
            "2"
        );
        assert_eq!(
            eval_rule_lexical(&context, b"function detect() { return 'function'; }", true,)
                .expect("function detect should evaluate"),
            "function"
        );
        assert_eq!(
            eval_rule_lexical(
                &context,
                b"const detect = main; function main() { return 'const'; }",
                true,
            )
            .expect("const detect must not conflict with the prior rule"),
            "const"
        );
    }
}
