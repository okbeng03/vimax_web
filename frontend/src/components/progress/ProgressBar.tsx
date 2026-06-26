import { Steps, Tooltip, Popconfirm } from "antd";
import {
  LoadingOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  ClockCircleOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import type { ProgressStep } from "../../types/project";

const WINDOW_SIZE = 5;

const STATUS_ICON: Record<string, React.ReactNode> = {
  success: <CheckCircleOutlined />,
  running: <LoadingOutlined spin />,
  failed: <ExclamationCircleOutlined />,
  pending: <ClockCircleOutlined />,
  new: <ClockCircleOutlined />,
};

const STATUS_COLOR: Record<string, string> = {
  success: "#52c41a",
  running: "#1677ff",
  failed: "#ff4d4f",
  pending: "#d9d9d9",
  new: "#d9d9d9",
};

const RETRYABLE_STATUSES = new Set(["success", "failed"]);

interface Props {
  steps: ProgressStep[];
  currentStepOrder: number | null;
  onRetry?: (stepName: string) => void;
  retryDisabled?: boolean;
}

export default function ProgressBar({ steps, currentStepOrder, onRetry, retryDisabled }: Props) {
  if (!steps.length) return <div style={{ color: "#999", padding: 8 }}>暂无进度步骤</div>;

  // Determine the "current" index: running step > last completed step
  let currentIdx: number;
  if (currentStepOrder !== null) {
    currentIdx = currentStepOrder;
  } else {
    // No step is running — find the last success step as the highlight anchor
    const lastSuccess = steps.reduce(
      (acc: number, s, i) => (s.status === "success" ? i : acc),
      -1,
    );
    currentIdx = lastSuccess;
  }

  const total = steps.length;

  // ── sliding window: 5 steps centered on current ──
  const half = Math.floor(WINDOW_SIZE / 2);
  let start: number;
  let end: number;

  if (currentIdx < half) {
    // near the start: show first WINDOW_SIZE steps
    start = 0;
    end = Math.min(WINDOW_SIZE, total);
  } else if (currentIdx >= total - half) {
    // near the end: show last WINDOW_SIZE steps
    start = Math.max(0, total - WINDOW_SIZE);
    end = total;
  } else {
    // middle: center window on current
    start = currentIdx - half;
    end = currentIdx + half + 1;
  }

  const visible = steps.slice(start, end);

  // Adjust current index within the visible window for antd Steps component
  const visibleCurrentIdx = currentIdx - start;

  const hasLeftMore = start > 0;
  const hasRightMore = end < total;

  const allRetryable = onRetry && !retryDisabled
    ? steps.filter((s) => RETRYABLE_STATUSES.has(s.status))
    : [];

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center" }}>
        {hasLeftMore && (
          <span style={{ color: "#bbb", fontSize: 18, marginRight: 4, flexShrink: 0 }}>
            ···
          </span>
        )}

        <div style={{ flex: 1, overflow: "hidden" }}>
          <Steps
            size="small"
            current={visibleCurrentIdx >= 0 ? visibleCurrentIdx : 0}
            status={
              steps.some((s) => s.status === "failed")
                ? "error"
                : currentIdx >= 0
                  ? "process"
                  : "wait"
            }
            items={visible.map((s) => {
              const icon = STATUS_ICON[s.status] || STATUS_ICON.pending;
              const color = STATUS_COLOR[s.status] || STATUS_COLOR.pending;
              return {
                title: <span style={{ fontSize: 12 }}>{s.label}</span>,
                icon: <span style={{ color }}>{icon}</span>,
              };
            })}
          />
        </div>

        {hasRightMore && (
          <span style={{ color: "#bbb", fontSize: 18, marginLeft: 4, flexShrink: 0 }}>
            ···
          </span>
        )}
      </div>

      {allRetryable.length > 0 && (
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            gap: 12,
            marginTop: 6,
            flexWrap: "wrap",
          }}
        >
          {allRetryable.map((s) => (
            <Popconfirm
              key={s.name}
              title={`确认重新执行「${s.label}」步骤？`}
              onConfirm={() => onRetry!(s.name)}
              okText="确认"
              cancelText="取消"
            >
              <Tooltip title={`从 "${s.label}" 步骤重新开始`}>
                <span
                  style={{
                    cursor: "pointer",
                    color: "#1677ff",
                    fontSize: 12,
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 4,
                    padding: "2px 8px",
                    borderRadius: 4,
                    border: "1px solid #1677ff",
                    userSelect: "none",
                    whiteSpace: "nowrap",
                  }}
                >
                  <ReloadOutlined style={{ fontSize: 12 }} />
                  {s.label}
                </span>
              </Tooltip>
            </Popconfirm>
          ))}
        </div>
      )}
    </div>
  );
}
