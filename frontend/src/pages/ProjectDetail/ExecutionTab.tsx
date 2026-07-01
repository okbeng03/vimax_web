import { Tag, Space } from "antd";
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
} from "@ant-design/icons";
import TerminalView from "../../components/execution/TerminalView";

interface FinalStatus {
  project_status?: string;
  step_name?: string;
  error_message?: string;
}

interface StepReady {
  step_name?: string;
  step_status?: string;
}

interface Props {
  projectId: number;
  projectStatus: string;
  outputLines: string[];
  isConnected: boolean;
  finalStatus: FinalStatus | null;
  stepReady: StepReady | null;
}

export default function ExecutionTab({
  outputLines,
  isConnected,
  finalStatus,
  stepReady,
  projectStatus,
}: Props) {
  if (projectStatus === "idle") {
    return (
      <div style={{ textAlign: "center", padding: 40, color: "#999" }}>
        点击右上角"开始生成"按钮启动 ViMax 流程
      </div>
    );
  }

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="middle">
      {/* Connection indicator */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        {projectStatus === "running" && isConnected && !stepReady ? (
          <Tag icon={<LoadingOutlined spin />} color="processing">
            实时连接中
          </Tag>
        ) : null}
        {stepReady && (
          <Tag icon={<CheckCircleOutlined />} color="success">
            步骤 {stepReady.step_name} 已完成 — 请确认继续
          </Tag>
        )}
        {finalStatus ? (
          (finalStatus.project_status === "completed" || finalStatus.project_status === "success") ? (
            <Tag icon={<CheckCircleOutlined />} color="success">
              执行成功
            </Tag>
          ) : (
            <Tag icon={<CloseCircleOutlined />} color="error">
              执行失败
            </Tag>
          )
        ) : null}
        <span style={{ color: "#888", fontSize: 12 }}>
          {outputLines.length} 行输出
        </span>
      </div>

      {/* Terminal */}
      <TerminalView outputLines={outputLines} />

      {/* Final error message */}
      {finalStatus?.error_message && (
        <div
          style={{
            padding: 12,
            background: "#fff2f0",
            border: "1px solid #ffccc7",
            borderRadius: 6,
            color: "#cf1322",
            fontSize: 13,
          }}
        >
          {finalStatus.error_message}
        </div>
      )}
    </Space>
  );
}
