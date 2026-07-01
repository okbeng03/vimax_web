import { useRef, useEffect, useState, useCallback } from "react";
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

  // IME composition guard — skip onChange callback during composition
  const isComposing = useRef(false);
  const composeValueRef = useRef(content);

  // Reset baseline when file path changes (new file loaded)
  useEffect(() => {
    originalRef.current = content;
    composeValueRef.current = content;
    setDirty(false);
  }, [path]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleBeforeMount = useCallback((monaco: any) => {
    // Override the editor creation to intercept composition events early
  }, []);

  const handleMount = useCallback((editor: any) => {
    const domNode = editor.getDomNode();
    if (!domNode) return;
    // Monaco's underlying textarea emits composition events
    const textarea = domNode.querySelector("textarea");
    if (!textarea) return;

    const onCompositionStart = () => {
      isComposing.current = true;
    };
    const onCompositionEnd = () => {
      isComposing.current = false;
      // After IME commits, push the final value up
      const finalValue = editor.getValue();
      composeValueRef.current = finalValue;
      onChange(finalValue);
      setDirty(finalValue !== originalRef.current);
    };

    textarea.addEventListener("compositionstart", onCompositionStart);
    textarea.addEventListener("compositionend", onCompositionEnd);

    // Cleanup not strictly necessary for single mount, but good practice
    return () => {
      textarea.removeEventListener("compositionstart", onCompositionStart);
      textarea.removeEventListener("compositionend", onCompositionEnd);
    };
  }, [onChange]);

  const handleChange = useCallback((v: string | undefined) => {
    const val = v || "";
    composeValueRef.current = val;
    // During IME composition, don't push intermediate pinyin to parent
    if (isComposing.current) return;
    onChange(val);
    setDirty(val !== originalRef.current);
  }, [onChange]);

  const editor = (
    <MonacoEditor
      height="100%"
      language={lang}
      value={content}
      onChange={handleChange}
      beforeMount={handleBeforeMount}
      onMount={handleMount}
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
