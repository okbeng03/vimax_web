import { Image, Typography, Empty, Button, Popconfirm } from "antd";
import { DeleteOutlined } from "@ant-design/icons";

const { Text } = Typography;

interface Props {
  src: string;
  path: string;
  onDelete?: () => void;
}

export default function ImagePreview({ src, path, onDelete }: Props) {
  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
        <Text strong style={{ fontSize: 13, fontFamily: "monospace" }}>{path}</Text>
        {onDelete && (
          <Popconfirm
            title="确定删除此文件？"
            description="文件将移至 caches 目录"
            onConfirm={onDelete}
            okText="删除"
            cancelText="取消"
          >
            <Button size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        )}
      </div>
      <div style={{
        background: "#f5f5f5",
        borderRadius: 8,
        padding: 16,
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        minHeight: 300,
      }}>
        <Image
          src={src}
          alt={path}
          style={{ maxWidth: "100%", maxHeight: "60vh", objectFit: "contain" }}
          fallback="data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgZmlsbD0iI2VlZSIvPjx0ZXh0IHg9IjUwJSIgeT0iNTAlIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBkeT0iLjNlbSIgZmlsbD0iIzk5OSIgZm9udC1zaXplPSIxNiI+5Yqg6L295aSx6LSlPC90ZXh0Pjwvc3ZnPg=="
        />
      </div>
    </div>
  );
}
