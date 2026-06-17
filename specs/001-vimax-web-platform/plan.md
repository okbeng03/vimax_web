# Implementation Plan: ViMax Web — 视频生成管理平台

**Branch**: `001-vimax-web-platform` | **Date**: 2026-06-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-vimax-web-platform/spec.md`

## Summary

将 ViMax CLI 视频生成工具封装为 Web 平台，核心能力包括：项目管理（模板创建、配置双向同步）、分步执行与实时可视化（subprocess 调用 ViMax + WebSocket stdout 推送 + interrupt_step 断点控制）、ComfyUI 结果管理（预览/确认/重试抽卡）、人工操作记录追踪、统计数据分析。技术方案：React + Ant Design 6 前端 SPA，Python 3.13 + FastAPI 0.137 后端 API，SQLite 元数据存储 + 文件系统产物存储。

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript 5.x (frontend)
**Primary Dependencies**: FastAPI 0.137, SQLAlchemy 2.0 + aiosqlite, Pydantic v2, React 19 + Ant Design 6, xterm.js (terminal), Monaco Editor (code editor)
**Storage**: SQLite (元数据) + 本地文件系统 (生成产物)
**Testing**: pytest + pytest-asyncio (backend), Vitest + React Testing Library (frontend)
**Target Platform**: macOS 本地开发 / localhost Web 应用 (MVP)
**Project Type**: Web 应用 (前后端分离 SPA)
**Performance Goals**: FCP ≤1.5s, LCP ≤2.5s, 步骤过渡 ≤2s, 文件编辑保存响应 ≤3s
**Constraints**: 全局最多 1 个 ViMax 进程运行中, localhost 单用户, 无认证 (MVP)
**Scale/Scope**: 单用户, 数十个项目, 数百个生成结果/项目, 6 个核心页面

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原则 | 检查项 | 状态 | 说明 |
|------|--------|------|------|
| **一、代码质量优先** | 命名语义化、函数 ≤200 行、文件 ≤500 行 | ✅ PASS | 前后端分别强制执行 |
| | 代码风格一致性 | ✅ PASS | 前端 ESLint + Prettier, 后端 Ruff |
| | 外部输入校验 | ✅ PASS | FastAPI Pydantic 校验 + 前端表单校验 |
| | 禁止 console.log / 魔法数字 / 废弃代码 | ✅ PASS | ESLint no-console + 审查流程 |
| **二、测试标准** | 单元测试覆盖率 ≥80% | ✅ PASS | pytest-cov + Vitest coverage |
| | 组件测试覆盖可复用组件 | ✅ PASS | React Testing Library |
| | 集成测试覆盖关键流程 | ✅ PASS | Playwright E2E (项目创建→生成→确认) |
| | CI 测试失败阻塞合并 | 🔄 DEFERRED | CI 配置在 MVP 后实施 |
| **三、用户体验一致性** | Ant Design 6 统一组件库 | ✅ PASS | 全站使用 Ant Design 6 |
| | 响应式三断点 (375/768/1280px) | ✅ PASS | Ant Design Grid 响应式布局 |
| | 可访问性 WCAG 2.1 AA | ⚠️ ATTENTION | xterm.js 终端和 Monaco Editor 需额外 a11y 检查 |
| | Loading/空/错误状态覆盖 | ✅ PASS | 全页面覆盖 |
| | i18n 国际化就绪 | 🔄 DEFERRED | MVP 阶段中文硬编码，预留 i18n 结构 |
| **四、性能要求** | FCP ≤1.5s, LCP ≤2.5s | ✅ PASS | SPA + CDN 静态资源 |
| | INP ≤200ms | ✅ PASS | React concurrent 特性 |
| | 大列表虚拟滚动 | ✅ PASS | 生成结果列表使用虚拟滚动 |
| | 图片 WebP/懒加载 | ✅ PASS | ComfyUI 结果预览 |

**Gate Result**: ✅ ALL PASS — No blocking violations. Two items deferred to post-MVP (CI config, i18n). One attention item (terminal a11y) noted but not blocking.

## Project Structure

### Documentation (this feature)

```text
specs/001-vimax-web-platform/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (API contracts)
└── tasks.md             # Phase 2 output (NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── main.py                  # FastAPI app entry point
│   ├── config.py                # App configuration (DB path, ViMax path, working_dir root)
│   ├── database.py              # SQLAlchemy engine + session factory
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py              # User model (default "muze")
│   │   ├── project.py           # Project model
│   │   ├── step.py              # Step model (with completion states)
│   │   ├── generation_result.py # ComfyUI generation result model
│   │   ├── operation_log.py     # Operation log model
│   │   └── template.py          # Project template model
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── project.py           # Pydantic request/response schemas
│   │   ├── step.py
│   │   ├── generation_result.py
│   │   ├── operation_log.py
│   │   └── statistics.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── projects.py          # /api/projects CRUD
│   │   ├── steps.py             # /api/projects/{id}/steps execution
│   │   ├── files.py             # /api/projects/{id}/files browser + edit
│   │   ├── generations.py       # /api/projects/{id}/generations ComfyUI results
│   │   ├── operations.py        # /api/projects/{id}/operations logs
│   │   ├── stats.py             # /api/statistics
│   │   ├── templates.py         # /api/templates
│   │   └── ws.py                # WebSocket endpoint for stdout streaming
│   ├── services/
│   │   ├── __init__.py
│   │   ├── vimax_runner.py      # ViMax subprocess manager (start/kill/stdout capture)
│   │   ├── file_manager.py      # File system operations (read/write/browse working_dir)
│   │   ├── config_sync.py       # YAML/config.py bidirectional sync
│   │   ├── comfyui_client.py    # ComfyUI API client (health check, query, submit)
│   │   └── statistics.py        # Statistics computation service
│   └── templates/               # Built-in project templates
│       ├── standard/
│       │   ├── idea2video.yaml
│       │   └── config.py
│       ├── fast_preview/
│       │   ├── idea2video.yaml
│       │   └── config.py
│       └── high_quality/
│           ├── idea2video.yaml
│           └── config.py
└── tests/
    ├── conftest.py
    ├── unit/
    │   ├── test_vimax_runner.py
    │   ├── test_file_manager.py
    │   ├── test_config_sync.py
    │   └── test_statistics.py
    └── integration/
        ├── test_project_api.py
        ├── test_step_execution.py
        └── test_generation_api.py

frontend/
├── src/
│   ├── main.tsx                 # React entry point
│   ├── App.tsx                  # Root component with router
│   ├── api/
│   │   ├── client.ts            # Axios/fetch wrapper
│   │   ├── projects.ts          # Project API calls
│   │   ├── steps.ts             # Step execution API calls
│   │   ├── files.ts             # File API calls
│   │   ├── generations.ts       # Generation result API calls
│   │   ├── operations.ts        # Operation log API calls
│   │   ├── stats.ts             # Statistics API calls
│   │   └── ws.ts                # WebSocket client for stdout
│   ├── pages/
│   │   ├── ProjectList/         # 项目列表页 (P1)
│   │   ├── ProjectDetail/       # 项目详情 + 执行面板 (P1)
│   │   ├── FileEditor/          # 文件查看编辑 (P2)
│   │   ├── GenerationManager/   # ComfyUI 结果管理 (P2)
│   │   ├── OperationLog/        # 操作记录 (P3)
│   │   └── Statistics/          # 统计分析 (P3)
│   ├── components/
│   │   ├── layout/              # AppLayout, Sidebar, Header
│   │   ├── project/             # ProjectCard, ProjectForm, TemplateSelector
│   │   ├── execution/           # StepPipeline, StepConfirmModal, TerminalView
│   │   ├── file/                # FileTree, TextEditor, JsonViewer
│   │   ├── generation/          # ResultGrid, ResultCard, WorkflowEditor
│   │   ├── log/                 # LogTable, LogFilter
│   │   └── stats/               # StatsDashboard, TrendChart
│   ├── hooks/
│   │   ├── useWebSocket.ts      # WebSocket connection hook
│   │   ├── useStdout.ts         # Terminal stdout stream hook
│   │   ├── useProjectPolling.ts # Project status polling
│   │   └── useFileEditor.ts     # File read/write hook
│   ├── stores/                  # Zustand or Context state
│   │   ├── projectStore.ts
│   │   └── executionStore.ts
│   ├── types/
│   │   ├── project.ts
│   │   ├── step.ts
│   │   ├── generation.ts
│   │   └── statistics.ts
│   └── utils/
│       ├── formatters.ts
│       └── validators.ts
├── public/
│   └── index.html
└── tests/
    ├── components/
    │   ├── ProjectCard.test.tsx
    │   ├── TerminalView.test.tsx
    │   └── ResultGrid.test.tsx
    └── e2e/
        └── project-flow.spec.ts  # Playwright E2E

# Shared workspace data
data/
├── vimax_web.db               # SQLite database (auto-created)
└── projects/                  # All project working_dirs
    └── {project_id}/
        ├── idea2video.yaml
        ├── config.py
        ├── vimax_stdout.tmp   # Temporary stdout log
        ├── story.txt
        ├── script.json
        ├── storyboard.json
        └── ...
```

**Structure Decision**: 采用 Web 应用 Option 2 (前后端分离)。`backend/` 使用 FastAPI + SQLAlchemy + SQLite，`frontend/` 使用 React + Ant Design 6。项目数据存储在 `data/` 目录下，与源代码分离。此结构天然支持前端通过 API 调用后端，后端通过 subprocess 管理 ViMax 进程。

## Complexity Tracking

> No constitution violations requiring justification.
