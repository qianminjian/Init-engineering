# TASKS.md — 任务跟踪表

> 创建：2026-07-14 | 更新：2026-07-15（E2E 测试 + 3 Bug 修复完成）

# TASKS.md — 任务跟踪表

> 用途：本项目唯一的任务跟踪文件。所有待办、进行中、已完成、已延后的任务在此记录。

---

## §v5.3 信息流修复 ✅（2026-07-14 完成）

**背景**：ae-init 存量项目严重缺陷报告（10 项缺陷）。根因：`phase_prompt()` L95-98 白名单过滤导致 detect 阶段提取的 java_version、spring_boot_version、is_multi_module 等信息被丢弃。

**设计**：BEACON.md 决策 18-20 + 架构总览"信息流"节。

### 任务清单

| # | 任务 | 文件 | 描述 | 状态 |
|---|------|------|------|------|
| v5.3-1 | 移除白名单过滤 | `phases/prompt.py:91-98` | detection.as_answers() 全量写入 answers.defaults | ✅ |
| v5.3-2 | 扩展 as_answers() | `detector_constants.py` | 增加 java_packaging / is_multi_module / java_group_id / java_artifact_id | ✅ |
| v5.3-3 | project_name 覆盖 | `detector.py` | Java 项目优先用 artifact_id 作为 project_name | ✅ |
| v5.3-4 | 模板变量回退 | `templates/monorepo/java/pom.xml.jinja` | `{{ detected_java_version or java_version }}` | ✅ |
| v5.3-5 | 模板变量回退 | `templates/_features/java/pom.xml.jinja` | `{{ detected_java_version or java_version }}` | ✅ |
| v5.3-6 | 模板变量回退 | `templates/_shared/CLAUDE.md.jinja` + `app-service/CLAUDE.md.jinja` | Java 用 `mvn test/install` 替代裸 `junit` | ✅ |
| v5.3-7 | 多模块 src/ 跳过 | `scaffold_render.py:render_to()` | is_multi_module 时排除 src/** | ✅ |
| v5.3-8 | 回退 P1-12 | `detector.py:list_candidates()` | 移除 spec-doc 消歧义，恢复"报告所有候选" | ✅ |
| v5.3-9 | 测试更新 | `tests/test_cli_commands.py` | 确认 P1-12 回退后测试仍通过 | ✅ |
| v5.3-10 | 全量测试验证 | `tests/` | 650 passed, 0 failed | ✅ |

### 变更摘要

| 文件 | 变更 |
|------|------|
| `phases/prompt.py:91-96` | 移除 6 字段白名单 → detection.as_answers() 全量进入 defaults |
| `detector_constants.py:51-66` | as_answers() 新增 java_packaging / is_multi_module / java_group_id / java_artifact_id |
| `detector.py:74-83` | 回退 P1-12 spec-doc 消歧义 |
| `detector.py:106-108` | Java 项目用 artifact_id 覆盖 project_name |
| `scaffold_render.py:183-184` | is_multi_module → exclude.append("src/**") |
| `templates/monorepo/java/pom.xml.jinja:28` | `{{ detected_java_version or java_version }}` |
| `templates/_features/java/pom.xml.jinja:27` | `{{ detected_java_version or java_version }}` |
| `templates/_shared/CLAUDE.md.jinja` | Java 专用命令块（mvn test/install/checkstyle/spotless） |
| `templates/app-service/CLAUDE.md.jinja` | Java 专用命令块 |

---

## §v5.3-bugreport 故障报告补充修复 ✅（2026-07-14 完成）

| # | 任务 | 文件 | 描述 | 状态 |
|---|------|------|------|------|
| P1-6 | --incremental 自动启用 defaults | `cli/commands.py:146-151` | incremental=True 也触发 defaults，增量模式不弹交互 | ✅ |
| P2-8 | .gitignore 补充 | `templates/_shared/.gitignore.jinja` | 新增 logs/、_scratch/、.ae-state/ | ✅ |
| P2-9 | _scratch/ 模板 | `templates/_shared/_scratch/` | 创建 reports/buginfo/coverage/test-output 四个子目录模板 | ✅ |
| P2-10 | CI 模板 Java 分支 | `_features/github-actions/` + `_features/gitlab-ci/` | Java Maven CI 用 `detected_java_version or java_version` | ✅ |
| P0-2 | Spring Boot 版本 | `_features/java/pom.xml.jinja` | 父 POM 版本用 `detected_spring_boot_version or '3.5.5'` | ✅ |
| P0-4 | JUnit 版本 | `_features/java/pom.xml.jinja` + `monorepo/java/pom.xml.jinja` | Java 8 / Spring Boot 2.x 自动选 JUnit 4.13.2，否则 JUnit 5 | ✅ |

---

## §v5.4 检测信息完整性修复 ✅（2026-07-15 实现完成）

**背景**：幻肢审计发现 5 类缺口 — _external_data 有路无车、analyze_* 采集后丢弃 dependencies/modules/build_backend/module_path、as_answers() 暴露不足、analyze_python/go/node 无 _*_info 存储、模板不消费已有检测字段。

**设计**：BEACON.md 决策 24-28。

### Phase A — 分析器数据保存（detector_analyzers.py）

| # | 任务 | 描述 | 状态 |
|---|------|------|------|
| A1 | _java_info 保存 dependencies + modules | analyze_java() 已采集但丢弃的 dependencies[] 和 modules[] 存入 _java_info | ✅ |
| A2 | 创建 _python_info | analyze_python() 结果增加 _python_info: {build_backend, dependencies[]} | ✅ |
| A3 | 创建 _go_info | analyze_go() 结果增加 _go_info: {module_path} | ✅ |
| A4 | 创建 _node_info | analyze_node() 结果增加 _node_info: {package_name, package_version} | ✅ |

### Phase B — as_answers() 全量暴露（detector_constants.py）

| # | 任务 | 描述 | 状态 |
|---|------|------|------|
| B1 | DetectionResult 新增 _*_info 字段 | 添加 _python_info, _go_info, _node_info dataclass fields | ✅ |
| B2 | as_answers() 暴露公共字段 | frameworks, project_description, candidates 进入模板上下文 | ✅ |
| B3 | as_answers() 暴露 _java_info 全量 | java_build_tool, java_version_num, java_dependencies, java_modules | ✅ |
| B4 | as_answers() 暴露 _python_info | python_build_backend, python_dependencies | ✅ |
| B5 | as_answers() 暴露 _go_info | go_module_path | ✅ |
| B6 | as_answers() 暴露 _node_info | node_package_name, node_package_version | ✅ |

### Phase C — 模板消费检测数据

| # | 任务 | 文件 | 描述 | 状态 |
|---|------|------|------|------|
| C1 | CLAUDE.md 渲染 frameworks | `_shared/CLAUDE.md.jinja` | {% if frameworks %}## 框架{% for f in frameworks %}- {{ f }}{% endfor %}{% endif %} | ✅ |
| C2 | CLAUDE.md 渲染 modules | `_shared/CLAUDE.md.jinja` | Java 多模块项目渲染模块列表 | ✅ |
| C3 | CLAUDE.md 渲染 dependencies | `_shared/CLAUDE.md.jinja` | 依赖概要（从检测数据提取关键依赖） | ✅ |
| C4 | CLAUDE.md _external_data 桥 | `_shared/CLAUDE.md.jinja` | {% if _external_data %}{{ _external_data.architecture }}{% endif %} 条件渲染段 | ✅ |
| C5 | pom.xml 消费 java_version_num | `monorepo/java/pom.xml.jinja` + `_features/java/pom.xml.jinja` | `<version>{{ java_version_num or '0.1.0' }}</version>` | ✅ |
| C6 | app-service CLAUDE.md 同步 | `app-service/CLAUDE.md.jinja` | 同 C1-C4 更新 | ✅ |

### Phase D — 测试验证

| # | 任务 | 描述 | 状态 |
|---|------|------|------|
| D1 | 全量测试 | 650+ tests pass, 0 failures | ✅ |

---

## §v5.5 CLI 命令重组 + 帮助系统 ✅（2026-07-15 完成）

**背景**：ae init 有 28 个选项，--list-types/--list-templates/--analyze 伪装成 init 子选项语义混淆，5 个从 Copier 盲目继承的无用选项，--use-*/--no-* 双向开关浪费空间，选项无分层无使用示例。

**设计**：BEACON.md 决策 30。

### 命令重组

| # | 任务 | 描述 | 状态 |
|---|------|------|------|
| R1 | analyze 提升为独立命令 | `ae analyze <path> [--include-hidden]` | ✅ |
| R2 | list-types 提升为独立命令 | `ae list-types` | ✅ |
| R3 | list-templates 提升为独立命令 | `ae list-templates [--type <type>]` | ✅ |

### 选项精简

| # | 任务 | 描述 | 状态 |
|---|------|------|------|
| R4 | 移除 --templates-suffix | 无真实使用场景，内部 API 保留默认值 | ✅ |
| R5 | 移除 --preserve-symlinks | 同上 | ✅ |
| R6 | 移除 --hook-timeout | 模板 Task.timeout 已支持逐任务覆盖 | ✅ |
| R7 | 移除 --force-unsafe-template | 内聚到 --template-dir 白名单检查 | ✅ |
| R8 | 移除 --telemetry | 全局设置不应是单次 init flag | ✅ |

### 帮助系统

| # | 任务 | 描述 | 状态 |
|---|------|------|------|
| R9 | ae --help 场景导航 | 顶层帮助展示两种核心模式 + 命令列表 | ✅ |
| R10 | 每个命令有使用示例 epilog | init/analyze/update 各有使用示例 | ✅ |
| R11 | init 选项分层 | 核心(6)/配置覆盖(7)/流程控制(4)/高级 hidden(4) | ✅ |

### 向后兼容 + 测试

| # | 任务 | 描述 | 状态 |
|---|------|------|------|
| R12 | 保留 deprecated 选项 | init 上 --list-types/--list-templates/--analyze 仍可用但输出 warning | ✅ |
| R13 | Skill 模式更新 | _parse.py 新增 list-types/list-templates 解析；_runner.py 新增 _run_list_types/_run_list_templates | ✅ |
| R14 | 全量测试 | 655 passed, 0 failed | ✅ |

---

## §v5.5-e2e E2E 测试 + Bug 修复 ✅（2026-07-15 完成）

**背景**：以 TMP-for-init（Java Maven 多模块存量项目）为测试项目，端到端验证 ae analyze + ae init 全场景命令组合。

### Bug 修复

| # | Bug | 位置 | 修复 | 状态 |
|---|-----|------|------|------|
| E2E-1 | pom.xml 命名空间解析失败 | `detector_analyzers.py:176,189,195,203,206,236,238` | `tag(element)` → `tag(element.tag)`（7 处），传了 Element 对象而非 tag 字符串 | ✅ |
| E2E-2 | Jinja2 `or` 对 undefined 变量抛 UndefinedError | 4 模板文件 8 处 | `{{ detected_java_version or java_version }}` → `{{ detected_java_version \| default(java_version) }}`；`{% set is_java8 = ... %}` → 先用 `\| default('')` 存中间变量 | ✅ |
| E2E-3 | app-service/library 缺少 java_version | `app-service/ae-template.yml` + `library/ae-template.yml` | 新增 `java_version` question（default "21", when language == 'java'） | ✅ |

### 测试覆盖

| 场景 | 命令 | 结果 |
|------|------|------|
| 存量项目分析 | `ae analyze TMP-for-init` | 正确检测 library, app-service, monorepo + Java 8 + Spring Boot + Spring Cloud + 8 模块 |
| 存量项目分析（含隐藏目录） | `ae analyze TMP-for-init --include-hidden` | 正常工作 |
| 新建 monorepo Java | `ae init /tmp/dir --defaults --type monorepo --language java --skip-tasks --no-install` | 24 文件，pom.xml 正确（packaging=pom, modules, JUnit 5, java.version=21） |
| 新建 app-service Java | `ae init /tmp/dir --defaults --type app-service --language java --skip-tasks --no-install` | 21 文件，pom.xml 正确（Spring Boot parent, Spring Boot starters） |
| 新建 library Java | `ae init /tmp/dir --defaults --type library --language java --ci gitlab --skip-tasks --no-install` | 21 文件，pom.xml 正确（无 Spring Boot, JUnit 5），GitLab CI 生成 |
| 存量项目 --incremental | `ae init TMP-for-init --defaults --pretend --incremental` | 正确报错：缺少 .ae-answers.yml 基线（符合设计） |
| 存量项目 --force --pretend | `ae init TMP-for-init --defaults --pretend --force --type monorepo` | 通过 detect+prompt 阶段，不渲染 |
| 命令帮助 | `ae --help` / `ae init --help` / `ae analyze --help` / `ae update --help` | 选项分层清晰，使用示例 epilog |
| 独立命令 | `ae list-types` / `ae list-templates` / `ae list-templates --type monorepo` | 全部正常 |
| 全量测试 | `pytest tests/ -q --no-cov` | 655 passed, 0 failed |

---

## §v5.6-PhaseA Qoder 深度提取 + 分析输出重构 ✅（2026-07-15 完成）

**背景**：ae analyze 反复流于表面 — detect 只用 FRAMEWORK_SIGNATURES + pom.xml 解析，qoder 只读标题/描述，隐藏目录 4 个数据源（_index.yaml/技术栈与依赖.md/模块详解/知识图谱）基本未利用。系统根因：analyzer 是解析器不是分析器、输出是 stdout 散装不是结构化报告。

**设计**：BEACON.md 决策 36-38，3 层分析模型。

### A1-A5: detector_qoder.py 重构 — 5 个子函数独立解析

| # | 任务 | 描述 | 状态 |
|---|------|------|------|
| A1 | _extract_qoder_index() | 抽取 _index.yaml 解析逻辑：modules 列表、depends_on 关系、root module 元数据 | ✅ |
| A2 | _extract_qoder_tech_stack() | 解析 技术栈与依赖.md — 提取 ## 引言 段落作为技术栈摘要 | ✅ |
| A3 | _extract_qoder_module_details() | 遍历 核心模块详解/{mod}.md — 提取每个模块的 ## 简介 段落 | ✅ |
| A4 | _extract_qoder_metadata() | 解析 repowiki-metadata.json — 提取 wiki_pages/relations/catalog 统计 | ✅ |
| A5 | analyze_qoder_repowiki() 重构 | 调用 5 个子函数 + _build_module_relations()，组装完整 _qoder_info dict | ✅ |

### A6-A9: _qoder_info 字段扩展

| # | 任务 | 描述 | 状态 |
|---|------|------|------|
| A6 | tech_stack_summary | 从 技术栈与依赖.md 提取的结构化文本（500 字符截断） | ✅ |
| A7 | module_details | [{key, title, overview}] — 8 个模块各含概述文本（TMP-for-init 实测） | ✅ |
| A8 | module_relations | 从 _index.yaml depends_on + related_to 聚合（_build_module_relations()） | ✅ |
| A9 | quickstart | 从 快速开始.md 提取 3 个关键段落（简介/环境搭建/编译） | ✅ |

### A10-A12: as_answers() + 模板上下文

| # | 任务 | 文件 | 描述 | 状态 |
|---|------|------|------|------|
| A10 | as_answers() 暴露 qoder 新字段 | `detector_constants.py` | qoder_tech_stack_summary, qoder_module_details, qoder_module_relations, qoder_quickstart, qoder_has_quickstart, qoder_repowiki_metadata | ✅ |
| A11 | _RENDER_STR_VARS 补充 | `scaffold_render.py` | 新增 qoder_tech_stack_summary, qoder_quickstart 默认空字符串 | ✅ |
| A12 | CLAUDE.md 模板消费 qoder 变量 | `_shared/CLAUDE.md.jinja` + `monorepo/java/CLAUDE.md.jinja` | Tech Stack 段追加 qoder_tech_stack_summary；Modules 段用 qoder_module_details 作为 java_modules 回退 | ✅ |

### A13-A15: ae analyze 输出重构 + 验证

| # | 任务 | 文件 | 描述 | 状态 |
|---|------|------|------|------|
| A13 | ae analyze 4 段分层输出 | `_list_cmds.py` | §项目身份 → §技术栈 → §模块结构 → §初始化建议 | ✅ |
| A14 | --include-hidden 深度输出 | `_list_cmds.py` | include_hidden 时追加 §反向工程发现（qoder） | ✅ |
| A15 | 全量测试验证 | `tests/` | 655 passed, 0 failed（含 3 个测试断言更新） | ✅ |

### 变更摘要

| 文件 | 变更 |
|------|------|
| `detector_qoder.py` | 单一函数 → 6 个子函数：_extract_qoder_index/tech_stack/module_details/metadata/quickstart + _build_module_relations + _extract_first_paragraph + _extract_section_paragraph |
| `detector_constants.py:108-127` | as_answers() 新增 6 个 qoder 变量 |
| `scaffold_render.py:42-51` | _RENDER_STR_VARS 新增 qoder_tech_stack_summary, qoder_quickstart |
| `_list_cmds.py:50-100` | cmd_analyze 输出从 8 行平铺 → 5 段分层（含 §反向工程发现） |
| `templates/_shared/CLAUDE.md.jinja` | Tech Stack 段追加 qoder_tech_stack_summary；Modules 段 qoder_module_details 回退 |
| `templates/monorepo/java/CLAUDE.md.jinja` | Tech Stack 段追加 qoder_tech_stack_summary |
| `tests/test_cli_commands.py` | 6 处断言更新（"分析目录"→"项目身份"，"使用 --type 指定类型"→"手动指定"） |
| `tests/test_cli_integration.py` | 2 处断言更新（同上） |

---

## §1 活跃任务（P1 — 短期）

### TemplateRenderer 参数透传

| # | 任务 | 文件 | 描述 | 状态 |
|---|------|------|------|------|
| T2-1 | templates_suffix 参数 | `renderer.py` | TemplateRenderer.__init__ 添加 templates_suffix 参数 | 🔲 |
| T2-2 | preserve_symlinks 参数 | `renderer.py` | TemplateRenderer.__init__ 添加 preserve_symlinks 参数 | 🔲 |
| T2-3 | 读取 self.preserve_symlinks | `renderer.py` | render_to() 内联逻辑读取实例属性替代硬编码 | 🔲 |
| T2-4 | scaffold_render 签名扩展 | `scaffold_render.py` | render_to() 接收并透传 templates_suffix + preserve_symlinks | 🔲 |
| T2-5 | InitWorker 端到端透传 | `scaffold_phases.py` | _phase_render() 传递 template_config.templates_suffix | 🔲 |

### AnswersMap

| # | 任务 | 文件 | 描述 | 状态 |
|---|------|------|------|------|
| T3-1 | 版本语义澄清 | `answers.py`, `__init__.py` | _ae_version（模板引擎版本）vs __version__（包版本）注释说明 | 🔲 |

### run_update()

| # | 任务 | 描述 | 状态 |
|---|------|------|------|
| T16-1 | 研究 Copier run_update() | 读取 $AE_REFS_DIR/copier/copier/worker.py，输出设计决策 | 🔲 |
| T16-2 | 实现或放弃 | 基于 T16-1 决策，实现 run_update() 或更新 BEACON.md §不做 | 🔲 |

---

## §2 后续任务（P2 — 可延后）

| # | 任务 | 描述 | 状态 |
|---|------|------|------|
| T3-2 | secret_questions 验证 | 确认 secret: true 的 Question 自动调用 answers.hide() | 🔲 |
| T5-VERIFY | multiselect 验证 | 验证 click.Choice 多选支持，不支持则标记为 P2 改造项 | 🔲 |
| T12-VERIFY | 模板目录核对 | 核对 init/templates/ 实际文件与设计描述一致性 | 🔲 |
| T15-VERIFY | AnswersMap 层数确认 | 确认 Copier 额外 2 层在 AE 无实际用途，6 层已足够 | 🔲 |
| TTEST-COVER | 关键测试覆盖 | §17.2 8 个关键测试用例（路径穿越/条件渲染/冲突/增量/中断恢复）逐条覆盖 | 🔲 |
| TTEST-3 | 覆盖率目标 | 全量测试覆盖率 ≥ 80% | 🔲 |
| T11-1 | 设计文档 §3 更新 | _features/ 实际数量同步到文档 | 🔲 |
| T10-VERIFY | CLI 参数决策 | 确认 templates_suffix/preserve_symlinks 是否暴露到 CLI | 🔲 |

---

## §3 审计积压（已知但暂不修复）

> 处理纪律：每条含不修复理由 + 触发修复条件。后续审计必须先读此表，避免重复报告。

| # | 来源 | 级别 | 问题 | 位置 | 不修复理由 | 触发条件 |
|---|------|------|------|------|----------|---------|
| B1 | R2 | P1 | 变量命名不一致 — dst_path/target_dir/project_dir/dstdir 混用 | 10+ 文件 | 跨文件批量改名风险大，不影响功能 | 该模块大规模重构时顺手统一 |
| B2 | R2 | P2 | 双层 _shared/ 目录 — init_engineering/_shared/ 与 init/_shared/ 同名 | 2 目录 | 服务不同层级（包级 vs 模块级），强行合并破坏分层 | 包结构大调整时重新审视 |
| B3 | R2 | P2 | AnswersMap 核心方法返回 -> Any — 类型逃逸链 | answers.py:5 处 | 需泛型重设计，API 破坏性变更 | v6.0 大版本 |
| B4 | R2 | P2 | _load_schema() 硬编码路径 | manifest.py:83 | 路径相对 __file__，任何部署下都正确 | 需要支持外部 schema 路径时 |
| B5 | R2 | P2 | _LazyExternalDict 两处 Path.cwd() | answers.py:181,295 | 调用点仅在 init 过程内，cwd 不会变化 | 长生命周期守护进程场景 |
| B6 | R2 | P2 | render_to() 18 个参数 | scaffold_render.py:138 | 提取 RenderOptions dataclass 改 10+ 调用点，纯机械重构 | 修改 render 逻辑时顺手提取 |
| B7 | R2 | P2 | 4 文件接近 300 行 | answers.py/prompts.py/scaffold_phases.py/scaffold_update.py | 职责单一、拆散后增加阅读跳转成本 | 接近 400 行或职责混杂时 |
| B8 | R6 | - | 误报：_LazyExternalDict.__iter__/__len__/keys/items 被标记为未使用 | answers.py:299-310 | 已回退删除（8 测试失败），是 dict 协议必要部分 | 审计 agent 再次报告时忽略 |

---

## §4 历史执行阶段（已合并或完成）

以下阶段已基本完成或合并到上述任务，保留记录供追溯：

| 阶段 | 来源 | 内容 | 处置 |
|------|------|------|------|
| Phase 01-07 | v5.0-atdo-EXECUTION-PLAN.md | P0-2 exclude / P1-1~P1-5 透传 / P2-3 安全 / 测试 | 已基本完成，剩余任务已纳入 §1-§2 |
| Q-A 版本统一 | REFACTORING-PLAN.md Step 0 | _ae_version / __version__ / _min_ae_version 统一为 1.0.0 | ✅ 已完成 |
| Q-B 测试覆盖 | REFACTORING-PLAN.md Step 0 | 测试覆盖率 ≥ 80% | 持续进行，见 TTEST-3 |
| Q-C skill.py 参数 | REFACTORING-PLAN.md Step 0 | templates_suffix/preserve_symlinks Skill 入口 | ⏸ 暂缓（低频使用） |

---

## §5 优先级排序

```
v5.5 CLI 重组 + 帮助系统 ✅                     P0 — 已完成
  ↓
v5.4 检测信息完整性修复 ✅                       P0 — 已完成
  ↓
v5.3 信息流修复 ✅                               P0 — 已完成
  ↓
§1 活跃任务 (T2-1~5, T3-1, T16-1)             P1 — 短期应完成
  ↓
§2 后续任务 (TTEST-COVER, TTEST-3, ...)        P2 — 可延后
  ↓
§3 审计积压 (B1-B7)                             P2 — 触发条件满足时修复
```
