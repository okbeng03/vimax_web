import { Routes, Route, Navigate } from "react-router-dom";
import { Suspense, lazy } from "react";
import { Spin } from "antd";
import AppLayout from "./components/layout/AppLayout";

const ProjectList = lazy(() => import("./pages/ProjectList/ProjectListPage"));
const ProjectDetail = lazy(() => import("./pages/ProjectDetail/ProjectDetailPage"));
const Statistics = lazy(() => import("./pages/Statistics/StatisticsPage"));
const TemplateManagement = lazy(() => import("./pages/TemplateManagement/TemplateManagementPage"));

function Loading() {
  return (
    <div style={{ textAlign: "center", padding: 100 }}>
      <Spin size="large" />
    </div>
  );
}

function App() {
  return (
    <Suspense fallback={<Loading />}>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Navigate to="/projects" replace />} />
          <Route path="/projects" element={<ProjectList />} />
          <Route path="/projects/:id" element={<ProjectDetail />} />
          <Route path="/templates" element={<TemplateManagement />} />
          <Route path="/statistics" element={<Statistics />} />
        </Route>
      </Routes>
    </Suspense>
  );
}

export default App;
