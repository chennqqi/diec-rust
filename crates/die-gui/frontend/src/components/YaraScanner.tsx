import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { open as openDialog } from "@tauri-apps/plugin-dialog";

interface YaraMatch {
  rule: string;
  namespace: string;
  tags: string[];
}

interface YaraScanResult {
  match_count: number;
  matches: YaraMatch[];
}

export function YaraScanner({ path }: { path: string }) {
  const [rules, setRules] = useState(
    'rule test_rule { strings: $a = "test" condition: $a }'
  );
  const [result, setResult] = useState<YaraScanResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadRules() {
    try {
      const selected = await openDialog({
        multiple: false,
        filters: [{ name: "YARA Rules", extensions: ["yar", "yara"] }],
      });
      if (typeof selected === "string") {
        // Read file via Tauri FS plugin would require permission;
        // for now, user pastes rules manually.
        setRules(`// Loaded from: ${selected}\n${rules}`);
      }
    } catch (e) {
      setError(String(e));
    }
  }

  async function scan() {
    if (!path || !rules) return;
    setLoading(true);
    setError(null);
    try {
      const res = await invoke<YaraScanResult>("yara_scan", {
        rulesSource: rules,
        filePath: path,
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
        <h3 className="text-sm font-medium">YARA Scanner</h3>
        <div className="flex-1" />
        <button
          onClick={loadRules}
          className="px-2 py-0.5 text-xs border border-border rounded"
        >
          Load .yar
        </button>
        <button
          onClick={scan}
          disabled={loading}
          className="px-3 py-0.5 text-xs bg-primary text-background rounded disabled:opacity-50"
        >
          {loading ? "Scanning..." : "Scan"}
        </button>
      </div>
      <textarea
        value={rules}
        onChange={(e) => setRules(e.target.value)}
        className="w-full h-32 text-xs font-mono border border-border rounded p-2 mb-2"
        placeholder="Enter YARA rules..."
      />
      {error && <div className="text-xs text-red-600 mb-2">{error}</div>}
      {result && (
        <div>
          <p className="text-xs text-muted-foreground mb-1">
            {result.match_count} match(es)
          </p>
          {result.matches.length > 0 && (
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-muted-foreground border-b border-border">
                  <th className="py-1">Rule</th>
                  <th className="py-1">Namespace</th>
                  <th className="py-1">Tags</th>
                </tr>
              </thead>
              <tbody>
                {result.matches.map((m, i) => (
                  <tr key={i} className="border-b border-border">
                    <td className="py-1 font-mono">{m.rule}</td>
                    <td className="py-1">{m.namespace}</td>
                    <td className="py-1">{m.tags.join(", ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
