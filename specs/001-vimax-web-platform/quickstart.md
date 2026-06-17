# Quickstart: ViMax Web 平台

**Feature**: 001-vimax-web-platform | **Date**: 2026-06-17

## 前置条件

- Python 3.13 安装并可用
- Node.js 20+ (LTS)
- ViMax 源码位于 `/Users/wangchangbin/ai/ViMax-main`
- ComfyUI 服务 (可选，无 ComfyUI 时平台仍可运行但图像生成部分跳过)

## 快速启动

### 1. 后端 (FastAPI)

```bash
cd backend

# 创建虚拟环境
python3.13 -m venv venv
source venv/bin/activate

# 安装依赖
pip install fastapi==0.137.* uvicorn sqlalchemy[aiosqlite] aiosqlite pydantic pyyaml httpx aiofiles

# 初始化数据库 (创建表 + 种子数据)
python -m src.database --init

# 启动服务
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. 前端 (React)

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

访问 `http://localhost:5173`

### 3. 验证

```bash
# 后端健康检查
curl http://localhost:8000/api/health

# 查看模板列表
curl http://localhost:8000/api/templates | python -m json.tool

# 创建第一个项目
curl -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{"name":"测试项目","creative_description":"一只小猫","template_id":1,"working_dir_root":"/Users/wangchangbin/ai/vimax_ru"}'
```

## 项目配置

环境变量（可选，有默认值）:

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `VIMAX_ROOT` | `/Users/wangchangbin/ai/ViMax-main` | ViMax 源码根目录 |
| `WORKING_DIR_ROOT` | `./data/projects` | 项目工作目录根 |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/vimax_web.db` | SQLite 数据库路径 |
| `DEFAULT_USERNAME` | `muze` | 默认用户名 |

## 首次使用流程

1. 打开 `http://localhost:5173`
2. 点击"新建项目"，选择模板（标准视频/快速预览/高质量）
3. 填写项目名称和创意描述
4. 进入项目，查看/编辑 idea2video.yaml 和 config.py
5. 点击"开始生成"，观察 stdout 终端输出
6. 每个步骤完成后在确认弹窗中查看结果，点击"确认继续"或"重新生成"
7. 在"生成结果"标签页管理 ComfyUI 输出，确认满意的结果
8. 完成后查看统计数据
