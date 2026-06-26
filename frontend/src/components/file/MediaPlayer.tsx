import { Typography, Button, Popconfirm } from "antd";
import { DeleteOutlined } from "@ant-design/icons";

const { Text } = Typography;

interface Props {
  src: string;
  path: string;
  type: "audio" | "video";
  onDelete?: () => void;
}

export default function MediaPlayer({ src, path, type, onDelete }: Props) {
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
        background: "#000",
        borderRadius: 8,
        padding: type === "audio" ? 40 : 8,
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
      }}>
        {type === "audio" ? (
          <audio controls style={{ width: "100%", maxWidth: 500 }}>
            <source src={src} />
            您的浏览器不支持音频播放
          </audio>
        ) : (
          <video
            controls
            style={{ width: "100%", maxHeight: "60vh", borderRadius: 4 }}
            preload="metadata"
          >
            <source src={src} />
            您的浏览器不支持视频播放
          </video>
        )}
      </div>
    </div>
  );
}
