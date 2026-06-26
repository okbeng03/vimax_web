import { Tree } from "antd";
import { FileOutlined, FolderOutlined, FileImageOutlined, FileTextOutlined, AudioOutlined, VideoCameraOutlined } from "@ant-design/icons";
import { useEffect, useState, useCallback, useRef } from "react";
import * as filesApi from "../../api/files";
import type { FileItem } from "../../api/files";

const IMAGE_EXTS = [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"];
const AUDIO_EXTS = [".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac"];
const VIDEO_EXTS = [".mp4", ".webm"];
const TEXT_EXTS = [".txt", ".json", ".py", ".yaml", ".yml"];
const SELECTABLE_EXTS = [...TEXT_EXTS, ...IMAGE_EXTS, ...AUDIO_EXTS, ...VIDEO_EXTS];

function getFileIcon(ext: string): React.ReactNode {
  if (IMAGE_EXTS.includes(ext)) return <FileImageOutlined />;
  if (AUDIO_EXTS.includes(ext)) return <AudioOutlined />;
  if (VIDEO_EXTS.includes(ext)) return <VideoCameraOutlined />;
  if (TEXT_EXTS.includes(ext)) return <FileTextOutlined />;
  return <FileOutlined />;
}

interface Props {
  projectId: number;
  onSelectFile: (path: string) => void;
  /** Set to a deleted file path to refresh its parent directory in-place */
  deletedPath?: string;
  /** When true, refetch root to show latest files */
  visible?: boolean;
}

export default function FileTree({ projectId, onSelectFile, deletedPath, visible }: Props) {
  const [treeData, setTreeData] = useState<any[]>([]);
  const [loadedPaths, setLoadedPaths] = useState<Set<string>>(new Set([""]));
  const [expandedKeys, setExpandedKeys] = useState<string[]>([]);
  const prevDeletedPath = useRef<string | undefined>();
  const prevVisible = useRef<boolean | undefined>();

  // Load root on mount / project change
  useEffect(() => {
    setLoadedPaths(new Set([""]));
    filesApi.fetchFileTree(projectId).then((d) => setTreeData(itemsToTree(d.files, "")));
  }, [projectId]);

  // Refetch root when tab becomes visible
  useEffect(() => {
    if (visible && !prevVisible.current) {
      setLoadedPaths(new Set([""]));
      filesApi.fetchFileTree(projectId).then((d) => setTreeData(itemsToTree(d.files, "")));
    }
    prevVisible.current = visible;
  }, [visible, projectId]);

  // Refresh parent directory when a file is deleted
  useEffect(() => {
    if (!deletedPath || deletedPath === prevDeletedPath.current) return;
    prevDeletedPath.current = deletedPath;

    const parentPath = deletedPath.includes("/") ? deletedPath.substring(0, deletedPath.lastIndexOf("/")) : "";
    filesApi.fetchFileTree(projectId, parentPath).then((d) => {
      const children = itemsToTree(d.files, parentPath);
      if (parentPath) {
        setTreeData((prev) => mergeChildren(prev, parentPath, children));
      } else {
        setTreeData(children);
      }
    });
  }, [deletedPath, projectId]);

  const itemsToTree = (items: FileItem[], parentPath: string): any[] =>
    items.map((item) => {
      const fullPath = parentPath ? `${parentPath}/${item.name}` : item.name;
      const ext = item.name.includes(".") ? `.${item.name.split(".").pop()?.toLowerCase()}` : "";
      return {
        key: fullPath,
        title: item.name,
        icon: item.type === "directory" ? <FolderOutlined /> : getFileIcon(ext),
        isLeaf: item.type === "file",
        children: item.type === "directory" ? [] : undefined,
      };
    });

  // Lazy load subdirectories on expand
  const onLoadData = useCallback(
    async (node: any) => {
      const { key } = node;
      if (loadedPaths.has(key)) return;
      try {
        const d = await filesApi.fetchFileTree(projectId, key);
        const children = itemsToTree(d.files, key);
        setTreeData((prev) => mergeChildren(prev, key, children));
        setLoadedPaths((prev) => new Set(prev).add(key));
      } catch {
        // silently ignore load errors
      }
    },
    [projectId, loadedPaths],
  );

  const mergeChildren = (nodes: any[], targetKey: string, children: any[]): any[] =>
    nodes.map((node) => {
      if (node.key === targetKey) return { ...node, children };
      if (node.children && node.children.length > 0)
        return { ...node, children: mergeChildren(node.children, targetKey, children) };
      return node;
    });

  return (
    <Tree
      showIcon
      treeData={treeData}
      loadData={onLoadData}
      expandedKeys={expandedKeys}
      onExpand={(keys) => setExpandedKeys(keys as string[])}
      onSelect={(keys) => {
        if (keys.length > 0) {
          const key = String(keys[0]);
          const ext = key.includes(".") ? `.${key.split(".").pop()?.toLowerCase()}` : "";
          if (SELECTABLE_EXTS.includes(ext)) {
            onSelectFile(key);
          }
        }
      }}
    />
  );
}
