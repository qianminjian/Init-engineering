# design/ — 文档索引

> 创建：2026-06-25 | 更新：2026-07-14 | 维护规则：每次合并/重命名后更新本文件

---

## 文档分类

| 类别 | 文件 | 描述 |
|------|------|------|
| **项目明灯** | `BEACON.md` | 当前阶段/目标/阻塞项/设计决策 |
| **设计文档** | `v5.0-Design-Init.md` | v5.2 Init Engineering 完整设计（2026-07-14 更新） |
| **归档** | `his_bak/` | v1.0/v1.1 历史设计/计划/审计（见 §归档清单） |

---

## 命名规范

```
V<major>.<minor>-<Category>-<Name>.md
```

| Category 前缀 | 含义 |
|--------------|------|
| `Design` | 设计文档 — 架构/子系统设计 |
| `Audit` | 审计报告 — 问题发现/评估 |
| `Plan` | 执行计划 — 开发任务/路线图 |

**例外**：`BEACON.md` / `INDEX.md` — 特殊角色文件，保持原名。

---

## 归档清单（his_bak/）

| 原文件名 | 说明 | 日期 |
|---------|------|------|
| `v1.0-Design-Init.md` | v1.0 Init 设计 | 2026-06-25 |
| `v1.0-Design-Templates.md` | Init 模板设计 | 2026-06-25 |
| `v1.0-Design-Shared.md` | Init/Loop 共享契约（Init 保留参考） | 2026-06-25 |
| `v1.1-Audit-Report.md` | v1.1 审计报告（含 Init 修复） | 2026-06-25 |
| `v1.1-Plan-Dev.md` | v1.1 开发计划 | 2026-06-25 |
| `init-PLAN.md` | Init 开发计划 | 2026-06-25 |
| `init-TODO.md` | Init 待办 | 2026-06-25 |
| `v1.0-INIT-PLAN.md` | v1.0 Init 计划 | 2026-06-25 |

---

## 合并日志

| 日期 | 主文档 | 来源/操作 | 摘要 |
|------|--------|---------|------|
| 2026-07-14 | `v5.0-Design-Init.md` → v5.2 | R8 深度审计 16 项修复 + pipeline 绕过阻断（SKILL.md MUST_READ + _required_outputs + skill/ 拆分） |
| 2026-06-30 | — | 文档裁剪 | 删除 Loop 相关文档：`design/v5.0-Design-Loop.md`、`docs/`、`design/his_bak/` 下所有 Loop/v2.x 文件，保留 Init 相关设计文档 |
| 2026-06-25 | `v1.0-Design-*.md` | 重命名 | 设计文档启用新命名规范 |
| 2026-06-25 | `v1.1-Audit-Report.md` | 重命名 + 合并 | 合并审计报告 |
| 2026-06-25 | `his_bak/` | 重命名归档 | 12 个历史待办文件归档 |

---

## 工作流程规范

### 主文档头部格式

```markdown
# <文档名>

> 来源：@design/INDEX.md | 创建：YYYY-MM-DD | 更新：YYYY-MM-DD
```

### 合并/重命名流程

1. **工作中**：在 `design/` 根目录创建带时间戳的工作文档
2. **完成确认后**：
   - 将内容合并到对应的主文档
   - 将工作文档移动到 `his_bak/`，命名改为 `v<VERSION>-<Category>-<YYYYMMDD>.md`
   - 在本 INDEX.md 的合并日志追加一行
3. **主文档头部**：必须包含 `来源:` 字段，指向本 INDEX

---

## 引用约定

- 主文档引用：`@design/<filename.md>`
- 归档引用：`@design/his_bak/<filename.md>`
- 代码引用：`@auto_engineering/<path>`
