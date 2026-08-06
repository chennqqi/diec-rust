import { useState } from "react";
import { useTranslation } from "react-i18next";
import { invoke } from "@tauri-apps/api/core";
import { open as openDialog } from "@tauri-apps/plugin-dialog";

interface PeidMatch {
  name: string;
  pattern: string;
}

interface PeidScanResult {
  signatures_loaded: number;
  matches: PeidMatch[];
}

export function PeidScanner({ path }: { path: string }) {
  const { t } = useTranslation();
  const [userdbPath, setUserdbPath] = useState("");
  const [result, setResult] = useState<PeidScanResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function pickUserdb() {
    try {
      const selected = await openDialog({
        multiple: false,
        filters: [{ name: "PEID Database", extensions: ["txt", "db"] }],
      });
      if (typeof selected === "string") {
        setUserdbPath(selected);
      }
    } catch (e) {
      setError(String(e));
    }
  }

  async function scan() {
    if (!path || !userdbPath) return;
    setLoading(true);
    setError(null);
    try {
      const res = await invoke<PeidScanResult>("peid_scan", {
        userdbPath,
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
        <h3 className="text-sm font-medium">{t("peid.title")}</h3>
      </div>
      <div className="flex items-center gap-2 mb-2">
        <input
          type="text"
          value={userdbPath}
          onChange={(e) => setUserdbPath(e.target.value)}
          placeholder="userdb.txt path..."
          className="flex-1 text-xs border border-border rounded px-2 py-1"
        />
        <button
          onClick={pickUserdb}
          className="px-2 py-1 text-xs border border-border rounded"
        >
          Browse
        </button>
        <button
          onClick={scan}
          disabled={loading || !userdbPath}
          className="px-3 py-1 text-xs bg-primary text-background rounded disabled:opacity-50"
        >
          {loading ? t("peid.scanning") : t("peid.scan")}
        </button>
      </div>
      {error && <div className="text-xs text-red-600 mb-2">{error}</div>}
      {result && (
        <div>
          <p className="text-xs text-muted-foreground mb-1">
            {result.signatures_loaded} signatures loaded, {result.matches.length} match(es)
          </p>
          {result.matches.length > 0 && (
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-muted-foreground border-b border-border">
                  <th className="py-1">Name</th>
                  <th className="py-1">Pattern</th>
                </tr>
              </thead>
              <tbody>
                {result.matches.map((m, i) => (
                  <tr key={i} className="border-b border-border">
                    <td className="py-1 font-mono">{m.name}</td>
                    <td className="py-1">{m.pattern}</td>
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
