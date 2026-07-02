# Template Variables Reference

All variables available in `.jinja` templates during rendering.

## Built-in Variables

Always available, injected by the engine:

| Variable | Type | Description |
|----------|------|-------------|
| `_ae_version` | str | Template engine version (e.g., `"1.0.0"`) |
| `_folder_name` | str | Target directory name |
| `current_year` | str | Current year (e.g., `"2026"`) |
| `_ae_python` | str | Path to Python executable |
| `sep` | str | OS path separator (`/` or `\`) |
| `os` | str | `"macos"`, `"linux"`, or `"windows"` |

## Project Configuration

From `ae-template.yml` questions and CLI overrides:

### Common (all project types)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `project_name` | str | folder name | Project name |
| `project_description` | str | `""` | One-line description |
| `language` | str | `"typescript"` | `typescript` / `python` / `go` / `rust` |
| `package_manager` | str | varies | `npm` / `pnpm` / `yarn` / `bun` / `uv` / `poetry` |
| `test_runner` | str | varies | `vitest` / `jest` / `pytest` / `go test` / `cargo test` |
| `ci_platform` | str | `"github"` | `github` / `gitlab` / `none` |
| `use_typescript` | bool | `true` | Enable TypeScript |
| `use_lefthook` | bool | `false` | Enable lefthook git hooks |
| `use_docker` | bool | `false` | Enable Docker support |

### app-service / library / cli-tool specific

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `project_name` | str | folder name | Project/directory name |
| `project_description` | str | `""` | One-line description |

### skill specific

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `skill_name` | str | `"my-skill"` | Skill name (kebab-case) |
| `skill_description` | str | `""` | Skill description for AI trigger |
| `author_name` | str | `""` | Author name |

### hook specific

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `hook_name` | str | `"my-hook"` | Hook name |
| `hook_description` | str | `""` | Hook description |
| `hook_type` | str | `"PreToolUse"` | `PreToolUse` / `PostToolUse` |

### mcp-server specific

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `server_name` | str | `"my-mcp-server"` | MCP server name |
| `server_description` | str | `""` | Server description |
| `transport` | str | `"stdio"` | `stdio` / `sse` / `streamable-http` |

### spec-doc specific

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `doc_name` | str | `"my-spec"` | Document project name |
| `doc_description` | str | `""` | Document description |
| `author_name` | str | `""` | Author name |
| `doc_status` | str | `"探索"` | Status: 探索/定义/设计/实现/验证/完成 |
| `version` | str | `"0.1.0"` | Document version |

## External Data

Available via `_external_data.<key>` (lazy-loaded from YAML/JSON files specified in `_external_data`):

```jinja
{{ _external_data.api_spec.endpoints }}
```

## Feature Availability Conditions

Features are conditionally included based on answers:

| Feature | Condition | Templates Included |
|---------|-----------|-------------------|
| TypeScript | `language == "typescript"` | tsconfig, eslint, prettier, package.json |
| Python | `language == "python"` | pyproject.toml, ruff.toml, __init__.py |
| Go | `language == "go"` | go.mod, main.go, main_test.go |
| Rust | `language == "rust"` | Cargo.toml, main.rs, lib.rs |
| GitHub Actions | `ci_platform == "github"` | .github/workflows/ci.yml |
| GitLab CI | `ci_platform == "gitlab"` | .gitlab-ci.yml |
| Docker | `use_docker == true` | Dockerfile, .dockerignore |
| Lefthook | `use_lefthook == true` | lefthook.yml |

## Template Path Conventions

Template file paths mirror the generated project structure:

```
templates/_shared/CLAUDE.md.jinja       →  {project}/CLAUDE.md
templates/_shared/.gitignore.jinja      →  {project}/.gitignore
templates/_features/typescript/tsconfig.json.jinja → {project}/tsconfig.json
templates/_features/github-actions/.github/workflows/ci.yml.jinja → {project}/.github/workflows/ci.yml
```

- Files ending in `.jinja` are rendered (both path and content)
- Files without `.jinja` suffix are copied verbatim
- Rendered path becomes empty string → file is skipped
- `.jinja` suffix is stripped from the output filename
