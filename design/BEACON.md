> 创建：2026-06-24 | 更新：2026-07-02 | 阶段：v1.0 投产就绪

## 目标与成功标准

1. **Agent Skill 模式运行**：`ae init` 作为 Claude Code Skill 在 agent 里调用，为 agent 工作流提供项目环境初始化能力
2. **存量项目自动初始化**：通过代码分析自动识别项目类型、依赖、配置，生成正确的初始化配置
3. **新项目向导初始化**：交互式询问确认项目方向、技术栈、目录结构，生成定制化项目骨架
4. **模板组合引擎**：10 类型 × 4 语言（含 plugin 多 Skill 插件模板）
5. **路径穿越防护**：!include + external_data 路径必须在 sandbox 内（realpath 双侧校验）
6. **项目升级支持**：`ae update` 重新渲染已有项目模板，支持 skip/overwrite/prompt 三种冲突策略
7. **CI / Docker / Lefthook 条件渲染**：use_docker / use_lefthook / ci_platform 字段控制可选模板

## 范围边界

**做：**
- Agent Skill 模式：`ae init` 作为 Claude Code Skill 在 agent 里调用
- 存量项目初始化：代码分析 → 自动识别 → 自动化配置
- 新项目向导：交互式询问 → 确认方向 → 生成骨架
- 升级模式：`ae update` 重新渲染已有项目，保留用户修改
- 10 类型 × 4 语言模板：app-service / cli-tool / library / monorepo / mcp-server / spec-doc / skill / hook / plugin
- 语言特性：TypeScript / Python / Go / Rust
- 条件化 feature：lefthook / docker / github-actions / gitlab-ci
- init 模板体系：50+ 模板文件 + `ae-template.yml` 完整字段集
- 路径穿越防护 + 钩子错误传播 + fcntl 并发锁

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
| 5 | **统一版本号：__version__ = _ae_version = "1.0.0"** | 消除 v0.1.0/1.0.0/5.0.0 三元不一致；设计文档 v5.0.0 笔误已修正 | 2026-07-02 | ✅ |
| 6 | **monorepo 支持 4 语言（typescript/python/go/rust）** | 通过 _nested_templates 切换子目录，每个语言对应独立 workspace 模板 | 2026-07-02 | ✅ |
| 7 | **InitWorker 拆分为 5 阶段函数（scaffold_phase_funcs.py）** | scaffold_phases.py 501→235 行，满足 300 行硬约束 | 2026-07-02 | ✅ |
| 8 | **detector 拆分为 constants/analyzers/helpers** | detector.py 382→179 行；解除 detector ↔ analyzer 循环依赖 | 2026-07-02 | ✅ |
| 9 | **run_update() 实现** | 类比 Copier `copier update`；支持 skip/overwrite/prompt 冲突策略 | 2026-07-02 | ✅ |
| 10 | **AnswerMap 6 层 ChainMap 简化** | 来源 Copier 8 层；优先级 cli > interactive > previous > defaults > builtins > external | 2026-07-01 | ✅ |
| 11 | **5 类渲染生命周期钩子** | before_renderer / on_exists / after_renderer / tasks_before / tasks_after | 2026-07-01 | ✅ |
| 12 | **CLI 单版本透传 templates_suffix / preserve_symlinks** | TemplateConfig 默认值可被 CLI 覆盖 | 2026-07-01 | ✅ |

## 当前状态

**阶段：** v1.0 投产就绪

**最近动作：** 2026-07-02 投产就绪 7 项 — 统一版本号 1.0.0 / monorepo 4 语言支持 / 拆分 scaffold_phases 与 detector 满足 300 行硬约束 / run_update() 实现 + 6 个测试 / BEACON 同步到 v1.0

**下一步：** 无 — 当前为最终版本

**阻塞项：** 无

## 设计演进日志

| 日期 | 变更 | 原因 |
|------|------|------|
| 2026-07-02 | v1.0 投产就绪 7 项 | 统一版本号 / monorepo 4 语言 / InitWorker 拆分 / detector 拆分 / run_update / BEACON 同步 |
| 2026-07-01 | 第三轮深度修复 3 项 | lefthook 条件门控 + ProjectDetector 深度分析(依赖解析/框架识别/包管理器推断) + hook多语言/spec-doc 7段BEACON+ADR |
| 2026-07-01 | 第二轮优化 5 项 | CI 条件渲染 + 清理 Copier 遗留文件 + --language CLI + 共享模板泛化 + project_name 默认值 |
| 2026-07-01 | 全面投产修复 7 项 | P0: builtin hooks 非阻塞 + Skill 注册 / P1: 6 类型模板 + 4 feature + ae-feature 泄露 + 布尔值 + __main__ |
| 2026-06-30 | v5.0 精简 + 项目目标更新 | 明确 Agent Skill 模式、存量/新项目两种初始化路径 |
| 2026-06-24 | Init 深度审计 21 项 | 对照设计+实现+Copier/Cookiecutter/Yeoman 源码 |

## 待解决问题

| 状态 | 问题 | 说明 |
|------|------|------|
| [✓] | 代码分析深度 | 已实现：依赖解析 + 框架识别 + 包管理器/测试框架/CI 自动推断 |
| [✓] | monorepo 多语言 | 已实现：typescript/python/go/rust 通过 _nested_templates 切换 |
| [✓] | run_update 命令 | 已实现：skip/overwrite/prompt 三种冲突策略 + 6 个测试 |
| [✓] | 模板版本约束 | 已实现：_min_ae_version vs __version__ 强校验 |

## 引用文件

@design/INDEX.md · @design/v5.0-Design-Init.md · @design/v1.0-Design-Init.md · @design/v1.0-Design-Templates.md · @design/his_bak/
