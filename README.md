# RepoPilot

RepoPilot 是一个受控代码修复 Agent 平台。用户输入本地 Git 仓库路径和自然语言修复任务后，系统会在隔离的 worktree 中分析仓库、规划修复、运行测试、生成补丁、再次验证测试，并在前端展示执行轨迹、命令日志、补丁计划和最终 diff。

项目重点不是做一个聊天式写代码助手，而是把代码修复流程工程化：每一步可观察、命令执行有权限边界、结果可复盘，并支持用 benchmark case 批量评估 Agent 的成功率和失败原因。

## 核心能力

- **Plan-Act-Observe-Repair 流程**：先生成 repo profile 和结构化计划，再读文件、应用补丁、运行测试并记录结果。
- **隔离执行环境**：每次任务都会基于目标仓库创建独立 Git worktree，避免污染原始工作区。
- **受控命令执行**：命令按风险分级处理；`pytest`、`git diff` 等安全命令自动执行，高风险依赖安装命令需要审批。
- **OpenAI-compatible LLM 接口**：可接入 OpenAI、DeepSeek、Qwen 等兼容 Chat Completions 的服务；无 API Key 时提供 deterministic fallback，方便本地演示和测试。
- **可视化运行台**：Next.js 前端展示运行摘要、规划结果、patch plan、测试观察、命令日志和最终 diff。
- **Benchmark 评估**：支持批量执行 case，统计通过率、平均修复轮数、失败原因、失败阶段和失败命令。

## 技术栈

- Backend：Python 3.11、FastAPI、Pydantic、SQLAlchemy、httpx、pytest
- Frontend：Next.js、TypeScript、React、Recharts、CSS Modules
- Infra：Docker Compose、PostgreSQL、Git worktree
- AI：OpenAI-compatible Chat Completions API

## 快速启动

### 1. 后端

```bash
cd apps/api
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

### 2. 前端

```bash
cd apps/web
npm install
npm run dev
```

访问 `http://localhost:3000/dashboard`。

### 3. Docker Compose

```bash
docker compose up --build
```

## API 示例

创建一次代码修复任务：

```bash
curl -X POST http://localhost:8000/api/runs \
  -H "Content-Type: application/json" \
  -d "{\"repo_path\":\"D:\\repos\\example-python-service\",\"task_input\":\"Fix the failing boundary check so zero raises ValueError.\",\"base_ref\":\"HEAD\"}"
```

运行 benchmark：

```bash
curl -X POST http://localhost:8000/api/evals \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"RepoPilot Sample Benchmark\",\"cases_path\":\"D:\\找实习\\insight-agent-studio\\benchmark\\cases\\sample_cases.json\"}"
```

## 项目结构

```text
insight-agent-studio
├── apps
│   ├── api                 # FastAPI 后端与 RepoPilot Runtime
│   │   └── app
│   │       ├── api         # REST API
│   │       ├── db          # SQLAlchemy models/session
│   │       ├── repopilot   # repo 管理、工具层、LLM、runtime、benchmark
│   │       └── schemas     # 请求/响应模型
│   └── web                 # Next.js 可视化前端
├── benchmark
│   └── cases               # benchmark case 文件
├── docs                    # 架构、设计和简历表达文档
├── docker-compose.yml
└── README.md
```

## 适合写进简历的描述

> 设计并实现受控代码修复 Agent 平台 RepoPilot，将自然语言修复任务转化为可执行的 patch-test-repair 工作流；基于 FastAPI + Next.js 构建前后端闭环，使用 Git worktree 隔离每次运行，封装 OpenAI-compatible 模型调用、命令风险分级、人工审批、执行 trace、最终 diff 和 benchmark 评估能力，提升代码修复过程的可验证性、可观察性与可审计性。
