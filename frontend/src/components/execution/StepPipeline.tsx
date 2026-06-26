import { Steps, Tag, Typography } from "antd";
import {
  LoadingOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
} from "@ant-design/icons";
import type { Step } from "../../types/step";

const { Text } = Typography;

const STATUS_ICON: Record<string, { icon: React.ReactNode; color: string }> = {
  pending: { icon: <ClockCircleOutlined />, color: "default" },
  running: { icon: <LoadingOutlined spin />, color: "processing" },
  fully_complete: { icon: <CheckCircleOutlined />, color: "success" },
  partially_complete: { icon: <ExclamationCircleOutlined />, color: "warning" },
  failed: { icon: <CloseCircleOutlined />, color: "error" },
};

const STATUS_LABEL: Record<string, string> = {
  pending: "待执行",
  running: "执行中",
  fully_complete: "完成",
  partially_complete: "部分完成",
  failed: "失败",
};

interface Props {
  steps: Step[];
  onStepClick?: (step: Step) => void;
}

export default function StepPipeline({ steps, onStepClick }: Props) {
  return (
    <Steps
      direction="vertical"
      size="small"
      current={steps.findIndex((s) => s.status === "running")}
      items={steps.map((s) => {
        const info = STATUS_ICON[s.status] || STATUS_ICON.pending;
        return {
          title: (
            <div
              style={{ cursor: onStepClick ? "pointer" : "default", display: "flex", alignItems: "center", gap: 8 }}
              onClick={() => onStepClick?.(s)}
            >
              <Text>{s.name}</Text>
              <Tag color={info.color} icon={info.icon}>
                {STATUS_LABEL[s.status] || s.status}
              </Tag>
              {s.duration_seconds && <Text type="secondary">{s.duration_seconds.toFixed(1)}s</Text>}
              {s.retry_count > 0 && <Text type="secondary">重试: {s.retry_count}</Text>}
            </div>
          ),
          icon: info.icon,
        };
      })}
    />
  );
}
