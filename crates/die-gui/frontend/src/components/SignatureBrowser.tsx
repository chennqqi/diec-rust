import { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";

interface SignatureInfoDto {
  name: string;
  file_path: string;
}

interface SignatureGroupDto {
  file_type: string;
  signatures: SignatureInfoDto[];
}

interface SignatureSourceDto {
  source: string;
  file_path: string;
}

export function SignatureBrowser() {
  const [groups, setGroups] = useState<SignatureGroupDto[]>([]);
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [selectedSig, setSelectedSig] = useState<string | null>(null);
  const [source, setSource] = useState<SignatureSourceDto | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const result = await invoke<SignatureGroupDto[]>("list_signatures");
        setGroups(result);
      } catch (e) {
        setError(String(e));
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  async function loadSource(fileType: string, name: string) {
    setSelectedSig(name);
    setError(null);
    try {
      const result = await invoke<SignatureSourceDto>("get_signature_source", {
        fileType,
        name,
      });
      setSource(result);
    } catch (e) {
      setError(String(e));
    }
  }

  return (
    <div className="border border-border rounded p-3 mt-3">
      <h3 className="text-sm font-medium mb-2">Signature Browser</h3>
      {loading && <p className="text-xs text-muted-foreground">Loading...</p>}
      {error && <div className="text-xs text-red-600 mb-2">{error}</div>}
      <div className="flex gap-3 max-h-64">
        <div className="w-40 overflow-y-auto border-r border-border pr-2">
          {groups.map((g) => (
            <div key={g.file_type} className="mb-1">
              <button
                onClick={() => setSelectedType(g.file_type)}
                className={`text-xs font-medium w-full text-left px-1 py-0.5 rounded ${
                  selectedType === g.file_type ? "bg-primary text-background" : "hover:bg-muted"
                }`}
              >
                {g.file_type} ({g.signatures.length})
              </button>
              {selectedType === g.file_type && (
                <div className="ml-2 mt-0.5">
                  {g.signatures.map((s) => (
                    <button
                      key={s.name}
                      onClick={() => loadSource(g.file_type, s.name)}
                      className={`text-xs block w-full text-left px-1 py-0.5 rounded truncate ${
                        selectedSig === s.name ? "bg-muted font-medium" : "hover:bg-muted"
                      }`}
                      title={s.name}
                    >
                      {s.name}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
        <div className="flex-1 overflow-y-auto">
          {source ? (
            <pre className="text-xs font-mono bg-muted p-2 rounded overflow-x-auto">
              {source.source}
            </pre>
          ) : (
            <p className="text-xs text-muted-foreground">
              Select a signature to view its source.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
