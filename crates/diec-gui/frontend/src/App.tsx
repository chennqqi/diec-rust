import { useState, useEffect, useRef } from "react";
import { invoke, Channel } from "@tauri-apps/api/core";
import { open as openDialog } from "@tauri-apps/plugin-dialog";
import { getCurrentWebview } from "@tauri-apps/api/webview";
import { HexViewer } from "./components/HexViewer";
import { Disassembler } from "./components/Disassembler";
import { DemangleTool } from "./components/DemangleTool";
import { SignatureBrowser } from "./components/SignatureBrowser";

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

interface AppSettings {
  view: { theme: string; language: string; stay_on_top: boolean; advanced: boolean };
  file: { last_directory: string; recent_files: string[]; save_backup: boolean };
  scan: {
    scan_after_open: boolean;
    hide_unknown: boolean;
    sort: boolean;
    log_profiling: boolean;
    flags: ScanFlagsDto;
  };
  database: {
    main_path: string;
    extra_path: string;
    custom_path: string;
    extra_enabled: boolean;
    custom_enabled: boolean;
  };
  engine: { die_enabled: boolean; nfd_enabled: boolean; peid_enabled: boolean; yara_enabled: boolean };
}

interface DirectoryScanProgress {
  event: string;
  data: { total_files?: number; index?: number; file_path?: string; result?: ScanResultDto; total?: number; message?: string };
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

const defaultSettings: AppSettings = {
  view: { theme: "system", language: "en", stay_on_top: false, advanced: false },
  file: { last_directory: "", recent_files: [], save_backup: true },
  scan: { scan_after_open: true, hide_unknown: false, sort: false, log_profiling: false, flags: defaultFlags },
  database: { main_path: "", extra_path: "", custom_path: "", extra_enabled: false, custom_enabled: false },
  engine: { die_enabled: true, nfd_enabled: false, peid_enabled: false, yara_enabled: false },
};

export default function App() {
  const [filePath, setFilePath] = useState<string>("");
  const [result, setResult] = useState<ScanResultDto | null>(null);
  const [dirResults, setDirResults] = useState<ScanResultDto[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [scanning, setScanning] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [settings, setSettings] = useState<AppSettings>(defaultSettings);
  const [flags, setFlags] = useState<ScanFlagsDto>(defaultFlags);
  const [dirProgress, setDirProgress] = useState<{ current: number; total: number } | null>(null);
  const [activeTab, setActiveTab] = useState<"scan" | "hex" | "disasm" | "demangle" | "sigs">("scan");
  const dragCounter = useRef(0);

  // Load settings on mount.
  useEffect(() => {
    invoke<AppSettings>("get_settings")
      .then((s) => {
        setSettings(s);
        setFlags(s.scan.flags);
      })
      .catch(() => {});
  }, []);

  // Register drag-drop event listener.
  useEffect(() => {
    const webview = getCurrentWebview();
    const unlisten = webview.onDragDropEvent((event: { payload: { type: string; paths?: string[] } }) => {
      if (event.payload.type === "over") {
        setDragOver(true);
      } else if (event.payload.type === "drop") {
        setDragOver(false);
        const paths = event.payload.paths;
        if (paths && paths.length > 0) {
          setFilePath(paths[0]);
          setResult(null);
          setDirResults([]);
          setError(null);
        }
      } else if (event.payload.type === "leave") {
        setDragOver(false);
      }
    });
    return () => {
      unlisten.then((fn: () => void) => fn());
    };
  }, []);

  // Also handle native HTML drag-over for visual feedback.
  useEffect(() => {
    const handleDragEnter = (e: DragEvent) => {
      e.preventDefault();
      dragCounter.current++;
      setDragOver(true);
    };
    const handleDragLeave = (e: DragEvent) => {
      e.preventDefault();
      dragCounter.current--;
      if (dragCounter.current === 0) setDragOver(false);
    };
    const handleDragOver = (e: DragEvent) => {
      e.preventDefault();
    };
    const handleDrop = (e: DragEvent) => {
      e.preventDefault();
      dragCounter.current = 0;
      setDragOver(false);
    };
    window.addEventListener("dragenter", handleDragEnter);
    window.addEventListener("dragleave", handleDragLeave);
    window.addEventListener("dragover", handleDragOver);
    window.addEventListener("drop", handleDrop);
    return () => {
      window.removeEventListener("dragenter", handleDragEnter);
      window.removeEventListener("dragleave", handleDragLeave);
      window.removeEventListener("dragover", handleDragOver);
      window.removeEventListener("drop", handleDrop);
    };
  }, []);

  async function pickFile() {
    try {
      const selected = await openDialog({ multiple: false });
      if (typeof selected === "string") {
        setFilePath(selected);
        setResult(null);
        setDirResults([]);
        setError(null);
      }
    } catch (e) {
      setError(String(e));
    }
  }

  async function pickDirectory() {
    try {
      const selected = await openDialog({ directory: true, multiple: false });
      if (typeof selected === "string") {
        setFilePath(selected);
        setResult(null);
        setDirResults([]);
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
    setDirResults([]);
    try {
      const res = await invoke<ScanResultDto>("scan_file", {
        path: filePath,
        flags,
      });
      setResult(res);
    } catch (e) {
      const err = e as GuiError;
      setError(err.message ?? String(e));
    } finally {
      setScanning(false);
    }
  }

  async function scanDirectory() {
    if (!filePath) return;
    setScanning(true);
    setError(null);
    setResult(null);
    setDirResults([]);
    setDirProgress({ current: 0, total: 0 });
    try {
      const channel = new Channel<DirectoryScanProgress>();
      channel.onmessage = (msg) => {
        if (msg.event === "started" && msg.data.total_files !== undefined) {
          setDirProgress({ current: 0, total: msg.data.total_files });
        } else if (msg.event === "file_scanned") {
          if (msg.data.result) {
            setDirResults((prev) => [...prev, msg.data.result!]);
          }
          setDirProgress({
            current: (msg.data.index ?? 0) + 1,
            total: dirProgress?.total ?? 0,
          });
        } else if (msg.event === "finished") {
          setDirProgress(null);
        } else if (msg.event === "error") {
          setError(msg.data.message ?? "Unknown error");
        }
      };
      const results = await invoke<ScanResultDto[]>("scan_directory", {
        dir: filePath,
        flags,
        subdirectories: flags.recursive,
        onProgress: channel,
      });
      setDirResults(results);
    } catch (e) {
      const err = e as GuiError;
      setError(err.message ?? String(e));
    } finally {
      setScanning(false);
      setDirProgress(null);
    }
  }

  async function stopScan() {
    try {
      await invoke("stop_scan");
    } catch (e) {
      setError(String(e));
    }
  }

  async function saveSettings() {
    const newSettings = { ...settings, scan: { ...settings.scan, flags } };
    setSettings(newSettings);
    try {
      await invoke("save_settings", { settings: newSettings });
      setShowSettings(false);
    } catch (e) {
      const err = e as GuiError;
      setError(err.message ?? String(e));
    }
  }

  return (
    <div
      className={`min-h-screen bg-background text-foreground p-4 ${dragOver ? "ring-2 ring-primary ring-inset" : ""}`}
    >
      <header className="flex items-center gap-3 mb-4">
        <h1 className="text-xl font-semibold">diec-gui</h1>
        <span className="text-sm text-muted-foreground">Detect It Easy</span>
        <div className="flex-1" />
        <button
          onClick={() => setShowSettings(!showSettings)}
          className="px-3 py-1 text-sm border border-border rounded hover:bg-muted"
        >
          Settings
        </button>
      </header>

      {dragOver && (
        <div className="mb-4 p-4 border-2 border-dashed border-primary rounded text-center text-sm text-muted-foreground">
          Drop file here to scan
        </div>
      )}

      <section className="flex items-center gap-2 mb-4">
        <input
          type="text"
          value={filePath}
          onChange={(e) => setFilePath(e.target.value)}
          placeholder="Select a file or directory to scan..."
          className="flex-1 px-3 py-1.5 border border-border rounded bg-background text-sm"
        />
        <button
          onClick={pickFile}
          className="px-3 py-1.5 text-sm border border-border rounded hover:bg-muted"
        >
          File
        </button>
        <button
          onClick={pickDirectory}
          className="px-3 py-1.5 text-sm border border-border rounded hover:bg-muted"
        >
          Dir
        </button>
        <button
          onClick={scan}
          disabled={!filePath || scanning}
          className="px-4 py-1.5 text-sm bg-primary text-background rounded disabled:opacity-50"
        >
          {scanning ? "Scanning..." : "Scan"}
        </button>
        <button
          onClick={scanDirectory}
          disabled={!filePath || scanning}
          className="px-3 py-1.5 text-sm border border-border rounded hover:bg-muted disabled:opacity-50"
        >
          Scan Dir
        </button>
        <button
          onClick={stopScan}
          disabled={!scanning}
          className="px-3 py-1.5 text-sm border border-red-500 text-red-600 rounded hover:bg-red-50 disabled:opacity-30 disabled:border-gray-300 disabled:text-gray-400"
        >
          Stop
        </button>
      </section>

      {showSettings && (
        <section className="mb-4 border border-border rounded p-4 space-y-3">
          <h2 className="font-medium text-sm">Scan Flags</h2>
          <div className="grid grid-cols-3 gap-2 text-xs">
            {(Object.keys(flags) as (keyof ScanFlagsDto)[]).map((key) => (
              <label key={key} className="flex items-center gap-1">
                <input
                  type="checkbox"
                  checked={flags[key]}
                  onChange={(e) => setFlags({ ...flags, [key]: e.target.checked })}
                />
                {key}
              </label>
            ))}
          </div>
          <div className="flex gap-2">
            <button
              onClick={saveSettings}
              className="px-3 py-1 text-sm bg-primary text-background rounded"
            >
              Save
            </button>
            <button
              onClick={() => setShowSettings(false)}
              className="px-3 py-1 text-sm border border-border rounded"
            >
              Cancel
            </button>
          </div>
        </section>
      )}

      {dirProgress && (
        <div className="mb-4 p-2 text-xs text-muted-foreground">
          Scanning directory: {dirProgress.current} / {dirProgress.total} files...
        </div>
      )}

      {error && (
        <div className="mb-4 p-3 border border-red-500 text-red-600 rounded text-sm">
          {error}
        </div>
      )}

      {/* Tab navigation */}
      <div className="flex gap-1 mb-3 border-b border-border">
        {(["scan", "hex", "disasm", "demangle", "sigs"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-3 py-1 text-sm rounded-t ${
              activeTab === tab
                ? "bg-background border border-border border-b-background -mb-px font-medium"
                : "text-muted-foreground hover:bg-muted"
            }`}
          >
            {tab === "scan" ? "Scan" : tab === "hex" ? "Hex" : tab === "disasm" ? "Disasm" : tab === "demangle" ? "Demangle" : "Signatures"}
          </button>
        ))}
      </div>

      {activeTab === "scan" && (
        <>
          {result && (
            <section className="border border-border rounded p-4 mb-4">
              <div className="flex justify-between mb-3">
                <h2 className="font-medium text-sm">{result.path}</h2>
                <span className="text-xs text-muted-foreground">{result.scan_time_ms} ms</span>
              </div>
              <DetectionTable detections={result.detections} />
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

          {dirResults.length > 0 && (
            <section className="border border-border rounded p-4">
              <h2 className="font-medium text-sm mb-3">
                Directory Results ({dirResults.length} files)
              </h2>
              <div className="space-y-2">
                {dirResults.map((r, i) => (
                  <div key={i} className="border-b border-border pb-2">
                    <div className="flex justify-between text-xs">
                      <span className="font-mono">{r.path}</span>
                      <span className="text-muted-foreground">{r.scan_time_ms} ms</span>
                    </div>
                    <DetectionTable detections={r.detections} compact />
                  </div>
                ))}
              </div>
            </section>
          )}
        </>
      )}

      {activeTab === "hex" && filePath && <HexViewer path={filePath} />}
      {activeTab === "disasm" && filePath && <Disassembler path={filePath} />}
      {activeTab === "demangle" && <DemangleTool />}
      {activeTab === "sigs" && <SignatureBrowser />}
    </div>
  );
}

function DetectionTable({
  detections,
  compact,
}: {
  detections: ScanDetectionDto[];
  compact?: boolean;
}) {
  if (detections.length === 0) {
    return <p className="text-sm text-muted-foreground">No detections.</p>;
  }
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-muted-foreground border-b border-border">
          <th className={compact ? "py-0.5" : "py-1"}>Type</th>
          <th className={compact ? "py-0.5" : "py-1"}>Name</th>
          <th className={compact ? "py-0.5" : "py-1"}>Version</th>
          <th className={compact ? "py-0.5" : "py-1"}>Options</th>
        </tr>
      </thead>
      <tbody>
        {detections.map((d, i) => (
          <tr key={i} className="border-b border-border">
            <td className={compact ? "py-0.5" : "py-1"}>{d.type_name}</td>
            <td className={compact ? "py-0.5" : "py-1"}>{d.name}</td>
            <td className={compact ? "py-0.5" : "py-1"}>{d.version ?? "-"}</td>
            <td className={compact ? "py-0.5" : "py-1"}>{d.options ?? "-"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
