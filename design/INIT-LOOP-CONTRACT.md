# Init → Loop 契约交接文档（面向 Init 项目）

> 创建：2026-07-09 | 契约版本：schema **1.1**（v5.6）| 来源：Loop 项目 BEACON 决策 #48 / D21
> 用途：本文件是 **Loop 项目对 Init 项目的需求输入**，自包含。Init 团队照此实现，无需读 Loop 内部设计文档。
> 定位：Loop 是 Init 产物的**消费者**。本文件规定 Init **必须产出什么、格式如何、如何保持双仓库不漂移**。

---

## 0. TL;DR（Init 这次要做的 4 件事）

1. **产出 `init-manifest.json`** 到目标项目根 `.ae-state/init-manifest.json`，符合 schema 1.1。
2. **新增 2 个字段**（v5.6 相对旧版的增量）：
   - `conventions.ci_platform`（Init 声明它脚手架了哪个 CI：`github`/`gitlab`/`none`）
   - `structure.design_root`（可选：设计文档目录约定）
3. **采用共享 Schema SSOT**：复制 `init-manifest.schema.json`（版本 pin），**生成 manifest 后依它自校验**（产出即合约）。
4. **维护共享 reference fixture**：`init-manifest.reference.json`，Init 侧做生成断言（双仓库同步）。

> 不需要 Init 做的：任何 Loop 侧逻辑（校验代码、Gate 配置、CI 执行）都在 Loop 项目，Init 不实现。见 §8。

---

## 1. 契约总览

| 维度 | 约定 |
|------|------|
| **方向** | 单向 `Init → Loop`。Init 完成初始化时**写**，Loop 启动时**读**。 |
| **Loop → Init** | 无。Loop **不反向调用** Init，不依赖 Init 运行时在场。 |
| **产物位置** | 目标项目根 `.ae-state/init-manifest.json` |
| **只读保证** | Loop **不修改** manifest（含 mtime 不变）。Init 是该文件唯一写入方。 |
| **契约 SSOT** | `init-manifest.schema.json`（版本化 JSON Schema，双仓库共享，见 §5） |
| **前向兼容** | Loop 遇未知字段静默忽略（WARN 不阻断）。Init 可安全添加扩展字段。 |

**设计思路（为什么这样）**：单向 + 文件桥接 = Init 与 Loop 完全解耦，Init 可用任意语言实现，双方独立发版；只读保证使 Loop 不会污染 Init 产物；文件而非 API 调用，便于调试与离线复现。

---

## 2. Init 必须产出的 manifest — 完整字段规格

写入 `.ae-state/init-manifest.json`，UTF-8 JSON，顶层为对象。

| 字段 | 类型 | 必需 | 含义 / Init 如何填 | 版本 |
|------|------|------|-------------------|------|
| `schema_version` | string | ✅ | 本 manifest 遵循的 schema 版本，当前 `"1.1"`。Loop 兼容窗口：≥1.0 接受，>9.9 WARN。 | 1.0 |
| `project_type` | enum(8) | ✅ | 见 §3 枚举。决定 Loop 的项目类型校验。 | 1.0 |
| `language` | enum(5) | ✅ | `python`/`typescript`/`go`/`rust`/`bash`。决定默认工具链。 | 1.0 |
| `conventions.linter` | string | ✅ | linter 命令名（如 `ruff`/`eslint`）。Loop 配 lint Gate。 | 1.0 |
| `conventions.type_checker` | string | ✅ | 类型检查命令（如 `mypy`/`tsc`）。Loop 配 type_check Gate。 | 1.0 |
| `conventions.test_runner` | string | ✅ | 测试命令（如 `pytest`/`vitest`）。Loop 配 test Gate。 | 1.0 |
| `conventions.build_cmd` | string | ⬜ | 构建命令（如 `uv build`）。Loop 配 build Gate。缺省则跳过 build。 | 1.0 |
| **`conventions.ci_platform`** | **enum** | **⬜（默认 `none`）** | **`github`/`gitlab`/`none`。Init 声明它脚手架了哪个远程 CI。Loop 据此选 CI 薄壳。** | **1.1（新增）** |
| `structure.source_root` | string | ✅ | 源码根（如 `src` 或包名目录）。Loop 文件沙箱根。 | 1.0 |
| `structure.test_root` | string | ✅ | 测试目录（如 `tests`）。 | 1.0 |
| **`structure.design_root`** | **string** | **⬜** | **设计文档目录约定（如 `design`）。Loop 的设计文档模式 / 预检默认检索根。** | **1.1（新增）** |

### 2.1 完整示例（Init 目标产物）

```json
{
  "schema_version": "1.1",
  "project_type": "cli-tool",
  "language": "python",
  "framework": null,
  "created_at": "2026-07-09T10:00:00Z",
  "init_version": "1.0.0",
  "conventions": {
    "linter": "ruff",
    "type_checker": "mypy",
    "test_runner": "pytest",
    "build_cmd": "uv build",
    "ci_platform": "github"
  },
  "structure": {
    "source_root": "my_tool",
    "test_root": "tests",
    "design_root": "design"
  },
  "templates_applied": ["python-cli"],
  "answers": {}
}
```

> `framework`/`created_at`/`init_version`/`templates_applied`/`answers` 是 Loop 已知的可选扩展字段（Init 可填，Loop 保留不报未知）。任何其它字段 Loop 静默忽略。

---

## 3. 枚举合法值

**`project_type`（8）**：`app-service` · `library` · `cli-tool` · `skill` · `hook` · `mcp-server` · `spec-doc` · `monorepo`

**`language`（5）**：`python` · `typescript` · `go` · `rust` · `bash`

**`conventions.ci_platform`（3，v5.6 新增）**：`github` · `gitlab` · `none`

> Loop 对 `project_type`/`language` 做**严格枚举校验**（不在表内 → 拒绝运行）。Init 不得输出表外值。若 Init 需要新增类型/语言，须先按 §5 升级 schema 并双仓库同步。

---

## 4. v5.6 新增字段的设计思路（Init 需理解的"为什么"）

### 4.1 `conventions.ci_platform`（决策 B1）

- **为什么放在 manifest**：Init 知道自己脚手架了 `.github/workflows/` 还是 `.gitlab-ci.yml`，由 Init 声明**最权威**。Loop 若靠运行时探测目录来猜平台会很脆弱（两个都在、都不在、命名变体）。
- **Init 怎么填**：脚手架 GitHub Actions → `"github"`；GitLab CI → `"gitlab"`；未配置远程 CI → `"none"`（或省略）。
- **Loop 怎么用**：选择对应的远程 CI 薄壳（GitHub Actions / GitLab CI），CI 只跑静态 Gate，不跑 dev-loop、不需要 API Key。

### 4.2 `structure.design_root`（决策 B2）

- **边界（重要）**：manifest 只声明设计文档**目录位置**，**不承载设计文档内容**。设计文档的**内容/路径**是人工/CLI 输入（Loop 侧 `ae dev-loop --design-doc <path>`）。
- **判据**：manifest 载"结构约定 / 工具约定"，不载"设计意图"。Init 负责脚手架结构（可以创建空的 `design/` 目录并声明其位置），但 Init **不生产设计意图内容**。
- **Init 怎么填**：若脚手架时创建了设计文档目录（如 `design/`），填其相对路径；否则省略。

---

## 5. Schema SSOT 协议 —— 防跨仓库漂移（决策 A，核心）

**问题**：Init 与 Loop 是**两个独立仓库**。若契约只写在各自文档里，字段迟早对不上。

**协议**：

1. **唯一权威源** = `init-manifest.schema.json`（标准 JSON Schema，draft 2020-12）。**Loop 仓库持有权威副本**。
2. **Init 侧采用方式**：**复制** schema 文件进 Init 仓库并 **pin 版本**（记录来源 commit / version）。**不做运行时链接**（不 import、不网络拉取）——复制内化。
3. **Init 生成后自校验**：Init 写出 manifest 前，用该 schema 校验自己的产物（如 Node 用 `ajv`、Python 用 `jsonschema`）。**产出即合约**——Init 不产出不合 schema 的 manifest。
4. **变更流程**：任何字段增删改 = 契约变更 → **先改 schema + bump `version` 字段 + 双仓库同步 + 更新 reference fixture（§6）**，再改各自代码。
5. **版本联动**：schema 文件的 `version` 与 manifest 的 `schema_version` 对应。Loop 兼容窗口 min 1.0（硬拒绝更低）/ max 9.9（更高则 WARN forward-compat）。

### 5.1 权威 JSON Schema（schema 1.1，Init 复制此内容为 `init-manifest.schema.json`）

```jsonc
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://auto-engineering/init-manifest.schema.json",
  "version": "1.1",
  "type": "object",
  "required": ["schema_version", "project_type", "language", "conventions", "structure"],
  "additionalProperties": true,
  "properties": {
    "schema_version": { "type": "string" },
    "project_type": {
      "enum": ["app-service","library","cli-tool","skill","hook","mcp-server","spec-doc","monorepo"]
    },
    "language": { "enum": ["python","typescript","go","rust","bash"] },
    "conventions": {
      "type": "object",
      "required": ["linter", "type_checker", "test_runner"],
      "properties": {
        "linter": { "type": "string" },
        "type_checker": { "type": "string" },
        "test_runner": { "type": "string" },
        "build_cmd": { "type": "string" },
        "ci_platform": { "enum": ["github","gitlab","none"], "default": "none" }
      }
    },
    "structure": {
      "type": "object",
      "required": ["source_root", "test_root"],
      "properties": {
        "source_root": { "type": "string" },
        "test_root": { "type": "string" },
        "design_root": { "type": "string" }
      }
    }
  }
}
```

> `additionalProperties: true` 是刻意的——保证前向兼容（Init 可加扩展字段，旧 Loop 忽略）。

---

## 6. 共享 reference fixture 协议（决策 D）

**问题**：此前双方只在各自仓库测合成样例，Init 的**真实输出格式**从未被双方共同 pin —— 双边契约只测了一侧。

**协议**：

- **共享样例** = `init-manifest.reference.json`：一份**代表真实 Init 产物**的样例，覆盖全部必需 + 可选字段 + 一个 monorepo 样例。
- **双仓库同步**：同一份 fixture 存在于 Init 与 Loop 两仓库。
  - **Init 侧（生成断言）**：Init 对某标准输入跑初始化，断言产出 == reference fixture（或至少通过 schema + 关键字段匹配）。
  - **Loop 侧（消费断言）**：Loop 对 reference fixture 断言 `validate` 通过且 Gate 配置符合预期。
- **升级同步**：schema `version` 升级时，两侧同步更新此 fixture。

---

## 7. monorepo 约定（决策 C，Init 须知的当前限制）

- Loop 当前的文件沙箱与批次状态设计**基于单包布局**。
- `monorepo` 枚举值**被接受**，但 Loop 会把 `structure.source_root` / `test_root` 当作**主包**根处理（多包沙箱隔离**尚未实现**）。
- **Init 怎么填**：若输出 `project_type: "monorepo"`，请把 `source_root`/`test_root` 指向**主包/主要工作包**。Loop 运行时会输出单包降级 WARN。
- 多包完整支持是 Loop 侧未来工作，届时会 bump schema 并按 §5 通知 Init。

---

## 8. 明确不属于 Init 的部分（避免误做）

以下全部是 **Loop 侧**职责，Init **不实现**：

- manifest 的校验代码（Loop 用 `jsonschema` 对照 schema 校验）
- `conventions.*` → 具体 Gate 实例的映射（lint/type_check/test/build/CI 薄壳选型）
- 设计文档内容的解析、Pre-flight Gap 分析、dev-loop 执行
- `.ae-state/checkpoints.db` —— 这是 **Loop 私有运行时状态，不是契约面**，Init 不读不写

---

## 9. Init 侧实现验收清单

- [ ] 产出 `.ae-state/init-manifest.json`，`schema_version` = `"1.1"`
- [ ] 5 个必需字段齐全（schema_version/project_type/language/conventions/structure），且 conventions 含 linter/type_checker/test_runner，structure 含 source_root/test_root
- [ ] `project_type`/`language` 取值在 §3 枚举内
- [ ] **新增** `conventions.ci_platform` 反映实际脚手架的 CI（github/gitlab/none）
- [ ] **新增** `structure.design_root`（若脚手架了设计文档目录）
- [ ] 复制 `init-manifest.schema.json`（version 1.1）进 Init 仓库并 pin 版本
- [ ] 生成 manifest 后**依 schema 自校验**通过才写盘
- [ ] 同步 `init-manifest.reference.json` 并加生成侧断言
- [ ] `project_type=monorepo` 时 source_root/test_root 指向主包
- [ ] 不写 `.ae-state/checkpoints.db`，不期望 Loop 回调

---

## 10. 变更历史

| 日期 | schema | 变更 |
|------|--------|------|
| 2026-07-09 | 1.1 | v5.6：新增 `conventions.ci_platform` + `structure.design_root`；引入 schema SSOT + reference fixture 双仓库同步协议；澄清 monorepo 单包限制；checkpoints.db 明确非契约面。Loop BEACON #48 / D21 |
| （更早） | 1.0 | 初始契约：schema_version/project_type/language/conventions/structure + IL-AC-01~05 |
