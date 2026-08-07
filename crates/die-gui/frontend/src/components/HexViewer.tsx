import { useState, useEffect, useCallback, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { invoke } from "@tauri-apps/api/core";
import { Search, ArrowRight, Copy, Check } from "lucide-react";

interface HexLine {
  offset: string;
  hex: string;
  ascii: string;
}

interface HexDump {
  file_size: number;
  start_offset: number;
  lines: HexLine[];
}

interface SearchHit {
  offset: number;
}

interface SearchResult {
  file_size: number;
  hits: SearchHit[];
}

const LINE_BYTES = 16;
const LINE_HEIGHT = 20;
const VISIBLE_LINES = 30;
const CHUNK_BYTES = LINE_BYTES * VISIBLE_LINES; // 480 bytes per chunk

export function HexViewer({ path }: { path: string }) {
  const { t } = useTranslation();
  const [fileSize, setFileSize] = useState(0);
  const [scrollTop, setScrollTop] = useState(0);
  const [chunks, setChunks] = useState<Map<number, HexLine[]>>(new Map());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchPattern, setSearchPattern] = useState("");
  const [searchResults, setSearchResults] = useState<SearchHit[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [jumpOffset, setJumpOffset] = useState("");
  const [copied, setCopied] = useState(false);
  const [selectedLine, setSelectedLine] = useState<number | null>(null);

  // Total number of lines in the file (for virtual scroll height).
  const totalLines = useMemo(() => Math.ceil(fileSize / LINE_BYTES), [fileSize]);
  const totalHeight = totalLines * LINE_HEIGHT;

  // First visible line index based on scroll position.
  const firstVisibleLine = Math.floor(scrollTop / LINE_HEIGHT);
  const visibleStart = Math.max(0, firstVisibleLine - 5);
  const visibleEnd = Math.min(totalLines, firstVisibleLine + VISIBLE_LINES + 5);

  // Load file size on path change.
  useEffect(() => {
    if (!path) return;
    setChunks(new Map());
    setScrollTop(0);
    setSearchResults(null);
    setSelectedLine(null);
    setLoading(true);
    setError(null);
    invoke<HexDump>("read_hex", { path, offset: 0, maxBytes: 16 })
      .then((d) => {
        setFileSize(d.file_size);
        setLoading(false);
      })
      .catch((e) => {
        setError(String(e));
        setLoading(false);
      });
  }, [path]);

  // Load visible chunks on demand.
  const loadChunk = useCallback(
    async (chunkIndex: number) => {
      if (!path || chunks.has(chunkIndex)) return;
      const offset = chunkIndex * CHUNK_BYTES;
      if (offset >= fileSize) return;
      try {
        const dump = await invoke<HexDump>("read_hex", {
          path,
          offset,
          maxBytes: CHUNK_BYTES,
        });
        setChunks((prev) => {
          const next = new Map(prev);
          next.set(chunkIndex, dump.lines);
          return next;
        });
      } catch (e) {
        setError(String(e));
      }
    },
    [path, chunks, fileSize],
  );

  // Load all visible chunks.
  useEffect(() => {
    if (!path || fileSize === 0) return;
    const startChunk = Math.floor(visibleStart / (CHUNK_BYTES / LINE_BYTES));
    const endChunk = Math.ceil(visibleEnd / (CHUNK_BYTES / LINE_BYTES));
    for (let c = startChunk; c <= endChunk; c++) {
      loadChunk(c);
    }
  }, [path, fileSize, visibleStart, visibleEnd, loadChunk]);

  // Clean up old chunks to save memory (keep only visible ± 10 chunks).
  useEffect(() => {
    if (chunks.size < 20) return;
    const startChunk = Math.floor(visibleStart / (CHUNK_BYTES / LINE_BYTES));
    const endChunk = Math.ceil(visibleEnd / (CHUNK_BYTES / LINE_BYTES));
    setChunks((prev) => {
      const next = new Map();
      for (let c = startChunk - 10; c <= endChunk + 10; c++) {
        if (prev.has(c)) next.set(c, prev.get(c)!);
      }
      return next;
    });
  }, [visibleStart, visibleEnd, chunks.size]);

  // Get a line from the chunk cache.
  function getLine(lineIndex: number): HexLine | null {
    const chunkIndex = Math.floor(lineIndex / (CHUNK_BYTES / LINE_BYTES));
    const lineInChunk = lineIndex % (CHUNK_BYTES / LINE_BYTES);
    const chunk = chunks.get(chunkIndex);
    if (!chunk || lineInChunk >= chunk.length) return null;
    return chunk[lineInChunk];
  }

  // Handle search.
  async function handleSearch() {
    if (!path || !searchPattern.trim()) return;
    setSearching(true);
    setError(null);
    try {
      const result = await invoke<SearchResult>("search_hex", {
        path,
        pattern: searchPattern,
        startOffset: 0,
        maxHits: 1000,
      });
      setSearchResults(result.hits);
    } catch (e) {
      setError(String(e));
    } finally {
      setSearching(false);
    }
  }

  // Handle jump to offset.
  function handleJump() {
    const off = jumpOffset.trim();
    if (!off) return;
    // Parse as hex (with or without 0x prefix) or decimal.
    const num = off.startsWith("0x") || off.startsWith("0X")
      ? parseInt(off.slice(2), 16)
      : /^[0-9a-fA-F]+$/.test(off) && off.length > 3
        ? parseInt(off, 16)
        : parseInt(off, 10);
    if (isNaN(num) || num < 0 || num >= fileSize) {
      setError(t("hex.invalidOffset"));
      return;
    }
    const lineIndex = Math.floor(num / LINE_BYTES);
    setScrollTop(lineIndex * LINE_HEIGHT);
    setSelectedLine(lineIndex);
    setError(null);
  }

  // Jump to a search hit.
  function jumpToHit(offset: number) {
    const lineIndex = Math.floor(offset / LINE_BYTES);
    setScrollTop(lineIndex * LINE_HEIGHT);
    setSelectedLine(lineIndex);
  }

  // Copy selected line to clipboard.
  async function copyLine(line: HexLine) {
    const text = `${line.offset}  ${line.hex}  ${line.ascii}`;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard not available.
    }
  }

  if (!path) return null;

  // Render visible lines.
  const renderedLines: React.ReactNode[] = [];
  for (let i = visibleStart; i < visibleEnd; i++) {
    const line = getLine(i);
    if (!line) {
      renderedLines.push(
        <div
          key={i}
          style={{ height: LINE_HEIGHT, lineHeight: `${LINE_HEIGHT}px` }}
          className="text-fg-muted"
        >
          {" ".repeat(8)}  {"—".repeat(47)}  {"—".repeat(16)}
        </div>,
      );
    } else {
      // Check if this line contains a search hit.
      const lineStartOffset = i * LINE_BYTES;
      const lineEndOffset = lineStartOffset + LINE_BYTES;
      const hasHit = searchResults?.some(
        (h) => h.offset >= lineStartOffset && h.offset < lineEndOffset,
      );
      renderedLines.push(
        <div
          key={i}
          style={{ height: LINE_HEIGHT, lineHeight: `${LINE_HEIGHT}px` }}
          className={`flex gap-2 cursor-pointer hover:bg-accent-blue/10 ${selectedLine === i ? "bg-accent-blue/20" : ""} ${hasHit ? "bg-yellow-500/20" : ""}`}
          onClick={() => {
            setSelectedLine(i);
            copyLine(line);
          }}
        >
          <span className="text-fg-muted w-24">{line.offset}</span>
          <span className="text-fg-primary w-[360px]">{line.hex}</span>
          <span className="text-fg-muted">{line.ascii}</span>
        </div>,
      );
    }
  }

  return (
    <div className="border border-border rounded p-3 mt-3">
      {/* Toolbar */}
      <div className="flex items-center gap-2 mb-2 flex-wrap">
        <h3 className="text-sm font-medium">{t("hex.title")}</h3>
        <span className="text-xs text-fg-muted">
          {fileSize > 0 && `${fileSize.toLocaleString()} bytes`}
        </span>
        <div className="flex-1" />

        {/* Search */}
        <div className="flex items-center gap-1">
          <Search size={12} className="text-fg-muted" />
          <input
            type="text"
            value={searchPattern}
            onChange={(e) => setSearchPattern(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            placeholder={t("hex.searchPlaceholder")}
            className="input py-0.5 px-2 text-xs"
            style={{ width: "160px" }}
          />
          <button
            onClick={handleSearch}
            disabled={searching || !searchPattern.trim()}
            className="px-2 py-0.5 text-xs border border-border rounded disabled:opacity-50"
          >
            {searching ? "..." : t("hex.search")}
          </button>
        </div>

        {/* Jump */}
        <div className="flex items-center gap-1">
          <ArrowRight size={12} className="text-fg-muted" />
          <input
            type="text"
            value={jumpOffset}
            onChange={(e) => setJumpOffset(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleJump()}
            placeholder="0x00000000"
            className="input py-0.5 px-2 text-xs"
            style={{ width: "100px" }}
          />
          <button
            onClick={handleJump}
            className="px-2 py-0.5 text-xs border border-border rounded"
          >
            {t("hex.jump")}
          </button>
        </div>

        {/* Copy indicator */}
        {copied && (
          <span className="text-xs text-green-500 flex items-center gap-1">
            <Check size={12} /> {t("hex.copied")}
          </span>
        )}
      </div>

      {/* Search results */}
      {searchResults && (
        <div className="mb-2 text-xs text-fg-muted">
          {searchResults.length > 0 ? (
            <span>
              {searchResults.length} {t("hex.hits")}{" "}
              <select
                className="input py-0 px-1 ml-1"
                onChange={(e) => {
                  if (e.target.value) jumpToHit(parseInt(e.target.value, 10));
                }}
                defaultValue=""
              >
                <option value="">{t("hex.jumpToHit")}</option>
                {searchResults.slice(0, 50).map((h, i) => (
                  <option key={i} value={h.offset}>
                    0x{h.offset.toString(16).toUpperCase()}
                  </option>
                ))}
              </select>
            </span>
          ) : (
            <span>{t("hex.noHits")}</span>
          )}
        </div>
      )}

      {error && <div className="text-xs text-red-600 mb-2">{error}</div>}
      {loading && <div className="text-xs text-fg-muted mb-2">{t("hex.loading")}</div>}

      {/* Virtual scroll hex dump */}
      <div
        className="mono text-xs bg-muted/30 rounded overflow-y-auto"
        style={{ height: VISIBLE_LINES * LINE_HEIGHT + 20, overflowY: "auto" }}
        onScroll={(e) => setScrollTop((e.target as HTMLDivElement).scrollTop)}
      >
        {/* Spacer for virtual scrolling */}
        <div style={{ height: visibleStart * LINE_HEIGHT }} />
        {renderedLines}
        <div style={{ height: (totalLines - visibleEnd) * LINE_HEIGHT }} />
      </div>

      {/* Status bar */}
      <div className="flex items-center gap-3 mt-1 text-xs text-fg-muted">
        <span>
          {t("hex.offset")}: 0x{Math.floor(scrollTop / LINE_HEIGHT * LINE_BYTES).toString(16).toUpperCase()}
        </span>
        <Copy size={10} />
        <span>{t("hex.clickToCopy")}</span>
      </div>
    </div>
  );
}
