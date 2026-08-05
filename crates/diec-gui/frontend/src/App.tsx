import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { open as openDialog } from "@tauri-apps/plugin-dialog";

interface ScanDetectionDto {
  file_type: string;
  type_name: string;
  name: string;
  version: string | null;
  options: string | null;
}

interface ScanResultDto {
  path: string;
  detections: ScanDetectionDto[];
  diagnostics: string[];
  scan_time_ms: number;
}

interface GuiError {
  code: string;
  message: string;
}

interface ScanFlagsDto {
  recursive: boolean;
  deep: boolean;
  heuristic: boolean;
  verbose: boolean;
  aggressive: boolean;
  alltypes: boolean;
  overlay: boolean;
  resources: boolean;
  archives: boolean;
  first_wrapper_only: boolean;
  hide_unknown: boolean;
}

const defaultFlags: ScanFlagsDto = {
  recursive: true,
  deep: false,
  heuristic: false,
  verbose: false,
  aggressive: false,
  alltypes: false,
  overlay: true,
  resources: true,
  archives: true,
  first_wrapper_only: false,
  hide_unknown: false,
};

export default function App() {
  const [filePath, setFilePath] = useState<string>("");
  const [result, setResult] = useState<ScanResultDto | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [scanning, setScanning] = useState(false);

  async function pickFile() {
    try {
      const selected = await openDialog({ multiple: false });
      if (typeof selected === "string") {
        setFilePath(selected);
        setResult(null);
        setError(null);
      }
    } catch (e) {
      setError(String(e));
    }
  }

  async function scan() {
    if (!filePath) return;
    setScanning(true);
    setError(null);
    setResult(null);
    try {
      const res = await invoke<ScanResultDto>("scan_file", {
        path: filePath,
        flags: defaultFlags,
      });
      setResult(res);
    } catch (e) {
      const err = e as GuiError;
      setError(err.message ?? String(e));
    } finally {
      setScanning(false);
    }
  }

  return (
    <div className="min-h-screen bg-background text-foreground p-4">
      <header className="flex items-center gap-3 mb-4">
        <h1 className="text-xl font-semibold">diec-gui</h1>
        <span className="text-sm text-muted-foreground">Detect It Easy</span>
      </header>

      <section className="flex items-center gap-2 mb-4">
        <input
          type="text"
          value={filePath}
          onChange={(e) => setFilePath(e.target.value)}
          placeholder="Select a file to scan..."
          className="flex-1 px-3 py-1.5 border border-border rounded bg-background text-sm"
        />
        <button
          onClick={pickFile}
          className="px-3 py-1.5 text-sm border border-border rounded hover:bg-muted"
        >
          Browse
        </button>
        <button
          onClick={scan}
          disabled={!filePath || scanning}
          className="px-4 py-1.5 text-sm bg-primary text-background rounded disabled:opacity-50"
        >
          {scanning ? "Scanning..." : "Scan"}
        </button>
      </section>

      {error && (
        <div className="mb-4 p-3 border border-red-500 text-red-600 rounded text-sm">
          {error}
        </div>
      )}

      {result && (
        <section className="border border-border rounded p-4">
          <div className="flex justify-between mb-3">
            <h2 className="font-medium">{result.path}</h2>
            <span className="text-xs text-muted-foreground">
              {result.scan_time_ms} ms
            </span>
          </div>
          {result.detections.length === 0 ? (
            <p className="text-sm text-muted-foreground">No detections.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted-foreground border-b border-border">
                  <th className="py-1">Type</th>
                  <th className="py-1">Name</th>
                  <th className="py-1">Version</th>
                  <th className="py-1">Options</th>
                </tr>
              </thead>
              <tbody>
                {result.detections.map((d, i) => (
                  <tr key={i} className="border-b border-border">
                    <td className="py-1">{d.type_name}</td>
                    <td className="py-1">{d.name}</td>
                    <td className="py-1">{d.version ?? "-"}</td>
                    <td className="py-1">{d.options ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {result.diagnostics.length > 0 && (
            <details className="mt-3 text-xs">
              <summary className="cursor-pointer text-muted-foreground">
                Diagnostics ({result.diagnostics.length})
              </summary>
              <pre className="mt-2 p-2 bg-muted rounded overflow-x-auto">
                {result.diagnostics.join("\n")}
              </pre>
            </details>
          )}
        </section>
      )}
    </div>
  );
}
