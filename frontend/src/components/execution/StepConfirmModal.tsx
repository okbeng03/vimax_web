import { Modal, Button, Space, Typography, Tag } from "antd";
import type { Step } from "../../types/step";

const { Text, Paragraph } = Typography;

interface Props {
  open: boolean;
  step: Step | null;
  onConfirm: () => void;
  onRegenerate: () => void;
  loading?: boolean;
}

export default function StepConfirmModal({ open, step, onConfirm, onRegenerate, loading }: Props) {
  if (!step) return null;

  return (
    <Modal
      title={`步骤完成: ${step.name}`}
      open={open}
      footer={null}
      closable={false}
      maskClosable={false}
    >
      <Space direction="vertical" style={{ width: "100%" }}>
        <div>
          <Tag color="success">完成</Tag>
          {step.duration_seconds && <Text type="secondary">耗时: {step.duration_seconds.toFixed(1)}s</Text>}
        </div>

        {step.output_files && step.output_files.length > 0 && (
          <div>
            <Text strong>输出文件:</Text>
            <Paragraph>
              {step.output_files.map((f) => (
                <Tag key={f}>{f}</Tag>
              ))}
            </Paragraph>
          </div>
        )}

        {step.comfyui_results && step.comfyui_results.length > 0 && (
          <div>
            <Text strong>ComfyUI 生成结果: {step.comfyui_results.length} 个</Text>
          </div>
        )}

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 12, marginTop: 16 }}>
          <Button onClick={onRegenerate} disabled={loading}>
            重新生成
          </Button>
          <Button type="primary" onClick={onConfirm} loading={loading}>
            确认并继续
          </Button>
        </div>
      </Space>
    </Modal>
  );
}
