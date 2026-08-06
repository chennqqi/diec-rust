import { useState, useEffect } from "react";
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

interface DataPathsDto {
  db: string;
  db_extra: string | null;
  db_custom: string | null;
  peid_rules: string | null;
  yara_rules: string | null;
  yara_rule_files: string[];
  peid_userdb_files: string[];
}

export function PeidScanner({ path }: { path: string }) {
  const { t } = useTranslation();
  const [userdbPath, setUserdbPath] = useState("");
  const [result, setResult] = useState<PeidScanResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [builtinUserdbs, setBuiltinUserdbs] = useState<string[]>([]);
  const [peidRulesDir, setPeidRulesDir] = useState<string | null>(null);

  // Load bundled PEID userdb file list on mount.
  useEffect(() => {
    invoke<DataPathsDto>("get_data_paths")
      .then((paths) => {
        setPeidRulesDir(paths.peid_rules);
        setBuiltinUserdbs(paths.peid_userdb_files);
        // Auto-select the default userdb.txt if available.
        const defaultDb = paths.peid_userdb_files.find((f) =>
          f.endsWith("userdb.txt")
        );
        if (defaultDb && paths.peid_rules) {
          const sep = paths.peid_rules.includes("\\") ? "\\" : "/";
          setUserdbPath(paths.peid_rules + sep + defaultDb);
        }
      })
      .catch(() => {
        // Not in Tauri environment — no bundled rules.
      });
  }, []);

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
          placeholder={t("peid.placeholder")}
          className="flex-1 text-xs border border-border rounded px-2 py-1"
        />
        <button
          onClick={pickUserdb}
          className="px-2 py-1 text-xs border border-border rounded"
        >
          {t("peid.browse")}
        </button>
        <button
          onClick={scan}
          disabled={loading || !userdbPath}
          className="px-3 py-1 text-xs bg-primary text-background rounded disabled:opacity-50"
        >
          {loading ? t("peid.scanning") : t("peid.scan")}
        </button>
      </div>
      {/* Built-in userdb selector */}
      {builtinUserdbs.length > 0 && peidRulesDir && (
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs text-fg-muted">{t("peid.builtin")}:</span>
          <select
            className="text-xs border border-border rounded px-1 py-0.5"
            onChange={(e) => {
              const sep = peidRulesDir.includes("\\") ? "\\" : "/";
              setUserdbPath(peidRulesDir + sep + e.target.value);
            }}
            value=""
          >
            <option value="">— {t("peid.selectBuiltin")} —</option>
            {builtinUserdbs.map((f) => (
              <option key={f} value={f}>{f}</option>
            ))}
          </select>
        </div>
      )}
      {error && <div className="text-xs text-red-600 mb-2">{error}</div>}
      {result && (
        <div>
          <p className="text-xs text-muted-foreground mb-1">
            {result.signatures_loaded} {t("peid.signaturesLoaded")}, {result.matches.length} {t("peid.matches")}
          </p>
          {result.matches.length > 0 && (
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-muted-foreground border-b border-border">
                  <th className="py-1">{t("peid.name")}</th>
                  <th className="py-1">{t("peid.pattern")}</th>
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
