import { useMemo } from "react";

/**
 * Lightweight syntax highlighter for DIE signature files (.sg).
 *
 * DIE signatures use a C-like syntax with specific built-in functions
 * and keywords. This highlighter tokenizes the source and wraps
 * tokens in colored spans. It is intentionally simple (regex-based)
 * to avoid pulling in a heavy highlighting dependency.
 *
 * Token classes and colors (mapped to CSS variables):
 * - comment:   // ... or /* ... *​/  → fg-muted, italic
 * - string:    "..." or '...'        → accent-green
 * - keyword:    if, else, for, etc.  → accent-blue, bold
 * - builtin:   detect, set, etc.    → accent-purple
 * - number:    0x..., digits        → accent-yellow
 * - operator:  +, -, =, etc.        → fg-secondary
 * - default:   everything else      → fg-primary
 */

// Reserved keywords in DIE signature scripts.
const KEYWORDS = new Set([
  "if", "else", "for", "while", "do", "return", "break", "continue",
  "function", "var", "let", "const", "true", "false", "null", "undefined",
  "new", "delete", "typeof", "in", "of", "this",
]);

// Built-in DIE host API functions (commonly used in signatures).
const BUILTINS = new Set([
  "detect", "set", "get", "readByte", "readWord", "readDword", "readQword",
  "readString", "readUnicodeString", "getByte", "getWord", "getDword",
  "getQword", "getString", "getUnicodeString",
  "getFileSize", "getEntryPoint", "getOverlaySize", "getOverlayOffset",
  "isPE", "isELF", "isMachO", "isArchive",
  "getSectionNumber", "getSectionName", "getSectionOffset", "getSectionSize",
  "getSectionVirtualAddress", "getSectionVirtualSize",
  "getImportFunctionName", "getExportFunctionName", "getExportFunctionOffset",
  "getResourceName", "getResourceOffset", "getResourceSize",
  "getVersionInfo", "getVersionInfoByKey",
  "getManifest", "getCertificateName", "getCertificateIndex",
  "printf", "print", "log",
  "XSignature", "XBinary", "XPE", "XELF", "XMachO", "XArchive",
  "SDeepScan", "SScan", "SAdvancedScan",
]);

interface Token {
  type: "comment" | "string" | "keyword" | "builtin" | "number" | "operator" | "default";
  value: string;
}

/**
 * Tokenize a line of DIE signature source code.
 */
function tokenizeLine(line: string): Token[] {
  const tokens: Token[] = [];
  let i = 0;

  while (i < line.length) {
    const ch = line[i];

    // Line comment: // ...
    if (ch === "/" && line[i + 1] === "/") {
      tokens.push({ type: "comment", value: line.slice(i) });
      break;
    }

    // Block comment start: /* ... (single-line handling)
    if (ch === "/" && line[i + 1] === "*") {
      const end = line.indexOf("*/", i + 2);
      if (end !== -1) {
        tokens.push({ type: "comment", value: line.slice(i, end + 2) });
        i = end + 2;
        continue;
      }
      // Unterminated block comment — rest of line is comment.
      tokens.push({ type: "comment", value: line.slice(i) });
      break;
    }

    // String literal: "..." or '...'
    if (ch === '"' || ch === "'") {
      const quote = ch;
      let j = i + 1;
      while (j < line.length && line[j] !== quote) {
        if (line[j] === "\\") j++; // skip escaped char
        j++;
      }
      tokens.push({ type: "string", value: line.slice(i, j + 1) });
      i = j + 1;
      continue;
    }

    // Number: 0x..., 0X..., or digits
    if (ch === "0" && (line[i + 1] === "x" || line[i + 1] === "X")) {
      let j = i + 2;
      while (j < line.length && /[0-9a-fA-F]/.test(line[j])) j++;
      tokens.push({ type: "number", value: line.slice(i, j) });
      i = j;
      continue;
    }
    if (/[0-9]/.test(ch)) {
      let j = i;
      while (j < line.length && /[0-9.]/.test(line[j])) j++;
      tokens.push({ type: "number", value: line.slice(i, j) });
      i = j;
      continue;
    }

    // Identifier: [a-zA-Z_$][a-zA-Z0-9_$]*
    if (/[a-zA-Z_$]/.test(ch)) {
      let j = i;
      while (j < line.length && /[a-zA-Z0-9_$]/.test(line[j])) j++;
      const word = line.slice(i, j);
      if (KEYWORDS.has(word)) {
        tokens.push({ type: "keyword", value: word });
      } else if (BUILTINS.has(word)) {
        tokens.push({ type: "builtin", value: word });
      } else {
        tokens.push({ type: "default", value: word });
      }
      i = j;
      continue;
    }

    // Operator: +, -, *, /, =, <, >, !, &, |, ^, ~, %
    if (/[+\-*/=<>!&|^~%]/.test(ch)) {
      let j = i;
      while (j < line.length && /[+\-*/=<>!&|^~%]/.test(line[j])) j++;
      tokens.push({ type: "operator", value: line.slice(i, j) });
      i = j;
      continue;
    }

    // Default: single char
    tokens.push({ type: "default", value: ch });
    i++;
  }

  return tokens;
}

const TOKEN_CLASS: Record<Token["type"], string> = {
  comment: "syntax-comment",
  string: "syntax-string",
  keyword: "syntax-keyword",
  builtin: "syntax-builtin",
  number: "syntax-number",
  operator: "syntax-operator",
  default: "syntax-default",
};

/**
 * Render DIE signature source code with syntax highlighting.
 *
 * Each line is tokenized independently and rendered as a <div> with
 * colored <span> children. Line numbers are shown in a gutter.
 */
export function SignatureHighlighter({ source }: { source: string }) {
  const lines = useMemo(() => source.split("\n"), [source]);

  return (
    <div className="syntax-container">
      {lines.map((line, idx) => {
        const tokens = tokenizeLine(line);
        return (
          <div key={idx} className="syntax-line">
            <span className="syntax-gutter">{idx + 1}</span>
            <span className="syntax-content">
              {tokens.map((tok, ti) => (
                <span key={ti} className={TOKEN_CLASS[tok.type]}>
                  {tok.value}
                </span>
              ))}
              {tokens.length === 0 && "\u00A0"}
            </span>
          </div>
        );
      })}
    </div>
  );
}
