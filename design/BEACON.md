> 创建：2026-06-24 | 更新：2026-07-14 | 阶段：--include-hidden 扫描设计

## 目标与成功标准

1. **Agent Skill 模式运行**：`ae init` 作为 Claude Code Skill 在 agent 里调用，为 agent 工作流提供项目环境初始化能力
2. **存量项目自动初始化**：通过代码分析自动识别项目类型、依赖、配置，生成正确的初始化配置
3. **新项目向导初始化**：交互式询问确认项目方向、技术栈、目录结构，生成定制化项目骨架
4. **模板组合引擎**：9 类型 × 5 语言（含 plugin 多 Skill 插件模板）
5. **Pipeline 绕过阻断**：SKILL.md MUST_READ 门禁 + _required_outputs 自检，防止 AI 跳过 5 阶段流水线
6. **隐藏目录可扫描**：`--include-hidden` 将 .qoder/.claude/ 等隐藏目录纳入检测输入，消费反向工程资产

## 范围边界

**做：**
- Agent Skill 模式：5 阶段流水线（detect → prompt → render → tasks → finalize）
- 存量项目初始化：代码分析 → 自动识别 → 自动化配置（含隐藏目录资产）
- 新项目向导：交互式询问 → 确认方向 → 生成骨架
- 9 类型 × 5 语言模板 + 13 exports 公共 API
- `--include-hidden`：检测阶段扫描隐藏目录（默认关闭，显式 opt-in）

**不做：**
- 知识库格式适配器 — 隐藏目录内容由现有 analyze_* 函数统一处理，不做特殊解析
- dev-loop 开发循环 / 多 LLM Provider / Web UI / 远程模板

## 设计决策

| # | 决策 | 理由 | 日期 | status |
|---|------|------|------|--------|
| 1 | **v5.0 精简：只保留 Init 部分** | 项目聚焦 Init 工程 | 2026-06-30 | ✅ |
| 7 | **InitWorker 拆分为 5 阶段函数** | scaffold_phases.py 501→285 行 | 2026-07-02 | ✅ |
| 8 | **detector 拆分为 constants/analyzers/helpers** | detector.py 382→82 行 | 2026-07-02 | ✅ |
| 9 | **run_update() 实现** | 类比 Copier copier update | 2026-07-02 | ✅ |
| 10 | **AnswerMap 6 层 ChainMap 简化** | 来源 Copier 8 层 | 2026-07-01 | ✅ |
| 11 | **2 类渲染生命周期钩子** | tasks_before/after，移除 before_renderer 等 | 2026-07-01 | ✅ |
| 12 | **CLI 单版本透传 templates_suffix/preserve_symlinks** | TemplateConfig 默认值可被 CLI 覆盖 | 2026-07-01 | ✅ |
| 13 | **SKILL.md MUST_READ 门禁 + _required_outputs** | pipeline 绕过阻断：AI 不再手动模拟 init 流程 | 2026-07-14 | ✅ |
| 14 | **skill.py 拆为 skill/ 子包** | 337 行 → 4 文件（_types/_parse/_runner/__init__） | 2026-07-14 | ✅ |
| 15 | **NEGATED_FLAG_MAP 提取到 config_types.py** | --no-* 标志映射 SSOT，skill 和 CLI 文档共享 | 2026-07-14 | ✅ |
| 16 | **analyze_* 返回 DetectionResult 不静默 mutate** | 5 个分析函数签名从 -> None 改为 -> DetectionResult | 2026-07-14 | ✅ |
| 17 | **`--include-hidden` 扫描隐藏目录** | 将 .qoder/.claude/ 等隐藏目录纳入检测输入，不区分知识库格式 | 2026-07-14 | ✅ |

## 当前状态

**阶段：** --include-hidden 已实现，R8 审计修复完成

**最近动作：** 2026-07-14 — 实现 `--include-hidden`：detector_helpers（signature_matches + find_signatures_in_tree）→ detector.py → scaffold_phases.py → phases/detect.py → CLI + Skill 全链路透传，8 文件，~40 行改动，0 新文件。639 测试通过。

**下一步：** 待用户确认

**阻塞项：** 无

## 设计演进日志

| 日期 | 变更 | 原因 |
|------|------|------|
| 2026-07-14 | 设计 --include-hidden 扫描隐藏目录 | .qoder 等反向工程资产在隐藏目录下，原来被 detector_helpers 系统性跳过 |
| 2026-07-14 | R8 审计 16 项修复 + pipeline 绕过阻断 | P0 _logger 回归修复 / P1 API 扩展+skill 拆分+analyze 签名 / P2 日志+文档+命名 / SKILL.md 门禁 |
| 2026-07-14 | ae-init pipeline 绕过事故复盘 | AI 手动模拟 init 写 3 个文件而非调用 5 阶段流水线，根因 SKILL.md 缺 Pipeline 定义 |
| 2026-07-08 | 深度审计 9 轮 (R1-R8) | 错误处理/测试质量/类型安全/架构/性能/并发/模板/文档 8 维度扫描 |
| 2026-07-02 | v1.0 投产就绪 7 项 | 统一版本号 / monorepo 4 语言 / InitWorker 拆分 / detector 拆分 / run_update |
| 2026-07-01 | 第三轮深度修复 3 项 | lefthook 条件门控 + ProjectDetector 深度分析 + hook 多语言 |
| 2026-07-01 | 第二轮优化 5 项 | CI 条件渲染 + --language CLI + 共享模板泛化 |
| 2026-07-01 | 全面投产修复 7 项 | P0: builtin hooks 非阻塞 + Skill 注册 / P1: 6 类型模板 |

## 待解决问题

| 状态 | 问题 | 说明 |
|------|------|------|
| [✓] | 代码分析深度 | 已实现：依赖解析 + 框架识别 + 包管理器/测试框架/CI 自动推断 |
| [✓] | monorepo 多语言 | 已实现：typescript/python/go/rust/java 通过 _nested_templates 切换 |
| [✓] | run_update 命令 | 已实现：skip/overwrite/prompt 三种冲突策略 |
| [✓] | pipeline 绕过阻断 | 已实现：SKILL.md MUST_READ + _required_outputs 自检 |
| [~] | answers.py 323 行 | 接近 300 行阈值，职责仍单一，暂不拆分 |

## 引用文件

@design/INDEX.md · @design/v5.0-Design-Init.md · @design/audit-backlog.md · @design/his_bak/
