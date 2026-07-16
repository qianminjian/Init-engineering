# TASKS.md — 任务跟踪表

> 创建：2026-07-14 | 更新：2026-07-16（v5.6 Phase D+E+F+G 完成）

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

## §v5.6-Phase-D 模板工程化修复 ✅（2026-07-16 完成）

**背景**：故障报告 `ae-init-incremental-2026-07-16.md`（P0: 测试文件未生成/sub-module pom.xml 缺失/source entry 缺失，P1: Maven wrapper jar 缺失/模块名不匹配，P2: pre-commit 空 shell）。根因：monorepo 模板设计为 TypeScript-only，Java monorepo 的测试目录、Maven wrapper、模块校验等均未覆盖。

**设计**：BEACON.md 决策 47-53。

| # | 任务 | 文件 | 描述 | 状态 |
|---|------|------|------|------|
| PD-1 | 测试目录统一 | `_features/{ts,java,go,bash,rust}/tests/` + `monorepo/{java,ts,python,go,rust}/tests/` | 6 语言测试文件从 src/ 移到根级 tests/，独立于源码目录 | ✅ |
| PD-2 | Monorepo Java tests/ Maven 模块 | `monorepo/java/tests/pom.xml.jinja` + `MonorepoTest.java.jinja` | tests/ 作为独立 Maven 模块，parent 引用根 POM，testSourceDirectory=. | ✅ |
| PD-3 | Maven testSourceDirectory 统一 | `_features/java/pom.xml.jinja` | app-service + library 添加 `<testSourceDirectory>tests</testSourceDirectory>` | ✅ |
| PD-4 | Maven wrapper jar 内嵌 | `_features/java/.mvn/wrapper/maven-wrapper.jar` | 63KB 二进制从 Maven Central v3.3.2 下载纳入模板 | ✅ |
| PD-5 | .gitignore 白名单 | `_shared/.gitignore.jinja` | Java 块添加 `!.mvn/wrapper/maven-wrapper.jar` | ✅ |
| PD-6 | 模块磁盘校验 | `detector_analyzers.py` + `_list_cmds.py` | analyze_java() 对比 pom.xml modules vs 磁盘目录，输出缺失/多余模块警告 | ✅ |
| PD-7 | 增量排除范围精确化 | `scaffold_render.py` | `packages/**` → `packages/**/src/main/**`，保留测试模板和 pom.xml | ✅ |
| PD-8 | monorepo/ae-template.yml java_modules 默认值 | `monorepo/ae-template.yml` | 默认 `"module1,module2"` → `"module1,module2,tests"` | ✅ |
| PD-9 | Go/Rust 测试惯例对齐 | `monorepo/go/tests/main_test.go.jinja` + `monorepo/rust/tests/test_lib.rs.jinja` | Go 使用 package main_test 黑盒测试，Rust 使用 tests/ cargo 集成测试 | ✅ |
| PD-10 | 测试断言更新 | `tests/test_init.py:147` | `src/index.test.ts` → `tests/index.test.ts` | ✅ |

### 变更摘要

| 文件 | 变更 |
|------|------|
| `_features/typescript/tests/index.test.ts.jinja` | 从 `src/index.test.ts.jinja` 移动 |
| `_features/java/tests/MainTest.java.jinja` | 从 `src/test/java/com/example/app/MainTest.java.jinja` 移动 |
| `_features/go/tests/main_test.go.jinja` | 从 `{{ project_name }}/main_test.go.jinja` 移动 |
| `_features/bash/tests/test_hello.sh.jinja` | 从 `test_hello.sh.jinja` 移动 |
| `_features/rust/tests/test_main.rs.jinja` | 新建 |
| `monorepo/java/tests/MonorepoTest.java.jinja` | 新建 |
| `monorepo/java/tests/pom.xml.jinja` | 新建（Maven 模块 POM） |
| `monorepo/typescript/tests/index.test.ts.jinja` | 新建 |
| `monorepo/python/tests/test_hello.py.jinja` | 新建 |
| `monorepo/go/tests/main_test.go.jinja` | 新建 |
| `monorepo/rust/tests/test_lib.rs.jinja` | 新建 |
| `_features/java/pom.xml.jinja` | 添加 `<testSourceDirectory>tests</testSourceDirectory>`（app-service + library 双分支） |
| `_features/java/.mvn/wrapper/maven-wrapper.jar` | 新建（63KB 二进制） |
| `_shared/.gitignore.jinja` | 添加 `!.mvn/wrapper/maven-wrapper.jar` |
| `detector_analyzers.py:261-293` | 添加 module-disk validation |
| `_list_cmds.py:205-210` | 添加 module mismatch 警告 |
| `scaffold_render.py:199-203` | 增量排除 `packages/**/src/main/**`，新增 incremental monorepo 排除 |
| `monorepo/ae-template.yml:78` | java_modules 默认值更新 |
| `tests/test_init.py:147` | 断言路径更新 |

---

## §v5.6-Phase-E Phase 4 任务分层 ✅（2026-07-16 完成）

**背景**：模板引擎为 1:1 静态文件映射，无法为 `java_modules` 中动态检测的模块列表生成 per-module 测试。根级别 `tests/` Maven 模块由模板覆盖，但 `{module}/src/test/java/` 需要运行时动态生成。

**设计**：BEACON.md 决策 52 — Phase 4 任务分层：模板覆盖根级别骨架，`_tasks` 负责模块级动态补充。

| # | 任务 | 文件 | 描述 | 状态 |
|---|------|------|------|------|
| PE-1 | monorepo _tasks 新增 | `monorepo/ae-template.yml` | 新增 `_tasks` 块（39 行），Phase 4 bash 任务 | ✅ |
| PE-2 | bash 脚本：per-module 测试生成 | 同上 | 遍历 `java_modules`，检查 `{module}/src/test/java/` 是否存在，缺则生成 JUnit 5 骨架 | ✅ |
| PE-3 | when 条件 | 同上 | `language == 'java' and java_modules | default('') | trim` | ✅ |
| PE-4 | 幂等性 | 同上 | `[ ! -d "$TD" ]` 保证已存在测试目录不覆盖 | ✅ |
| PE-5 | 全量测试验证 | `tests/` | 655 passed, 0 failed | ✅ |

### 技术细节

- **执行层**：`TaskRunner.run()` → `subprocess_run(["bash", "-c", "<script>"], cwd=tmpdir)`，`shell=False`（list cmd 模式）
- **Jinja2 渲染**：`{{ java_modules }}`、`{{ java_group_id }}` 在 bash 执行前由 SandboxedEnvironment 渲染
- **Bash 逻辑**：`IFS=',' read -ra` 分割逗号分隔模块列表，`xargs` 修剪空白，`tr '.' '/'` 转换包路径
- **跳过规则**：空模块名、`tests` 根模块、已有 `src/test/java/` 的模块
- **生成产物**：`{module}/src/test/java/{group_id_path}/ModuleTest.java`（JUnit 5 骨架）

---

## §v5.6-Phase-F — 检测层根因修复 ✅（2026-07-16 完成）

**背景**：TMP-for-init 故障报告 6 个问题。测试目录反复生成失败 10+ 次的根因不在模板层（Phase D/E），而在检测层——模块路径扁平化、同级 POM 漏检、增量模式结构冲突。

**设计**：BEACON.md 决策 58-60。

### 问题 → 修复映射

| # | 问题 | 严重度 | 根因 | 修复 | 文件 |
|---|------|--------|------|------|------|
| 1 | spec-doc 误判绕过 monorepo 路径 | P0 | `design/*.md` 签名匹配任何有设计文档的项目，project_type 在深度分析前被确定为 spec-doc | 深度分析检测到语言+monorepo 时覆盖签名级类型 | `detector.py` |
| 2 | `/pom.xml` exclude 从未生效 | P1 | `_is_excluded()` 检查模板源路径（含 `.jinja`），`/pom.xml` 无法匹配 `pom.xml.jinja` | 输出路径（去 .jinja 后）二次检查 | `renderer.py` |
| 3 | 兄弟 POM 扫描 UnboundLocalError | P0 | 函数内 `import ET` 遮蔽顶层导入，代码路径未经过内部 import 时 ET 未绑定 | 移除重复内部 import | `detector.py` |

### 修复详情

| # | 任务 | 文件 | 描述 | 状态 |
|---|------|------|------|------|
| PG-1 | spec-doc 覆盖 | `detector.py` | `result.language is not None and "monorepo" in candidates` → 覆盖 project_type | ✅ |
| PG-2 | exclude 输出路径检查 | `renderer.py` | 去 .jinja 后缀后用 `self._exclude_matcher(rendered_rel)` 再检查 | ✅ |
| PG-3 | 移除内部 import ET | `detector.py` | 删除 L130 `import xml.etree.ElementTree as ET`，使用顶层导入 | ✅ |
| PG-4 | TMP-for-init 实战验证 | - | project_type=monorepo, 10/10 模块测试文件, 无根 pom.xml, 无 packages/ | ✅ |
| PG-5 | 全量测试 | `tests/` | 655 passed, 0 failed | ✅ |

### TMP-for-init 验证结果

| 检查项 | 结果 |
|--------|------|
| project_type | monorepo ✅ |
| 根 pom.xml | 未生成 ✅ |
| packages/ | 未生成 ✅ |
| tmp/tmp-boot~tmp-workflows (8) | src/test/java/ModuleTest.java ✅ |
| tmp-manage | src/test/java/ModuleTest.java ✅ |
| tmp-window | src/test/java/ModuleTest.java ✅ |
| 模块路径前缀 | tmp/tmp-boot ✅ |
| 同级 POM 识别 | tmp-manage, tmp-window ✅ |

---

## §v5.6-Phase-H — 内容感知类型推断 ✅（2026-07-16 完成）

**背景**：Phase G 修复了 spec-doc 签名过于宽泛的问题，但内容推断仅扫描 `design/*.md`。voice_clone_for_auto_design 设计文档（`需求提示词.md`）在根目录，无 `design/` 目录，零签名匹配。voice_clone_for_auto_test-2 的 design/ 目录下文档被正确推断，但根目录设计文档项目无法覆盖。

**设计**：BEACON.md 决策 61。

### 修复详情

| # | 任务 | 文件 | 描述 | 状态 |
|---|------|------|------|------|
| PH-1 | 扫描范围扩展 | `detector.py:_infer_type_from_design_docs` | 同时扫描根目录 *.md + design/*.md | ✅ |
| PH-2 | 触发条件扩展 | `detector.py:analyze()` | project_type in (None, "spec-doc")，覆盖零签名匹配 | ✅ |
| PH-3 | 关键词表 | `detector_constants.py` | TYPE_HINT_KEYWORDS: app-service/cli-tool/library 中英文 | ✅ |
| PH-4 | voice_clone_for_auto_design 验证 | - | 根目录需求提示词.md → app-service ✅ | ✅ |
| PH-5 | 回归验证 | - | voice_clone_for_auto_test-2 → app-service ✅, TMP-for-init → monorepo ✅ | ✅ |

### 验证结果

| 测试项目 | 签名匹配 | 构建文件 | 推断来源 | 最终类型 |
|---------|---------|---------|---------|---------|
| voice_clone_for_auto_test-2 | spec-doc (design/*.md) | 无 | design/*.md 关键词 | app-service ✅ |
| voice_clone_for_auto_design | 无 | 无 | 根目录 *.md 关键词 | app-service ✅ |
| TMP-for-init | spec-doc, monorepo | Java/Maven | 深度分析（构建系统） | monorepo ✅ |

---

## §v5.6-Phase-F — 检测层根因修复 ✅（2026-07-16 完成）

**背景**：TMP-for-init 故障报告 6 个问题。测试目录反复生成失败 10+ 次的根因不在模板层（Phase D/E），而在检测层——模块路径扁平化、同级 POM 漏检、增量模式结构冲突。

**设计**：BEACON.md 决策 54-57。

### 问题 → 修复映射

| # | 问题 | 严重度 | 根因 | 修复 | 文件 |
|---|------|--------|------|------|------|
| 1 | 根级 pom.xml 与实际结构不符 | P0 | `is_multi_module` 触发 monorepo 模板生成根 reactor POM，但项目聚合在 `tmp/pom.xml` | aggregator_path 非空时排除 `/pom.xml` `packages/` | `scaffold_render.py` |
| 2 | packages/ 目录污染 | P0 | monorepo 模板默认创建 `packages/` 目录 | 同上（打包修复） | `scaffold_render.py` |
| 3 | 测试目录/配置未生成 | P1 | 模块路径扁平化 → Phase 4 bash 任务找错目录 | 模块路径拼接 aggregator_path 前缀 | `detector_analyzers.py` |
| 4 | java_version 字段冲突 | P1 | 两个检测源（pom.xml + qoder）值不一致 | 用户自行处理（数据一致性校验超出 Phase F 范围） | - |
| 5 | 模块路径扁平化 | P2 | `<module>tmp-boot</module>` 在 `tmp/pom.xml` 中，路径应为 `tmp/tmp-boot` | `analyze_java()` 接收 `project_root`，计算 relative path 前缀 | `detector_analyzers.py` |
| 6 | tmp-manage/tmp-window 漏检 | P2 | 只解析 `<modules>` 列表，未扫同级目录的 `<parent>` 引用 | `detector.py` 新增同级 POM 扫描逻辑 | `detector.py` |

### 修复详情

| # | 任务 | 文件 | 描述 | 状态 |
|---|------|------|------|------|
| PF-1 | 模块路径前缀 | `detector_analyzers.py` | `analyze_java()` 签名增加 `project_root`，计算 aggregator_path | ✅ |
| PF-2 | 同级 POM 扫描 | `detector.py` | 遍历根目录 pom.xml，匹配 `<parent>` 引用聚合 POM 的独立模块 | ✅ |
| PF-3 | 增量结构防护 | `scaffold_render.py` | `aggregator_path` 非空时 exclude `["/pom.xml", "packages/"]` | ✅ |
| PF-4 | 磁盘校验顺序修复 | `detector_analyzers.py` | `missing_modules` 校验移到路径拼接**之前**，使用原始模块名 | ✅ |
| PF-5 | aggregator_path 数据流 | `detector_constants.py` | `as_answers()` 新增 `aggregator_path` 导出 | ✅ |
| PF-6 | 全量测试 | `tests/` | 655 passed, 0 failed | ✅ |
| PF-7 | Mock 验证 | - | 模拟 TMP-for-init：5 模块全检测、路径正确、无假阳性 | ✅ |

### 变更文件

| 文件 | 变更 |
|------|------|
| `detector_analyzers.py` | aggregator_path 计算 + 模块路径前缀 + 磁盘校验顺序修复 |
| `detector.py` | 同级 POM 扫描 + `analyze_java()` 传递 `project_root` |
| `scaffold_render.py` | 增量模式结构防护（aggregator_path 非空时排除冲突模板） |
| `detector_constants.py` | `as_answers()` 导出 `aggregator_path` |

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
