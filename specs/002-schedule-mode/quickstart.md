# Quickstart: 调度模式与调度管理

**Feature**: 002-schedule-mode | **Date**: 2026-08-20

## 前置条件

1. 调度服务（Vimax Scheduler）已启动，可从 `http://127.0.0.1:8001/docs` 访问其 API 文档，且已知其分配的 `API_KEY`。
2. ViMax Web 平台（backend + frontend）可正常运行（参考 001 quickstart）。

## 配置

在 backend 运行环境设置以下配置项（沿用 `VIMAX_` 前缀环境变量，或加入 `.env`）：

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| 调度服务地址 | `VIMAX_SCHEDULE_SERVICE_URL` | `http://127.0.0.1:8001` | 调度服务 base URL |
| 调度服务 API_KEY | `VIMAX_SCHEDULE_API_KEY` | （空） | 调度服务分配的鉴权 key，请求头 `X-API-Key` 携带 |

示例 `.env`：

```bash
VIMAX_SCHEDULE_SERVICE_URL=http://127.0.0.1:8001
VIMAX_SCHEDULE_API_KEY=your-scheduler-api-key
```

> 未配置 API_KEY 时，调度模式相关操作会返回明确的鉴权错误提示。

## 启动

```bash
# backend（沿用既有方式）
cd backend
uvicorn src.main:app --reload --port 8000

# frontend（沿用既有方式）
cd frontend
npm run dev
```

## 使用流程

### 项目调度模式

1. 打开项目详情页 → 点击"开启调度模式"。
2. 点击"执行"发起生成 → 本机 vimax_main 执行并输出 `[COMFYUI SCHEDULE]::` 与 `[COMFYUI SCHEDULE DETAIL]::` 日志。
3. backend 监听日志，自动将调度事件同步到调度服务（首次自动隐式创建调度项目），项目状态显示"调度中"。
4. 调度任务未全部结束前，无法切回执行模式；可在详情页"取消调度"或置顶项目。

### 调度管理

1. 进入"调度管理"页：查看按优先级排序的调度项目列表与任务数量。
2. 置顶：对目标项目点击"置顶"（优先级设为最高）。
3. 取消：点击"取消"终止该项目全部排队任务（需确认影响范围）。
4. 获取结果：点击"获取结果"→ backend 拉取已完成列表并逐个回传 → 成功任务保存到项目目录并生成 `generation_result`，失败任务标记失败原因。
5. 项目任务列表：展开项目查看任务明细，可对排队任务执行取消。

## 验证

- [ ] `GET /api/v1/health` 通过；项目详情开启调度模式成功。
- [ ] 调度模式下执行生成，日志解析事件在 30s 内同步至调度服务（调度管理页可见任务）。
- [ ] 存在未结束调度任务时，切换执行模式被拒绝并提示。
- [ ] "获取结果"后成功任务在项目结果页可见、可预览；失败任务标记失败原因。
