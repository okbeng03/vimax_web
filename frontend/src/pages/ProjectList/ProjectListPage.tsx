import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Table, Button, Input, Select, Space, Tag, Popconfirm, message, Typography, Progress } from "antd";
import { PlusOutlined, SearchOutlined, DeleteOutlined } from "@ant-design/icons";
import { useProjectStore } from "../../stores/projectStore";
import ProjectForm from "../../components/project/ProjectForm";
import type { ProjectListItem } from "../../types/project";

const { Title } = Typography;

const STATUS_MAP: Record<string, { color: string; label: string }> = {
  idle: { color: "default", label: "就绪" },
  running: { color: "processing", label: "生成中" },
  completed: { color: "success", label: "已完成" },
  failed: { color: "error", label: "失败" },
};

export default function ProjectListPage() {
  const { projects, total, loading, fetchProjects, deleteProject } = useProjectStore();
  const navigate = useNavigate();
  const [modalOpen, setModalOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string | undefined>();

  useEffect(() => {
    fetchProjects({ status: statusFilter, search, page: 1 });
  }, [fetchProjects, statusFilter, search]);

  const handleDelete = async (id: number) => {
    await deleteProject(id);
    message.success("项目已删除");
    fetchProjects({ status: statusFilter, search, page: 1 });
  };

  const columns = [
    {
      title: "项目名称",
      dataIndex: "name",
      key: "name",
      render: (name: string, record: ProjectListItem) => (
        <a onClick={() => navigate(`/projects/${record.id}`)}>{name}</a>
      ),
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 100,
      render: (status: string) => {
        const s = STATUS_MAP[status] || { color: "default", label: status };
        return <Tag color={s.color}>{s.label}</Tag>;
      },
    },
    {
      title: "步骤进度",
      key: "progress",
      width: 180,
      render: (_: unknown, record: ProjectListItem) => {
        const summary = record.step_summary;
        if (!summary) return "-";
        const pct = summary.total > 0 ? Math.round((summary.completed / summary.total) * 100) : 0;
        const isRunning = record.status === "running";
        return (
          <Progress
            percent={pct}
            size="small"
            status={record.status === "failed" ? "exception" : isRunning ? "active" : undefined}
            format={() => `${summary.completed}/${summary.total}`}
          />
        );
      },
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      key: "created_at",
      width: 180,
      render: (v: string) => new Date(v + "Z").toLocaleString("zh-CN"),
    },
    {
      title: "操作",
      key: "actions",
      width: 100,
      render: (_: unknown, record: ProjectListItem) => (
        <Space>
          <Button size="small" type="link" onClick={() => navigate(`/projects/${record.id}`)}>
            进入
          </Button>
          <Popconfirm title="确定删除此项目？" onConfirm={() => handleDelete(record.id)} okText="确定" cancelText="取消">
            <Button size="small" type="link" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>
          项目列表
        </Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          新建项目
        </Button>
      </div>

      <Space style={{ marginBottom: 16 }}>
        <Input
          placeholder="搜索项目"
          prefix={<SearchOutlined />}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ width: 240 }}
          allowClear
        />
        <Select
          placeholder="状态筛选"
          value={statusFilter}
          onChange={(v) => setStatusFilter(v)}
          allowClear
          style={{ width: 140 }}
          options={[
            { value: "idle", label: "就绪" },
            { value: "running", label: "生成中" },
            { value: "completed", label: "已完成" },
            { value: "failed", label: "失败" },
          ]}
        />
      </Space>

      <Table
        dataSource={projects}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={{
          total,
          pageSize: 20,
          onChange: (page) => fetchProjects({ status: statusFilter, search, page }),
        }}
      />

      <ProjectForm
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onCreated={() => fetchProjects({ status: statusFilter, search, page: 1 })}
      />
    </div>
  );
}
