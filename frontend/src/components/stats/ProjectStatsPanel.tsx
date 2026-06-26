import { useEffect, useState } from "react";
import {
  Row,
  Col,
  Card,
  Statistic,
  Progress,
  Empty,
  Spin,
} from "antd";
import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
} from "recharts";
import * as statsApi from "../../api/stats";
import type { ProjectStats } from "../../types/statistics";

// ── Color palette ──
const TYPE_COLORS: Record<string, string> = {
  first_frame: "#1890ff",
  last_frame: "#722ed1",
  video: "#13c2c2",
  image: "#52c41a",
  audio: "#fa8c16",
};
const CHART_COLORS = ["#52c41a", "#ff4d4f", "#1890ff", "#faad14", "#722ed1", "#13c2c2"];

const TYPE_LABELS: Record<string, string> = {
  first_frame: "首帧",
  last_frame: "尾帧",
  video: "视频",
  image: "图片",
  audio: "音频",
};

interface Props {
  projectId: number;
  visible: boolean;
}

export default function ProjectStatsPanel({ projectId, visible }: Props) {
  const [stats, setStats] = useState<ProjectStats | null>(null);
  const [loading, setLoading] = useState(true);

  const loadStats = () => {
    setLoading(true);
    statsApi
      .fetchProjectStats(projectId)
      .then(setStats)
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadStats();
  }, [projectId]);

  useEffect(() => {
    if (visible) loadStats();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible]);

  if (loading) {
    return (
      <div style={{ textAlign: "center", padding: 60 }}>
        <Spin size="default" />
      </div>
    );
  }

  if (!stats) {
    return <Empty description="暂无统计数据" />;
  }

  const genStats = stats.generation_stats;
  const byType = stats.generations_by_type?.map((t) => ({
    name: TYPE_LABELS[t.type] || t.type,
    value: t.count,
    type: t.type,
  })) || [];

  const byStep = stats.generations_by_step || [];
  const durBuckets = stats.duration_buckets || [];
  const logRetries = (stats.step_log_retries || []).filter(
    (r) => r.log_retry_count > 0 || r.confirm_count > 0 || r.reject_count > 0
  );

  // Success / Fail pie data
  const successFailData = [
    { name: "成功", value: genStats.success, color: "#52c41a" },
    { name: "失败", value: genStats.failed, color: "#ff4d4f" },
  ];

  const hasGenerations = genStats.total > 0;
  const hasStepBreakdown = byStep.length > 0;
  const hasDurationData = durBuckets.some((b) => b.count > 0);

  return (
    <div>
      {/* ── Row 1: Core stats cards ── */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic title="步骤总数" value={stats.step_overview.total} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title="已完成步骤"
              value={stats.step_overview.completed}
              valueStyle={{ color: "#52c41a" }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title="失败步骤"
              value={stats.step_overview.failed}
              valueStyle={{ color: "#ff4d4f" }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title="步骤成功率"
              value={Math.round(stats.step_overview.success_rate * 100)}
              suffix="%"
            />
            <Progress
              percent={Math.round(stats.step_overview.success_rate * 100)}
              size="small"
              showInfo={false}
              strokeColor={
                stats.step_overview.success_rate >= 0.8
                  ? "#52c41a"
                  : stats.step_overview.success_rate >= 0.5
                    ? "#faad14"
                    : "#ff4d4f"
              }
            />
          </Card>
        </Col>
      </Row>

      {/* ── Row 2: Generation overview ── */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={12} sm={4}>
          <Card size="small">
            <Statistic title="生成总数" value={genStats.total} />
          </Card>
        </Col>
        <Col xs={12} sm={4}>
          <Card size="small">
            <Statistic
              title="成功"
              value={genStats.success}
              valueStyle={{ color: "#52c41a" }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={4}>
          <Card size="small">
            <Statistic
              title="失败"
              value={genStats.failed}
              valueStyle={{ color: "#ff4d4f" }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={4}>
          <Card size="small">
            <Statistic
              title="生成成功率"
              value={Math.round(genStats.success_rate * 100)}
              suffix="%"
            />
            <Progress
              percent={Math.round(genStats.success_rate * 100)}
              size="small"
              showInfo={false}
              strokeColor={
                genStats.success_rate >= 0.8
                  ? "#52c41a"
                  : genStats.success_rate >= 0.5
                    ? "#faad14"
                    : "#ff4d4f"
              }
            />
          </Card>
        </Col>
        <Col xs={12} sm={4}>
          <Card size="small">
            <Statistic
              title="总耗时"
              value={stats.total_duration_seconds}
              suffix="秒"
              precision={1}
            />
          </Card>
        </Col>
        <Col xs={12} sm={4}>
          <Card size="small">
            <Statistic
              title="平均耗时"
              value={
                genStats.total > 0
                  ? +(stats.total_duration_seconds / genStats.total).toFixed(1)
                  : 0
              }
              suffix="秒/次"
              precision={1}
            />
          </Card>
        </Col>
      </Row>

      {!hasGenerations && (
        <Empty description="暂无生成数据，执行项目后统计图表将在此展示" />
      )}

      {/* ── Row 3: Charts ── */}
      {hasGenerations && (
        <Row gutter={[16, 16]}>
          {/* Pie: Success / Fail */}
          <Col xs={24} md={12}>
            <Card title="生成结果分布" size="small">
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie
                    data={successFailData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={90}
                    paddingAngle={3}
                    label={({ name, value, percent }) =>
                      `${name} ${value} (${(percent * 100).toFixed(0)}%)`
                    }
                  >
                    {successFailData.map((entry, i) => (
                      <Cell key={i} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </Card>
          </Col>

          {/* Pie: By generation type */}
          {byType.length > 0 && (
            <Col xs={24} md={12}>
              <Card title="生成类型分布" size="small">
                <ResponsiveContainer width="100%" height={260}>
                  <PieChart>
                    <Pie
                      data={byType}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      innerRadius={50}
                      outerRadius={90}
                      paddingAngle={3}
                      label={({ name, value }) => `${name}: ${value}`}
                    >
                      {byType.map((entry, i) => (
                        <Cell
                          key={i}
                          fill={
                            TYPE_COLORS[entry.type] ||
                            CHART_COLORS[i % CHART_COLORS.length]
                          }
                        />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </Card>
            </Col>
          )}

          {/* Bar: Generation count per step */}
          {hasStepBreakdown && (
            <Col xs={24} md={14}>
              <Card title="各步骤生成统计" size="small">
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart
                    data={byStep}
                    margin={{ top: 8, right: 16, left: 0, bottom: 8 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="step_name"
                      tick={{ fontSize: 11 }}
                      angle={-20}
                      textAnchor="end"
                      height={60}
                    />
                    <YAxis allowDecimals={false} />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="success" name="成功" stackId="a" fill="#52c41a" />
                    <Bar dataKey="failed" name="失败" stackId="a" fill="#ff4d4f" />
                  </BarChart>
                </ResponsiveContainer>
              </Card>
            </Col>
          )}

          {/* Radar: Avg duration by type */}
          {stats.avg_duration_by_type && stats.avg_duration_by_type.length > 0 && (
            <Col xs={24} md={10}>
              <Card title="各类型平均耗时" size="small">
                <ResponsiveContainer width="100%" height={280}>
                  <RadarChart
                    data={stats.avg_duration_by_type.map((d) => ({
                      name: TYPE_LABELS[d.type] || d.type,
                      value: d.avg_duration,
                    }))}
                  >
                    <PolarGrid />
                    <PolarAngleAxis dataKey="name" tick={{ fontSize: 11 }} />
                    <PolarRadiusAxis />
                    <Radar
                      dataKey="value"
                      stroke="#1890ff"
                      fill="#1890ff"
                      fillOpacity={0.3}
                      name="平均耗时(s)"
                    />
                    <Tooltip formatter={(val: number) => `${val.toFixed(1)}s`} />
                  </RadarChart>
                </ResponsiveContainer>
              </Card>
            </Col>
          )}

          {/* Bar: Duration distribution histogram */}
          {hasDurationData && (
            <Col xs={24} md={12}>
              <Card title="生成耗时分布" size="small">
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart
                    data={durBuckets}
                    margin={{ top: 8, right: 16, left: 0, bottom: 8 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="range" tick={{ fontSize: 12 }} />
                    <YAxis allowDecimals={false} />
                    <Tooltip formatter={(val: number) => [`${val} 次`, "数量"]} />
                    <Bar dataKey="count" name="次数" fill="#1890ff" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </Card>
            </Col>
          )}

          {/* Empty placeholder if no step breakdown */}
          {!hasStepBreakdown && byType.length > 0 && !hasDurationData && (
            <Col xs={24} md={12}>
              <Card title="生成耗时分布" size="small">
                <Empty description="生成进行中，暂无耗时数据" />
              </Card>
            </Col>
          )}
        </Row>
      )}

      {/* ── Step Retry Analysis (log-based) ── */}
      {stats.step_log_retry_summary && (
        <Card
          title="步骤重试分析 (基于操作日志)"
          size="small"
          style={{ marginTop: 24 }}
        >
          {/* ── Summary row ── */}
          <Row gutter={[16, 16]} style={{ marginBottom: 20 }}>
            <Col xs={12} sm={6}>
              <Statistic
                title="总重试次数"
                value={stats.step_log_retry_summary.total_log_retries}
                valueStyle={{ color: "#1890ff", fontSize: 22 }}
              />
            </Col>
            <Col xs={12} sm={6}>
              <Statistic
                title="平均每步重试"
                value={stats.step_log_retry_summary.avg_log_retries_per_step}
                precision={1}
                suffix="次"
                valueStyle={{ fontSize: 22 }}
              />
            </Col>
            <Col xs={12} sm={6}>
              <Statistic
                title="最大重试步骤"
                value={stats.step_log_retry_summary.max_log_retries_per_step}
                suffix={` 次`}
                valueStyle={{ color: "#ff4d4f", fontSize: 22 }}
              />
              <div style={{ fontSize: 12, color: "#999", marginTop: -4 }}>
                {stats.step_log_retry_summary.max_log_retry_step}
              </div>
            </Col>
            <Col xs={12} sm={6}>
              <Statistic
                title="涉及步骤"
                value={`${stats.step_log_retry_summary.steps_with_retries} / ${stats.step_log_retry_summary.total_steps}`}
                valueStyle={{ fontSize: 22 }}
              />
            </Col>
          </Row>

          {/* ── Charts row ── */}
          {logRetries.length > 0 && (
            <Row gutter={[16, 16]}>
              {/* Left: Horizontal bar — retry count per step */}
              <Col xs={24} md={14}>
                <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 8, color: "#666" }}>
                  各步骤重试次数
                </div>
                <ResponsiveContainer width="100%" height={Math.max(180, logRetries.length * 36)}>
                  <BarChart
                    data={logRetries}
                    layout="vertical"
                    margin={{ top: 0, right: 20, left: 10, bottom: 0 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                    <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                    <YAxis
                      type="category"
                      dataKey="step_name"
                      width={100}
                      tick={{ fontSize: 11 }}
                    />
                    <Tooltip
                      formatter={(val: number) => [`${val} 次`, "操作日志重试"]}
                    />
                    <Bar
                      dataKey="log_retry_count"
                      fill="#1890ff"
                      radius={[0, 4, 4, 0]}
                      maxBarSize={24}
                      label={{
                        position: "right",
                        fontSize: 11,
                        fill: "#1890ff",
                        formatter: (v: number) => (v > 0 ? `${v}次` : ""),
                      }}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </Col>

              {/* Right: Pie — confirm vs reject */}
              <Col xs={24} md={10}>
                <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 8, color: "#666" }}>
                  确认 / 拒绝分布
                </div>
                {(stats.step_log_retry_summary.total_confirms > 0 ||
                  stats.step_log_retry_summary.total_rejects > 0) ? (
                  <ResponsiveContainer width="100%" height={Math.max(180, logRetries.length * 36)}>
                    <PieChart>
                      <Pie
                        data={[
                          {
                            name: "确认",
                            value: stats.step_log_retry_summary.total_confirms,
                          },
                          {
                            name: "拒绝",
                            value: stats.step_log_retry_summary.total_rejects,
                          },
                        ]}
                        dataKey="value"
                        nameKey="name"
                        cx="50%"
                        cy="50%"
                        innerRadius={40}
                        outerRadius={70}
                        paddingAngle={4}
                        label={({ name, value, percent }) =>
                          `${name} ${value} (${(percent * 100).toFixed(0)}%)`
                        }
                      >
                        <Cell fill="#52c41a" />
                        <Cell fill="#ff4d4f" />
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <Empty
                    description="暂无确认/拒绝记录"
                    style={{ padding: 24 }}
                  />
                )}
              </Col>
            </Row>
          )}

          {/* No per-step chart data but summary exists */}
          {logRetries.length === 0 && (
            <div
              style={{
                textAlign: "center",
                color: "#999",
                fontSize: 13,
                padding: "16px 0",
              }}
            >
              当前项目步骤暂无操作日志中的重试记录
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
