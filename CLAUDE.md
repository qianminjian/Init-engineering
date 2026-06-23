# CLAUDE.md

## 项目信息

- 名称：Auto-Engineering
- 类型：Python CLI 应用 — 团队级 Loop 工程 + 多 Agent 协作
- 版本：1.0.0（设计阶段）
- 创建日期：2026-06-23

## 项目性质

本项目为 **Python 应用**，非 Claude Code Skill。使用 Claude API（Anthropic SDK）调用 LLM，Python 控制执行流。

核心依赖：`anthropic`、`click`、`pydantic`、`asyncio`

## 架构

```
Python 控制流（确定性）        LLM 调用（智能）
┌──────────────────────┐     ┌──────────────────┐
│ engine/loop.py        │     │ agents/           │
│   while True:         │────→│   architect.py   │
│     tick()            │     │   developer.py   │
│     agent.execute()   │     │   critic.py      │
│     gates.check()     │←────│                  │
│     after_tick()      │     └──────────────────┘
└──────────────────────┘
```

## 参考源码

`references/` 目录包含三个业界框架的完整源码：

| 框架 | 路径 | 核心文件 |
|------|------|---------|
| LangGraph | `references/langgraph/` | `libs/langgraph/langgraph/graph/state.py`, `pregel/_loop.py`, `pregel/_algo.py` |
| AutoGen | `references/autogen/` | `python/packages/autogen-core/src/autogen_core/_single_threaded_agent_runtime.py` |
| CrewAI | `references/crewai/` | `lib/crewai/src/crewai/crew.py`, `lib/crewai/src/crewai/task.py` |

## 核心命令（设计目标）

| 命令 | 用途 |
|------|------|
| `ae init <project>` | 项目环境初始化 |
| `ae dev-loop <requirement>` | 单需求开发循环 |
| `ae dev-loop --multi <requirement>` | 多 Agent 并行开发（未来） |
| `ae status` | 查看当前进度 |
| `ae checkpoint resume <id>` | 从 checkpoint 恢复 |

## 设计文档

- `design/v1.0-DESIGN.md` — 完整架构设计方案
- `design/` — 后续设计产出目录

## 管理约束

- tests/ 下测试，覆盖率 ≥ 80%
- 参考源码（references/）为只读，不修改
- 模板从 project-engineering-init 迁移，保持模板变量兼容
