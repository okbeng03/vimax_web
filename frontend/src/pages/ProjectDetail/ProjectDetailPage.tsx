import { useEffect, useState, useCallback, useRef } from "react";
import { useParams } from "react-router-dom";
import { Tabs, Typography, Tag, Spin, message, Space, Button, Modal } from "antd";
import { PlayCircleOutlined, StopOutlined, ForwardOutlined } from "@ant-design/icons";
import { useProjectStore } from "../../stores/projectStore";
import { useExecutionStore } from "../../stores/executionStore";
import { fetchRunningProject, fetchProjectProgress } from "../../api/projects";
import { useStdout } from "../../hooks/useStdout";
import MonacoEditor from "@monaco-editor/react";
import FullscreenWrapper from "../../components/common/FullscreenWrapper";
import ExecutionTab from "./ExecutionTab";
import FileTab from "./FileTab";
import GenerationsTab from "./GenerationsTab";
import LogsTab from "./LogsTab";
import ProgressBar from "../../components/progress/ProgressBar";
import ProjectStatsPanel from "../../components/stats/ProjectStatsPanel";
import type { ProgressStep } from "../../types/project";

const { Title, Text } = Typography;

const STATUS_MAP: Record<string, { color: string; label: string }> = {
  idle: { color: "default", label: "就绪" },
  running: { color: "processing", label: "生成中" },
  completed: { color: "success", label: "已完成" },
  failed: { color: "error", label: "失败" },
};

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const pid = Number(id);
  const { currentProject, loading, fetchProject, updateConfig } = useProjectStore();
  const { steps, execute, kill, fetchSteps } = useExecutionStore();

  const [yamlContent, setYamlContent] = useState("");
  const [pythonContent, setPythonContent] = useState("");
  const configLoadedRef = useRef(false);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState("config");

  // ---------- global running state ----------
  const [globalRunningProjectId, setGlobalRunningProjectId] = useState<number | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [retryLoading, setRetryLoading] = useState(false);

  // Only connect WS when BOTH project has "running" status AND
  // vimax_runner confirms a subprocess is actually alive for this project.
  // (monitor_completion updates step status but leaves project.status="running"
  //  between steps, causing false WS connections)
  const isProcessRunning =
    currentProject?.status === "running" && globalRunningProjectId === pid;
  const { outputLines, finalStatus, stepReady, isConnected, clear } = useStdout(
    pid,
    isProcessRunning,
    currentProject?.status,
  );

  // ---------- progress bar ----------
  const [progressSteps, setProgressSteps] = useState<ProgressStep[]>([]);
  const [currentStepOrder, setCurrentStepOrder] = useState<number | null>(null);
  const [continueLoading, setContinueLoading] = useState(false);

  const refreshGlobalRunning = useCallback(async () => {
    try {
      const r = await fetchRunningProject();
      setGlobalRunningProjectId(r.project_id);
    } catch {
      // ignore
    }
  }, []);

  const loadProgress = useCallback(async () => {
    if (!id) return;
    try {
      const p = await fetchProjectProgress(Number(id));
      setProgressSteps(p.steps);
      setCurrentStepOrder(p.current_step_order);
    } catch {
      // ignore
    }
  }, [id]);

  useEffect(() => {
    refreshGlobalRunning();
  }, [refreshGlobalRunning]);

  // ---------- project data ----------
  useEffect(() => {
    if (id) {
      configLoadedRef.current = false;  // reset for new project
      fetchProject(Number(id));
      loadProgress();
    }
  }, [id, fetchProject, loadProgress]);

  // Default tab: "idle" → config, all others → execution
  useEffect(() => {
    if (currentProject) {
      setActiveTab(currentProject.status === "idle" ? "config" : "execution");
    }
  }, [currentProject?.id]);  // only on project change, not on status updates

  // Refresh progress + steps when step_ready arrives
  useEffect(() => {
    if (!stepReady) return;
    setGlobalRunningProjectId(null); // disable WS, process paused awaiting user confirmation
    if (id) {
      fetchProject(Number(id), { silent: true });
      fetchSteps(Number(id));
      loadProgress();
    }
  }, [stepReady, fetchSteps, loadProgress, id, fetchProject]);

  // On final status (completed / failed): fetch full data without triggering Spin
  const isSelfRunning = currentProject?.status === "running";
  useEffect(() => {
    if (!finalStatus) return;
    refreshGlobalRunning();
    if (id) {
      fetchProject(Number(id), { silent: true });
      fetchSteps(Number(id));
      loadProgress();
    }
  }, [finalStatus, refreshGlobalRunning, fetchSteps, loadProgress, id, fetchProject]);

  // Only sync editor content on initial load — never overwrite user edits
  useEffect(() => {
    if (!configLoadedRef.current && currentProject?.config) {
      setYamlContent(currentProject.config.yaml_content);
      setPythonContent(currentProject.config.config_py_content);
      configLoadedRef.current = true;
    }
  }, [currentProject]);

  const handleSaveConfig = async () => {
    if (!id) return;
    setSaving(true);
    try {
      await updateConfig(Number(id), { yaml_content: yamlContent, config_py_content: pythonContent });
      message.success("配置已保存到 working_dir");
    } catch {
      message.error("配置保存失败");
    } finally {
      setSaving(false);
    }
  };

  // ---------- 开始生成 / 确认并继续 / 强制停止 ----------
  const isOtherRunning = globalRunningProjectId !== null && globalRunningProjectId !== pid;

  // Show "确认并继续" when:
  //   a) WS is connected and sent step_ready, OR
  //   b) Progress data from DB shows current step is fully_complete (handles page refresh / late entry)
  const currentStepIsComplete =
    progressSteps.some(
      (ps) => ps.name === currentProject?.current_step_name && ps.status === "success",
    );
  const showContinue = isSelfRunning && (!!stepReady || currentStepIsComplete);

  // Find the first non-success step for resume logic
  const firstNonSuccess = progressSteps.find(
    (s) => s.status !== "success",
  );
  const hasCompletedSteps = progressSteps.some((s) => s.status === "success");
  const startAction: "start" | "retry_step" =
    hasCompletedSteps && firstNonSuccess ? "retry_step" : "start";
  const startStepName: string | undefined =
    hasCompletedSteps && firstNonSuccess ? firstNonSuccess.name : undefined;
  const startLabel = hasCompletedSteps ? "继续生成" : "开始生成";

  const handleStart = async () => {
    if (!id) return;
    setActionLoading(true);
    clear();
    try {
      await execute(pid, startAction, startStepName);
      setGlobalRunningProjectId(pid);
      useProjectStore.setState((state) => ({
        currentProject: state.currentProject
          ? { ...state.currentProject, status: "running" as const }
          : null,
      }));
      setActiveTab("execution");
      message.success(startAction === "retry_step" ? "已从失败步骤继续生成" : "ViMax 已启动");
      loadProgress();
      fetchSteps(pid);
    } catch {
      message.error("启动失败");
    } finally {
      setActionLoading(false);
    }
  };

  const handleContinue = async () => {
    if (!id) return;
    setContinueLoading(true);
    try {
      // 1. Save editor config to working_dir
      await updateConfig(pid, { yaml_content: yamlContent, config_py_content: pythonContent });
    } catch {
      // config save non-fatal — continue anyway with whatever is on disk
    }

    clear(); // new step starts → truncate terminal output
    try {
      // 2. Execute continue (backend syncs working_dir → VIMAX_ROOT)
      await execute(pid, "continue");

      // 3. Set running state → WS connects
      setGlobalRunningProjectId(pid);
      useProjectStore.setState((state) => ({
        currentProject: state.currentProject
          ? { ...state.currentProject, status: "running" as const }
          : null,
      }));

      message.success("已确认，执行下一步");
      loadProgress();
      fetchSteps(pid);
    } catch {
      message.error("继续执行失败");
    } finally {
      setContinueLoading(false);
    }
  };

  const handleKill = () => {
    Modal.confirm({
      title: "确认强制终止",
      content: "这会终止正在运行的 ViMax 进程，当前步骤将标记为失败。",
      okText: "确认终止",
      cancelText: "取消",
      okType: "danger",
      onOk: async () => {
        await kill(pid);
        setGlobalRunningProjectId(null);
        // Update project status so UI reflects "failed" immediately
        useProjectStore.setState((state) => ({
          currentProject: state.currentProject
            ? { ...state.currentProject, status: "failed" as const }
            : null,
        }));
        message.info("已终止");
        fetchSteps(pid);
        loadProgress();
      },
    });
  };

  const handleRetry = async (stepName: string) => {
    if (!id) return;
    setRetryLoading(true);
    setGlobalRunningProjectId(null); // disconnect existing WS
    clear();
    try {
      await execute(pid, "retry_step", stepName);
      setGlobalRunningProjectId(pid);
      useProjectStore.setState((state) => ({
        currentProject: state.currentProject
          ? { ...state.currentProject, status: "running" as const }
          : null,
      }));
      setActiveTab("execution");
      message.success(`已从 "${stepName}" 开始重新生成`);
      loadProgress();
      fetchSteps(pid);
    } catch {
      message.error("重试失败");
    } finally {
      setRetryLoading(false);
    }
  };
  if (loading || !currentProject) {
    return (
      <div style={{ textAlign: "center", padding: 100 }}>
        <Spin size="large" />
      </div>
    );
  }

  const statusInfo = STATUS_MAP[currentProject.status] || { color: "default", label: currentProject.status };

  const tabItems = [
    {
      key: "config",
      label: "配置",
      children: (
        <div>
          <div style={{ marginBottom: 16, display: "flex", gap: 16 }}>
            <div style={{ flex: 1 }}>
              <FullscreenWrapper toolbar={<Title level={5} style={{ margin: 0 }}>idea2video.yaml</Title>}>
                {(fs: boolean) => (
                  <div style={{ height: fs ? "100%" : 400 }}>
                    <MonacoEditor
                      height="100%"
                      language="yaml"
                      value={yamlContent}
                      onChange={(v) => setYamlContent(v || "")}
                      theme="vs-dark"
                      options={{ minimap: { enabled: false }, fontSize: 13 }}
                    />
                  </div>
                )}
              </FullscreenWrapper>
            </div>
            <div style={{ flex: 1 }}>
              <FullscreenWrapper toolbar={<Title level={5} style={{ margin: 0 }}>config.py</Title>}>
                {(fs: boolean) => (
                  <div style={{ height: fs ? "100%" : 400 }}>
                    <MonacoEditor
                      height="100%"
                      language="python"
                      value={pythonContent}
                      onChange={(v) => setPythonContent(v || "")}
                      theme="vs-dark"
                      options={{ minimap: { enabled: false }, fontSize: 13 }}
                    />
                  </div>
                )}
              </FullscreenWrapper>
            </div>
          </div>
          <button onClick={handleSaveConfig} disabled={saving} style={{ padding: "8px 24px", cursor: "pointer" }}>
            {saving ? "保存中..." : "保存配置"}
          </button>
        </div>
      ),
    },
    {
      key: "execution",
      label: "执行",
      children: (
        <ExecutionTab
          projectId={currentProject.id}
          projectStatus={currentProject.status}
          outputLines={outputLines}
          isConnected={isConnected}
          finalStatus={finalStatus}
          stepReady={stepReady}
        />
      ),
    },
    {
      key: "files",
      label: "文件",
      children: <FileTab projectId={currentProject.id} visible={activeTab === "files"} />,
    },
    {
      key: "generations",
      label: currentProject.unconfirmed_count > 0 ? (
        <span>
          结果 <Tag color="red">{currentProject.unconfirmed_count}</Tag>
        </span>
      ) : (
        "结果"
      ),
      children: <GenerationsTab projectId={currentProject.id} isRunning={isProcessRunning} visible={activeTab === "generations"} />,
    },
    {
      key: "logs",
      label: "日志",
      children: <LogsTab projectId={currentProject.id} visible={activeTab === "logs"} />,
    },
    { key: "stats", label: "统计", children: <ProjectStatsPanel projectId={currentProject.id} visible={activeTab === "stats"} /> },
  ];

  return (
    <div>
      {/* ===== 标题栏：项目名 + 状态 + 核心操作按钮 ===== */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: 12,
        }}
      >
        <div>
          <Title level={4} style={{ marginBottom: 8 }}>
            {currentProject.name}
          </Title>
          <Space>
            <Tag color={statusInfo.color}>{statusInfo.label}</Tag>
            <Text type="secondary">{currentProject.creative_description}</Text>
          </Space>
        </div>

        <div style={{ flexShrink: 0, marginLeft: 24, display: "flex", gap: 8 }}>
          {isProcessRunning && (
            <Button danger icon={<StopOutlined />} size="large" onClick={handleKill}>
              强制停止
            </Button>
          )}
          {!isProcessRunning && showContinue && (
            <Button
              type="primary"
              ghost
              icon={<ForwardOutlined />}
              size="large"
              onClick={handleContinue}
              loading={continueLoading}
            >
              确认并继续下一步
            </Button>
          )}
          {!isProcessRunning && !showContinue && (
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              size="large"
              onClick={handleStart}
              loading={actionLoading}
              disabled={isOtherRunning}
            >
              {isOtherRunning ? "其他项目运行中" : startLabel}
            </Button>
          )}
        </div>
      </div>

      {/* ===== 进度条（始终可见） ===== */}
      <div
        style={{
          marginBottom: 12,
          padding: "8px 16px",
          background: "#fafafa",
          borderRadius: 8,
          border: "1px solid #f0f0f0",
        }}
      >
        <ProgressBar
          steps={progressSteps}
          currentStepOrder={currentStepOrder}
          onRetry={handleRetry}
          retryDisabled={isProcessRunning || retryLoading}
        />
        {currentProject?.current_step_name && (
          <Text type="secondary" style={{ fontSize: 12 }}>
            当前步骤: <Text strong>{currentProject.current_step_name}</Text>
          </Text>
        )}
      </div>

      <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />
    </div>
  );
}
