import { useState, useCallback, useMemo } from "react";
import { message, Spin, Empty, Typography } from "antd";
import FileTree from "../../components/file/FileTree";
import TextEditor from "../../components/file/TextEditor";
import ImagePreview from "../../components/file/ImagePreview";
import MediaPlayer from "../../components/file/MediaPlayer";
import { useFileEditor } from "../../hooks/useFileEditor";
import { getMediaUrl, deleteFile } from "../../api/files";

const { Text } = Typography;

const TEXT_EDITABLE_EXTS = [".txt", ".py", ".yaml", ".yml", ".json"];
const IMAGE_EXTS = [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"];
const AUDIO_EXTS = [".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac"];
const VIDEO_EXTS = [".mp4", ".webm"];

interface Props {
  projectId: number;
  visible?: boolean;
}

export default function FileTab({ projectId, visible }: Props) {
  const [selectedPath, setSelectedPath] = useState("");
  const [saving, setSaving] = useState(false);
  const [deletedPath, setDeletedPath] = useState("");
  const { content, setContent, currentPath, loading, loadFile, saveFile } = useFileEditor(projectId);

  const ext = selectedPath.includes(".") ? `.${selectedPath.split(".").pop()?.toLowerCase()}` : "";
  const isEditableText = TEXT_EDITABLE_EXTS.includes(ext);
  const isImage = IMAGE_EXTS.includes(ext);
  const isAudio = AUDIO_EXTS.includes(ext);
  const isVideo = VIDEO_EXTS.includes(ext);
  const isMedia = isImage || isAudio || isVideo;

  const mediaUrl = useMemo(
    () => (isMedia && selectedPath ? getMediaUrl(projectId, selectedPath) : ""),
    [isMedia, projectId, selectedPath],
  );

  const handleSelectFile = useCallback(
    (path: string) => {
      setSelectedPath(path);
      const e = path.includes(".") ? `.${path.split(".").pop()?.toLowerCase()}` : "";
      if (TEXT_EDITABLE_EXTS.includes(e)) {
        loadFile(path);
      }
    },
    [loadFile],
  );

  const handleSave = async () => {
    setSaving(true);
    try {
      await saveFile();
      message.success("文件已保存");
    } catch {
      message.error("保存失败");
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteFile = useCallback(
    async (path: string) => {
      try {
        await deleteFile(projectId, path);
        message.success(`已删除: ${path}`);
        setDeletedPath(path);
        if (path === selectedPath) {
          setSelectedPath("");
        }
      } catch {
        message.error("删除失败");
      }
    },
    [projectId, selectedPath],
  );

  const renderEditor = () => {
    if (!selectedPath) {
      return <Empty description="请从左侧文件树选择文件" />;
    }

    if (loading && isEditableText) {
      return (
        <div style={{ textAlign: "center", padding: 60 }}>
          <Spin />
        </div>
      );
    }

    if (isEditableText) {
      return (
        <TextEditor
          path={currentPath || selectedPath}
          content={content}
          onChange={setContent}
          onSave={handleSave}
          saving={saving}
          onDelete={() => handleDeleteFile(selectedPath)}
        />
      );
    }

    if (isImage) {
      return <ImagePreview src={mediaUrl} path={selectedPath} onDelete={() => handleDeleteFile(selectedPath)} />;
    }

    if (isAudio) {
      return <MediaPlayer src={mediaUrl} path={selectedPath} type="audio" onDelete={() => handleDeleteFile(selectedPath)} />;
    }

    if (isVideo) {
      return <MediaPlayer src={mediaUrl} path={selectedPath} type="video" onDelete={() => handleDeleteFile(selectedPath)} />;
    }

    // Unsupported file type
    return (
      <div style={{ textAlign: "center", padding: 60 }}>
        <Text type="secondary">不支持预览此类型文件</Text>
      </div>
    );
  };

  return (
    <div style={{ display: "flex", gap: 16, minHeight: 500 }}>
      {/* Left: FileTree */}
      <div
        style={{
          width: "30%",
          minWidth: 200,
          border: "1px solid #f0f0f0",
          borderRadius: 8,
          padding: 12,
          overflow: "auto",
          maxHeight: "70vh",
        }}
      >
        <Text strong style={{ display: "block", marginBottom: 8 }}>文件列表</Text>
        <FileTree projectId={projectId} onSelectFile={handleSelectFile} deletedPath={deletedPath} visible={visible} />
      </div>

      {/* Right: Editor / Viewer */}
      <div
        style={{
          flex: 1,
          border: "1px solid #f0f0f0",
          borderRadius: 8,
          padding: 16,
          overflow: "auto",
          maxHeight: "70vh",
        }}
      >
        {renderEditor()}
      </div>
    </div>
  );
}
