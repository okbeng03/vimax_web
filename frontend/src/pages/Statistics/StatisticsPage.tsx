import { useEffect, useState } from "react";
import { Typography, Space } from "antd";
import StatsDashboard from "../../components/stats/StatsDashboard";
import TrendChart from "../../components/stats/TrendChart";
import * as statsApi from "../../api/stats";
import type { GlobalStats } from "../../types/statistics";

const { Title } = Typography;

export default function StatisticsPage() {
  const [stats, setStats] = useState<GlobalStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    statsApi.fetchGlobalStats().then(setStats).finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>全局统计</Title>
      <Space direction="vertical" style={{ width: "100%" }} size="large">
        <StatsDashboard stats={stats} loading={loading} />
        <TrendChart data={stats?.trend?.daily || []} title="每日趋势" />
        <TrendChart data={stats?.trend?.weekly || []} title="每周趋势" />
      </Space>
    </div>
  );
}
