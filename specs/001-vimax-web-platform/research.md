# Research: ViMax Web 平台技术调研

**Feature**: 001-vimax-web-platform | **Date**: 2026-06-17

## 1. ViMax Subprocess 管理

**Decision**: 使用 `asyncio.create_subprocess_exec` 启动 ViMax，通过全局单例 `VimaxRunner` 管理进程生命周期。

**Rationale**:
- FastAPI 原生支持 async/await，`asyncio.create_subprocess_exec` 不阻塞事件循环
- 全局单例确保 FR-011 约束（最多 1 个项目生成中）
- stdout 重定向到临时文件，WebSocket 从文件 tail 读取并推送
- `subprocess.kill()` 实现用户手动中断

**Alternatives considered**:
- `subprocess.Popen` + 线程池：需要额外线程管理，与 async 生态割裂
- Celery 任务队列：过度工程化，ViMax 任务本质是单一长进程
- Docker 容器化：MVP 阶段引入运维复杂度，不必要

**Key Patterns**:
```python
# VimaxRunner 单例
class VimaxRunner:
    _instance = None
    _process: asyncio.subprocess.Process | None = None
    _current_project_id: int | None = None

    async def start(self, project_id: int, working_dir: Path, config: dict):
        if self._process and self._process.returncode is None:
            raise ConflictError("Another project is already running")
        # Write interrupt_step to YAML before launch
        # Redirect stdout to {working_dir}/vimax_stdout.tmp
        self._process = await asyncio.create_subprocess_exec(
            "python", "main_idea2video.py",
            cwd=working_dir,
            stdout=open(working_dir / "vimax_stdout.tmp", "w"),
            stderr=asyncio.subprocess.STDOUT,
        )
        self._current_project_id = project_id

    async def kill(self):
        if self._process:
            self._process.kill()
            await self._process.wait()

    async def wait(self):
        return await self._process.wait()
```

---

## 2. WebSocket stdout 实时推送

**Decision**: 使用 FastAPI WebSocket + `aiofiles` tail 临时日志文件实现实时 stdout 推送。

**Rationale**:
- ViMax stdout 写入临时文件（覆盖模式），Web 端无需持久化历史日志
- `aiofiles` 支持 async 文件读取，不阻塞事件循环
- 轮询间隔 500ms 读取文件增量，平衡实时性与 CPU 开销
- 前端 xterm.js 渲染终端输出，无需额外组件

**Alternatives considered**:
- SSE (Server-Sent Events)：单向推送够用但 WebSocket 提供更丰富的双向通信语义（未来可用于发送 kill 信号）
- pipe 直接读取 subprocess stdout：内存占用不确定，无法在浏览器重连后恢复
- Redis pub/sub：引入额外依赖，过度工程化

**Key Patterns**:
```python
@router.websocket("/ws/projects/{project_id}/stdout")
async def stdout_websocket(websocket: WebSocket, project_id: int):
    await websocket.accept()
    log_path = get_project_working_dir(project_id) / "vimax_stdout.tmp"
    last_pos = 0
    while True:
        if log_path.exists():
            async with aiofiles.open(log_path, "r") as f:
                await f.seek(last_pos)
                new_content = await f.read()
                if new_content:
                    await websocket.send_text(new_content)
                    last_pos = await f.tell()
        await asyncio.sleep(0.5)
```

---

## 3. ComfyUI API 集成

**Decision**: 通过 HTTP 客户端直接调用 ComfyUI REST API (`/prompt`, `/history/{prompt_id}`)，封装为 `ComfyUIClient`。

**Rationale**:
- ComfyUI 暴露标准 REST API，无需额外适配层
- 健康检查通过 `GET /system_stats` 实现，失败时标记步骤为"部分完成"
- Workflow 定义（ui 版和 api 版）存储于 {working_dir}/workflows/ 目录，前端展示和重试时按 prompt_id 读取
- 支持编辑 workflow 后重新 POST 提交（抽卡模式）

**Alternatives considered**:
- ComfyUI WebSocket API：功能更丰富但 MVP 阶段 REST 足够
- 直接操作 ComfyUI 的 `output/` 目录：绕过 API 不可控，不选

**Key Patterns**:
```python
class ComfyUIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.base_url}/system_stats", timeout=5)
                return resp.status_code == 200
        except Exception:
            return False

    async def submit_workflow(self, workflow: dict) -> str:
        """Returns prompt_id"""
        ...

    async def get_result(self, prompt_id: str) -> dict:
        """Returns generation result with output file paths"""
        ...
```

---

## 4. YAML/Config 双向同步

**Decision**: `ConfigSyncService` 直接读写文件系统，不引入版本控制或 diff 引擎。

**Rationale**:
- FR-003 要求保存后同步到 working_dir，切换项目时回读
- 使用 `pyyaml` 读写 YAML，使用 `importlib` 动态加载 config.py（仅读取）
- config.py 的编辑通过文本编辑模式实现（非结构化表单），用户自行保证语法正确
- 每次保存覆盖写入，不保留历史版本（操作记录表记录变更摘要）

**Alternatives considered**:
- Git 版本控制：过度工程化，操作记录已覆盖变更追踪需求
- 结构化表单编辑 config.py：config.py 变量复杂（嵌套 dict），文本编辑更灵活

---

## 5. SQLite + SQLAlchemy Async (aiosqlite)

**Decision**: 使用 `SQLAlchemy 2.0` async engine + `aiosqlite` 驱动，Pydantic v2 做序列化。

**Rationale**:
- SQLite 零配置、单文件、适合本地单用户
- `aiosqlite` 提供原生 async 支持，与 FastAPI async handler 无缝集成
- SQLAlchemy 2.0 ORM 声明式模型，迁移用 Alembic（可选）
- 统计查询通过 SQLAlchemy `func.count/sum/group_by` 直接在 SQLite 完成

**Alternatives considered**:
- Tortoise ORM：社区较小，SQLAlchemy 生态更成熟
- Peewee：不支持 async
- 纯文件 JSON 存储：查询和统计复杂度高

---

## 6. React + Ant Design 6 项目结构

**Decision**: Vite + React 19 + Ant Design 6 + React Router v7，使用 Zustand 做轻量状态管理。

**Rationale**:
- Vite 构建速度快，HMR 体验好
- Ant Design 6 提供统一的组件库，满足设计系统一致性要求
- Zustand 比 Redux 轻量，适合 MVP 规模的状态管理
- React Router v7 支持数据加载和代码分割
- xterm.js 用于终端模拟器，Monaco Editor 用于代码/YAML 编辑

**Alternatives considered**:
- Next.js：SSR 不必要（localhost 单用户），引入额外复杂度
- Umi.js：与 Ant Design 集成好但黑盒化程度高

---

## 7. 步骤完成状态机

**Decision**: Step 状态流转：`待执行 → 执行中 → 完全完成 | 部分完成 | 失败`

**Rationale**:
- "完全完成"：所有产出已生成，包括 ComfyUI 图像/视频
- "部分完成"：仅文本产出生成，ComfyUI 部分因服务不可用跳过 → 允许进下一步
- "失败"：ViMax 进程异常退出或用户 kill
- 下次运行从第一个非"完全完成"步骤开始（清除该步骤缓存 + 设置 interrupt_step）

**State Machine**:
```
待执行 ──[start]──→ 执行中 ──[success+comfyui_ok]──→ 完全完成
                     │
                     ├──[success+comfyui_down]──→ 部分完成 ──[re-run]──→ 执行中
                     │
                     └──[error/kill]──→ 失败 ──[retry]──→ 待执行
```
