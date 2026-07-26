//! Phase 0 spike for the pinned XBinary signature language.

use std::fmt;

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum Operation {
    CompareBytes(Vec<u8>),
    Skip(usize),
    NotNull(usize),
    Ansi(usize),
    NotAnsi(usize),
    NotAnsiAndNotNull(usize),
    DecimalDigit(usize),
    FindBytes { window: usize, bytes: Vec<u8> },
    RelativeOffset { width: usize },
    AbsoluteAddress { width: usize, base: Option<u64> },
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Pattern {
    operations: Vec<Operation>,
}

impl Pattern {
    pub fn parse(source: &str) -> Result<Self, ParseError> {
        Self::parse_with_mode(source, false).map(|report| report.pattern)
    }

    pub fn parse_upstream_compatible(source: &str) -> Result<ParseReport, ParseError> {
        Self::parse_with_mode(source, true)
    }

    fn parse_with_mode(source: &str, upstream_compatible: bool) -> Result<ParseReport, ParseError> {
        let mut quirks = Vec::new();
        let normalized = normalize(source, upstream_compatible, &mut quirks)?;
        let mut operations = Vec::new();
        let mut index = 0;

        while index < normalized.len() {
            match normalized[index] {
                b'.' => {
                    let count = repeated(&normalized, index, b'.');
                    operations.push(Operation::Skip(pair_count(
                        count,
                        index,
                        "wildcard",
                        upstream_compatible,
                        &mut quirks,
                    )?));
                    index += count;
                }
                b'*' => {
                    let count = repeated(&normalized, index, b'*');
                    operations.push(Operation::NotNull(pair_count(
                        count,
                        index,
                        "not-null",
                        upstream_compatible,
                        &mut quirks,
                    )?));
                    index += count;
                }
                b'%' if normalized.get(index + 1) == Some(&b'%') => {
                    let count = repeated_pair(&normalized, index, b'%', b'%');
                    operations.push(Operation::Ansi(count));
                    index += count * 2;
                }
                b'%' if normalized.get(index + 1) == Some(&b'&') => {
                    let count = repeated_pair(&normalized, index, b'%', b'&');
                    operations.push(Operation::DecimalDigit(count));
                    index += count * 2;
                }
                b'!' if normalized.get(index + 1) == Some(&b'%') => {
                    let count = repeated_pair(&normalized, index, b'!', b'%');
                    operations.push(Operation::NotAnsi(count));
                    index += count * 2;
                }
                b'_' if normalized.get(index + 1) == Some(&b'%') => {
                    let count = repeated_pair(&normalized, index, b'_', b'%');
                    operations.push(Operation::NotAnsiAndNotNull(count));
                    index += count * 2;
                }
                b'+' => {
                    let count = repeated(&normalized, index, b'+');
                    let bytes_start = index + count;
                    let (bytes, consumed) =
                        parse_hex_run(&normalized, bytes_start, upstream_compatible, &mut quirks)?;
                    if bytes.is_empty() {
                        return Err(ParseError::new(
                            bytes_start,
                            ParseErrorKind::MissingFindNeedle,
                        ));
                    }
                    operations.push(Operation::FindBytes {
                        window: count.checked_mul(32).ok_or_else(|| {
                            ParseError::new(index, ParseErrorKind::LengthOverflow)
                        })?,
                        bytes,
                    });
                    index = bytes_start + consumed;
                }
                b'$' => {
                    let count = repeated(&normalized, index, b'$');
                    operations.push(Operation::RelativeOffset {
                        width: address_width(
                            count,
                            index,
                            "relative offset",
                            upstream_compatible,
                            &mut quirks,
                        )?,
                    });
                    index += count;
                }
                b'#' => {
                    let (operation, consumed) = parse_absolute_address(
                        &normalized,
                        index,
                        upstream_compatible,
                        &mut quirks,
                    )?;
                    operations.push(operation);
                    index += consumed;
                }
                byte if is_hex(byte) => {
                    let (bytes, consumed) =
                        parse_hex_run(&normalized, index, upstream_compatible, &mut quirks)?;
                    operations.push(Operation::CompareBytes(bytes));
                    index += consumed;
                }
                byte => {
                    return Err(ParseError::new(
                        index,
                        ParseErrorKind::UnexpectedCharacter(char::from(byte)),
                    ));
                }
            }
        }

        if operations.is_empty() {
            return Err(ParseError::new(0, ParseErrorKind::EmptyPattern));
        }
        Ok(ParseReport {
            pattern: Self { operations },
            quirks,
        })
    }

    pub fn operations(&self) -> &[Operation] {
        &self.operations
    }

    pub fn matches_raw(&self, data: &[u8], offset: usize) -> Result<bool, MatchError> {
        let mut cursor = offset;
        for operation in &self.operations {
            match operation {
                Operation::CompareBytes(expected) => {
                    let Some(actual) = bounded_slice(data, cursor, expected.len()) else {
                        return Ok(false);
                    };
                    if actual != expected {
                        return Ok(false);
                    }
                    cursor += expected.len();
                }
                Operation::Skip(size) => {
                    if bounded_slice(data, cursor, *size).is_none() {
                        return Ok(false);
                    }
                    cursor += size;
                }
                Operation::NotNull(size) => {
                    if !match_class(data, &mut cursor, *size, |byte| byte != 0) {
                        return Ok(false);
                    }
                }
                Operation::Ansi(size) => {
                    if !match_class(data, &mut cursor, *size, |byte| {
                        (0x20..0x80).contains(&byte)
                    }) {
                        return Ok(false);
                    }
                }
                Operation::NotAnsi(size) => {
                    if !match_class(data, &mut cursor, *size, |byte| {
                        !(0x20..0x80).contains(&byte)
                    }) {
                        return Ok(false);
                    }
                }
                Operation::NotAnsiAndNotNull(size) => {
                    if !match_class(data, &mut cursor, *size, |byte| {
                        byte != 0 && !(0x20..0x80).contains(&byte)
                    }) {
                        return Ok(false);
                    }
                }
                Operation::DecimalDigit(size) => {
                    if !match_class(data, &mut cursor, *size, |byte| byte.is_ascii_digit()) {
                        return Ok(false);
                    }
                }
                Operation::FindBytes { window, bytes } => {
                    let Some(search_size) = window.checked_add(bytes.len()) else {
                        return Ok(false);
                    };
                    let Some(haystack) = bounded_slice(data, cursor, search_size) else {
                        return Ok(false);
                    };
                    let Some(relative) = haystack
                        .windows(bytes.len())
                        .position(|candidate| candidate == bytes)
                    else {
                        return Ok(false);
                    };
                    cursor += relative + bytes.len();
                }
                Operation::RelativeOffset { .. } | Operation::AbsoluteAddress { .. } => {
                    return Err(MatchError::MemoryMapRequired);
                }
            }
        }
        Ok(true)
    }
}

fn normalize(
    source: &str,
    upstream_compatible: bool,
    quirks: &mut Vec<CompatibilityQuirk>,
) -> Result<Vec<u8>, ParseError> {
    let mut result = Vec::with_capacity(source.len());
    let mut quoted = false;
    for (position, character) in source.chars().enumerate() {
        if character == '\'' {
            quoted = !quoted;
        } else if quoted {
            for unit in character.encode_utf16(&mut [0; 2]) {
                let value = u8::try_from(*unit).unwrap_or(0);
                result.push(hex_digit(value >> 4));
                result.push(hex_digit(value & 0x0f));
            }
        } else if character == ' ' {
            continue;
        } else if character == '?' {
            result.push(b'.');
        } else if character.is_ascii() {
            result.push(character.to_ascii_lowercase() as u8);
        } else {
            return Err(ParseError::new(
                position,
                ParseErrorKind::NonAsciiSyntax(character),
            ));
        }
    }
    if quoted {
        let position = source.chars().count();
        if upstream_compatible {
            quirks.push(CompatibilityQuirk::UnterminatedQuotedString { position });
        } else {
            return Err(ParseError::new(
                position,
                ParseErrorKind::UnterminatedQuotedString,
            ));
        }
    }
    Ok(result)
}

fn parse_hex_run(
    input: &[u8],
    start: usize,
    upstream_compatible: bool,
    quirks: &mut Vec<CompatibilityQuirk>,
) -> Result<(Vec<u8>, usize), ParseError> {
    let count = input[start..]
        .iter()
        .take_while(|byte| is_hex(**byte))
        .count();
    if count == 0 {
        return Ok((Vec::new(), 0));
    }
    let odd = count % 2 != 0;
    if odd && !upstream_compatible {
        return Err(ParseError::new(
            start,
            ParseErrorKind::OddTokenLength {
                token: "hex bytes",
                length: count,
            },
        ));
    }
    let mut bytes = Vec::with_capacity(count.div_ceil(2));
    let pairs_start = if odd {
        quirks.push(CompatibilityQuirk::OddHexLength {
            position: start,
            length: count,
        });
        bytes.push(hex_value(input[start]));
        start + 1
    } else {
        start
    };
    for pair in input[pairs_start..start + count].chunks_exact(2) {
        bytes.push((hex_value(pair[0]) << 4) | hex_value(pair[1]));
    }
    Ok((bytes, count))
}

fn parse_absolute_address(
    input: &[u8],
    start: usize,
    upstream_compatible: bool,
    quirks: &mut Vec<CompatibilityQuirk>,
) -> Result<(Operation, usize), ParseError> {
    let mut index = start;
    let mut markers = 0;
    while input.get(index) == Some(&b'#') {
        markers += 1;
        index += 1;
    }
    let base = if input.get(index) == Some(&b'[') {
        let base_start = index + 1;
        let Some(relative_end) = input[base_start..].iter().position(|byte| *byte == b']') else {
            return Err(ParseError::new(
                index,
                ParseErrorKind::UnterminatedBaseAddress,
            ));
        };
        let base_end = base_start + relative_end;
        if base_end == base_start || !input[base_start..base_end].iter().all(|byte| is_hex(*byte)) {
            return Err(ParseError::new(
                base_start,
                ParseErrorKind::InvalidBaseAddress,
            ));
        }
        index = base_end + 1;
        let base_text = std::str::from_utf8(&input[base_start..base_end])
            .map_err(|_| ParseError::new(base_start, ParseErrorKind::InvalidBaseAddress))?;
        Some(
            u64::from_str_radix(base_text, 16)
                .map_err(|_| ParseError::new(base_start, ParseErrorKind::InvalidBaseAddress))?,
        )
    } else {
        None
    };
    while input.get(index) == Some(&b'#') {
        markers += 1;
        index += 1;
    }
    Ok((
        Operation::AbsoluteAddress {
            width: address_width(
                markers,
                start,
                "absolute address",
                upstream_compatible,
                quirks,
            )?,
            base,
        },
        index - start,
    ))
}

fn address_width(
    count: usize,
    position: usize,
    token: &'static str,
    upstream_compatible: bool,
    quirks: &mut Vec<CompatibilityQuirk>,
) -> Result<usize, ParseError> {
    let width = pair_count(count, position, token, upstream_compatible, quirks)?;
    if !matches!(width, 1 | 2 | 4 | 8) {
        return Err(ParseError::new(
            position,
            ParseErrorKind::UnsupportedAddressWidth { token, width },
        ));
    }
    Ok(width)
}

fn pair_count(
    count: usize,
    position: usize,
    token: &'static str,
    upstream_compatible: bool,
    quirks: &mut Vec<CompatibilityQuirk>,
) -> Result<usize, ParseError> {
    if count % 2 != 0 {
        if upstream_compatible {
            quirks.push(CompatibilityQuirk::OddRepeatedToken {
                position,
                token,
                length: count,
            });
        } else {
            return Err(ParseError::new(
                position,
                ParseErrorKind::OddTokenLength {
                    token,
                    length: count,
                },
            ));
        }
    }
    Ok(count / 2)
}

fn repeated(input: &[u8], start: usize, expected: u8) -> usize {
    input[start..]
        .iter()
        .take_while(|byte| **byte == expected)
        .count()
}

fn repeated_pair(input: &[u8], start: usize, first: u8, second: u8) -> usize {
    input[start..]
        .chunks_exact(2)
        .take_while(|pair| pair == &[first, second])
        .count()
}

fn is_hex(byte: u8) -> bool {
    byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte)
}

fn hex_value(byte: u8) -> u8 {
    if byte.is_ascii_digit() {
        byte - b'0'
    } else {
        byte - b'a' + 10
    }
}

fn hex_digit(value: u8) -> u8 {
    if value < 10 {
        b'0' + value
    } else {
        b'a' + value - 10
    }
}

fn bounded_slice(data: &[u8], offset: usize, size: usize) -> Option<&[u8]> {
    let end = offset.checked_add(size)?;
    data.get(offset..end)
}

fn match_class(
    data: &[u8],
    cursor: &mut usize,
    size: usize,
    predicate: impl Fn(u8) -> bool,
) -> bool {
    if size == 0 {
        return false;
    }
    let Some(bytes) = bounded_slice(data, *cursor, size) else {
        return false;
    };
    if !bytes.iter().copied().all(predicate) {
        return false;
    }
    *cursor += size;
    true
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ParseError {
    pub position: usize,
    pub kind: ParseErrorKind,
}

impl ParseError {
    fn new(position: usize, kind: ParseErrorKind) -> Self {
        Self { position, kind }
    }
}

impl fmt::Display for ParseError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            formatter,
            "invalid signature at character {}: {}",
            self.position, self.kind
        )
    }
}

impl std::error::Error for ParseError {}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ParseReport {
    pub pattern: Pattern,
    pub quirks: Vec<CompatibilityQuirk>,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum CompatibilityQuirk {
    UnterminatedQuotedString {
        position: usize,
    },
    OddHexLength {
        position: usize,
        length: usize,
    },
    OddRepeatedToken {
        position: usize,
        token: &'static str,
        length: usize,
    },
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum ParseErrorKind {
    EmptyPattern,
    UnexpectedCharacter(char),
    NonAsciiSyntax(char),
    UnterminatedQuotedString,
    OddTokenLength { token: &'static str, length: usize },
    MissingFindNeedle,
    UnterminatedBaseAddress,
    InvalidBaseAddress,
    UnsupportedAddressWidth { token: &'static str, width: usize },
    LengthOverflow,
}

impl fmt::Display for ParseErrorKind {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::EmptyPattern => formatter.write_str("pattern is empty"),
            Self::UnexpectedCharacter(character) => {
                write!(formatter, "unexpected character {character:?}")
            }
            Self::NonAsciiSyntax(character) => {
                write!(formatter, "non-ASCII syntax character {character:?}")
            }
            Self::UnterminatedQuotedString => formatter.write_str("unterminated quoted string"),
            Self::OddTokenLength { token, length } => {
                write!(formatter, "{token} token has odd length {length}")
            }
            Self::MissingFindNeedle => formatter.write_str("find token has no byte needle"),
            Self::UnterminatedBaseAddress => {
                formatter.write_str("unterminated absolute-address base")
            }
            Self::InvalidBaseAddress => formatter.write_str("invalid absolute-address base"),
            Self::UnsupportedAddressWidth { token, width } => {
                write!(formatter, "{token} width {width} is not 1, 2, 4, or 8")
            }
            Self::LengthOverflow => formatter.write_str("token length overflow"),
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum MatchError {
    MemoryMapRequired,
}

impl fmt::Display for MatchError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::MemoryMapRequired => {
                formatter.write_str("signature operation requires a format memory map")
            }
        }
    }
}

impl std::error::Error for MatchError {}

#[cfg(test)]
mod tests {
    use super::{CompatibilityQuirk, MatchError, Operation, ParseErrorKind, Pattern};
    use serde_json::Value;
    use std::collections::BTreeSet;

    fn decode_hex(source: &str) -> Vec<u8> {
        assert_eq!(source.len() % 2, 0);
        source
            .as_bytes()
            .chunks_exact(2)
            .map(|pair| (hex_test_value(pair[0]) << 4) | hex_test_value(pair[1]))
            .collect()
    }

    fn hex_test_value(byte: u8) -> u8 {
        match byte {
            b'0'..=b'9' => byte - b'0',
            b'a'..=b'f' => byte - b'a' + 10,
            _ => panic!("invalid fixture hex byte"),
        }
    }

    #[test]
    fn parses_normalization_literals_and_wildcards() {
        let pattern = Pattern::parse(" 7F 'ELF' ?? .. 01 ").expect("pattern should parse");
        assert_eq!(
            pattern.operations(),
            &[
                Operation::CompareBytes(b"\x7fELF".to_vec()),
                Operation::Skip(2),
                Operation::CompareBytes(vec![1]),
            ]
        );
        assert_eq!(pattern.matches_raw(b"\x7fELF\xaa\xbb\x01", 0), Ok(true));
    }

    #[test]
    fn parses_and_matches_all_byte_classes() {
        let pattern = Pattern::parse("**%%!%_%%&").expect("byte class pattern should parse");
        assert_eq!(pattern.matches_raw(&[1, b'A', 0, 0x80, b'7'], 0), Ok(true));
        assert_eq!(
            pattern.matches_raw(&[1, b'A', b'!', 0x80, b'7'], 0),
            Ok(false)
        );
        assert_eq!(
            pattern.matches_raw(&[1, b'A', 0, 0x80, b'A'], 0),
            Ok(false),
            "%& follows the pinned matcher and accepts decimal digits only"
        );
    }

    #[test]
    fn bounded_find_uses_32_bytes_per_plus() {
        let pattern = Pattern::parse("++'MZ'").expect("find pattern should parse");
        let mut data = vec![0; 66];
        data[64..].copy_from_slice(b"MZ");
        assert_eq!(pattern.matches_raw(&data, 0), Ok(true));
        let mut outside = vec![0; 67];
        outside[65..].copy_from_slice(b"MZ");
        assert_eq!(pattern.matches_raw(&outside, 0), Ok(false));
    }

    #[test]
    fn parses_context_dependent_offsets_but_refuses_raw_matching() {
        let relative = Pattern::parse("e9$$$$$$$$").expect("relative offset should parse");
        assert_eq!(
            relative.operations(),
            &[
                Operation::CompareBytes(vec![0xe9]),
                Operation::RelativeOffset { width: 4 },
            ]
        );
        assert_eq!(
            relative.matches_raw(&[0xe9, 0, 0, 0, 0], 0),
            Err(MatchError::MemoryMapRequired)
        );

        let absolute = Pattern::parse("68########[401000]").expect("absolute address should parse");
        assert_eq!(
            absolute.operations(),
            &[
                Operation::CompareBytes(vec![0x68]),
                Operation::AbsoluteAddress {
                    width: 4,
                    base: Some(0x401000),
                },
            ]
        );

        let markers_around_base = Pattern::parse("##[401000]##")
            .expect("address markers around a base should remain one record");
        assert_eq!(
            markers_around_base.operations(),
            &[Operation::AbsoluteAddress {
                width: 2,
                base: Some(0x401000),
            }]
        );
    }

    #[test]
    fn malformed_or_unknown_syntax_is_never_silent() {
        for source in ["", "a", ".", "+", "%%x", "'unterminated"] {
            assert!(
                Pattern::parse(source).is_err(),
                "{source:?} must be diagnosed"
            );
        }
        assert_eq!(
            Pattern::parse("$").expect_err("odd token should fail").kind,
            ParseErrorKind::OddTokenLength {
                token: "relative offset",
                length: 1,
            }
        );
    }

    #[test]
    fn compatible_mode_reports_pinned_qt_parser_quirks() {
        let unterminated = Pattern::parse_upstream_compatible("'AMX ")
            .expect("pinned parser accepts an unterminated quoted string");
        assert_eq!(
            unterminated.quirks,
            vec![CompatibilityQuirk::UnterminatedQuotedString { position: 5 }]
        );
        assert_eq!(
            unterminated.pattern.operations(),
            &[Operation::CompareBytes(b"AMX ".to_vec())]
        );

        let odd = Pattern::parse_upstream_compatible("abc")
            .expect("pinned QByteArray::fromHex accepts an odd nibble count");
        assert_eq!(
            odd.quirks,
            vec![CompatibilityQuirk::OddHexLength {
                position: 0,
                length: 3,
            }]
        );
        assert_eq!(
            odd.pattern.operations(),
            &[Operation::CompareBytes(vec![0x0a, 0xbc])]
        );

        let zero_width = Pattern::parse_upstream_compatible("*")
            .expect("pinned parser records a zero-width not-null token");
        assert_eq!(
            zero_width.pattern.matches_raw(b"", 0),
            Ok(false),
            "pinned matcher rejects zero-width character classes"
        );
    }

    #[test]
    fn parses_every_fixed_dynamic_inventory_pattern() {
        let inventory: Value = serde_json::from_str(include_str!(
            "../../../docs/research/data/signature-pattern-inventory.json"
        ))
        .expect("inventory should be valid JSON");
        let patterns = inventory["patterns"]
            .as_array()
            .expect("inventory patterns should be an array");
        assert_eq!(patterns.len(), 317);
        let mut strict_failures = Vec::new();
        let mut compatibility_quirks = Vec::new();
        for pattern in patterns {
            let source = pattern.as_str().expect("pattern should be a string");
            if let Err(error) = Pattern::parse(source) {
                strict_failures.push(format!("{source:?}: {error}"));
            }
            let report = Pattern::parse_upstream_compatible(source)
                .unwrap_or_else(|error| panic!("cannot parse {source:?}: {error}"));
            compatibility_quirks.extend(report.quirks);
        }
        assert_eq!(strict_failures.len(), 5, "{strict_failures:#?}");
        assert_eq!(
            compatibility_quirks
                .iter()
                .filter(|quirk| matches!(
                    quirk,
                    CompatibilityQuirk::UnterminatedQuotedString { .. }
                ))
                .count(),
            4
        );
        assert_eq!(
            compatibility_quirks
                .iter()
                .filter(|quirk| matches!(quirk, CompatibilityQuirk::OddHexLength { .. }))
                .count(),
            1
        );
        assert_eq!(
            compatibility_quirks
                .iter()
                .filter(|quirk| matches!(quirk, CompatibilityQuirk::OddRepeatedToken { .. }))
                .count(),
            1
        );
    }

    #[test]
    fn context_free_matches_agree_with_pinned_xbinary_oracle() {
        let selected = BTreeSet::from([
            "quoted_literal_and_wildcard_match",
            "literal_mismatch",
            "exact_match_at_eof",
            "truncated_literal",
            "all_byte_classes_match",
            "decimal_class_rejects_letter",
            "ansi_del_compare_find_divergence",
            "not_ansi_del_compare_find_divergence",
            "find_at_window_end",
            "find_outside_window",
            "odd_hex_qbytearray_behavior",
            "unterminated_quote_behavior",
            "odd_hex_and_zero_width_wildcard",
            "single_wildcard_is_zero_width",
            "single_not_null_is_zero_width_but_fails",
            "non_latin1_quote_becomes_zero",
        ]);
        let oracle: Value = serde_json::from_str(include_str!(
            "../../../docs/research/data/signature-oracle-qt5.json"
        ))
        .expect("oracle baseline should be valid JSON");
        let cases = oracle["cases"]
            .as_array()
            .expect("oracle cases should be an array");
        let mut compared = 0;
        for case in cases {
            let id = case["id"].as_str().expect("case id should be a string");
            if !selected.contains(id) {
                continue;
            }
            let source = case["pattern"]
                .as_str()
                .expect("pattern should be a string");
            let data = decode_hex(
                case["data_hex"]
                    .as_str()
                    .expect("data should be a hex string"),
            );
            let offset = case["offset"]
                .as_u64()
                .and_then(|value| usize::try_from(value).ok())
                .expect("offset should fit usize");
            let expected = case["compare"]
                .as_bool()
                .expect("compare result should be boolean");
            let report = Pattern::parse_upstream_compatible(source)
                .unwrap_or_else(|error| panic!("cannot parse {id}: {error}"));
            assert_eq!(
                report.pattern.matches_raw(&data, offset),
                Ok(expected),
                "differential mismatch for {id}"
            );
            compared += 1;
        }
        assert_eq!(compared, selected.len());
    }
}
