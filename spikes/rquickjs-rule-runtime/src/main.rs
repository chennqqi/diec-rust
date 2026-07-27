#![recursion_limit = "256"]

use std::collections::{BTreeMap, BTreeSet};
use std::env;
use std::fs;
use std::panic::{self, AssertUnwindSafe};
use std::path::{Path, PathBuf};
use std::process::ExitCode;
use std::sync::Arc;
use std::sync::Mutex;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::thread;
use std::time::{Duration, Instant};

use diec_signature_parser_spike::{Endian, FileType, MemoryMap, MemoryRecord, Pattern};

use rquickjs::{
    CatchResultExt, Context, Error, Function, Object, Runtime, context::EvalOptions, function::Opt,
};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};

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
const XSCANENGINE_COMMIT: &str = "dfe4a419e4f491bb23688ba03c5a5bf39e34da83";
const RULES_COMMIT: &str = "c2c17dfa5ea4e078ba31eab55d87430c96622fb6";
const LINUX_QT5_BINARY_ORDER_SHA256: &str =
    "27138d68ed788dd2609b7c533fecf540593fa2e4ddb7195adc26b1a9ff0e1ff3";
const NINTENDO_CORPUS_MANIFEST_SHA256: &str =
    "eac3ad62c7f21d5112ee1ca73fbb6cc4e5306b6004357aeaf86144fa3ef51a03";
const NINTENDO_BASELINE_SHA256: &str =
    "683d2d85abc7053321785f53224842cd2047427d4d8ce6d591248453e2f29503";
const BINARY_SIGNATURE_COUNT: usize = 292;
const PE_RULE_SUFFIX: &str = "PE/compiler_Cygwin32.4.sg";
const PE_RULE_BYTES: usize = 240;
const PE_RULE_SHA256: &str = "de563e3333c54b966efb7aa3d678acd56ca5fa9b83a7b8356b3a4e71e47dc4cd";
const PE_FIXTURE_SHA256: &str = "102eacfa044f838fb51992c65a2cf7e90cd346a493bffc77b08f4ec02f5159e1";
const PE_QT5_BASELINE_SHA256: &str =
    "645fc9b13d500f1eda3203df90439cb5234f8eb850d820de119962b4778be03a";
const ELF_RULE_SUFFIX: &str = "ELF/protector_Burneye.2.sg";
const ELF_RULE_BYTES: usize = 282;
const ELF_RULE_SHA256: &str = "35461b495f056d98de9af44eda91df3c6412d22555b182834af9b6a68842d44c";
const ELF_FIXTURE_SHA256: &str = "b3547482b2013a993a36262860f82dbda69b1588898cd2a8020124c6b9aad5b4";
const ELF_QT5_BASELINE_SHA256: &str =
    "edf2d32cde44c8fcf010190e48cc33076dcb1dc0ea81830996eeab7a57f89410";
const FORMATS_COMMIT: &str = "1151e7254fdee3c0294ff7095edbdd7bfccf8201";
const FORMAT_RESULT_SHIM: &[u8] = br#"
    var bDetected, sType, sName, sVersion, sOptions;
    function meta(type, name, version, options) {
        sType = type;
        sName = name ? name : String();
        sVersion = version ? version : String();
        sOptions = options ? options : String();
        bDetected = false;
    }
    function _error(message) { throw new Error(String(message)); }
    function result() {
        if (bDetected) {
            sVersion = sVersion ? sVersion : String();
            sOptions = sOptions ? sOptions : String();
            if (!sName) _error("No input detection name.");
            _setResult(sType, sName, sVersion, sOptions);
        }
        sName = sVersion = sOptions = "";
        var value = bDetected;
        bDetected = false;
        return value;
    }
"#;

type Detection = (String, String, String, String);
type DetectionTriple = (String, String, String);
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
    is_unicode_text_calls: AtomicUsize,
    is_text_calls: AtomicUsize,
    get_scan_id_calls: AtomicUsize,
    is_resource_calls: AtomicUsize,
    is_debug_data_calls: AtomicUsize,
    is_file_part_calls: AtomicUsize,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum HostFilePart {
    Header,
    Overlay,
    Resource,
    DebugData,
}

#[derive(Clone, Debug, Eq, PartialEq)]
struct BinaryHostContext {
    file_part: HostFilePart,
    overlay_offset: i64,
    overlay_size: i64,
    scan_id: String,
}

#[derive(Clone, Debug, Eq, PartialEq)]
struct PeRuleContext {
    entry_point_offset: Option<usize>,
    memory_map: MemoryMap,
    aliased_out_of_bounds_sections: usize,
}

#[derive(Clone, Debug, Eq, PartialEq)]
struct ElfRuleContext {
    elf_class: u8,
    entry_point_offset: Option<usize>,
    memory_map: MemoryMap,
    out_of_bounds_loads: usize,
}

#[derive(Default)]
struct EntryPointHostTrace {
    compare_ep_calls: AtomicUsize,
    fast_paths: AtomicUsize,
    generic_paths: AtomicUsize,
    errors: AtomicUsize,
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

    fn is_unicode_text(&self) -> bool {
        self.unicode_type != TextUnicodeType::None
    }

    fn is_text(&self) -> bool {
        self.is_plain_text || self.is_utf8_text || self.is_unicode_text()
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
            scan_id: String::new(),
        })
    }

    fn with_scan_id(mut self, scan_id: impl Into<String>) -> Self {
        self.scan_id = scan_id.into();
        self
    }

    fn identity_header(data_len: usize) -> Result<Self, String> {
        Self::new(
            HostFilePart::Header,
            i64::try_from(data_len)
                .map_err(|_| "Binary input length does not fit qint64".to_owned())?,
            0,
        )
        .map(|context| context.with_scan_id(""))
    }

    fn is_overlay(&self) -> bool {
        self.file_part == HostFilePart::Overlay
    }

    fn is_overlay_present(&self) -> bool {
        self.overlay_size != 0
    }

    fn is_resource(&self) -> bool {
        self.file_part == HostFilePart::Resource
    }

    fn is_debug_data(&self) -> bool {
        self.file_part == HostFilePart::DebugData
    }

    fn is_file_part(&self) -> bool {
        self.file_part != HostFilePart::Header
    }
}

fn pe_u16(data: &[u8], offset: usize) -> Option<u16> {
    let bytes: [u8; 2] = data.get(offset..offset.checked_add(2)?)?.try_into().ok()?;
    Some(u16::from_le_bytes(bytes))
}

fn pe_u32(data: &[u8], offset: usize) -> Option<u32> {
    let bytes: [u8; 4] = data.get(offset..offset.checked_add(4)?)?.try_into().ok()?;
    Some(u32::from_le_bytes(bytes))
}

fn pe_u64(data: &[u8], offset: usize) -> Option<u64> {
    let bytes: [u8; 8] = data.get(offset..offset.checked_add(8)?)?.try_into().ok()?;
    Some(u64::from_le_bytes(bytes))
}

fn pe_field(base: usize, relative: usize, name: &str) -> Result<usize, String> {
    base.checked_add(relative)
        .ok_or_else(|| format!("PE {name} offset overflow"))
}

impl PeRuleContext {
    fn parse(data: &[u8]) -> Result<Self, String> {
        if data.get(0..2) != Some(b"MZ") {
            return Err("PE DOS signature is missing".to_owned());
        }
        let pe_offset = usize::try_from(
            pe_u32(data, 0x3c).ok_or_else(|| "PE e_lfanew is truncated".to_owned())?,
        )
        .map_err(|_| "PE e_lfanew does not fit usize".to_owned())?;
        let signature_end = pe_field(pe_offset, 4, "signature end")?;
        if data.get(pe_offset..signature_end) != Some(b"PE\0\0") {
            return Err("PE signature is missing or truncated".to_owned());
        }
        let coff = signature_end;
        let section_count = usize::from(
            pe_u16(data, pe_field(coff, 2, "section count")?)
                .ok_or_else(|| "PE COFF header is truncated".to_owned())?,
        );
        if section_count > 96 {
            return Err(format!(
                "PE section count {section_count} exceeds spike limit 96"
            ));
        }
        let optional_size = usize::from(
            pe_u16(data, pe_field(coff, 16, "optional header size")?)
                .ok_or_else(|| "PE COFF header is truncated".to_owned())?,
        );
        let optional = pe_field(coff, 20, "optional header")?;
        let optional_end = optional
            .checked_add(optional_size)
            .ok_or_else(|| "PE optional header size overflow".to_owned())?;
        if optional_end > data.len() {
            return Err("PE optional header is truncated".to_owned());
        }
        let magic =
            pe_u16(data, optional).ok_or_else(|| "PE optional magic is truncated".to_owned())?;
        let image_base = match magic {
            0x10b => u64::from(
                pe_u32(data, pe_field(optional, 28, "PE32 image base")?)
                    .ok_or_else(|| "PE32 image base is truncated".to_owned())?,
            ),
            0x20b => pe_u64(data, pe_field(optional, 24, "PE32+ image base")?)
                .ok_or_else(|| "PE32+ image base is truncated".to_owned())?,
            other => {
                return Err(format!(
                    "unsupported PE optional header magic 0x{other:04x}"
                ));
            }
        };
        let entry_rva = u64::from(
            pe_u32(data, pe_field(optional, 16, "entry point RVA")?)
                .ok_or_else(|| "PE entry point RVA is truncated".to_owned())?,
        );
        let size_of_headers = u64::from(
            pe_u32(data, pe_field(optional, 60, "SizeOfHeaders")?)
                .ok_or_else(|| "PE SizeOfHeaders is truncated".to_owned())?,
        );
        let section_table_size = section_count
            .checked_mul(40)
            .ok_or_else(|| "PE section table size overflow".to_owned())?;
        let section_table_end = optional_end
            .checked_add(section_table_size)
            .ok_or_else(|| "PE section table offset overflow".to_owned())?;
        if section_table_end > data.len() {
            return Err("PE section table is truncated".to_owned());
        }

        let mut records = Vec::with_capacity(section_count.saturating_add(1));
        let mut aliased_out_of_bounds_sections = 0_usize;
        let header_size = usize::try_from(size_of_headers)
            .unwrap_or(usize::MAX)
            .min(data.len());
        if header_size != 0 {
            records.push(MemoryRecord {
                offset: 0,
                address: image_base,
                size: header_size as u64,
            });
        }
        let mut entry_point_offset = (entry_rva < size_of_headers)
            .then(|| usize::try_from(entry_rva).ok())
            .flatten()
            .filter(|offset| *offset < data.len());
        for index in 0..section_count {
            let section = optional_end
                .checked_add(
                    index
                        .checked_mul(40)
                        .ok_or_else(|| "PE section offset overflow".to_owned())?,
                )
                .ok_or_else(|| "PE section offset overflow".to_owned())?;
            let virtual_size = u64::from(
                pe_u32(data, pe_field(section, 8, "section virtual size")?)
                    .ok_or_else(|| "PE section header is truncated".to_owned())?,
            );
            let virtual_address = u64::from(
                pe_u32(data, pe_field(section, 12, "section virtual address")?)
                    .ok_or_else(|| "PE section header is truncated".to_owned())?,
            );
            let raw_size = u64::from(
                pe_u32(data, pe_field(section, 16, "section raw size")?)
                    .ok_or_else(|| "PE section header is truncated".to_owned())?,
            );
            let raw_offset = u64::from(
                pe_u32(data, pe_field(section, 20, "section raw offset")?)
                    .ok_or_else(|| "PE section header is truncated".to_owned())?,
            );
            let address = image_base
                .checked_add(virtual_address)
                .ok_or_else(|| "PE section address overflow".to_owned())?;
            let physical_offset = usize::try_from(raw_offset).ok().map(|offset| {
                if offset > data.len() {
                    aliased_out_of_bounds_sections += 1;
                    0
                } else {
                    offset
                }
            });
            let available_size = physical_offset.map_or(0, |offset| {
                if offset == data.len() {
                    0
                } else {
                    usize::try_from(raw_size)
                        .unwrap_or(usize::MAX)
                        .min(data.len() - offset)
                }
            });
            if available_size != 0 {
                records.push(MemoryRecord {
                    offset: physical_offset.unwrap_or(0) as u64,
                    address,
                    size: available_size as u64,
                });
            }
            if entry_point_offset.is_none() {
                let mapped_size = virtual_size.max(raw_size);
                let section_end = virtual_address.checked_add(mapped_size);
                if section_end.is_some_and(|end| virtual_address <= entry_rva && entry_rva < end) {
                    let delta = entry_rva - virtual_address;
                    entry_point_offset = raw_offset
                        .checked_add(delta)
                        .and_then(|offset| usize::try_from(offset).ok())
                        .filter(|offset| {
                            delta < raw_size
                                && *offset < data.len()
                                && usize::try_from(raw_offset)
                                    .ok()
                                    .is_some_and(|raw| *offset >= raw)
                        });
                }
            }
        }
        Ok(Self {
            entry_point_offset,
            aliased_out_of_bounds_sections,
            memory_map: MemoryMap {
                file_type: FileType::Pe,
                endian: Endian::Little,
                code_base: 0,
                start_load_offset: 0,
                records,
            },
        })
    }
}

fn elf_u16(data: &[u8], offset: usize, endian: Endian) -> Option<u16> {
    let bytes: [u8; 2] = data.get(offset..offset.checked_add(2)?)?.try_into().ok()?;
    Some(match endian {
        Endian::Little => u16::from_le_bytes(bytes),
        Endian::Big => u16::from_be_bytes(bytes),
    })
}

fn elf_u32(data: &[u8], offset: usize, endian: Endian) -> Option<u32> {
    let bytes: [u8; 4] = data.get(offset..offset.checked_add(4)?)?.try_into().ok()?;
    Some(match endian {
        Endian::Little => u32::from_le_bytes(bytes),
        Endian::Big => u32::from_be_bytes(bytes),
    })
}

fn elf_u64(data: &[u8], offset: usize, endian: Endian) -> Option<u64> {
    let bytes: [u8; 8] = data.get(offset..offset.checked_add(8)?)?.try_into().ok()?;
    Some(match endian {
        Endian::Little => u64::from_le_bytes(bytes),
        Endian::Big => u64::from_be_bytes(bytes),
    })
}

fn elf_field(base: usize, relative: usize, name: &str) -> Result<usize, String> {
    base.checked_add(relative)
        .ok_or_else(|| format!("ELF {name} offset overflow"))
}

impl ElfRuleContext {
    fn parse(data: &[u8]) -> Result<Self, String> {
        if data.get(0..4) != Some(b"\x7fELF") {
            return Err("ELF signature is missing".to_owned());
        }
        let elf_class = *data
            .get(4)
            .ok_or_else(|| "ELF class is truncated".to_owned())?;
        let endian = match data
            .get(5)
            .copied()
            .ok_or_else(|| "ELF data encoding is truncated".to_owned())?
        {
            1 => Endian::Little,
            2 => Endian::Big,
            other => return Err(format!("unsupported ELF data encoding {other}")),
        };
        if data.get(6) != Some(&1) {
            return Err("unsupported or truncated ELF identification version".to_owned());
        }
        let (header_size, program_header_size, entry, program_offset, entry_size, entry_count) =
            match elf_class {
                1 => (
                    52_usize,
                    32_usize,
                    u64::from(
                        elf_u32(data, 24, endian)
                            .ok_or_else(|| "ELF32 entry point is truncated".to_owned())?,
                    ),
                    u64::from(
                        elf_u32(data, 28, endian)
                            .ok_or_else(|| "ELF32 program table offset is truncated".to_owned())?,
                    ),
                    elf_u16(data, 42, endian)
                        .ok_or_else(|| "ELF32 program entry size is truncated".to_owned())?,
                    elf_u16(data, 44, endian)
                        .ok_or_else(|| "ELF32 program entry count is truncated".to_owned())?,
                ),
                2 => (
                    64_usize,
                    56_usize,
                    elf_u64(data, 24, endian)
                        .ok_or_else(|| "ELF64 entry point is truncated".to_owned())?,
                    elf_u64(data, 32, endian)
                        .ok_or_else(|| "ELF64 program table offset is truncated".to_owned())?,
                    elf_u16(data, 54, endian)
                        .ok_or_else(|| "ELF64 program entry size is truncated".to_owned())?,
                    elf_u16(data, 56, endian)
                        .ok_or_else(|| "ELF64 program entry count is truncated".to_owned())?,
                ),
                other => return Err(format!("unsupported ELF class {other}")),
            };
        let declared_header_size = usize::from(
            elf_u16(data, if elf_class == 1 { 40 } else { 52 }, endian)
                .ok_or_else(|| "ELF header size is truncated".to_owned())?,
        );
        if declared_header_size < header_size || data.len() < header_size {
            return Err(format!(
                "ELF header is truncated or smaller than class minimum {header_size}"
            ));
        }
        let entry_size = usize::from(entry_size);
        if entry_size < program_header_size {
            return Err(format!(
                "ELF program entry size {entry_size} is smaller than {program_header_size}"
            ));
        }
        let entry_count = usize::from(entry_count);
        if entry_count > 1024 {
            return Err(format!(
                "ELF program entry count {entry_count} exceeds spike limit 1024"
            ));
        }
        let program_offset = usize::try_from(program_offset)
            .map_err(|_| "ELF program table offset does not fit usize".to_owned())?;
        let table_size = entry_count
            .checked_mul(entry_size)
            .ok_or_else(|| "ELF program table size overflow".to_owned())?;
        let table_end = program_offset
            .checked_add(table_size)
            .ok_or_else(|| "ELF program table end overflow".to_owned())?;
        if table_end > data.len() {
            return Err("ELF program table is truncated".to_owned());
        }

        let mut loads = Vec::new();
        for index in 0..entry_count {
            let header = program_offset
                .checked_add(
                    index
                        .checked_mul(entry_size)
                        .ok_or_else(|| "ELF program entry offset overflow".to_owned())?,
                )
                .ok_or_else(|| "ELF program entry offset overflow".to_owned())?;
            let segment_type = elf_u32(data, header, endian)
                .ok_or_else(|| "ELF program entry type is truncated".to_owned())?;
            if segment_type != 1 {
                continue;
            }
            let (offset, address, file_size) = if elf_class == 1 {
                (
                    u64::from(
                        elf_u32(data, elf_field(header, 4, "ELF32 segment offset")?, endian)
                            .ok_or_else(|| "ELF32 segment offset is truncated".to_owned())?,
                    ),
                    u64::from(
                        elf_u32(data, elf_field(header, 8, "ELF32 segment address")?, endian)
                            .ok_or_else(|| "ELF32 segment address is truncated".to_owned())?,
                    ),
                    u64::from(
                        elf_u32(data, elf_field(header, 16, "ELF32 file size")?, endian)
                            .ok_or_else(|| "ELF32 file size is truncated".to_owned())?,
                    ),
                )
            } else {
                (
                    elf_u64(data, elf_field(header, 8, "ELF64 segment offset")?, endian)
                        .ok_or_else(|| "ELF64 segment offset is truncated".to_owned())?,
                    elf_u64(
                        data,
                        elf_field(header, 16, "ELF64 segment address")?,
                        endian,
                    )
                    .ok_or_else(|| "ELF64 segment address is truncated".to_owned())?,
                    elf_u64(data, elf_field(header, 32, "ELF64 file size")?, endian)
                        .ok_or_else(|| "ELF64 file size is truncated".to_owned())?,
                )
            };
            if file_size != 0 {
                loads.push((offset, address, file_size));
            }
        }
        let image_base = loads
            .iter()
            .map(|(_, address, _)| *address)
            .min()
            .ok_or_else(|| "ELF contains no non-empty PT_LOAD segment".to_owned())?;
        let mut entry_point_offset = None;
        let mut records = Vec::with_capacity(loads.len());
        let mut out_of_bounds_loads = 0_usize;
        let data_len = u64::try_from(data.len())
            .map_err(|_| "ELF input length does not fit u64".to_owned())?;
        for (offset, address, size) in loads {
            let normalized_address = address
                .checked_sub(image_base)
                .ok_or_else(|| "ELF normalized segment address underflow".to_owned())?;
            let segment_end = offset
                .checked_add(size)
                .ok_or_else(|| "ELF segment file range overflow".to_owned())?;
            if segment_end > data_len {
                out_of_bounds_loads += 1;
            }
            if entry_point_offset.is_none() {
                let address_end = address
                    .checked_add(size)
                    .ok_or_else(|| "ELF segment address range overflow".to_owned())?;
                if address <= entry && entry < address_end {
                    entry_point_offset = offset
                        .checked_add(entry - address)
                        .and_then(|value| usize::try_from(value).ok());
                }
            }
            records.push(MemoryRecord {
                offset,
                address: normalized_address,
                size,
            });
        }
        Ok(Self {
            elf_class,
            entry_point_offset,
            out_of_bounds_loads,
            memory_map: MemoryMap {
                file_type: FileType::Elf,
                endian,
                code_base: 0,
                start_load_offset: 0,
                records,
            },
        })
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

fn install_entry_point_host(
    context: &Context,
    receiver_name: &'static str,
    data: Arc<Vec<u8>>,
    entry_point_offset: Option<usize>,
    memory_map: MemoryMap,
) -> Result<Arc<EntryPointHostTrace>, String> {
    let trace = Arc::new(EntryPointHostTrace::default());
    let trace_for_context = Arc::clone(&trace);
    let compare_api = match receiver_name {
        "PE" => "PE.compareEP",
        "ELF" => "ELF.compareEP",
        _ => "format.compareEP",
    };
    context.with(|ctx| {
        let receiver = Object::new(ctx.clone()).map_err(|error| error.to_string())?;
        let compare_data = Arc::clone(&data);
        let compare_memory_map = memory_map.clone();
        receiver
            .set(
                "compareEP",
                Function::new(ctx.clone(), move |pattern: String, offset: Opt<i64>| {
                    trace_for_context
                        .compare_ep_calls
                        .fetch_add(1, Ordering::Relaxed);
                    match Pattern::compare_entry_point_wrapper(
                        &pattern,
                        &compare_data,
                        entry_point_offset,
                        offset.0.unwrap_or(0),
                        &compare_memory_map,
                    ) {
                        Ok(report) => {
                            if report.header_fast_path {
                                trace_for_context.fast_paths.fetch_add(1, Ordering::Relaxed);
                            } else {
                                trace_for_context
                                    .generic_paths
                                    .fetch_add(1, Ordering::Relaxed);
                            }
                            Ok(report.matched)
                        }
                        Err(error) => {
                            trace_for_context.errors.fetch_add(1, Ordering::Relaxed);
                            Err(Error::new_from_js_message(
                                compare_api,
                                "boolean",
                                error.to_string(),
                            ))
                        }
                    }
                })
                .map_err(|error| error.to_string())?,
            )
            .map_err(|error| error.to_string())?;
        ctx.globals()
            .set(receiver_name, receiver)
            .map_err(|error| error.to_string())
    })?;
    Ok(trace)
}

fn install_pe_host(
    context: &Context,
    data: Arc<Vec<u8>>,
    pe_context: PeRuleContext,
) -> Result<Arc<EntryPointHostTrace>, String> {
    install_entry_point_host(
        context,
        "PE",
        data,
        pe_context.entry_point_offset,
        pe_context.memory_map,
    )
}

fn install_elf_host(
    context: &Context,
    data: Arc<Vec<u8>>,
    elf_context: ElfRuleContext,
) -> Result<Arc<EntryPointHostTrace>, String> {
    install_entry_point_host(
        context,
        "ELF",
        data,
        elf_context.entry_point_offset,
        elf_context.memory_map,
    )
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
    let is_overlay = host_context.is_overlay();
    let overlay_offset = host_context.overlay_offset;
    let overlay_size = host_context.overlay_size;
    let is_overlay_present = host_context.is_overlay_present();
    let scan_id = host_context.scan_id.clone();
    let is_resource = host_context.is_resource();
    let is_debug_data = host_context.is_debug_data();
    let is_file_part = host_context.is_file_part();
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
                    is_overlay
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
                    overlay_offset
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
                    overlay_size
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
                    is_overlay_present
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
        {
            let value = string_context.is_unicode_text();
            let string_trace = Arc::clone(&signature_trace_for_context);
            x.set(
                "isUnicodeText",
                Function::new(ctx.clone(), move || {
                    string_trace
                        .is_unicode_text_calls
                        .fetch_add(1, Ordering::Relaxed);
                    value
                })
                .map_err(|error| error.to_string())?,
            )
            .map_err(|error| error.to_string())?;
        }
        {
            let value = string_context.is_text();
            let string_trace = Arc::clone(&signature_trace_for_context);
            x.set(
                "isText",
                Function::new(ctx.clone(), move || {
                    string_trace.is_text_calls.fetch_add(1, Ordering::Relaxed);
                    value
                })
                .map_err(|error| error.to_string())?,
            )
            .map_err(|error| error.to_string())?;
        }
        {
            let context_trace = Arc::clone(&signature_trace_for_context);
            x.set(
                "getScanID",
                Function::new(ctx.clone(), move || {
                    context_trace
                        .get_scan_id_calls
                        .fetch_add(1, Ordering::Relaxed);
                    scan_id.clone()
                })
                .map_err(|error| error.to_string())?,
            )
            .map_err(|error| error.to_string())?;
        }
        {
            let context_trace = Arc::clone(&signature_trace_for_context);
            x.set(
                "isResource",
                Function::new(ctx.clone(), move || {
                    context_trace
                        .is_resource_calls
                        .fetch_add(1, Ordering::Relaxed);
                    is_resource
                })
                .map_err(|error| error.to_string())?,
            )
            .map_err(|error| error.to_string())?;
        }
        {
            let context_trace = Arc::clone(&signature_trace_for_context);
            x.set(
                "isDebugData",
                Function::new(ctx.clone(), move || {
                    context_trace
                        .is_debug_data_calls
                        .fetch_add(1, Ordering::Relaxed);
                    is_debug_data
                })
                .map_err(|error| error.to_string())?,
            )
            .map_err(|error| error.to_string())?;
        }
        {
            let context_trace = Arc::clone(&signature_trace_for_context);
            x.set(
                "isFilePart",
                Function::new(ctx.clone(), move || {
                    context_trace
                        .is_file_part_calls
                        .fetch_add(1, Ordering::Relaxed);
                    is_file_part
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
    let mut canonical = Vec::new();
    for name in &order {
        canonical.extend_from_slice(name.as_bytes());
        canonical.push(b'\n');
    }
    if sha256_hex(&canonical) != LINUX_QT5_BINARY_ORDER_SHA256 {
        return Err("Binary canonical order SHA-256 mismatch".to_owned());
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

fn trace_binary_detects_report_with_data(
    rule_root: &Path,
    input_path: &Path,
    order_path: &Path,
    data: Vec<u8>,
) -> Result<Value, String> {
    let order_document: Value = serde_json::from_slice(
        &fs::read(order_path)
            .map_err(|error| format!("cannot read {}: {error}", order_path.display()))?,
    )
    .map_err(|error| format!("cannot parse {}: {error}", order_path.display()))?;
    let order = parse_binary_order(&order_document)?;
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
        let is_unicode_text_calls_before = signature_trace
            .is_unicode_text_calls
            .load(Ordering::Relaxed);
        let is_text_calls_before = signature_trace.is_text_calls.load(Ordering::Relaxed);
        let get_scan_id_calls_before = signature_trace.get_scan_id_calls.load(Ordering::Relaxed);
        let is_resource_calls_before = signature_trace.is_resource_calls.load(Ordering::Relaxed);
        let is_debug_data_calls_before =
            signature_trace.is_debug_data_calls.load(Ordering::Relaxed);
        let is_file_part_calls_before = signature_trace.is_file_part_calls.load(Ordering::Relaxed);
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
        let is_unicode_text_call_count = signature_trace
            .is_unicode_text_calls
            .load(Ordering::Relaxed)
            .saturating_sub(is_unicode_text_calls_before);
        let is_text_call_count = signature_trace
            .is_text_calls
            .load(Ordering::Relaxed)
            .saturating_sub(is_text_calls_before);
        let get_scan_id_call_count = signature_trace
            .get_scan_id_calls
            .load(Ordering::Relaxed)
            .saturating_sub(get_scan_id_calls_before);
        let is_resource_call_count = signature_trace
            .is_resource_calls
            .load(Ordering::Relaxed)
            .saturating_sub(is_resource_calls_before);
        let is_debug_data_call_count = signature_trace
            .is_debug_data_calls
            .load(Ordering::Relaxed)
            .saturating_sub(is_debug_data_calls_before);
        let is_file_part_call_count = signature_trace
            .is_file_part_calls
            .load(Ordering::Relaxed)
            .saturating_sub(is_file_part_calls_before);
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
                "is_unicode_text": is_unicode_text_call_count,
                "is_text": is_text_call_count,
            },
            "context_host_calls": {
                "get_scan_id": get_scan_id_call_count,
                "is_resource": is_resource_call_count,
                "is_debug_data": is_debug_data_call_count,
                "is_file_part": is_file_part_call_count,
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
    let overlay_host_call_totals = json!({
        "is_overlay": signature_trace.is_overlay_calls.load(Ordering::Relaxed),
        "get_overlay_offset": signature_trace.get_overlay_offset_calls.load(Ordering::Relaxed),
        "get_overlay_size": signature_trace.get_overlay_size_calls.load(Ordering::Relaxed),
        "is_overlay_present": signature_trace.is_overlay_present_calls.load(Ordering::Relaxed),
    });
    let string_host_call_totals = json!({
        "get_file_suffix": signature_trace.get_file_suffix_calls.load(Ordering::Relaxed),
        "get_header_string": signature_trace.get_header_string_calls.load(Ordering::Relaxed),
        "is_plain_text": signature_trace.is_plain_text_calls.load(Ordering::Relaxed),
        "is_utf8_text": signature_trace.is_utf8_text_calls.load(Ordering::Relaxed),
        "is_unicode_text": signature_trace.is_unicode_text_calls.load(Ordering::Relaxed),
        "is_text": signature_trace.is_text_calls.load(Ordering::Relaxed),
    });
    let context_host_call_totals = json!({
        "get_scan_id": signature_trace.get_scan_id_calls.load(Ordering::Relaxed),
        "is_resource": signature_trace.is_resource_calls.load(Ordering::Relaxed),
        "is_debug_data": signature_trace.is_debug_data_calls.load(Ordering::Relaxed),
        "is_file_part": signature_trace.is_file_part_calls.load(Ordering::Relaxed),
    });
    Ok(json!({
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
        "overlay_host_call_totals": overlay_host_call_totals,
        "string_host_call_totals": string_host_call_totals,
        "context_host_call_totals": context_host_call_totals,
        "detection_count": all_detections.len(),
        "detections": all_detections,
        "observations": observations,
        "interrupt_handler_call_limit_per_rule": 1_000_000,
        "elapsed_ms": started.elapsed().as_millis(),
        "completed": true,
    }))
}

fn trace_binary_detects_report(
    rule_root: &Path,
    input_path: &Path,
    order_path: &Path,
) -> Result<Value, String> {
    let data = fs::read(input_path)
        .map_err(|error| format!("cannot read {}: {error}", input_path.display()))?;
    trace_binary_detects_report_with_data(rule_root, input_path, order_path, data)
}

fn trace_binary_detects(
    rule_root: &Path,
    input_path: &Path,
    order_path: &Path,
) -> Result<bool, String> {
    let report = trace_binary_detects_report(rule_root, input_path, order_path)?;
    println!(
        "{}",
        serde_json::to_string_pretty(&report)
            .map_err(|error| format!("cannot serialize report: {error}"))?
    );
    Ok(true)
}

fn sha256_hex(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

fn decode_hex_string(value: &str, field: &str) -> Result<Vec<u8>, String> {
    if !value.len().is_multiple_of(2) {
        return Err(format!("{field} has an odd number of hex digits"));
    }
    value
        .as_bytes()
        .chunks_exact(2)
        .map(|pair| {
            let text = std::str::from_utf8(pair)
                .map_err(|error| format!("{field} is not ASCII: {error}"))?;
            u8::from_str_radix(text, 16)
                .map_err(|error| format!("{field} contains invalid hex: {error}"))
        })
        .collect()
}

fn pe_physical_map_projection(context: &PeRuleContext) -> Value {
    json!({
        "file_type": "pe",
        "endian": "little",
        "code_base": context.memory_map.code_base.to_string(),
        "start_load_offset": context.memory_map.start_load_offset.to_string(),
        "records": context
            .memory_map
            .records
            .iter()
            .map(|record| json!({
                "offset": record.offset.to_string(),
                "address": record.address.to_string(),
                "size": record.size.to_string(),
            }))
            .collect::<Vec<_>>(),
    })
}

fn qt5_pe_physical_map_projection(value: &Value) -> Result<Value, String> {
    let object = value
        .as_object()
        .ok_or_else(|| "Qt5 PE memory map must be an object".to_owned())?;
    let records = object
        .get("records")
        .and_then(Value::as_array)
        .ok_or_else(|| "Qt5 PE memory map records are missing".to_owned())?
        .iter()
        .filter_map(|record| {
            let object = record.as_object()?;
            let is_virtual = object.get("virtual")?.as_bool()?;
            let size = object.get("size")?.as_str()?;
            (!is_virtual && size != "0").then(|| {
                json!({
                    "offset": object.get("offset"),
                    "address": object.get("address"),
                    "size": size,
                })
            })
        })
        .collect::<Vec<_>>();
    Ok(json!({
        "file_type": object.get("file_type"),
        "endian": object.get("endian"),
        "code_base": object.get("code_base"),
        "start_load_offset": object.get("start_load_offset"),
        "records": records,
    }))
}

fn elf_matcher_map_projection(context: &ElfRuleContext) -> Value {
    let endian = match context.memory_map.endian {
        Endian::Little => "little",
        Endian::Big => "big",
    };
    json!({
        "file_type": "elf",
        "endian": endian,
        "code_base": context.memory_map.code_base.to_string(),
        "start_load_offset": context.memory_map.start_load_offset.to_string(),
        "records": context
            .memory_map
            .records
            .iter()
            .map(|record| json!({
                "offset": record.offset.to_string(),
                "address": record.address.to_string(),
                "size": record.size.to_string(),
            }))
            .collect::<Vec<_>>(),
    })
}

#[derive(Debug, Eq, PartialEq)]
struct Qt5ElfMapProjection {
    matcher_map: Value,
    discarded_virtual_records: usize,
    discarded_nonpositive_size_records: usize,
    discarded_negative_offset_records: usize,
    discarded_overlay_sentinel_records: usize,
}

fn parse_qt5_i128(value: Option<&Value>, field: &str) -> Result<i128, String> {
    value
        .and_then(Value::as_str)
        .ok_or_else(|| format!("Qt5 ELF memory record {field} is missing"))?
        .parse::<i128>()
        .map_err(|error| format!("Qt5 ELF memory record {field} is invalid: {error}"))
}

fn qt5_elf_matcher_map_projection(value: &Value) -> Result<Qt5ElfMapProjection, String> {
    let object = value
        .as_object()
        .ok_or_else(|| "Qt5 ELF memory map must be an object".to_owned())?;
    let source_records = object
        .get("records")
        .and_then(Value::as_array)
        .ok_or_else(|| "Qt5 ELF memory map records are missing".to_owned())?;
    let mut records = Vec::new();
    let mut discarded_virtual_records = 0_usize;
    let mut discarded_nonpositive_size_records = 0_usize;
    let mut discarded_negative_offset_records = 0_usize;
    let mut discarded_overlay_sentinel_records = 0_usize;
    for record in source_records {
        let record = record
            .as_object()
            .ok_or_else(|| "Qt5 ELF memory map record must be an object".to_owned())?;
        if record.get("virtual").and_then(Value::as_bool) != Some(false) {
            discarded_virtual_records += 1;
            continue;
        }
        let size = parse_qt5_i128(record.get("size"), "size")?;
        if size <= 0 {
            discarded_nonpositive_size_records += 1;
            continue;
        }
        let offset = parse_qt5_i128(record.get("offset"), "offset")?;
        if offset < 0 {
            discarded_negative_offset_records += 1;
            continue;
        }
        let address = parse_qt5_i128(record.get("address"), "address")?;
        if address == i128::from(u64::MAX) {
            discarded_overlay_sentinel_records += 1;
            continue;
        }
        records.push(json!({
            "offset": offset.to_string(),
            "address": address.to_string(),
            "size": size.to_string(),
        }));
    }
    Ok(Qt5ElfMapProjection {
        matcher_map: json!({
            "file_type": object.get("file_type"),
            "endian": object.get("endian"),
            "code_base": object.get("code_base"),
            "start_load_offset": object.get("start_load_offset"),
            "records": records,
        }),
        discarded_virtual_records,
        discarded_nonpositive_size_records,
        discarded_negative_offset_records,
        discarded_overlay_sentinel_records,
    })
}

fn verify_pe_rule(
    rule_root: &Path,
    fixture_path: &Path,
    baseline_path: &Path,
) -> Result<bool, String> {
    let fixture_bytes = fs::read(fixture_path)
        .map_err(|error| format!("cannot read {}: {error}", fixture_path.display()))?;
    let baseline_bytes = fs::read(baseline_path)
        .map_err(|error| format!("cannot read {}: {error}", baseline_path.display()))?;
    if sha256_hex(&fixture_bytes) != PE_FIXTURE_SHA256 {
        return Err(format!(
            "fixed PE fixture hash mismatch: {}",
            fixture_path.display()
        ));
    }
    if sha256_hex(&baseline_bytes) != PE_QT5_BASELINE_SHA256 {
        return Err(format!(
            "fixed Qt5 PE baseline hash mismatch: {}",
            baseline_path.display()
        ));
    }
    let rule_path = rule_root.join(PE_RULE_SUFFIX);
    let rule_source = fs::read(&rule_path)
        .map_err(|error| format!("cannot read {}: {error}", rule_path.display()))?;
    if rule_source.len() != PE_RULE_BYTES || sha256_hex(&rule_source) != PE_RULE_SHA256 {
        return Err(format!("fixed PE rule mismatch: {}", rule_path.display()));
    }
    let fixture: Value = serde_json::from_slice(&fixture_bytes)
        .map_err(|error| format!("cannot parse {}: {error}", fixture_path.display()))?;
    let baseline: Value = serde_json::from_slice(&baseline_bytes)
        .map_err(|error| format!("cannot parse {}: {error}", baseline_path.display()))?;
    for (document_name, document) in [("fixture", &fixture), ("baseline", &baseline)] {
        if document["upstream_commit"] != UPSTREAM_COMMIT
            || document["xscanengine_commit"] != XSCANENGINE_COMMIT
            || document["rules_commit"] != RULES_COMMIT
            || document["case_count"] != 3
        {
            return Err(format!("{document_name} PE metadata mismatch"));
        }
    }
    if fixture["formats_commit"] != baseline["formats_commit"]
        || fixture["rule"]["path"] != PE_RULE_SUFFIX
        || fixture["rule"]["sha256"] != PE_RULE_SHA256
        || baseline["rule_sha256"] != PE_RULE_SHA256
        || baseline["qt_version"] != "5.15.13"
        || baseline["engine"] != "QScriptEngine"
    {
        return Err("fixed PE fixture/baseline contract mismatch".to_owned());
    }
    let fixture_cases = fixture["cases"]
        .as_array()
        .ok_or_else(|| "PE fixture cases are missing".to_owned())?;
    let baseline_cases = baseline["cases"]
        .as_array()
        .ok_or_else(|| "Qt5 PE baseline cases are missing".to_owned())?;
    if fixture_cases.len() != 3 || baseline_cases.len() != 3 {
        return Err("fixed PE case count mismatch".to_owned());
    }

    let mut reports = Vec::with_capacity(fixture_cases.len());
    let mut all_match = true;
    for fixture_case in fixture_cases {
        let id = fixture_case["id"]
            .as_str()
            .ok_or_else(|| "PE fixture case id is missing".to_owned())?;
        let baseline_case = baseline_cases
            .iter()
            .find(|case| case["id"] == id)
            .ok_or_else(|| format!("Qt5 PE baseline case is missing: {id}"))?;
        if fixture_case["data_hex"] != baseline_case["data_hex"]
            || fixture_case["data_sha256"] != baseline_case["data_sha256"]
        {
            return Err(format!("{id}: fixture and Qt5 input evidence differ"));
        }
        let data_hex = fixture_case["data_hex"]
            .as_str()
            .ok_or_else(|| format!("{id}: data_hex is missing"))?;
        let data = decode_hex_string(data_hex, &format!("{id}.data_hex"))?;
        if sha256_hex(&data) != fixture_case["data_sha256"] {
            return Err(format!("{id}: decoded input hash mismatch"));
        }
        let pe_context = PeRuleContext::parse(&data).map_err(|error| format!("{id}: {error}"))?;
        let expected_entry_point = baseline_case["entry_point_offset"]
            .as_i64()
            .ok_or_else(|| format!("{id}: Qt5 entry point offset is missing"))?;
        let actual_entry_point = pe_context
            .entry_point_offset
            .and_then(|offset| i64::try_from(offset).ok())
            .unwrap_or(-1);
        let actual_map = pe_physical_map_projection(&pe_context);
        let expected_map = qt5_pe_physical_map_projection(&baseline_case["memory_map"])?;

        let runtime = new_runtime()?;
        let context = new_context(&runtime)?;
        let detections = Arc::new(Mutex::new(Vec::new()));
        install_nintendo_host(&context, Arc::new(data.clone()), Arc::clone(&detections))?;
        let pe_trace = install_pe_host(&context, Arc::new(data), pe_context.clone())?;
        eval_unit(&context, FORMAT_RESULT_SHIM)?;
        let detect_result = eval_rule_lexical(&context, &rule_source, true)
            .map_err(|error| format!("{id}: fixed PE rule failed: {error}"))?;
        let actual_detections = detections
            .lock()
            .map_err(|_| "PE detection result mutex poisoned".to_owned())?
            .clone();
        let expected_detections: Vec<Detection> =
            serde_json::from_value(baseline_case["detections"].clone())
                .map_err(|error| format!("{id}: invalid Qt5 detections: {error}"))?;
        let expected_detect_result = baseline_case["detect_result"]
            .as_bool()
            .ok_or_else(|| format!("{id}: Qt5 detect result is missing"))?;
        let compare_ep_calls = pe_trace.compare_ep_calls.load(Ordering::Relaxed);
        let fast_paths = pe_trace.fast_paths.load(Ordering::Relaxed);
        let generic_paths = pe_trace.generic_paths.load(Ordering::Relaxed);
        let errors = pe_trace.errors.load(Ordering::Relaxed);
        let entry_point_matches = actual_entry_point == expected_entry_point;
        let memory_map_matches = actual_map == expected_map;
        let matches = entry_point_matches
            && memory_map_matches
            && detect_result == expected_detect_result.to_string()
            && actual_detections == expected_detections
            && compare_ep_calls == 1
            && fast_paths + generic_paths == 1
            && errors == 0;
        all_match &= matches;
        reports.push(json!({
            "id": id,
            "input_sha256": fixture_case["data_sha256"],
            "input_bytes": data_hex.len() / 2,
            "parser_valid": true,
            "entry_point_offset": {
                "qt5": expected_entry_point,
                "rust": actual_entry_point,
                "matches": entry_point_matches,
            },
            "physical_memory_map": {
                "qt5": expected_map,
                "rust": actual_map,
                "matches": memory_map_matches,
                "bounded_upstream_alias_count":
                    pe_context.aliased_out_of_bounds_sections,
            },
            "detect_result": {
                "qt5": expected_detect_result,
                "rust": detect_result,
            },
            "detections": {
                "qt5": expected_detections,
                "rust": actual_detections,
            },
            "pe_compare_ep_calls": compare_ep_calls,
            "pe_compare_ep_fast_paths": fast_paths,
            "pe_compare_ep_generic_paths": generic_paths,
            "pe_compare_ep_errors": errors,
            "matches": matches,
        }));
    }
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({
            "schema_version": 1,
            "operation": "byte-identical fixed PE rule with Rust PE context and PE.compareEP",
            "runtime": "rquickjs 0.12.1 / QuickJS-NG 0.15.1",
            "upstream_commit": UPSTREAM_COMMIT,
            "xscanengine_commit": XSCANENGINE_COMMIT,
            "rules_commit": RULES_COMMIT,
            "rule": {
                "path": normalized_path(&rule_path),
                "bytes": rule_source.len(),
                "sha256": PE_RULE_SHA256,
            },
            "fixture": {
                "path": normalized_path(fixture_path),
                "sha256": PE_FIXTURE_SHA256,
            },
            "qt5_baseline": {
                "path": normalized_path(baseline_path),
                "sha256": PE_QT5_BASELINE_SHA256,
            },
            "case_count": reports.len(),
            "matched_count": reports.iter().filter(|case| case["matches"] == true).count(),
            "cases": reports,
            "all_match": all_match,
        }))
        .map_err(|error| format!("cannot serialize PE rule report: {error}"))?
    );
    Ok(all_match)
}

fn verify_elf_rule(
    rule_root: &Path,
    fixture_path: &Path,
    baseline_path: &Path,
) -> Result<bool, String> {
    let fixture_bytes = fs::read(fixture_path)
        .map_err(|error| format!("cannot read {}: {error}", fixture_path.display()))?;
    let baseline_bytes = fs::read(baseline_path)
        .map_err(|error| format!("cannot read {}: {error}", baseline_path.display()))?;
    if sha256_hex(&fixture_bytes) != ELF_FIXTURE_SHA256 {
        return Err(format!(
            "fixed ELF fixture hash mismatch: {}",
            fixture_path.display()
        ));
    }
    if sha256_hex(&baseline_bytes) != ELF_QT5_BASELINE_SHA256 {
        return Err(format!(
            "fixed Qt5 ELF baseline hash mismatch: {}",
            baseline_path.display()
        ));
    }
    let rule_path = rule_root.join(ELF_RULE_SUFFIX);
    let rule_source = fs::read(&rule_path)
        .map_err(|error| format!("cannot read {}: {error}", rule_path.display()))?;
    if rule_source.len() != ELF_RULE_BYTES || sha256_hex(&rule_source) != ELF_RULE_SHA256 {
        return Err(format!("fixed ELF rule mismatch: {}", rule_path.display()));
    }
    let fixture: Value = serde_json::from_slice(&fixture_bytes)
        .map_err(|error| format!("cannot parse {}: {error}", fixture_path.display()))?;
    let baseline: Value = serde_json::from_slice(&baseline_bytes)
        .map_err(|error| format!("cannot parse {}: {error}", baseline_path.display()))?;
    for (document_name, document) in [("fixture", &fixture), ("baseline", &baseline)] {
        if document["upstream_commit"] != UPSTREAM_COMMIT
            || document["formats_commit"] != FORMATS_COMMIT
            || document["xscanengine_commit"] != XSCANENGINE_COMMIT
            || document["rules_commit"] != RULES_COMMIT
            || document["case_count"] != 6
        {
            return Err(format!("{document_name} ELF metadata mismatch"));
        }
    }
    if fixture["rule"]["path"] != ELF_RULE_SUFFIX
        || fixture["rule"]["sha256"] != ELF_RULE_SHA256
        || baseline["rule_path"] != format!("/opt/die-source/Detect-It-Easy/db/{ELF_RULE_SUFFIX}")
        || baseline["rule_sha256"] != ELF_RULE_SHA256
        || baseline["qt_version"] != "5.15.13"
        || baseline["engine"] != "QScriptEngine"
    {
        return Err("fixed ELF fixture/baseline contract mismatch".to_owned());
    }
    let fixture_cases = fixture["cases"]
        .as_array()
        .ok_or_else(|| "ELF fixture cases are missing".to_owned())?;
    let baseline_cases = baseline["cases"]
        .as_array()
        .ok_or_else(|| "Qt5 ELF baseline cases are missing".to_owned())?;
    if fixture_cases.len() != 6 || baseline_cases.len() != 6 {
        return Err("fixed ELF case count mismatch".to_owned());
    }

    let mut reports = Vec::with_capacity(fixture_cases.len());
    let mut all_match = true;
    for fixture_case in fixture_cases {
        let id = fixture_case["id"]
            .as_str()
            .ok_or_else(|| "ELF fixture case id is missing".to_owned())?;
        let baseline_case = baseline_cases
            .iter()
            .find(|case| case["id"] == id)
            .ok_or_else(|| format!("Qt5 ELF baseline case is missing: {id}"))?;
        if fixture_case["data_hex"] != baseline_case["data_hex"]
            || fixture_case["data_sha256"] != baseline_case["data_sha256"]
            || fixture_case["elf_class"] != baseline_case["elf_class"]
        {
            return Err(format!("{id}: fixture and Qt5 input evidence differ"));
        }
        if baseline_case["parser_valid"] != true || baseline_case["elf_script_error"] != "" {
            return Err(format!("{id}: Qt5 ELF parser/script evidence is not valid"));
        }
        let data_hex = fixture_case["data_hex"]
            .as_str()
            .ok_or_else(|| format!("{id}: data_hex is missing"))?;
        let data = decode_hex_string(data_hex, &format!("{id}.data_hex"))?;
        if sha256_hex(&data) != fixture_case["data_sha256"] {
            return Err(format!("{id}: decoded input hash mismatch"));
        }
        let elf_context = ElfRuleContext::parse(&data).map_err(|error| format!("{id}: {error}"))?;
        let expected_class = baseline_case["elf_class"]
            .as_u64()
            .ok_or_else(|| format!("{id}: Qt5 ELF class is missing"))?;
        let actual_class = u64::from(elf_context.elf_class) * 32;
        let expected_entry_point = baseline_case["entry_point_offset"]
            .as_i64()
            .ok_or_else(|| format!("{id}: Qt5 entry point offset is missing"))?;
        let actual_entry_point = elf_context
            .entry_point_offset
            .and_then(|offset| i64::try_from(offset).ok())
            .unwrap_or(-1);
        let actual_map = elf_matcher_map_projection(&elf_context);
        let expected_projection = qt5_elf_matcher_map_projection(&baseline_case["memory_map"])?;
        let memory_map_matches = actual_map == expected_projection.matcher_map;

        let runtime = new_runtime()?;
        let context = new_context(&runtime)?;
        let detections = Arc::new(Mutex::new(Vec::new()));
        install_nintendo_host(&context, Arc::new(data.clone()), Arc::clone(&detections))?;
        let elf_trace = install_elf_host(&context, Arc::new(data), elf_context.clone())?;
        eval_unit(&context, FORMAT_RESULT_SHIM)?;
        let detect_result = eval_rule_lexical(&context, &rule_source, true)
            .map_err(|error| format!("{id}: fixed ELF rule failed: {error}"))?;
        let actual_detections = detections
            .lock()
            .map_err(|_| "ELF detection result mutex poisoned".to_owned())?
            .clone();
        let expected_detections: Vec<Detection> =
            serde_json::from_value(baseline_case["detections"].clone())
                .map_err(|error| format!("{id}: invalid Qt5 detections: {error}"))?;
        let expected_detect_result = baseline_case["detect_result"]
            .as_bool()
            .ok_or_else(|| format!("{id}: Qt5 detect result is missing"))?;
        let compare_ep_calls = elf_trace.compare_ep_calls.load(Ordering::Relaxed);
        let fast_paths = elf_trace.fast_paths.load(Ordering::Relaxed);
        let generic_paths = elf_trace.generic_paths.load(Ordering::Relaxed);
        let errors = elf_trace.errors.load(Ordering::Relaxed);
        let class_matches = actual_class == expected_class;
        let entry_point_matches = actual_entry_point == expected_entry_point;
        let matches = class_matches
            && entry_point_matches
            && memory_map_matches
            && detect_result == expected_detect_result.to_string()
            && actual_detections == expected_detections
            && compare_ep_calls == 1
            && fast_paths + generic_paths == 1
            && errors == 0;
        all_match &= matches;
        reports.push(json!({
            "id": id,
            "input_sha256": fixture_case["data_sha256"],
            "input_bytes": data_hex.len() / 2,
            "parser_valid": true,
            "elf_class": {
                "qt5": expected_class,
                "rust": actual_class,
                "matches": class_matches,
            },
            "entry_point_offset": {
                "qt5": expected_entry_point,
                "rust": actual_entry_point,
                "matches": entry_point_matches,
            },
            "matcher_memory_map": {
                "qt5_safe_projection": expected_projection.matcher_map,
                "rust": actual_map,
                "matches": memory_map_matches,
                "qt5_discarded_records": {
                    "virtual": expected_projection.discarded_virtual_records,
                    "nonpositive_size":
                        expected_projection.discarded_nonpositive_size_records,
                    "negative_offset":
                        expected_projection.discarded_negative_offset_records,
                    "overlay_sentinel":
                        expected_projection.discarded_overlay_sentinel_records,
                },
                "rust_declared_out_of_bounds_loads": elf_context.out_of_bounds_loads,
            },
            "detect_result": {
                "qt5": expected_detect_result,
                "rust": detect_result,
            },
            "detections": {
                "qt5": expected_detections,
                "rust": actual_detections,
            },
            "elf_compare_ep_calls": compare_ep_calls,
            "elf_compare_ep_fast_paths": fast_paths,
            "elf_compare_ep_generic_paths": generic_paths,
            "elf_compare_ep_errors": errors,
            "matches": matches,
        }));
    }
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({
            "schema_version": 1,
            "operation": "byte-identical fixed ELF rule with Rust ELF context and ELF.compareEP",
            "runtime": "rquickjs 0.12.1 / QuickJS-NG 0.15.1",
            "upstream_commit": UPSTREAM_COMMIT,
            "formats_commit": FORMATS_COMMIT,
            "xscanengine_commit": XSCANENGINE_COMMIT,
            "rules_commit": RULES_COMMIT,
            "rule": {
                "path": normalized_path(&rule_path),
                "bytes": rule_source.len(),
                "sha256": ELF_RULE_SHA256,
            },
            "fixture": {
                "path": normalized_path(fixture_path),
                "sha256": ELF_FIXTURE_SHA256,
            },
            "qt5_baseline": {
                "path": normalized_path(baseline_path),
                "sha256": ELF_QT5_BASELINE_SHA256,
            },
            "case_count": reports.len(),
            "matched_count": reports.iter().filter(|case| case["matches"] == true).count(),
            "cases": reports,
            "all_match": all_match,
        }))
        .map_err(|error| format!("cannot serialize ELF rule report: {error}"))?
    );
    Ok(all_match)
}

fn upstream_type_priority(kind: &str) -> i32 {
    let normalized = kind.to_lowercase().replace(['~', '!'], "");
    match normalized.as_str() {
        "operation system" | "virtual machine" => 10,
        "format" => 12,
        "platform" | "dos extender" => 14,
        "linker" => 20,
        "compiler" => 30,
        "language" => 40,
        "library" => 50,
        "tool" | "pe tool" | "sign tool" | "apk tool" => 60,
        "protector" | "cryptor" | "crypter" => 70,
        ".net obfuscator" | "apk obfuscator" | "jar obfuscator" => 80,
        "dongle protection" | "protection" => 90,
        "packer" | ".net compressor" => 100,
        "joiner" => 110,
        "sfx" | "installer" => 120,
        "virus" | "malware" | "trojan" | "corrupted data" | "personal data" | "author" => 70,
        "debug data" => 200,
        _ => 1000,
    }
}

fn parse_detection_triples(
    value: &Value,
    sample_name: &str,
) -> Result<Vec<DetectionTriple>, String> {
    value
        .as_array()
        .ok_or_else(|| format!("baseline detections for {sample_name} are not an array"))?
        .iter()
        .enumerate()
        .map(|(index, detection)| {
            let fields = detection.as_array().ok_or_else(|| {
                format!("baseline detection {index} for {sample_name} is not an array")
            })?;
            if fields.len() != 3 {
                return Err(format!(
                    "baseline detection {index} for {sample_name} has {} fields, expected 3",
                    fields.len()
                ));
            }
            Ok((
                fields[0]
                    .as_str()
                    .ok_or_else(|| {
                        format!("baseline detection {index} type for {sample_name} is not a string")
                    })?
                    .to_owned(),
                fields[1]
                    .as_str()
                    .ok_or_else(|| {
                        format!("baseline detection {index} name for {sample_name} is not a string")
                    })?
                    .to_owned(),
                fields[2]
                    .as_str()
                    .ok_or_else(|| {
                        format!(
                            "baseline detection {index} version for {sample_name} is not a string"
                        )
                    })?
                    .to_owned(),
            ))
        })
        .collect()
}

fn parse_runtime_detections(report: &Value, sample_name: &str) -> Result<Vec<Detection>, String> {
    report
        .get("detections")
        .and_then(Value::as_array)
        .ok_or_else(|| format!("runtime detections for {sample_name} are missing"))?
        .iter()
        .enumerate()
        .map(|(index, detection)| {
            let fields = detection.as_array().ok_or_else(|| {
                format!("runtime detection {index} for {sample_name} is not an array")
            })?;
            if fields.len() != 4 {
                return Err(format!(
                    "runtime detection {index} for {sample_name} has {} fields, expected 4",
                    fields.len()
                ));
            }
            let field = |field_index: usize, label: &str| {
                fields[field_index]
                    .as_str()
                    .map(str::to_owned)
                    .ok_or_else(|| {
                        format!(
                            "runtime detection {index} {label} for {sample_name} is not a string"
                        )
                    })
            };
            Ok((
                field(0, "type")?,
                field(1, "name")?,
                field(2, "version")?,
                field(3, "info")?,
            ))
        })
        .collect()
}

fn sorted_detection_projection(detections: &[Detection]) -> (Vec<DetectionTriple>, bool) {
    let mut priority_counts = BTreeMap::new();
    for (kind, _, _, _) in detections {
        *priority_counts
            .entry(upstream_type_priority(kind))
            .or_insert(0_usize) += 1;
    }
    let priorities_unambiguous = priority_counts.values().all(|count| *count == 1);
    let mut sorted = detections.to_vec();
    sorted.sort_by_key(|(kind, _, _, _)| upstream_type_priority(kind));
    (
        sorted
            .into_iter()
            .map(|(kind, name, version, _)| (kind, name, version))
            .collect(),
        priorities_unambiguous,
    )
}

fn report_u64(report: &Value, field: &str, sample_name: &str) -> Result<u64, String> {
    report
        .get(field)
        .and_then(Value::as_u64)
        .ok_or_else(|| format!("{sample_name}: runtime report field {field} is missing"))
}

fn verify_binary_corpus(
    rule_root: &Path,
    corpus_root: &Path,
    corpus_manifest_path: &Path,
    baseline_path: &Path,
    order_path: &Path,
) -> Result<bool, String> {
    let corpus_manifest_bytes = fs::read(corpus_manifest_path).map_err(|error| {
        format!(
            "cannot read corpus manifest {}: {error}",
            corpus_manifest_path.display()
        )
    })?;
    if sha256_hex(&corpus_manifest_bytes) != NINTENDO_CORPUS_MANIFEST_SHA256 {
        return Err("Nintendo corpus manifest SHA-256 mismatch".to_owned());
    }
    let corpus_manifest: Value =
        serde_json::from_slice(&corpus_manifest_bytes).map_err(|error| {
            format!(
                "cannot parse corpus manifest {}: {error}",
                corpus_manifest_path.display()
            )
        })?;
    if corpus_manifest
        .get("schema_version")
        .and_then(Value::as_u64)
        != Some(1)
        || corpus_manifest.get("generator").and_then(Value::as_str)
            != Some("tools/corpus/generate_nintendo_certified_corpus.py")
    {
        return Err("unexpected Nintendo corpus manifest identity".to_owned());
    }
    let mut manifest_samples = BTreeMap::new();
    for sample in corpus_manifest
        .get("samples")
        .and_then(Value::as_array)
        .ok_or_else(|| "Nintendo corpus manifest samples are missing".to_owned())?
    {
        let name = sample
            .get("name")
            .and_then(Value::as_str)
            .ok_or_else(|| "Nintendo corpus manifest sample name is missing".to_owned())?
            .to_owned();
        let size = sample
            .get("size")
            .and_then(Value::as_u64)
            .ok_or_else(|| format!("Nintendo corpus manifest size is missing for {name}"))?;
        let sha256 = sample
            .get("sha256")
            .and_then(Value::as_str)
            .ok_or_else(|| format!("Nintendo corpus manifest SHA-256 is missing for {name}"))?
            .to_owned();
        if manifest_samples
            .insert(name.clone(), (size, sha256))
            .is_some()
        {
            return Err(format!("duplicate Nintendo corpus manifest sample: {name}"));
        }
    }

    let baseline_bytes = fs::read(baseline_path)
        .map_err(|error| format!("cannot read {}: {error}", baseline_path.display()))?;
    if sha256_hex(&baseline_bytes) != NINTENDO_BASELINE_SHA256 {
        return Err("Nintendo oracle baseline SHA-256 mismatch".to_owned());
    }
    let baseline: Value = serde_json::from_slice(&baseline_bytes)
        .map_err(|error| format!("cannot parse {}: {error}", baseline_path.display()))?;
    if baseline.get("schema_version").and_then(Value::as_u64) != Some(1)
        || baseline.get("expected_revision").and_then(Value::as_str) != Some(UPSTREAM_COMMIT)
        || baseline.get("rules_commit").and_then(Value::as_str) != Some(RULES_COMMIT)
    {
        return Err("unexpected Nintendo oracle baseline identity".to_owned());
    }
    let baseline_samples = baseline
        .get("samples")
        .and_then(Value::as_object)
        .ok_or_else(|| "Nintendo oracle baseline samples are missing".to_owned())?;
    let manifest_names = manifest_samples.keys().collect::<BTreeSet<_>>();
    let baseline_names = baseline_samples.keys().collect::<BTreeSet<_>>();
    if manifest_names != baseline_names {
        return Err("Nintendo corpus manifest and oracle baseline sample sets differ".to_owned());
    }

    let mut sample_reports = Vec::with_capacity(baseline_samples.len());
    let mut all_match = true;
    let mut signature_compare_call_total = 0_u64;
    let mut signature_search_call_total = 0_u64;
    let mut attempted_detect_count = 0_u64;
    let mut accepted_detect_count = 0_u64;
    let mut detect_error_count = 0_u64;
    let mut fallback_call_total = 0_u64;
    let mut signature_compare_error_total = 0_u64;
    let mut signature_search_error_total = 0_u64;
    let mut detection_count = 0_u64;
    let mut unambiguous_priority_sample_count = 0_usize;
    let mut nintendo_info_matched_count = 0_usize;
    let mut elapsed_ms = 0_u64;
    for (name, baseline_sample) in baseline_samples {
        let expected = parse_detection_triples(
            baseline_sample
                .get("detections")
                .ok_or_else(|| format!("baseline detections are missing for {name}"))?,
            name,
        )?;
        let (expected_size, expected_sha256) = &manifest_samples[name];
        let input_path = corpus_root.join(name);
        let input = fs::read(&input_path)
            .map_err(|error| format!("cannot read {}: {error}", input_path.display()))?;
        let input_size = input.len();
        let input_size_matches = input_size as u64 == *expected_size;
        let actual_sha256 = sha256_hex(&input);
        let input_sha256_matches = actual_sha256 == *expected_sha256;
        if !input_size_matches || !input_sha256_matches {
            return Err(format!(
                "{name}: generated input identity mismatch: size={} sha256={actual_sha256}",
                input.len()
            ));
        }

        let trace =
            trace_binary_detects_report_with_data(rule_root, &input_path, order_path, input)
                .map_err(|error| format!("{name}: {error}"))?;
        let actual = parse_runtime_detections(&trace, name)?;
        let execution_order = actual
            .iter()
            .map(|(kind, detection_name, version, _)| {
                (kind.clone(), detection_name.clone(), version.clone())
            })
            .collect::<Vec<_>>();
        let (output_order, output_priorities_unambiguous) = sorted_detection_projection(&actual);
        let nintendo_detections = actual
            .iter()
            .filter(|(_, detection_name, _, _)| detection_name.starts_with("Nintendō "))
            .collect::<Vec<_>>();
        let nintendo_info_ok =
            nintendo_detections.len() == 1 && nintendo_detections[0].3 == "fSELF";

        let attempted = report_u64(&trace, "attempted_detect_count", name)?;
        let accepted = report_u64(&trace, "accepted_detect_count", name)?;
        let errors = report_u64(&trace, "detect_error_count", name)?;
        let overlays = report_u64(&trace, "compatibility_overlay_count", name)?;
        let fallbacks = report_u64(&trace, "fallback_call_total", name)?;
        let include_calls = report_u64(&trace, "include_call_count", name)?;
        let compare_errors = report_u64(&trace, "signature_compare_error_total", name)?;
        let search_errors = report_u64(&trace, "signature_search_error_total", name)?;
        let completed = trace.get("completed").and_then(Value::as_bool) == Some(true);
        let lifecycle_ok = attempted == BINARY_SIGNATURE_COUNT as u64
            && accepted == BINARY_SIGNATURE_COUNT as u64
            && errors == 0
            && overlays == 1
            && fallbacks == 0
            && include_calls == 30
            && compare_errors == 0
            && search_errors == 0
            && completed;
        let matches = lifecycle_ok
            && output_priorities_unambiguous
            && output_order == expected
            && nintendo_info_ok;
        all_match &= matches;
        unambiguous_priority_sample_count += usize::from(output_priorities_unambiguous);
        nintendo_info_matched_count += usize::from(nintendo_info_ok);

        signature_compare_call_total = signature_compare_call_total
            .checked_add(report_u64(&trace, "signature_compare_call_total", name)?)
            .ok_or_else(|| "signature compare aggregate overflow".to_owned())?;
        signature_search_call_total = signature_search_call_total
            .checked_add(report_u64(&trace, "signature_search_call_total", name)?)
            .ok_or_else(|| "signature search aggregate overflow".to_owned())?;
        elapsed_ms = elapsed_ms
            .checked_add(report_u64(&trace, "elapsed_ms", name)?)
            .ok_or_else(|| "elapsed millisecond aggregate overflow".to_owned())?;
        attempted_detect_count = attempted_detect_count
            .checked_add(attempted)
            .ok_or_else(|| "attempted detect aggregate overflow".to_owned())?;
        accepted_detect_count = accepted_detect_count
            .checked_add(accepted)
            .ok_or_else(|| "accepted detect aggregate overflow".to_owned())?;
        detect_error_count = detect_error_count
            .checked_add(errors)
            .ok_or_else(|| "detect error aggregate overflow".to_owned())?;
        fallback_call_total = fallback_call_total
            .checked_add(fallbacks)
            .ok_or_else(|| "fallback call aggregate overflow".to_owned())?;
        signature_compare_error_total =
            signature_compare_error_total
                .checked_add(compare_errors)
                .ok_or_else(|| "signature compare error aggregate overflow".to_owned())?;
        signature_search_error_total = signature_search_error_total
            .checked_add(search_errors)
            .ok_or_else(|| "signature search error aggregate overflow".to_owned())?;
        detection_count = detection_count
            .checked_add(actual.len() as u64)
            .ok_or_else(|| "detection aggregate overflow".to_owned())?;

        sample_reports.push(json!({
            "name": name,
            "input": {
                "bytes": input_size,
                "sha256": actual_sha256,
            },
            "expected_output_order": expected,
            "actual_execution_order": execution_order,
            "actual_output_order": output_order,
            "actual_detection_details": actual,
            "output_priorities_unambiguous": output_priorities_unambiguous,
            "nintendo_info_ok": nintendo_info_ok,
            "lifecycle": {
                "attempted_detect_count": attempted,
                "accepted_detect_count": accepted,
                "detect_error_count": errors,
                "compatibility_overlay_count": overlays,
                "fallback_call_total": fallbacks,
                "include_call_count": include_calls,
                "signature_compare_error_total": compare_errors,
                "signature_search_error_total": search_errors,
                "completed": completed,
                "matches": lifecycle_ok,
            },
            "matches": matches,
        }));
    }

    let report = json!({
        "schema_version": 1,
        "operation": "all fixed-order Binary detect functions over the generated Nintendo corpus",
        "scope": "14 generated Binary header samples; exact ordered type/name/version oracle plus Nintendo info invariant",
        "runtime": "rquickjs 0.12.1 / QuickJS-NG 0.15.1",
        "upstream_commit": UPSTREAM_COMMIT,
        "rules_commit": RULES_COMMIT,
        "compatibility_overlay": "nintendo-unused-var-tp-v1",
        "corpus_manifest": normalized_path(corpus_manifest_path),
        "corpus_manifest_sha256": sha256_hex(&corpus_manifest_bytes),
        "baseline": normalized_path(baseline_path),
        "baseline_sha256": sha256_hex(&baseline_bytes),
        "order_manifest": normalized_path(order_path),
        "order_sha256": LINUX_QT5_BINARY_ORDER_SHA256,
        "result_sort_oracle": {
            "component": "XScanEngine@dfe4a419e4f491bb23688ba03c5a5bf39e34da83",
            "source": "xscanengine.cpp::_sortItems, sortRecords, typeToPrio",
            "comparison": "ascending numeric nPrio",
            "equal_priority_limitation": "upstream std::sort has no stable tie-order contract; every multi-detection sample in this corpus has distinct priorities",
        },
        "rule_count_per_sample": BINARY_SIGNATURE_COUNT,
        "sample_count": sample_reports.len(),
        "matched_count": sample_reports.iter().filter(|sample| sample["matches"] == true).count(),
        "attempted_detect_count": attempted_detect_count,
        "accepted_detect_count": accepted_detect_count,
        "detect_error_count": detect_error_count,
        "fallback_call_total": fallback_call_total,
        "signature_compare_error_total": signature_compare_error_total,
        "signature_search_error_total": signature_search_error_total,
        "detection_count": detection_count,
        "unambiguous_priority_sample_count": unambiguous_priority_sample_count,
        "nintendo_info_matched_count": nintendo_info_matched_count,
        "signature_compare_call_total": signature_compare_call_total,
        "signature_search_call_total": signature_search_call_total,
        "elapsed_ms": elapsed_ms,
        "samples": sample_reports,
        "all_match": all_match,
    });
    println!(
        "{}",
        serde_json::to_string_pretty(&report)
            .map_err(|error| format!("cannot serialize corpus report: {error}"))?
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
    let memory_limit_recovery = eval_string(&memory_context, b"String(6 * 7)");

    const STACK_LIMIT_BYTES: usize = 128 * 1024;
    let stack_runtime = new_runtime()?;
    stack_runtime.set_max_stack_size(STACK_LIMIT_BYTES);
    let stack_context = new_context(&stack_runtime)?;
    let stack_limit_error = eval_unit(
        &stack_context,
        b"function recurse() { return 1 + recurse(); } recurse();",
    )
    .err();
    let stack_limit_recovery = eval_string(&stack_context, b"String(6 * 7)");

    const PANIC_SENTINEL: &str = "diec-rquickjs-native-panic-sentinel";
    let panic_runtime = new_runtime()?;
    let panic_context = new_context(&panic_runtime)?;
    panic_context.with(|ctx| {
        let panic_host = Function::new(ctx.clone(), move || -> i32 {
            panic!("{PANIC_SENTINEL}");
        })
        .map_err(|error| error.to_string())?;
        ctx.globals()
            .set("panicHost", panic_host)
            .map_err(|error| error.to_string())
    })?;
    let previous_panic_hook = panic::take_hook();
    panic::set_hook(Box::new(|_| {}));
    let native_panic_result = panic::catch_unwind(AssertUnwindSafe(|| {
        eval_unit(&panic_context, b"panicHost();")
    }));
    panic::set_hook(previous_panic_hook);
    let native_panic_payload = native_panic_result.as_ref().err().and_then(|payload| {
        payload
            .downcast_ref::<&str>()
            .map(|value| (*value).to_owned())
            .or_else(|| payload.downcast_ref::<String>().cloned())
    });
    let native_panic_recovery = eval_string(&panic_context, b"String(6 * 7)");

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
        && memory_limit_error.is_some()
        && memory_limit_recovery.as_deref() == Ok("42")
        && stack_limit_error.is_some()
        && stack_limit_recovery.as_deref() == Ok("42")
        && native_panic_payload.as_deref() == Some(PANIC_SENTINEL)
        && native_panic_recovery.as_deref() == Ok("42");
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
            "same_context_recovery": {
                "result": memory_limit_recovery.as_deref().ok(),
                "error": memory_limit_recovery.as_ref().err(),
            },
        },
        "stack_limit": {
            "bytes": STACK_LIMIT_BYTES,
            "error": stack_limit_error,
            "same_context_recovery": {
                "result": stack_limit_recovery.as_deref().ok(),
                "error": stack_limit_recovery.as_ref().err(),
            },
        },
        "native_host_panic": {
            "caught_at_rust_eval_boundary": native_panic_result.is_err(),
            "payload_matches_sentinel": native_panic_payload.as_deref() == Some(PANIC_SENTINEL),
            "eval_returned_without_panic": native_panic_result.is_ok(),
            "same_context_recovery": {
                "result": native_panic_recovery.as_deref().ok(),
                "error": native_panic_recovery.as_ref().err(),
            },
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
         <main-rule-root> <input-file> <binary-order-json>\n       \
         diec-rquickjs-rule-runtime-spike verify-binary-corpus \
         <main-rule-root> <corpus-dir> <corpus-manifest-json> \
         <baseline-json> <binary-order-json>\n       \
         diec-rquickjs-rule-runtime-spike verify-pe-rule \
         <main-rule-root> <pe-fixture-json> <qt5-baseline-json>\n       \
         diec-rquickjs-rule-runtime-spike verify-elf-rule \
         <main-rule-root> <elf-fixture-json> <qt5-baseline-json>"
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
    } else if command == "verify-binary-corpus" && roots.len() == 5 {
        verify_binary_corpus(&roots[0], &roots[1], &roots[2], &roots[3], &roots[4])
    } else if command == "verify-pe-rule" && roots.len() == 3 {
        verify_pe_rule(&roots[0], &roots[1], &roots[2])
    } else if command == "verify-elf-rule" && roots.len() == 3 {
        verify_elf_rule(&roots[0], &roots[1], &roots[2])
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
        BinaryHostContext, BinaryStringContext, ElfRuleContext, HostFilePart,
        NINTENDO_COMPAT_DECLARATION, NINTENDO_RULE_BYTES, NINTENDO_VAR_DECLARATION, PeRuleContext,
        TextUnicodeType, apply_compatibility_overlay, apply_exact_lifecycle_overlay,
        collect_rule_files, elf_matcher_map_projection, eval_rule_lexical, eval_string, eval_unit,
        install_diagnostic_host_fallbacks, install_nintendo_host,
        install_nintendo_host_with_context, install_nintendo_host_with_context_and_strings,
        new_context, new_runtime, nonnegative_index, normalized_path, parse_detection_triples,
        parse_scope_detections, parse_scope_fixture_order, pe_physical_map_projection,
        qt5_elf_matcher_map_projection, qt5_pe_physical_map_projection, read_ascii,
        read_byte_array, read_signed, read_unsigned, sha256_hex, shift_right_unsigned,
        sorted_detection_projection, upstream_type_priority,
    };
    use std::fs;
    use std::path::{Path, PathBuf};
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
    fn upstream_result_priority_matches_fixed_xscanengine_mapping() {
        let cases = [
            ("operation system", 10),
            ("virtual machine", 10),
            ("format", 12),
            ("platform", 14),
            ("dos extender", 14),
            ("linker", 20),
            ("compiler", 30),
            ("language", 40),
            ("library", 50),
            ("tool", 60),
            ("pe tool", 60),
            ("sign tool", 60),
            ("apk tool", 60),
            ("protector", 70),
            ("cryptor", 70),
            ("crypter", 70),
            (".net obfuscator", 80),
            ("apk obfuscator", 80),
            ("jar obfuscator", 80),
            ("dongle protection", 90),
            ("protection", 90),
            ("packer", 100),
            (".net compressor", 100),
            ("joiner", 110),
            ("sfx", 120),
            ("installer", 120),
            ("virus", 70),
            ("malware", 70),
            ("trojan", 70),
            ("corrupted data", 70),
            ("personal data", 70),
            ("author", 70),
            ("debug data", 200),
            ("audio", 1000),
        ];
        for (kind, expected) in cases {
            assert_eq!(upstream_type_priority(kind), expected, "{kind}");
        }
        assert_eq!(upstream_type_priority("~!FORMAT"), 12);
    }

    #[test]
    fn pe_context_matches_fixed_qt5_entry_points_and_physical_maps() {
        let baseline: serde_json::Value =
            serde_json::from_str(include_str!("../../../docs/research/data/pe-rule-qt5.json"))
                .expect("fixed Qt5 PE rule baseline should be valid JSON");
        let cases = baseline["cases"]
            .as_array()
            .expect("fixed Qt5 PE baseline should have cases");
        assert_eq!(cases.len(), 3);
        for case in cases {
            assert_eq!(case["parser_valid"], true);
            let id = case["id"].as_str().expect("case should have an id");
            let data = decode_hex(case["data_hex"].as_str().expect("case should contain data"));
            let context = PeRuleContext::parse(&data)
                .unwrap_or_else(|error| panic!("{id}: PE context should parse: {error}"));
            let entry_point = context
                .entry_point_offset
                .and_then(|offset| i64::try_from(offset).ok())
                .unwrap_or(-1);
            assert_eq!(entry_point, case["entry_point_offset"].as_i64().unwrap());
            assert_eq!(
                pe_physical_map_projection(&context),
                qt5_pe_physical_map_projection(&case["memory_map"])
                    .expect("Qt5 map should project")
            );
            assert_eq!(
                context.aliased_out_of_bounds_sections,
                usize::from(id == "cygwin32_entry_point_truncated")
            );
        }
    }

    #[test]
    fn elf_context_matches_fixed_qt5_entry_points_and_safe_matcher_maps() {
        let baseline: serde_json::Value = serde_json::from_str(include_str!(
            "../../../docs/research/data/elf-rule-qt5.json"
        ))
        .expect("fixed Qt5 ELF rule baseline should be valid JSON");
        let cases = baseline["cases"]
            .as_array()
            .expect("fixed Qt5 ELF baseline should have cases");
        assert_eq!(cases.len(), 6);
        for case in cases {
            assert_eq!(case["parser_valid"], true);
            let id = case["id"].as_str().expect("case should have an id");
            let data = decode_hex(case["data_hex"].as_str().expect("case should contain data"));
            let context = ElfRuleContext::parse(&data)
                .unwrap_or_else(|error| panic!("{id}: ELF context should parse: {error}"));
            assert_eq!(
                u64::from(context.elf_class) * 32,
                case["elf_class"].as_u64().unwrap()
            );
            let entry_point = context
                .entry_point_offset
                .and_then(|offset| i64::try_from(offset).ok())
                .unwrap_or(-1);
            assert_eq!(entry_point, case["entry_point_offset"].as_i64().unwrap());
            let expected = qt5_elf_matcher_map_projection(&case["memory_map"])
                .expect("Qt5 ELF map should safely project");
            assert_eq!(elf_matcher_map_projection(&context), expected.matcher_map);
            if id.ends_with("_truncated") {
                assert_eq!(context.out_of_bounds_loads, 2);
                assert_eq!(expected.discarded_virtual_records, 2);
                assert_eq!(expected.discarded_nonpositive_size_records, 2);
                assert_eq!(expected.discarded_overlay_sentinel_records, 0);
            } else {
                assert_eq!(context.out_of_bounds_loads, 0);
                assert_eq!(expected.discarded_virtual_records, 0);
                assert_eq!(expected.discarded_nonpositive_size_records, 0);
                assert_eq!(expected.discarded_overlay_sentinel_records, 1);
            }
            assert_eq!(expected.discarded_negative_offset_records, 0);
        }
    }

    #[test]
    fn elf_context_rejects_malformed_counts_ranges_and_missing_loads() {
        assert!(ElfRuleContext::parse(&[]).is_err());
        let baseline: serde_json::Value = serde_json::from_str(include_str!(
            "../../../docs/research/data/elf-rule-qt5.json"
        ))
        .expect("fixed Qt5 ELF rule baseline should be valid JSON");
        let mut data = decode_hex(
            baseline["cases"][3]["data_hex"]
                .as_str()
                .expect("ELF64 case should contain data"),
        );

        let mut short_entry = data.clone();
        short_entry[54..56].copy_from_slice(&0_u16.to_le_bytes());
        assert!(
            ElfRuleContext::parse(&short_entry)
                .expect_err("undersized program entry must fail")
                .contains("smaller")
        );

        let mut excessive_count = data.clone();
        excessive_count[56..58].copy_from_slice(&1025_u16.to_le_bytes());
        assert!(
            ElfRuleContext::parse(&excessive_count)
                .expect_err("excessive program entry count must fail")
                .contains("limit 1024")
        );

        data[72..80].copy_from_slice(&u64::MAX.to_le_bytes());
        assert!(
            ElfRuleContext::parse(&data)
                .expect_err("overflowing segment range must fail")
                .contains("range overflow")
        );

        let mut no_loads = decode_hex(
            baseline["cases"][3]["data_hex"]
                .as_str()
                .expect("ELF64 case should contain data"),
        );
        no_loads[64..68].copy_from_slice(&0_u32.to_le_bytes());
        no_loads[120..124].copy_from_slice(&0_u32.to_le_bytes());
        assert!(
            ElfRuleContext::parse(&no_loads)
                .expect_err("missing PT_LOAD must fail")
                .contains("no non-empty PT_LOAD")
        );
    }

    #[test]
    fn output_projection_sorts_distinct_priorities_and_rejects_tie_evidence() {
        let distinct = vec![
            (
                "audio".to_owned(),
                "audio-name".to_owned(),
                "audio-version".to_owned(),
                String::new(),
            ),
            (
                "platform".to_owned(),
                "platform-name".to_owned(),
                "platform-version".to_owned(),
                String::new(),
            ),
            (
                "format".to_owned(),
                "format-name".to_owned(),
                "format-version".to_owned(),
                "format-info".to_owned(),
            ),
        ];
        let (projection, unambiguous) = sorted_detection_projection(&distinct);
        assert!(unambiguous);
        assert_eq!(
            projection,
            [
                (
                    "format".to_owned(),
                    "format-name".to_owned(),
                    "format-version".to_owned(),
                ),
                (
                    "platform".to_owned(),
                    "platform-name".to_owned(),
                    "platform-version".to_owned(),
                ),
                (
                    "audio".to_owned(),
                    "audio-name".to_owned(),
                    "audio-version".to_owned(),
                ),
            ]
        );

        let tied = vec![
            (
                "audio".to_owned(),
                "first".to_owned(),
                String::new(),
                String::new(),
            ),
            (
                "unknown".to_owned(),
                "second".to_owned(),
                String::new(),
                String::new(),
            ),
        ];
        assert!(!sorted_detection_projection(&tied).1);
    }

    #[test]
    fn corpus_oracle_helpers_hash_and_strictly_parse_triples() {
        assert_eq!(
            sha256_hex(b"abc"),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        );
        let detections = serde_json::json!([["format", "name", "version"]]);
        assert_eq!(
            parse_detection_triples(&detections, "sample").expect("valid triple"),
            [("format".to_owned(), "name".to_owned(), "version".to_owned())]
        );
        let invalid = serde_json::json!([["format", "name", "version", "info"]]);
        assert!(parse_detection_triples(&invalid, "sample").is_err());
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
    fn scan_and_file_part_context_matches_pinned_qt5_oracle() {
        let oracle: serde_json::Value = serde_json::from_str(include_str!(
            "../../../docs/research/data/signature-oracle-qt5.json"
        ))
        .expect("Qt5 signature oracle should be valid JSON");
        let cases = oracle["cases"]
            .as_array()
            .expect("Qt5 signature oracle should contain cases");
        let mut checked = 0_usize;
        for case in cases {
            let Some(file_part_name) = case["binary_script_file_part"].as_str() else {
                continue;
            };
            let Some(scan_id) = case["binary_script_scan_id"].as_str() else {
                continue;
            };
            checked += 1;
            let file_part = match file_part_name {
                "header" => HostFilePart::Header,
                "resource" => HostFilePart::Resource,
                "debugdata" => HostFilePart::DebugData,
                other => panic!("unexpected oracle file part: {other}"),
            };
            let actual = BinaryHostContext::new(file_part, 0, 0)
                .expect("oracle context should be valid")
                .with_scan_id(scan_id);
            assert_eq!(
                actual.scan_id,
                case["binary_script_get_scan_id_result"]
                    .as_str()
                    .expect("oracle scan ID should be a string")
            );
            assert_eq!(
                actual.is_resource(),
                case["binary_script_is_resource_result"]
                    .as_bool()
                    .expect("oracle resource flag should be a bool")
            );
            assert_eq!(
                actual.is_debug_data(),
                case["binary_script_is_debug_data_result"]
                    .as_bool()
                    .expect("oracle debug-data flag should be a bool")
            );
            assert_eq!(
                actual.is_file_part(),
                case["binary_script_is_file_part_result"]
                    .as_bool()
                    .expect("oracle file-part flag should be a bool")
            );
        }
        assert_eq!(checked, 3);
    }

    #[test]
    fn text_context_is_deterministic_across_upstream_prefill_states() {
        let oracle: serde_json::Value = serde_json::from_str(include_str!(
            "../../../docs/research/data/signature-oracle-qt5.json"
        ))
        .expect("Qt5 signature oracle should be valid JSON");
        let cases = oracle["cases"]
            .as_array()
            .expect("Qt5 signature oracle should contain cases");
        let find = |id: &str| {
            cases
                .iter()
                .find(|case| case["id"].as_str() == Some(id))
                .unwrap_or_else(|| panic!("missing oracle case {id}"))
        };
        let nontext_zero = find("binary_script_nontext_prefill_zero");
        let nontext_one = find("binary_script_nontext_prefill_one");
        assert_eq!(
            nontext_zero["binary_script_prefill_is_text_result"].as_bool(),
            Some(false)
        );
        assert_eq!(
            nontext_one["binary_script_prefill_is_text_result"].as_bool(),
            Some(true),
            "fixed upstream result must expose the uninitialized-state divergence"
        );
        let nontext = BinaryStringContext::from_file_name(&decode_hex("00010203"), "");
        assert!(!nontext.is_unicode_text());
        assert!(!nontext.is_text());

        for id in [
            "binary_script_unicode_prefill_zero",
            "binary_script_unicode_prefill_one",
        ] {
            let case = find(id);
            assert_eq!(
                case["binary_script_prefill_is_unicode_text_result"].as_bool(),
                Some(true)
            );
            assert_eq!(
                case["binary_script_prefill_is_text_result"].as_bool(),
                Some(true)
            );
        }
        let unicode = BinaryStringContext::from_file_name(&decode_hex("fffe4100"), "");
        assert!(unicode.is_unicode_text());
        assert!(unicode.is_text());
    }

    #[test]
    fn fixed_context_rules_match_pinned_qt5_oracle_end_to_end() {
        const RESULT_SHIM: &[u8] = br#"
            var bDetected, sType, sName, sVersion, sOptions;
            function meta(type, name, version, options) {
                sType = type;
                sName = name ? name : String();
                sVersion = version ? version : String();
                sOptions = options ? options : String();
                bDetected = false;
            }
            function _error(message) { throw new Error(String(message)); }
            function result() {
                if (bDetected) {
                    sVersion = sVersion ? sVersion : String();
                    sOptions = sOptions ? sOptions : String();
                    if (!sName) _error("No input detection name.");
                    _setResult(sType, sName, sVersion, sOptions);
                }
                sName = sVersion = sOptions = "";
                var value = bDetected;
                bDetected = false;
                return value;
            }
        "#;

        let oracle: serde_json::Value = serde_json::from_str(include_str!(
            "../../../docs/research/data/context-rule-qt5.json"
        ))
        .expect("Qt5 context-rule oracle should be valid JSON");
        let cases = oracle["cases"]
            .as_array()
            .expect("Qt5 context-rule oracle should contain cases");
        let rule_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../../upstream/Detect-It-Easy/db/Binary");
        assert_eq!(cases.len(), 8);

        for case in cases {
            let id = case["id"].as_str().expect("oracle case should have an id");
            let data = decode_hex(
                case["data_hex"]
                    .as_str()
                    .expect("oracle case should have data"),
            );
            let file_part = match case["file_part"]
                .as_str()
                .expect("oracle case should have a file part")
            {
                "header" => HostFilePart::Header,
                "resource" => HostFilePart::Resource,
                "debugdata" => HostFilePart::DebugData,
                other => panic!("unexpected context-rule file part: {other}"),
            };
            let scan_id = case["scan_id"]
                .as_str()
                .expect("oracle case should have a scan ID");
            let file_name = case["file_name"]
                .as_str()
                .expect("oracle case should have a file name");
            let rule_name = Path::new(
                case["rule_path"]
                    .as_str()
                    .expect("oracle case should have a rule path"),
            )
            .file_name()
            .expect("oracle rule path should have a file name");
            let rule_path = rule_root.join(rule_name);
            let source = fs::read(&rule_path)
                .unwrap_or_else(|error| panic!("cannot read {}: {error}", rule_path.display()));

            let runtime = new_runtime().expect("runtime should be created");
            let context = new_context(&runtime).expect("context should be created");
            let detections = Arc::new(Mutex::new(Vec::new()));
            let bytes = Arc::new(data);
            let host_context = BinaryHostContext::new(
                file_part,
                i64::try_from(bytes.len()).expect("fixture size should fit qint64"),
                0,
            )
            .expect("fixed context should be valid")
            .with_scan_id(scan_id);
            let string_context = BinaryStringContext::from_file_name(&bytes, file_name);
            install_nintendo_host_with_context_and_strings(
                &context,
                bytes,
                Arc::clone(&detections),
                host_context,
                string_context,
            )
            .expect("host should be installed");
            eval_unit(&context, RESULT_SHIM).expect("result shim should evaluate");
            let detect_result = eval_rule_lexical(&context, &source, true)
                .unwrap_or_else(|error| panic!("{id} should evaluate: {error}"));
            assert_eq!(
                detect_result,
                if case["detect_result"].as_bool() == Some(true) {
                    "true"
                } else {
                    "false"
                },
                "detect result mismatch for {id}"
            );
            let actual_detections = detections
                .lock()
                .expect("fixture result mutex should not be poisoned")
                .clone();
            assert_eq!(
                serde_json::to_value(actual_detections).expect("detections should serialize"),
                case["detections"],
                "detection mismatch for {id}"
            );
        }
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
                    String(Binary.isUTF8Text()) + "|" +
                    String(Binary.isUnicodeText()) + "|" +
                    String(Binary.isText())"#,
            )
            .expect("string HostApi should be callable"),
            "C|function test() {}\n|true|false|false|true"
        );
        assert_eq!(trace.get_file_suffix_calls.load(Ordering::Relaxed), 1);
        assert_eq!(trace.get_header_string_calls.load(Ordering::Relaxed), 1);
        assert_eq!(trace.is_plain_text_calls.load(Ordering::Relaxed), 1);
        assert_eq!(trace.is_utf8_text_calls.load(Ordering::Relaxed), 1);
        assert_eq!(trace.is_unicode_text_calls.load(Ordering::Relaxed), 1);
        assert_eq!(trace.is_text_calls.load(Ordering::Relaxed), 1);
    }

    #[test]
    fn scan_and_file_part_context_is_exposed_as_native_host_api() {
        let runtime = new_runtime().expect("runtime should be created");
        let context = new_context(&runtime).expect("context should be created");
        let bytes = Arc::new(vec![0x41]);
        let host_context = BinaryHostContext::new(HostFilePart::Resource, 1, 0)
            .expect("fixed context should be valid")
            .with_scan_id("24");
        let string_context = BinaryStringContext::from_file_name(&bytes, "");
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
                br#"Binary.getScanID() + "|" +
                    String(Binary.isResource()) + "|" +
                    String(Binary.isDebugData()) + "|" +
                    String(Binary.isFilePart())"#,
            )
            .expect("scan and file-part HostApi should be callable"),
            "24|true|false|true"
        );
        assert_eq!(trace.get_scan_id_calls.load(Ordering::Relaxed), 1);
        assert_eq!(trace.is_resource_calls.load(Ordering::Relaxed), 1);
        assert_eq!(trace.is_debug_data_calls.load(Ordering::Relaxed), 1);
        assert_eq!(trace.is_file_part_calls.load(Ordering::Relaxed), 1);
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
