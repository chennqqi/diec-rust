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
    normalized_len: usize,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum FileType {
    Binary,
    Pe,
    Elf,
    MachO,
    Com,
    MsDos,
    AmigaHunk,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Endian {
    Little,
    Big,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct MemoryRecord {
    pub offset: u64,
    pub address: u64,
    pub size: u64,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct MemoryMap {
    pub file_type: FileType,
    pub endian: Endian,
    pub code_base: u64,
    pub start_load_offset: u64,
    pub records: Vec<MemoryRecord>,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct FindResult {
    pub offset: usize,
    pub size: usize,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct BinaryCompareReport {
    pub matched: bool,
    pub header_fast_path: bool,
    pub quirks: Vec<CompatibilityQuirk>,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct BinarySearchReport {
    pub found: Option<FindResult>,
    pub quirks: Vec<CompatibilityQuirk>,
}

impl MemoryMap {
    fn offset_to_address(&self, offset: u64) -> Option<u64> {
        self.records.iter().rev().find_map(|record| {
            let end = record.offset.checked_add(record.size)?;
            (record.offset <= offset && offset < end)
                .then(|| record.address.checked_add(offset - record.offset))
                .flatten()
        })
    }

    fn address_to_offset(&self, address: u64) -> Option<u64> {
        self.records.iter().rev().find_map(|record| {
            let end = record.address.checked_add(record.size)?;
            (record.address <= address && address < end)
                .then(|| record.offset.checked_add(address - record.address))
                .flatten()
        })
    }
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
                    if upstream_compatible && !operations.is_empty() {
                        quirks.push(CompatibilityQuirk::TrailingUnexpectedCharacter {
                            position: index,
                            character: char::from(byte),
                        });
                        break;
                    }
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
            pattern: Self {
                operations,
                normalized_len: normalized.len(),
            },
            quirks,
        })
    }

    pub fn operations(&self) -> &[Operation] {
        &self.operations
    }

    pub fn compare_binary_wrapper(
        source: &str,
        data: &[u8],
        offset: i64,
    ) -> Result<BinaryCompareReport, BinaryCompareError> {
        let mut normalization_quirks = Vec::new();
        let normalized = normalize(source, true, &mut normalization_quirks)?;
        let header_size = data.len().min(256);
        let header_fast_path = i128::try_from(normalized.len())
            .ok()
            .and_then(|length| length.checked_add(i128::from(offset)))
            .is_some_and(|end| end < header_size as i128)
            && !normalized
                .iter()
                .any(|byte| matches!(byte, b'$' | b'#' | b'+' | b'%' | b'*'));
        if header_fast_path {
            return Ok(BinaryCompareReport {
                matched: compare_header_nibbles(
                    &normalized,
                    data,
                    usize::try_from(offset).unwrap_or(0),
                ),
                header_fast_path: true,
                quirks: normalization_quirks,
            });
        }

        let parsed = Self::parse_upstream_compatible(source)?;
        if offset < 0 {
            return Ok(BinaryCompareReport {
                matched: false,
                header_fast_path: false,
                quirks: parsed.quirks,
            });
        }
        let Ok(offset) = usize::try_from(offset) else {
            return Ok(BinaryCompareReport {
                matched: false,
                header_fast_path: false,
                quirks: parsed.quirks,
            });
        };
        let memory_map = MemoryMap {
            file_type: FileType::Binary,
            endian: Endian::Little,
            code_base: 0,
            start_load_offset: 0,
            records: vec![MemoryRecord {
                offset: 0,
                address: 0,
                size: data.len() as u64,
            }],
        };
        let matched = parsed
            .pattern
            .matches_with_memory_map(data, offset, &memory_map)?;
        Ok(BinaryCompareReport {
            matched,
            header_fast_path: false,
            quirks: parsed.quirks,
        })
    }

    pub fn compare_entry_point_wrapper(
        source: &str,
        data: &[u8],
        entry_point_offset: Option<usize>,
        offset: i64,
        memory_map: &MemoryMap,
    ) -> Result<BinaryCompareReport, BinaryCompareError> {
        let mut normalization_quirks = Vec::new();
        let normalized = normalize(source, true, &mut normalization_quirks)?;
        let cached_bytes = entry_point_offset
            .and_then(|entry_point| data.get(entry_point..))
            .map_or(0, |bytes| bytes.len().min(256));
        let cached_signature_chars = cached_bytes.saturating_mul(2);
        let source_char_count = source.encode_utf16().count();
        let header_fast_path = i128::try_from(source_char_count)
            .ok()
            .and_then(|length| length.checked_add(i128::from(offset)))
            .is_some_and(|end| end < cached_signature_chars as i128)
            && !normalized
                .iter()
                .any(|byte| matches!(byte, b'$' | b'#' | b'+' | b'%' | b'*'));
        if header_fast_path {
            let matched = entry_point_offset.is_some_and(|entry_point| {
                compare_header_nibbles(
                    &normalized,
                    data.get(entry_point..).unwrap_or_default(),
                    usize::try_from(offset).unwrap_or(0),
                )
            });
            return Ok(BinaryCompareReport {
                matched,
                header_fast_path: true,
                quirks: normalization_quirks,
            });
        }

        let parsed = Self::parse_upstream_compatible(source)?;
        let compare_offset = entry_point_offset.and_then(|entry_point| {
            usize::try_from(offset)
                .ok()
                .and_then(|offset| entry_point.checked_add(offset))
        });
        let matched = match compare_offset {
            Some(offset) => parsed
                .pattern
                .matches_with_memory_map(data, offset, memory_map)?,
            None => false,
        };
        Ok(BinaryCompareReport {
            matched,
            header_fast_path: false,
            quirks: parsed.quirks,
        })
    }

    pub fn find_binary_wrapper(
        source: &str,
        data: &[u8],
        offset: i64,
        size: i64,
    ) -> Result<BinarySearchReport, BinarySearchError> {
        let parsed = Self::parse_upstream_compatible(source)?;
        let Some((offset, size)) = normalize_binary_search_range(data.len(), offset, size) else {
            return Ok(BinarySearchReport {
                found: None,
                quirks: parsed.quirks,
            });
        };
        let memory_map = MemoryMap {
            file_type: FileType::Binary,
            endian: Endian::Little,
            code_base: 0,
            start_load_offset: 0,
            records: vec![MemoryRecord {
                offset: 0,
                address: 0,
                size: data.len() as u64,
            }],
        };
        let found = parsed
            .pattern
            .find_with_memory_map(data, offset, size, &memory_map)?;
        Ok(BinarySearchReport {
            found,
            quirks: parsed.quirks,
        })
    }

    pub fn matches_raw(&self, data: &[u8], offset: usize) -> Result<bool, MatchError> {
        self.matches(data, offset, None)
    }

    pub fn matches_with_memory_map(
        &self,
        data: &[u8],
        offset: usize,
        memory_map: &MemoryMap,
    ) -> Result<bool, MatchError> {
        self.matches(data, offset, Some(memory_map))
    }

    pub fn find_raw(
        &self,
        data: &[u8],
        offset: usize,
        size: usize,
    ) -> Result<Option<FindResult>, MatchError> {
        self.find(data, offset, size, None)
    }

    pub fn find_with_memory_map(
        &self,
        data: &[u8],
        offset: usize,
        size: usize,
        memory_map: &MemoryMap,
    ) -> Result<Option<FindResult>, MatchError> {
        self.find(data, offset, size, Some(memory_map))
    }

    fn find(
        &self,
        data: &[u8],
        offset: usize,
        size: usize,
        memory_map: Option<&MemoryMap>,
    ) -> Result<Option<FindResult>, MatchError> {
        let Some(end) = offset
            .checked_add(size)
            .map(|end| end.min(data.len()))
            .filter(|end| offset < *end)
        else {
            return Ok(None);
        };
        let has_control = self.operations.iter().any(|operation| {
            matches!(
                operation,
                Operation::FindBytes { .. }
                    | Operation::RelativeOffset { .. }
                    | Operation::AbsoluteAddress { .. }
            )
        });
        let found = if has_control {
            self.find_control(data, offset, end, memory_map)?
        } else if self.operations.iter().any(|operation| {
            matches!(
                operation,
                Operation::Skip(_)
                    | Operation::NotNull(_)
                    | Operation::Ansi(_)
                    | Operation::NotAnsi(_)
                    | Operation::NotAnsiAndNotNull(_)
                    | Operation::DecimalDigit(_)
            )
        }) {
            self.find_sigbytes(data, offset, end)?
        } else {
            self.find_plain(data, offset, end)
        };
        Ok(found.map(|offset| FindResult {
            offset,
            size: if has_control {
                1
            } else {
                self.normalized_len / 2
            },
        }))
    }

    fn find_plain(&self, data: &[u8], offset: usize, end: usize) -> Option<usize> {
        let mut needle = Vec::new();
        for operation in &self.operations {
            let Operation::CompareBytes(bytes) = operation else {
                return None;
            };
            needle.extend_from_slice(bytes);
        }
        find_exact(data, offset, end, &needle)
    }

    fn find_sigbytes(
        &self,
        data: &[u8],
        offset: usize,
        end: usize,
    ) -> Result<Option<usize>, MatchError> {
        let mut predicates: Vec<SigPredicate> = Vec::new();
        for operation in &self.operations {
            match operation {
                Operation::CompareBytes(bytes) => {
                    predicates.extend(bytes.iter().copied().map(SigPredicate::Exact));
                }
                Operation::Skip(size) => {
                    predicates.extend(std::iter::repeat_n(SigPredicate::Any, *size));
                }
                Operation::NotNull(size) => {
                    predicates.extend(std::iter::repeat_n(SigPredicate::NotNull, *size));
                }
                Operation::Ansi(size) => {
                    predicates.extend(std::iter::repeat_n(SigPredicate::Ansi, *size));
                }
                Operation::NotAnsi(size) => {
                    predicates.extend(std::iter::repeat_n(SigPredicate::NotAnsi, *size));
                }
                Operation::NotAnsiAndNotNull(size) => {
                    predicates.extend(std::iter::repeat_n(SigPredicate::NotAnsiAndNotNull, *size));
                }
                Operation::DecimalDigit(size) => {
                    predicates.extend(std::iter::repeat_n(SigPredicate::Alphanumeric, *size));
                }
                Operation::FindBytes { .. }
                | Operation::RelativeOffset { .. }
                | Operation::AbsoluteAddress { .. } => return Ok(None),
            }
        }
        let leading_non_exact = predicates
            .iter()
            .take_while(|predicate| !matches!(predicate, SigPredicate::Exact(_)))
            .count();
        if leading_non_exact >= 3 {
            let fixed: Vec<u8> = predicates[leading_non_exact..]
                .iter()
                .map_while(|predicate| match predicate {
                    SigPredicate::Exact(byte) => Some(*byte),
                    _ => None,
                })
                .collect();
            if fixed.len() >= 3 {
                let mut search_from = offset;
                while search_from < end {
                    let Some(found) = find_exact(data, search_from, end, &fixed) else {
                        break;
                    };
                    match found.checked_sub(leading_non_exact) {
                        Some(candidate)
                            if candidate >= offset && self.matches(data, candidate, None)? =>
                        {
                            return Ok(Some(candidate));
                        }
                        _ => {}
                    }
                    search_from = found.saturating_add(1);
                }
                return Ok(None);
            }
        }
        Ok(find_predicates(data, offset, end, &predicates))
    }

    fn find_control(
        &self,
        data: &[u8],
        offset: usize,
        end: usize,
        memory_map: Option<&MemoryMap>,
    ) -> Result<Option<usize>, MatchError> {
        let contains_find = self
            .operations
            .iter()
            .any(|operation| matches!(operation, Operation::FindBytes { .. }));
        let mut anchor_index = 0;
        let mut anchor_delta = 0;
        if !contains_find {
            let mut current_delta: usize = 0;
            let mut maximum: usize = 0;
            for (index, operation) in self.operations.iter().enumerate() {
                if matches!(
                    operation,
                    Operation::RelativeOffset { .. } | Operation::AbsoluteAddress { .. }
                ) {
                    break;
                }
                if matches!(
                    operation,
                    Operation::CompareBytes(_) | Operation::FindBytes { .. }
                ) && operation_span(operation) > maximum
                {
                    maximum = operation_span(operation);
                    anchor_index = index;
                    anchor_delta = current_delta;
                }
                current_delta = current_delta.saturating_add(operation_span(operation));
            }
        }

        if anchor_index > 0 {
            let Some(anchor_start) = offset.checked_add(anchor_delta) else {
                return Ok(None);
            };
            let anchor = &self.operations[anchor_index];
            let mut search_from = anchor_start;
            while search_from < end {
                let Some(found) = find_control_anchor(data, search_from, end, anchor) else {
                    break;
                };
                match found.checked_sub(anchor_delta) {
                    Some(candidate)
                        if candidate >= offset && self.matches(data, candidate, memory_map)? =>
                    {
                        return Ok(Some(candidate));
                    }
                    _ => {}
                }
                search_from = found.saturating_add(1);
            }
            return Ok(None);
        }

        match self.operations.first() {
            Some(first) if is_searchable_control_anchor(first) => {
                let mut search_from = offset;
                while search_from < end {
                    let Some(found) = find_control_anchor(data, search_from, end, first) else {
                        break;
                    };
                    if self.matches(data, found, memory_map)? {
                        return Ok(Some(found));
                    }
                    search_from = found.saturating_add(1);
                }
                return Ok(None);
            }
            _ => {}
        }

        for candidate in offset..end {
            if self.matches(data, candidate, memory_map)? {
                return Ok(Some(candidate));
            }
        }
        Ok(None)
    }

    fn matches(
        &self,
        data: &[u8],
        offset: usize,
        memory_map: Option<&MemoryMap>,
    ) -> Result<bool, MatchError> {
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
                Operation::RelativeOffset { width } => {
                    let Some(memory_map) = memory_map else {
                        return Err(MatchError::MemoryMapRequired);
                    };
                    let Some(delta) = relative_delta(data, cursor, *width, memory_map) else {
                        return Ok(false);
                    };
                    let target = if matches!(memory_map.file_type, FileType::Com | FileType::MsDos)
                    {
                        segmented_relative_offset(cursor, delta)
                    } else {
                        memory_map
                            .offset_to_address(cursor as u64)
                            .and_then(|address| add_signed(address, delta))
                            .and_then(|address| memory_map.address_to_offset(address))
                            .and_then(|offset| usize::try_from(offset).ok())
                    };
                    let Some(target) = target else {
                        return Ok(false);
                    };
                    cursor = target;
                }
                Operation::AbsoluteAddress { width, .. } => {
                    let Some(memory_map) = memory_map else {
                        return Err(MatchError::MemoryMapRequired);
                    };
                    let Some(address) = read_unsigned(data, cursor, *width, memory_map.endian)
                    else {
                        return Ok(false);
                    };
                    let target = match (memory_map.file_type, *width) {
                        (FileType::MsDos, 2) => address
                            .checked_add(memory_map.code_base)
                            .and_then(|value| memory_map.address_to_offset(value))
                            .and_then(|offset| usize::try_from(offset).ok()),
                        (FileType::MsDos, 4) => {
                            let low = address & 0xffff;
                            let high = (address >> 16) & 0xffff;
                            high.checked_mul(16)
                                .and_then(|value| value.checked_add(low))
                                .and_then(|value| value.checked_add(memory_map.start_load_offset))
                                .and_then(|offset| usize::try_from(offset).ok())
                        }
                        (FileType::MsDos, _) => Some(cursor),
                        _ => memory_map
                            .address_to_offset(address)
                            .and_then(|offset| usize::try_from(offset).ok()),
                    };
                    let Some(target) = target else {
                        return Ok(false);
                    };
                    cursor = target;
                }
            }
            if memory_map.is_some() && cursor > data.len() {
                return Ok(false);
            }
        }
        Ok(true)
    }
}

fn normalize_binary_search_range(
    data_len: usize,
    offset: i64,
    size: i64,
) -> Option<(usize, usize)> {
    let offset = usize::try_from(offset).ok()?;
    if offset >= data_len {
        return None;
    }
    let remaining = data_len - offset;
    let size = if size == -1 {
        remaining
    } else {
        usize::try_from(size).ok()?.min(remaining)
    };
    (size > 0).then_some((offset, size))
}

#[derive(Clone, Copy)]
enum SigPredicate {
    Exact(u8),
    Any,
    NotNull,
    Ansi,
    NotAnsi,
    NotAnsiAndNotNull,
    Alphanumeric,
    DecimalDigit,
    RecordAnsi,
    RecordNotAnsi,
    RecordNotAnsiAndNotNull,
}

impl SigPredicate {
    fn matches(self, byte: u8) -> bool {
        match self {
            Self::Exact(expected) => byte == expected,
            Self::Any => true,
            Self::NotNull => byte != 0,
            Self::Ansi => (0x20..=0x7e).contains(&byte),
            Self::NotAnsi => !(0x20..=0x7e).contains(&byte),
            Self::NotAnsiAndNotNull => byte != 0 && !(0x20..=0x7e).contains(&byte),
            Self::Alphanumeric => byte.is_ascii_alphanumeric(),
            Self::DecimalDigit => byte.is_ascii_digit(),
            Self::RecordAnsi => (0x20..0x80).contains(&byte),
            Self::RecordNotAnsi => !(0x20..0x80).contains(&byte),
            Self::RecordNotAnsiAndNotNull => byte != 0 && !(0x20..0x80).contains(&byte),
        }
    }
}

fn find_exact(data: &[u8], offset: usize, end: usize, needle: &[u8]) -> Option<usize> {
    if needle.is_empty() || offset > end {
        return None;
    }
    let region = data.get(offset..end)?;
    region
        .windows(needle.len())
        .position(|candidate| candidate == needle)
        .and_then(|relative| offset.checked_add(relative))
}

fn find_predicates(
    data: &[u8],
    offset: usize,
    end: usize,
    predicates: &[SigPredicate],
) -> Option<usize> {
    if predicates.is_empty() || offset > end {
        return None;
    }
    let region = data.get(offset..end)?;
    region
        .windows(predicates.len())
        .position(|candidate| {
            predicates
                .iter()
                .copied()
                .zip(candidate.iter().copied())
                .all(|(predicate, byte)| predicate.matches(byte))
        })
        .and_then(|relative| offset.checked_add(relative))
}

fn operation_span(operation: &Operation) -> usize {
    match operation {
        Operation::CompareBytes(bytes) => bytes.len(),
        Operation::Skip(size)
        | Operation::NotNull(size)
        | Operation::Ansi(size)
        | Operation::NotAnsi(size)
        | Operation::NotAnsiAndNotNull(size)
        | Operation::DecimalDigit(size) => *size,
        Operation::FindBytes { window, .. } => *window,
        Operation::RelativeOffset { width } | Operation::AbsoluteAddress { width, .. } => *width,
    }
}

fn is_searchable_control_anchor(operation: &Operation) -> bool {
    matches!(
        operation,
        Operation::CompareBytes(_)
            | Operation::FindBytes { .. }
            | Operation::NotNull(_)
            | Operation::Ansi(_)
            | Operation::NotAnsi(_)
            | Operation::NotAnsiAndNotNull(_)
            | Operation::DecimalDigit(_)
    )
}

fn find_control_anchor(
    data: &[u8],
    offset: usize,
    end: usize,
    operation: &Operation,
) -> Option<usize> {
    match operation {
        Operation::CompareBytes(bytes) | Operation::FindBytes { bytes, .. } => {
            find_exact(data, offset, end, bytes)
        }
        Operation::NotNull(size) => {
            find_predicates(data, offset, end, &vec![SigPredicate::NotNull; *size])
        }
        Operation::Ansi(size) => {
            find_predicates(data, offset, end, &vec![SigPredicate::RecordAnsi; *size])
        }
        Operation::NotAnsi(size) => {
            find_predicates(data, offset, end, &vec![SigPredicate::RecordNotAnsi; *size])
        }
        Operation::NotAnsiAndNotNull(size) => find_predicates(
            data,
            offset,
            end,
            &vec![SigPredicate::RecordNotAnsiAndNotNull; *size],
        ),
        Operation::DecimalDigit(size) => {
            find_predicates(data, offset, end, &vec![SigPredicate::DecimalDigit; *size])
        }
        Operation::Skip(_)
        | Operation::RelativeOffset { .. }
        | Operation::AbsoluteAddress { .. } => None,
    }
}

fn relative_delta(
    data: &[u8],
    offset: usize,
    width: usize,
    memory_map: &MemoryMap,
) -> Option<i128> {
    let value = match width {
        1 => i128::from(read_signed(data, offset, width, memory_map.endian)?).checked_add(1)?,
        2 => i128::from(read_unsigned(data, offset, width, memory_map.endian)?).checked_add(
            if memory_map.file_type == FileType::AmigaHunk {
                0
            } else {
                2
            },
        )?,
        4 | 8 => i128::from(read_signed(data, offset, width, memory_map.endian)?).checked_add(
            if memory_map.file_type == FileType::AmigaHunk {
                0
            } else {
                width as i128
            },
        )?,
        _ => return None,
    };
    Some(value)
}

fn read_unsigned(data: &[u8], offset: usize, width: usize, endian: Endian) -> Option<u64> {
    let bytes = bounded_slice(data, offset, width)?;
    Some(match endian {
        Endian::Little => bytes
            .iter()
            .rev()
            .fold(0_u64, |value, byte| (value << 8) | u64::from(*byte)),
        Endian::Big => bytes
            .iter()
            .fold(0_u64, |value, byte| (value << 8) | u64::from(*byte)),
    })
}

fn read_signed(data: &[u8], offset: usize, width: usize, endian: Endian) -> Option<i64> {
    let unsigned = read_unsigned(data, offset, width, endian)?;
    let shift = 64_usize.checked_sub(width.checked_mul(8)?)?;
    Some(((unsigned << shift) as i64) >> shift)
}

fn add_signed(value: u64, delta: i128) -> Option<u64> {
    let result = i128::from(value).checked_add(delta)?;
    u64::try_from(result).ok()
}

fn segmented_relative_offset(offset: usize, delta: i128) -> Option<usize> {
    let high = offset & !0xffff;
    let low = i128::try_from(offset & 0xffff).ok()?;
    let wrapped = low.checked_add(delta)?.rem_euclid(0x10000);
    high.checked_add(usize::try_from(wrapped).ok()?)
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
    if !count.is_multiple_of(2) {
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

fn compare_header_nibbles(normalized: &[u8], data: &[u8], offset: usize) -> bool {
    if normalized.is_empty() {
        return false;
    }
    normalized.iter().enumerate().all(|(index, expected)| {
        let Some(nibble_index) = offset
            .checked_mul(2)
            .and_then(|base| base.checked_add(index))
        else {
            return false;
        };
        let Some(byte) = data.get(nibble_index / 2) else {
            return false;
        };
        let actual = if nibble_index % 2 == 0 {
            hex_digit(byte >> 4)
        } else {
            hex_digit(byte & 0x0f)
        };
        *expected == b'.' || *expected == actual
    })
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
    TrailingUnexpectedCharacter {
        position: usize,
        character: char,
    },
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum BinaryCompareError {
    Parse(ParseError),
    Match(MatchError),
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum BinarySearchError {
    Parse(ParseError),
    Match(MatchError),
}

impl fmt::Display for BinaryCompareError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Parse(error) => error.fmt(formatter),
            Self::Match(error) => error.fmt(formatter),
        }
    }
}

impl std::error::Error for BinaryCompareError {}

impl From<ParseError> for BinaryCompareError {
    fn from(error: ParseError) -> Self {
        Self::Parse(error)
    }
}

impl From<MatchError> for BinaryCompareError {
    fn from(error: MatchError) -> Self {
        Self::Match(error)
    }
}

impl fmt::Display for BinarySearchError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Parse(error) => error.fmt(formatter),
            Self::Match(error) => error.fmt(formatter),
        }
    }
}

impl std::error::Error for BinarySearchError {}

impl From<ParseError> for BinarySearchError {
    fn from(error: ParseError) -> Self {
        Self::Parse(error)
    }
}

impl From<MatchError> for BinarySearchError {
    fn from(error: MatchError) -> Self {
        Self::Match(error)
    }
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
    use super::{
        CompatibilityQuirk, Endian, FileType, FindResult, MatchError, MemoryMap, MemoryRecord,
        Operation, ParseErrorKind, Pattern,
    };
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

    fn memory_map(value: &Value) -> MemoryMap {
        let file_type = match value["file_type"]
            .as_str()
            .expect("file_type should be a string")
        {
            "binary" => FileType::Binary,
            "pe" => FileType::Pe,
            "elf" => FileType::Elf,
            "macho" => FileType::MachO,
            "com" => FileType::Com,
            "msdos" => FileType::MsDos,
            "amigahunk" => FileType::AmigaHunk,
            other => panic!("unsupported fixture file type {other}"),
        };
        let endian = match value["endian"].as_str().expect("endian should be a string") {
            "little" => Endian::Little,
            "big" => Endian::Big,
            other => panic!("unsupported fixture endian {other}"),
        };
        let records = value["records"]
            .as_array()
            .expect("records should be an array")
            .iter()
            .map(|record| MemoryRecord {
                offset: record["offset"]
                    .as_u64()
                    .expect("record offset should be an integer"),
                address: record["address"]
                    .as_u64()
                    .expect("record address should be an integer"),
                size: record["size"]
                    .as_u64()
                    .expect("record size should be an integer"),
            })
            .collect();
        MemoryMap {
            file_type,
            endian,
            code_base: value["code_base"].as_u64().unwrap_or(0),
            start_load_offset: value["start_load_offset"].as_u64().unwrap_or(0),
            records,
        }
    }

    fn derived_memory_map(value: &Value) -> MemoryMap {
        let file_type = match value["file_type"]
            .as_str()
            .expect("file_type should be a string")
        {
            "pe" => FileType::Pe,
            "elf" => FileType::Elf,
            "macho" => FileType::MachO,
            "com" => FileType::Com,
            "msdos" => FileType::MsDos,
            "amigahunk" => FileType::AmigaHunk,
            other => panic!("unsupported derived file type {other}"),
        };
        let endian = match value["endian"].as_str().expect("endian should be a string") {
            "little" => Endian::Little,
            "big" => Endian::Big,
            other => panic!("unsupported derived endian {other}"),
        };
        let records = value["records"]
            .as_array()
            .expect("records should be an array")
            .iter()
            .filter_map(|record| {
                let offset = record["offset"]
                    .as_str()
                    .expect("derived offset should be a string")
                    .parse::<i64>()
                    .expect("derived offset should be decimal");
                let address = record["address"]
                    .as_str()
                    .expect("derived address should be a string")
                    .parse::<u64>()
                    .expect("derived address should be decimal");
                let size = record["size"]
                    .as_str()
                    .expect("derived size should be a string")
                    .parse::<u64>()
                    .expect("derived size should be decimal");
                (offset >= 0 && address != u64::MAX && size != 0).then_some(MemoryRecord {
                    offset: offset as u64,
                    address,
                    size,
                })
            })
            .collect();
        MemoryMap {
            file_type,
            endian,
            code_base: value["code_base"]
                .as_str()
                .expect("code_base should be a string")
                .parse()
                .expect("code_base should be decimal"),
            start_load_offset: value["start_load_offset"]
                .as_str()
                .expect("start_load_offset should be a string")
                .parse()
                .expect("start_load_offset should be decimal"),
            records,
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

    #[test]
    fn binary_wrapper_matches_pinned_qt5_oracle() {
        let oracle: Value = serde_json::from_str(include_str!(
            "../../../docs/research/data/signature-oracle-qt5.json"
        ))
        .expect("oracle baseline should be valid JSON");
        let cases = oracle["cases"]
            .as_array()
            .expect("oracle cases should be an array");
        let mut compared = 0;
        let mut fast_paths = 0;
        let mut generic_quirks = 0;
        for case in cases {
            if case["binary_script_compare"].as_bool() != Some(true) {
                continue;
            }
            let id = case["id"].as_str().expect("case id should be a string");
            let source = case["pattern"]
                .as_str()
                .expect("pattern should be a string");
            let data = decode_hex(
                case["data_hex"]
                    .as_str()
                    .expect("data should be a hex string"),
            );
            let offset = case["offset"]
                .as_i64()
                .expect("offset should be an integer");
            let expected = case["binary_script_compare_result"]
                .as_bool()
                .expect("wrapper result should be boolean");
            let actual = Pattern::compare_binary_wrapper(source, &data, offset)
                .unwrap_or_else(|error| panic!("cannot compare {id}: {error}"));
            assert_eq!(actual.matched, expected, "wrapper mismatch for {id}");
            fast_paths += usize::from(actual.header_fast_path);
            generic_quirks += usize::from(!actual.quirks.is_empty());
            compared += 1;
        }
        assert_eq!(compared, 7);
        assert_eq!(fast_paths, 5);
        assert_eq!(generic_quirks, 1);
        let mut negative_header = vec![0_u8; 256];
        negative_header[..4].copy_from_slice(b"COLL");
        let negative_fast = Pattern::compare_binary_wrapper("'COLL'", &negative_header, -1)
            .expect("Qt5 header fast path should clamp a negative mid position");
        assert!(negative_fast.header_fast_path);
        assert!(negative_fast.matched);
        let negative_generic = Pattern::compare_binary_wrapper("**", b"A", -1)
            .expect("generic matcher should reject a negative offset without an adapter error");
        assert!(!negative_generic.header_fast_path);
        assert!(!negative_generic.matched);
    }

    #[test]
    fn entry_point_wrapper_uses_bounded_cache_and_real_pe_map() {
        let mut data = vec![0_u8; 0x600];
        data[0x200..0x208].copy_from_slice(&decode_hex("5589e583ec04833d"));
        let map = MemoryMap {
            file_type: FileType::Pe,
            endian: Endian::Little,
            code_base: 0,
            start_load_offset: 0,
            records: vec![
                MemoryRecord {
                    offset: 0,
                    address: 0x400000,
                    size: 0x200,
                },
                MemoryRecord {
                    offset: 0x200,
                    address: 0x401000,
                    size: 0x200,
                },
            ],
        };
        let matched =
            Pattern::compare_entry_point_wrapper("5589E583EC04833D", &data, Some(0x200), 0, &map)
                .expect("fixed Cygwin32 signature should be valid");
        assert!(matched.matched);
        assert!(matched.header_fast_path);

        data[0x200] ^= 0xff;
        let mismatch =
            Pattern::compare_entry_point_wrapper("5589E583EC04833D", &data, Some(0x200), 0, &map)
                .expect("fixed Cygwin32 signature should be valid");
        assert!(!mismatch.matched);
        assert!(mismatch.header_fast_path);

        let truncated =
            Pattern::compare_entry_point_wrapper("5589E583EC04833D", &data[..0x200], None, 0, &map)
                .expect("fixed Cygwin32 signature should be valid");
        assert!(!truncated.matched);
        assert!(!truncated.header_fast_path);
    }

    #[test]
    fn binary_search_wrappers_match_pinned_qt5_oracle() {
        let oracle: Value = serde_json::from_str(include_str!(
            "../../../docs/research/data/signature-oracle-qt5.json"
        ))
        .expect("oracle baseline should be valid JSON");
        let cases = oracle["cases"]
            .as_array()
            .expect("oracle cases should be an array");
        let mut compared = 0;
        for case in cases {
            if case["binary_script_find_signature"].as_bool() != Some(true) {
                continue;
            }
            let id = case["id"].as_str().expect("case id should be a string");
            let source = case["pattern"]
                .as_str()
                .expect("pattern should be a string");
            let data = decode_hex(
                case["data_hex"]
                    .as_str()
                    .expect("data should be a hex string"),
            );
            let offset = case["search_offset"]
                .as_i64()
                .expect("search offset should be an integer");
            let size = case["search_size"]
                .as_i64()
                .expect("search size should be an integer");
            let expected_offset = case["binary_script_find_signature_result"]
                .as_i64()
                .expect("findSignature result should be an integer");
            assert_eq!(
                case["binary_script_f_sig_result"].as_i64(),
                Some(expected_offset),
                "fSig oracle alias mismatch for {id}"
            );
            assert_eq!(
                case["binary_script_is_signature_present_result"].as_bool(),
                Some(expected_offset >= 0),
                "isSignaturePresent oracle projection mismatch for {id}"
            );
            let actual = Pattern::find_binary_wrapper(source, &data, offset, size)
                .unwrap_or_else(|error| panic!("cannot search {id}: {error}"));
            assert_eq!(
                actual.found.map_or(-1, |found| found.offset as i64),
                expected_offset,
                "findSignature wrapper mismatch for {id}"
            );
            if let Some(found) = actual.found {
                assert_eq!(
                    found.size,
                    case["find_result_size"]
                        .as_u64()
                        .and_then(|value| usize::try_from(value).ok())
                        .expect("find result size should fit usize"),
                    "match size mismatch for {id}"
                );
            }
            compared += 1;
        }
        assert_eq!(compared, 4);
    }

    #[test]
    fn binary_search_wrapper_rejects_invalid_ranges_without_panicking() {
        for (offset, size) in [(-1, 1), (0, -2), (0, 0), (i64::MAX, i64::MAX)] {
            let actual = Pattern::find_binary_wrapper("41", b"A", offset, size)
                .expect("a valid pattern with an invalid range is not an adapter error");
            assert_eq!(actual.found, None, "range ({offset}, {size})");
        }
    }

    #[test]
    fn memory_map_matches_agree_with_pinned_xbinary_oracle() {
        let selected = BTreeSet::from([
            "pe_relative_crosses_raw_gap",
            "elf_big_endian_relative_crosses_raw_gap",
            "macho_64_absolute_crosses_raw_gap",
            "com_relative_ignores_nonidentity_map",
            "msdos_absolute_word_adds_code_base",
            "msdos_far_pointer_uses_segment_address",
            "amigahunk_relative_word_omits_width_increment",
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
            let map = memory_map(&case["memory_map"]);
            let report = Pattern::parse_upstream_compatible(source)
                .unwrap_or_else(|error| panic!("cannot parse {id}: {error}"));
            assert_eq!(
                report.pattern.matches_with_memory_map(&data, offset, &map),
                Ok(expected),
                "differential mismatch for {id}"
            );
            compared += 1;
        }
        assert_eq!(compared, selected.len());
    }

    #[test]
    fn parser_derived_memory_maps_agree_with_pinned_xbinary_oracle() {
        let selected = BTreeSet::from([
            "pe32_parser_memory_map_relative_jump",
            "pe64_parser_memory_map_relative_jump",
            "elf64_parser_memory_map_relative_jump",
            "elf32_parser_memory_map_relative_jump",
            "macho64_parser_memory_map_absolute_jump",
            "macho32_parser_memory_map_absolute_jump",
            "com_parser_memory_map_relative_jump",
            "msdos_parser_memory_map_far_pointer",
            "amigahunk_parser_memory_map_relative_jump",
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
            assert_eq!(case["format_valid"].as_bool(), Some(true));
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
            let map = derived_memory_map(&case["derived_memory_map"]);
            let report = Pattern::parse_upstream_compatible(source)
                .unwrap_or_else(|error| panic!("cannot parse {id}: {error}"));
            assert_eq!(
                report.pattern.matches_with_memory_map(&data, offset, &map),
                Ok(expected),
                "differential mismatch for {id}"
            );
            compared += 1;
        }
        assert_eq!(compared, selected.len());
    }

    #[test]
    fn independent_find_paths_agree_with_pinned_xbinary_oracle() {
        let selected = BTreeSet::from([
            "quoted_literal_and_wildcard_match",
            "exact_match_at_eof",
            "all_byte_classes_match",
            "decimal_class_rejects_letter",
            "ansi_del_compare_find_divergence",
            "not_ansi_del_compare_find_divergence",
            "find_at_window_end",
            "find_outside_window",
            "relative_offset_little_endian",
            "absolute_address_identity_map",
            "address_markers_around_ignored_base",
            "odd_hex_qbytearray_behavior",
            "unterminated_quote_behavior",
            "single_wildcard_is_zero_width",
            "plain_find_clamps_oversized_range",
            "sigbyte_fixed_anchor_rechecks_record_classes",
            "control_longest_literal_anchor",
            "control_class_first_anchor",
            "control_relative_first_fallback",
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
            let search_offset = case["search_offset"]
                .as_u64()
                .and_then(|value| usize::try_from(value).ok())
                .expect("search offset should fit usize");
            let search_size = case["search_size"]
                .as_u64()
                .and_then(|value| usize::try_from(value).ok())
                .expect("search size should fit usize");
            let expected_offset = case["find_offset"]
                .as_i64()
                .expect("find offset should be an integer");
            let expected = (expected_offset >= 0).then(|| FindResult {
                offset: expected_offset as usize,
                size: case["find_result_size"]
                    .as_u64()
                    .and_then(|value| usize::try_from(value).ok())
                    .expect("find result size should fit usize"),
            });
            let report = Pattern::parse_upstream_compatible(source)
                .unwrap_or_else(|error| panic!("cannot parse {id}: {error}"));
            let actual = if report.pattern.operations().iter().any(|operation| {
                matches!(
                    operation,
                    Operation::RelativeOffset { .. } | Operation::AbsoluteAddress { .. }
                )
            }) {
                let map = MemoryMap {
                    file_type: FileType::Binary,
                    endian: Endian::Little,
                    code_base: 0,
                    start_load_offset: 0,
                    records: vec![MemoryRecord {
                        offset: 0,
                        address: 0,
                        size: data.len() as u64,
                    }],
                };
                report
                    .pattern
                    .find_with_memory_map(&data, search_offset, search_size, &map)
            } else {
                report.pattern.find_raw(&data, search_offset, search_size)
            };
            assert_eq!(actual, Ok(expected), "find mismatch for {id}");
            compared += 1;
        }
        assert_eq!(compared, selected.len());
    }
}
