import { Select, DatePicker } from "antd";
import { Space } from "antd";
import dayjs from "dayjs";

const { RangePicker } = DatePicker;

export interface LogFilterValues {
  type?: string;
  dateFrom?: string;
  dateTo?: string;
}

interface Props {
  typeFilter?: string;
  onTypeChange: (v?: string) => void;
  onFilter: (values: LogFilterValues) => void;
}

export default function LogFilter({ typeFilter, onTypeChange, onFilter }: Props) {
  const handleTypeChange = (v: string | undefined) => {
    onTypeChange(v);
    onFilter({ type: v || undefined });
  };

  const handleDateChange = (_: any, dates: [string, string]) => {
    onFilter({
      type: typeFilter || undefined,
      dateFrom: dates[0] ? dayjs(dates[0]).startOf("day").toISOString() : undefined,
      dateTo: dates[1] ? dayjs(dates[1]).endOf("day").toISOString() : undefined,
    });
  };

  return (
    <Space style={{ marginBottom: 16 }}>
      <Select
        placeholder="操作类型"
        value={typeFilter}
        onChange={handleTypeChange}
        allowClear
        style={{ width: 160 }}
        options={[
          { value: "", label: "全部" },
          { value: "edit_file", label: "编辑文件" },
          { value: "confirm_result", label: "确认结果" },
          { value: "reject_result", label: "拒绝结果" },
          { value: "regenerate_step", label: "重新生成" },
          { value: "execute_step", label: "启动执行" },
          { value: "kill_step", label: "终止执行" },
        ]}
      />
      <RangePicker onChange={handleDateChange} placeholder={["开始日期", "结束日期"]} />
    </Space>
  );
}
