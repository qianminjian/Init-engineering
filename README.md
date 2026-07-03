# ae — Init Engineering

**Claude Code Agent Skill** — 项目环境初始化工具。

5 阶段流水线（detect → prompt → render → tasks → finalize），8 种项目类型 × 4 种语言，**78 个 Jinja2 模板**。

## 分享与安装

### 方式 1：GitHub 克隆（推荐, 团队 5-20 人内部用）

```bash
# 1. 克隆到 Claude Code / agent skills 标准目录
git clone https://github.com/qianminjian/Init-engineering.git \
  ~/.agents/skills/init-engineering

# 2. 一键安装依赖
cd ~/.agents/skills/init-engineering
./scripts/setup.sh

# 3. 验证
ae --version
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

## 快速开始

```bash
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

78 个模板分三层：
- `_shared/` — 所有项目共有（CLAUDE.md, README, .gitignore, LICENSE, design/）
- `_features/` — 条件包含（语言、CI、Docker、Lefthook）
- `templates/<type>/` — 项目类型特定模板

## 更新

```bash
cd ~/.agents/skills/init-engineering
git pull
./scripts/setup.sh  # 同步依赖（如 pyproject.toml 有变化）
```

## 开发

```bash
uv sync --dev                # 装开发依赖
uv run pytest tests/         # 跑测试 (629 tests, 80%+ coverage gate)
uv run ruff check init_engineering/  # Lint
uv run ae --help             # CLI 帮助
```

## License

MIT
