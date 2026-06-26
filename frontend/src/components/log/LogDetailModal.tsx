import { useState, useMemo } from "react";
import { Modal, Segmented, Tabs } from "antd";
import { SwapOutlined, FileTextOutlined } from "@ant-design/icons";
import MonacoEditor from "@monaco-editor/react";
import DiffViewer, {
  parseDetails,
  isJsonContent,
  formatJsonString,
  type DetailData,
} from "./DiffViewer";

// ── View Mode ──

type ViewMode = "diff" | "original";

// ── Original Content Renderer ──

function OriginalContent({ text }: { text: string }) {
  const isJson = useMemo(() => isJsonContent(text), [text]);
  const formatted = useMemo(() => (isJson ? formatJsonString(text) : text), [text, isJson]);

  if (isJson) {
    return (
      <MonacoEditor
        height={400}
        language="json"
        value={formatted}
        theme="vs-dark"
        options={{
          readOnly: true,
          minimap: { enabled: false },
          fontSize: 13,
          wordWrap: "on",
          scrollBeyondLastLine: false,
          lineNumbers: "on",
          folding: true,
          renderWhitespace: "selection",
          automaticLayout: true,
        }}
      />
    );
  }

  return (
    <pre
      style={{
        fontFamily: "'SF Mono', 'Monaco', 'Menlo', 'Consolas', monospace",
        fontSize: 12,
        lineHeight: "20px",
        background: "#1e1e1e",
        color: "#d4d4d4",
        borderRadius: 6,
        padding: 12,
        maxHeight: 460,
        overflow: "auto",
        whiteSpace: "pre-wrap",
        wordBreak: "break-all",
        margin: 0,
      }}
    >
      {text || "\u00A0"}
    </pre>
  );
}

// ── Single File: Diff + Original Toggle ──

function SingleFileView({ diff, original }: { diff: string; original: string }) {
  const [mode, setMode] = useState<ViewMode>("diff");

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <Segmented
          size="small"
          value={mode}
          onChange={(v) => setMode(v as ViewMode)}
          options={[
            { label: "变更对比", value: "diff", icon: <SwapOutlined /> },
            { label: "原文", value: "original", icon: <FileTextOutlined /> },
          ]}
        />
      </div>

      {mode === "diff" ? (
        <DiffViewer diff={diff} />
      ) : (
        <OriginalContent text={original} />
      )}
    </div>
  );
}

// ── Multi-File: Tabs per file, each with Diff/Original toggle ──

function MultiFileView({ files }: { files: DetailData & { type: "changes" }["files"] }) {
  const [activeFile, setActiveFile] = useState(files[0]?.file ?? "");

  const current = files.find((f) => f.file === activeFile) ?? files[0];

  const tabItems = files.map((f) => ({
    key: f.file,
    label: f.file,
  }));

  return (
    <div>
      <Tabs
        activeKey={activeFile}
        onChange={setActiveFile}
        items={tabItems}
        size="small"
      />
      {current && <SingleFileView diff={current.diff} original={current.original} />}
    </div>
  );
}

// ── JSON Only (no diffs) ──

function JsonOnlyView({ data }: { data: DetailData & { type: "json" } }) {
  const text = JSON.stringify(data.content, null, 2);
  return <OriginalContent text={text} />;
}

// ── Plain Text ──

function PlainTextView({ text }: { text: string }) {
  return (
    <pre
      style={{
        fontFamily: "'SF Mono', 'Monaco', 'Menlo', 'Consolas', monospace",
        fontSize: 13,
        background: "#1e1e1e",
        color: "#d4d4d4",
        padding: 12,
        borderRadius: 6,
        maxHeight: 460,
        overflow: "auto",
        whiteSpace: "pre-wrap",
        wordBreak: "break-all",
        margin: 0,
      }}
    >
      {text || "\u00A0"}
    </pre>
  );
}

// ── Main Modal ──

interface Props {
  open: boolean;
  title: string;
  details: string | null;
  onClose: () => void;
}

export default function LogDetailModal({ open, title, details, onClose }: Props) {
  const data = useMemo(() => parseDetails(details), [details]);

  const body = useMemo(() => {
    if (!data) return null;
    switch (data.type) {
      case "changes":
        return <MultiFileView files={data.files} />;
      case "single-diff":
        return <SingleFileView diff={data.diff} original={data.original} />;
      case "json":
        return <JsonOnlyView data={data} />;
      case "text":
        return <PlainTextView text={data.content} />;
    }
  }, [data]);

  return (
    <Modal
      title={title}
      open={open}
      onCancel={onClose}
      footer={null}
      width={900}
      destroyOnClose
    >
      {body}
    </Modal>
  );
}
