import { Select, Space, Typography } from "antd";
import { useProjectStore } from "../../stores/projectStore";
import { useEffect } from "react";

const { Text } = Typography;

interface Props {
  value?: number;
  onChange?: (value: number) => void;
}

export default function TemplateSelector({ value, onChange }: Props) {
  const { templates, fetchTemplates } = useProjectStore();

  useEffect(() => {
    fetchTemplates();
  }, [fetchTemplates]);

  return (
    <Select
      value={value}
      onChange={onChange}
      placeholder="选择项目模板"
      style={{ width: "100%" }}
      options={templates.map((t) => ({
        value: t.id,
        label: (
          <Space direction="vertical" size={0}>
            <Text strong>{t.display_name}</Text>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {t.description}
            </Text>
          </Space>
        ),
      }))}
    />
  );
}
