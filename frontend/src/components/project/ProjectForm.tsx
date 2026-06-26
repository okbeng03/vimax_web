import { Modal, Form, Input, message } from "antd";
import { useProjectStore } from "../../stores/projectStore";
import TemplateSelector from "./TemplateSelector";

interface Props {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}

export default function ProjectForm({ open, onClose, onCreated }: Props) {
  const [form] = Form.useForm();
  const { createProject } = useProjectStore();

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      await createProject({
        name: values.name,
        creative_description: values.creative_description,
        template_id: values.template_id,
        working_dir_root: values.working_dir_root || "/Users/wangchangbin/ai/vimax_ru",
      });
      message.success("项目创建成功");
      form.resetFields();
      onCreated();
      onClose();
    } catch {
      // Validation error — form will show inline errors
    }
  };

  return (
    <Modal title="新建项目" open={open} onOk={handleSubmit} onCancel={onClose} okText="创建" cancelText="取消" destroyOnClose>
      <Form form={form} layout="vertical" initialValues={{ working_dir_root: "/Users/wangchangbin/ai/vimax_ru" }}>
        <Form.Item name="name" label="项目名称" rules={[{ required: true, message: "请输入项目名称" }]}>
          <Input placeholder="例如：我的第一个视频" />
        </Form.Item>
        <Form.Item
          name="creative_description"
          label="创意描述"
          rules={[{ required: true, message: "请输入创意描述" }]}
        >
          <Input.TextArea rows={3} placeholder="用一句话描述你想要生成的视频内容" />
        </Form.Item>
        <Form.Item name="template_id" label="项目模板" rules={[{ required: true, message: "请选择模板" }]}>
          <TemplateSelector />
        </Form.Item>
        <Form.Item name="working_dir_root" label="工作目录" tooltip="项目的 working_dir，模板文件将直接复制到此目录">
          <Input placeholder="/Users/wangchangbin/ai/vimax_ru" />
        </Form.Item>
      </Form>
    </Modal>
  );
}
