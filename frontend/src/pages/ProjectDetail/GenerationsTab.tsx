import { useState, useEffect, useCallback, useRef } from "react";
import { Select, Switch, Button, Space, Empty, Spin, Typography, Divider, Modal, InputNumber, Radio, message } from "antd";
import { EyeOutlined, EyeInvisibleOutlined } from "@ant-design/icons";
import ResultGrid from "../../components/generation/ResultGrid";
import * as generationsApi from "../../api/generations";
import * as stepsApi from "../../api/steps";
import type { GenerationResult, GachaRequest } from "../../types/generation";

const { Text } = Typography;

interface Props {
  projectId: number;
  isRunning?: boolean;
  visible: boolean;
}

export default function GenerationsTab({ projectId, isRunning, visible }: Props) {
  const [results, setResults] = useState<GenerationResult[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [stepNames, setStepNames] = useState<string[]>([]);
  const [filterStep, setFilterStep] = useState<string | undefined>();
  const [filterConfirmed, setFilterConfirmed] = useState<string>("unconfirmed"); // all / unconfirmed / confirmed
  const [page, setPage] = useState(1);
  const [collapseConfirmed, setCollapseConfirmed] = useState(true);
  const [sortBy, setSortBy] = useState<string>("scene_shot");
  const [sortOrder, setSortOrder] = useState<string>("asc");
  const pageSize = 20;

  // Gacha modal state
  const [gachaOpen, setGachaOpen] = useState(false);
  const [gachaTargetId, setGachaTargetId] = useState<number | null>(null);
  const [gachaType, setGachaType] = useState<"last_frame" | "first_frame" | "video">("last_frame");
  const [gachaScene, setGachaScene] = useState(1);
  const [gachaShot, setGachaShot] = useState(2);
  const [gachaLoading, setGachaLoading] = useState(false);

  const loadResults = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = {
        page,
        page_size: pageSize,
        sort_by: sortBy,
        sort_order: sortOrder,
      };
      if (filterStep) params.step_name = filterStep;
      if (filterConfirmed === "unconfirmed") params.confirmed = false;
      if (filterConfirmed === "confirmed") params.confirmed = true;
      const data = await generationsApi.fetchGenerations(projectId, params);
      setResults(data.generations);
      setTotal(data.total);
      setTotalPages(data.total_pages || 1);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [projectId, page, filterStep, filterConfirmed, sortBy, sortOrder]);

  // Load step names for filter dropdown
  useEffect(() => {
    stepsApi.fetchSteps(projectId).then((data) => {
      setStepNames(data.steps.map((s) => s.name));
    }).catch(() => {});
  }, [projectId]);

  // Load results on mount / filter change / page change
  useEffect(() => {
    loadResults();
  }, [loadResults]);

  // Load once when user switches to this tab
  useEffect(() => {
    if (visible) loadResults();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible]);

  // Poll while running AND tab is visible
  useEffect(() => {
    if (!isRunning || !visible) return;
    const timer = setInterval(loadResults, 5000);
    return () => clearInterval(timer);
  }, [isRunning, visible, loadResults]);

  // Reload when step completes (isRunning true → false)
  const prevIsRunningRef = useRef(isRunning);
  useEffect(() => {
    if (prevIsRunningRef.current === true && isRunning === false && visible) {
      loadResults();
    }
    prevIsRunningRef.current = isRunning;
  }, [isRunning, visible, loadResults]);

  const displayResults = collapseConfirmed ? results.filter((r) => !r.confirmed) : results;

  const handleConfirm = async (generationId: number) => {
    try {
      await generationsApi.confirmGeneration(projectId, generationId);
      setResults((prev) =>
        prev.map((r) => (r.id === generationId ? { ...r, confirmed: true } : r)),
      );
      message.success("已确认");
    } catch {
      message.error("确认失败");
    }
  };

  const handleCancel = async (generationId: number) => {
    try {
      const res = await generationsApi.cancelGeneration(projectId, generationId);
      setResults((prev) =>
        prev.map((r) => (r.id === generationId ? { ...r, cancelled: true, confirmed: false } : r)),
      );
      message.success(res.was_confirmed ? "已取消确认并归档至 caches" : "已取消，文件归档至 caches");
    } catch {
      message.error("取消失败");
    }
  };

  const handleRecover = async (generationId: number) => {
    try {
      await generationsApi.recoverGeneration(projectId, generationId);
      setResults((prev) =>
        prev.map((r) => (r.id === generationId ? { ...r, cancelled: false, storage_path: r.file_path } : r)),
      );
      message.success("已恢复");
    } catch {
      message.error("恢复失败");
    }
  };

  const handleOpenGacha = (generationId: number) => {
    // Infer gacha type from result
    const result = results.find((r) => r.id === generationId);
    let inferredType: "last_frame" | "first_frame" | "video" = "video";
    if (result) {
      if (result.generation_type === "first_frame") inferredType = "first_frame";
      else if (result.generation_type === "last_frame") inferredType = "last_frame";
      else if (result.generation_type === "video") inferredType = "video";
    }
    setGachaType(inferredType);
    setGachaTargetId(generationId);
    setGachaOpen(true);
  };

  const handleGachaSubmit = async () => {
    if (!gachaTargetId) return;
    setGachaLoading(true);
    try {
      const body: GachaRequest = { gacha_type: gachaType, scene: gachaScene, shot: gachaShot };
      await generationsApi.gachaGeneration(projectId, gachaTargetId, body);
      message.success("抽卡已启动，ViMax 运行中...");
      setGachaOpen(false);
      // Refresh after a delay
      setTimeout(() => loadResults(), 3000);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "抽卡失败");
    } finally {
      setGachaLoading(false);
    }
  };

  const handleRetry = (generationId: number) => {
    generationsApi
      .retryGeneration(projectId, generationId, { modified_params: {} })
      .then(() => {
        message.success("已重新提交");
        loadResults();
      })
      .catch(() => message.error("重试失败"));
  };

  const handlePageChange = (newPage: number) => {
    setPage(newPage);
  };

  return (
    <div>
      {/* Filter bar */}
      <Space style={{ marginBottom: 16 }} wrap>
        <Select
          placeholder="步骤筛选"
          value={filterStep}
          onChange={(v) => {
            setFilterStep(v);
            setPage(1);
          }}
          allowClear
          style={{ width: 160 }}
          options={stepNames.map((n) => ({ value: n, label: n }))}
        />
        <Select
          value={filterConfirmed}
          onChange={(v) => {
            setFilterConfirmed(v);
            setPage(1);
          }}
          style={{ width: 120 }}
          options={[
            { value: "all", label: "全部" },
            { value: "unconfirmed", label: "未确认" },
            { value: "confirmed", label: "已确认" },
          ]}
        />
        <Button
          icon={collapseConfirmed ? <EyeOutlined /> : <EyeInvisibleOutlined />}
          onClick={() => setCollapseConfirmed(!collapseConfirmed)}
        >
          {collapseConfirmed ? "展开全部" : "收起已确认"}
        </Button>
        <Select
          value={sortBy}
          onChange={(v) => { setSortBy(v); setPage(1); }}
          style={{ width: 120 }}
          options={[
            { value: "created_at", label: "按时间" },
            { value: "scene_shot", label: "按场景+镜头" },
            { value: "scene", label: "按场景" },
            { value: "shot", label: "按镜头" },
          ]}
        />
        <Button
          size="small"
          onClick={() => { setSortOrder(sortOrder === "asc" ? "desc" : "asc"); setPage(1); }}
        >
          {sortOrder === "asc" ? "↑ 升序" : "↓ 降序"}
        </Button>
      </Space>

      {/* Content */}
      {loading && results.length === 0 ? (
        <div style={{ textAlign: "center", padding: 60 }}>
          <Spin />
        </div>
      ) : displayResults.length === 0 ? (
        results.length === 0 ? (
          <Empty description="暂无生成结果" />
        ) : (
          <div style={{ textAlign: "center", padding: 60, color: "#999" }}>
            <Text type="secondary">当前页全部为已确认结果，共 {total} 条</Text>
            <br />
            <Button
              type="link"
              icon={<EyeOutlined />}
              onClick={() => setCollapseConfirmed(false)}
              style={{ marginTop: 8 }}
            >
              展开全部
            </Button>
          </div>
        )
      ) : (
        <>
          <Text type="secondary" style={{ marginBottom: 8, display: "block" }}>
            共 {displayResults.length} 条 (总计 {total})
          </Text>
          <ResultGrid
            projectId={projectId}
            results={displayResults}
            grouped={sortBy === "scene_shot"}
            onConfirm={handleConfirm}
            onCancel={handleCancel}
            onRecover={handleRecover}
            onGacha={handleOpenGacha}
            onRetry={handleRetry}
          />
          {totalPages > 1 && (
            <div style={{ textAlign: "center", marginTop: 16 }}>
              <Space>
                <Button
                  disabled={page <= 1}
                  onClick={() => handlePageChange(page - 1)}
                >
                  上一页
                </Button>
                <Text>
                  第 {page} / {totalPages} 页
                </Text>
                <Button
                  disabled={page >= totalPages}
                  onClick={() => handlePageChange(page + 1)}
                >
                  下一页
                </Button>
              </Space>
            </div>
          )}
        </>
      )}

      {/* Gacha config modal */}
      <Modal
        title="抽卡配置"
        open={gachaOpen}
        onCancel={() => setGachaOpen(false)}
        onOk={handleGachaSubmit}
        confirmLoading={gachaLoading}
        okText="开始抽卡"
        cancelText="取消"
      >
        <Space direction="vertical" style={{ width: "100%" }} size="middle">
          <div>
            <Text strong style={{ display: "block", marginBottom: 8 }}>抽卡类型</Text>
            <Radio.Group value={gachaType} onChange={(e) => setGachaType(e.target.value)}>
              <Radio.Button value="last_frame">尾帧</Radio.Button>
              <Radio.Button value="first_frame">首帧</Radio.Button>
              <Radio.Button value="video">视频</Radio.Button>
            </Radio.Group>
          </div>
          <div>
            <Text strong style={{ display: "block", marginBottom: 8 }}>场景</Text>
            <InputNumber min={1} value={gachaScene} onChange={(v) => setGachaScene(v || 1)} style={{ width: "100%" }} />
          </div>
          <div>
            <Text strong style={{ display: "block", marginBottom: 8 }}>镜头</Text>
            <InputNumber min={1} value={gachaShot} onChange={(v) => setGachaShot(v || 2)} style={{ width: "100%" }} />
          </div>
          <Text type="secondary" style={{ fontSize: 12 }}>
            点击后将自动取消当前结果、设置抽卡模式并启动 ViMax 运行，运行结束后自动恢复 YAML 配置
          </Text>
        </Space>
      </Modal>
    </div>
  );
}
