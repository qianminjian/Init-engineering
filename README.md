# ae — Init Engineering

**Claude Code Agent Skill** — 项目环境初始化工具。

5 阶段流水线（detect → prompt → render → tasks → finalize），8 种项目类型 × 4 种语言，**78 个 Jinja2 模板**。

## 分享与安装

### 方式 1：GitHub 克隆（推荐, 团队 5-20 人内部用）

```bash
git clone https://github.com/qianminjian/Init-engineering.git \
  ~/.agents/skills/init-engineering
cd ~/.agents/skills/init-engineering
uv sync
uv run ae --version
```

**安装位置**:
- Skill 入口: `~/.agents/skills/init-engineering/skills/init-engineering/SKILL.md`
- Python 包: `~/.agents/skills/init-engineering/src/init_engineering/`
- Plugin metadata: `~/.agents/skills/init-engineering/.claude-plugin/plugin.json`

### 方式 2：项目级安装（per-repo, 团队成员自动继承）

在项目 `.claude/settings.json` 中添加：

```json
{
  "extraKnownMarketplaces": {
    "qianminjian-tools": {
      "source": {
        "source": "github",
        "repo": "qianminjian/Init-engineering"
      }
    }
  }
}
```

团队成员 `git pull` 项目后自动看到 skill。

### 方式 3：开发安装（修改本项目后本地验证）

```bash
git clone https://github.com/qianminjian/Init-engineering.git
cd Init-engineering
uv sync --dev
uv run ae --help
```

## 使用

在 Claude Code 中输入 `/ae-init` 即可调用。

**新建项目**：
```
/ae-init my-app --type app-service
```

**存量项目分析**：
```
/ae-init --analyze .
```

**常用参数**：`--type app-service|library|cli-tool|skill|hook|mcp-server|spec-doc|monorepo`、`--language go|python|rust`、`--ci github|gitlab`、`--defaults`（非交互全部默认值）、`--force`（覆盖非空目录）、`--incremental`（增量补充缺失文件）。

引擎层 CLI（`ae`）仅供开发调试，正常使用走 `/ae-init`。

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

78 个模板分三层：
- `_shared/` — 所有项目共有（CLAUDE.md, README, .gitignore, LICENSE, design/）
- `_features/` — 条件包含（语言、CI、Docker、Lefthook）
- `templates/<type>/` — 项目类型特定模板

## 更新

```bash
cd ~/.agents/skills/init-engineering
git pull
uv sync  # 同步依赖（如 pyproject.toml 有变化）
```

## 开发

```bash
uv sync --dev --extra dev       # 装开发依赖
uv run pytest tests/            # 跑测试 (689 tests, 90% coverage)
uv run ruff check .             # Lint
```

## License

MIT
