# ae — Init Engineering

**Claude Code Agent Skill** — 项目环境初始化工具。

5 阶段流水线（detect → prompt → render → tasks → finalize），8 种项目类型 × 4 种语言，76 个 Jinja2 模板。

## 快速开始

```bash
# 安装
pip install auto-engineering
# 或开发安装
git clone <repo-url> && cd Init-engineering && uv sync

# 新建 TypeScript 应用
ae init my-app --type app-service --defaults

# 存量项目分析
ae init --analyze .

# 查看所有选项
ae init --help
```

## 项目类型

| 类型 | 用途 | 典型产物 |
|------|------|---------|
| `app-service` | Web 应用/API 服务 | CLAUDE.md, design/, CI, linter |
| `library` | npm/pypi/cargo/go 库 | 库入口文件, 测试, CI |
| `cli-tool` | 命令行工具 | CLI 入口, 参数解析 |
| `skill` | Claude Code Skill | SKILL.md, run.sh/py |
| `hook` | Claude Code Hook | hook.sh/py/js, CLAUDE.md |
| `mcp-server` | MCP Server | stdio transport, index.ts/cli.py |
| `spec-doc` | 技术规格文档 | BEACON.md, spec.md, ADR |
| `monorepo` | 多包仓库 | pnpm-workspace, turbo.json |

## 语言支持

| 语言 | 包管理器 | 测试框架 | CI |
|------|---------|---------|-----|
| TypeScript | npm/pnpm/yarn/bun | vitest/jest | GitHub/GitLab |
| Python | uv/poetry | pytest | GitHub/GitLab |
| Go | go mod | go test | GitHub/GitLab |
| Rust | cargo | cargo test | GitHub/GitLab |

## 常用选项

```bash
ae init <project> --type <type>     # 指定项目类型
ae init --analyze <path>            # 存量项目代码分析
ae init <project> --defaults        # 非交互，全部使用默认值
ae init <project> --force           # 覆盖非空目录
ae init <project> --incremental     # 增量补充缺失文件
ae init <project> --pretend         # 模拟执行，不写文件
ae init <project> --language go     # 指定语言
ae init <project> --ci github       # 指定 CI 平台
ae init <project> --strict          # 严格模式：钩子失败即中断
```

## 模板变量

所有可用变量见 [TEMPLATE-VARS.md](docs/TEMPLATE-VARS.md)。

## 架构

```
detect → prompt → render → tasks → finalize
  │         │         │        │         │
  │    交互式问答  模板渲染  钩子执行   文件写入
  │    (2-pass)  (双层Jinja2) (pre/post) (.ae-answers.yml)
  │
  代码分析 + 签名匹配 + 框架识别
```

76 个模板分三层：
- `_shared/` — 所有项目共有（CLAUDE.md, README, .gitignore, LICENSE, design/）
- `_features/` — 条件包含（语言、CI、Docker、Lefthook）
- `templates/<type>/` — 项目类型特定模板

## 开发

```bash
uv sync                    # 安装依赖
uv run pytest tests/       # 运行测试 (492 tests)
uv run ae --help           # CLI 帮助
```

## License

MIT
