import { Typography } from "antd";

const { Text } = Typography;

// ── Types ──

export interface DetailChange {
  file: string;
  diff: string;
  original: string;
}

export type DetailData =
  | { type: "changes"; files: DetailChange[] }
  | { type: "single-diff"; diff: string; original: string }
  | { type: "json"; content: unknown }
  | { type: "text"; content: string };

// ── Parsing ──

/** Parse details JSON string into structured data for the LogDetailModal */
export function parseDetails(raw: string | null): DetailData | null {
  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw);

    // Multi-file edit: {"changes": [{"file": "...", "diff": "...", "original": "..."}]}
    if (parsed.changes && Array.isArray(parsed.changes) && parsed.changes.length > 0) {
      return { type: "changes", files: parsed.changes as DetailChange[] };
    }

    // Single-file edit: {"diff": "...", "original": "..."}
    if (typeof parsed.diff === "string") {
      return { type: "single-diff", diff: parsed.diff, original: parsed.original ?? "" };
    }

    // Generic JSON
    return { type: "json", content: parsed };
  } catch {
    // Plain text
    return { type: "text", content: raw };
  }
}

/** Check if a string is valid JSON (object or array) */
export function isJsonContent(s: string): boolean {
  if (!s || typeof s !== "string") return false;
  const t = s.trim();
  if (!((t.startsWith("{") && t.endsWith("}")) || (t.startsWith("[") && t.endsWith("]")))) return false;
  try {
    JSON.parse(t);
    return true;
  } catch {
    return false;
  }
}

/** Try to parse and pretty-print a JSON string */
export function formatJsonString(s: string): string {
  try {
    return JSON.stringify(JSON.parse(s), null, 2);
  } catch {
    return s;
  }
}

// ── Diff Renderer ──

interface Props {
  diff: string;
}

/** Render a git unified diff with colored +/- lines */
export default function DiffViewer({ diff }: Props) {
  if (!diff) return <Text type="secondary">无变更</Text>;

  const lines = diff.split("\n");

  return (
    <div
      style={{
        fontFamily: "'SF Mono', 'Monaco', 'Menlo', 'Consolas', monospace",
        fontSize: 12,
        lineHeight: "20px",
        background: "#1e1e1e",
        color: "#d4d4d4",
        borderRadius: 6,
        padding: "8px 0",
        maxHeight: 460,
        overflow: "auto",
      }}
    >
      {lines.map((line, i) => {
        let color = "#d4d4d4";
        let bg = "transparent";

        if (line.startsWith("@@")) {
          color = "#569cd6";
          bg = "rgba(86,156,214,0.12)";
        } else if (line.startsWith("+++") || line.startsWith("---")) {
          color = "#c586c0";
          bg = "rgba(197,134,192,0.08)";
        } else if (line.startsWith("+")) {
          color = "#4ec9b0";
          bg = "rgba(78,201,176,0.1)";
        } else if (line.startsWith("-")) {
          color = "#f44747";
          bg = "rgba(244,71,71,0.1)";
        } else if (line.startsWith("diff ") || line.startsWith("index ")) {
          color = "#808080";
        }

        return (
          <div
            key={i}
            style={{
              background: bg,
              padding: "0 8px",
              whiteSpace: "pre-wrap",
              wordBreak: "break-all",
              color,
              minHeight: 20,
            }}
          >
            {line || "\u00A0"}
          </div>
        );
      })}
    </div>
  );
}

// ── Legacy compatibility (used by LogTable before migration) ──

/** @deprecated Use parseDetails + LogDetailModal instead */
export function renderDetails(details: string | null): React.ReactNode {
  if (!details) return null;

  const data = parseDetails(details);
  if (!data) return null;

  if (data.type === "changes") {
    return (
      <div>
        {data.files.map((c, i) => (
          <div key={i} style={{ marginBottom: i < data.files.length - 1 ? 16 : 0 }}>
            <Text strong style={{ display: "block", marginBottom: 4 }}>
              {c.file}
            </Text>
            <DiffViewer diff={c.diff} />
          </div>
        ))}
      </div>
    );
  }

  if (data.type === "single-diff") {
    return <DiffViewer diff={data.diff} />;
  }

  if (data.type === "json") {
    return (
      <pre style={{
        fontFamily: "'SF Mono', 'Monaco', 'Menlo', 'Consolas', monospace",
        fontSize: 12,
        background: "#1e1e1e",
        color: "#d4d4d4",
        padding: 12,
        borderRadius: 6,
        maxHeight: 400,
        overflow: "auto",
        whiteSpace: "pre-wrap",
        wordBreak: "break-all",
      }}>
        {JSON.stringify(data.content, null, 2)}
      </pre>
    );
  }

  return <Text>{data.content}</Text>;
}
