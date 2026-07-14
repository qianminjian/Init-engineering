---
name: ae-init
description: >-
  Initialize project environment. Two modes: (1) new project wizard,
  (2) existing project auto-detection. 9 project types × 4 languages.
  Trigger: /ae-init
command: ~/.claude/skills/ae-init/.venv/bin/ae $ARGUMENTS
argument-hint: "<project> [--type <type>] [options] | --analyze <path> | update [<project>] | status"
---

# ae-init

Project environment initialization for Claude Code agent workflows.

> 🛑 **MUST_READ — 本文件 §Pipeline 是所有 init 操作的硬性前提。**
> 调用 `/ae-init` 时，**必须先读 Pipeline 章节**，对照 5 阶段逐项执行。
> **禁止手动模拟 init 流程**——必须通过 `skill()` 程序入口（`src/init_engineering/skill.py`）
> 调用 `InitWorker.execute()`，由代码强制流水线保证完整性和可恢复性。

---

## Pipeline（5 阶段流水线 — 必须使用程序入口）

ae-init 的 5 阶段流水线定义在 `src/init_engineering/init/scaffold_phases.py:InitWorker.execute()`，
经 `src/init_engineering/skill.py:skill()` 统一调用。**调用方不能跳过或手动模拟任何阶段。**

| Phase | 名称 | 职责 | 关键产出 | 代码位置 |
|-------|------|------|---------|---------|
| 1 | **detect** | 项目类型检测 + fcntl 并发锁 | `project_type` 确定 + `InitLock` | `phases/detect.py` |
| 2 | **prompt** | 加载 `ae-template.yml` + 交互问答 | `AnswersMap` (6 层 ChainMap) | `phases/prompt.py` |
| 3 | **render** | Jinja2 渲染到 tmpdir（多层模板目录合并） | 完整文件树（`_shared/` + `_features/` + type 模板） | `phases/render.py` |
| 4 | **tasks** | 执行 pre/post 钩子（git init, pm install, lefthook） | git repo + 依赖安装 + CI 配置 | `scaffold_tasks_runner.py` |
| 5 | **finalize** | 原子 copytree 到目标目录 + 写入 `.ae-answers.yml` + manifest | 最终项目目录 + `.ae-state/init-manifest.json` | `phases/finalize.py` |

### 正确调用方式

```python
# Skill 模式 — 唯一正确的调用路径
from init_engineering.skill import skill

# 存量项目分析
result = skill("init . --analyze")

# 新项目初始化（向导式）
result = skill("init my-app --type app-service")

# 非交互模式（CI / Claude Code agent）
result = skill("init my-lib --type library --defaults")
```

CLI 等效命令：`ae init <project> --type <type> [options]`

### 禁止的错误方式（红线）

| # | 禁止行为 | 后果 | 正确做法 |
|---|---------|------|---------|
| 1 | **手动创建文件模拟 init** | 只产出 3-4 个文件，遗漏 5+ 个模板文件 + `_features/` | 使用 `skill()` 入口 |
| 2 | 只读几个模板文件选择性写入 | 遗漏 `.editorconfig` / `design/INDEX.md` / `.ae-answers.yml` 等 | 让 `TemplateRenderer` 遍历全部模板目录 |
| 3 | 跳过 `skill()` 直接调用 `TemplateRenderer` | 跳过 detect + prompt + tasks + finalize，缺 `.ae-answers.yml` + manifest | 走完整 `InitWorker.execute()` |
| 4 | 用"理解→执行"替代"读 Pipeline → 调 skill()" | pipeline 代码约束被完全绕过 | 先读本文件 §Pipeline，再调 `skill()` |

### 执行前自检清单

调用 `/ae-init` 时，agent 必须先确认：

- [ ] 已读取 SKILL.md §Pipeline（本章节）
- [ ] 确认使用 `skill()` 入口，而非手动模拟
- [ ] 已知目标项目类型和语言
- [ ] 已知将产出的文件清单（对照 §Init Stage Contract 的 11 项产出物）
- [ ] 执行后逐项验证 11 项产出物是否齐全

---

## Usage

```
/ae-init init my-app --type app-service           # new TypeScript project
/ae-init init . --analyze                         # analyze existing project
/ae-init init my-lib --type library --defaults    # non-interactive, all defaults
```

## Project Types

| Type | Description |
|------|-------------|
| app-service | Web app / API service |
| library | npm/pypi/cargo/go library |
| cli-tool | CLI tool |
| skill | Claude Code Skill |
| hook | Claude Code Hook |
| mcp-server | MCP Server |
| spec-doc | Technical spec document |
| monorepo | Multi-package repo |
| plugin | Multi-Skill plugin (.claude-plugin/) |

## Common Options

- `--type <type>` — project type (app-service/cli-tool/library/skill/hook/mcp-server/spec-doc/monorepo/plugin)
- `--language <lang>` — typescript, python, go, rust
- `--ci <platform>` — github, gitlab
- `--defaults` — non-interactive mode
- `--force` — overwrite non-empty directory
- `--incremental` — only add missing files
- `--pretend` — dry-run, show what would be generated
- `--skip-tasks` — skip post-init hooks (git init, package install, etc.)
- `--use-docker / --no-docker` — toggle Docker support
- `--list-types` — list all available project types
- `--list-templates` — list all available template files

## Advanced Options

- `--package-manager <pm>` — npm, pnpm, yarn, bun, uv, poetry, pip
- `--test-runner <runner>` — pytest, jest, vitest
- `--use-typescript / --no-typescript` — toggle TypeScript
- `--use-lefthook / --no-lefthook` — toggle Lefthook git hooks
- `--templates-suffix <suffix>` — template file suffix (default: .jinja)
- `--preserve-symlinks / --no-preserve-symlinks` — preserve symlinks (default: true)
- `--from-answers <file>` — replay from saved answers
- `--no-install` — skip package manager install phase
- `--strict` — fail on any hook error
- `--verbose` — debug logging
- `--quiet` — suppress progress messages
- `--telemetry` — enable anonymous usage data collection
- `--template-dir <dir>` — use external template directory
- `--force-unsafe-template` — bypass template-dir sandbox check
- `--hook-timeout <seconds>` — override default 300s hook timeout
- `--no-cleanup` — keep tmpdir on failure for debugging

---

## Init Stage Contract (agent 行为规范)

> **ae-init 是脚手架生成器，不是应用生成器。以下规范是 agent 调用 ae-init 时的硬性约束。**

### Init 产出物（硬性要求）

ae-init 生成以下文件，全部通过验收才算 init 完成：

| # | 必须项 | 验收标准 |
|---|--------|---------|
| 1 | 工程基础配置 | `.editorconfig` `.gitignore` `.github/ci.yml` 已生成 |
| 2 | 语言工具链配置 | `tsconfig.json`/`pyproject.toml`/`Cargo.toml` 等 |
| 3 | 包管理器初始化 | `package.json`/`pyproject.toml` 含 devDependencies，`install` 成功 |
| 4 | Lint/Format 配置 | `eslint.config.js` + `prettier.config.js`（或等价物） |
| 5 | 测试框架配置 | vitest/pytest/jest 配置，示例测试可运行 |
| 6 | BEACON.md 基线 | 含「目标」「范围边界」「当前状态」三节，日期为实际日期 |
| 7 | CLAUDE.md 项目文档 | 含项目名称、类型、语言、核心命令 |
| 8 | CI 配置 | GitHub Actions / GitLab CI 基础流水线 |
| 9 | 源码入口占位 | 最小可编译/可运行的入口文件 + 对应测试 |
| 10 | LICENSE + README.md | 含项目名称和一句话描述 |
| 11 | .ae-answers.yml + init-manifest.json | 记录初始化参数和模板应用情况 |

### Init 红线（绝对不能做的事）

| # | 禁止项 | 原因 |
|---|--------|------|
| 1 | 安装业务依赖 | React/Vite/Express/Tailwind 等属于设计阶段决策 |
| 2 | 生成业务代码 | 脚手架只给入口占位（hello world），不写业务逻辑 |
| 3 | 做技术选型决策 | 不替用户选 React/Vue/Express/Django。需由 agent 提问，不能暗箱操作 |
| 4 | 覆盖已有文件 | 已有 `design/`、`styles/`、用户文档等一律保留 |
| 5 | 修改用户配置文件 | 不修改用户已有的 .env、CI 配置、规则文件 |
| 6 | 启动开发服务器 | init 阶段只验证静态正确性（tsc/lint/test），不启动 runtime |
| 7 | 填充设计文档的业务内容 | BEACON.md 填项目名/类型/日期，不填具体目标/架构 |

### Init 后强制动作

**init 完成后，agent 必须执行以下步骤，不得跳过：**

1. **验证检查清单**：
   - 所有必须文件已生成（`find` 列出文件清单）
   - 类型检查通过（`tsc --noEmit` / `mypy`）
   - 测试框架可运行（`pnpm test` / `pytest`）
   - BEACON.md 日期为实际日期
   - 已有用户文件未损坏

2. **输出完成报告**（ae-init CLI 已自动输出结构化报告）

3. **声明阶段边界** — 必须以明确语言告知用户：
   > "init 阶段完成。下一步是**设计阶段**：确认技术选型和架构方案。是否进入设计阶段？"

4. **等待用户确认** — 用户说"继续"时，**不能**直接安装业务依赖或编码。必须先确认用户意图是"继续设计阶段"还是"继续完善 init"。

### Init 后禁止

- ❌ 用户说「继续」→ 不能直接开始安装业务依赖或编码
- ❌ 看到 BEACON.md 有空标记 → 不能在 init 阶段填充业务内容
- ❌ 看到 tsconfig 路径有问题 → 不能在 init 阶段大幅修改
- ✅ 正确做法：完成报告后声明阶段边界，等用户确认

### 阶段边界图

```
┌─────────────── INIT 边界 ───────────────┐
│  脚手架生成   工程配置   工具链验证        │
│  .gitignore  tsconfig   tsc --noEmit    │
│  .editorcon  eslint     vitest run      │
│  package.js  prettier   pnpm install    │
│  BEACON.md   CI yaml                    │
│  CLAUDE.md   README                     │
│                                          │
│  ✅ 入口占位 src/index.ts (hello world) │
│  ❌ 业务组件 App.tsx / ApiKeyInput.tsx   │
│  ❌ React/Vite/Express/Tailwind 依赖     │
│  ❌ vite.config.ts (框架配置)            │
│  ❌ 业务代码                             │
└──────────────────────────────────────────┘
        │
        │  "init 完成。下一步：设计阶段"
        │
        ▼
┌─────────────── 设计阶段 ───────────────┐
│  BEACON.md 填充  技术选型  架构方案      │
└──────────────────────────────────────────┘
        │
        ▼
┌─────────────── 编码阶段 ───────────────┐
│  安装业务依赖  编写代码  修复错误  验证   │
└──────────────────────────────────────────┘
```
