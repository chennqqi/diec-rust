import { useState } from "react";
import { useTranslation } from "react-i18next";

interface OnlineService {
  name: string;
  urlTemplate: (hash: string) => string;
}

const services: OnlineService[] = [
  {
    name: "VirusTotal",
    urlTemplate: (h) => `https://www.virustotal.com/gui/file/${h}`,
  },
  {
    name: "Hybrid Analysis",
    urlTemplate: (h) => `https://hybrid-analysis.com/search?query=${h}`,
  },
  {
    name: "MalwareBazaar",
    urlTemplate: (h) => `https://bazaar.abuse.ch/browse.php?search=md5:${h}`,
  },
  {
    name: "MalShare",
    urlTemplate: (h) => `https://malshare.com/sample.php?action=detail&hash=${h}`,
  },
  {
    name: "VirusBay",
    urlTemplate: (h) => `https://virusbay.io/sample/${h}`,
  },
  {
    name: "Censys",
    urlTemplate: (h) => `https://search.censys.io/search?resource=hosts&q=${h}`,
  },
];

export function OnlineTools({ hash }: { hash: string }) {
  const { t } = useTranslation();
  const [customHash, setCustomHash] = useState("");
  const effectiveHash = hash || customHash;

  if (!effectiveHash) {
    return (
      <div className="border border-border rounded p-3 mt-3">
        <h3 className="text-sm font-medium mb-2">{t("online.title")}</h3>
        <input
          type="text"
          value={customHash}
          onChange={(e) => setCustomHash(e.target.value)}
          placeholder={t("online.enterHash")}
          className="w-full text-xs font-mono border border-border rounded px-2 py-1"
        />
        <p className="text-xs text-muted-foreground mt-2">
          {t("online.hint")}
        </p>
      </div>
    );
  }

  return (
    <div className="border border-border rounded p-3 mt-3">
      <h3 className="text-sm font-medium mb-2">{t("online.title")}</h3>
      <div className="flex items-center gap-2 mb-2">
        <input
          type="text"
          value={effectiveHash}
          onChange={(e) => setCustomHash(e.target.value)}
          placeholder="File hash..."
          className="flex-1 text-xs font-mono border border-border rounded px-2 py-1"
        />
      </div>
      <div className="grid grid-cols-2 gap-2">
        {services.map((svc) => (
          <a
            key={svc.name}
            href={svc.urlTemplate(effectiveHash)}
            target="_blank"
            rel="noopener noreferrer"
            className="px-3 py-1.5 text-xs border border-border rounded hover:bg-muted text-center"
          >
            {svc.name}
          </a>
        ))}
      </div>
    </div>
  );
}
