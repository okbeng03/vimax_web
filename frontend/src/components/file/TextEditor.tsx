import { useRef, useEffect, useState } from "react";
import MonacoEditor from "@monaco-editor/react";
import { Button, Popconfirm } from "antd";
import { SaveOutlined, EditOutlined, DeleteOutlined } from "@ant-design/icons";
import FullscreenWrapper from "../common/FullscreenWrapper";

const EXT_LANG_MAP: Record<string, string> = {
  ".txt": "plaintext",
  ".json": "json",
  ".py": "python",
  ".yaml": "yaml",
  ".yml": "yaml",
};

interface Props {
  path: string;
  content: string;
  onChange: (v: string) => void;
  onSave: () => void;
  saving?: boolean;
  onDelete?: () => void;
}

export default function TextEditor({ path, content, onChange, onSave, saving, onDelete }: Props) {
  const ext = path.includes(".") ? `.${path.split(".").pop()}` : ".txt";
  const lang = EXT_LANG_MAP[ext] || "plaintext";

  // Track original content to detect unsaved changes
  const originalRef = useRef(content);
  const [dirty, setDirty] = useState(false);

  // Reset baseline when file path changes (new file loaded)
  useEffect(() => {
    originalRef.current = content;
    setDirty(false);
  }, [path]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleChange = (v: string | undefined) => {
    const val = v || "";
    onChange(val);
    setDirty(val !== originalRef.current);
  };

  const editor = (
    <MonacoEditor
      height="100%"
      language={lang}
      value={content}
      onChange={handleChange}
      theme="vs-dark"
      options={{ minimap: { enabled: false }, fontSize: 13, wordWrap: "on" }}
    />
  );

  return (
    <FullscreenWrapper
      toolbar={
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <strong>{path}</strong>
          <div style={{ flex: 1 }} />
          {dirty ? (
            <Button icon={<SaveOutlined />} onClick={onSave} loading={saving} type="primary" size="small">
              保存
            </Button>
          ) : (
            <span style={{ fontSize: 12, color: "#52c41a" }}>
              <EditOutlined style={{ marginRight: 4 }} />
              预览中
            </span>
          )}
          {onDelete && (
            <Popconfirm
              title="确定删除此文件？"
              description="文件将移至 caches 目录"
              onConfirm={onDelete}
              okText="删除"
              cancelText="取消"
            >
              <Button size="small" danger icon={<DeleteOutlined />} style={{ marginRight: 12 }}>删除</Button>
            </Popconfirm>
          )}
        </div>
      }
    >
      {(fs: boolean) => (
        <div style={{ height: fs ? "100%" : 500 }}>{editor}</div>
      )}
    </FullscreenWrapper>
  );
}
