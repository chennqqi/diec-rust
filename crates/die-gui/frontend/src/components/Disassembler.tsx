import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { invoke } from "@tauri-apps/api/core";

interface Instruction {
  address: string;
  bytes: string;
  mnemonic: string;
  label: string | null;
  comment: string | null;
  jump_target: string | null;
}

interface DisassemblyResult {
  start_address: number;
  instruction_count: number;
  instructions: Instruction[];
}

type Syntax = "intel" | "gas" | "nasm";
type Arch = "x86" | "x64" | "arm" | "arm64";

export function Disassembler({
  path,
  initialOffset,
}: {
  path: string;
  initialOffset?: number | null;
}) {
  const { t } = useTranslation();
  const [result, setResult] = useState<DisassemblyResult | null>(null);
  const [offset, setOffset] = useState(initialOffset ?? 0);
  const [arch, setArch] = useState<Arch>("x64");
  const [maxBytes, setMaxBytes] = useState(4096);
  const [syntax, setSyntax] = useState<Syntax>("intel");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // When initialOffset changes (e.g. from HexViewer "Follow in Disasm"),
  // update offset and auto-disassemble.
  useEffect(() => {
    if (initialOffset != null && initialOffset !== offset) {
      setOffset(initialOffset);
    }
  }, [initialOffset]);

  async function disasm() {
    if (!path) return;
    setLoading(true);
    setError(null);
    try {
      const res = await invoke<DisassemblyResult>("disassemble", {
        path,
        offset,
        maxBytes,
        syntax,
        arch,
      });
      setResult(res);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  if (!path) return null;

  return (
    <div className="border border-border rounded p-3 mt-3">
      {/* Toolbar */}
      <div className="flex items-center gap-2 mb-2 flex-wrap">
        <h3 className="text-sm font-medium">{t("disasm.title")}</h3>
        <div className="flex-1" />

        {/* Architecture selector */}
        <span className="text-xs text-fg-muted">{t("disasm.arch")}</span>
        <select
          value={arch}
          onChange={(e) => setArch(e.target.value as Arch)}
          className="text-xs border border-border rounded px-1 py-0.5"
        >
          <option value="x86">x86</option>
          <option value="x64">x86-64</option>
          <option value="arm">ARM</option>
          <option value="arm64">ARM64</option>
        </select>

        {/* Syntax selector (x86/x64 only) */}
        {(arch === "x86" || arch === "x64") && (
          <select
            value={syntax}
            onChange={(e) => setSyntax(e.target.value as Syntax)}
            className="text-xs border border-border rounded px-1 py-0.5"
          >
            <option value="intel">{t("disasm.intel")}</option>
            <option value="gas">{t("disasm.gas")}</option>
            <option value="nasm">{t("disasm.nasm")}</option>
          </select>
        )}

        {/* Max bytes */}
        <select
          value={maxBytes}
          onChange={(e) => setMaxBytes(Number(e.target.value))}
          className="text-xs border border-border rounded px-1 py-0.5"
        >
          <option value={256}>256B</option>
          <option value={1024}>1KB</option>
          <option value={4096}>4KB</option>
          <option value={16384}>16KB</option>
          <option value={65536}>64KB</option>
        </select>

        {/* Offset input */}
        <input
          type="text"
          value={offset.toString(16)}
          onChange={(e) => setOffset(parseInt(e.target.value, 16) || 0)}
          placeholder="0x0"
          className="w-20 text-xs border border-border rounded px-1 py-0.5 font-mono"
        />

        <button
          onClick={disasm}
          disabled={loading}
          className="px-2 py-0.5 text-xs bg-primary text-background rounded disabled:opacity-50"
        >
          {t("disasm.disassemble")}
        </button>
      </div>

      {error && <div className="text-xs text-red-600 mb-2">{error}</div>}

      {/* Instruction count */}
      {result && (
        <div className="text-xs text-fg-muted mb-1">
          {result.instruction_count} {t("disasm.instructions")}
        </div>
      )}

      {/* Disassembly listing with label, address, bytes, mnemonic, comment columns */}
      {result && (
        <div
          className="mono text-xs bg-muted/30 rounded overflow-y-auto"
          style={{ maxHeight: "320px", overflowY: "auto" }}
        >
          {/* Header */}
          <div className="flex gap-2 px-2 py-1 border-b border-border-c text-fg-secondary font-medium sticky top-0 bg-muted/80">
            <span className="w-24">{t("disasm.label")}</span>
            <span className="w-32">{t("disasm.address")}</span>
            <span className="w-48">{t("disasm.bytes")}</span>
            <span className="flex-1">{t("disasm.mnemonic")}</span>
            <span className="w-40">{t("disasm.comment")}</span>
          </div>

          {/* Instructions */}
          {result.instructions.map((instr, i) => (
            <div
              key={i}
              className={`flex gap-2 px-2 hover:bg-accent-blue/10 ${instr.label ? "border-t border-border-c/30" : ""}`}
              style={{ lineHeight: "18px" }}
            >
              <span className="w-24 text-orange-400 truncate">
                {instr.label ?? ""}
              </span>
              <span className="w-32 text-fg-muted">{instr.address}</span>
              <span className="w-48 text-blue-400 truncate">{instr.bytes}</span>
              <span className="flex-1 text-fg-primary">{instr.mnemonic}</span>
              <span className="w-40 text-fg-muted truncate">
                {instr.comment ?? ""}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
