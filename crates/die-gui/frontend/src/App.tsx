import { useState, useEffect, useRef, useCallback } from "react";
import { invoke, Channel } from "@tauri-apps/api/core";
import { open as openDialog } from "@tauri-apps/plugin-dialog";
import { getCurrentWebview } from "@tauri-apps/api/webview";
import {
  FileSearch,
  FolderOpen,
  Play,
  FolderSearch,
  Square,
  Settings as SettingsIcon,
  ChevronRight,
  ChevronDown,
  FileText,
  Binary,
  Code2,
  Tags,
  Shield,
  ScanSearch,
  Globe,
  Info,
  AlertCircle,
  Clock,
  CheckCircle2,
  XCircle,
  FileSearch as FileSearchIcon,
} from "lucide-react";
import { HexViewer } from "./components/HexViewer";
import { Disassembler } from "./components/Disassembler";
import { DemangleTool } from "./components/DemangleTool";
import { SignatureBrowser } from "./components/SignatureBrowser";
import { YaraScanner } from "./components/YaraScanner";
import { PeidScanner } from "./components/PeidScanner";
import { OnlineTools } from "./components/OnlineTools";
import { FileInfoPanel } from "./components/FileInfoPanel";

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
  view: { theme: "dark", language: "en", stay_on_top: false, advanced: false },
  file: { last_directory: "", recent_files: [], save_backup: true },
  scan: { scan_after_open: true, hide_unknown: false, sort: false, log_profiling: false, flags: defaultFlags },
  database: { main_path: "", extra_path: "", custom_path: "", extra_enabled: false, custom_enabled: false },
  engine: { die_enabled: true, nfd_enabled: false, peid_enabled: false, yara_enabled: false },
};

type TabId = "scan" | "info" | "hex" | "disasm" | "demangle" | "sigs" | "yara" | "peid" | "online";

const TABS: { id: TabId; label: string; icon: typeof FileSearch }[] = [
  { id: "scan", label: "Scan", icon: ScanSearch },
  { id: "info", label: "Info", icon: FileSearchIcon },
  { id: "hex", label: "Hex", icon: Binary },
  { id: "disasm", label: "Disasm", icon: Code2 },
  { id: "demangle", label: "Demangle", icon: FileText },
  { id: "sigs", label: "Signatures", icon: Tags },
  { id: "yara", label: "YARA", icon: Shield },
  { id: "peid", label: "PEID", icon: ScanSearch },
  { id: "online", label: "Online", icon: Globe },
];

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
  const [activeTab, setActiveTab] = useState<TabId>("scan");
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
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

  const pickFile = useCallback(async () => {
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
  }, []);

  const pickDirectory = useCallback(async () => {
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
  }, []);

  const scan = useCallback(async () => {
    if (!filePath) return;
    setScanning(true);
    setError(null);
    setResult(null);
    setDirResults([]);
    try {
      const res = await invoke<ScanResultDto>("scan_file", { path: filePath, flags });
      setResult(res);
      // Auto-expand all nodes.
      setExpandedNodes(new Set(res.detections.map((_, i) => `node-${i}`)));
    } catch (e) {
      const err = e as GuiError;
      setError(err.message ?? String(e));
    } finally {
      setScanning(false);
    }
  }, [filePath, flags]);

  const scanDirectory = useCallback(async () => {
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
  }, [filePath, flags, dirProgress]);

  const stopScan = useCallback(async () => {
    try {
      await invoke("stop_scan");
    } catch (e) {
      setError(String(e));
    }
  }, []);

  const saveSettings = useCallback(async () => {
    const newSettings = { ...settings, scan: { ...settings.scan, flags } };
    setSettings(newSettings);
    try {
      await invoke("save_settings", { settings: newSettings });
      setShowSettings(false);
    } catch (e) {
      const err = e as GuiError;
      setError(err.message ?? String(e));
    }
  }, [settings, flags]);

  const toggleNode = (id: string) => {
    setExpandedNodes((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const fileName = filePath.split(/[\\/]/).pop() || filePath;
  const totalDetections = result?.detections.length ?? 0;
  const totalDiags = result?.diagnostics.length ?? 0;

  return (
    <div
      className="h-screen flex flex-col bg-window text-fg-primary"
      style={{ background: "rgb(var(--bg-window))" }}
    >
      {/* Drag overlay */}
      {dragOver && (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-blue-900/30 border-2 border-dashed border-accent-blue rounded">
          <div className="text-center">
            <FileSearch size={48} className="mx-auto mb-2 text-accent-blue" />
            <p className="text-lg text-accent-blue">Drop file here to scan</p>
          </div>
        </div>
      )}

      {/* Toolbar — file input + scan controls */}
      <div
        className="flex items-center gap-1 px-2 py-1.5 border-b border-border-c"
        style={{ background: "rgb(var(--bg-panel))" }}
      >
        <input
          type="text"
          value={filePath}
          onChange={(e) => setFilePath(e.target.value)}
          placeholder="Select a file or directory to scan..."
          className="input flex-1 selectable"
        />
        <button onClick={pickFile} className="btn" title="Open file">
          <FileSearch size={14} /> File
        </button>
        <button onClick={pickDirectory} className="btn" title="Open directory">
          <FolderOpen size={14} /> Dir
        </button>
        <div className="w-px h-5 bg-border-c mx-1" />
        <button
          onClick={scan}
          disabled={!filePath || scanning}
          className="btn btn-primary"
          title="Scan file"
        >
          <Play size={14} /> {scanning ? "Scanning..." : "Scan"}
        </button>
        <button
          onClick={scanDirectory}
          disabled={!filePath || scanning}
          className="btn"
          title="Scan directory"
        >
          <FolderSearch size={14} /> Scan Dir
        </button>
        <button
          onClick={stopScan}
          disabled={!scanning}
          className="btn btn-danger"
          title="Stop scan"
        >
          <Square size={14} /> Stop
        </button>
        <div className="flex-1" />
        <button
          onClick={() => setShowSettings(!showSettings)}
          className="btn"
          title="Settings"
        >
          <SettingsIcon size={14} />
        </button>
      </div>

      {/* Settings panel (collapsible) */}
      {showSettings && (
        <div
          className="px-3 py-2 border-b border-border-c space-y-2"
          style={{ background: "rgb(var(--bg-panel))" }}
        >
          <div className="text-xs font-medium text-fg-secondary">Scan Flags</div>
          <div className="grid grid-cols-4 gap-1.5 text-xs">
            {(Object.keys(flags) as (keyof ScanFlagsDto)[]).map((key) => (
              <label key={key} className="flex items-center gap-1.5 cursor-pointer hover:text-fg-primary">
                <input
                  type="checkbox"
                  checked={flags[key]}
                  onChange={(e) => setFlags({ ...flags, [key]: e.target.checked })}
                  className="accent-blue-500"
                />
                {key}
              </label>
            ))}
          </div>
          <div className="flex gap-2 pt-1">
            <button onClick={saveSettings} className="btn btn-primary">Save</button>
            <button onClick={() => setShowSettings(false)} className="btn">Cancel</button>
          </div>
        </div>
      )}

      {/* Tab bar */}
      <div
        className="flex items-center gap-0 px-1 border-b border-border-c"
        style={{ background: "rgb(var(--bg-panel))" }}
      >
        {TABS.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs ${
                activeTab === tab.id ? "tab-active" : "tab-inactive"
              }`}
            >
              <Icon size={13} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Main content area */}
      <div className="flex-1 overflow-auto" style={{ background: "rgb(var(--bg-window))" }}>
        {/* Error banner */}
        {error && (
          <div
            className="flex items-center gap-2 px-3 py-2 mx-2 mt-2 rounded text-xs"
            style={{ background: "rgba(var(--accent-red), 0.1)", border: "1px solid rgb(var(--accent-red))" }}
          >
            <AlertCircle size={14} className="text-accent-red" />
            <span className="text-accent-red selectable">{error}</span>
          </div>
        )}

        {/* Scan tab */}
        {activeTab === "scan" && (
          <div className="flex flex-col h-full">
            {/* File info bar */}
            {filePath && (
              <div
                className="flex items-center gap-3 px-3 py-1.5 border-b border-border-c text-xs"
                style={{ background: "rgb(var(--bg-panel))" }}
              >
                <Info size={13} className="text-fg-muted" />
                <span className="selectable text-fg-secondary">{fileName}</span>
                {result && (
                  <>
                    <div className="w-px h-3 bg-border-c" />
                    <span className="text-fg-muted">{totalDetections} detections</span>
                    {totalDiags > 0 && (
                      <span className="text-accent-yellow">{totalDiags} diagnostics</span>
                    )}
                    <div className="flex-1" />
                    <span className="flex items-center gap-1 text-fg-muted">
                      <Clock size={11} /> {result.scan_time_ms} ms
                    </span>
                  </>
                )}
              </div>
            )}

            {/* Progress bar during directory scan */}
            {dirProgress && (
              <div className="px-3 py-1.5">
                <div className="flex justify-between text-xs text-fg-secondary mb-1">
                  <span>Scanning directory...</span>
                  <span>{dirProgress.current} / {dirProgress.total}</span>
                </div>
                <div className="progress-bar">
                  <div
                    className="progress-bar-fill"
                    style={{
                      width: dirProgress.total > 0
                        ? `${(dirProgress.current / dirProgress.total) * 100}%`
                        : "0%",
                    }}
                  />
                </div>
              </div>
            )}

            {/* Scanning indicator */}
            {scanning && !dirProgress && (
              <div className="px-3 py-2 text-xs text-fg-secondary flex items-center gap-2">
                <div className="w-3 h-3 border-2 border-accent-blue border-t-transparent rounded-full animate-spin" />
                Scanning...
              </div>
            )}

            {/* Results: TreeView for single file, list for directory */}
            {result && (
              <DetectionTreeView
                result={result}
                expandedNodes={expandedNodes}
                onToggle={toggleNode}
              />
            )}

            {dirResults.length > 0 && (
              <DirectoryResultsView results={dirResults} />
            )}

            {/* Empty state */}
            {!result && dirResults.length === 0 && !scanning && !error && (
              <div className="flex flex-col items-center justify-center h-full text-fg-muted">
                <FileSearch size={48} className="mb-3 opacity-40" />
                <p className="text-sm">Open a file or drag & drop to begin scanning</p>
              </div>
            )}
          </div>
        )}

        {activeTab === "info" && filePath && <FileInfoPanel path={filePath} />}
        {activeTab === "hex" && filePath && <HexViewer path={filePath} />}
        {activeTab === "disasm" && filePath && <Disassembler path={filePath} />}
        {activeTab === "demangle" && <DemangleTool />}
        {activeTab === "sigs" && <SignatureBrowser />}
        {activeTab === "yara" && filePath && <YaraScanner path={filePath} />}
        {activeTab === "peid" && filePath && <PeidScanner path={filePath} />}
        {activeTab === "online" && <OnlineTools hash="" />}
      </div>

      {/* Status bar */}
      <div className="statusbar">
        {scanning ? (
          <>
            <div className="w-3 h-3 border-2 border-accent-blue border-t-transparent rounded-full animate-spin" />
            <span>Scanning...</span>
          </>
        ) : result ? (
          <>
            <CheckCircle2 size={12} className="text-accent-green" />
            <span>Ready — {totalDetections} detections</span>
          </>
        ) : error ? (
          <>
            <XCircle size={12} className="text-accent-red" />
            <span>Error</span>
          </>
        ) : (
          <>
            <div className="w-2 h-2 rounded-full bg-fg-muted" />
            <span>Ready</span>
          </>
        )}
        {result && <span className="text-fg-muted">| {result.scan_time_ms} ms</span>}
        {filePath && <span className="text-fg-muted selectable">| {fileName}</span>}
        <div className="flex-1" />
        <span className="text-fg-muted">DIE v0.3.0</span>
      </div>
    </div>
  );
}

/** Tree view for detection results — mirrors upstream DIE's 3-column TreeView. */
function DetectionTreeView({
  result,
  expandedNodes,
  onToggle,
}: {
  result: ScanResultDto;
  expandedNodes: Set<string>;
  onToggle: (id: string) => void;
}) {
  if (result.detections.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-fg-muted">
        <Info size={32} className="mb-2 opacity-40" />
        <p className="text-sm">No detections</p>
      </div>
    );
  }

  // Group detections by file_type (upstream groups by type in tree).
  const groups = new Map<string, ScanDetectionDto[]>();
  for (const d of result.detections) {
    const arr = groups.get(d.file_type) ?? [];
    arr.push(d);
    groups.set(d.file_type, arr);
  }

  return (
    <div className="selectable p-1">
      {/* Header row */}
      <div
        className="flex items-center gap-2 px-2 py-1 text-xs font-medium text-fg-secondary border-b border-border-c"
      >
        <span className="w-6" />
        <span className="flex-1">String</span>
        <span className="w-20 text-center">Type</span>
        <span className="w-24">Version</span>
        <span className="w-32">Options</span>
      </div>

      {/* Tree rows */}
      {Array.from(groups.entries()).map(([fileType, dets], gi) => {
        const groupId = `group-${gi}`;
        const expanded = expandedNodes.has(groupId);
        return (
          <div key={groupId}>
            <div
              className="tree-row text-xs"
              onClick={() => onToggle(groupId)}
            >
              <span className="w-6 flex justify-center">
                {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              </span>
              <span className="flex-1 font-medium text-accent-blue">{fileType}</span>
              <span className="w-20 text-center text-fg-muted">({dets.length})</span>
              <span className="w-24" />
              <span className="w-32" />
            </div>
            {expanded &&
              dets.map((d, di) => {
                const nodeId = `group-${gi}-${di}`;
                const nodeExpanded = expandedNodes.has(nodeId);
                const hasOptions = d.options && d.options.length > 0;
                return (
                  <div key={nodeId}>
                    <div
                      className="tree-row text-xs"
                      style={{ marginLeft: 20 }}
                      onClick={() => hasOptions && onToggle(nodeId)}
                    >
                      <span className="w-6 flex justify-center">
                        {hasOptions ? (
                          nodeExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />
                        ) : (
                          <div className="w-3" />
                        )}
                      </span>
                      <span className="flex-1">
                        <span className="text-fg-secondary">{d.type_name}: </span>
                        <span className="text-fg-primary">{d.name}</span>
                      </span>
                      <span className="w-20 text-center text-fg-muted">{d.type_name}</span>
                      <span className="w-24 text-fg-secondary">{d.version ?? ""}</span>
                      <span className="w-32 text-fg-muted truncate">
                        {d.options ? `${d.options.split(",").length} options` : ""}
                      </span>
                    </div>
                    {nodeExpanded && hasOptions && (
                      <div className="tree-children mono text-xs text-fg-secondary">
                        {d.options!.split(",").map((opt, oi) => (
                          <div key={oi} className="tree-row">
                            <span className="w-6" />
                            <span className="flex-1">{opt.trim()}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
          </div>
        );
      })}

      {/* Diagnostics */}
      {result.diagnostics.length > 0 && (
        <details className="mt-3 mx-2">
          <summary className="cursor-pointer text-xs text-accent-yellow flex items-center gap-1">
            <AlertCircle size={12} /> Diagnostics ({result.diagnostics.length})
          </summary>
          <pre
            className="mt-1 p-2 rounded mono text-xs text-fg-secondary overflow-x-auto"
            style={{ background: "rgb(var(--bg-input))" }}
          >
            {result.diagnostics.join("\n")}
          </pre>
        </details>
      )}
    </div>
  );
}

/** Directory scan results — compact list view. */
function DirectoryResultsView({ results }: { results: ScanResultDto[] }) {
  return (
    <div className="p-2 space-y-1 selectable">
      <div className="text-xs font-medium text-fg-secondary mb-2">
        Directory Results ({results.length} files)
      </div>
      {results.map((r, i) => {
        const fileName = r.path.split(/[\\/]/).pop() || r.path;
        return (
          <div
            key={i}
            className="panel p-2"
          >
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="mono text-fg-primary">{fileName}</span>
              <div className="flex items-center gap-2 text-fg-muted">
                <span className="flex items-center gap-1">
                  <CheckCircle2 size={11} className="text-accent-green" />
                  {r.detections.length}
                </span>
                <span className="flex items-center gap-1">
                  <Clock size={11} />
                  {r.scan_time_ms} ms
                </span>
              </div>
            </div>
            {r.detections.length > 0 && (
              <div className="text-xs text-fg-secondary ml-2">
                {r.detections.slice(0, 5).map((d, j) => (
                  <span key={j}>
                    {j > 0 && ", "}
                    <span className="text-accent-blue">{d.type_name}</span>: {d.name}
                  </span>
                ))}
                {r.detections.length > 5 && (
                  <span className="text-fg-muted"> +{r.detections.length - 5} more</span>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
