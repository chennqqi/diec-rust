import { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import { Map, AlertCircle } from "lucide-react";

interface SectionInfo {
  name: string;
  virtual_address: number;
  virtual_size: number;
  raw_offset: number;
  raw_size: number;
  entropy: number;
}

interface FileInfo {
  path: string;
  file_name: string;
  size: number;
  size_human: string;
  entropy: number;
  format: string;
  sections: SectionInfo[];
}

/** Memory map viewer — displays section virtual address layout.
 *  Mirrors upstream XMemoryMap widget showing PE/ELF/Mach-O sections
 *  as a visual memory map with address ranges. */
export function MemoryMapViewer({ filePath }: { filePath: string }) {
  const [info, setInfo] = useState<FileInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!filePath) {
      setInfo(null);
      return;
    }
    setLoading(true);
    setError(null);
    invoke<FileInfo>("get_file_info", { path: filePath })
      .then((res) => setInfo(res))
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [filePath]);

  if (!filePath) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-fg-muted">
        <Map size={48} className="mb-3 opacity-40" />
        <p className="text-sm">Open a file to view its memory map.</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-xs text-fg-secondary">
        <div className="w-3 h-3 border-2 border-accent-blue border-t-transparent rounded-full animate-spin mr-2" />
        Loading memory map...
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-2 p-3 text-xs text-accent-red">
        <AlertCircle size={14} />
        {error}
      </div>
    );
  }

  if (!info || info.sections.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-fg-muted">
        <Map size={48} className="mb-3 opacity-40" />
        <p className="text-sm">No sections found for {info?.file_name ?? "this file"}.</p>
        <p className="text-xs mt-1">Memory map is available for PE, ELF, and Mach-O binaries.</p>
      </div>
    );
  }

  // Calculate virtual address range for the memory map visualization.
  const sections = info.sections;
  const minAddr = Math.min(...sections.map((s) => s.virtual_address));
  const maxAddr = Math.max(...sections.map((s) => s.virtual_address + s.virtual_size));
  const totalRange = maxAddr - minAddr || 1;

  // Color palette for sections.
  const sectionColors = [
    "rgba(59, 130, 246, 0.7)",   // blue
    "rgba(34, 197, 94, 0.7)",    // green
    "rgba(168, 85, 247, 0.7)",   // purple
    "rgba(234, 179, 8, 0.7)",    // yellow
    "rgba(239, 68, 68, 0.7)",    // red
    "rgba(20, 184, 166, 0.7)",   // teal
    "rgba(249, 115, 22, 0.7)",   // orange
    "rgba(99, 102, 241, 0.7)",   // indigo
  ];

  const hex = (n: number) => "0x" + n.toString(16).toUpperCase().padStart(8, "0");

  return (
    <div className="p-3 overflow-auto h-full">
      <div className="flex items-center gap-2 mb-3">
        <Map size={16} className="text-accent-blue" />
        <h3 className="text-sm font-medium">Memory Map — {info.file_name}</h3>
        <span className="text-xs text-fg-muted">{info.format}</span>
      </div>

      {/* Visual memory map bar */}
      <div className="mb-4">
        <div className="text-xs text-fg-muted mb-1">Virtual Address Layout</div>
        <div
          className="relative h-12 rounded border border-border-c overflow-hidden"
          style={{ background: "rgb(var(--bg-panel))" }}
        >
          {sections.map((s, i) => {
            const left = ((s.virtual_address - minAddr) / totalRange) * 100;
            const width = (s.virtual_size / totalRange) * 100;
            return (
              <div
                key={i}
                className="absolute h-full flex items-center justify-center text-xs text-white overflow-hidden"
                style={{
                  left: `${left}%`,
                  width: `${Math.max(width, 0.5)}%`,
                  background: sectionColors[i % sectionColors.length],
                }}
                title={`${s.name}: ${hex(s.virtual_address)} - ${hex(s.virtual_address + s.virtual_size)}`}
              >
                {width > 5 && s.name}
              </div>
            );
          })}
        </div>
        <div className="flex justify-between text-xs text-fg-muted mt-1 mono">
          <span>{hex(minAddr)}</span>
          <span>{hex(maxAddr)}</span>
        </div>
      </div>

      {/* Section table */}
      <table className="w-full text-xs selectable">
        <thead>
          <tr className="text-fg-muted border-b border-border-c">
            <th className="text-left py-1 px-2">Name</th>
            <th className="text-right py-1 px-2">VAddr</th>
            <th className="text-right py-1 px-2">VSize</th>
            <th className="text-right py-1 px-2">Raw Off</th>
            <th className="text-right py-1 px-2">Raw Size</th>
            <th className="text-right py-1 px-2">Entropy</th>
          </tr>
        </thead>
        <tbody>
          {sections.map((s, i) => (
            <tr key={i} className="border-b border-border-c/50 hover:bg-hover">
              <td className="py-1 px-2 font-medium" style={{ color: sectionColors[i % sectionColors.length].replace("0.7", "1") }}>
                {s.name}
              </td>
              <td className="py-1 px-2 text-right mono text-fg-secondary">{hex(s.virtual_address)}</td>
              <td className="py-1 px-2 text-right mono text-fg-secondary">{hex(s.virtual_size)}</td>
              <td className="py-1 px-2 text-right mono text-fg-muted">{hex(s.raw_offset)}</td>
              <td className="py-1 px-2 text-right mono text-fg-muted">{hex(s.raw_size)}</td>
              <td className="py-1 px-2 text-right mono">
                <span className={
                  s.entropy > 7.5 ? "text-accent-red" :
                  s.entropy > 6.0 ? "text-accent-yellow" :
                  "text-fg-muted"
                }>
                  {s.entropy.toFixed(4)}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
