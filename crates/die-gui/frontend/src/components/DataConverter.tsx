import { useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Repeat, Copy, CheckCircle2 } from "lucide-react";

/** Data converter — convert between hex, decimal, binary, octal, base64, ASCII.
 *  Mirrors upstream XDataConverter widget. */
export function DataConverter() {
  const { t } = useTranslation();
  const [input, setInput] = useState("48656C6C6F");
  const [inputFormat, setInputFormat] = useState<"hex" | "dec" | "bin" | "oct" | "base64" | "ascii">("hex");
  const [copiedField, setCopiedField] = useState<string | null>(null);

  // Decode input to raw bytes based on inputFormat.
  const rawBytes = useMemo((): Uint8Array => {
    try {
      switch (inputFormat) {
        case "hex": {
          const cleaned = input.replace(/0x/gi, "").replace(/\s+/g, "");
          if (cleaned.length % 2 !== 0) return new Uint8Array();
          const arr = new Uint8Array(cleaned.length / 2);
          for (let i = 0; i < cleaned.length; i += 2) {
            const byte = parseInt(cleaned.substr(i, 2), 16);
            if (isNaN(byte)) return new Uint8Array();
            arr[i / 2] = byte;
          }
          return arr;
        }
        case "dec": {
          // Interpret as a single decimal number → bytes (big-endian).
          const num = BigInt(input.trim());
          if (num < 0n) return new Uint8Array();
          const hex = num.toString(16);
          const padded = hex.length % 2 === 0 ? hex : "0" + hex;
          const arr = new Uint8Array(padded.length / 2);
          for (let i = 0; i < padded.length; i += 2) {
            arr[i / 2] = parseInt(padded.substr(i, 2), 16);
          }
          return arr;
        }
        case "bin": {
          // Interpret as a binary string (space-separated bits).
          const bits = input.replace(/\s+/g, "");
          if (bits.length % 8 !== 0 || !/^[01]+$/.test(bits)) return new Uint8Array();
          const arr = new Uint8Array(bits.length / 8);
          for (let i = 0; i < bits.length; i += 8) {
            arr[i / 8] = parseInt(bits.substr(i, 8), 2);
          }
          return arr;
        }
        case "oct": {
          const num = BigInt(input.trim());
          if (num < 0n) return new Uint8Array();
          const hex = num.toString(16);
          const padded = hex.length % 2 === 0 ? hex : "0" + hex;
          const arr = new Uint8Array(padded.length / 2);
          for (let i = 0; i < padded.length; i += 2) {
            arr[i / 2] = parseInt(padded.substr(i, 2), 16);
          }
          return arr;
        }
        case "base64": {
          const decoded = atob(input.trim());
          return Uint8Array.from(decoded, (c) => c.charCodeAt(0));
        }
        case "ascii": {
          return Uint8Array.from(input, (c) => c.charCodeAt(0));
        }
      }
    } catch {
      return new Uint8Array();
    }
  }, [input, inputFormat]);

  // Encode raw bytes to all formats.
  const conversions = useMemo(() => {
    const bytes = Array.from(rawBytes);
    if (bytes.length === 0) {
      return { hex: "", dec: "", bin: "", oct: "", base64: "", ascii: "", valid: false };
    }

    // Hex.
    const hex = bytes.map((b) => b.toString(16).padStart(2, "0").toUpperCase()).join(" ");

    // Decimal (as big-endian number).
    let dec = "0";
    try {
      let big = 0n;
      for (const b of bytes) {
        big = (big << 8n) | BigInt(b);
      }
      dec = big.toString();
    } catch { /* ignore */ }

    // Binary.
    const bin = bytes.map((b) => b.toString(2).padStart(8, "0")).join(" ");

    // Octal.
    let oct = "0";
    try {
      let big = 0n;
      for (const b of bytes) {
        big = (big << 8n) | BigInt(b);
      }
      oct = big.toString(8);
    } catch { /* ignore */ }

    // Base64.
    let base64 = "";
    try {
      base64 = btoa(String.fromCharCode(...bytes));
    } catch { /* ignore */ }

    // ASCII (printable chars, dots for non-printable).
    const ascii = bytes
      .map((b) => (b >= 32 && b <= 126) ? String.fromCharCode(b) : ".")
      .join("");

    return { hex, dec, bin, oct, base64, ascii, valid: true };
  }, [rawBytes]);

  const copy = (text: string, field: string) => {
    navigator.clipboard.writeText(text);
    setCopiedField(field);
    setTimeout(() => setCopiedField(null), 1500);
  };

  const formatLabels: { id: typeof inputFormat; label: string }[] = [
    { id: "hex", label: "Hex" },
    { id: "dec", label: "Decimal" },
    { id: "bin", label: "Binary" },
    { id: "oct", label: "Octal" },
    { id: "base64", label: "Base64" },
    { id: "ascii", label: "ASCII" },
  ];

  const outputFields = [
    { id: "hex", label: "Hex", value: conversions.hex },
    { id: "dec", label: "Decimal", value: conversions.dec },
    { id: "bin", label: "Binary", value: conversions.bin },
    { id: "oct", label: "Octal", value: conversions.oct },
    { id: "base64", label: "Base64", value: conversions.base64 },
    { id: "ascii", label: "ASCII", value: conversions.ascii },
  ];

  return (
    <div className="p-3 overflow-auto h-full">
      <div className="flex items-center gap-2 mb-3">
        <Repeat size={16} className="text-accent-blue" />
        <h3 className="text-sm font-medium">{t("converter.title")}</h3>
      </div>

      {/* Input section */}
      <div className="mb-4">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs text-fg-muted">{t("converter.inputFormat")}</span>
          <select
            className="input py-0.5 px-1.5 text-xs"
            value={inputFormat}
            onChange={(e) => setInputFormat(e.target.value as typeof inputFormat)}
            style={{ width: "100px" }}
          >
            {formatLabels.map((f) => (
              <option key={f.id} value={f.id}>{f.label}</option>
            ))}
          </select>
          {!conversions.valid && input && (
            <span className="text-xs text-accent-red">{t("converter.invalid")}</span>
          )}
        </div>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          className="input w-full p-2 mono text-xs resize-none"
          rows={3}
          placeholder={`Enter ${inputFormat} data...`}
          spellCheck={false}
        />
      </div>

      {/* Output conversions */}
      <div className="space-y-2">
        <div className="text-xs font-medium text-fg-secondary mb-1">{t("converter.output")}</div>
        {outputFields.map((field) => (
          <div key={field.id} className="flex items-start gap-2">
            <div className="w-16 text-xs text-fg-muted pt-1 flex-shrink-0">{field.label}</div>
            <div className="flex-1 relative">
              <input
                type="text"
                readOnly
                value={field.value}
                className="input w-full pr-8 py-1 mono text-xs selectable"
              />
              <button
                onClick={() => copy(field.value, field.id)}
                className="absolute right-1 top-1/2 -translate-y-1/2 p-0.5 hover:text-accent-blue"
                title={`Copy ${field.label}`}
              >
                {copiedField === field.id ? (
                  <CheckCircle2 size={12} className="text-accent-green" />
                ) : (
                  <Copy size={12} className="text-fg-muted" />
                )}
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Byte info */}
      {conversions.valid && (
        <div className="mt-4 pt-2 border-t border-border-c text-xs text-fg-muted">
          {rawBytes.length} {t("converter.bytes")} ({(rawBytes.length / 1024).toFixed(2)} KB)
        </div>
      )}
    </div>
  );
}
