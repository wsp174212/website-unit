# 协作验证方案 — Codex × Claude 双 Worktree 并行开发

> 目标：验证两个 AI agent 在各自 worktree/分支中并行开发，分工清晰、冲突最小，
> 最终人类执行两条 merge 即可完成整合。

## 1. 被测的中等任务：访问统计仪表盘

当前系统已经在 `sites` 表记录了 `visit_count` / `last_visited_at`，
`POST /api/sites/{id}/visit` 也已存在，但数据只反映"累计总数"，没有时间窗口
概念，前端也没有任何可视化。本次新增：

- **后端**：新增 append-only 的 `visit_events` 表记录每次访问；新增
  `GET /api/stats/overview?days=30` 聚合接口（每日访问、Top 站点、分组分布）。
- **前端**：新增「统计」视图，用零依赖的内联 SVG 展示每日访问柱状图、
  Top 站点、分组占比，支持 7 / 30 / 90 天切换。

选这个任务的原因：它是一个真正端到端的中等功能，但接缝恰好与仓库现有的
分层边界（`app/` vs `static/`）完全重合，两个 agent 的写文件集合**交集为空**，
同时又必须严格依赖同一份接口契约才能跑通——既验证"不冲突"，又验证"能协作"。

## 2. 分支与 worktree

| 角色 | 分支 | worktree |
|---|---|---|
| Codex（后端） | `agent/codex-api` | `../my-project-codex` |
| Claude（前端） | `agent/claude-ui` | `../my-project-claude` |
| 人类（合并） | `main` | `../website-unit` |

## 3. 防冲突设计的四个机制

1. **脚手架先行**：AGENTS.md、CLAUDE.md、docs/collab/* 先进入 main，
   两个 agent 分支从同一基线出发（见第 5 节）。agent 不允许在自己分支上
   新增/修改这些文件，从根上消除"两边都写规则文件"的冲突。
2. **文件归属表**（AGENTS.md 第 3 节）：每个文件有且仅有一个可写方，
   表外文件一律不碰——包括格式化、import 重排这类"无害改动"。
3. **契约冻结**：docs/collab/CONTRACT.md 是唯一接口事实来源，路径、参数、
   JSON 字段名、空值规则全部写死；发现缺陷只能提"变更建议"，不能私自改。
4. **提交留痕**：提交信息前缀 `[codex-api]` / `[claude-ui]`，
   便于事后审计双方实际改了哪些文件。

## 4. 验证成功的标准

| # | 标准 | 检查方式 |
|---|---|---|
| 1 | 两条 merge 均无冲突完成 | 人类执行 docs/collab/MERGE.md |
| 2 | 双方改动文件集合交集为空 | `git diff --name-only` 对比（见 MERGE.md） |
| 3 | 无 agent 触碰冻结文件/对方文件 | 同上 |
| 4 | 合并后全量测试通过 | `pytest` |
| 5 | 端到端跑通：点击站点 → 统计视图出现数据 | 浏览器人工验收 |

## 5. 启动前的脚手架落地步骤（人类执行，只做一次）

当前这批协作文件是在 `agent/codex-api` worktree 生成的，需先同步到 main
并让两个分支共享同一基线：

```powershell
# 1) codex worktree 中提交脚手架
git add AGENTS.md CLAUDE.md docs/collab
git commit -m "chore: add dual-agent collaboration scaffolding"

# 2) main worktree 中合入（应为 fast-forward）
cd ..\website-unit
git merge --ff-only agent/codex-api

# 3) 两个 agent worktree 各自快进到该基线
cd ..\my-project-codex ; git merge --ff-only main
cd ..\my-project-claude ; git merge --ff-only main
```

完成后，两个 VS Code 窗口分别打开对应 worktree，把 docs/collab/PROMPT_CODEX.md
和 docs/collab/PROMPT_CLAUDE.md 的内容作为首条消息发给各自 agent 即可。

## 6. 文件清单

- `AGENTS.md` — 协作总规则 + 文件归属表（冻结）
- `CLAUDE.md` — 指针文件，指向 AGENTS.md，不复制内容，防止分叉
- `docs/collab/PLAN.md` — 本文档
- `docs/collab/CONTRACT.md` — 接口契约（冻结）
- `docs/collab/PROMPT_CODEX.md` — 发给 Codex 的提示词
- `docs/collab/PROMPT_CLAUDE.md` — 发给 Claude 的提示词
- `docs/collab/MERGE.md` — 人类合并与验收手册