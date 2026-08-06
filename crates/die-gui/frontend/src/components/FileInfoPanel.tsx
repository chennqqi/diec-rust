import { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import {
  FileText,
  Hash,
  Layers,
  Code2,
  Activity,
  Copy,
  Check,
} from "lucide-react";

interface FileHashes {
  md5: string;
  sha1: string;
  sha256: string;
}

interface SectionInfo {
  name: string;
  virtual_address: number;
  virtual_size: number;
  raw_offset: number;
  raw_size: number;
  entropy: number;
}

interface SymbolInfo {
  name: string;
  address: number;
  size: number;
  kind: string;
}

interface FileInfo {
  path: string;
  file_name: string;
  size: number;
  size_human: string;
  entropy: number;
  hashes: FileHashes;
  format: string;
  sections: SectionInfo[];
  symbols: SymbolInfo[];
}

type SubTab = "info" | "sections" | "symbols" | "entropy";

export function FileInfoPanel({ path }: { path: string }) {
  const [info, setInfo] = useState<FileInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [subTab, setSubTab] = useState<SubTab>("info");
  const [copied, setCopied] = useState<string | null>(null);

  useEffect(() => {
    if (!path) return;
    setLoading(true);
    setError(null);
    invoke<FileInfo>("get_file_info", { path })
      .then(setInfo)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [path]);

  const copyHash = (hash: string, label: string) => {
    navigator.clipboard.writeText(hash);
    setCopied(label);
    setTimeout(() => setCopied(null), 1500);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-fg-secondary text-xs">
        <div className="w-4 h-4 border-2 border-accent-blue border-t-transparent rounded-full animate-spin mr-2" />
        Analyzing file...
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-3 text-xs text-accent-red selectable">{error}</div>
    );
  }

  if (!info) {
    return (
      <div className="flex items-center justify-center h-full text-fg-muted text-xs">
        No file loaded
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Sub-tab bar */}
      <div
        className="flex items-center gap-0 px-1 border-b border-border-c"
        style={{ background: "rgb(var(--bg-panel))" }}
      >
        <SubTabButton active={subTab === "info"} onClick={() => setSubTab("info")} icon={FileText} label="Info" />
        <SubTabButton active={subTab === "sections"} onClick={() => setSubTab("sections")} icon={Layers} label={`Sections (${info.sections.length})`} />
        <SubTabButton active={subTab === "symbols"} onClick={() => setSubTab("symbols")} icon={Code2} label={`Symbols (${info.symbols.length})`} />
        <SubTabButton active={subTab === "entropy"} onClick={() => setSubTab("entropy")} icon={Activity} label="Entropy" />
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-3 selectable">
        {subTab === "info" && (
          <div className="space-y-3 text-xs">
            <InfoRow label="File" value={info.file_name} />
            <InfoRow label="Path" value={info.path} mono />
            <InfoRow label="Size" value={`${info.size_human} (${info.size.toLocaleString()} bytes)`} />
            <InfoRow label="Format" value={info.format} />
            <InfoRow
              label="Entropy"
              value={`${info.entropy.toFixed(4)} ${entropyLabel(info.entropy)}`}
            />

            <div className="pt-2 border-t border-border-c">
              <div className="flex items-center gap-1.5 mb-2 text-fg-secondary">
                <Hash size={13} />
                <span className="font-medium">Hashes</span>
              </div>
              <HashRow
                label="MD5"
                value={info.hashes.md5}
                copied={copied === "md5"}
                onCopy={() => copyHash(info.hashes.md5, "md5")}
              />
              <HashRow
                label="SHA-1"
                value={info.hashes.sha1}
                copied={copied === "sha1"}
                onCopy={() => copyHash(info.hashes.sha1, "sha1")}
              />
              <HashRow
                label="SHA-256"
                value={info.hashes.sha256}
                copied={copied === "sha256"}
                onCopy={() => copyHash(info.hashes.sha256, "sha256")}
              />
            </div>
          </div>
        )}

        {subTab === "sections" && (
          <div className="text-xs">
            {info.sections.length === 0 ? (
              <p className="text-fg-muted">No sections (not a recognized binary format).</p>
            ) : (
              <table className="w-full mono">
                <thead>
                  <tr className="text-left text-fg-secondary border-b border-border-c">
                    <th className="py-1 pr-3">Name</th>
                    <th className="py-1 pr-3">VAddr</th>
                    <th className="py-1 pr-3">VSize</th>
                    <th className="py-1 pr-3">Raw Off</th>
                    <th className="py-1 pr-3">Raw Size</th>
                    <th className="py-1">Entropy</th>
                  </tr>
                </thead>
                <tbody>
                  {info.sections.map((s, i) => (
                    <tr key={i} className="border-b border-border-c hover:bg-hover">
                      <td className="py-0.5 pr-3 text-accent-blue">{s.name}</td>
                      <td className="py-0.5 pr-3 text-fg-secondary">0x{s.virtual_address.toString(16).padStart(8, "0")}</td>
                      <td className="py-0.5 pr-3 text-fg-secondary">0x{s.virtual_size.toString(16)}</td>
                      <td className="py-0.5 pr-3 text-fg-muted">0x{s.raw_offset.toString(16)}</td>
                      <td className="py-0.5 pr-3 text-fg-muted">0x{s.raw_size.toString(16)}</td>
                      <td className="py-0.5">
                        <span className={entropyColor(s.entropy)}>
                          {s.entropy.toFixed(3)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {subTab === "symbols" && (
          <div className="text-xs">
            {info.symbols.length === 0 ? (
              <p className="text-fg-muted">No symbols (stripped or not a recognized binary format).</p>
            ) : (
              <table className="w-full mono">
                <thead>
                  <tr className="text-left text-fg-secondary border-b border-border-c">
                    <th className="py-1 pr-3">Address</th>
                    <th className="py-1 pr-3">Kind</th>
                    <th className="py-1 pr-3">Size</th>
                    <th className="py-1">Name</th>
                  </tr>
                </thead>
                <tbody>
                  {info.symbols.slice(0, 500).map((s, i) => (
                    <tr key={i} className="border-b border-border-c hover:bg-hover">
                      <td className="py-0.5 pr-3 text-fg-muted">0x{s.address.toString(16).padStart(8, "0")}</td>
                      <td className="py-0.5 pr-3 text-fg-secondary">{s.kind}</td>
                      <td className="py-0.5 pr-3 text-fg-muted">{s.size > 0 ? `0x${s.size.toString(16)}` : "-"}</td>
                      <td className="py-0.5 text-fg-primary">{s.name}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {info.symbols.length > 500 && (
              <p className="mt-2 text-fg-muted">
                Showing first 500 of {info.symbols.length} symbols.
              </p>
            )}
          </div>
        )}

        {subTab === "entropy" && (
          <EntropyView path={path} overall={info.entropy} />
        )}
      </div>
    </div>
  );
}

function SubTabButton({
  active,
  onClick,
  icon: Icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: typeof FileText;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 px-3 py-1.5 text-xs ${
        active ? "tab-active" : "tab-inactive"
      }`}
    >
      <Icon size={13} />
      {label}
    </button>
  );
}

function InfoRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex gap-3">
      <span className="text-fg-secondary w-20 flex-shrink-0">{label}</span>
      <span className={`text-fg-primary ${mono ? "mono" : ""} break-all`}>{value}</span>
    </div>
  );
}

function HashRow({
  label,
  value,
  copied,
  onCopy,
}: {
  label: string;
  value: string;
  copied: boolean;
  onCopy: () => void;
}) {
  return (
    <div className="flex items-center gap-2 py-0.5 group">
      <span className="text-fg-secondary w-16 flex-shrink-0">{label}</span>
      <span className="mono text-fg-primary flex-1 break-all">{value}</span>
      <button
        onClick={onCopy}
        className="opacity-0 group-hover:opacity-100 transition-opacity p-1 hover:bg-hover rounded"
        title="Copy"
      >
        {copied ? <Check size={12} className="text-accent-green" /> : <Copy size={12} />}
      </button>
    </div>
  );
}

function entropyLabel(e: number): string {
  if (e < 1) return "(very low — likely text/data)";
  if (e < 4) return "(low — structured data)";
  if (e < 6) return "(medium — mixed content)";
  if (e < 7.5) return "(high — possibly compressed/encrypted)";
  return "(very high — likely encrypted/compressed)";
}

function entropyColor(e: number): string {
  if (e < 4) return "text-accent-green";
  if (e < 6) return "text-accent-yellow";
  return "text-accent-red";
}

/** Entropy graph view — renders a simple bar chart of block-level entropy. */
function EntropyView({ path, overall }: { path: string; overall: number }) {
  const [graph, setGraph] = useState<{ blocks: number[]; block_size: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    invoke<{ blocks: number[]; block_size: number; overall: number }>(
      "get_entropy_graph",
      { path, blockSize: 256 }
    )
      .then(setGraph)
      .catch((e) => setError(String(e)));
  }, [path]);

  if (error) return <p className="text-accent-red text-xs">{error}</p>;
  if (!graph) return <p className="text-fg-muted text-xs">Computing entropy graph...</p>;

  const maxBlocks = 200;
  const displayBlocks =
    graph.blocks.length > maxBlocks
      ? graph.blocks.filter((_, i) => i % Math.ceil(graph.blocks.length / maxBlocks) === 0)
      : graph.blocks;

  return (
    <div className="text-xs">
      <div className="mb-3">
        <div className="flex justify-between mb-1">
          <span className="text-fg-secondary">Overall entropy: <span className={entropyColor(overall)}>{overall.toFixed(4)}</span></span>
          <span className="text-fg-muted">{graph.blocks.length} blocks × {graph.block_size} bytes</span>
        </div>
      </div>
      {/* Simple bar chart */}
      <div className="flex items-end gap-px h-32 bg-input rounded p-1">
        {displayBlocks.map((e, i) => (
          <div
            key={i}
            className="flex-1 rounded-t"
            style={{
              height: `${(e / 8) * 100}%`,
              background: e < 4
                ? "rgb(var(--accent-green))"
                : e < 6
                ? "rgb(var(--accent-yellow))"
                : "rgb(var(--accent-red))",
              minHeight: "1px",
            }}
            title={`Block ${i}: ${e.toFixed(3)}`}
          />
        ))}
      </div>
      <div className="flex justify-between mt-1 text-fg-muted">
        <span>0</span>
        <span>{graph.blocks.length}</span>
      </div>
      <div className="mt-3 flex gap-4 text-fg-secondary">
        <span className="flex items-center gap-1">
          <div className="w-3 h-3 rounded" style={{ background: "rgb(var(--accent-green))" }} />
          &lt; 4.0 (low)
        </span>
        <span className="flex items-center gap-1">
          <div className="w-3 h-3 rounded" style={{ background: "rgb(var(--accent-yellow))" }} />
          4.0–6.0 (medium)
        </span>
        <span className="flex items-center gap-1">
          <div className="w-3 h-3 rounded" style={{ background: "rgb(var(--accent-red))" }} />
          &gt; 6.0 (high)
        </span>
      </div>
    </div>
  );
}
