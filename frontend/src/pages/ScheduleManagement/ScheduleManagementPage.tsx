import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Table,
  Tag,
  Space,
  Button,
  message,
  Typography,
  Popconfirm,
  Badge,
  InputNumber,
  Tabs,
  Tooltip,
} from "antd";
import {
  ReloadOutlined,
  SyncOutlined,
  StopOutlined,
  CloudServerOutlined,
  InboxOutlined,
  EyeOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import {
  fetchScheduleProjects,
  fetchScheduleResults,
  syncScheduleResults,
  cancelScheduleProject,
  setScheduleProjectPriority,
  fetchScheduleHealth,
  pauseScheduler,
  resumeScheduler,
} from "../../api/schedule";
import type {
  ScheduleProject,
  ScheduleResult,
} from "../../types/schedule";

const { Title, Text } = Typography;

const TASK_STATUS: Record<string, { color: string; label: string }> = {
  QUEUED: { color: "default", label: "排队中" },
  RUNNING: { color: "processing", label: "执行中" },
  SUCCESS: { color: "success", label: "已完成" },
  FAILED: { color: "error", label: "失败" },
  CANCELED: { color: "warning", label: "已取消" },
};

export default function ScheduleManagementPage() {
  const navigate = useNavigate();
  const [health, setHealth] = useState<string>("checking");
  const [projects, setProjects] = useState<ScheduleProject[]>([]);
  const [results, setResults] = useState<ScheduleResult[]>([]);
  const [loadingProjects, setLoadingProjects] = useState(false);
  const [loadingResults, setLoadingResults] = useState(false);
  const [syncingResults, setSyncingResults] = useState(false);
  const [schedulerPaused, setSchedulerPaused] = useState(false);

  const loadHealth = useCallback(async () => {
    try {
      const h = await fetchScheduleHealth();
      setHealth(h.status === "ok" ? "ok" : "unavailable");
    } catch {
      setHealth("unavailable");
    }
  }, []);

  const loadProjects = useCallback(async () => {
    setLoadingProjects(true);
    try {
      setProjects(await fetchScheduleProjects());
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "获取调度项目失败");
    } finally {
      setLoadingProjects(false);
    }
  }, []);

  const loadResults = useCallback(async () => {
    setLoadingResults(true);
    try {
      setResults(await fetchScheduleResults(false));
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "获取调度结果失败");
    } finally {
      setLoadingResults(false);
    }
  }, []);

  const refreshAll = useCallback(() => {
    loadHealth();
    loadProjects();
    loadResults();
  }, [loadHealth, loadProjects, loadResults]);

  useEffect(() => {
    refreshAll();
  }, [refreshAll]);

  const handleSyncResults = async () => {
    const items = results
      .filter((r) => !r.synced && r.project_id != null)
      .map((r) => ({ task_id: r.business_task_id, project_id: Number(r.project_id) }));
    if (items.length === 0) {
      message.info("暂无可同步的调度结果");
      return;
    }
    setSyncingResults(true);
    try {
      const r = await syncScheduleResults(items);
      // 接口为异步触发：后台串行执行（避免 SQLite 锁表），前端不等待结果
      message.success(`已开始同步 ${r.count} 条调度结果，完成后可在后端日志查看统计`);
      // 后台任务需要一段时间，延迟刷新一次以便尽快看到已同步的条目
      setTimeout(() => refreshAll(), 3000);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "触发调度结果同步失败");
    } finally {
      setSyncingResults(false);
    }
  };

  const handleCancel = async (projectId: string) => {
    try {
      const r = await cancelScheduleProject(projectId);
      message.success(r.cancelled ? "已取消该项目全部任务" : "取消失败");
      refreshAll();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "取消任务失败");
    }
  };

  const handlePriorityChange = async (projectId: string, value: number | null) => {
    if (value == null) return;
    try {
      await setScheduleProjectPriority(projectId, value);
      message.success("优先级已更新");
      refreshAll();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "更新优先级失败");
    }
  };

  const handlePauseScheduler = async () => {
    try {
      await pauseScheduler();
      setSchedulerPaused(true);
      message.success("调度器已暂停，不再派发新任务");
      refreshAll();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "暂停调度器失败");
    }
  };

  const handleResumeScheduler = async () => {
    try {
      await resumeScheduler();
      setSchedulerPaused(false);
      message.success("调度器已恢复");
      refreshAll();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "恢复调度器失败");
    }
  };

  const projectColumns: ColumnsType<ScheduleProject> = [
    {
      title: "项目 ID",
      dataIndex: "project_id",
      width: 90,
    },
    {
      title: "项目名称",
      dataIndex: "name",
      render: (v: string) => v || "-",
    },
    {
      title: "状态",
      dataIndex: "paused",
      width: 90,
      render: (paused: boolean) =>
        paused ? (
          <Tag icon={<PauseCircleOutlined />} color="warning">
            已暂停
          </Tag>
        ) : (
          <Tag color="success">运行中</Tag>
        ),
    },
    {
      title: "优先级",
      dataIndex: "priority",
      width: 140,
      render: (v: number, record) => (
        <InputNumber
          size="small"
          min={0}
          max={100}
          value={v}
          onChange={(nv) => handlePriorityChange(record.project_id, nv)}
          style={{ width: 80 }}
        />
      ),
    },
    {
      title: "统计",
      key: "stats",
      width: 260,
      render: (_, record) => {
        const s = record.stats || {};
        return (
          <Space size={4} wrap>
            <Tag>总任务 {s.total ?? 0}</Tag>
            <Tag>排队 {s.pending ?? 0}</Tag>
            <Tag color="success">成功 {s.success ?? 0}</Tag>
            <Tag color="error">失败 {s.failed ?? 0}</Tag>
          </Space>
        );
      },
    },
    {
      title: "操作",
      key: "actions",
      width: 200,
      render: (_, record) => {
        const hasActive = (record.stats?.pending ?? 0) > 0;
        return (
          <Space
            onClick={(e) => e.stopPropagation()}
          >
            <Button
              size="small"
              icon={<EyeOutlined />}
              onClick={() => navigate(`/schedule/projects/${record.project_id}`)}
            >
              查看任务
            </Button>
            <Popconfirm
              title="取消该项目全部未完成任务？"
              disabled={!hasActive}
              onConfirm={() => handleCancel(record.project_id)}
            >
              <Button
                danger
                size="small"
                icon={<StopOutlined />}
                disabled={!hasActive}
              >
                取消任务
              </Button>
            </Popconfirm>
          </Space>
        );
      },
    },
  ];

  const resultColumns: ColumnsType<ScheduleResult> = [
    { title: "任务 ID", dataIndex: "business_task_id", width: 140 },
    { title: "工作流", dataIndex: "workflow_name", render: (v: string | null) => v || "-" },
    {
      title: "状态",
      dataIndex: "status",
      width: 100,
      render: (v: string | null) => {
        const s = TASK_STATUS[v || ""] || { color: "default", label: v || "-" };
        return <Tag color={s.color}>{s.label}</Tag>;
      },
    },
    {
      title: "文件",
      dataIndex: "file_path",
      render: (v: string | null) => (
        <Text type="secondary" ellipsis style={{ maxWidth: 280 }}>
          {v || "-"}
        </Text>
      ),
    },
    {
      title: "已回传",
      dataIndex: "synced",
      width: 90,
      render: (v: boolean) => (v ? <Badge status="success" text="是" /> : <Badge status="default" text="否" />),
    },
  ];

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 16,
        }}
      >
        <Title level={4} style={{ margin: 0 }}>
          调度管理
        </Title>
        <Space>
          <Badge
            status={health === "ok" ? "success" : health === "unavailable" ? "error" : "processing"}
            text={health === "ok" ? "调度服务在线" : health === "unavailable" ? "调度服务离线" : "检查中"}
          />
          <Tooltip title={schedulerPaused ? "恢复调度器继续派发任务" : "暂停调度器，不再派发新任务"}>
            {schedulerPaused ? (
              <Button type="primary" icon={<PlayCircleOutlined />} onClick={handleResumeScheduler}>
                恢复调度
              </Button>
            ) : (
              <Button icon={<PauseCircleOutlined />} onClick={handlePauseScheduler}>
                暂停调度
              </Button>
            )}
          </Tooltip>
          <Button icon={<ReloadOutlined />} onClick={refreshAll}>
            刷新
          </Button>
        </Space>
      </div>

      <Tabs
        items={[
          {
            key: "projects",
            label: (
              <span>
                <CloudServerOutlined /> 调度项目
              </span>
            ),
            children: (
              <Table<ScheduleProject>
                rowKey="project_id"
                columns={projectColumns}
                dataSource={projects}
                loading={loadingProjects}
                pagination={false}
                onRow={(record) => ({
                  onClick: () => navigate(`/schedule/projects/${record.project_id}`),
                  style: { cursor: "pointer" },
                })}
              />
            ),
          },
          {
            key: "results",
            label: (
              <span>
                <InboxOutlined /> 调度结果
              </span>
            ),
            children: (
              <div>
                <div style={{ marginBottom: 12, textAlign: "right" }}>
                  <Tooltip title="将调度器中的成功/失败结果回传到本地项目">
                    <Button
                      type="primary"
                      icon={<SyncOutlined />}
                      loading={syncingResults}
                      onClick={handleSyncResults}
                    >
                      同步选中结果到本地
                    </Button>
                  </Tooltip>
                </div>
                <Table
                  rowKey="business_task_id"
                  columns={resultColumns}
                  dataSource={results}
                  loading={loadingResults}
                  pagination={{ pageSize: 20 }}
                />
              </div>
            ),
          },
        ]}
      />
    </div>
  );
}
