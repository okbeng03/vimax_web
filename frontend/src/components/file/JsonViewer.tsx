import { useState } from "react";
import { Tree, Typography } from "antd";

const { Text } = Typography;

interface Props {
  jsonString: string;
  onEdit?: (path: string, value: unknown) => void;
}

function toTreeData(obj: unknown, key = "root"): any[] {
  if (obj === null || obj === undefined) return [{ key, title: <Text type="secondary">null</Text>, isLeaf: true }];
  if (typeof obj !== "object") {
    // Explicit check for BigInt
    const val = typeof obj === "bigint" ? obj.toString() : String(obj);
    return [{ key, title: <Text>{val}</Text>, isLeaf: true }];
  }
  if (Array.isArray(obj)) {
    return obj.map((item, i) => ({
      key: `${key}[${i}]`,
      title: <Text style={{ color: "#1890ff" }}>[{i}]</Text>,
      children: toTreeData(item, `${key}[${i}]`),
    }));
  }
  return Object.entries(obj as Record<string, unknown>).map(([k, v]) => ({
    key: `${key}.${k}`,
    title: (
      <span>
        <Text strong>{k}</Text>
        {typeof v !== "object" || v === null ? (
          <Text style={{ marginLeft: 8 }} type="secondary">
            {typeof v === "bigint" ? String(v) : String(v ?? "null")}
          </Text>
        ) : null}
      </span>
    ),
    children: typeof v === "object" && v !== null ? toTreeData(v, `${key}.${k}`) : undefined,
  }));
}

export default function JsonViewer({ jsonString, onEdit }: Props) {
  const [treeData] = useState(() => {
    try {
      return toTreeData(JSON.parse(jsonString));
    } catch {
      return [{ key: "error", title: <Text type="danger">Invalid JSON</Text>, isLeaf: true }];
    }
  });

  return <Tree showLine defaultExpandAll treeData={treeData} />;
}
