# CLAUDE.md

## ⚠️ 硬禁令（2026-06-24 96GB 内存爆炸事故后确立）

**核心风险**：96GB 内存爆炸事故 — 3 个 subagent 并行扫描 `references/` 全量建立 file tree index，触发 macOS `vm-compressor-space-shortage` → 系统强制重启。

**参考源码已迁出项目根**（路径：`~/Documents/06-Mi-Model-Rule/历史项目或资料备份/auto-eng/references/`，下文 `$AE_REFS_DIR/`）。

**禁止：批量 / 并行加载（事故根因）：**

- ❌ 禁止并行启动多个 subagent 同时扫描 `$AE_REFS_DIR/`
- ❌ 禁止一次性 Read 整个框架（如 Read `$AE_REFS_DIR/langgraph/` 全部文件）
- ❌ 禁止 `ls -R $AE_REFS_DIR/` 递归列出全部文件（等同批量索引）
- ❌ 禁止 `find $AE_REFS_DIR/` 不带过滤列出所有文件
- ❌ 禁止 `grep -r $AE_REFS_DIR/` 后批量 Read 多个匹配文件

**允许的探索方式（单次 / 小批量 — 不触发内存爆炸）：**

- ✅ `ls $AE_REFS_DIR/` 顶层（只 6 个子目录名，轻量）
- ✅ `find $AE_REFS_DIR/ -name "目标.py" -type f`（定位单个文件）
- ✅ `grep -n "符号" $AE_REFS_DIR/特定路径`（只输出匹配行）
- ✅ Read 单个文件 50-200 行片段（用 `offset`/`limit`，绝不整文件 Read）
- ✅ 一次只探索一个组件（如只探索 `langgraph/pregel/_loop.py`）
- ✅ 探索后立即总结要点 + 丢弃 context，不缓存

**纪律：**

- 探索 ≠ 批量：可以探索，但限制单次 / 并行量级
- 优先 Grep 定位 → 50-200 行 Read → 立即丢弃（三步法）
- 不并行触发多 subagent 全量扫描 `$AE_REFS_DIR/`（事故根因）

**已迁出项目根**（`.gitignore` 保留防御行 + `pyrightconfig.json` 已移除 exclude）。

**Why：** 2026-06-24 16:10 atdo Phase 02 spawn 3 个 subagent，每个 claude code 进程启动时扫描项目根建立 file tree index（含 references/），3 个进程叠加吃掉 96 GB 物理内存，触发 macOS `vm-compressor-space-shortage` → 系统强制重启。

**How to apply：** 任何需要参考实现的场景，必须先 Grep 定位 50-200 行片段，绝不批量 Read。

---

## 项目信息

- 名称：Init-Engineering
- 类型：**Agent Skill** — 在 Claude Code agent 里以 skill 模式运行的项目环境初始化工具
- 版本：v5.0（聚焦 Init Engineering，Loop 已裁剪）
- 创建日期：2026-06-23
- 更新日期：2026-06-30

## 项目性质

本项目为 **Claude Code Skill**，在 agent 里调用，为 agent 工作流提供项目环境初始化能力。

两种初始化模式：
1. **存量项目**：通过代码分析自动识别项目类型、依赖、配置，自动化初始化
2. **新项目**：向导式询问确认方向，生成定制化项目骨架

核心依赖：`click`、`pydantic`、`asyncio`、`jinja2`、`pathspec`

## 架构

```
Init-Engineering
├── init/                          # 初始化引擎核心
│   ├── answers.py                 # AnswersMap（6层答案链）
│   ├── config_loader.py          # 配置加载 + 安全校验
│   ├── config_types.py           # 配置类型定义
│   ├── detector.py               # 项目类型检测器（82行）
│   ├── detector_constants.py     # DetectionResult + 常量
│   ├── detector_analyzers.py     # 深度分析器
│   ├── detector_helpers.py       # 检测辅助函数
│   ├── errors.py                 # 9个异常类 + recovery_hint
│   ├── hooks.py                  # TaskRunner（pre/post钩子执行）
│   ├── prompts.py                # InteractivePrompt（交互式问答）
│   ├── renderer.py               # Jinja2模板渲染
│   ├── scaffold_hooks.py         # 内置钩子（git/pm/lefthook）
│   ├── scaffold_lock.py          # fcntl并发锁 + 心跳
│   ├── scaffold_phases.py        # InitWorker 5阶段编排器
│   ├── scaffold_prereq.py        # 前置条件检查
│   ├── scaffold_question_eval.py # Question when条件求值
│   ├── scaffold_render.py        # 渲染调度
│   ├── scaffold_tasks_runner.py  # Phase 4任务执行
│   ├── scaffold_update.py        # run_update增量更新
│   ├── phases/                   # 5阶段实现
│   │   ├── detect.py             # Phase 1: 类型检测+锁
│   │   ├── prompt.py             # Phase 2: 加载+问答
│   │   ├── render.py             # Phase 3: Jinja2渲染
│   │   └── finalize.py           # Phase 5: 原子复制+post_install
│   ├── _shared/                  # init内部共享
│   │   ├── io.py                 # YAML读写+临时文件
│   │   ├── exclude.py            # 模板排除匹配
│   │   └── path_utils.py         # 路径安全工具
│   └── templates/                 # 102个模板文件（11类型+_shared+_features）
├── config/                        # 共享配置
│   └── environment.py            # ProjectEnvironment
├── cli/                          # CLI入口
│   ├── __init__.py               # Click命令组
│   ├── commands.py               # cmd_init + cmd_status
│   ├── subcommands.py            # update子命令
│   └── _helpers.py               # 日志配置
├── _shared/                       # 包级共享
│   └── detection.py              # 跨层共享检测工具
├── skill.py                      # Agent Skill入口
└── telemetry.py                  # 遥测（默认localhost）
```

**参考框架：**

| 框架 | 路径 | 核心文件 | 用途 |
|------|------|---------|------|
| Copier | `$AE_REFS_DIR/copier/` | `_main.py`(Worker), `_user_data.py`(Question/AnswersMap) | init 脚手架参考 |
| Cookiecutter | `$AE_REFS_DIR/cookiecutter/` | `generate.py`, `prompt.py`, `main.py` | init 模板渲染参考 |
| Yeoman | `$AE_REFS_DIR/yeoman/` | `lib/routes/` | init 组合模式参考 |

## 设计文档

| 文档 | 内容 | 读取条件 |
|------|------|---------|
| `design/BEACON.md` | 设计基线（目标/范围/决策/当前状态） | 任何设计讨论时先读 |
| `design/his_bak/v5.0-Design-Init.md` | v5.0 Init Engineering 完整设计 | 开发 init 子系统时 |
| `design/his_bak/v1.0-Design-Init.md` | v1.0 init 子系统设计 + 实现偏差审计 | 开发 `ae init` 时 |
| `design/his_bak/v1.0-Design-Templates.md` | 43 个模板文件 + 8 个 ae-template.yml | 实现 `init/templates/` 时 |
| `design/his_bak/v1.0-Design-Shared.md` | 共享架构、CLI 设计、共享契约 | Init/Loop 共享契约参考 |
| `design/his_bak/audit-backlog.md` | 已知但暂不修复的审计发现（避免重复报） | **任何审计前必须先读** |

## 安装

```bash
# 首次安装：从 GitHub 克隆到 skill 目录
git clone https://github.com/qianminjian/Init-engineering.git ~/.claude/skills/ae-init/

# 更新到最新版本
cd ~/.claude/skills/ae-init && git pull origin main
```

> skill 目录是只读安装态，开发在项目目录进行。

## 核心命令

```bash
# Agent Skill 模式
ae init                              # 新项目：向导式初始化
ae init --analyze <path>            # 存量项目：代码分析 + 自动初始化

# CLI 模式
ae init <project> --type <type>     # 项目类型：app-service/cli-tool/library/skill/hook/mcp-server/spec-doc/monorepo/plugin
ae init --list-types                # 列出支持的项目类型
ae init --list-templates            # 列出可用模板

# 其他 CLI 命令
ae update [project]                 # 增量更新已有项目
ae status                           # 查看项目环境状态
```

## 管理约束

- tests/ 下测试，覆盖率 ≥ 80%
- 测试运行遵守 `@.claude/rules/pytest-memory-management.md`（16G 内存约束）
- 参考源码（`$AE_REFS_DIR/`）为只读，不修改
- 模板从 project-engineering-init 迁移，保持模板变量兼容
