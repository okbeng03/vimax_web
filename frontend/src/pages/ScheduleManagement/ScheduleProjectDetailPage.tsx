import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Button,
  Card,
  Descriptions,
  InputNumber,
  Popconfirm,
  Space,
  Table,
  Tag,
  Typography,
  message,
  Badge,
} from "antd";
import {
  ArrowLeftOutlined,
  ReloadOutlined,
  StopOutlined,
  PauseCircleOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import {
  fetchScheduleProject,
  fetchScheduleProjectTasks,
  cancelScheduleProject,
  setScheduleProjectPriority,
} from "../../api/schedule";
import type { ScheduleProject, ScheduleTask } from "../../types/schedule";

const { Title, Text } = Typography;

const TASK_STATUS: Record<string, { color: string; label: string }> = {
  QUEUED: { color: "default", label: "排队中" },
  RUNNING: { color: "processing", label: "执行中" },
  SUCCESS: { color: "success", label: "已完成" },
  FAILED: { color: "error", label: "失败" },
  CANCELED: { color: "warning", label: "已取消" },
};

function formatTime(v: string | null): string {
  if (!v) return "-";
  const d = new Date(v);
  return isNaN(d.getTime()) ? v : d.toLocaleString();
}

export default function ScheduleProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [project, setProject] = useState<ScheduleProject | null>(null);
  const [tasks, setTasks] = useState<ScheduleTask[]>([]);
  const [loadingProject, setLoadingProject] = useState(false);
  const [loadingTasks, setLoadingTasks] = useState(false);

  const loadProject = useCallback(async () => {
    if (!id) return;
    setLoadingProject(true);
    try {
      setProject(await fetchScheduleProject(id));
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "获取调度项目失败");
    } finally {
      setLoadingProject(false);
    }
  }, [id]);

  const loadTasks = useCallback(async () => {
    if (!id) return;
    setLoadingTasks(true);
    try {
      setTasks(await fetchScheduleProjectTasks(id));
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "获取任务列表失败");
    } finally {
      setLoadingTasks(false);
    }
  }, [id]);

  useEffect(() => {
    loadProject();
    loadTasks();
  }, [loadProject, loadTasks]);

  const handleCancelAll = async () => {
    if (!id) return;
    try {
      const r = await cancelScheduleProject(id);
      message.success(r.cancelled ? "已取消该项目全部任务" : "取消失败");
      loadTasks();
      loadProject();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "取消任务失败");
    }
  };

  const handlePriorityChange = async (value: number | null) => {
    if (!id || value == null) return;
    try {
      await setScheduleProjectPriority(id, value);
      message.success("优先级已更新");
      loadProject();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "更新优先级失败");
    }
  };

  const taskColumns: ColumnsType<ScheduleTask> = [
    {
      title: "任务 ID",
      dataIndex: "business_task_id",
      width: 200,
      render: (v: string) => <Text code>{v}</Text>,
    },
    {
      title: "类型",
      dataIndex: "type",
      width: 120,
      render: (v: string | null) => v || "-",
    },
    {
      title: "状态",
      dataIndex: "status",
      width: 110,
      render: (v: string) => {
        const s = TASK_STATUS[v] || { color: "default", label: v };
        return <Tag color={s.color}>{s.label}</Tag>;
      },
    },
    {
      title: "重试次数",
      dataIndex: "retry_count",
      width: 90,
    },
    {
      title: "失败原因",
      dataIndex: "failure_reason",
      render: (v: string | null) => (
        <Text type="secondary" ellipsis style={{ maxWidth: 300 }}>
          {v || "-"}
        </Text>
      ),
    },
    {
      title: "提交时间",
      dataIndex: "created_at",
      width: 170,
      render: formatTime,
    },
    {
      title: "更新时间",
      dataIndex: "updated_at",
      width: 170,
      render: formatTime,
    },
  ];

  const s = project?.stats || { total: 0, pending: 0, success: 0, failed: 0 };

  return (
    <div>
      <Space style={{ marginBottom: 16 }} align="center">
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/schedule")}>
          返回调度管理
        </Button>
        <Title level={4} style={{ margin: 0 }}>
          项目任务
          {project ? (
            <Text type="secondary" style={{ fontWeight: 400, marginLeft: 8 }}>
              #{project.project_id} {project.name || ""}
            </Text>
          ) : null}
        </Title>
      </Space>

      <Card
        loading={loadingProject}
        style={{ marginBottom: 16 }}
        extra={
          <Button icon={<ReloadOutlined />} onClick={loadProject}>
            刷新
          </Button>
        }
      >
        {project && (
          <Descriptions size="small" column={4}>
            <Descriptions.Item label="项目 ID">{project.project_id}</Descriptions.Item>
            <Descriptions.Item label="项目名称">{project.name || "-"}</Descriptions.Item>
            <Descriptions.Item label="状态">
              {project.paused ? (
                <Tag icon={<PauseCircleOutlined />} color="warning">
                  已暂停
                </Tag>
              ) : (
                <Badge status="success" text="运行中" />
              )}
            </Descriptions.Item>
            <Descriptions.Item label="优先级">
              <InputNumber
                size="small"
                min={0}
                max={100}
                value={project.priority}
                onChange={handlePriorityChange}
                style={{ width: 80 }}
              />
            </Descriptions.Item>
            <Descriptions.Item label="总任务">{s.total ?? 0}</Descriptions.Item>
            <Descriptions.Item label="排队中">{s.pending ?? 0}</Descriptions.Item>
            <Descriptions.Item label="成功">
              <Tag color="success">{s.success ?? 0}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="失败">
              <Tag color="error">{s.failed ?? 0}</Tag>
            </Descriptions.Item>
          </Descriptions>
        )}
      </Card>

      <Card
        title={
          <Space>
            <span>任务列表</span>
            {tasks.length > 0 && <Text type="secondary">共 {tasks.length} 条</Text>}
          </Space>
        }
        extra={
          <Space>
            <Popconfirm
              title="取消该项目全部未完成任务？"
              disabled={(s.pending ?? 0) === 0}
              onConfirm={handleCancelAll}
            >
              <Button
                danger
                icon={<StopOutlined />}
                disabled={(s.pending ?? 0) === 0}
              >
                取消全部任务
              </Button>
            </Popconfirm>
            <Button icon={<ReloadOutlined />} onClick={loadTasks}>
              刷新
            </Button>
          </Space>
        }
      >
        <Table<ScheduleTask>
          rowKey="business_task_id"
          columns={taskColumns}
          dataSource={tasks}
          loading={loadingTasks}
          pagination={{ pageSize: 20 }}
          locale={{ emptyText: "暂无任务记录" }}
        />
      </Card>
    </div>
  );
}
