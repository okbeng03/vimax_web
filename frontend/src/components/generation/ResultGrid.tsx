import { useState, useRef, useCallback } from "react";
import { Row, Col, Typography, Divider, Button, Modal, Spin, message, Space } from "antd";
import { EditOutlined, CheckOutlined } from "@ant-design/icons";
import MonacoEditor from "@monaco-editor/react";
import type { GenerationResult } from "../../types/generation";
import * as filesApi from "../../api/files";
import ResultCard from "./ResultCard";

const { Text } = Typography;

interface Props {
  projectId: number;
  results: GenerationResult[];
  /** When true, results are already grouped by scene+shot — render with group headers */
  grouped?: boolean;
  onConfirm: (id: number) => void;
  onCancel: (id: number) => void;
  onRecover: (id: number) => void;
  onGacha: (id: number, scene: number, shot: number) => void;
  onRetry: (id: number) => void;
}

function groupKey(r: GenerationResult): string {
  if (r.scene != null && r.shot != null) return `scene${r.scene}_shot${r.shot}`;
  if (r.scene != null) return `scene${r.scene}`;
  if (r.shot != null) return `shot${r.shot}`;
  return "__other__";
}

/** Derive shot_description.json path from an item in the group */
function getShotDescriptionPath(item: GenerationResult): string {
  // Use original_relative_path — never contains caches/ prefix
  const rel = item.original_relative_path || item.relative_path;
  const dir = rel.includes("/") ? rel.substring(0, rel.lastIndexOf("/") + 1) : "";
  return dir + "shot_description.json";
}

/** Edit button + modal for shot_description.json */
function ShotDescriptionEditor({ projectId, item }: { projectId: number; item: GenerationResult }) {
  const [open, setOpen] = useState(false);
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const path = getShotDescriptionPath(item);
  const originalRef = { current: "" };
  const isComposing = useRef(false);

  const handleOpen = async () => {
    setOpen(true);
    setLoading(true);
    setDirty(false);
    try {
      const data = await filesApi.fetchFileContent(projectId, path);
      setContent(data.content);
      originalRef.current = data.content;
    } catch {
      setContent("");
      originalRef.current = "";
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (v: string | undefined) => {
    const val = v || "";
    setContent(val);
    setDirty(val !== originalRef.current);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await filesApi.updateFileContent(projectId, path, content);
      originalRef.current = content;
      setDirty(false);
      message.success("描述已保存");
    } catch {
      message.error("保存失败");
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <Button
        size="small"
        type="link"
        icon={<EditOutlined />}
        onClick={handleOpen}
        style={{ fontSize: 11, marginLeft: 4 }}
      >
        shot_description
      </Button>
      <Modal
        open={open}
        onCancel={() => setOpen(false)}
        width={900}
        destroyOnClose
        title={
          <Space>
            <EditOutlined />
            <span>编辑 shot_description.json</span>
          </Space>
        }
        footer={
          <Space>
            <Button onClick={() => setOpen(false)}>关闭</Button>
            {dirty && (
              <Button type="primary" icon={<CheckOutlined />} onClick={handleSave} loading={saving}>
                保存
              </Button>
            )}
          </Space>
        }
      >
        {loading ? (
          <div style={{ textAlign: "center", padding: 60 }}><Spin /></div>
        ) : (
          <div style={{ height: "60vh" }}>
            <MonacoEditor
              height="100%"
              language="json"
              value={content}
              onChange={handleChange}
              theme="vs-dark"
              options={{ minimap: { enabled: false }, fontSize: 13, wordWrap: "on" }}
            />
          </div>
        )}
      </Modal>
    </>
  );
}

export default function ResultGrid({ projectId, results, grouped, onConfirm, onCancel, onRecover, onGacha, onRetry }: Props) {
  if (!grouped) {
    return (
      <Row gutter={[16, 16]}>
        {results.map((r) => (
          <Col xs={24} sm={12} md={8} lg={6} key={r.id}>
            <ResultCard
              projectId={projectId}
              result={r}
              onConfirm={() => onConfirm(r.id)}
              onCancel={() => onCancel(r.id)}
              onRecover={() => onRecover(r.id)}
              onGacha={(s, sh) => onGacha(r.id, s, sh)}
              onRetry={() => onRetry(r.id)}
            />
          </Col>
        ))}
      </Row>
    );
  }

  // Grouped mode: split into sections with headers
  const groups: { key: string; label: string; items: GenerationResult[] }[] = [];
  let currentKey = "";
  for (const r of results) {
    const k = groupKey(r);
    if (k !== currentKey) {
      const scene = r.scene != null ? `场景 ${r.scene}` : "";
      const shot = r.shot != null ? `镜头 ${r.shot}` : "";
      const label = [scene, shot].filter(Boolean).join(" · ") || "其他";
      groups.push({ key: k, label, items: [r] });
      currentKey = k;
    } else {
      groups[groups.length - 1].items.push(r);
    }
  }

  return (
    <div>
      {groups.map((g) => (
        <div key={g.key} style={{ marginBottom: 16 }}>
          <Divider orientation="left" style={{ margin: "12px 0 8px" }}>
            <Text strong style={{ fontSize: 14 }}>{g.label}</Text>
            <Text type="secondary" style={{ fontSize: 12, marginLeft: 8 }}>({g.items.length})</Text>
            <ShotDescriptionEditor projectId={projectId} item={g.items[0]} />
          </Divider>
          <Row gutter={[16, 16]}>
            {g.items.map((r) => (
              <Col xs={24} sm={12} md={8} lg={6} key={r.id}>
                <ResultCard
                  projectId={projectId}
                  result={r}
                  onConfirm={() => onConfirm(r.id)}
                  onCancel={() => onCancel(r.id)}
                  onRecover={() => onRecover(r.id)}
                  onGacha={(s, sh) => onGacha(r.id, s, sh)}
                  onRetry={() => onRetry(r.id)}
                />
              </Col>
            ))}
          </Row>
        </div>
      ))}
    </div>
  );
}
