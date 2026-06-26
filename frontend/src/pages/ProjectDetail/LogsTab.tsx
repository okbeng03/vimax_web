import { useState, useEffect, useCallback } from "react";
import { Empty, Spin } from "antd";
import LogFilter, { type LogFilterValues } from "../../components/log/LogFilter";
import LogTable from "../../components/log/LogTable";
import * as operationsApi from "../../api/operations";
import type { OperationLog } from "../../api/operations";

interface Props {
  projectId: number;
  visible: boolean;
}

export default function LogsTab({ projectId, visible }: Props) {
  const [logs, setLogs] = useState<OperationLog[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState<string | undefined>();
  const [filterValues, setFilterValues] = useState<LogFilterValues>({});
  const [page, setPage] = useState(1);
  const pageSize = 50;

  const loadLogs = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = {
        page,
        page_size: pageSize,
      };
      if (filterValues.type) params.type = filterValues.type;
      const data = await operationsApi.fetchOperations(projectId, params);
      // Client-side date filtering if server doesn't support
      // Both API dates and filter dates are UTC strings — append 'Z' for correct comparison
      let filtered = data.operations;
      if (filterValues.dateFrom) {
        const from = new Date(filterValues.dateFrom + "Z").getTime();
        filtered = filtered.filter((l) => new Date(l.created_at + "Z").getTime() >= from);
      }
      if (filterValues.dateTo) {
        const to = new Date(filterValues.dateTo + "Z").getTime();
        filtered = filtered.filter((l) => new Date(l.created_at + "Z").getTime() <= to);
      }
      setLogs(filtered);
      setTotal(data.total);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [projectId, page, filterValues]);

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  // Reload when switching to this tab
  useEffect(() => {
    if (visible) loadLogs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible]);

  const handleFilter = (values: LogFilterValues) => {
    setFilterValues(values);
    setPage(1);
  };

  const handlePageChange = (newPage: number) => {
    setPage(newPage);
  };

  return (
    <div>
      <LogFilter
        typeFilter={typeFilter}
        onTypeChange={setTypeFilter}
        onFilter={handleFilter}
      />

      {loading && logs.length === 0 ? (
        <div style={{ textAlign: "center", padding: 60 }}>
          <Spin />
        </div>
      ) : logs.length === 0 ? (
        <Empty description="暂无操作记录" />
      ) : (
        <LogTable
          logs={logs}
          loading={loading}
          total={total}
          onPageChange={handlePageChange}
        />
      )}
    </div>
  );
}
