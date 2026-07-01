import { useState, useCallback, useRef, useEffect } from "react";
import { Card, Button, Tag, Space, Typography, Image, Modal, message, Spin } from "antd";
import {
  CheckOutlined,
  StopOutlined,
  RetweetOutlined,
  UndoOutlined,
  PlayCircleOutlined,
  SoundOutlined,
  FileOutlined,
  EditOutlined,
} from "@ant-design/icons";
import MonacoEditor from "@monaco-editor/react";
import type { GenerationResult } from "../../types/generation";
import * as filesApi from "../../api/files";

const { Text } = Typography;

const VIDEO_EXTS = [".mp4", ".webm", ".avi", ".mov", ".mkv"];
const IMAGE_EXTS = [".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"];
const AUDIO_EXTS = [".flac", ".wav", ".mp3", ".ogg", ".aac", ".m4a"];

function fileExt(path: string): string {
  return path.includes(".") ? `.${path.split(".").pop()?.toLowerCase()}` : "";
}

function isVideo(path: string): boolean { return VIDEO_EXTS.includes(fileExt(path)); }
function isImage(path: string): boolean { return IMAGE_EXTS.includes(fileExt(path)); }
function isAudio(path: string): boolean { return AUDIO_EXTS.includes(fileExt(path)); }

/** Prompt file mapping per step_name (takes priority over generation_type) */
const STEP_PROMPT_MAP: Record<string, string> = {
  shot_description: "shot_description.json",
};

/** Prompt file mapping per generation_type (fallback) */
const PROMPT_FILE_MAP: Record<string, string> = {
  first_frame: "first_frame_selector_output.json",
  last_frame: "last_frame_selector_output.json",
  video: "ltx_prompt.json",
};

function getPromptRelPath(resultRelPath: string, promptFile: string): string {
  const dir = resultRelPath.includes("/")
    ? resultRelPath.substring(0, resultRelPath.lastIndexOf("/") + 1)
    : "";
  return dir + promptFile;
}

interface Props {
  projectId: number;
  result: GenerationResult;
  onConfirm: () => void;
  onCancel: () => void;
  onRecover: () => void;
  onGacha: (scene: number, shot: number) => void;
  onRetry: () => void;
}

export default function ResultCard({ projectId, result, onConfirm, onCancel, onRecover, onGacha, onRetry }: Props) {
  const [previewOpen, setPreviewOpen] = useState(false);
  const previewHeight = 180;

  // ── Prompt file editor ──
  const promptFileName = STEP_PROMPT_MAP[result.step_name || ""] || PROMPT_FILE_MAP[result.generation_type] || "";
  const isGachaEligible = !!promptFileName;
  const canEditPrompt = !!promptFileName;
  const promptRelPath = canEditPrompt ? getPromptRelPath(result.original_relative_path || result.relative_path, promptFileName) : "";

  const [promptEditorOpen, setPromptEditorOpen] = useState(false);
  const [promptContent, setPromptContent] = useState("");
  const [promptLoading, setPromptLoading] = useState(false);
  const [promptSaving, setPromptSaving] = useState(false);
  const [promptDirty, setPromptDirty] = useState(false);
  const promptOriginalRef = { current: "" };
  const isComposing = useRef(false);

  // ── Drag state for prompt modal ──
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const dragging = useRef(false);
  const dragStart = useRef({ x: 0, y: 0 });
  const offsetStart = useRef({ x: 0, y: 0 });

  const handleDragStart = (e: React.MouseEvent) => {
    dragging.current = true;
    dragStart.current = { x: e.clientX, y: e.clientY };
    offsetStart.current = { ...dragOffset };
  };

  const handleDragMove = (e: MouseEvent) => {
    if (!dragging.current) return;
    setDragOffset({
      x: offsetStart.current.x + e.clientX - dragStart.current.x,
      y: offsetStart.current.y + e.clientY - dragStart.current.y,
    });
  };

  const handleDragEnd = () => {
    dragging.current = false;
  };

  const handleClosePromptEditor = () => {
    setPromptEditorOpen(false);
    setDragOffset({ x: 0, y: 0 });
  };

  useEffect(() => {
    window.addEventListener("mousemove", handleDragMove);
    window.addEventListener("mouseup", handleDragEnd);
    return () => {
      window.removeEventListener("mousemove", handleDragMove);
      window.removeEventListener("mouseup", handleDragEnd);
    };
  }, []);

  const handleOpenPromptEditor = useCallback(async () => {
    setPromptEditorOpen(true);
    setPromptLoading(true);
    setPromptDirty(false);
    try {
      const data = await filesApi.fetchFileContent(projectId, promptRelPath);
      setPromptContent(data.content);
      promptOriginalRef.current = data.content;
    } catch {
      setPromptContent("");
      promptOriginalRef.current = "";
    } finally {
      setPromptLoading(false);
    }
  }, [projectId, promptRelPath]);

  const handlePromptChange = (v: string | undefined) => {
    const val = v || "";
    if (isComposing.current) return;
    setPromptContent(val);
    setPromptDirty(val !== promptOriginalRef.current);
  };

  const handlePromptEditorMount = useCallback((editor: any) => {
    const domNode = editor.getDomNode();
    if (!domNode) return;
    const textarea = domNode.querySelector("textarea");
    if (!textarea) return;
    textarea.addEventListener("compositionstart", () => { isComposing.current = true; });
    textarea.addEventListener("compositionend", () => { isComposing.current = false; });
  }, []);

  const handleSavePrompt = async () => {
    setPromptSaving(true);
    try {
      await filesApi.updateFileContent(projectId, promptRelPath, promptContent);
      promptOriginalRef.current = promptContent;
      setPromptDirty(false);
      message.success("Prompt 已保存");
    } catch {
      message.error("保存失败");
    } finally {
      setPromptSaving(false);
    }
  };

  const mediaSrc = `/api/projects/${projectId}/files/media?path=${encodeURIComponent(result.relative_path)}`;

  const renderPreview = () => {
    if (result.file_path === "pending") return null;

    // ── Video ──
    if (isVideo(result.file_path)) {
      return (
        <div
          style={{ height: previewHeight, backgroundColor: "#1a1a1a", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer" }}
          onClick={() => setPreviewOpen(true)}
        >
          <PlayCircleOutlined style={{ fontSize: 48, color: "#fff", opacity: 0.7 }} />
        </div>
      );
    }

    // ── Image ──
    if (isImage(result.file_path)) {
      return (
        <div
          style={{ height: previewHeight, overflow: "hidden", display: "flex", alignItems: "center", justifyContent: "center", backgroundColor: "#f5f5f5", cursor: "pointer" }}
        >
          <Image
            src={mediaSrc}
            alt={result.relative_path}
            style={{ maxHeight: previewHeight, objectFit: "cover" }}
            fallback="data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAwIiBoZWlnaHQ9IjEwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZjBmMGYwIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGR5PSIuM2VtIiBmaWxsPSIjOTk5IiBmb250LXNpemU9IjEyIiBmb250LWZhbWlseT0ic2Fucy1zZXJpZiI+5Zu+54mH5Yqg6L295aSx6LSlPC90ZXh0Pjwvc3ZnPg=="
          />
        </div>
      );
    }

    // ── Audio ──
    if (isAudio(result.file_path)) {
      return (
        <div style={{ height: previewHeight, backgroundColor: "#fafafa", display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 8, padding: 16 }}>
          <SoundOutlined style={{ fontSize: 32, color: "#1677ff" }} />
          <audio
            controls
            style={{ width: "100%", maxWidth: 260 }}
            src={mediaSrc}
            preload="metadata"
          >
            Your browser does not support audio playback.
          </audio>
        </div>
      );
    }

    // ── Unknown ──
    return (
      <div style={{ height: previewHeight, backgroundColor: "#f0f0f0", display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 4 }}>
        <FileOutlined style={{ fontSize: 28, color: "#bbb" }} />
        <Text type="secondary" style={{ fontSize: 11 }}>无预览</Text>
      </div>
    );
  };

  return (
    <>
      <Card
        size="small"
        style={result.confirmed ? { borderColor: "#52c41a", opacity: 0.7 } : result.cancelled ? { opacity: 0.45 } : {}}
        cover={renderPreview()}
      >
        <Space direction="vertical" size={4} style={{ width: "100%" }}>
          {/* Relative path */}
          <Text type="secondary" style={{ fontSize: 11 }} ellipsis title={result.relative_path}>
            {result.relative_path}
          </Text>

          {/* Prompt ID */}
          {result.prompt_id && (
            <Text type="secondary" style={{ fontSize: 10, fontFamily: "monospace" }} ellipsis title={result.prompt_id}>
              {result.prompt_id}
            </Text>
          )}

          {/* Scene / Shot */}
          {(result.scene != null || result.shot != null) && (
            <Space size={4}>
              {result.scene != null && <Tag color="purple" style={{ fontSize: 10, lineHeight: "16px" }}>场景 {result.scene}</Tag>}
              {result.shot != null && <Tag color="cyan" style={{ fontSize: 10, lineHeight: "16px" }}>镜头 {result.shot}</Tag>}
            </Space>
          )}

          {/* Workflow name */}
          {result.workflow_name && (
            <Text type="secondary" style={{ fontSize: 10 }} ellipsis>{result.workflow_name}</Text>
          )}

          {/* Type + duration */}
          <Space size={4} wrap>
            <Tag color="blue" style={{ fontSize: 11, lineHeight: "18px" }}>{result.generation_type}</Tag>
            {result.duration_seconds > 0 && (
              <Text type="secondary" style={{ fontSize: 11 }}>{result.duration_seconds.toFixed(1)}s</Text>
            )}
            {result.cancelled && <Tag color="default" style={{ fontSize: 11, lineHeight: "18px" }}>已取消</Tag>}
          </Space>

          {/* Actions */}
          {result.cancelled ? (
            <Space size={4} wrap>
              <Button size="small" icon={<UndoOutlined />} onClick={onRecover}>
                恢复
              </Button>
              {canEditPrompt && (
                <Button size="small" icon={<EditOutlined />} onClick={handleOpenPromptEditor}>
                  Prompt
                </Button>
              )}
              {isGachaEligible && (
                <Button size="small" icon={<RetweetOutlined />} onClick={() => onGacha(result.scene ?? 1, result.shot ?? 2)}>
                  抽卡
                </Button>
              )}
            </Space>
          ) : (
            <Space size={4} wrap>
              {result.confirmed ? (
                <>
                  <Tag color="success" style={{ fontSize: 11 }}>已确认</Tag>
                  <Button size="small" danger icon={<StopOutlined />} onClick={onCancel}>
                    取消
                  </Button>
                  {canEditPrompt && (
                    <Button size="small" icon={<EditOutlined />} onClick={handleOpenPromptEditor}>
                      Prompt
                    </Button>
                  )}
                </>
              ) : (
                <>
                  <Button size="small" type="primary" icon={<CheckOutlined />} onClick={onConfirm}>
                    确认
                  </Button>
                  <Button size="small" danger icon={<StopOutlined />} onClick={onCancel}>
                    取消
                  </Button>
                  {canEditPrompt && (
                    <Button size="small" icon={<EditOutlined />} onClick={handleOpenPromptEditor}>
                      Prompt
                    </Button>
                  )}
                </>
              )}
            </Space>
          )}
        </Space>
      </Card>

      {/* Video preview modal */}
      {isVideo(result.file_path) && (
        <Modal
          open={previewOpen}
          footer={null}
          onCancel={() => setPreviewOpen(false)}
          width={800}
          destroyOnClose
          title={result.relative_path}
        >
          <video
            controls
            autoPlay
            style={{ width: "100%", maxHeight: "70vh", backgroundColor: "#000" }}
            src={mediaSrc}
          >
            Your browser does not support video playback.
          </video>
        </Modal>
      )}

      {/* Prompt file editor modal */}
      {canEditPrompt && (
        <Modal
          open={promptEditorOpen}
          onCancel={handleClosePromptEditor}
          width={900}
          destroyOnClose
          modalRender={(modal) => (
            <div
              style={{
                transform: `translate(${dragOffset.x}px, ${dragOffset.y}px)`,
              }}
            >
              {modal}
            </div>
          )}
          title={
            <div
              onMouseDown={handleDragStart}
              style={{ cursor: "move", userSelect: "none", margin: -20, padding: "20px 24px" }}
            >
              <Space>
                <EditOutlined />
                <span>编辑 Prompt — {promptFileName}</span>
              </Space>
            </div>
          }
          footer={
            <Space>
              <Button onClick={handleClosePromptEditor}>关闭</Button>
              {promptDirty && (
                <Button type="primary" icon={<CheckOutlined />} onClick={handleSavePrompt} loading={promptSaving}>
                  保存
                </Button>
              )}
            </Space>
          }
        >
          {promptLoading ? (
            <div style={{ textAlign: "center", padding: 60 }}><Spin /></div>
          ) : (
            <div style={{ height: "60vh" }}>
              <MonacoEditor
                height="100%"
                language="json"
                value={promptContent}
                onChange={handlePromptChange}
                onMount={handlePromptEditorMount}
                theme="vs-dark"
                options={{ minimap: { enabled: false }, fontSize: 13, wordWrap: "on" }}
              />
            </div>
          )}
        </Modal>
      )}
    </>
  );
}
