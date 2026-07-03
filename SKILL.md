---
name: ae-init
description: >-
  Initialize project environment. Two modes: (1) new project wizard,
  (2) existing project auto-detection. 8 project types × 4 languages.
  Trigger: /ae-init
command: uv run --directory ~/.claude/skills/ae-init ae $ARGUMENTS
argument-hint: "<project> [--type <type>] [options]"
---

# ae-init

Project environment initialization for Claude Code agent workflows.

## Usage

```
/ae-init my-app --type app-service           # new TypeScript project
/ae-init --analyze .                         # analyze existing project
/ae-init my-lib --type library --defaults    # non-interactive, all defaults
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

## Key Options

- `--type <type>` — project type
- `--language <lang>` — typescript, python, go, rust
- `--ci <platform>` — github, gitlab
- `--defaults` — non-interactive mode
- `--force` — overwrite non-empty directory
- `--incremental` — only add missing files
