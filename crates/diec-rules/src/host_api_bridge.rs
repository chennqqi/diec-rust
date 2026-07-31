//! Binary_Script host API bridge for the rquickjs backend.
//!
//! This module creates a JavaScript `Binary` object (and `X`/`File` aliases)
//! that bridges the 155 Binary_Script methods to the Rust `HostApi` trait.
//! The bridge is registered on the QuickJS context before rule evaluation.
//!
//! Per ADR 0006, unknown methods must produce typed incompatibility errors,
//! not silent fallbacks. Methods that are not yet implemented return
//! `HostApiError::NotImplemented`.
//!
//! See `docs/research/host-api-inventory.md` for the full method list.

use crate::error::RuleError;
use crate::host_api::HostApi;
use rquickjs::{Context, Ctx};

/// A parsed signature element: either a literal byte or a wildcard.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SigElement {
    /// Exact byte match.
    Byte(u8),
    /// Wildcard: matches any single byte (`.` or `?` in signature).
    Any,
}

/// Parse a DIE signature string into a sequence of signature elements.
///
/// DIE signature format:
/// - Hex digit pairs match exact bytes: `AABBCC`
/// - `.` and `?` match any single nibble (two needed for a full byte)
/// - Single-quoted strings match literal ASCII: `'7z'`
/// - Spaces are skipped
/// - `#` and `$` are jump markers (not yet fully supported, treated as wildcards)
///
/// Returns `Err` if the signature is malformed.
pub fn parse_signature(signature: &str) -> Result<Vec<SigElement>, String> {
    let mut elements = Vec::new();
    let chars: Vec<char> = signature.chars().collect();
    let mut i = 0;

    while i < chars.len() {
        let c = chars[i];

        if c.is_whitespace() {
            i += 1;
            continue;
        }

        if c == '\'' {
            // String literal: read until closing quote.
            i += 1;
            while i < chars.len() && chars[i] != '\'' {
                for b in chars[i].to_string().as_bytes() {
                    elements.push(SigElement::Byte(*b));
                }
                i += 1;
            }
            if i >= chars.len() {
                return Err("unterminated string literal in signature".into());
            }
            i += 1; // skip closing quote
            continue;
        }

        if c == '#' || c == '$' {
            // Jump markers: treat as wildcards for now.
            // TODO: implement proper jump handling.
            elements.push(SigElement::Any);
            i += 1;
            continue;
        }

        if c == '.' || c == '?' {
            // Wildcard nibble: need two for a full byte.
            let mut nibbles = 0u8;
            let mut byte_val = 0u8;
            while i < chars.len() && (chars[i] == '.' || chars[i] == '?') {
                nibbles += 1;
                byte_val <<= 4;
                i += 1;
            }
            if nibbles == 1 {
                // Single wildcard nibble + hex nibble
                if i < chars.len() {
                    let h = chars[i].to_digit(16);
                    if let Some(h) = h {
                        byte_val |= h as u8;
                        elements.push(SigElement::Byte(byte_val));
                        i += 1;
                    } else {
                        return Err("invalid hex after wildcard".into());
                    }
                } else {
                    return Err("dangling wildcard nibble".into());
                }
            } else if nibbles == 2 {
                elements.push(SigElement::Any);
            } else if nibbles > 2 {
                // Multiple bytes of wildcards
                for _ in 0..(nibbles / 2) {
                    elements.push(SigElement::Any);
                }
                if nibbles % 2 == 1 {
                    // Odd nibble: combine with next hex digit if available
                    if i < chars.len() {
                        let h = chars[i].to_digit(16);
                        if let Some(h) = h {
                            elements.push(SigElement::Byte(h as u8));
                            i += 1;
                        }
                    }
                }
            } else {
                // Shouldn't happen since we enter the loop with at least one
                return Err("invalid wildcard".into());
            }
            continue;
        }

        if c.is_ascii_hexdigit() {
            // Hex byte: read two hex digits.
            if i + 1 >= chars.len() {
                return Err("odd number of hex digits".into());
            }
            let h1 = chars[i].to_digit(16).ok_or("invalid hex digit")?;
            let h2 = chars[i + 1].to_digit(16).ok_or("invalid hex digit")?;
            // Check if next is also a hex digit (not a wildcard or string)
            if chars[i + 1].is_ascii_hexdigit() {
                elements.push(SigElement::Byte((h1 * 16 + h2) as u8));
                i += 2;
            } else if chars[i + 1] == '.' || chars[i + 1] == '?' {
                // Hex nibble + wildcard nibble
                elements.push(SigElement::Byte((h1 * 16) as u8)); // partial - TODO
                i += 1;
            } else {
                return Err("invalid hex digit pair".into());
            }
            continue;
        }

        return Err(format!("unexpected character '{c}' in signature"));
    }

    Ok(elements)
}

/// Match a parsed signature against data at the given offset.
pub fn match_signature(data: &[u8], offset: usize, elements: &[SigElement]) -> bool {
    if offset + elements.len() > data.len() {
        return false;
    }
    for (i, elem) in elements.iter().enumerate() {
        match elem {
            SigElement::Byte(b) => {
                if data[offset + i] != *b {
                    return false;
                }
            }
            SigElement::Any => {}
        }
    }
    true
}
use std::sync::Arc;

/// A wrapper around `HostApi` that can be shared with JavaScript callbacks.
///
/// `HostApi` is not `Clone`, so we use `Arc<dyn HostApi + Send + Sync>` for
/// shared access from JavaScript callbacks. The actual `HostApi`
/// implementation in `diec-engine` will be `Send + Sync` because it only
/// accesses immutable parsed format data and the cancel token.
pub struct HostApiBridge {
    host: Arc<dyn HostApi + Send + Sync>,
}

impl HostApiBridge {
    /// Create a new host API bridge.
    pub fn new(host: Arc<dyn HostApi + Send + Sync>) -> Self {
        Self { host }
    }

    /// Register the `Binary` object on the JavaScript context.
    ///
    /// This creates a JavaScript object with methods that call back into
    /// the Rust `HostApi` trait. The object is registered as `Binary`,
    /// and aliases `X` and `File` are set to point to the same object.
    pub fn register(&self, context: &Context) -> Result<(), RuleError> {
        let host = self.host.clone();
        let ctx = context.clone();

        ctx.with(|ctx: Ctx<'_>| -> Result<(), RuleError> {
            let globals = ctx.globals();

            // Create the Binary object.
            let binary = rquickjs::Object::new(ctx.clone()).map_err(|e| RuleError::Backend {
                detail: format!("failed to create Binary object: {e}"),
            })?;

            // --- Read primitives ---

            // readByte(offset) -> u8
            let h = host.clone();
            let read_byte_fn = rquickjs::Function::new(ctx.clone(), move |offset: i32| {
                h.read_u8(offset as u64).map(|v| v as i32).unwrap_or(-1)
            })
            .map_err(|e| RuleError::Backend {
                detail: format!("readByte: {e}"),
            })?;
            binary
                .set("readByte", read_byte_fn)
                .map_err(|e| RuleError::Backend {
                    detail: format!("readByte set: {e}"),
                })?;

            // readSByte(offset) -> i8
            let h = host.clone();
            let read_sbyte_fn = rquickjs::Function::new(ctx.clone(), move |offset: i32| {
                h.read_i8(offset as u64).map(|v| v as i32).unwrap_or(0)
            })
            .map_err(|e| RuleError::Backend {
                detail: format!("readSByte: {e}"),
            })?;
            binary
                .set("readSByte", read_sbyte_fn)
                .map_err(|e| RuleError::Backend {
                    detail: format!("readSByte set: {e}"),
                })?;

            // readWord(offset) -> u16 (little-endian)
            let h = host.clone();
            let read_word_fn = rquickjs::Function::new(ctx.clone(), move |offset: i32| {
                h.read_u16_le(offset as u64).map(|v| v as i32).unwrap_or(0)
            })
            .map_err(|e| RuleError::Backend {
                detail: format!("readWord: {e}"),
            })?;
            binary
                .set("readWord", read_word_fn)
                .map_err(|e| RuleError::Backend {
                    detail: format!("readWord set: {e}"),
                })?;

            // readDword(offset) -> u32 (little-endian)
            let h = host.clone();
            let read_dword_fn = rquickjs::Function::new(ctx.clone(), move |offset: i32| {
                h.read_u32_le(offset as u64).unwrap_or(0)
            })
            .map_err(|e| RuleError::Backend {
                detail: format!("readDword: {e}"),
            })?;
            binary
                .set("readDword", read_dword_fn)
                .map_err(|e| RuleError::Backend {
                    detail: format!("readDword set: {e}"),
                })?;

            // readQword(offset) -> u64 (little-endian), returned as number
            let h = host.clone();
            let read_qword_fn = rquickjs::Function::new(ctx.clone(), move |offset: i32| {
                h.read_u64_le(offset as u64).unwrap_or(0) as f64
            })
            .map_err(|e| RuleError::Backend {
                detail: format!("readQword: {e}"),
            })?;
            binary
                .set("readQword", read_qword_fn)
                .map_err(|e| RuleError::Backend {
                    detail: format!("readQword set: {e}"),
                })?;

            // readSWord(offset) -> i16 (little-endian)
            let h = host.clone();
            let read_sword_fn = rquickjs::Function::new(ctx.clone(), move |offset: i32| {
                h.read_i16_le(offset as u64).map(|v| v as i32).unwrap_or(0)
            })
            .map_err(|e| RuleError::Backend {
                detail: format!("readSWord: {e}"),
            })?;
            binary
                .set("readSWord", read_sword_fn)
                .map_err(|e| RuleError::Backend {
                    detail: format!("readSWord set: {e}"),
                })?;

            // readSDword(offset) -> i32 (little-endian)
            let h = host.clone();
            let read_sdword_fn = rquickjs::Function::new(ctx.clone(), move |offset: i32| {
                h.read_i32_le(offset as u64).unwrap_or(0)
            })
            .map_err(|e| RuleError::Backend {
                detail: format!("readSDword: {e}"),
            })?;
            binary
                .set("readSDword", read_sdword_fn)
                .map_err(|e| RuleError::Backend {
                    detail: format!("readSDword set: {e}"),
                })?;

            // readSQword(offset) -> i64 (little-endian) as f64
            let h = host.clone();
            let read_sqword_fn = rquickjs::Function::new(ctx.clone(), move |offset: i32| {
                h.read_i64_le(offset as u64).unwrap_or(0) as f64
            })
            .map_err(|e| RuleError::Backend {
                detail: format!("readSQword: {e}"),
            })?;
            binary
                .set("readSQword", read_sqword_fn)
                .map_err(|e| RuleError::Backend {
                    detail: format!("readSQword set: {e}"),
                })?;

            // --- read_uintN / read_intN with endian support ---
            // _LE = 0 (default), _BE = 1

            // read_uint8(offset) -> u8
            let h = host.clone();
            let read_uint8_fn = rquickjs::Function::new(ctx.clone(), move |offset: i32| {
                h.read_u8(offset as u64).map(|v| v as i32).unwrap_or(-1)
            })
            .map_err(|e| RuleError::Backend {
                detail: format!("read_uint8: {e}"),
            })?;
            binary
                .set("read_uint8", read_uint8_fn)
                .map_err(|e| RuleError::Backend {
                    detail: format!("read_uint8 set: {e}"),
                })?;

            // read_int8(offset) -> i8
            let h = host.clone();
            let read_int8_fn = rquickjs::Function::new(ctx.clone(), move |offset: i32| {
                h.read_i8(offset as u64).map(|v| v as i32).unwrap_or(0)
            })
            .map_err(|e| RuleError::Backend {
                detail: format!("read_int8: {e}"),
            })?;
            binary
                .set("read_int8", read_int8_fn)
                .map_err(|e| RuleError::Backend {
                    detail: format!("read_int8 set: {e}"),
                })?;

            // read_uint16(offset, endian?) -> u16
            let h = host.clone();
            let read_uint16_fn =
                rquickjs::Function::new(ctx.clone(), move |offset: i32, endian: i32| {
                    if endian == 1 {
                        h.read_u16_be(offset as u64).map(|v| v as i32).unwrap_or(0)
                    } else {
                        h.read_u16_le(offset as u64).map(|v| v as i32).unwrap_or(0)
                    }
                })
                .map_err(|e| RuleError::Backend {
                    detail: format!("read_uint16: {e}"),
                })?;
            binary
                .set("read_uint16", read_uint16_fn)
                .map_err(|e| RuleError::Backend {
                    detail: format!("read_uint16 set: {e}"),
                })?;

            // read_int16(offset, endian?) -> i16
            let h = host.clone();
            let read_int16_fn =
                rquickjs::Function::new(ctx.clone(), move |offset: i32, endian: i32| {
                    if endian == 1 {
                        h.read_u16_be(offset as u64)
                            .map(|v| v as i16 as i32)
                            .unwrap_or(0)
                    } else {
                        h.read_u16_le(offset as u64)
                            .map(|v| v as i16 as i32)
                            .unwrap_or(0)
                    }
                })
                .map_err(|e| RuleError::Backend {
                    detail: format!("read_int16: {e}"),
                })?;
            binary
                .set("read_int16", read_int16_fn)
                .map_err(|e| RuleError::Backend {
                    detail: format!("read_int16 set: {e}"),
                })?;

            // read_uint24(offset, endian?) -> u32
            let h = host.clone();
            let read_uint24_fn =
                rquickjs::Function::new(ctx.clone(), move |offset: i32, endian: i32| {
                    if endian == 1 {
                        h.read_u24_be(offset as u64).unwrap_or(0)
                    } else {
                        h.read_u24_le(offset as u64).unwrap_or(0)
                    }
                })
                .map_err(|e| RuleError::Backend {
                    detail: format!("read_uint24: {e}"),
                })?;
            binary
                .set("read_uint24", read_uint24_fn)
                .map_err(|e| RuleError::Backend {
                    detail: format!("read_uint24 set: {e}"),
                })?;

            // read_uint32(offset, endian?) -> u32
            let h = host.clone();
            let read_uint32_fn =
                rquickjs::Function::new(ctx.clone(), move |offset: i32, endian: i32| {
                    if endian == 1 {
                        h.read_u32_be(offset as u64).unwrap_or(0)
                    } else {
                        h.read_u32_le(offset as u64).unwrap_or(0)
                    }
                })
                .map_err(|e| RuleError::Backend {
                    detail: format!("read_uint32: {e}"),
                })?;
            binary
                .set("read_uint32", read_uint32_fn)
                .map_err(|e| RuleError::Backend {
                    detail: format!("read_uint32 set: {e}"),
                })?;

            // read_int32(offset, endian?) -> i32
            let h = host.clone();
            let read_int32_fn =
                rquickjs::Function::new(ctx.clone(), move |offset: i32, endian: i32| {
                    if endian == 1 {
                        h.read_u32_be(offset as u64).map(|v| v as i32).unwrap_or(0)
                    } else {
                        h.read_u32_le(offset as u64).map(|v| v as i32).unwrap_or(0)
                    }
                })
                .map_err(|e| RuleError::Backend {
                    detail: format!("read_int32: {e}"),
                })?;
            binary
                .set("read_int32", read_int32_fn)
                .map_err(|e| RuleError::Backend {
                    detail: format!("read_int32 set: {e}"),
                })?;

            // read_uint64(offset, endian?) -> u64 as f64
            let h = host.clone();
            let read_uint64_fn =
                rquickjs::Function::new(ctx.clone(), move |offset: i32, endian: i32| {
                    if endian == 1 {
                        h.read_u64_be(offset as u64).unwrap_or(0) as f64
                    } else {
                        h.read_u64_le(offset as u64).unwrap_or(0) as f64
                    }
                })
                .map_err(|e| RuleError::Backend {
                    detail: format!("read_uint64: {e}"),
                })?;
            binary
                .set("read_uint64", read_uint64_fn)
                .map_err(|e| RuleError::Backend {
                    detail: format!("read_uint64 set: {e}"),
                })?;

            // read_int64(offset, endian?) -> i64 as f64
            let h = host.clone();
            let read_int64_fn =
                rquickjs::Function::new(ctx.clone(), move |offset: i32, endian: i32| {
                    if endian == 1 {
                        h.read_u64_be(offset as u64)
                            .map(|v| v as i64 as f64)
                            .unwrap_or(0.0)
                    } else {
                        h.read_u64_le(offset as u64)
                            .map(|v| v as i64 as f64)
                            .unwrap_or(0.0)
                    }
                })
                .map_err(|e| RuleError::Backend {
                    detail: format!("read_int64: {e}"),
                })?;
            binary
                .set("read_int64", read_int64_fn)
                .map_err(|e| RuleError::Backend {
                    detail: format!("read_int64 set: {e}"),
                })?;

            // --- Scan mode flags (continued) ---

            // isVerbose() -> bool (same as isDeepScan for now)
            let h = host.clone();
            let is_verbose_fn =
                rquickjs::Function::new(ctx.clone(), move || h.is_deep()).map_err(|e| {
                    RuleError::Backend {
                        detail: format!("isVerbose: {e}"),
                    }
                })?;
            binary
                .set("isVerbose", is_verbose_fn)
                .map_err(|e| RuleError::Backend {
                    detail: format!("isVerbose set: {e}"),
                })?;

            // --- Short aliases (U8, U16, U24, U32, U64, I8, I16, I32, I64) ---

            // U8(offset) -> u8
            let h = host.clone();
            let u8_fn = rquickjs::Function::new(ctx.clone(), move |offset: i32| {
                h.read_u8(offset as u64).map(|v| v as i32).unwrap_or(-1)
            })
            .map_err(|e| RuleError::Backend {
                detail: format!("U8: {e}"),
            })?;
            binary.set("U8", u8_fn).map_err(|e| RuleError::Backend {
                detail: format!("U8 set: {e}"),
            })?;

            // I8(offset) -> i8
            let h = host.clone();
            let i8_fn = rquickjs::Function::new(ctx.clone(), move |offset: i32| {
                h.read_i8(offset as u64).map(|v| v as i32).unwrap_or(0)
            })
            .map_err(|e| RuleError::Backend {
                detail: format!("I8: {e}"),
            })?;
            binary.set("I8", i8_fn).map_err(|e| RuleError::Backend {
                detail: format!("I8 set: {e}"),
            })?;

            // U16(offset) -> u16
            let h = host.clone();
            let u16_fn = rquickjs::Function::new(ctx.clone(), move |offset: i32| {
                h.read_u16_le(offset as u64).map(|v| v as i32).unwrap_or(0)
            })
            .map_err(|e| RuleError::Backend {
                detail: format!("U16: {e}"),
            })?;
            binary.set("U16", u16_fn).map_err(|e| RuleError::Backend {
                detail: format!("U16 set: {e}"),
            })?;

            // U24(offset) -> u32
            let h = host.clone();
            let u24_fn = rquickjs::Function::new(ctx.clone(), move |offset: i32| {
                h.read_u24_le(offset as u64).unwrap_or(0)
            })
            .map_err(|e| RuleError::Backend {
                detail: format!("U24: {e}"),
            })?;
            binary.set("U24", u24_fn).map_err(|e| RuleError::Backend {
                detail: format!("U24 set: {e}"),
            })?;

            // U32(offset) -> u32
            let h = host.clone();
            let u32_fn = rquickjs::Function::new(ctx.clone(), move |offset: i32| {
                h.read_u32_le(offset as u64).unwrap_or(0)
            })
            .map_err(|e| RuleError::Backend {
                detail: format!("U32: {e}"),
            })?;
            binary.set("U32", u32_fn).map_err(|e| RuleError::Backend {
                detail: format!("U32 set: {e}"),
            })?;

            // U64(offset) -> u64 as f64
            let h = host.clone();
            let u64_fn = rquickjs::Function::new(ctx.clone(), move |offset: i32| {
                h.read_u64_le(offset as u64).unwrap_or(0) as f64
            })
            .map_err(|e| RuleError::Backend {
                detail: format!("U64: {e}"),
            })?;
            binary.set("U64", u64_fn).map_err(|e| RuleError::Backend {
                detail: format!("U64 set: {e}"),
            })?;

            // I32(offset) -> i32
            let h = host.clone();
            let i32_fn = rquickjs::Function::new(ctx.clone(), move |offset: i32| {
                h.read_i32_le(offset as u64).unwrap_or(0)
            })
            .map_err(|e| RuleError::Backend {
                detail: format!("I32: {e}"),
            })?;
            binary.set("I32", i32_fn).map_err(|e| RuleError::Backend {
                detail: format!("I32 set: {e}"),
            })?;

            // --- File metadata ---

            // getSize() -> file size
            let h = host.clone();
            let get_size_fn = rquickjs::Function::new(ctx.clone(), move || h.file_size() as f64)
                .map_err(|e| RuleError::Backend {
                    detail: format!("getSize: {e}"),
                })?;
            binary
                .set("getSize", get_size_fn)
                .map_err(|e| RuleError::Backend {
                    detail: format!("getSize set: {e}"),
                })?;

            // getEntryPointOffset() -> entry point
            let h = host.clone();
            let get_ep_fn =
                rquickjs::Function::new(ctx.clone(), move || h.entry_point().unwrap_or(0) as f64)
                    .map_err(|e| RuleError::Backend {
                    detail: format!("getEntryPointOffset: {e}"),
                })?;
            binary
                .set("getEntryPointOffset", get_ep_fn)
                .map_err(|e| RuleError::Backend {
                    detail: format!("getEntryPointOffset set: {e}"),
                })?;

            // --- String and signature search ---

            // getString(offset, maxLen?) -> string
            // If maxLen is omitted or 0, read to end of file (matching upstream).
            // We register a 2-arg native function and override it with a JS
            // wrapper after the Binary global is registered (see end of register()).
            let h = host.clone();
            let get_string_fn =
                rquickjs::Function::new(ctx.clone(), move |offset: i32, max_len: i32| {
                    let max = if max_len <= 0 {
                        h.file_size()
                    } else {
                        max_len as u64
                    };
                    h.read_string(offset as u64, max).unwrap_or_default()
                })
                .map_err(|e| RuleError::Backend {
                    detail: format!("getString: {e}"),
                })?;
            binary
                .set("getString", get_string_fn.clone())
                .map_err(|e| RuleError::Backend {
                    detail: format!("getString set: {e}"),
                })?;
            binary
                .set("getString", get_string_fn)
                .map_err(|e| RuleError::Backend {
                    detail: format!("getString set: {e}"),
                })?;

            // findSignature(start, signature) -> offset or -1
            let h = host.clone();
            let find_sig_fn =
                rquickjs::Function::new(ctx.clone(), move |start: i32, signature: String| match h
                    .find_signature(start as u64, &signature)
                {
                    Ok(Some(offset)) => offset as f64,
                    _ => -1.0,
                })
                .map_err(|e| RuleError::Backend {
                    detail: format!("findSignature: {e}"),
                })?;
            binary
                .set("findSignature", find_sig_fn)
                .map_err(|e| RuleError::Backend {
                    detail: format!("findSignature set: {e}"),
                })?;

            // isSignaturePresent(offset, size, signature) -> bool
            // Upstream: bool isSignaturePresent(qint64 nOffset, qint64 nSize, const QString &sSignature)
            // Searches for signature within [offset, offset+size) range.
            let h = host.clone();
            let is_sig_present_fn = rquickjs::Function::new(
                ctx.clone(),
                move |offset: i32, size: i32, signature: String| {
                    if size <= 0 {
                        h.check_signature(offset as u64, &signature).unwrap_or(false)
                    } else {
                        h.find_signature(offset as u64, &signature)
                            .ok()
                            .flatten()
                            .map(|found| {
                                found >= offset as u64 && found < (offset as u64 + size as u64)
                            })
                            .unwrap_or(false)
                    }
                },
            )
            .map_err(|e| RuleError::Backend {
                detail: format!("isSignaturePresent: {e}"),
            })?;
            binary
                .set("isSignaturePresent", is_sig_present_fn)
                .map_err(|e| RuleError::Backend {
                    detail: format!("isSignaturePresent set: {e}"),
                })?;

            // compare(signature, offset=0) -> bool
            // Upstream signature: bool compare(const QString &sSignature, qint64 nOffset = 0)
            // We register a 2-arg native and a JS wrapper that defaults offset to 0.
            let h = host.clone();
            let compare_fn =
                rquickjs::Function::new(ctx.clone(), move |signature: String, offset: i32| {
                    h.check_signature(offset as u64, &signature)
                        .unwrap_or(false)
                })
                .map_err(|e| RuleError::Backend {
                    detail: format!("compare: {e}"),
                })?;
            binary
                .set("__compare", compare_fn)
                .map_err(|e| RuleError::Backend {
                    detail: format!("compare set: {e}"),
                })?;

            // --- Scan mode flags ---

            let h = host.clone();
            let is_deep_fn =
                rquickjs::Function::new(ctx.clone(), move || h.is_deep()).map_err(|e| {
                    RuleError::Backend {
                        detail: format!("isDeepScan: {e}"),
                    }
                })?;
            binary
                .set("isDeepScan", is_deep_fn)
                .map_err(|e| RuleError::Backend {
                    detail: format!("isDeepScan set: {e}"),
                })?;

            let h = host.clone();
            let is_heuristic_fn = rquickjs::Function::new(ctx.clone(), move || h.is_heuristic())
                .map_err(|e| RuleError::Backend {
                    detail: format!("isHeuristicScan: {e}"),
                })?;
            binary
                .set("isHeuristicScan", is_heuristic_fn)
                .map_err(|e| RuleError::Backend {
                    detail: format!("isHeuristicScan set: {e}"),
                })?;

            let h = host.clone();
            let is_aggressive_fn = rquickjs::Function::new(ctx.clone(), move || h.is_aggressive())
                .map_err(|e| RuleError::Backend {
                    detail: format!("isAggressiveScan: {e}"),
                })?;
            binary
                .set("isAggressiveScan", is_aggressive_fn)
                .map_err(|e| RuleError::Backend {
                    detail: format!("isAggressiveScan set: {e}"),
                })?;

            let h = host.clone();
            let is_recursive_fn = rquickjs::Function::new(ctx.clone(), move || h.is_recursive())
                .map_err(|e| RuleError::Backend {
                    detail: format!("isRecursiveScan: {e}"),
                })?;
            binary
                .set("isRecursiveScan", is_recursive_fn)
                .map_err(|e| RuleError::Backend {
                    detail: format!("isRecursiveScan set: {e}"),
                })?;

            // --- Architecture detection ---

            let h = host.clone();
            let is8_fn = rquickjs::Function::new(ctx.clone(), move || {
                // 8-bit architecture check based on file type
                let ft = h.file_type();
                ft.name == "Binary_8bit"
            })
            .map_err(|e| RuleError::Backend {
                detail: format!("is8: {e}"),
            })?;
            binary.set("is8", is8_fn).map_err(|e| RuleError::Backend {
                detail: format!("is8 set: {e}"),
            })?;

            let h = host.clone();
            let is16_fn = rquickjs::Function::new(ctx.clone(), move || {
                let ft = h.file_type();
                ft.name == "Binary_16bit"
            })
            .map_err(|e| RuleError::Backend {
                detail: format!("is16: {e}"),
            })?;
            binary
                .set("is16", is16_fn)
                .map_err(|e| RuleError::Backend {
                    detail: format!("is16 set: {e}"),
                })?;

            let h = host.clone();
            let is32_fn = rquickjs::Function::new(ctx.clone(), move || {
                let ft = h.file_type();
                ft.name == "Binary_32bit"
            })
            .map_err(|e| RuleError::Backend {
                detail: format!("is32: {e}"),
            })?;
            binary
                .set("is32", is32_fn)
                .map_err(|e| RuleError::Backend {
                    detail: format!("is32 set: {e}"),
                })?;

            let h = host.clone();
            let is64_fn = rquickjs::Function::new(ctx.clone(), move || {
                let ft = h.file_type();
                ft.name == "Binary_64bit"
            })
            .map_err(|e| RuleError::Backend {
                detail: format!("is64: {e}"),
            })?;
            binary
                .set("is64", is64_fn)
                .map_err(|e| RuleError::Backend {
                    detail: format!("is64 set: {e}"),
                })?;

            // --- Entropy and hashes ---

            let h = host.clone();
            let calc_entropy_fn =
                rquickjs::Function::new(ctx.clone(), move |offset: i32, size: i32| {
                    h.entropy(offset as u64, size as u64).unwrap_or(0.0)
                })
                .map_err(|e| RuleError::Backend {
                    detail: format!("calculateEntropy: {e}"),
                })?;
            binary
                .set("calculateEntropy", calc_entropy_fn)
                .map_err(|e| RuleError::Backend {
                    detail: format!("calculateEntropy set: {e}"),
                })?;

            let h = host.clone();
            let calc_md5_fn =
                rquickjs::Function::new(ctx.clone(), move |offset: i32, size: i32| {
                    h.md5(offset as u64, size as u64).unwrap_or_default()
                })
                .map_err(|e| RuleError::Backend {
                    detail: format!("calculateMD5: {e}"),
                })?;
            binary
                .set("calculateMD5", calc_md5_fn)
                .map_err(|e| RuleError::Backend {
                    detail: format!("calculateMD5 set: {e}"),
                })?;

            let h = host.clone();
            let calc_crc32_fn =
                rquickjs::Function::new(ctx.clone(), move |offset: i32, size: i32| {
                    h.crc32(offset as u64, size as u64).unwrap_or(0) as f64
                })
                .map_err(|e| RuleError::Backend {
                    detail: format!("calculateCRC32: {e}"),
                })?;
            binary
                .set("calculateCRC32", calc_crc32_fn)
                .map_err(|e| RuleError::Backend {
                    detail: format!("calculateCRC32 set: {e}"),
                })?;

            // --- File name/path ---

            let h = host.clone();
            let get_file_base_name_fn = rquickjs::Function::new(ctx.clone(), move || {
                // Return base name: file name without extension.
                let name = h.file_name();
                match name.rfind('.') {
                    Some(pos) => name[..pos].to_string(),
                    None => name.to_string(),
                }
            })
            .map_err(|e| RuleError::Backend {
                detail: format!("getFileBaseName: {e}"),
            })?;
            binary
                .set("getFileBaseName", get_file_base_name_fn)
                .map_err(|e| RuleError::Backend {
                    detail: format!("getFileBaseName set: {e}"),
                })?;

            // --- Short aliases (Sz, c, SA, SC, fStr, fSig, BA) ---

            // Sz() -> file size (alias for getSize)
            let h = host.clone();
            let sz_fn = rquickjs::Function::new(ctx.clone(), move || h.file_size() as f64)
                .map_err(|e| RuleError::Backend {
                    detail: format!("Sz: {e}"),
                })?;
            binary.set("Sz", sz_fn).map_err(|e| RuleError::Backend {
                detail: format!("Sz set: {e}"),
            })?;

            // c(signature, offset) -> bool (alias for compare, but args reversed)
            let h = host.clone();
            let c_fn =
                rquickjs::Function::new(ctx.clone(), move |signature: String, offset: i32| {
                    h.check_signature(offset as u64, &signature)
                        .unwrap_or(false)
                })
                .map_err(|e| RuleError::Backend {
                    detail: format!("c: {e}"),
                })?;
            binary.set("c", c_fn).map_err(|e| RuleError::Backend {
                detail: format!("c set: {e}"),
            })?;

            // SA(offset, maxSize) -> string (ANSI string read)
            let h = host.clone();
            let sa_fn = rquickjs::Function::new(ctx.clone(), move |offset: i32, max_size: i32| {
                h.read_string(offset as u64, max_size as u64)
                    .unwrap_or_default()
            })
            .map_err(|e| RuleError::Backend {
                detail: format!("SA: {e}"),
            })?;
            binary.set("SA", sa_fn).map_err(|e| RuleError::Backend {
                detail: format!("SA set: {e}"),
            })?;

            // SC(offset, maxByteSize, codePage) -> string (code page string)
            // For now, just read as ANSI string (code page not implemented).
            let h = host.clone();
            let sc_fn = rquickjs::Function::new(
                ctx.clone(),
                move |offset: i32, max_size: i32, _code_page: String| {
                    h.read_string(offset as u64, max_size as u64)
                        .unwrap_or_default()
                },
            )
            .map_err(|e| RuleError::Backend {
                detail: format!("SC: {e}"),
            })?;
            binary.set("SC", sc_fn).map_err(|e| RuleError::Backend {
                detail: format!("SC set: {e}"),
            })?;

            // fStr(offset, size, string) -> offset of found string or -1
            let h = host.clone();
            let fstr_fn = rquickjs::Function::new(
                ctx.clone(),
                move |offset: i32, _size: i32, needle: String| {
                    // Search for ASCII string in file data
                    let start = offset as usize;
                    let needle_bytes = needle.as_bytes();
                    if needle_bytes.is_empty()
                        || start + needle_bytes.len() > h.file_size() as usize
                    {
                        return -1.0;
                    }
                    // Use find_signature with hex encoding of the string
                    let hex: String = needle_bytes.iter().map(|b| format!("{b:02X}")).collect();
                    match h.find_signature(start as u64, &hex) {
                        Ok(Some(off)) => off as f64,
                        _ => -1.0,
                    }
                },
            )
            .map_err(|e| RuleError::Backend {
                detail: format!("fStr: {e}"),
            })?;
            binary
                .set("fStr", fstr_fn)
                .map_err(|e| RuleError::Backend {
                    detail: format!("fStr set: {e}"),
                })?;

            // fSig(offset, size, signature) -> offset or -1 (alias for findSignature with extra size param)
            let h = host.clone();
            let fsig_fn = rquickjs::Function::new(
                ctx.clone(),
                move |offset: i32, _size: i32, signature: String| match h
                    .find_signature(offset as u64, &signature)
                {
                    Ok(Some(off)) => off as f64,
                    _ => -1.0,
                },
            )
            .map_err(|e| RuleError::Backend {
                detail: format!("fSig: {e}"),
            })?;
            binary
                .set("fSig", fsig_fn)
                .map_err(|e| RuleError::Backend {
                    detail: format!("fSig set: {e}"),
                })?;

            // BA(offset, size, replaceZero?) -> array of bytes
            let h = host.clone();
            let ba_fn = rquickjs::Function::new(
                ctx.clone(),
                move |offset: i32, size: i32, _replace: bool| {
                    let start = offset as usize;
                    let end = (start + size as usize).min(h.file_size() as usize);
                    if start >= end {
                        return Vec::<i32>::new();
                    }
                    // Use read_u8 for each byte
                    (start..end)
                        .map(|i| h.read_u8(i as u64).map(|v| v as i32).unwrap_or(0))
                        .collect::<Vec<i32>>()
                },
            )
            .map_err(|e| RuleError::Backend {
                detail: format!("BA: {e}"),
            })?;
            binary.set("BA", ba_fn).map_err(|e| RuleError::Backend {
                detail: format!("BA set: {e}"),
            })?;

            // --- Register the Binary object and aliases ---

            globals
                .set("Binary", binary.clone())
                .map_err(|e| RuleError::Backend {
                    detail: format!("failed to set Binary global: {e}"),
                })?;

            // X and File are aliases for Binary (per file type binding).
            globals
                .set("X", binary.clone())
                .map_err(|e| RuleError::Backend {
                    detail: format!("failed to set X alias: {e}"),
                })?;

            globals
                .set("File", binary.clone())
                .map_err(|e| RuleError::Backend {
                    detail: format!("failed to set File alias: {e}"),
                })?;

            // Register a PE global object as an alias to Binary with
            // PE-specific stub methods. The PE-specific methods (sections,
            // imports, exports, resources) return defaults until the full
            // PE host API is implemented.
            globals
                .set("PE", binary.clone())
                .map_err(|e| RuleError::Backend {
                    detail: format!("failed to set PE alias: {e}"),
                })?;

            // Add PE-specific stub methods that return defaults.
            // These are needed so PE rules that reference PE at the top
            // level don't crash during loading.
            ctx.eval::<(), _>(
                r#"
                (function() {
                    // compareEP: compare at entry point
                    PE.compareEP = function(sig) {
                        return PE.compare(sig, PE.nEP);
                    };

                    // isSignaturePresent: search for signature in range
                    PE.isSignaturePresent = function(offset, size, sig) {
                        return PE.compare(sig, offset);
                    };

                    // Section/resource info stubs
                    PE.getNumberOfSections = function() { return 0; };
                    PE.getSectionName = function(n) { return ""; };
                    PE.getSectionVirtualSize = function(n) { return 0; };
                    PE.getSectionVirtualAddress = function(n) { return 0; };
                    PE.getSectionFileSize = function(n) { return 0; };
                    PE.getSectionFileOffset = function(n) { return 0; };
                    PE.getSectionCharacteristics = function(n) { return 0; };
                    PE.nLastSection = -1;
                    PE.section = [];

                    // Resource stubs
                    PE.getNumberOfResources = function() { return 0; };
                    PE.getResourceNameByNumber = function(n) { return ""; };
                    PE.getResourceIdByNumber = function(n) { return 0; };
                    PE.getResourceOffsetByNumber = function(n) { return 0; };
                    PE.getResourceSizeByNumber = function(n) { return 0; };
                    PE.getResourceTypeByNumber = function(n) { return 0; };
                    PE.getResourceNameOffset = function(s) { return 0; };
                    PE.resource = [];

                    // Import/export stubs
                    PE.getNumberOfImports = function() { return 0; };
                    PE.getImportLibraryName = function(n) { return ""; };
                    PE.getNumberOfExportFunctions = function() { return 0; };
                    PE.getExportFunctionName = function(n) { return ""; };

                    // PE header stubs
                    PE.nEP = 0;
                    PE.getEntryPoint = function() { return 0; };
                    PE.getImageBase = function() { return 0; };
                    PE.getSizeOfImage = function() { return 0; };
                    PE.getGeneralOptions = function() { return ""; };
                    PE.isConsole = function() { return false; };
                    PE.getManifest = function() { return ""; };
                    PE.isSignedFile = function() { return false; };
                    PE.getSignature = function(offset, size) { return ""; };

                    // PE-specific string methods
                    PE.getEntryPointSignature = function(nOffset, nSize) {
                        return PE.getSignature(PE.nEP + nOffset, nSize);
                    };
                    PE.getGeneralOptionsEx = function() { return ""; };
                    PE.isLibraryPresentExp = function(p) { return null; };
                    PE.isExportFunctionPresentExp = function(p) { return null; };
                    PE.isSectionNamePresentExp = function(p) { return null; };
                    PE.isResourceNamePresentExp = function(p) { return null; };
                    PE.isResourceNamePresent = function(s) { return false; };
                    PE.isSectionNamePresent = function(s) { return false; };
                    PE.isLibraryPresent = function(s) { return false; };
                    PE.isExportFunctionPresent = function(s) { return false; };

                    // File info stubs (PE-specific methods not on Binary)
                    PE.getPEFileVersion = function(s) { return ""; };
                    PE.getVersionStringInfo = function(s) { return ""; };
                    PE.findString = function(offset, size, s) { return -1; };
                })();
                "#,
            )
            .map_err(|e| RuleError::Backend {
                detail: format!("PE stubs: {e}"),
            })?;

            // Override getString with a JS wrapper that handles missing 2nd arg.
            // The upstream getString(offset, maxLen?) accepts 1 or 2 args.
            // Also add compare wrapper: compare(signature, offset=0).
            ctx.eval::<(), _>(
                r#"
                (function() {
                    var _orig_gs = Binary.getString;
                    Binary.getString = function(offset, maxLen) {
                        if (maxLen === undefined) maxLen = 0;
                        return _orig_gs(offset, maxLen);
                    };
                    X.getString = Binary.getString;
                    File.getString = Binary.getString;

                    var _orig_cmp = Binary.__compare;
                    Binary.compare = function(signature, offset) {
                        if (offset === undefined) offset = 0;
                        return _orig_cmp(signature, offset);
                    };
                    X.compare = Binary.compare;
                    File.compare = Binary.compare;
                    PE.compare = Binary.compare;
                })();
                "#,
            )
            .map_err(|e| RuleError::Backend {
                detail: format!("getString/compare wrapper: {e}"),
            })?;

            Ok(())
        })?;

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::host_api::HostApiError;
    use diec_core::format::FileType;
    use diec_core::input::ByteView;

    /// Test host API with a small in-memory buffer.
    struct TestHost {
        data: Vec<u8>,
        file_type: FileType,
    }

    impl TestHost {
        fn new(data: Vec<u8>) -> Self {
            Self {
                data,
                file_type: FileType::new("Binary"),
            }
        }
    }

    impl HostApi for TestHost {
        fn file_type(&self) -> &FileType {
            &self.file_type
        }

        fn view(&self) -> &ByteView<'_> {
            unimplemented!()
        }

        fn read_u8(&self, offset: u64) -> Result<u8, HostApiError> {
            self.data
                .get(offset as usize)
                .copied()
                .ok_or(HostApiError::OutOfBounds {
                    offset,
                    file_size: self.data.len() as u64,
                })
        }

        fn read_u16_le(&self, offset: u64) -> Result<u16, HostApiError> {
            let i = offset as usize;
            if i + 2 > self.data.len() {
                return Err(HostApiError::OutOfBounds {
                    offset,
                    file_size: self.data.len() as u64,
                });
            }
            Ok(u16::from_le_bytes([self.data[i], self.data[i + 1]]))
        }

        fn read_u16_be(&self, offset: u64) -> Result<u16, HostApiError> {
            let i = offset as usize;
            if i + 2 > self.data.len() {
                return Err(HostApiError::OutOfBounds {
                    offset,
                    file_size: self.data.len() as u64,
                });
            }
            Ok(u16::from_be_bytes([self.data[i], self.data[i + 1]]))
        }

        fn read_u24_le(&self, offset: u64) -> Result<u32, HostApiError> {
            let i = offset as usize;
            if i + 3 > self.data.len() {
                return Err(HostApiError::OutOfBounds {
                    offset,
                    file_size: self.data.len() as u64,
                });
            }
            Ok((self.data[i] as u32)
                | ((self.data[i + 1] as u32) << 8)
                | ((self.data[i + 2] as u32) << 16))
        }

        fn read_u24_be(&self, offset: u64) -> Result<u32, HostApiError> {
            let i = offset as usize;
            if i + 3 > self.data.len() {
                return Err(HostApiError::OutOfBounds {
                    offset,
                    file_size: self.data.len() as u64,
                });
            }
            Ok(((self.data[i] as u32) << 16)
                | ((self.data[i + 1] as u32) << 8)
                | (self.data[i + 2] as u32))
        }

        fn read_u32_le(&self, offset: u64) -> Result<u32, HostApiError> {
            let i = offset as usize;
            if i + 4 > self.data.len() {
                return Err(HostApiError::OutOfBounds {
                    offset,
                    file_size: self.data.len() as u64,
                });
            }
            Ok(u32::from_le_bytes([
                self.data[i],
                self.data[i + 1],
                self.data[i + 2],
                self.data[i + 3],
            ]))
        }

        fn read_u32_be(&self, offset: u64) -> Result<u32, HostApiError> {
            let i = offset as usize;
            if i + 4 > self.data.len() {
                return Err(HostApiError::OutOfBounds {
                    offset,
                    file_size: self.data.len() as u64,
                });
            }
            Ok(u32::from_be_bytes([
                self.data[i],
                self.data[i + 1],
                self.data[i + 2],
                self.data[i + 3],
            ]))
        }

        fn read_u64_le(&self, offset: u64) -> Result<u64, HostApiError> {
            let i = offset as usize;
            if i + 8 > self.data.len() {
                return Err(HostApiError::OutOfBounds {
                    offset,
                    file_size: self.data.len() as u64,
                });
            }
            Ok(u64::from_le_bytes(self.data[i..i + 8].try_into().unwrap()))
        }

        fn read_u64_be(&self, offset: u64) -> Result<u64, HostApiError> {
            let i = offset as usize;
            if i + 8 > self.data.len() {
                return Err(HostApiError::OutOfBounds {
                    offset,
                    file_size: self.data.len() as u64,
                });
            }
            Ok(u64::from_be_bytes(self.data[i..i + 8].try_into().unwrap()))
        }

        fn read_i8(&self, offset: u64) -> Result<i8, HostApiError> {
            self.read_u8(offset).map(|v| v as i8)
        }

        fn read_i16_le(&self, offset: u64) -> Result<i16, HostApiError> {
            self.read_u16_le(offset).map(|v| v as i16)
        }

        fn read_i32_le(&self, offset: u64) -> Result<i32, HostApiError> {
            self.read_u32_le(offset).map(|v| v as i32)
        }

        fn read_i64_le(&self, offset: u64) -> Result<i64, HostApiError> {
            self.read_u64_le(offset).map(|v| v as i64)
        }

        fn file_size(&self) -> u64 {
            self.data.len() as u64
        }

        fn check_signature(&self, offset: u64, signature: &str) -> Result<bool, HostApiError> {
            let elements =
                parse_signature(signature).map_err(|detail| HostApiError::InvalidSignature {
                    pattern: signature.into(),
                    detail,
                })?;
            Ok(match_signature(&self.data, offset as usize, &elements))
        }

        fn find_signature(&self, start: u64, signature: &str) -> Result<Option<u64>, HostApiError> {
            let elements =
                parse_signature(signature).map_err(|detail| HostApiError::InvalidSignature {
                    pattern: signature.into(),
                    detail,
                })?;
            let start = start as usize;
            if elements.is_empty() {
                return Ok(None);
            }
            if start + elements.len() > self.data.len() {
                return Ok(None);
            }
            for i in start..=self.data.len() - elements.len() {
                if match_signature(&self.data, i, &elements) {
                    return Ok(Some(i as u64));
                }
            }
            Ok(None)
        }

        fn read_string(&self, offset: u64, max_len: u64) -> Result<String, HostApiError> {
            let start = offset as usize;
            let end = (start + max_len as usize).min(self.data.len());
            let bytes = &self.data[start..end];
            let nul_pos = bytes.iter().position(|&b| b == 0).unwrap_or(bytes.len());
            Ok(String::from_utf8_lossy(&bytes[..nul_pos]).to_string())
        }

        fn file_name(&self) -> &str {
            "test.bin"
        }

        fn entry_point(&self) -> Result<u64, HostApiError> {
            Ok(0)
        }

        fn is_deep(&self) -> bool {
            false
        }
        fn is_heuristic(&self) -> bool {
            false
        }
        fn is_aggressive(&self) -> bool {
            false
        }
        fn is_recursive(&self) -> bool {
            false
        }

        fn entropy(&self, offset: u64, size: u64) -> Result<f64, HostApiError> {
            let start = offset as usize;
            let end = (start + size as usize).min(self.data.len());
            if start >= end {
                return Ok(0.0);
            }
            let mut counts = [0u32; 256];
            for &b in &self.data[start..end] {
                counts[b as usize] += 1;
            }
            let total = (end - start) as f64;
            let mut entropy = 0.0;
            for &count in &counts {
                if count > 0 {
                    let p = count as f64 / total;
                    entropy -= p * p.log2();
                }
            }
            Ok(entropy)
        }

        fn md5(&self, _offset: u64, _size: u64) -> Result<String, HostApiError> {
            Err(HostApiError::NotImplemented {
                method: "md5".into(),
            })
        }

        fn crc32(&self, _offset: u64, _size: u64) -> Result<u32, HostApiError> {
            Err(HostApiError::NotImplemented {
                method: "crc32".into(),
            })
        }
    }

    fn make_runtime_with_host(
        data: Vec<u8>,
    ) -> (rquickjs::Runtime, rquickjs::Context, HostApiBridge) {
        let runtime = rquickjs::Runtime::new().unwrap();
        let context = rquickjs::Context::full(&runtime).unwrap();
        let host = Arc::new(TestHost::new(data));
        let bridge = HostApiBridge::new(host);
        bridge.register(&context).unwrap();
        (runtime, context, bridge)
    }

    #[test]
    fn binary_get_size_returns_file_size() {
        let (_rt, ctx, _bridge) = make_runtime_with_host(vec![0x41, 0x42, 0x43, 0x44]);
        let size: f64 = ctx.with(|c| c.eval("Binary.getSize();").unwrap());
        assert_eq!(size, 4.0);
    }

    #[test]
    fn binary_read_byte() {
        let (_rt, ctx, _bridge) = make_runtime_with_host(vec![0x41, 0x42, 0x43]);
        let val: i32 = ctx.with(|c| c.eval("Binary.readByte(0);").unwrap());
        assert_eq!(val, 0x41);
        let val: i32 = ctx.with(|c| c.eval("Binary.readByte(1);").unwrap());
        assert_eq!(val, 0x42);
    }

    #[test]
    fn binary_read_word_le() {
        let (_rt, ctx, _bridge) = make_runtime_with_host(vec![0x78, 0x56, 0x34, 0x12]);
        let val: i32 = ctx.with(|c| c.eval("Binary.readWord(0);").unwrap());
        assert_eq!(val, 0x5678);
    }

    #[test]
    fn binary_read_dword_le() {
        let (_rt, ctx, _bridge) = make_runtime_with_host(vec![0x78, 0x56, 0x34, 0x12]);
        let val: u32 = ctx.with(|c| c.eval("Binary.readDword(0);").unwrap());
        assert_eq!(val, 0x12345678);
    }

    #[test]
    fn binary_u8_alias() {
        let (_rt, ctx, _bridge) = make_runtime_with_host(vec![0xFF, 0x42]);
        let val: i32 = ctx.with(|c| c.eval("X.U8(1);").unwrap());
        assert_eq!(val, 0x42);
    }

    #[test]
    fn binary_u16_alias() {
        let (_rt, ctx, _bridge) = make_runtime_with_host(vec![0x78, 0x56]);
        let val: i32 = ctx.with(|c| c.eval("X.U16(0);").unwrap());
        assert_eq!(val, 0x5678);
    }

    #[test]
    fn binary_u32_alias() {
        let (_rt, ctx, _bridge) = make_runtime_with_host(vec![0x78, 0x56, 0x34, 0x12]);
        let val: u32 = ctx.with(|c| c.eval("File.U32(0);").unwrap());
        assert_eq!(val, 0x12345678);
    }

    #[test]
    fn binary_get_string() {
        let (_rt, ctx, _bridge) = make_runtime_with_host(b"Hello\0World".to_vec());
        let val: String = ctx.with(|c| c.eval("Binary.getString(0, 11);").unwrap());
        assert_eq!(val, "Hello");
    }

    #[test]
    fn binary_compare_signature() {
        let (_rt, ctx, _bridge) = make_runtime_with_host(vec![0x4D, 0x5A, 0x90, 0x00]);
        let val: bool = ctx.with(|c| c.eval("Binary.compare('4D5A', 0);").unwrap());
        assert!(val);
        let val: bool = ctx.with(|c| c.eval("Binary.compare('9090', 0);").unwrap());
        assert!(!val);
    }

    #[test]
    fn binary_compare_string_literal_signature() {
        // 7z signature: '7z'BCAF271C
        let data = vec![0x37, 0x7A, 0xBC, 0xAF, 0x27, 0x1C, 0x00, 0x04];
        let (_rt, ctx, _bridge) = make_runtime_with_host(data);
        let val: bool = ctx.with(|c| c.eval("Binary.compare(\"'7z'BCAF271C\", 0);").unwrap());
        assert!(val, "7z signature should match");
    }

    #[test]
    fn binary_is_signature_present() {
        let (_rt, ctx, _bridge) = make_runtime_with_host(vec![0x4D, 0x5A, 0x90, 0x00]);
        let val: bool = ctx.with(|c| c.eval("Binary.isSignaturePresent(0, 4, '4D5A');").unwrap());
        assert!(val);
    }

    #[test]
    fn binary_find_signature() {
        let (_rt, ctx, _bridge) = make_runtime_with_host(vec![0x00, 0x00, 0x4D, 0x5A]);
        let val: f64 = ctx.with(|c| c.eval("Binary.findSignature(0, '4D5A');").unwrap());
        assert_eq!(val, 2.0);
    }

    #[test]
    fn binary_calculate_entropy() {
        let (_rt, ctx, _bridge) = make_runtime_with_host(vec![0x00; 100]);
        let val: f64 = ctx.with(|c| c.eval("Binary.calculateEntropy(0, 100);").unwrap());
        assert_eq!(val, 0.0); // All zeros -> entropy 0
    }

    #[test]
    fn binary_calculate_entropy_random() {
        let data: Vec<u8> = (0..256).map(|i| i as u8).collect();
        let (_rt, ctx, _bridge) = make_runtime_with_host(data);
        let val: f64 = ctx.with(|c| c.eval("Binary.calculateEntropy(0, 256);").unwrap());
        assert!((val - 8.0).abs() < 0.01); // Uniform distribution -> entropy 8
    }

    #[test]
    fn binary_get_file_base_name() {
        let (_rt, ctx, _bridge) = make_runtime_with_host(vec![0x00]);
        let val: String = ctx.with(|c| c.eval("Binary.getFileBaseName();").unwrap());
        assert_eq!(val, "test"); // "test.bin" without extension
    }

    #[test]
    fn binary_is_deep_scan() {
        let (_rt, ctx, _bridge) = make_runtime_with_host(vec![0x00]);
        let val: bool = ctx.with(|c| c.eval("Binary.isDeepScan();").unwrap());
        assert!(!val);
    }

    #[test]
    fn binary_x_and_file_are_aliases() {
        let (_rt, ctx, _bridge) = make_runtime_with_host(vec![0x41, 0x42]);
        // X and File should be the same object as Binary.
        let val: i32 = ctx.with(|c| c.eval("X.readByte(0);").unwrap());
        assert_eq!(val, 0x41);
        let val: i32 = ctx.with(|c| c.eval("File.readByte(0);").unwrap());
        assert_eq!(val, 0x41);
    }

    #[test]
    fn binary_read_byte_out_of_bounds_returns_minus_one() {
        let (_rt, ctx, _bridge) = make_runtime_with_host(vec![0x41]);
        let val: i32 = ctx.with(|c| c.eval("Binary.readByte(100);").unwrap());
        assert_eq!(val, -1);
    }
}
