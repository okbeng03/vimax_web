import { useEffect, useState, useCallback } from "react";
import {
  Table,
  Button,
  Space,
  Tag,
  Popconfirm,
  message,
  Typography,
  Modal,
  Form,
  Input,
  Tooltip,
} from "antd";
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  ReloadOutlined,
  LockOutlined,
} from "@ant-design/icons";
import type { Template, TemplateCreate, TemplateUpdate } from "../../api/templates";
import * as templatesApi from "../../api/templates";

const { Title } = Typography;

export default function TemplateManagementPage() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<Template | null>(null);
  const [form] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);

  const loadTemplates = useCallback(async () => {
    setLoading(true);
    try {
      const data = await templatesApi.fetchTemplates();
      setTemplates(data.templates);
    } catch {
      message.error("加载模板列表失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  const handleCreate = () => {
    setEditingTemplate(null);
    form.resetFields();
    setModalOpen(true);
  };

  const handleEdit = (record: Template) => {
    setEditingTemplate(record);
    form.setFieldsValue({
      display_name: record.display_name,
      description: record.description,
      directory_name: record.directory_name,
    });
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    const values = await form.validateFields();
    setSubmitting(true);
    try {
      if (editingTemplate) {
        const body: TemplateUpdate = {
          display_name: values.display_name,
          description: values.description,
          directory_name: values.directory_name,
        };
        await templatesApi.updateTemplate(editingTemplate.id, body);
        message.success("模板已更新");
      } else {
        const body: TemplateCreate = {
          name: values.name,
          display_name: values.display_name,
          description: values.description,
          directory_name: values.directory_name,
        };
        await templatesApi.createTemplate(body);
        message.success("模板已创建");
      }
      setModalOpen(false);
      form.resetFields();
      loadTemplates();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      message.error(msg || "操作失败");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await templatesApi.deleteTemplate(id);
      message.success("模板已删除");
      loadTemplates();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      message.error(msg || "删除失败");
    }
  };

  const columns = [
    {
      title: "模板名称",
      dataIndex: "display_name",
      key: "display_name",
      width: 160,
      render: (text: string, record: Template) => (
        <Space>
          <Typography.Text strong>{text}</Typography.Text>
          {record.is_builtin && (
            <Tooltip title="内置模板，不可修改">
              <Tag icon={<LockOutlined />} color="blue" style={{ fontSize: 11 }}>
                内置
              </Tag>
            </Tooltip>
          )}
        </Space>
      ),
    },
    {
      title: "标识名",
      dataIndex: "name",
      key: "name",
      width: 120,
      render: (v: string) => <Typography.Text code>{v}</Typography.Text>,
    },
    {
      title: "目录名",
      dataIndex: "directory_name",
      key: "directory_name",
      width: 120,
      render: (v: string) => <Tag>{v}</Tag>,
    },
    {
      title: "描述",
      dataIndex: "description",
      key: "description",
      ellipsis: true,
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      key: "created_at",
      width: 170,
      render: (v: string) => new Date(v + "Z").toLocaleString("zh-CN"),
    },
    {
      title: "操作",
      key: "actions",
      width: 120,
      render: (_: unknown, record: Template) => (
        <Space size="small">
          <Button
            size="small"
            type="link"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
            disabled={record.is_builtin}
          >
            编辑
          </Button>
          {!record.is_builtin && (
            <Popconfirm
              title="确定删除此模板？"
              onConfirm={() => handleDelete(record.id)}
              okText="确定"
              cancelText="取消"
            >
              <Button size="small" type="link" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 20,
        }}
      >
        <Title level={4} style={{ margin: 0 }}>
          模板管理
        </Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={loadTemplates}>
            刷新
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
            新建模板
          </Button>
        </Space>
      </div>

      <Table
        dataSource={templates}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={false}
      />

      <Modal
        title={editingTemplate ? `编辑模板: ${editingTemplate.display_name}` : "新建模板"}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => {
          setModalOpen(false);
          form.resetFields();
        }}
        confirmLoading={submitting}
        okText={editingTemplate ? "保存" : "创建"}
        cancelText="取消"
        destroyOnClose
        width={520}
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          {!editingTemplate && (
            <Form.Item
              name="name"
              label="标识名"
              rules={[
                { required: true, message: "请输入标识名" },
                { pattern: /^[a-z][a-z0-9_]*$/, message: "仅支持小写字母、数字、下划线，以字母开头" },
              ]}
              extra="唯一标识，创建后不可修改（如: studio_quality）"
            >
              <Input placeholder="studio_quality" />
            </Form.Item>
          )}
          <Form.Item name="display_name" label="显示名称" rules={[{ required: true, message: "请输入显示名称" }]}>
            <Input placeholder="如: 工作室品质" />
          </Form.Item>
          <Form.Item name="description" label="描述" rules={[{ required: true, message: "请输入描述" }]}>
            <Input.TextArea rows={2} placeholder="简短描述此模板的特点和适用场景" />
          </Form.Item>
          <Form.Item name="directory_name" label="目录名" rules={[{ required: true, message: "请输入目录名" }]}>
            <Input placeholder="如: studio_quality" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
