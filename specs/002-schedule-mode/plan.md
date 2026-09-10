# Implementation Plan: 调度模式与调度管理

**Branch**: `002-schedule-mode` | **Date**: 2026-08-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-schedule-mode/spec.md`

## Summary

在现有 ViMax Web 平台（FastAPI + React）上集成独立调度服务（Vimax Scheduler，`http://127.0.0.1:8001`，`X-API-Key` 鉴权），实现：

1. **项目调度模式**：项目详情支持开启/关闭调度模式；调度模式下监听 vimax_main 日志中的 `[COMFYUI SCHEDULE]::` 与 `[COMFYUI SCHEDULE DETAIL]::` 记录，解析出与 generation_result 同构的调度事件（prompt_id、type、workflow_name、workflow_path、output_ids、file_path），自动同步到调度服务（首次隐式创建项目）；产生调度任务后项目状态更新为"调度中"；调度未完成前禁止切回执行模式；支持置顶与取消。
2. **调度管理**：新增调度管理页，透传调度服务 API：调度项目列表（按优先级排序、任务统计）、获取调度结果（`/api/v1/results` → 逐个任务结果 → ComfyUI view 拉取 → 保存到项目目录 → 生成 `generation_result`）、置顶（PATCH priority）、取消（POST cancel）、项目任务列表。

技术方案：backend 新增调度服务客户端（httpx + X-API-Key）、日志调度事件解析器（新增独立模块，与既有 generation_parser 完全解耦）、调度同步服务；Project 模型增量扩展调度字段（带迁移兼容）；本地仅建"待同步事件队列"表用于失败重试，调度项目/任务数据以调度服务为准（透传）。前端新增调度管理页 + 项目详情调度模式开关。

## 增量扩展与兼容性保障（不破坏既有逻辑）

本功能为现有平台**增量扩展**，明确以下兼容性边界（详见 research.md D1/D9）：

1. **解析链路隔离**：既有 `GenerationParser`（解析中文日志生成 `generation_result`）与执行/落库路径**零改动**。新增独立 `ScheduleLogParser` 解析 `[COMFYUI SCHEDULE]::` 新格式，两者并行、互不干扰；`generation_monitor` 仅新增调度分支的**并行调用**，不改动其既有轮询、推送与结果落库逻辑。
2. **项目状态机不受影响**：既有 `Project.status`（idle/running/completed/failed）状态机保持原样；新增 `schedule_mode` / `schedule_status` 为**独立维度**，不参与、不覆盖既有状态判定。模式切换约束只在用户主动切换执行模式时生效，不改变既有执行流程内部逻辑。
3. **数据库向后兼容**：`Project` 新增列通过**启动时幂等迁移**（`PRAGMA table_info` 检查缺失列后 `ALTER TABLE ADD COLUMN`，带默认值）添加；不引入 Alembic、不重建表、不影响既有行数据与既有查询。**不新增本地表**：任务与队列执行记录由调度器维护。
4. **默认关闭、旁路生效**：调度模式开关默认关闭；非调度项目（既有全部项目）行为与现在**完全一致**，不新增任何调度调用或日志解析。调度分支仅在项目开启调度模式后才激活。
5. **API 全部新增**：Web 端新增 `/api/projects/{id}/schedule-*` 与 `/api/schedule/*` 端点；不修改、不删除任何既有端点；`main.py` 仅追加注册新 router。
6. **配置项带默认值**：新增 `SCHEDULE_SERVICE_URL`（默认 `http://127.0.0.1:8001`）与 `SCHEDULE_API_KEY`（默认空），缺失时不报错、仅调度操作提示，不影响既有启动与功能。

## Technical Context

**Language/Version**:  Python 3.13（backend，FastAPI）；TypeScript + React 18（frontend，Vite）

**Primary Dependencies**:
- backend: FastAPI、SQLAlchemy 2.x (async, aiosqlite)、pydantic-settings、httpx（新增，调度服务客户端）、aiofiles
- frontend: React 18、Ant Design、zustand、axios（现有 API 客户端扩展）

**Storage**: SQLite（`sqlite+aiosqlite:///data/vimax_web.db`）。**不新增本地表**（任务与队列记录由调度器维护）；`Project` 表**增量扩展** `schedule_mode`、`schedule_status`、`schedule_updated_at` 字段（启动时幂等 `ALTER TABLE ADD COLUMN` 迁移，带默认值，不重建表、不影响既有数据）。

**Testing**: pytest（backend，含 httpx MockTransport 模拟调度服务）；vitest + Testing Library（frontend，如已有测试框架则沿用）

**Target Platform**: macOS 本地（ViMax 执行环境）+ 浏览器（前端）

**Project Type**: Web 应用（前后端分离，现有 001 平台扩展）

**Performance Goals**: SC-002 — 调度事件从日志出现到同步至调度服务 ≤30s；SC-006 — 触发"获取结果"后结果回传 ≤3min

**Constraints**: 调度服务为外部依赖，须通过 `X-API-Key` 鉴权；调度服务无独立项目创建接口（首次提交任务隐式创建）、无单任务取消接口（取消为项目级，仅 QUEUED 任务）；调度模式切换受未结束任务约束

**Scale/Scope**: 单用户本地工具；调度项目 ≤ 数十、单项目任务 ≤ 数百

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

基于既有 `specs/001-vimax-web-platform/plan.md` 的宪章原则（constitution.md 为模板占位，沿用平台既有四项原则）：

| # | 原则 | 本功能落实 |
|---|------|-----------|
| 1 | 代码质量优先：分层清晰、复用既有服务（generation_monitor/parser 模式） | ✅ 新增解析器/客户端复用既有文件轮询与 GenerationResult 落库模式；与既有解析/执行/落库逻辑完全解耦，不破坏原逻辑（见"增量扩展与兼容性保障"） |
| 2 | 测试标准：核心解析/同步/约束逻辑有单元测试 | ✅ 日志解析、事件去重、模式切换约束、结果回传映射纳入测试 |
| 3 | 用户体验一致性：沿用 Ant Design、项目详情交互风格、错误提示模式 | ✅ 调度模式开关与既有项目操作一致；调度管理页沿用表格/按钮风格 |
| 4 | 性能要求：实时性满足规格成功标准 | ✅ SC-002/SC-006 可衡量目标纳入验收 |

**Gate 结论**: 通过，无违规需要豁免。

## Project Structure

### Documentation (this feature)

```text
specs/002-schedule-mode/
├── plan.md              # This file
├── spec.md              # Feature spec
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── api.yaml
└── checklists/
    └── requirements.md
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── config.py                    # 增量修改：+ SCHEDULE_SERVICE_URL / SCHEDULE_API_KEY（带默认值）
│   ├── models/
│   │   ├── project.py               # 增量修改：+ schedule_mode / schedule_status / schedule_updated_at（幂等迁移）
│   │   └── migration.py             # NEW 启动时幂等 ALTER TABLE 迁移（不破坏既有表/数据）
│   ├── schemas/
│   │   ├── project.py               # 增量修改：+ schedule 字段（响应，默认值）
│   │   └── schedule.py              # NEW 调度相关请求/响应模型
│   ├── services/
│   │   ├── schedule_client.py       # NEW 调度服务 HTTP 客户端（X-API-Key）
│   │   ├── schedule_log_parser.py   # NEW [COMFYUI SCHEDULE]:: 日志解析（独立模块，不改既有 generation_parser）
│   │   ├── schedule_sync.py         # NEW 直接提交调度器（submit_schedule_event）/结果回传
│   │   └── generation_monitor.py    # 增量修改：仅并行追加调度监听分支调用，不改动既有解析/推送/落库逻辑
│   ├── routers/
│   │   ├── projects.py              # 增量修改：仅追加调度模式/状态端点，不改既有端点
│   │   └── schedule.py              # NEW 调度管理 API（透传）
│   └── main.py                      # 增量修改：仅追加注册 schedule router
└── tests/
    ├── test_schedule_log_parser.py
    ├── test_schedule_sync.py
    ├── test_schedule_client.py
    └── test_migration.py            # 迁移幂等性 + 既有数据保留

frontend/
├── src/
│   ├── api/
│   │   └── schedule.ts              # NEW 调度 API client
│   ├── pages/
│   │   ├── ProjectDetail/           # 增量修改：+ 调度模式开关/状态/取消/置顶入口（不影响既有执行/结果逻辑）
│   │   └── ScheduleManagement/      # NEW 调度管理页
│   ├── router.tsx                   # 增量修改：仅追加 /schedule 路由
│   └── types/
│       └── schedule.ts              # NEW 调度类型定义
└── tests/
    └── ScheduleManagement.test.tsx
```

**Structure Decision**: 采用前后端分离现有结构（Option 2 Web application），调度逻辑全部落在 backend `services/schedule_*` 与 `routers/schedule.py`，前端新增独立页面与 API 模块，复用既有 Ant Design 与项目详情交互模式。

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

无违规，无需填写。

## Phase 0 & Phase 1 交付物

- `research.md` — 调度服务 API 契约调研、关键设计决策（事件同步映射、任务取消适配、结果回传流程、workflow 对象来源、重试策略）
- `data-model.md` — Project 扩展字段、schedule_sync_queue 表、状态机
- `contracts/api.yaml` — web 端新增 API + 调度服务对接端点映射
- `quickstart.md` — 配置与运行说明
- `CODEBUDDY.md` — 更新 agent context 指向本 plan
