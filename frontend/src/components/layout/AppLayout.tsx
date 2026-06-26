import { Layout, Menu, Typography, Avatar } from "antd";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import {
  ProjectOutlined,
  BarChartOutlined,
  AppstoreOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { useState } from "react";
import { useCurrentUser } from "../../hooks/useCurrentUser";

const { Header, Sider, Content } = Layout;

const HEADER_STYLE: React.CSSProperties = {
  background: "#fff",
  padding: "0 24px",
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  borderBottom: "1px solid #f0f0f0",
  height: 56,
};

export default function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(true);
  const { user } = useCurrentUser();

  const avatarChar = user?.display_name?.charAt(0)?.toUpperCase() || "U";

  const menuItems = [
    { key: "/projects", icon: <ProjectOutlined />, label: "项目列表" },
    { key: "/templates", icon: <AppstoreOutlined />, label: "模板管理" },
    { key: "/statistics", icon: <BarChartOutlined />, label: "全局统计" },
  ];

  let selectedKey = "/projects";
  for (const item of menuItems) {
    if (location.pathname.startsWith(item.key)) {
      selectedKey = item.key;
      break;
    }
  }

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        collapsedWidth="64"
        theme="dark"
        width={220}
        style={{ borderRight: "1px solid rgba(255,255,255,0.06)" }}
      >
        <div
          style={{
            height: 64,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            borderBottom: "1px solid rgba(255,255,255,0.1)",
          }}
        >
          <ThunderboltOutlined style={{ fontSize: 22, color: "#1677ff" }} />
          {!collapsed && (
            <Typography.Text
              strong
              style={{ color: "#fff", fontSize: 16, whiteSpace: "nowrap", marginLeft: 10 }}
            >
              ViMax Web
            </Typography.Text>
          )}
        </div>
        <Menu
          mode="inline"
          theme="dark"
          selectedKeys={[selectedKey]}
          onClick={({ key }) => navigate(key)}
          items={menuItems}
          style={{ borderInlineEnd: "none", marginTop: 8 }}
        />
      </Sider>
      <Layout>
        <Header style={HEADER_STYLE}>
          <Typography.Title level={5} style={{ margin: 0 }}>
            视频生成管理平台
          </Typography.Title>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Avatar
              size={32}
              style={{ backgroundColor: "#1677ff", verticalAlign: "middle" }}
              src={undefined}
            >
              {avatarChar}
            </Avatar>
            <Typography.Text style={{ fontSize: 13 }}>
              {user?.display_name || "用户"}
            </Typography.Text>
          </div>
        </Header>
        <Content style={{ margin: 20, padding: 24, background: "#fff", borderRadius: 8, minHeight: 280 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
