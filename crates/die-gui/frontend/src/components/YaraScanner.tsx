import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
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

interface DataPathsDto {
  db: string;
  db_extra: string | null;
  db_custom: string | null;
  peid_rules: string | null;
  yara_rules: string | null;
  yara_rule_files: string[];
  peid_userdb_files: string[];
}

export function YaraScanner({ path }: { path: string }) {
  const { t } = useTranslation();
  const [rules, setRules] = useState(
    'rule test_rule { strings: $a = "test" condition: $a }'
  );
  const [result, setResult] = useState<YaraScanResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [builtinRules, setBuiltinRules] = useState<string[]>([]);

  // Load bundled YARA rule file list on mount.
  useEffect(() => {
    invoke<DataPathsDto>("get_data_paths")
      .then((paths) => {
        setBuiltinRules(paths.yara_rule_files);
      })
      .catch(() => {
        // Not in Tauri environment — no bundled rules.
      });
  }, []);

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

  // Load a built-in YARA rule file from the bundled yara_rules/ directory.
  async function loadBuiltinRule(relPath: string) {
    setLoading(true);
    setError(null);
    try {
      const content = await invoke<string>("read_data_file", {
        relativePath: `yara_rules/${relPath}`,
      });
      setRules(content);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
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
        <h3 className="text-sm font-medium">{t("yara.title")}</h3>
        <div className="flex-1" />
        {builtinRules.length > 0 && (
          <select
            className="text-xs border border-border rounded px-1 py-0.5"
            onChange={(e) => {
              if (e.target.value) loadBuiltinRule(e.target.value);
              e.target.value = "";
            }}
            value=""
          >
            <option value="">— {t("yara.loadBuiltin")} —</option>
            {builtinRules.map((f) => (
              <option key={f} value={f}>{f}</option>
            ))}
          </select>
        )}
        <button
          onClick={loadRules}
          className="px-2 py-0.5 text-xs border border-border rounded"
        >
          {t("yara.loadFile")}
        </button>
        <button
          onClick={scan}
          disabled={loading}
          className="px-3 py-0.5 text-xs bg-primary text-background rounded disabled:opacity-50"
        >
          {loading ? t("yara.scanning") : t("yara.scan")}
        </button>
      </div>
      <textarea
        value={rules}
        onChange={(e) => setRules(e.target.value)}
        className="w-full h-32 text-xs font-mono border border-border rounded p-2 mb-2"
        placeholder={t("yara.placeholder")}
      />
      {error && <div className="text-xs text-red-600 mb-2">{error}</div>}
      {result && (
        <div>
          <p className="text-xs text-muted-foreground mb-1">
            {result.match_count} {t("yara.matches")}
          </p>
          {result.matches.length > 0 && (
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-muted-foreground border-b border-border">
                  <th className="py-1">{t("yara.rule")}</th>
                  <th className="py-1">{t("yara.namespace")}</th>
                  <th className="py-1">{t("yara.tags")}</th>
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
