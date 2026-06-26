import { Card, Empty, Typography } from "antd";
import type { TrendPoint } from "../../types/statistics";

const { Text } = Typography;

interface Props {
  data: TrendPoint[];
  title: string;
}

export default function TrendChart({ data, title }: Props) {
  const maxTotal = data.length > 0 ? Math.max(...data.map((d) => d.total), 1) : 1;

  return (
    <Card title={title}>
      {data.length === 0 ? (
        <Empty description="暂无趋势数据" />
      ) : (
        <div style={{ overflowX: "auto" }}>
          {/* Horizontal bar chart */}
          <div style={{ marginBottom: 16 }}>
            {data.map((d, i) => {
              const pct = Math.round((d.total / maxTotal) * 100);
              const successPct = d.total > 0 ? Math.round((d.success / d.total) * 100) : 0;
              return (
                <div key={i} style={{ display: "flex", alignItems: "center", marginBottom: 6 }}>
                  <Text style={{ width: 100, fontSize: 12, flexShrink: 0 }}>{d.date}</Text>
                  <div style={{ flex: 1, marginRight: 8 }}>
                    <div style={{ display: "flex", height: 20, borderRadius: 4, overflow: "hidden", background: "#f5f5f5" }}>
                      <div
                        style={{
                          width: `${d.total > 0 ? Math.round((d.success / d.total) * pct) : 0}%`,
                          background: "#52c41a",
                          transition: "width 0.3s",
                          minWidth: d.success > 0 ? 4 : 0,
                        }}
                      />
                      <div
                        style={{
                          width: `${d.total > 0 ? Math.round((d.failed / d.total) * pct) : 0}%`,
                          background: "#ff4d4f",
                          transition: "width 0.3s",
                          minWidth: d.failed > 0 ? 4 : 0,
                        }}
                      />
                    </div>
                  </div>
                  <Text style={{ width: 50, fontSize: 12, textAlign: "right", flexShrink: 0 }}>
                    {d.total} <Text type="success" style={{ fontSize: 11 }}>{d.success}</Text>{" "}
                    <Text type="danger" style={{ fontSize: 11 }}>{d.failed}</Text>
                  </Text>
                </div>
              );
            })}
          </div>

          {/* Legend */}
          <div style={{ display: "flex", gap: 16, justifyContent: "center" }}>
            <span>
              <span style={{ display: "inline-block", width: 12, height: 12, background: "#52c41a", borderRadius: 2, marginRight: 4, verticalAlign: "middle" }} />
              <Text style={{ fontSize: 12 }}>成功</Text>
            </span>
            <span>
              <span style={{ display: "inline-block", width: 12, height: 12, background: "#ff4d4f", borderRadius: 2, marginRight: 4, verticalAlign: "middle" }} />
              <Text style={{ fontSize: 12 }}>失败</Text>
            </span>
          </div>

          {/* Table view */}
          <details style={{ marginTop: 16 }}>
            <summary style={{ cursor: "pointer", fontSize: 12, color: "#888" }}>表格视图</summary>
            <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 8 }}>
              <thead>
                <tr>
                  <th style={{ padding: 8, borderBottom: "1px solid #f0f0f0", textAlign: "left" }}>日期</th>
                  <th style={{ padding: 8, borderBottom: "1px solid #f0f0f0", textAlign: "right" }}>总数</th>
                  <th style={{ padding: 8, borderBottom: "1px solid #f0f0f0", textAlign: "right" }}>成功</th>
                  <th style={{ padding: 8, borderBottom: "1px solid #f0f0f0", textAlign: "right" }}>失败</th>
                </tr>
              </thead>
              <tbody>
                {data.map((d, i) => (
                  <tr key={i}>
                    <td style={{ padding: 8, borderBottom: "1px solid #f0f0f0" }}>{d.date}</td>
                    <td style={{ padding: 8, borderBottom: "1px solid #f0f0f0", textAlign: "right" }}>{d.total}</td>
                    <td style={{ padding: 8, borderBottom: "1px solid #f0f0f0", textAlign: "right", color: "#52c41a" }}>{d.success}</td>
                    <td style={{ padding: 8, borderBottom: "1px solid #f0f0f0", textAlign: "right", color: "#ff4d4f" }}>{d.failed}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        </div>
      )}
    </Card>
  );
}
