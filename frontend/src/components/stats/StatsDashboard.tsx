import { Row, Col, Card, Statistic, Progress, Tag, Typography } from "antd";
import type { GlobalStats } from "../../types/statistics";

const { Text } = Typography;

interface Props {
  stats: GlobalStats | null;
  loading: boolean;
}

const FAILURE_COLORS = [
  "#ff4d4f", "#ff7a45", "#ffa940", "#ffc53d", "#ffec3d",
  "#bae637", "#73d13d", "#36cfc9", "#597ef7", "#9254de",
];

export default function StatsDashboard({ stats, loading }: Props) {
  if (!stats && !loading) return null;

  const failureEntries = Object.entries(stats?.failure_reasons ?? {}).sort(
    (a, b) => b[1] - a[1],
  );

  return (
    <>
      <Row gutter={[16, 16]}>
        <Col xs={12} sm={6}>
          <Card loading={loading}><Statistic title="总项目数" value={stats?.total_projects ?? 0} /></Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card loading={loading}><Statistic title="已完成" value={stats?.completed_projects ?? 0} valueStyle={{ color: "#52c41a" }} /></Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card loading={loading}><Statistic title="失败" value={stats?.failed_projects ?? 0} valueStyle={{ color: "#ff4d4f" }} /></Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card loading={loading}>
            <Statistic title="成功率" value={Math.round((stats?.success_rate ?? 0) * 100)} suffix="%" />
            <Progress percent={Math.round((stats?.success_rate ?? 0) * 100)} size="small" showInfo={false} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card loading={loading}><Statistic title="总生成次数" value={stats?.total_generations ?? 0} /></Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card loading={loading}><Statistic title="平均耗时" value={stats?.avg_generation_duration ?? 0} suffix="秒" precision={1} /></Card>
        </Col>
      </Row>

      {/* Failure reasons breakdown */}
      {failureEntries.length > 0 && (
        <Card title="失败原因分布" size="small" style={{ marginTop: 16 }}>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {failureEntries.map(([reason, count], i) => (
              <Tag key={reason} color={FAILURE_COLORS[i % FAILURE_COLORS.length]}>
                {reason}: {count}
              </Tag>
            ))}
          </div>
          <div style={{ marginTop: 12 }}>
            {failureEntries.map(([reason, count], i) => {
              const maxCount = failureEntries[0][1];
              const pct = Math.round((count / maxCount) * 100);
              return (
                <div key={reason} style={{ display: "flex", alignItems: "center", marginBottom: 4 }}>
                  <Text style={{ width: 100, fontSize: 12 }}>{reason}</Text>
                  <div style={{ flex: 1, height: 16, background: "#f5f5f5", borderRadius: 4, overflow: "hidden", marginRight: 8 }}>
                    <div
                      style={{
                        height: "100%",
                        width: `${pct}%`,
                        background: FAILURE_COLORS[i % FAILURE_COLORS.length],
                        borderRadius: 4,
                        transition: "width 0.3s",
                      }}
                    />
                  </div>
                  <Text style={{ width: 30, fontSize: 12, textAlign: "right" }}>{count}</Text>
                </div>
              );
            })}
          </div>
        </Card>
      )}
    </>
  );
}
