//! Checked input model: read-only byte sources, validated views and scan
//! source variants.
//!
//! Parsers never open paths or seek global file handles directly. They consume
//! a [`ByteSource`] through checked ranges only. Offsets and lengths use `u64`
//! internally; conversions to `usize` and any allocation are checked against
//! platform limits and the request budget before being performed. See
//! `docs/design/architecture.md` section 7 and ADR 0013.

use core::fmt;
use std::path::Path;

/// A half-open byte range `[start, start + length)` relative to a known view.
///
/// `start` and `length` are non-negative. The range is stored uncombined so
/// that callers can distinguish "absolute offset" from "relative view offset"
/// at the field level instead of overloading a single field.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ByteRange {
    /// Absolute or view-relative start offset in bytes.
    pub start: u64,
    /// Length in bytes.
    pub length: u64,
}

impl ByteRange {
    /// Construct a range, returning `None` when `start + length` overflows.
    pub fn new(start: u64, length: u64) -> Option<Self> {
        let end = start.checked_add(length)?;
        // A zero-length range at `u64::MAX` is still valid (end == start).
        let _ = end;
        Some(Self { start, length })
    }

    /// The exclusive end offset, or `None` on overflow.
    pub fn end(self) -> Option<u64> {
        self.start.checked_add(self.length)
    }
}

/// Fixed-length, random-access byte source contract.
///
/// Implementations may borrow memory, own bytes, back by a file or mmap. Chunk
/// reads may make positive progress and fill less than requested on a
/// well-typed EOF, but a short read, seek or I/O error must be reported as a
/// typed [`IoError`] before probing. Implementations must not touch bytes
/// outside the requested range. `unsafe` file or mmap adapters live in a
/// separate adapter module and document their safety invariants.
pub trait ByteSource: std::fmt::Debug {
    /// The stable logical length of the source in bytes.
    fn len(&self) -> u64;

    /// `true` if the source contains zero bytes.
    fn is_empty(&self) -> bool {
        self.len() == 0
    }

    /// Read `out` bytes starting at `offset`, filling as much as available and
    /// returning the number of bytes read. A failure before any positive
    /// progress returns an [`IoError`].
    fn read_at(&self, offset: u64, out: &mut [u8]) -> Result<usize, IoError>;
}

/// A validated, read-only view over a [`ByteSource`] bounded by a checked
/// [`ByteRange`]. All integer reads first validate bounds; parsers must not
/// use slice panics to signal parse errors.
#[derive(Debug, Clone)]
pub struct ByteView<'a> {
    source: &'a dyn ByteSource,
    range: ByteRange,
}

impl<'a> ByteView<'a> {
    /// Construct a view, returning `None` if the range exceeds the source
    /// length or overflows.
    pub fn new(source: &'a dyn ByteSource, range: ByteRange) -> Option<Self> {
        let end = range.end()?;
        if end > source.len() {
            return None;
        }
        Some(Self { source, range })
    }

    /// The source-relative range covered by this view.
    pub fn range(&self) -> ByteRange {
        self.range
    }

    /// The length of this view in bytes.
    pub fn len(&self) -> u64 {
        self.range.length
    }

    /// `true` if the view covers zero bytes.
    pub fn is_empty(&self) -> bool {
        self.range.length == 0
    }

    /// Create a sub-view at `offset` of `length` bytes, checked against this
    /// view's bounds.
    pub fn subview(&self, offset: u64, length: u64) -> Option<ByteView<'_>> {
        let abs_start = self.range.start.checked_add(offset)?;
        let range = ByteRange::new(abs_start, length)?;
        ByteView::new(self.source, range)
    }

    /// Read `out` bytes starting at the view-relative `offset`.
    pub fn read_at(&self, offset: u64, out: &mut [u8]) -> Result<usize, IoError> {
        let abs = self
            .range
            .start
            .checked_add(offset)
            .ok_or(IoError::SeekError)?;
        self.source.read_at(abs, out)
    }
}

/// Display and provenance identity for a scan input. Identity is for display
/// and traceability only and must not participate in format identification.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct InputIdentity {
    /// Optional human-readable name shown in output.
    pub display_name: Option<String>,
    /// Optional logical path used for rule extension checks and provenance.
    pub logical_path: Option<String>,
}

/// Input source variants accepted by the scan service. Path entry points open
/// the file and read metadata before converting to a checked source; the core
/// API uses platform-native paths and UTF-8 limitations belong only to FFI.
#[derive(Debug)]
pub enum ScanSource<'a> {
    /// In-memory bytes with an explicit identity.
    Bytes {
        /// The byte buffer.
        data: &'a [u8],
        /// Display/provenance identity.
        identity: InputIdentity,
    },
    /// A pre-built [`ByteSource`] with an explicit identity.
    ByteSource {
        /// The byte source.
        source: &'a dyn ByteSource,
        /// Display/provenance identity.
        identity: InputIdentity,
    },
    /// A filesystem path opened by the engine adapter.
    Path(&'a Path),
}

impl<'a> ScanSource<'a> {
    /// The identity for non-path sources, or `None` for path sources whose
    /// identity is derived after opening.
    pub fn identity(&self) -> Option<&InputIdentity> {
        match self {
            ScanSource::Bytes { identity, .. } | ScanSource::ByteSource { identity, .. } => {
                Some(identity)
            }
            ScanSource::Path(_) => None,
        }
    }
}

/// Typed I/O error classification for checked input. Distinguishes
/// not-found, permission, short read and changed-during-read; see
/// `docs/design/api.md` section 12.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum IoError {
    /// The path or resource was not found.
    NotFound,
    /// Permission was denied.
    PermissionDenied,
    /// The source ended before the requested bytes were available.
    UnexpectedEof,
    /// A seek was requested outside the valid range.
    SeekError,
    /// A raw read or metadata operation failed.
    Other(String),
}

impl fmt::Display for IoError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            IoError::NotFound => f.write_str("input not found"),
            IoError::PermissionDenied => f.write_str("permission denied"),
            IoError::UnexpectedEof => f.write_str("unexpected end of input"),
            IoError::SeekError => f.write_str("seek out of range"),
            IoError::Other(msg) => write!(f, "io error: {msg}"),
        }
    }
}

impl std::error::Error for IoError {}
