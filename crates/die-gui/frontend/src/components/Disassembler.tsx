import { useState } from "react";
import { useTranslation } from "react-i18next";
import { invoke } from "@tauri-apps/api/core";

interface Instruction {
  address: string;
  bytes: string;
  mnemonic: string;
}

interface DisassemblyResult {
  start_address: number;
  instruction_count: number;
  instructions: Instruction[];
}

type Syntax = "intel" | "gas" | "nasm";

export function Disassembler({ path }: { path: string }) {
  const { t } = useTranslation();
  const [result, setResult] = useState<DisassemblyResult | null>(null);
  const [offset, setOffset] = useState(0);
  const [bitness, setBitness] = useState(64);
  const [syntax, setSyntax] = useState<Syntax>("intel");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function disasm() {
    if (!path) return;
    setLoading(true);
    setError(null);
    try {
      const res = await invoke<DisassemblyResult>("disassemble", {
        path,
        offset,
        maxBytes: 256,
        bitness,
        syntax,
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
      <div className="flex items-center gap-2 mb-2">
        <h3 className="text-sm font-medium">{t("disasm.title")}</h3>
        <div className="flex-1" />
        <select
          value={bitness}
          onChange={(e) => setBitness(Number(e.target.value))}
          className="text-xs border border-border rounded px-1 py-0.5"
        >
          <option value={16}>16-bit</option>
          <option value={32}>32-bit</option>
          <option value={64}>64-bit</option>
        </select>
        <select
          value={syntax}
          onChange={(e) => setSyntax(e.target.value as Syntax)}
          className="text-xs border border-border rounded px-1 py-0.5"
        >
          <option value="intel">{t("disasm.intel")}</option>
          <option value="gas">{t("disasm.gas")}</option>
          <option value="nasm">{t("disasm.nasm")}</option>
        </select>
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
      {result && (
        <pre className="text-xs font-mono bg-muted p-2 rounded overflow-x-auto max-h-64 overflow-y-auto">
          {result.instructions.map((instr, i) => (
            <div key={i} className="flex gap-2">
              <span className="text-muted-foreground">{instr.address}</span>
              <span className="text-blue-600">{instr.bytes}</span>
              <span>{instr.mnemonic}</span>
            </div>
          ))}
        </pre>
      )}
    </div>
  );
}
