> 创建：2026-06-24 | 更新：2026-06-30 | 阶段：v5.0 Init Engineering（Agent Skill 模式）

## 目标与成功标准

1. **Agent Skill 模式运行**：`ae init` 作为 Claude Code Skill 在 agent 里调用，为 agent 工作流提供项目环境初始化能力
2. **存量项目自动初始化**：通过代码分析自动识别项目类型、依赖、配置，生成正确的初始化配置
3. **新项目向导初始化**：交互式询问确认项目方向、技术栈、目录结构，生成定制化项目骨架
4. **模板组合引擎**：8 类型 × 4 语言 = 32 种模板组合，覆盖 app-service/cli/library/package 四类
5. **路径穿越防护**：!include 路径必须在项目根内，禁止 `..` 逃逸
6. **钩子错误传播**：模板渲染失败时错误信息可追踪到具体文件和行号

## 范围边界

**做：**
- Agent Skill 模式：`ae init` 作为 Claude Code Skill 在 agent 里调用
- 存量项目初始化：代码分析 → 自动识别 → 自动化配置
- 新项目向导：交互式询问 → 确认方向 → 生成骨架
- init 模板体系：43 个模板文件 + `ae-template.yml` 8 字段
- 路径穿越防护 + 钩子错误传播
- `ae init` CLI 命令
- 项目类型：app-service / cli / library / package
- 技术栈：Python / TypeScript / JavaScript / Go

**不做：**
- dev-loop 开发循环（Loop Engineering 已裁剪）
- 多 LLM Provider 支持
- Web UI 界面
- 远程模板 / 嵌套交互
- CrewAI Memory/RAG、AutoGen Pub/Sub、Jinja2 用于 Task 描述

## 设计决策

| # | 决策 | 理由 | 日期 | status |
|---|------|------|------|--------|
| 1 | **v5.0 精简：只保留 Init 部分，Loop 部分裁剪** | 项目聚焦 Init 工程，Loop 功能不在本项目范围 | 2026-06-30 | ✅ |
| 2 | **Agent Skill 模式：init 作为 agent 内 skill 运行** | agent 工作流中需要项目初始化能力 | 2026-06-30 | ✅ |
| 3 | **存量项目：代码分析驱动自动初始化** | 减少人工配置成本，通过分析现有代码推断正确配置 | 2026-06-30 | ✅ |
| 4 | **新项目：向导式询问确认方向** | 新项目方向不明确，需要交互式确认 | 2026-06-30 | ✅ |

## 当前状态

**阶段：** v5.0 Init Engineering（Agent Skill 模式）

**最近动作：** 2026-06-30 更新项目目标 — 明确为 Agent Skill 模式、存量项目自动初始化、新项目向导初始化

**下一步：** 基于新的项目目标更新设计文档和代码实现

**阻塞项：** 无

## 设计演进日志

| 日期 | 变更 | 原因 |
|------|------|------|
| 2026-06-30 | v5.0 精简 + 项目目标更新 | 明确 Agent Skill 模式、存量/新项目两种初始化路径 |
| 2026-06-24 | Init 深度审计 21 项 | 对照设计+实现+Copier/Cookiecutter/Yeoman 源码 |

## 待解决问题

| 状态 | 问题 | 说明 |
|------|------|------|
| [Q?] | 代码分析深度？ | 存量项目识别需要分析多少代码才能准确初始化？ |
| [Q?] | 向导字段数量？ | 新项目向导需要询问多少字段？哪些是必填？ |

## 引用文件

@design/INDEX.md · @design/v5.0-Design-Init.md · @design/v1.0-Design-Init.md · @design/v1.0-Design-Templates.md · @design/his_bak/
