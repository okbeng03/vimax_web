import { useState } from "react";
import { Table, Tag, Button } from "antd";
import { FileTextOutlined } from "@ant-design/icons";
import type { OperationLog } from "../../api/operations";
import LogDetailModal from "./LogDetailModal";

const TYPE_COLORS: Record<string, string> = {
  edit_file: "blue",
  confirm_result: "green",
  reject_result: "red",
  regenerate_step: "orange",
};

const TYPE_LABELS: Record<string, string> = {
  edit_file: "编辑文件",
  confirm_result: "确认结果",
  reject_result: "拒绝结果",
  regenerate_step: "重新生成",
};

interface Props {
  logs: OperationLog[];
  loading?: boolean;
  total?: number;
  onPageChange?: (page: number) => void;
}

export default function LogTable({ logs, loading, total, onPageChange }: Props) {
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailLog, setDetailLog] = useState<OperationLog | null>(null);

  const showDetail = (log: OperationLog) => {
    setDetailLog(log);
    setDetailOpen(true);
  };

  const columns = [
    {
      title: "时间",
      dataIndex: "created_at",
      key: "created_at",
      width: 180,
      render: (v: string) => new Date(v + "Z").toLocaleString("zh-CN"),
    },
    {
      title: "操作类型",
      dataIndex: "operation_type",
      key: "type",
      width: 120,
      render: (v: string) => <Tag color={TYPE_COLORS[v] || "default"}>{TYPE_LABELS[v] || v}</Tag>,
    },
    {
      title: "对象",
      dataIndex: "target_name",
      key: "target",
      width: 200,
    },
    {
      title: "摘要",
      dataIndex: "summary",
      key: "summary",
      ellipsis: true,
    },
    {
      title: "操作者",
      dataIndex: "user_name",
      key: "user",
      width: 80,
    },
    {
      title: "",
      key: "actions",
      width: 60,
      render: (_: unknown, record: OperationLog) =>
        record.details ? (
          <Button
            type="link"
            size="small"
            icon={<FileTextOutlined />}
            onClick={() => showDetail(record)}
          >
            详情
          </Button>
        ) : null,
    },
  ];

  return (
    <>
      <Table
        dataSource={logs}
        columns={columns}
        rowKey="id"
        loading={loading}
        size="small"
        pagination={{
          total,
          pageSize: 50,
          onChange: onPageChange,
          showSizeChanger: false,
        }}
      />
      <LogDetailModal
        open={detailOpen}
        title={detailLog?.summary || detailLog?.operation_type || ""}
        details={detailLog?.details ?? null}
        onClose={() => setDetailOpen(false)}
      />
    </>
  );
}
