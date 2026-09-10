# Research: 调度模式与调度管理

**Feature**: 002-schedule-mode | **Date**: 2026-08-20 | **Status**: Complete

## 1. 调度服务（Vimax Scheduler）API 契约调研

来源: `http://127.0.0.1:8001/openapi.json`（OpenAPI 3.1，版本 0.1.0）。调度器按**项目优先级**与**任务创建时间**生成队列，静默串行调度执行。

### 鉴权

所有接口（除 `/api/v1/health` 外）通过可选 `X-API-Key` Header 鉴权（`401` 认证失败）。

### 端点总览

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/v1/tasks` | 任务登记/同步（同 `business_task_id` 重复提交=覆盖更新；**无 priority 参数**，优先级项目级控制） |
| `GET` | `/api/v1/tasks/{business_task_id}?project_id=` | 查询任务 |
| `POST` | `/api/v1/tasks/{business_task_id}/retry?project_id=` | 重试任务（须已结束，否则 409） |
| `GET` | `/api/v1/queue` | 当前队列（含 `queue_position`、`project_priority`） |
| `GET` | `/api/v1/projects/{project_id}` | 项目详情（含 stats: total/pending/success/failed） |
| `PATCH` | `/api/v1/projects/{project_id}/priority` | 调整项目优先级（0~99，0=未设置排最后，1=最高） |
| `POST` | `/api/v1/projects/{project_id}/pause` / `resume` | 暂停 / 恢复项目 |
| `POST` | `/api/v1/projects/{project_id}/cancel` | **取消项目下全部 QUEUED 任务**（RUNNING 不受影响） |
| `GET` | `/api/v1/results?synced=false` | 未同步结果列表（含 SUCCESS/FAILED） |
| `GET` | `/api/v1/results/{business_task_id}?project_id=` | 单个任务结果详情 |
| `GET` | `/api/v1/scheduler/status` / `pause` / `resume` | 调度器状态与控制 |
| `GET` | `/api/v1/health` | 健康检查（无需鉴权） |
| `GET` | `/api/v1/service/logs` | 调度服务日志 |

### 任务登记请求体 `TaskCreate`

| 字段 | 类型 | 约束 |
|---|---|---|
| **business_task_id** | string | 调用方任务 id（应用内唯一），max 128 |
| **project_id** | integer | **ViMax_web 项目 id（调用方侧 id）** |
| **workflow** | object | ComfyUI workflow 定义（JSON 对象），**必填** |
| project_name | string/null | 项目名称，max 128 |
| outputs_id | string | 默认 `""`，max 128 |
| type | string | 固定值 `"comfyui"` |
| extend_data | object/null | 扩展数据 |

### 关键 API 缺口（影响设计）

1. **无独立"项目创建"接口**：项目在首次提交任务时**隐式创建**。→ 与规格 FR-011"首次同步自动新建项目"天然契合，无需额外调用。
2. **无单任务取消接口**：取消为**项目级**（取消该项目全部 QUEUED 任务）。→ 规格 FR-021"项目调度任务列表可取消单个任务"需适配（见决策 D4）。
3. **无批量任务提交**：一次一个任务；同 `business_task_id` 重提即覆盖。

## 2. 关键设计决策

### D1: 调度事件解析与同步链路（与既有解析完全解耦）

- **Decision**: 新增**独立模块** `ScheduleLogParser` 解析 `[COMFYUI SCHEDULE]:: prompt_id: {p}, type: {t}, workflow_name: {w}, workflow_path: {wp}, output_ids: {oid}` 与紧随的 `[COMFYUI SCHEDULE DETAIL]:: file_path: {fp}`，以 prompt_id 为键缓存拼接成完整调度事件。**既有 `GenerationParser`（解析中文日志生成 generation_result）、执行状态机与结果落库路径零改动**；监听沿用"轮询 vimax_output.tmp"模式，在 `generation_monitor` 中**仅并行追加**调度分支的调用，不改动其既有解析/推送/落库逻辑。调度监听仅在项目开启调度模式后激活（默认旁路）。
- **Rationale**: 复用既有文件轮询基础设施，避免双进程读文件；调度日志（`[COMFYUI SCHEDULE]::`）与既有中文日志格式正交，独立解析器互不干扰，杜绝影响既有 generation_result 生成逻辑。
- **Alternatives considered**: 在既有 GenerationParser 内扩展格式（污染既有解析，风险高，否决）；独立 asyncio 任务读文件（重复基建）；在 ws.py 推送链路解析（耦合实时推送，历史日志丢失）。

### D2: 任务登记字段映射

- **Decision**: `business_task_id = 本地 prompt_id`；`project_id = 本地 Project.id`（即调度服务侧保存的 web 项目 id，与 Q4 澄清一致）；`project_name = 本地项目名`；`outputs_id = output_ids[0]`（日志单节点）；`type = "comfyui"`；`workflow = 从 workflow_path 读取的 workflow JSON 内容`。
- **Rationale**: prompt_id 全局唯一天然满足 business_task_id 唯一性；project_id 使用 web 侧 id 与调度服务设计（保存调用方项目 id）一致；workflow 对象为调度服务执行所必需。
- **Alternatives considered**: 自生成 business_task_id（破坏与 prompt_id 的映射可追溯性）。
- **风险**: workflow_path 可能指向本地 workflow JSON 文件（如 `{working_dir}/workflows/{name}.json`）；若读取失败，先以 `{"name": workflow_name}` 最小对象提交并记录告警，重试后仍失败则标记同步失败进入重试队列（不阻塞日志监听）。

### D3: 调度事件提交（直接请求调度器）

- **Decision**: Web 监听到 `[COMFYUI SCHEDULE]` 日志后**直接**调用调度器 `POST /api/v1/tasks` 提交（`submit_schedule_event`），**不落本地队列**；任务与队列执行记录由调度器维护，Web 通过调度服务 API 查询。提交失败（网络/401/5xx）返回 `error`，监听侧进程内去重（known_ids）并下次轮询重试提交；workflow 缺失/损坏返回 `invalid` 直接放弃并告警，避免无限重试。
- **Rationale**: 满足 FR-012（同步失败不静默丢弃）与"调度服务不可用不丢失事件"；避免 Web 侧维护与调度器重复的队列状态（调度器已记录任务与队列）。
- **Alternatives considered**: 本地队列表持久化 + 后台重试（调度器已承担任务/队列记录职责，本地重复维护状态易产生双写不一致，已废弃）。

### D4: 任务级取消的 API 适配

- **Decision**: 调度服务仅支持项目级取消（`POST /api/v1/projects/{id}/cancel`，取消该项目全部 QUEUED 任务）。前端"项目调度任务列表"中的单个任务取消，映射为项目级取消并在 UI 明确提示影响范围（"将取消该项目下全部排队任务"），需用户确认；对 RUNNING/成功/失败任务不提供取消入口（FR-022）。
- **Rationale**: 尊重调度服务能力边界，避免伪造单任务取消语义；产品行为可通过确认对话框保障（与规格 FR-021/FR-022 验收一致）。
- **Alternatives considered**: 用"覆盖更新"重传终止标记（无文档支持、依赖调度器内部行为，不可靠）；本地伪状态（调度服务实际仍会执行，误导用户）。

### D5: 置顶映射

- **Decision**: "置顶"= 调用 `PATCH /api/v1/projects/{id}/priority` 将优先级设为 1（最高）；"取消置顶/恢复默认"= priority 设 0。调度管理列表按 `project_priority`（升序，0 排最后）展示，与调度服务 `GET /api/v1/projects/{id}` / `GET /api/v1/queue` 数据一致。
- **Rationale**: 调度服务以 1=最高、0=未设置为语义，与规格"置顶=提升到最高优先级"一致。
- **Alternatives considered**: 本地自定义排序（与调度器实际队列顺序不一致，误导）。

### D6: 结果回传流程

- **Decision**: "获取结果"按钮 → backend 调 `GET /api/v1/results?synced=false` 取未同步已完成列表（含 SUCCESS/FAILED）→ 逐个调 `GET /api/v1/results/{business_task_id}?project_id=` 取结果详情：
  - **SUCCESS**: 从 `result.view_urls`（ComfyUI view 预览地址）逐文件调用 ComfyUI view API 拉取输出 → 保存到 `{project.working_dir}/` 结果目录 → 落库 `GenerationResult`（file_path/storage_path/prompt_id/workflow_name/generation_type 与既有格式一致），并建立 prompt_id → GenerationResult 的去重（复用现有 DB 去重）。
  - **FAILED**: 记录失败状态与 `failure_reason`，不生成成功结果（FR-020）。
- **Rationale**: 与用户澄清一致（先列表后逐个获取）；view_urls 直接消费调度服务产出的 ComfyUI 预览地址，保存后复用既有预览/确认/重试能力。
- **Alternatives considered**: 前端直接访问 ComfyUI（绕过 backend，鉴权与路径映射不可控）。

### D7: 模式切换与"调度中"状态

- **Decision**: `Project` 扩展 `schedule_mode`（bool）与 `schedule_status`（idle/scheduling）。开启调度模式即时生效；提交成功产生调度任务 → `schedule_status=scheduling`；用户"获取结果"或主动刷新时，若调度服务侧该项目无未结束任务（stats.pending=0），则回到 `idle`。切换执行模式的约束条件：`schedule_mode=true 且调度服务 stats.pending>0` → 拒绝并提示。
- **Rationale**: 满足 FR-003/FR-004；调度任务的"未结束"判定以调度服务实时统计为准（任务与队列记录由调度器维护）。
- **Alternatives considered**: 仅依赖本地状态（任务在调度服务排队中本地无法感知，误放行切换）。

### D8: 配置项

- **Decision**: `config.py` 新增 `SCHEDULE_SERVICE_URL`（默认 `http://127.0.0.1:8001`）与 `SCHEDULE_API_KEY`（默认空），环境变量前缀沿用 `VIMAX_`（即 `VIMAX_SCHEDULE_SERVICE_URL` / `VIMAX_SCHEDULE_API_KEY`）。
- **Rationale**: 与既有 pydantic-settings 配置风格一致（FR-001）；API_KEY 未配置时调度操作返回明确错误提示。
- **Alternatives considered**: 无。

### D9: 数据库迁移与向后兼容（不破坏既有数据）

- **Decision**: 采用**启动时幂等迁移**：应用启动时执行 `PRAGMA table_info(projects)` 检查，对缺失的 `schedule_mode` / `schedule_status` / `schedule_updated_at` 列执行 `ALTER TABLE projects ADD COLUMN`（均带默认值：`false` / `'idle'` / NULL）。**不新增本地表**（任务与队列记录由调度器维护）。不引入 Alembic、不重建表、不触碰既有行数据与既有查询。
- **Rationale**: 现有项目无迁移框架（SQLite + create_all），启动时幂等 ALTER 是零依赖的最小侵入方案；默认值保证既有行读取正常、既有功能不受影响；重复启动幂等不报错。
- **Alternatives considered**: 引入 Alembic（引入重依赖、与既有启动流程不符，过重）；删除重建库表（破坏既有数据，不可接受）。
- **验证**: `test_migration.py` 覆盖：已有库（含旧数据）启动后新列存在、旧数据保留、二次启动幂等。

## 3. 测试策略

- **单元测试**: `schedule_log_parser`（正则解析、DETAIL 拼接、缺 file_path 暂存、重复行去重）；`schedule_sync`（字段映射、首次隐式建项目断言、重试退避、结果回传映射、模式切换约束）。
- **集成测试**: `schedule_client` 用 httpx `MockTransport` 模拟调度服务（成功/401/网络异常），验证 `X-API-Key` 头与端点路径。
- **前端测试**: 调度管理页列表渲染/置顶/取消交互、项目详情调度模式开关与切换约束提示。

## 4. 需要规划期注意的开放点

- workflow_path 实际指向的文件布局（`{working_dir}/workflows/` vs `VIMAX_ROOT/workflows/`）——实现时以 vimax_main 日志实际输出为准，解析器对两种路径前缀均兼容。
- 调度服务 `has_sync` 标记机制：拉取结果后若调度服务要求显式确认同步，则补充确认调用；当前 API 未见独立确认端点，按"拉取即同步"处理，规划期结合调度服务实际行为验证。
