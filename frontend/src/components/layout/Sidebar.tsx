import { Menu } from "antd";
import { useNavigate, useLocation } from "react-router-dom";
import { ProjectOutlined, BarChartOutlined } from "@ant-design/icons";

export default function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const selectedKey = location.pathname.startsWith("/statistics") ? "/statistics" : "/projects";

  return (
    <Menu
      mode="inline"
      selectedKeys={[selectedKey]}
      onClick={({ key }) => navigate(key)}
      items={[
        { key: "/projects", icon: <ProjectOutlined />, label: "项目列表" },
        { key: "/statistics", icon: <BarChartOutlined />, label: "全局统计" },
      ]}
    />
  );
}
