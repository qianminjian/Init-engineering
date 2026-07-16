> 创建：2026-06-24 | 更新：2026-07-16 | 阶段：v5.6 Phase F — 检测层模块路径修复 + 同级 POM 扫描

# BEACON.md — Init Engineering 设计基线

## 目标与成功标准

1. **Agent Skill 模式运行**：`ae init` 作为 Claude Code Skill 在 agent 里调用，为 agent 工作流提供项目环境初始化能力
2. **存量项目自动初始化**：通过代码分析自动识别项目类型、依赖、配置，检测结果**完整**驱动模板渲染。`--incremental` 模式基于文件系统对比（非 `.ae-answers.yml` 基线），逐文件判断"跳过已有/补充缺失"，不修改任何已有文件。首次使用的存量项目无需预先准备基线文件
3. **新项目向导初始化**：交互式询问确认项目方向、技术栈、目录结构，生成定制化项目骨架
4. **模板组合引擎**：9 类型 × 6 语言（含 plugin 多 Skill 插件模板）
5. **Pipeline 绕过阻断**：SKILL.md MUST_READ 门禁 + `_required_outputs` 自检，防止 AI 跳过 5 阶段流水线
6. **隐藏目录可扫描**：`--include-hidden` 将 .qoder/.claude/ 等隐藏目录纳入检测输入
7. **CLAUDE.md 有确定性内容**：模块列表、依赖概要、技术栈从检测数据渲染，不存在纯占位文本（Agent 深度扫描通过 `_external_data` 桥补充非确定性内容）

## 范围边界

**做：**
- Agent Skill 模式：5 阶段流水线（detect → prompt → render → tasks → finalize）
- 存量项目初始化：代码分析 → 自动识别 → `--incremental` 基于文件系统对比补充缺失
- 存量项目模板分类：基础设施模板（_shared/CI/lint）全量渲染；示例源码（_features/<lang>/src/）跳过
- 新项目向导：交互式询问 → 确认方向 → 生成骨架
- 9 类型 × 6 语言模板 + 13 exports 公共 API
- `--include-hidden`：检测阶段扫描隐藏目录（默认关闭，显式 opt-in）
- `run_update()`：增量更新已有项目（skip/overwrite/prompt 三种冲突策略）
- `ae analyze` 缺失工程文件检测：报告缺少的 .editorconfig/.gitignore/CLAUDE.md/CI/test 目录
- `--pretend` 输出完整文件清单
- **v5.4**：analyze_* 采集的全部结构化数据存入 _*_info，as_answers() 全量暴露
- **v5.6 Phase A**：Qoder 深度提取 — 4 个 repowiki 数据源全量解析
- **v5.6 Phase B**：设计文档发现 — BEACON.md/README.md/CLAUDE.md 提取
- **v5.6 Phase C**：存量项目增量初始化修复（本次）

**不做：**
- dev-loop 开发循环 / 多 LLM Provider / Web UI / 远程模板
- Agent 深度代码扫描 LLM 能力 — 非 init 核心职责（但通过 `_external_data` 桥提供注入点）
- 模板自适应生成（非填充）— 架构级变更，需独立设计

## 架构总览

### 5 阶段流水线

```
Phase 1: detect — ProjectDetector.analyze(target_dir)
  └─ list_candidates() → FRAMEWORK_SIGNATURES 9 类型匹配
  └─ analyze_java()    → _java_info:    {group_id, artifact_id, version, java_version,
                                          spring_boot_version, packaging, is_multi_module,
                                          build_tool, dependencies[], modules[]}
  └─ analyze_python()  → _python_info:  {build_backend, dependencies[]}
  └─ analyze_go()      → _go_info:      {module_path}
  └─ analyze_node()    → _node_info:    {package_name, package_version}
  └─ analyze_gradle()  → _java_info:    {build_tool="gradle"}
  └─ 输出 DetectionResult（含完整 _*_info，禁止采集后丢弃）
  └─ 模式判定（设计 §8 状态机）:
       • dst_path 不存在/空 → mode="fresh"
       • dst_path 非空 + --incremental → mode="incremental"（无需 .ae-answers.yml）
       • dst_path 非空 + --force → mode="fresh"
       • dst_path 非空 + 无 --force --incremental → TargetDirectoryError
  └─ v5.6: detect_missing_infrastructure() → missing[] 列表（.editorconfig 等缺失项）

Phase 2: prompt — InteractivePrompt + AnswersMap（6 层 ChainMap）
  └─ 优先级: cli_overrides > interactive > previous > defaults > builtins > external
  └─ detection.as_answers() → answers.defaults 层（全量通过）
  └─ as_answers() 暴露 30+ 字段：框架列表、依赖列表、模块列表、项目描述等

Phase 3: render — TemplateRenderer.render_to(tmpdir)
  └─ 遍历多层 template_dirs: _shared → _features → type → monorepo 子模板
  └─ CLAUDE.md 模板消费 frameworks/dependencies/modules/project_description
  └─ incremental 模式: 跳过示例源码模板（src/main/**），保留基础设施 + 测试模板
  └─ Jinja2 SandboxedEnvironment，双层渲染（文件名 + 内容）
  └─ --pretend 模式: 输出完整文件清单（路径列表）

Phase 4: tasks — TaskRunner.run(tasks_before, tasks_after)
Phase 5: finalize — merge_incremental (增量) / 原子 copytree (全量)
  └─ incremental: 逐文件对比 tmpdir vs dst_path → 跳过已有, 补充缺失
  └─ 写入 .ae-answers.yml + init-manifest.json（首次创建基线）
```

### 模块映射

| 模块 | 文件 | 职责 |
|------|------|------|
| InitWorker | `scaffold_phases.py` | 5 阶段编排器，状态机（fresh/incremental） |
| ProjectDetector | `detector.py` | 项目类型签名匹配（~75 行） |
| 深度分析器 | `detector_analyzers.py` | 5 个 analyze_* 函数，提取全部结构化数据存 _*_info |
| 检测常量 | `detector_constants.py` | DetectionResult + as_answers() 全量暴露逻辑 + FRAMEWORK_SIGNATURES |
| AnswersMap | `answers.py` | 6 层 ChainMap + _LazyExternalDict |
| TemplateRenderer | `renderer.py` | Jinja2 渲染引擎，路径穿越防护 |
| 渲染调度 | `scaffold_render.py` | render_to() 多模板目录遍历 |
| 配置加载 | `config_loader.py` + `config_types.py` | YAML 配置解析，!include 安全校验 |
| 错误体系 | `errors.py` | 8 种错误类 + exit_code + recovery_hint |
| CLI 入口 | `cli/commands.py` | Click 命令组 |
| Skill 入口 | `skill/` | Agent Skill 入口 |

### 检测 → 模板 完整数据流（v5.4）

```
┌──────────────────────────────────────────────────────────────────────┐
│ Phase 1: detect                                                      │
│                                                                       │
│ analyze_java(pom.xml):                                                │
│   解析: <java.version>8</java.version>                                │
│         <spring-boot.version>2.3.5</spring-boot.version>              │
│         <packaging>pom</packaging>                                    │
│         <modules><module>tmp</module><module>tmp-manage</module>...   │
│         <dependency>org.springframework.boot:spring-boot-starter...   │
│         <groupId>com.wrcb</groupId>                                   │
│         <artifactId>tmp-parent</artifactId>                           │
│         <version>1.0.0-SNAPSHOT</version>                             │
│   存储: result._java_info = {                                         │
│     group_id, artifact_id, version, java_version,                     │
│     spring_boot_version, packaging, is_multi_module,                  │
│     build_tool="maven",                                               │
│     dependencies: ["org.springframework.boot:spring-boot-starter:…",  │
│                    "module:tmp", "module:tmp-manage", ...],           │
│     modules: ["tmp", "tmp-manage", "tmp-window", ...]                 │
│   }                                                                   │
│                                                                       │
│ analyze_python(pyproject.toml):                                       │
│   存储: result._python_info = {build_backend, dependencies[]}         │
│                                                                       │
│ analyze_go(go.mod):                                                   │
│   存储: result._go_info = {module_path}                               │
│                                                                       │
│ analyze_node(package.json):                                           │
│   存储: result._node_info = {package_name, package_version}           │
│                                                                       │
│ 公共字段: result.frameworks, result.project_description, ...          │
│                                                                       │
├──────────────────────────────────────────────────────────────────────┤
│ Phase 2: prompt                                                       │
│                                                                       │
│ as_answers() 全量暴露（无白名单，无丢弃）:                             │
│   DetectionResult 公共字段:                                            │
│     project_type, language, package_manager, test_runner,             │
│     ci_platform, project_name, project_description,                   │
│     frameworks, use_lefthook, use_docker                              │
│   _java_info 展平:                                                    │
│     java_group_id, java_artifact_id, java_version_num,                │
│     detected_java_version, detected_spring_boot_version,              │
│     java_packaging, java_build_tool, is_multi_module,                 │
│     java_dependencies, java_modules                                   │
│   _python_info 展平:                                                  │
│     python_build_backend, python_dependencies                         │
│   _go_info 展平:                                                      │
│     go_module_path                                                    │
│   _node_info 展平:                                                    │
│     node_package_name, node_package_version                           │
│                                                                       │
├──────────────────────────────────────────────────────────────────────┤
│ Phase 3: render                                                       │
│                                                                       │
│ CLAUDE.md.jinja 消费:                                                 │
│   {% if frameworks %}## 框架{% for f in frameworks %}- {{ f }}{% endfor %}{% endif %}  │
│   {% if java_modules %}## 模块{% for m in java_modules %}- {{ m }}{% endfor %}{% endif %}│
│   {% if _external_data %}{{ _external_data.architecture }}{% endif %} │
│                                                                       │
│ pom.xml.jinja 消费:                                                   │
│   <java.version>{{ detected_java_version or java_version }}</...>     │
│   <parent><version>{{ detected_spring_boot_version or '3.5.5' }}...   │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

### 多层深度分析系统（v5.6 — 新增）

`ae analyze` 从表面检测升级为多层深度分析，整合三大信息源（源代码、隐藏目录、设计文档），输出结构化 AnalysisReport。解决反复出现的"分析流于表面"问题。

```
┌──────────────────────────────────────────────────────────────────────┐
│ ae analyze <path> [--include-hidden] [--deep]  [--json]              │
│                                                                       │
│ Layer 0: 基础签名检测 (always)                                         │
│   FRAMEWORK_SIGNATURES 9 类型匹配 → candidates[] → project_type       │
│                                                                       │
│ Layer 1: 源代码结构解析 (always)                                        │
│   analyze_java()    → _java_info:    {group_id, artifact_id, version, │
│     java_version, spring_boot_version, packaging, is_multi_module,    │
│     build_tool, dependencies[], modules[]}                            │
│   analyze_python()  → _python_info:  {build_backend, dependencies[]}  │
│   analyze_go()      → _go_info:      {module_path}                    │
│   analyze_node()    → _node_info:    {package_name, package_version}  │
│                                                                       │
│ Layer 2: 隐藏目录反向工程 (--include-hidden, Phase A 深度扩展)           │
│   analyze_qoder_repowiki() ──→ _qoder_info:                           │
│     _index.yaml            → modules (title, dir_name, depends_on)    │
│     技术栈与依赖.md         → tech_stack_summary (文本摘要)             │
│     核心模块详解/{mod}.md   → module_details[{key, title, overview}]   │
│     repowiki-metadata.json → knowledge_graph (关系图)                 │
│     快速开始.md             → quickstart (构建/运行步骤)               │
│                                                                       │
│ Layer 3: 设计文档发现 (--deep, Phase B)                                 │
│   analyze_design_docs() ──→ _design_info:                             │
│     design/BEACON.md       → goals, scope, decisions                  │
│     README.md              → summary                                  │
│     .claude/CLAUDE.md      → ai_instructions                          │
│                                                                       │
│ 输出:                                                                  │
│   stdout:  分层输出（身份 → 技术栈 → 模块 → 建议）                      │
│   --json:  机器可读结构化输出                                           │
│   enrich:  AnalysisReport → as_answers() → 模板上下文 (30+ → 50+)     │
└──────────────────────────────────────────────────────────────────────┘
```

### 分析 → 初始化 数据传递（v5.6 增强）

```
ae analyze ──→ AnalysisReport (结构化, 新增)
  ├── detection:     DetectionResult (30+ keys, existing)
  ├── qoder:         QoderAnalysis   (10+ keys, Phase A 新增)
  ├── design:        DesignDocAnalysis (5+ keys, Phase B 新增)
  └── recommend:     InitRecommendation (Phase C 新增)

ae init ──→ phase_prompt()
  ├── detection.as_answers()         → defaults (existing 30+)
  └── analysis_report.as_answers()   → defaults (new 15+)
      qoder_tech_stack_summary, qoder_module_details,
      qoder_module_relations, qoder_quickstart,
      design_beacon_goals, design_beacon_scope, ...
  → 模板变量: 30+ → 50+ 驱动渲染
```

## 设计决策

| # | 决策 | 理由 | 日期 | status |
|---|------|------|------|--------|
| 1 | **v5.0 精简：只保留 Init 部分** | 项目聚焦 Init 工程 | 2026-06-30 | ✅ |
| 7 | **InitWorker 拆分为 5 阶段函数** | scaffold_phases.py 501→285 行 | 2026-07-02 | ✅ |
| 8 | **detector 拆分为 constants/analyzers/helpers** | detector.py 382→82 行 | 2026-07-02 | ✅ |
| 9 | **run_update() 实现** | 类比 Copier copier update | 2026-07-02 | ✅ |
| 10 | **AnswerMap 6 层 ChainMap 简化** | 来源 Copier 8 层 | 2026-07-01 | ✅ |
| 11 | **2 类渲染生命周期钩子** | tasks_before/after | 2026-07-01 | ✅ |
| 12 | **CLI 单版本透传 templates_suffix/preserve_symlinks** | TemplateConfig 默认值可被 CLI 覆盖 | 2026-07-01 | ✅ |
| 13 | **SKILL.md MUST_READ 门禁 + _required_outputs** | pipeline 绕过阻断 | 2026-07-14 | ✅ |
| 14 | **skill.py 拆为 skill/ 子包** | 337 行 → 4 文件 | 2026-07-14 | ✅ |
| 15 | **NEGATED_FLAG_MAP 提取到 config_types.py** | --no-* 标志映射 SSOT | 2026-07-14 | ✅ |
| 16 | **analyze_* 返回 DetectionResult 不静默 mutate** | 5 个分析函数签名统一 | 2026-07-14 | ✅ |
| 17 | **`--include-hidden` 扫描隐藏目录** | .qoder/.claude/ 等纳入检测输入 | 2026-07-14 | ✅ |
| 18 | **phase_prompt() 不做白名单过滤** | detection.as_answers() 全量进入 AnswersMap | 2026-07-14 | ✅ |
| 19 | **检测值优先于模板默认值** | `{{ detected_java_version or java_version }}` 级联回退 | 2026-07-14 | ✅ |
| 20 | **多模块项目跳过根级 src/** | is_multi_module=True 时排除 src/** | 2026-07-14 | ✅ |
| 21 | **Spring Boot 版本从检测值驱动** | `{{ detected_spring_boot_version or '3.5.5' }}` | 2026-07-14 | ✅ |
| 22 | **JUnit 版本按 Java/Spring Boot 自适应** | Java 8 / SB 2.x → JUnit 4；否则 JUnit 5 | 2026-07-14 | ✅ |
| 23 | **--incremental 自动启用 --defaults** | 增量模式不弹交互 | 2026-07-14 | ✅ |
| 24 | **analyze_* 采集数据全量存储 _*_info** | dependencies/modules/build_backend/module_path 全部存入，禁止采后丢弃 | 2026-07-14 | ✅ |
| 25 | **as_answers() 全量暴露检测字段** | DetectionResult 公共字段 + _*_info 展平，30+ 变量进入模板上下文 | 2026-07-14 | ✅ |
| 26 | **CLAUDE.md 模板消费检测数据** | frameworks/modules/dependencies/project_description 渲染确定性内容 | 2026-07-14 | ✅ |
| 27 | **_external_data 模板消费桥** | CLAUDE.md 增加 `{% if _external_data %}` 条件渲染段，Agent 注入点可工作 | 2026-07-14 | ✅ |
| 28 | **pom.xml 模板消费 project_version** | `{{ java_version_num or '0.1.0' }}` 替代硬编码 `0.1.0` | 2026-07-14 | ✅ |
| 29 | **P1-12 回退 + 规范检测器职责** | 检测器报告所有候选，不静默消歧义；消歧义由上层（CLI --type / 交互）完成 | 2026-07-14 | ✅ |
| 30 | **v5.5 CLI 命令重组** | analyze/list-types/list-templates 提升为独立命令；移除 5 个无用选项（templates_suffix/preserve_symlinks/hook_timeout/force_unsafe_template/telemetry）；init 选项分层（核心/配置/流程/高级）；每个命令有使用示例 epilog | 2026-07-15 | ✅ |
| 31 | **修复 pom.xml 命名空间解析** | `analyze_java()` 中 `tag(element)` → `tag(element.tag)`，7 处调用传了 Element 对象而非 tag 字符串，导致所有带 xmlns 的 pom.xml 解析失败 | 2026-07-15 | ✅ |
| 32 | **Jinja2 `or` → `\| default()`** | Jinja2 的 `or` 对 undefined 变量仍抛 UndefinedError；`\| default()` 才安全处理变量缺失。修复 8 处模板（pom.xml ×4 + CI ×2 + is_java8 ×2）| 2026-07-15 | ✅ |
| 33 | **app-service/library ae-template.yml 补充 java_version** | `_features/java/pom.xml.jinja` 引用 `java_version` 但仅 monorepo 定义；新增到 app-service/library 配置 | 2026-07-15 | ✅ |
| 34 | **--from-answers 恢复时语言丢失** | `cmd_init` 从 answers 提取 `project_type` 但不提取 `language`；`phase_prompt` 的 nested 模板选择未查 `previous_answers`，导致空目录 `--from-answers` 回退到第一个嵌套模板（typescript），输出混合 Java+TypeScript | 2026-07-15 | ✅ |
| 35 | **CLAUDE.md Tech Stack 格式断裂** | `{%- if %}` 的 `-` 静默吞掉换行符（条件为 False 时仍生效），导致 `## Tech Stack- Language: java- CI: github`。改为 `{% if %}...\n{% endif %}{% if %}` 流式模板避免空白吞食 | 2026-07-15 | ✅ |
| 36 | **v5.6 多层深度分析** | ae analyze 从单层检测升级为 3 层分析：L1 源代码结构解析 + L2 隐藏目录反向工程（4 个 qoder 数据源：_index.yaml/技术栈与依赖.md/模块详解/知识图谱） + L3 设计文档发现（BEACON.md/README.md/CLAUDE.md）。AnalysisReport 结构化输出，分析结果写入 as_answers() 补充 15+ 模板变量。解决"分析流于表面"的系统性缺陷 | 2026-07-15 | ✅ |
| 37 | **detector_qoder.py 拆为多函数** | 单一 analyze_qoder_repowiki() → 拆为 _extract_qoder_index/tech_stack/module_details/metadata/quickstart 五个子函数 + _build_module_relations，各解析一个数据源 | 2026-07-15 | ✅ |
| 38 | **ae analyze 输出重构** | stdout 从 8 行平铺摘要 → 5 段分层输出（项目身份/技术栈/模块结构/初始化建议/反向工程发现），每段从多个数据源聚合而非单一函数输出 | 2026-07-15 | ✅ |
| 39 | **移除 --incremental 的 .ae-answers.yml 前提条件** | merge_incremental() 基于文件系统对比（tmpdir vs dst_path），逐文件判断存在性。基线文件是 init 的产出物，不是前提条件。首次存量项目直接可用 --incremental | 2026-07-15 | ✅ |
| 40 | **存量项目模板分类：基础设施 vs 示例源码** | incremental 模式：_shared/ + CI/lint 基础设施模板全量渲染；_features/<lang>/src/main/** 示例源码跳过。测试模板（src/test/**）保留——存量项目可能缺测试目录 | 2026-07-15 | ✅ |
| 41 | **ae analyze 增加缺失工程文件检测** | 检测并报告：.editorconfig / .gitignore / CLAUDE.md / README.md / LICENSE / .github/workflows/ / .gitlab-ci.yml / .pre-commit-config.yaml / lefthook.yml / src/test/ 目录。输出补全建议清单 | 2026-07-15 | ✅ |
| 42 | **非 TTY + --incremental 不再自动覆盖为 --defaults** | --incremental 显式传入时保持用户意图，不自动追加 --defaults。增量模式自身已隐含非交互（不弹问答），无需借道 --defaults | 2026-07-15 | ✅ |
| 43 | **--pretend 输出完整文件清单** | render 阶段完成后，列出所有将要生成的文件路径。存量项目用户可据此评估影响，决定是否执行 | 2026-07-15 | ✅ |
| 44 | **增量模式排除范围精确化** | 存量 monorepo 项目跳过 `packages/**/src/main/**`（示例源码），保留 src/test/**（测试模板）+ pom.xml（配置模板）| 2026-07-15 | ✅ (v5.6 Phase D: 范围精确化) |
| 45 | **analyze 输出增加初始化模式推荐** | 根据项目状态推荐正确命令：空目录→--defaults，存量项目→--incremental，有 .ae-answers.yml→--incremental（基线对比）。不再并列推荐不适用选项 | 2026-07-15 | ✅ |
| 46 | **Incremental 不弹交互** | --incremental 自己设置 non_interactive 内部标志，不依赖 --defaults。检测结果从 Phase 1 流入 AnswersMap.defaults，无需用户输入 | 2026-07-15 | ✅ |
| 47 | **测试目录统一：所有语言使用根级 tests/** | 所有类型（TypeScript/Python/Go/Rust/Java/Bash）测试文件从源码同目录移到根级 tests/，独立于源码目录。解决测试文件散落在 src/ 各处的结构不一致问题 | 2026-07-16 | ✅ |
| 48 | **Monorepo Java tests/ 作为独立 Maven 模块** | tests/ 有自己的 pom.xml（parent 引用根 POM，`<testSourceDirectory>.</testSourceDirectory>`），解决多模块项目中测试编译/运行隔离问题。默认加入 java_modules 列表 | 2026-07-16 | ✅ |
| 49 | **Maven testSourceDirectory 统一** | app-service 和 library 的 pom.xml.jinja 添加 `<testSourceDirectory>tests</testSourceDirectory>`，与物理 tests/ 目录保持一致 | 2026-07-16 | ✅ |
| 50 | **Maven wrapper jar 内嵌模板** | `.mvn/wrapper/maven-wrapper.jar`（63KB, v3.3.2）纳入 _features/java 模板，确保 mvnw 开箱即用。.gitignore 添加 `!.mvn/wrapper/maven-wrapper.jar` 白名单 | 2026-07-16 | ✅ |
| 51 | **模块磁盘校验** | `analyze_java()` 对比 pom.xml `<modules>` 与实际磁盘目录，检测缺失模块和磁盘存在但未声明的模块，在 `ae analyze` 输出中警告 | 2026-07-16 | ✅ |
| 52 | **Phase 4 任务分层：模板 + 任务双轨** | 模板覆盖根级别骨架（如 tests/ Maven 模块），Phase 4 `_tasks` 负责模块级动态补充（如 Java per-module test generation）。解决模板 1:1 静态映射无法覆盖动态模块列表的问题 | 2026-07-16 | ✅ |
| 53 | **Go/Rust 测试惯例对齐** | Go monorepo 使用 `package main_test` 黑盒测试惯例；Rust monorepo 使用 `tests/` 目录（cargo test 自动发现集成测试） | 2026-07-16 | ✅ |
| 54 | **模块路径拼接 aggregator_path 前缀** | `analyze_java()` 接收 `project_root` 参数，计算 POM 相对路径。`tmp/pom.xml` 的 `<module>tmp-boot</module>` → 模块路径为 `tmp/tmp-boot`，而非扁平化为 `tmp-boot` | 2026-07-16 | ✅ |
| 55 | **同级 POM 扫描（sibling detection）** | 扫描项目根目录中所有 pom.xml，检测 `<parent><artifactId>` 引用聚合 POM 但不在 `<modules>` 中的独立模块（如 `tmp-manage`/`tmp-window`）。追加到 `java_modules` 列表 | 2026-07-16 | ✅ |
| 56 | **磁盘校验在路径拼接前执行** | `missing_modules` 校验使用原始模块名（相对 pom_path.parent），而非拼接 aggregator_path 后的路径。避免 `tmp/tmp-boot` vs 磁盘目录 `tmp-boot` 的假阳性警告 | 2026-07-16 | ✅ |
| 57 | **增量模式结构防护** | `aggregator_path` 非空时（聚合 POM 不在根目录），增量渲染排除根级 `/pom.xml` 和 `packages/` 模板，避免与已有项目结构冲突 | 2026-07-16 | ✅ |

## Init → Loop 契约（Manifest）

Init 完成初始化时写入 `.ae-state/init-manifest.json`（schema 1.1），Loop 启动时读取。

**必需字段**：`schema_version`, `project_type`（9 枚举）, `language`（6 枚举）, `conventions`（linter/type_checker/test_runner）, `structure`（source_root/test_root）

**v5.6 新增**：`conventions.ci_platform`（github/gitlab/none）, `structure.design_root`

**契约 SSOT**：`init-manifest.schema.json`（JSON Schema draft 2020-12），Loop 仓库持有权威副本，Init 侧复制 + pin 版本。Init 生成 manifest 后依 schema 自校验通过才写盘。

## 当前状态

**阶段：** v5.6 Phase F — 检测层模块路径修复 + 同级 POM 扫描

**最近动作：** 2026-07-16 — Phase D+E+F 实施完成。
- Phase D（模板工程化修复）：测试目录统一（6 语言 → 根级 tests/）、Monorepo Java tests/ 独立 Maven 模块、Maven testSourceDirectory 统一、Maven wrapper jar 内嵌、模块磁盘校验、增量排除范围精确化（packages/** → packages/**/src/main/**）、Go/Rust 测试惯例对齐
- Phase E（Phase 4 任务分层）：monorepo/ae-template.yml 新增 `_tasks`，Phase 4 bash 任务对 Java 多模块项目动态生成 per-module 测试骨架（`{module}/src/test/java/{pkg}/ModuleTest.java`），幂等（已有则跳过），跳过 tests 根模块
- Phase F（检测层修复 — TMP-for-init 故障报告根因）：3 项修复
  1. 模块路径前缀：`analyze_java()` 计算 aggregator_path，`tmp/pom.xml` 的模块路径从 `tmp-boot` → `tmp/tmp-boot`
  2. 同级 POM 扫描：`detector.py` 扫项目根目录 pom.xml，通过 `<parent>` 引用识别独立模块（tmp-manage/tmp-window）
  3. 增量结构防护：`aggregator_path` 非空时排除根级 pom.xml + packages/ 模板
  4. 磁盘校验顺序修复：校验在路径拼接前执行，使用原始模块名避免假阳性

**下一步：** 无阻塞项。可推进 Phase F（monorepo 非 Java 语言 per-module 测试生成）或 bug 修复

**阻塞项：** 无

## 设计演进日志

| 日期 | 变更 | 原因 |
|------|------|------|
| 2026-07-16 | Phase D+E+F 模板工程化 + Phase 4 分层 + 检测层修复 | Phase D（7 项模板修复）：测试目录统一、Monorepo Java tests/ Maven 模块、testSourceDirectory、wrapper jar、模块校验、排除精确化、Go/Rust 惯例。Phase E（任务分层）：monorepo _tasks per-module 测试生成。Phase F（检测层根因修复）：模块路径前缀、同级 POM 扫描、增量结构防护、磁盘校验顺序修复。TMP-for-init 故障报告 6 问题全部解决 |
| 2026-07-15 | Phase C 存量项目增量初始化修复 | 根因：Phase 1 实现添加了设计未规定的 .ae-answers.yml 前提条件。修复：8 项改动 — detect 移除前提、brownfield 模板分类、analyze 缺失检测、pretend 文件清单、CLI 非 TTY 行为修正、SKILL.md 决策树 |
| 2026-07-15 | Phase A 实现完成 | detector_qoder.py 拆为 6 子函数、_qoder_info 5 新字段、as_answers() 6 新变量、ae analyze 5 段分层输出、655 tests pass |
| 2026-07-15 | v5.6 多层深度分析设计 | ae analyze 从单层检测升级为 3 层分析（源代码/隐藏目录/设计文档），AnalysisReport 结构化输出，15+ 新模板变量 |
| 2026-07-15 | E2E 测试 + 2 追加 Bug 修复 | --from-answers 语言丢失（混合模板）+ CLAUDE.md 格式断裂（Jinja2 空白吞食）
| 2026-07-15 | v5.5 CLI 重组 + 帮助系统 | 6 命令 + 选项分层 + 移除 5 无用选项 + 使用示例 epilog + 向后兼容 |
| 2026-07-15 | v5.4 完整性修复实现 | 4 阶段实现完成：analyze_* 全量存储 + as_answers() 30+ 字段曝光 + 模板消费 + 655 tests pass |
| 2026-07-14 | v5.4 幻肢审计 + 完整性设计 | _external_data 有路无车、analyze_* 采集后丢弃、as_answers 暴露不足、模板不消费检测数据 |
| 2026-07-14 | 设计文档合并为单一 BEACON.md + TASKS.md | 8 个设计文档分散 |
| 2026-07-14 | v5.3 信息流修复 | detect→prompt→render 信息链路断裂 |

## 待解决问题

| 状态 | 问题 | 说明 |
|------|------|------|
| [✓] | 代码分析深度 | 依赖解析 + 框架识别 + PM/测试/CI 自动推断 |
| [✓] | monorepo 多语言 | typescript/python/go/rust/java |
| [✓] | run_update 命令 | skip/overwrite/prompt 三种冲突策略 |
| [✓] | pipeline 绕过阻断 | SKILL.md MUST_READ + _required_outputs |
| [✓] | v5.3 信息流修复 | detect→prompt→render 全链路打通 |
| [✓] | v5.4 检测信息完整性 | 30+ 字段全量暴露 + 模板消费检测数据 + _external_data 桥 |
| [✓] | v5.6 Phase C 存量项目增量初始化 | .ae-answers.yml 前提条件移除 + brownfield 模板分类 + analyze 缺失检测 |
| [✓] | v5.6 Phase D 模板工程化修复 | 测试目录统一 + tests/ Maven 模块 + testSourceDirectory + wrapper jar + 模块校验 + 排除精确化 |
| [✓] | v5.6 Phase E Phase 4 任务分层 | Java per-module test generation via _tasks |
| [~] | answers.py 323 行 | 职责仍单一，暂不拆分 |
| [Q?] | monorepo 非 Java 语言 per-module 测试生成 | TypeScript/Python/Go/Rust monorepo 是否需要按模块动态生成测试？当前仅有根级 tests/ 骨架 |

## 引用文件

@design/TASKS.md · @design/his_bak/ · @SKILL.md · @src/init_engineering/
