# JD Alignment

## 岗位职责匹配

- **前后端开发与集成**：使用 FastAPI + Next.js 完成任务创建、运行详情、审批交互、benchmark 页面、diff 和 trace 展示。
- **AI 系统搭建与维护**：将 Planner、Patch Planner、受控工具层、运行时状态、失败分类和结果持久化拆成清晰模块。
- **模型接口封装**：封装 OpenAI-compatible Chat Completions API，并提供无 Key fallback，保证本地演示和测试稳定。
- **工程化 Agent 执行**：使用 Git worktree 隔离任务，记录命令风险等级、审批状态、测试输出、补丁结果和最终 diff。
- **评估驱动迭代**：通过 benchmark case 统计通过率、失败原因、失败阶段和失败命令，让 Agent 优化有数据依据。

## 任职要求匹配

- **编程基础和主流技术**：Python、TypeScript、FastAPI、Next.js、SQLAlchemy、pytest。
- **数据库与持久化**：PostgreSQL/SQLite 持久化 AgentRun、RunStep、CommandEvent 和 EvaluationRun。
- **系统调试与稳定性**：健康检查、异常分类、命令风险控制、审批恢复、无模型 Key fallback。
- **大模型应用开发**：结构化 planner 输出、patch plan 输出、模型服务商可切换、JSON 响应解析。
- **工程协作意识**：文档说明架构、运行方式、评估方法和扩展方向，便于团队接手。

## 面试讲法

可以用 STAR 结构表达：

> 我做了一个受控代码修复 Agent 平台 RepoPilot。背景是很多 AI coding demo 只展示一次性生成 patch，但真实工程里更关心可执行、可验证和可审计。所以我设计了一个 patch-test-repair 工作流：后端用 FastAPI 接收自然语言任务和本地 Git 仓库路径，运行时创建独立 worktree，先生成 repo profile 和结构化 plan，再运行 pytest 观察失败，读取候选文件，生成并应用最小 patch，最后再次跑测试并输出 diff。工程上我加入了命令风险分级、高风险命令审批、SQLAlchemy 持久化 trace、OpenAI-compatible 模型接口、无 Key fallback、Next.js 可视化运行台和 benchmark 评估页，用通过率、失败原因和修复轮数来驱动 Agent 迭代。

## 简历写法

> 设计并实现受控代码修复 Agent 平台 RepoPilot，将自然语言任务转化为可执行的 patch-test-repair 工作流；基于 FastAPI + Next.js 构建前后端闭环，使用 Git worktree 隔离运行环境，封装 OpenAI-compatible LLM、命令风险分级、人工审批、执行 trace、最终 diff 和 benchmark 评估能力，提升代码修复过程的可验证性与可审计性。
