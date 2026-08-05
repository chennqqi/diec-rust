import { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";

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

export function HexViewer({ path }: { path: string }) {
  const [dump, setDump] = useState<HexDump | null>(null);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pageSize = 4096;

  useEffect(() => {
    if (!path) return;
    setOffset(0);
  }, [path]);

  async function loadHex(off: number) {
    if (!path) return;
    setLoading(true);
    setError(null);
    try {
      const result = await invoke<HexDump>("read_hex", {
        path,
        offset: off,
        maxBytes: pageSize,
      });
      setDump(result);
      setOffset(off);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (path) loadHex(0);
  }, [path]);

  if (!path) return null;

  return (
    <div className="border border-border rounded p-3 mt-3">
      <div className="flex items-center gap-2 mb-2">
        <h3 className="text-sm font-medium">Hex Viewer</h3>
        <span className="text-xs text-muted-foreground">
          {dump && `${dump.file_size} bytes`}
        </span>
        <div className="flex-1" />
        <button
          onClick={() => loadHex(Math.max(0, offset - pageSize))}
          disabled={offset === 0 || loading}
          className="px-2 py-0.5 text-xs border border-border rounded disabled:opacity-50"
        >
          Prev
        </button>
        <span className="text-xs text-muted-foreground">
          {`0x${offset.toString(16).toUpperCase()}`}
        </span>
        <button
          onClick={() => loadHex(offset + pageSize)}
          disabled={!dump || offset + pageSize >= dump.file_size || loading}
          className="px-2 py-0.5 text-xs border border-border rounded disabled:opacity-50"
        >
          Next
        </button>
      </div>
      {error && <div className="text-xs text-red-600 mb-2">{error}</div>}
      {dump && (
        <pre className="text-xs font-mono bg-muted p-2 rounded overflow-x-auto max-h-64 overflow-y-auto">
          {dump.lines.map((line, i) => (
            <div key={i} className="flex gap-2">
              <span className="text-muted-foreground">{line.offset}</span>
              <span>{line.hex}</span>
              <span className="text-muted-foreground">{line.ascii}</span>
            </div>
          ))}
        </pre>
      )}
    </div>
  );
}
