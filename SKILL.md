---
name: ae-init
description: >-
  Initialize project environment. Two modes: (1) new project wizard,
  (2) existing project auto-detection. 9 project types × 5 languages.
  Trigger: /ae-init
command: ~/.claude/skills/ae-init/.venv/bin/ae $ARGUMENTS
argument-hint: "<project> [--type <type>] [options] | --analyze <path> | update [<project>] | status"
---

# ae-init

Project environment initialization for Claude Code agent workflows.

> **MUST_READ — 本文件 §Pipeline 是所有 init 操作的硬性前提。**
> 调用 `/ae-init` 时，**必须先读 Pipeline 章节**，对照 5 阶段逐项执行。
> **禁止手动模拟 init 流程**——必须通过 `skill()` 程序入口调用 `InitWorker.execute()`。

---

## Quick Reference

```
# ── 新项目 ──────────────────────────────────────
/ae-init init my-app --type app-service              # TS 全栈应用
/ae-init init my-lib --type library --language py    # Python 库
/ae-init init my-cli --type cli-tool --defaults      # 全部默认, 无交互
/ae-init init my-skill --type skill                  # Claude Code Skill

# ── 存量项目 ────────────────────────────────────
/ae-init init . --analyze                           # 自动检测 + 报告
/ae-init init . --analyze --include-hidden           # 含 .qoder/.claude/ 资产
/ae-init init . --incremental                        # 只补缺失文件

# ── 查询 ────────────────────────────────────────
/ae-init init --list-types                           # 列出 9 种项目类型
/ae-init init --list-templates                       # 列出所有模板文件

# ── 特殊场景 ────────────────────────────────────
/ae-init init . --force                              # 覆盖非空目录
/ae-init init my-app --from-answers .ae-answers.yml  # 从答案文件重放
/ae-init init my-app --pretend                       # 模拟, 不写文件
```

---

## Pipeline（5 阶段流水线 — 必须使用程序入口）

5 阶段流水线定义在 `InitWorker.execute()`，经 `skill()` 统一调用。**调用方不能跳过或手动模拟任何阶段。**

| Phase | 名称 | 职责 | 关键产出 |
|-------|------|------|---------|
| 1 | **detect** | 项目类型检测 + fcntl 并发锁 | `project_type` + `InitLock` |
| 2 | **prompt** | 加载 `ae-template.yml` + 交互问答 | `AnswersMap` (6 层 ChainMap) |
| 3 | **render** | Jinja2 渲染到 tmpdir | 完整文件树 |
| 4 | **tasks** | pre/post 钩子 (git init, pm install, lefthook) | git repo + deps |
| 5 | **finalize** | 原子 copytree + `.ae-answers.yml` + manifest | 最终项目 + `.ae-state/` |

### 正确调用方式

```python
from init_engineering.skill import skill
result = skill("init . --analyze")                    # 存量项目分析
result = skill("init my-app --type app-service")      # 新项目向导
result = skill("init my-lib --type library --defaults")  # CI/非交互
```

CLI 等效：`ae init <project> --type <type> [options]`

### 禁止的错误方式（红线）

| # | 禁止行为 | 后果 | 正确做法 |
|---|---------|------|---------|
| 1 | 手动创建文件模拟 init | 遗漏 5+ 模板文件 + `_features/` | 使用 `skill()` 入口 |
| 2 | 只读几个模板文件选择性写入 | 遗漏 `.editorconfig` / `design/INDEX.md` 等 | 让 `TemplateRenderer` 遍历全部模板 |
| 3 | 跳过 `skill()` 直接调 `TemplateRenderer` | 缺 `.ae-answers.yml` + manifest | 走完整 `InitWorker.execute()` |
| 4 | 用"理解→执行"替代"读 Pipeline → 调 skill()" | pipeline 代码约束被绕过 | 先读本文件 §Pipeline，再调 `skill()` |

---

## 两种模式

| 模式 | 命令 | 流程 |
|------|------|------|
| **新项目** | `/ae-init init <dir> --type <type>` | 交互问答 → 渲染模板 → 生成骨架 |
| **存量项目** | `/ae-init init <dir> --analyze` | 代码扫描 → 自动识别语言/框架/PM/CI → 增量补充 |
| **增量补充** | `/ae-init init <dir> --incremental` | 基于 .ae-answers.yml 只补缺失文件 |

## 项目类型 (--type)

| 类型 | 说明 | 典型产出的文件 |
|------|------|--------------|
| `app-service` | Web 应用 / API 服务 | src/, tests/, Dockerfile, CI |
| `library` | npm/pypi/cargo/go 库 | src/, tests/ |
| `cli-tool` | CLI 命令行工具 | src/cli/, tests/ |
| `skill` | Claude Code Skill | SKILL.md, .claude/skills/ |
| `hook` | Claude Code Hook | hook 脚本, 配置 |
| `mcp-server` | MCP 服务器 | MCP 清单, src/, tests/ |
| `spec-doc` | 技术规范文档 | design/, docs/ |
| `monorepo` | 多包仓库 | packages/, workspace 配置 |
| `plugin` | 多 Skill 插件 | .claude-plugin/, skills/ |

## 语言 (--language)

`typescript` (默认) · `python` · `go` · `rust` · `java`

monorepo 类型根据 `--language` 选择子模板 (5 语言各一套 workspace 配置)。

## 参数全集

### 基础控制

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `--type` | str | 自动检测 | 项目类型 (见上表) |
| `--language` | str | typescript | 主要语言 |
| `--defaults` | flag | false | 非交互, 全部用默认值 |
| `--force` | flag | false | 允许覆盖非空目录 |
| `--incremental` | flag | false | 只补缺失文件, 不覆盖已有 |
| `--quiet` | flag | false | 静默模式, 不输出进度 |
| `--verbose` | flag | false | DEBUG 日志 |

### 存量项目分析

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `--analyze` | flag | false | 只分析不初始化, 输出检测报告 |
| `--include-hidden` | flag | false | 扫描 .qoder/.claude/ 等隐藏目录 |

### 组件开关 (布尔, 可 --no 取反)

| 参数 | 默认 | 说明 |
|------|------|------|
| `--use-typescript / --no-typescript` | true (TS 项目) | TypeScript 支持 |
| `--use-docker / --no-docker` | false | Dockerfile + .dockerignore |
| `--use-lefthook / --no-lefthook` | true | git hooks (lefthook) |

### 工具链覆盖 (自动检测, 可手动指定)

| 参数 | 自动检测方式 | 可选值 |
|------|------------|--------|
| `--package-manager` | 扫描 lock 文件 | npm, pnpm, yarn, bun, uv, poetry |
| `--test-runner` | 扫描配置/依赖 | jest, vitest, pytest |
| `--ci` | 扫描 .github/workflows/ | github, gitlab |

### 模板与渲染

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `--template-dir <path>` | path | 内置模板 | 外部模板目录 |
| `--force-unsafe-template` | flag | false | 绕过模板目录安全白名单 |
| `--templates-suffix` | str | .jinja | 模板文件后缀 |
| `--preserve-symlinks / --no-preserve-symlinks` | bool | true | 渲染时保留符号链接 |

### 钩子与安装

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `--skip-tasks` | flag | false | 跳过所有 post-init 钩子 |
| `--no-install` | flag | false | 仅跳过依赖安装 (CI/离线场景) |
| `--strict` | flag | false | 钩子失败时抛异常 (默认警告) |
| `--hook-timeout <秒>` | int | 300 | 单个钩子超时秒数 |
| `--no-cleanup` | flag | false | 出错时保留 tmpdir 供调试 |

### 其他

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `--pretend` | flag | false | 模拟执行, 不写文件 |
| `--from-answers <file>` | path | - | 从 .ae-answers.yml 重放 |
| `--telemetry` | flag | false | 匿名使用数据 (需交互确认) |
| `--list-types` | flag | false | 列出 9 种类型后退出 |
| `--list-templates` | flag | false | 列出模板文件后退出 |

## 存量项目自动检测项

`--analyze` 或 `--incremental` 模式下, 自动检测以下字段:

| 检测项 | 来源 | 写入字段 |
|--------|------|---------|
| 语言 | pyproject.toml / go.mod / Cargo.toml / pom.xml | `language` |
| 包管理器 | lock 文件 (pnpm-lock.yaml / uv.lock / …) | `package_manager` |
| 测试框架 | 依赖 + 配置文件 | `test_runner` |
| CI 平台 | .github/workflows/ / .gitlab-ci.yml | `ci_platform` |
| Node 框架 | package.json dependencies | `frameworks` (express/next/…) |
| Python 工具 | pyproject.toml [tool.*] | `frameworks` (pytest/ruff/…) |
| Java 构建 | pom.xml / build.gradle | `language=java` + 构建工具 |
| Lefthook | lefthook.yml 存在 | `use_lefthook` |
| Docker | Dockerfile 存在 | `use_docker` |
| 隐藏目录资产 | .qoder/ .claude/ .repowiki/ (需 --include-hidden) | 同可见目录 |

---

## Init Stage Contract (agent 行为规范)

> **ae-init 是脚手架生成器，不是应用生成器。**

### Init 产出物（硬性要求）

| # | 必须项 | 验收标准 |
|---|--------|---------|
| 1 | 工程基础配置 | `.editorconfig` `.gitignore` `.github/ci.yml` 已生成 |
| 2 | 语言工具链配置 | `tsconfig.json`/`pyproject.toml`/`Cargo.toml` 等 |
| 3 | 包管理器初始化 | 含 devDependencies，`install` 成功 |
| 4 | Lint/Format 配置 | `eslint.config.js` + `prettier.config.js`（或等价物） |
| 5 | 测试框架配置 | 示例测试可运行 |
| 6 | BEACON.md 基线 | 含「目标」「范围边界」「当前状态」三节 |
| 7 | CLAUDE.md 项目文档 | 含项目名称、类型、语言、核心命令 |
| 8 | CI 配置 | GitHub Actions / GitLab CI 基础流水线 |
| 9 | 源码入口占位 | 最小可编译/可运行的入口文件 + 对应测试 |
| 10 | LICENSE + README.md | 含项目名和一句话描述 |
| 11 | .ae-answers.yml + init-manifest.json | 记录初始化参数和模板应用情况 |

### Init 红线（绝对不能做的事）

| # | 禁止项 | 原因 |
|---|--------|------|
| 1 | 安装业务依赖 | React/Vite/Express 等属于设计阶段决策 |
| 2 | 生成业务代码 | 脚手架只给入口占位，不写业务逻辑 |
| 3 | 做技术选型决策 | 不替用户选 React/Vue/Express/Django |
| 4 | 覆盖已有文件 | 已有 `design/`、`styles/`、用户文档等一律保留 |
| 5 | 修改用户配置文件 | 不修改用户已有的 .env、CI 配置、规则文件 |
| 6 | 启动开发服务器 | init 阶段只验证静态正确性，不启动 runtime |
| 7 | 填充设计文档的业务内容 | BEACON.md 填项目名/类型/日期，不填具体目标/架构 |

### Init 后强制动作

1. **验证检查清单**：所有必须文件已生成、类型检查通过、测试可运行、BEACON.md 日期正确
2. **输出完成报告**（ae-init CLI 已自动输出结构化报告）
3. **声明阶段边界**："init 阶段完成。下一步是**设计阶段**。"
4. **等待用户确认** — 用户说"继续"时，确认是"继续设计阶段"还是"继续完善 init"
