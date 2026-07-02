# Changelog

All notable changes to Init-Engineering (ae) will be documented in this file.

## [1.0.0] — 2026-07-02

### Added
- **`ae update` 命令**: 类比 Copier `copier update`,支持 skip/overwrite/prompt 三种冲突策略 + dry_run 模式
- **monorepo 多语言支持**: typescript/python/go/rust 4 个 nested template 变体,每种带 packages/shared/ 子包模板
- **条件化 features**: `use_docker` / `use_lefthook` / `ci_platform` 控制可选模板(github-actions/gitlab-ci/docker/lefthook)
- **5 类渲染生命周期钩子**: before_renderer / on_exists / after_renderer / tasks_before / tasks_after
- **ConfigLoaderSecurityError**: `!include` 路径沙箱越界时抛 exit_code=8
- **TemplatesConfig.sandbox_roots**: external_data 路径 realpath 双侧校验,防越权读取
- **CLI 单版本透传**: `--templates-suffix` / `--preserve-symlinks` / `--use-typescript` / `--use-lefthook` 可覆盖 TemplateConfig 默认值
- **AnswerMap 6 层 ChainMap**: cli_overrides > interactive > previous > defaults > builtins > external(从 Copier 8 层简化)
- **ConfigLoader !include**: 模板配置可拆分子文件
- **29 个类型×语言组合 E2E 测试**: 覆盖 8 类型 × 多语言变体
- **9 矩阵冲突策略测试**: 3 策略 × 3 文件状态全覆盖
- **6 个异常路径测试**: SIGINT / read-only / 权限拒绝 / git config 污染等

### Changed
- **版本统一**: `__version__` / `_ae_version` / 8 个 ae-template.yml 的 `_min_ae_version` 全部统一到 `1.0.0`
- **InitWorker 拆分**: 501 行的 InitWorker 拆为 5 阶段函数(scaffold_phase_funcs.py) + InitWorker 仅保留编排
- **detector 拆分**: 382 行 detector.py 拆为 constants/analyzers/helpers,解循环依赖
- **移除 anthropic SDK 依赖**: v5.0 裁剪后不再需要 LLM 调用
- **Windows 行为**: InitLock 检测到 fcntl 不可用时抛 TargetDirectoryError(不再假装成功)
- **project_type 校验**: 白名单校验从 phase_finalize 前移到 phase_detect 入口
- **ruff target-version**: `py312` → `py311` 与 `requires-python` 一致
- **bash feature 模板**: 补 hello.sh.jinja + test_hello.sh.jinja(原本是空壳)
- **PyPI classifiers**: 补 Operating System (Linux/MacOS/Windows :: Unsupported) + Programming Language :: Python :: Implementation :: CPython
- **Hatchling wheel include**: 显式声明 SKILL.md / CHANGELOG.md / LICENSE 打包

### Security
- **9 类 init 错误体系**: ConfigFileError / UnsatisfiedPrerequisiteError / TargetDirectoryError / ValidationError / TaskExecutionError / TemplateRenderError / InitInterruptedError / ConfigLoaderSecurityError / HookExecutionError,各带独立 exit_code
- **Jinja2 SandboxedEnvironment**: 主渲染路径阻 RCE
- **!include realpath 校验**: 防止路径穿越读敏感文件
- **InitLock fcntl**: 同一 dst_path 多进程并发互斥
- **CLI --use-typescript/--no-typescript 对称**: 之前只有 --no-typescript 无法启用

### Fixed
- 修复 ae init --defaults --type app-service --language X 在 monorepo 选错 nested template 的 bug
- 修复 prompt_for_nested_template 加 preferred 参数支持 CLI --language 透传
- 修复 scaffold_render.py 嵌套模板路径错误(已改为相对路径)
- 修复 renderer.is_binary 用 binaryornot 0.6.0 在 Python 3.13 上的 UnicodeDecodeError(替换为本地实现)
- 修复 InitLock 在 Windows 假装成功(改为显式拒绝)

## [0.3.0] — 2026-07-01

### Added
- **External template directory** (`--template-dir`): load templates from external directory with priority override
- **Concurrent initialization lock**: `fcntl.flock` on `.ae-init.lock` prevents dual `ae init` on same directory
- **Monorepo sub-package templates**: `packages/shared/` with package.json, tsconfig.json, src/index.ts
- **pre-commit config template**: `.pre-commit-config.yaml.jinja` with language-conditional hooks (biome/ruff/golangci/rust)
- **Go linter config**: `.golangci.yml.jinja` with errcheck, gosimple, staticcheck, goimports
- **Rust formatter config**: `rustfmt.toml.jinja` with 100-char width, crate-level imports
- **CI matrix strategy**: Node 18/20/22, Python 3.12/3.13, Go 1.22/1.23, Rust stable/beta
- **Verbose logging** (`--verbose` / `-v`): DEBUG-level output with phase transitions and template dir info
- **Opt-in telemetry** (`--telemetry`): anonymous usage data collection (AE_TELEMETRY env var)
- **Docker deployment templates**: `docker-compose.yml.jinja` + `k8s-deployment.yml.jinja`
- **ae Dockerfile**: containerized ae for CI/CD environments
- **Python 3.11 compatibility**: `tomli` fallback for `tomllib`, lowered `requires-python` to `>=3.11`

### Fixed
- **Concurrent lock timing**: lock created after non-empty check to avoid false "directory not empty" errors
- **pretend mode**: no longer creates dst_path directory or lock file
- **pyproject.toml Hatchling**: `[project.urls]` placed after `dependencies` to avoid TOML parsing error
- **Windows compatibility**: `os.readlink`, `symlink_to`, `copymode` all wrapped with OSError protection

### Changed
- Template count: 76 → **85** (+4 monorepo, +1 go, +1 rust, +2 docker, +1 shared)
- Coverage boosted: `detector.py` 76% → 94%
- Test count: 476 → 492

## [0.2.0] — 2026-07-01

### Added
- **Strict mode** (`--strict`): hook failures raise exceptions instead of warnings
- **Deep project analysis** (`ae init --analyze`): dependency parsing, framework recognition (28 frameworks), package manager detection (7 lock file types), CI platform detection
- **Hook strict mode**: `HookRunner(strict=True)` raises `HookExecutionError` on failure
- **10 new hook/spec-doc templates**: Python hook, Node.js hook, spec-doc ADR template, BEACON 7-section format, README, .gitignore
- **Language support for hook/skill/spec-doc types**: `language` choice field in ae-template.yml
- **ProjectDetector.analyze()**: returns `DetectionResult` with language, package_manager, test_runner, frameworks, ci_platform
- **Concurrent safety**: file lock test validates lock mechanism

### Fixed
- **lefthook conditional rendering**: lefthook.yml no longer generated when `use_lefthook=false`
- **CI template path**: GitHub Actions workflow now correctly renders to `.github/workflows/ci.yml`
- **Go framework detection**: regex handles nested module paths (e.g., `github.com/go-chi/chi/v5`)
- **Python dependency parsing**: handles PEP 621 list-format dependencies correctly
- **bash feature**: removed misplaced `hook.sh.jinja` from `_features/bash/`

### Changed
- `build_template_dirs`: lefthook feature now gated by `context.get("use_lefthook")`
- `run_builtin_hooks`: accepts `strict` parameter for error propagation
- CLI: added `--strict` flag, `--template-dir` option
- BEACON.md: updated to reflect v0.2.0 state

## [0.1.0] — 2026-06-30

### Added
- Initial release
- 5-phase pipeline: detect → prompt → render → tasks → finalize
- 8 project types: app-service, library, cli-tool, skill, hook, mcp-server, spec-doc, monorepo
- 4 languages: TypeScript, Python, Go, Rust
- 43 template files with `_shared` + `_features` + type-specific architecture
- Path traversal protection (macOS symlink aware)
- Hook error propagation with file/line tracking
- Agent Skill mode: `ae init` as Claude Code Skill
- Interactive wizard for new projects
- `--defaults` non-interactive mode
- `--incremental` partial update mode
- `--force` overwrite mode
- `--pretend` dry-run mode
- AnswersMap 6-layer priority resolution
- Jinja2 SandboxedEnvironment rendering
- TaskRunner with pre/post hooks
- 9 error types with distinct exit codes
