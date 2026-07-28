import { useEffect, useState } from "react";
import {
  Row,
  Col,
  Card,
  Statistic,
  Progress,
  Spin,
  Empty,
  Table,
  Tag,
  Typography,
} from "antd";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import * as statsApi from "../../api/stats";
import type { ProjectComparisonResponse } from "../../types/statistics";

const { Text } = Typography;

const CHART_COLORS = [
  "#1890ff", "#52c41a", "#722ed1", "#13c2c2",
  "#fa8c16", "#ff4d4f", "#faad14", "#eb2f96",
];

const STATUS_COLOR: Record<string, string> = {
  completed: "#52c41a",
  running: "#1890ff",
  failed: "#ff4d4f",
  pending: "#d9d9d9",
};

const STATUS_LABEL: Record<string, string> = {
  completed: "已完成",
  running: "运行中",
  failed: "失败",
  pending: "待处理",
};

export default function ProjectComparison() {
  const [data, setData] = useState<ProjectComparisonResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    statsApi
      .fetchProjectComparison()
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div style={{ textAlign: "center", padding: 60 }}>
        <Spin size="default" />
      </div>
    );
  }

  if (!data || data.projects.length === 0) {
    return <Empty description="暂无项目数据用于对比" />;
  }

  const { projects, summary } = data;

  // ── Chart data: success rate comparison ──
  const successData = projects
    .filter((p) => p.generation_total > 0)
    .map((p) => ({
      name: p.project_name,
      rate: +(p.generation_success_rate * 100).toFixed(1),
      success: p.generation_success,
      failed: p.generation_failed,
      total: p.generation_total,
    }));

  // ── Chart data: duration comparison ──
  const durationData = projects
    .filter((p) => p.avg_duration_seconds > 0)
    .map((p) => ({
      name: p.project_name,
      avg: +p.avg_duration_seconds.toFixed(1),
      max: +p.max_duration_seconds.toFixed(1),
      min: +p.min_duration_seconds.toFixed(1),
    }));

  // ── Chart data: retry comparison ──
  const retryData = projects
    .filter((p) => p.step_count > 0)
    .map((p) => ({
      name: p.project_name,
      avg: +p.avg_retries_per_step.toFixed(1),
      max: p.max_retries_per_step,
      total: p.total_retries,
    }));

  // ── Table columns ──
  const tableColumns = [
    {
      title: "项目名称",
      dataIndex: "project_name",
      key: "project_name",
      width: 200,
      render: (text: string) => <Text strong>{text}</Text>,
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 90,
      render: (s: string) => (
        <Tag color={STATUS_COLOR[s] || "#d9d9d9"}>
          {STATUS_LABEL[s] || s}
        </Tag>
      ),
    },
    {
      title: "生成",
      dataIndex: "generation_total",
      key: "gen_total",
      width: 80,
      align: "right" as const,
    },
    {
      title: "成功",
      dataIndex: "generation_success",
      key: "gen_success",
      width: 80,
      align: "right" as const,
      render: (v: number) => (
        <Text style={{ color: "#52c41a" }}>{v}</Text>
      ),
    },
    {
      title: "失败",
      dataIndex: "generation_failed",
      key: "gen_failed",
      width: 80,
      align: "right" as const,
      render: (v: number) => (
        <Text style={{ color: v > 0 ? "#ff4d4f" : undefined }}>{v}</Text>
      ),
    },
    {
      title: "成功率",
      dataIndex: "generation_success_rate",
      key: "success_rate",
      width: 120,
      render: (rate: number, record: { generation_total: number }) => {
        if (record.generation_total === 0) return <Text type="secondary">-</Text>;
        const pct = Math.round(rate * 100);
        return (
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <Progress
              percent={pct}
              size="small"
              showInfo={false}
              strokeColor={
                rate >= 0.8 ? "#52c41a" : rate >= 0.5 ? "#faad14" : "#ff4d4f"
              }
              style={{ width: 60, marginBottom: 0 }}
            />
            <Text>{pct}%</Text>
          </div>
        );
      },
    },
    {
      title: "平均耗时",
      dataIndex: "avg_duration_seconds",
      key: "avg_dur",
      width: 100,
      align: "right" as const,
      render: (v: number) =>
        v > 0 ? `${v.toFixed(1)}s` : <Text type="secondary">-</Text>,
    },
    {
      title: "最大耗时",
      dataIndex: "max_duration_seconds",
      key: "max_dur",
      width: 100,
      align: "right" as const,
      render: (v: number) =>
        v > 0 ? `${v.toFixed(1)}s` : <Text type="secondary">-</Text>,
    },
    {
      title: "最小耗时",
      dataIndex: "min_duration_seconds",
      key: "min_dur",
      width: 100,
      align: "right" as const,
      render: (v: number) =>
        v > 0 ? `${v.toFixed(1)}s` : <Text type="secondary">-</Text>,
    },
    {
      title: "总重试",
      dataIndex: "total_retries",
      key: "total_retry",
      width: 80,
      align: "right" as const,
    },
    {
      title: "平均重试/步",
      dataIndex: "avg_retries_per_step",
      key: "avg_retry",
      width: 110,
      align: "right" as const,
      render: (v: number) => v.toFixed(1),
    },
    {
      title: "最大重试/步",
      dataIndex: "max_retries_per_step",
      key: "max_retry",
      width: 110,
      align: "right" as const,
      render: (v: number) => (
        <Text style={{ color: v > 0 ? "#ff4d4f" : undefined }}>{v}</Text>
      ),
    },
  ];

  return (
    <div>
      {/* ── Summary Cards ── */}
      <Card title="项目间交叉分析" size="small" style={{ marginBottom: 16 }}>
        <Row gutter={[16, 16]}>
          {/* Success Rate */}
          <Col xs={24} sm={8}>
            <div style={{ marginBottom: 12 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                成功率对比
              </Text>
            </div>
            <Row gutter={12}>
              <Col span={8}>
                <Card size="small" style={{ textAlign: "center" }}>
                  <Statistic
                    title="平均"
                    value={Math.round(summary.avg_success_rate * 100)}
                    suffix="%"
                    valueStyle={{ fontSize: 18 }}
                  />
                </Card>
              </Col>
              <Col span={8}>
                <Card size="small" style={{ textAlign: "center" }}>
                  <Statistic
                    title="最高"
                    value={Math.round(summary.max_success_rate * 100)}
                    suffix="%"
                    valueStyle={{ color: "#52c41a", fontSize: 18 }}
                  />
                  <div style={{ fontSize: 11, color: "#999", marginTop: -4 }}>
                    {summary.max_success_rate_project}
                  </div>
                </Card>
              </Col>
              <Col span={8}>
                <Card size="small" style={{ textAlign: "center" }}>
                  <Statistic
                    title="最低"
                    value={Math.round(summary.min_success_rate * 100)}
                    suffix="%"
                    valueStyle={{ color: "#ff4d4f", fontSize: 18 }}
                  />
                  <div style={{ fontSize: 11, color: "#999", marginTop: -4 }}>
                    {summary.min_success_rate_project}
                  </div>
                </Card>
              </Col>
            </Row>
          </Col>

          {/* Duration */}
          <Col xs={24} sm={8}>
            <div style={{ marginBottom: 12 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                耗时对比 (平均耗时)
              </Text>
            </div>
            <Row gutter={12}>
              <Col span={8}>
                <Card size="small" style={{ textAlign: "center" }}>
                  <Statistic
                    title="平均"
                    value={summary.avg_duration_seconds}
                    suffix="s"
                    precision={1}
                    valueStyle={{ fontSize: 18 }}
                  />
                </Card>
              </Col>
              <Col span={8}>
                <Card size="small" style={{ textAlign: "center" }}>
                  <Statistic
                    title="最快"
                    value={summary.min_duration_seconds}
                    suffix="s"
                    precision={1}
                    valueStyle={{ color: "#52c41a", fontSize: 18 }}
                  />
                  <div style={{ fontSize: 11, color: "#999", marginTop: -4 }}>
                    {summary.min_duration_project}
                  </div>
                </Card>
              </Col>
              <Col span={8}>
                <Card size="small" style={{ textAlign: "center" }}>
                  <Statistic
                    title="最慢"
                    value={summary.max_duration_seconds}
                    suffix="s"
                    precision={1}
                    valueStyle={{ color: "#ff4d4f", fontSize: 18 }}
                  />
                  <div style={{ fontSize: 11, color: "#999", marginTop: -4 }}>
                    {summary.max_duration_project}
                  </div>
                </Card>
              </Col>
            </Row>
          </Col>

          {/* Retries */}
          <Col xs={24} sm={8}>
            <div style={{ marginBottom: 12 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                重试对比 (每步最大重试)
              </Text>
            </div>
            <Row gutter={12}>
              <Col span={8}>
                <Card size="small" style={{ textAlign: "center" }}>
                  <Statistic
                    title="平均"
                    value={summary.avg_retries_per_project}
                    suffix="次"
                    precision={1}
                    valueStyle={{ fontSize: 18 }}
                  />
                </Card>
              </Col>
              <Col span={8}>
                <Card size="small" style={{ textAlign: "center" }}>
                  <Statistic
                    title="最少"
                    value={summary.min_retries_per_project}
                    suffix="次"
                    valueStyle={{ color: "#52c41a", fontSize: 18 }}
                  />
                  <div style={{ fontSize: 11, color: "#999", marginTop: -4 }}>
                    {summary.min_retries_project}
                  </div>
                </Card>
              </Col>
              <Col span={8}>
                <Card size="small" style={{ textAlign: "center" }}>
                  <Statistic
                    title="最多"
                    value={summary.max_retries_per_project}
                    suffix="次"
                    valueStyle={{ color: "#ff4d4f", fontSize: 18 }}
                  />
                  <div style={{ fontSize: 11, color: "#999", marginTop: -4 }}>
                    {summary.max_retries_project}
                  </div>
                </Card>
              </Col>
            </Row>
          </Col>
        </Row>
      </Card>

      {/* ── Charts Row ── */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        {/* Success Rate Bar Chart */}
        {successData.length > 1 && (
          <Col xs={24} md={12}>
            <Card title="项目成功率对比" size="small">
              <ResponsiveContainer width="100%" height={300}>
                <BarChart
                  data={successData}
                  layout="vertical"
                  margin={{ top: 4, right: 30, left: 30, bottom: 4 }}
                >
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" domain={[0, 100]} unit="%" tick={{ fontSize: 11 }} />
                  <YAxis
                    type="category"
                    dataKey="name"
                    width={120}
                    tick={{ fontSize: 11 }}
                  />
                  <Tooltip
                    formatter={(val: number) => [`${val}%`, "成功率"]}
                  />
                  <Bar
                    dataKey="rate"
                    name="成功率"
                    fill="#1890ff"
                    radius={[0, 4, 4, 0]}
                    maxBarSize={28}
                    label={{
                      position: "right",
                      fontSize: 11,
                      formatter: (v: number) => `${v}%`,
                    }}
                  />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          </Col>
        )}

        {/* Duration Bar Chart */}
        {durationData.length > 0 && (
          <Col xs={24} md={12}>
            <Card title="项目耗时对比 (平均 / 最大 / 最小)" size="small">
              <ResponsiveContainer width="100%" height={300}>
                <BarChart
                  data={durationData}
                  margin={{ top: 4, right: 30, left: 30, bottom: 4 }}
                >
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} angle={-25} textAnchor="end" height={60} />
                  <YAxis tick={{ fontSize: 11 }} unit="s" />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="avg" name="平均耗时" fill="#1890ff" radius={[4, 4, 0, 0]} maxBarSize={28} />
                  <Bar dataKey="max" name="最大耗时" fill="#ff4d4f" radius={[4, 4, 0, 0]} maxBarSize={28} />
                  <Bar dataKey="min" name="最小耗时" fill="#52c41a" radius={[4, 4, 0, 0]} maxBarSize={28} />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          </Col>
        )}
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        {/* Retry Bar Chart */}
        {retryData.length > 0 && (
          <Col xs={24} md={12}>
            <Card title="项目重试对比 (平均 / 最大 重试/步)" size="small">
              <ResponsiveContainer width="100%" height={300}>
                <BarChart
                  data={retryData}
                  margin={{ top: 4, right: 30, left: 30, bottom: 4 }}
                >
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} angle={-25} textAnchor="end" height={60} />
                  <YAxis tick={{ fontSize: 11 }} unit="次" />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="avg" name="平均重试/步" fill="#1890ff" radius={[4, 4, 0, 0]} maxBarSize={28} />
                  <Bar dataKey="max" name="最大重试/步" fill="#ff4d4f" radius={[4, 4, 0, 0]} maxBarSize={28} />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          </Col>
        )}
      </Row>

      {/* ── Full Comparison Table ── */}
      {projects.length > 0 && (
        <Card title="项目详细对比表" size="small">
          <Table
            columns={tableColumns}
            dataSource={projects}
            rowKey="project_id"
            pagination={false}
            scroll={{ x: 1200 }}
            size="small"
          />
        </Card>
      )}
    </div>
  );
}
