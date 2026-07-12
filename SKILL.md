---
name: ae-init
description: >-
  Initialize project environment. Two modes: (1) new project wizard,
  (2) existing project auto-detection. 9 project types × 4 languages.
  Trigger: /ae-init
command: ~/.claude/skills/ae-init/.venv/bin/ae $ARGUMENTS
argument-hint: "<project> [--type <type>] [options]"
---

# ae-init

Project environment initialization for Claude Code agent workflows.

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
