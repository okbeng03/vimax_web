# Tasks: ViMax Web — 视频生成管理平台

**Input**: Design documents from `/specs/001-vimax-web-platform/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/api.yaml, quickstart.md

**Tests**: Tests are NOT explicitly requested. Task list focuses on implementation.
**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Backend**: `backend/src/`, `backend/tests/`
- **Frontend**: `frontend/src/`, `frontend/tests/`
- **Runtime Data**: `data/` (auto-created)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project scaffolding and dependency installation for both frontend and backend

- [ ] T001 Scaffold backend project: create `backend/src/`, `backend/tests/`, `backend/src/models/`, `backend/src/schemas/`, `backend/src/routers/`, `backend/src/services/` directory structure per plan.md
- [ ] T002 Scaffold frontend project with Vite + React 19 + TypeScript in `frontend/`, install Ant Design 6, React Router v7, Zustand, xterm.js, Monaco Editor via `npm install`
- [ ] T003 [P] Create `backend/pyproject.toml` with FastAPI 0.137, SQLAlchemy 2.0, aiosqlite, Pydantic v2, pyyaml, httpx, aiofiles dependencies
- [ ] T004 [P] Create `backend/src/config.py` — AppSettings Pydantic model with VIMAX_ROOT, WORKING_DIR_ROOT, DATABASE_URL, COMFYUI_BASE_URL, DEFAULT_USERNAME fields, load from `.env`
- [ ] T005 [P] Configure backend linting: add `backend/pyproject.toml` Ruff config and `backend/.ruff.toml`
- [ ] T006 [P] Configure frontend linting: ESLint + Prettier configs in `frontend/.eslintrc.cjs` and `frontend/.prettierrc`
- [ ] T007 [P] Create `frontend/src/main.tsx` — React entry point with React Router v7 BrowserRouter, Ant Design ConfigProvider, global CSS import
- [ ] T008 [P] Create `frontend/src/App.tsx` — Root layout with `<Routes>` skeleton, Ant Design Layout with Sider + Content

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story — database, base models, API framework, shared types

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Database & Models

- [ ] T009 Create `backend/src/database.py` — SQLAlchemy async engine (aiosqlite), session factory, Base model, `init_db()` with seed data (user "muze", 3 templates)
- [ ] T010 [P] Create `backend/src/models/__init__.py` — import all models for Base.metadata
- [ ] T011 [P] Create `backend/src/models/user.py` — User model (id, username, display_name, created_at) per data-model.md
- [ ] T012 [P] Create `backend/src/models/template.py` — Template model (id, name, display_name, description, directory_name, is_builtin, created_at) per data-model.md
- [ ] T013 [P] Create `backend/src/models/project.py` — Project model (id, user_id FK, name, creative_description, working_dir, template_id FK, status, current_step_name, created_at, updated_at, completed_at) per data-model.md
- [ ] T014 [P] Create `backend/src/models/step.py` — Step model (id, project_id FK, name, step_order, status, started_at, completed_at, duration_seconds, output_files JSON, retry_count, error_message) per data-model.md
- [ ] T015 [P] Create `backend/src/models/generation_result.py` — GenerationResult model (id, step_id FK, project_id FK, user_id FK, file_path, thumbnail_path, prompt_id, generation_type, duration_seconds, confirmed, confirmed_at, created_at) per data-model.md
- [ ] T016 [P] Create `backend/src/models/operation_log.py` — OperationLog model (id, project_id FK, user_id FK, operation_type, target_type, target_id, target_name, summary, details JSON, created_at) per data-model.md

### API Framework

- [ ] T017 Create `backend/src/main.py` — FastAPI app with CORS middleware (allow localhost:5173), include all routers, register startup event for DB init, add health check endpoint `GET /api/health`
- [ ] T018 [P] Create `backend/src/schemas/__init__.py` — shared base Pydantic model with `from_attributes=True`
- [ ] T019 [P] Create `frontend/src/api/client.ts` — Axios instance with baseURL `http://localhost:8000/api`, error interceptors, unified error response handling
- [ ] T020 [P] Create `frontend/src/types/project.ts` — TypeScript types for Project, ProjectList, ProjectCreateRequest, ProjectConfig matching API contracts
- [ ] T021 [P] Create `frontend/src/types/step.ts` — TypeScript types for Step, StepStatus, ComfyuiResultInStep matching API contracts
- [ ] T022 [P] Create `frontend/src/types/generation.ts` — TypeScript types for GenerationResult, GenerationFilter, RetryRequest matching API contracts
- [ ] T023 [P] Create `frontend/src/types/statistics.ts` — TypeScript types for ProjectStats, GlobalStats, TrendData matching API contracts

### 3 Built-in Project Templates

- [ ] T024 Create `backend/src/templates/standard/` directory with `idea2video.yaml` and `config.py` — standard template (balanced quality/speed)
- [ ] T025 [P] Create `backend/src/templates/fast_preview/` directory with `idea2video.yaml` and `config.py` — fast preview template (lower resolution, fewer steps)
- [ ] T026 [P] Create `backend/src/templates/high_quality/` directory with `idea2video.yaml` and `config.py` — high quality template (max resolution, full pipeline)

**Checkpoint**: Foundation ready — database initialized with seed data, all 6 models created, API server boots with health check, 3 templates in place. User story implementation can now begin.

---

## Phase 3: User Story 1 — 创建并管理视频生成项目 (Priority: P1) 🎯 MVP

**Goal**: Users can create video generation projects by selecting a built-in template, view project lists with filtering/search, read/edit project config (YAML + config.py) with bidirectional sync to working_dir

**Independent Test**: Create a project via POST /api/projects, verify it appears in project list with correct template association, edit its config via PUT /api/projects/{id}/config, confirm the files are synced to working_dir, then delete the project and verify working_dir is removed

### Backend

- [ ] T027 [P] [US1] Create `backend/src/schemas/project.py` — ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse Pydantic schemas
- [ ] T028 [P] [US1] Create `backend/src/schemas/template.py` — TemplateResponse Pydantic schema
- [ ] T029 [US1] Create `backend/src/routers/templates.py` — `GET /api/templates` endpoint, query Template table, return all templates
- [ ] T030 [US1] Create `backend/src/services/config_sync.py` — ConfigSyncService with `read_yaml(working_dir)`, `read_config_py(working_dir)`, `write_yaml(working_dir, content)`, `write_config_py(working_dir, content)`, `copy_template(template_dir, target_dir)` methods using pyyaml and file I/O
- [ ] T031 [US1] Create `backend/src/routers/projects.py`:
  - `GET /api/projects` — list with status/search/page/page_size filters, return paginated projects + step_summary
  - `POST /api/projects` — create project: generate working_dir path from working_dir_root, copy template files via ConfigSyncService, create Project + Steps (14 steps initialized as pending) in DB
  - `GET /api/projects/{id}` — detail with config (yaml_content + config_py_content loaded from filesystem), steps, unconfirmed_count
  - `PUT /api/projects/{id}/config` — update YAML + config.py via ConfigSyncService, write to both DB metadata and working_dir filesystem
  - `DELETE /api/projects/{id}` — delete project + remove working_dir directory recursively
- [ ] T032 [US1] Add OperationLog auto-recording in project router: on config save, record edit_file type operation log with user_id=1 (muze)

### Frontend

- [ ] T033 [P] [US1] Create `frontend/src/api/projects.ts` — API functions: fetchProjects, createProject, fetchProject, updateProjectConfig, deleteProject
- [ ] T034 [P] [US1] Create `frontend/src/api/templates.ts` — API function: fetchTemplates
- [ ] T035 [US1] Create `frontend/src/stores/projectStore.ts` — Zustand store: projects list, currentProject, templates, loading/error states, CRUD actions
- [ ] T036 [P] [US1] Create `frontend/src/components/project/TemplateSelector.tsx` — Modal/Select component listing 3 templates with name + description, user selects one
- [ ] T037 [P] [US1] Create `frontend/src/components/project/ProjectForm.tsx` — Ant Design Modal with Form: name, creative_description (TextArea), template_id (TemplateSelector), working_dir_root (input). Call POST /api/projects on submit
- [ ] T038 [US1] Create `frontend/src/pages/ProjectList/` — Page with:
  - `ProjectListPage.tsx`: Ant Design Table/List displaying projects, search bar, status filter dropdown (idle/running/completed/failed), "New Project" button opening ProjectForm
  - Each row: project name, status tag (colored), step progress (x/14), created_at, actions (enter project, delete with confirm)
  - Sort by created_at DESC, pagination

### Config Editor (US1 Sub-feature)

- [ ] T039 [US1] Create `frontend/src/pages/ProjectDetail/` — Basic detail page shell: loads project by id, displays name/status/description, tabs placeholder (Config | Execution | Files | Generations | Logs | Stats)
- [ ] T040 [US1] Create Config tab in `ProjectDetail` page:
  - YAML editor using Monaco Editor (with YAML language mode) displaying `yaml_content`
  - config.py editor using Monaco Editor (with Python language mode) displaying `config_py_content`
  - "Save" button calling PUT /api/projects/{id}/config, show success notification
  - Auto-load: when switching between projects, editors refresh with current project's config

**Checkpoint**: US1 complete — projects can be created from templates, listed/filtered/searched, config viewed and edited with bidirectional sync to working_dir

---

## Phase 4: User Story 2 — 分步执行并实时观察视频生成过程 (Priority: P1) 🎯 MVP

**Goal**: Start ViMax pipeline via subprocess, control steps through interrupt_step, display real-time stdout via WebSocket, step-by-step confirm/retry with summary display

**Independent Test**: Start a project execution, observe WebSocket stdout streaming, verify step pauses at interrupt_step, confirm step shows output summary, click "continue" to proceed to next step, test kill to force stop

### Backend — ViMax Runner

- [ ] T041 [US2] Create `backend/src/services/vimax_runner.py` — VimaxRunner singleton class per research.md:
  - `start(project_id, working_dir, interrupt_step)`: check no other running process (409 otherwise), modify idea2video.yaml interrupt_step, launch `asyncio.create_subprocess_exec("python", "main_idea2video.py", cwd=working_dir, stdout→vimax_stdout.tmp)`, update project status → running, step status → running
  - `kill()`: kill subprocess, update project status → failed, step status → failed
  - `_monitor()`: background asyncio task polling process.returncode; on completion parse stdout for step names/status, update Step records in DB (fully_complete/partially_complete/failed), update Project status
  - `is_running()`: return whether process is alive
  - `get_current_project_id()`: return running project id
- [ ] T042 [US2] Create `backend/src/routers/ws.py` — WebSocket endpoint `WS /ws/projects/{project_id}/stdout` per research.md: accept connection, tail `{working_dir}/vimax_stdout.tmp` from last position with 500ms polling via aiofiles, send `{"type":"stdout","content":"..."}` and `{"type":"status","step_name":"...","step_status":"..."}` messages, disconnect on client close
- [ ] T043 [US2] Create `backend/src/schemas/step.py` — StepResponse, StepListResponse, StepExecuteRequest, StepKillResponse Pydantic schemas
- [ ] T044 [US2] Create `backend/src/routers/steps.py`:
  - `GET /api/projects/{id}/steps` — list all steps with status, duration, output_files, comfyui_results (nested GenerationResult)
  - `POST /api/projects/{id}/steps/execute` — parse action ("start"/"continue"/"retry_step"), determine target interrupt_step (find first non-fully_complete step), call VimaxRunner.start(), return 202
  - `POST /api/projects/{id}/steps/kill` — call VimaxRunner.kill(), return 200
  - Validate: 409 if another project running, 400 if invalid action, update OperationLog on execute/kill

### Frontend — Step Pipeline UI

- [ ] T045 [P] [US2] Create `frontend/src/api/steps.ts` — API functions: fetchSteps, executeSteps, killSteps
- [ ] T046 [P] [US2] Create `frontend/src/hooks/useWebSocket.ts` — WebSocket hook: connect to `ws://localhost:8000/ws/projects/{project_id}/stdout`, auto-reconnect on close, push messages to store
- [ ] T047 [P] [US2] Create `frontend/src/hooks/useStdout.ts` — Hook wrapping useWebSocket, buffers stdout content for terminal display, exposes `lines: string[]`, `isConnected: boolean`
- [ ] T048 [US2] Create `frontend/src/stores/executionStore.ts` — Zustand store: steps list, stdoutLines buffer, isRunning, currentStepName, execute/confirm/retry/kill actions
- [ ] T049 [P] [US2] Create `frontend/src/components/execution/TerminalView.tsx` — xterm.js Terminal component: renders stdout content from executionStore, auto-scroll to bottom, monospace font, dark theme, clear on new execution
- [ ] T050 [P] [US2] Create `frontend/src/components/execution/StepPipeline.tsx` — Ant Design Steps component: visualizes all 14 steps as vertical timeline, each step shows name + status icon (pending=circle, running=spin, fully_complete=checkmark green, partially_complete=warning orange, failed=close red), clickable to expand output preview
- [ ] T051 [P] [US2] Create `frontend/src/components/execution/StepConfirmModal.tsx` — Ant Design Modal showing step output summary: 
  - Text files: display content preview (story.txt first 500 chars)
  - Image/video: thumbnail preview if available
  - "Confirm & Continue" button → POST execute with action="continue"
  - "Regenerate" button → POST execute with action="retry_step" + step_name
- [ ] T052 [US2] Create Execution tab in `frontend/src/pages/ProjectDetail/`:
  - If project status is idle: "Start Generation" button → POST execute action="start"
  - If project status is running: show TerminalView + StepPipeline + current step info
  - "Force Stop" button (danger) → POST kill with confirm modal
  - Step list with expandable detail (duration, output_files, retry_count)

**Checkpoint**: US2 complete — ViMax pipeline runs via subprocess, steps pause at interrupt_step, stdout streams in real-time, user can confirm/retry/kill

---

## Phase 5: User Story 3 — 查看和编辑生成过程的输出文件 (Priority: P2)

**Goal**: Browse working_dir file tree, view text files (plain text + structured JSON), edit and save files that affect subsequent steps

**Independent Test**: Expand file tree in a project, click story.txt to view content in editor, edit and save, verify saved content in file system, click script.json to see structured JSON view

### Backend

- [ ] T053 [P] [US3] Create `backend/src/services/file_manager.py` — FileManager service:
  - `list_files(working_dir, relative_path)`: os.scandir, return files with name/type/size/modified_at, exclude hidden files and `vimax_stdout.tmp`
  - `read_file(working_dir, relative_path)`: read text file content, detect encoding (UTF-8), return content + size + modified_at
  - `write_file(working_dir, relative_path, content)`: write content to file, ensure parent dirs exist
  - Validate: path traversal protection (reject `../`), file size limits (max 5MB for read/edit), allowed extensions (.txt, .json, .py, .yaml, .yml)
- [ ] T054 [US3] Create `frontend/src/api/files.ts` — API functions: fetchFileTree, fetchFileContent, updateFileContent
- [ ] T055 [US3] Create `backend/src/routers/files.py`:
  - `GET /api/projects/{id}/files?path=` → FileManager.list_files(), return JSON tree
  - `GET /api/projects/{id}/files/content?path=` → FileManager.read_file(), return content response
  - `PUT /api/projects/{id}/files/content` → FileManager.write_file(), auto-create OperationLog (edit_file type)

### Frontend

- [ ] T056 [P] [US3] Create `frontend/src/hooks/useFileEditor.ts` — Hook: loads file content on path change, provides save function with optimistic update
- [ ] T057 [P] [US3] Create `frontend/src/components/file/FileTree.tsx` — Ant Design Tree component: recursively render working_dir files/directories, click file → set selected file in store, expand/collapse directories, file type icons (text/json/image/video)
- [ ] T058 [P] [US3] Create `frontend/src/components/file/TextEditor.tsx` — Monaco Editor with syntax highlighting based on file extension (.txt→plaintext, .json→JSON, .py→Python, .yaml/.yml→YAML), edit + save toolbar
- [ ] T059 [P] [US3] Create `frontend/src/components/file/JsonViewer.tsx` — React component for structured JSON display: collapsible tree view, syntax highlighted, support editing individual fields (inline edit on leaf nodes)
- [ ] T060 [US3] Create Files tab in `frontend/src/pages/ProjectDetail/`:
  - Left panel: FileTree component
  - Right panel: TextEditor (for .txt/.py/.yaml) or JsonViewer (for .json) based on file extension
  - Save button → PUT file content → success message → auto-create operation log visible

**Checkpoint**: US3 complete — files browsable in tree, text files readable/editable with syntax highlighting, JSON structured viewer working

---

## Phase 6: User Story 4 — ComfyUI 图像/视频结果管理与重试 (Priority: P2)

**Goal**: View ComfyUI generation results (images/video) with metadata, confirm/reject results, retry with modified workflow params (from working_dir/workflows), track unconfirmed count with badge

**Independent Test**: View generation results for a step, confirm one result → it collapses, retry with modified params → new result appears, unconfirmed badge shows count

### Backend

- [ ] T061 [P] [US4] Create `backend/src/services/comfyui_client.py` — ComfyUIClient per research.md:
  - `health_check(base_url)`: `GET /system_stats`, return bool, timeout 5s
  - `submit_workflow(base_url, workflow)`: `POST /prompt`, return prompt_id
  - `get_result(base_url, prompt_id)`: `GET /history/{prompt_id}`, return output file paths
  - `read_workflow_from_dir(working_dir, prompt_id)`: read workflow JSON from `{working_dir}/workflows/` (ui version + api version)
- [ ] T062 [US4] Create `backend/src/schemas/generation_result.py` — GenerationResultResponse, GenerationListResponse, GenerationsRetryRequest Pydantic schemas
- [ ] T063 [US4] Create `backend/src/routers/generations.py`:
  - `GET /api/projects/{id}/generations?confirmed=&step_name=&page=&page_size=` — list results, return with unconfirmed_count
  - `POST /api/projects/{id}/generations/{generation_id}/confirm` — set confirmed=true, confirmed_at=NOW, create OperationLog (confirm_result type)
  - `POST /api/projects/{id}/generations/{generation_id}/retry` — read workflow from working_dir/workflows via ComfyUIClient, merge modified_params, submit to ComfyUI, create new GenerationResult record, return 202 with new_generation_id + prompt_id

### Frontend

- [ ] T064 [P] [US4] Create `frontend/src/api/generations.ts` — API functions: fetchGenerations, confirmGeneration, retryGeneration
- [ ] T065 [P] [US4] Create `frontend/src/components/generation/ResultCard.tsx` — Ant Design Card:
  - Image preview (with fallback for video — first frame thumbnail), file path below
  - Metadata display: prompt_id, generation_type (tag), duration_seconds
  - "Confirm" button (check icon) → collapse card, show green border
  - "Retry (抽卡)" button → opens workflow params editor modal
  - Confirmed cards auto-collapse (show only thumbnail), unconfirmed cards stay expanded
- [ ] T066 [P] [US4] Create `frontend/src/components/generation/ResultGrid.tsx` — Ant Design Row/Col grid layout, virtual scroll (react-window) for large result lists, grouped by step step_name
- [ ] T067 [US4] Create Generations tab in `frontend/src/pages/ProjectDetail/`:
  - Tab badge showing unconfirmed count (red dot/badge)
  - Filter bar: step_name dropdown, confirmed toggle (all/unconfirmed/confirmed)
  - ResultGrid component listing all GenerationResult
  - "Collapse All Confirmed" / "Expand All" toggle button

**Checkpoint**: US4 complete — generation results viewable with preview, confirm/retry works, workflow read from working_dir/workflows, unconfirmed badge visible

---

## Phase 7: User Story 5 — 人工操作记录追踪 (Priority: P3)

**Goal**: All manual operations (edit file, confirm/reject generation, regenerate step) are automatically logged with timestamp, type, target, summary; viewable in a dedicated log page

**Independent Test**: Edit a file, confirm a generation result, regenerate a step, then visit operation log page — verify all actions appear with correct metadata

### Backend

- [ ] T068 [P] [US5] Create `backend/src/schemas/operation_log.py` — OperationLogResponse, OperationLogListResponse Pydantic schemas
- [ ] T069 [US5] Create `backend/src/routers/operations.py`:
  - `GET /api/projects/{id}/operations?type=&page=&page_size=` — list operation logs for project, filter by operation_type, paginated
  - Operations are auto-created by other routers (files save, generation confirm, step retry/execute — no separate POST endpoint)

### Frontend

- [ ] T070 [P] [US5] Create `frontend/src/api/operations.ts` — API function: fetchOperations
- [ ] T071 [P] [US5] Create `frontend/src/components/log/LogFilter.tsx` — Ant Design Select/DatePicker filter bar: operation_type dropdown, date range picker
- [ ] T072 [P] [US5] Create `frontend/src/components/log/LogTable.tsx` — Ant Design Table:
  - Columns: created_at, operation_type (tag with color coding), target_type, target_name, summary (expandable if long), user_name
  - Sort by created_at DESC, pagination
- [ ] T073 [US5] Create Operations tab in `frontend/src/pages/ProjectDetail/`:
  - LogFilter + LogTable, auto-load on mount

**Checkpoint**: US5 complete — operation logs automatically recorded by existing actions, viewable with filtering

---

## Phase 8: User Story 6 — 生成数据统计与成功率分析 (Priority: P3)

**Goal**: Project-level and global statistics: scene count, file sizes, step durations, ComfyUI success/failure rates, trend charts by day/week

**Independent Test**: View project statistics after completion, view global overview with multiple projects, verify failure reasons are tracked

### Backend

- [ ] T074 [P] [US6] Create `backend/src/services/statistics.py` — StatisticsService:
  - `project_stats(project_id)`: aggregate scene_count (from file tree), file_counts by type, total_file_size, total_duration from Steps, generation stats (total/success/failed/rate)
  - `global_overview()`: total_projects, completed/failed/running counts, success_rate, total_generations, avg_generation_duration, failure_reasons breakdown (GROUP BY error_reason), trend data (GROUP BY date for daily, GROUP BY week for weekly)
  - `failure_reasons(project_id)`: list failed GenerationResult records with reason categorized (timeout/api_error/validation_failed/connection_failed)
  - `edit_success_correlation(project_id)`: for FR-026 — join OperationLog (edit_file type) time windows with subsequent GenerationResult outcomes, compute success rate delta before/after edits per file
- [ ] T075 [US6] Create `backend/src/schemas/statistics.py` — ProjectStatsResponse, GlobalStatsResponse Pydantic schemas
- [ ] T076 [US6] Create `backend/src/routers/stats.py`:
  - `GET /api/statistics/overview` → StatisticsService.global_overview()
  - `GET /api/projects/{id}/statistics` → StatisticsService.project_stats(id)
  - `GET /api/projects/{id}/statistics/correlation` → StatisticsService.edit_success_correlation(id)

### Frontend

- [ ] T077 [P] [US6] Create `frontend/src/api/stats.ts` — API functions: fetchGlobalStats, fetchProjectStats
- [ ] T078 [P] [US6] Create `frontend/src/components/stats/StatsDashboard.tsx` — Ant Design Grid:
  - Stat cards row: total projects, completed, failed, success_rate (Progress circle), total_generations (value), avg duration
  - Failure reasons pie/bar chart (recharts or @ant-design/charts)
  - Step duration bar chart
- [ ] T079 [P] [US6] Create `frontend/src/components/stats/TrendChart.tsx` — Line/bar chart for daily/weekly trend: x=date/week, y=count, lines for success/failed/total
- [ ] T080 [US6] Create Statistics tab in `frontend/src/pages/ProjectDetail/`:
  - Project-level: scene_count, file counts/sizes card, step duration table, generation stats
  - Edit-Success Correlation panel: display operation edit records with associated generation success rate change (before/after), per FR-026
- [ ] T081 [US6] Create `frontend/src/pages/Statistics/` — Global statistics page:
  - StatsDashboard + TrendChart
  - Date range filter (last 7 days / last 30 days / all time)
  - Accessible from sidebar navigation

**Checkpoint**: US6 complete — project and global statistics with trends and failure breakdown visible

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Layout, navigation, error handling, loading states, edge case handling across all stories

- [ ] T082 [P] Create `frontend/src/components/layout/AppLayout.tsx` — Ant Design Layout: Sider with menu items (Projects, Statistics), Header with app title "ViMax Web", Content area for `<Outlet />`, responsive collapsible sidebar
- [ ] T083 [P] Create `frontend/src/components/layout/Sidebar.tsx` — Navigation menu: "项目列表" → /projects, "全局统计" → /statistics, highlight active route
- [ ] T084 Wire all routes in `frontend/src/App.tsx`:
  - `/` redirect to `/projects`
  - `/projects` → ProjectList
  - `/projects/:id` → ProjectDetail with tabs
  - `/statistics` → global Statistics page
- [ ] T085 [P] Add loading skeletons (Ant Design Skeleton) to all list/detail pages
- [ ] T086 [P] Add empty states (Ant Design Empty) for: no projects, no files, no generation results, no operation logs, no statistics
- [ ] T087 [P] Add error boundaries in `frontend/src/App.tsx` and per-page error display with retry button
- [ ] T088 Handle ComfyUI unavailable: GenerationResult listing shows "ComfyUI 不可用" notice when health check fails, partial generation results still displayable
- [ ] T089 Add GenerationResult `error_message` field (nullable VARCHAR(500)) to model — captures failure reason for stats FR-024 (create migration or add to T015 model)
- [ ] T090 Validate quickstart.md workflow end-to-end: create project → edit config → start execution → view files → manage results → check logs → view stats

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Phase 2 — No dependencies on other stories
- **User Story 2 (Phase 4)**: Depends on Phase 2 + US1 (needs Project and config_sync) — US1 must complete first
- **User Story 3 (Phase 5)**: Depends on Phase 2 + US1 + US2 (needs Step execution to generate files to browse)
- **User Story 4 (Phase 6)**: Depends on Phase 2 + US1 + US2 (needs Step execution for ComfyUI results)
- **User Story 5 (Phase 7)**: Depends on Phase 2 + US1 + US3 + US4 (logs triggered by file edit, generation confirm, step retry actions)
- **User Story 6 (Phase 8)**: Depends on Phase 2 + US1 + US2 + US4 (needs Step and GenerationResult data)
- **Polish (Phase 9)**: Depends on all desired user stories

### User Story Dependency Graph

```
Phase 1: Setup
  ↓
Phase 2: Foundational (BLOCKS ALL)
  ↓
Phase 3: US1 ───────────────┐
  ↓                          │
Phase 4: US2 ───────┐        │
  ↓                 │        │
  ├── Phase 5: US3 ─┤       │ (US3 uses files from US2, US4 uses results from US2)
  │                  │       │
  └── Phase 6: US4 ─┘       │
         ↓                  │
  Phase 7: US5 (logs from US3/US4 actions)
         ↓
  Phase 8: US6 (data from US2/US4)
         ↓
  Phase 9: Polish
```

### Within Each User Story

- Backend models/schemas first (parallel where marked [P])
- Service layer second
- Router/endpoints third
- Frontend API layer + types fourth (parallel)
- Frontend components fifth (parallel where independent)
- Frontend page integration last

### Parallel Opportunities

- Phase 1: T002, T003, T004, T005, T007, T008 can all start after T001
- Phase 2: T010-T016 (all models) + T018-T023 (all types/schemas) can run in parallel; T024-T026 (all templates) in parallel
- Phase 3: T027+T028 (schemas) parallel; T033+T034 (API) parallel; T036+T037 (components) parallel
- Phase 4: T041 can start after US1 complete; T045+T046+T047 (API + hooks) parallel; T049+T050+T051 (components) parallel
- Phase 5: T053+T054 (backend) parallel; T056+T057+T058+T059 (hooks/components) parallel
- Phase 6: T061+T062 (backend) parallel; T064+T065+T066 (API+components) parallel
- Phase 7: T068 (backend schema) + T070+T071+T072 (API+components) all parallel
- Phase 8: T074+T075 (backend) parallel; T077+T078+T079 (API+components) parallel
- Phase 9: T082+T083+T085+T086+T087 (all layout/UX) parallel

---

## Parallel Example: User Story 1

```bash
# Phase 3 backend - launch in parallel:
Task T027: "Create backend/src/schemas/project.py"
Task T028: "Create backend/src/schemas/template.py"

# After both complete, sequential:
Task T029: "Create GET /api/templates router"
Task T030: "Create ConfigSyncService"
Task T031: "Create projects router" (depends on T027, T030)
Task T032: "Add OperationLog to project router" (depends on T031)

# Phase 3 frontend - launch in parallel:
Task T033: "Create frontend/src/api/projects.ts"
Task T034: "Create frontend/src/api/templates.ts"
# Then in parallel:
Task T036: "Create TemplateSelector component"
Task T037: "Create ProjectForm component"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2)

1. Complete Phase 1: Setup (~8 tasks)
2. Complete Phase 2: Foundational (~18 tasks) — CRITICAL: blocks all stories
3. Complete Phase 3: User Story 1 (~14 tasks) — Project CRUD + config sync
4. Complete Phase 4: User Story 2 (~12 tasks) — Step execution + terminal
5. **STOP and VALIDATE**: Create a project → edit its config → start ViMax pipeline → watch stdout → confirm steps

**MVP Deliverable**: Full ViMax pipeline controllable via Web UI with project management

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1 + US2 → Test → **MVP!** (core video generation workflow)
3. US3 → Test → File browsing/editing
4. US4 → Test → ComfyUI result management
5. US5 → Test → Operation logs
6. US6 → Test → Statistics dashboard
7. Polish → Final release

### Total Task Counts

| Phase | Tasks | Story |
|-------|-------|-------|
| Phase 1: Setup | 8 | — |
| Phase 2: Foundational | 18 | — |
| Phase 3: US1 | 14 | P1 🎯 |
| Phase 4: US2 | 12 | P1 🎯 |
| Phase 5: US3 | 8 | P2 |
| Phase 6: US4 | 7 | P2 |
| Phase 7: US5 | 6 | P3 |
| Phase 8: US6 | 8 | P3 |
| Phase 9: Polish | 9 | — |
| **Total** | **90** | 6 stories |

---

## Notes

- [P] tasks = different files, no dependencies → can execute in parallel
- [Story] label maps task to specific user story for traceability
- Each user story phase produces an independently testable increment
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Quickstart.md serves as end-to-end validation script (T090)
- All user_id defaults to 1 (muze) per MVP constraints
- Frontend dev server on :5173, backend on :8000 — CORS configured in Phase 2
