# AGENTS.md — SiteUnit 双 Agent 协作规则（本文件冻结，禁止任何一方单方修改）

> 本文件是 Codex 与 Claude 在本仓库协作时的最高规则。需要修改本文件、
> CLAUDE.md 或 docs/collab/CONTRACT.md 时，必须先停止工作并通知人类，
> 由人类在 main 上统一修改后再同步，禁止在自己的分支上直接改动。

## 1. 身份与工作区

- 你运行在一个 git worktree 中，当前分支即你的身份：
  - `agent/codex-api`：后端（FastAPI / SQLite / 迁移 / pytest）
  - `agent/claude-ui`：前端（static/ 下的 Vue ESM / CSS）
- main 的 worktree 在 `../website-unit`，另一个 agent 的 worktree 在
  `../my-project-claude` 或 `../my-project-codex`。
- **不要读写另一个 worktree、不要切换分支、不要操作主仓库、不要执行 merge。**

## 2. 铁律（违反即判定协作失败）

1. 只允许修改「文件归属表」分配给你的文件；表外文件一律不碰，包括格式化、
   重排 import、顺手修 typo 等"看起来无害"的改动。
2. 新建文件也必须落在归属目录内；归属存疑时，停下来在汇报中提问。
3. 以 docs/collab/CONTRACT.md 为唯一接口契约：路径、查询参数、JSON 字段名、
   类型与空值规则严格照做；契约没写的字段不加，契约写了的字段不能少。
4. 发现契约缺陷或需要对方配合：不要自行改契约，列入最终汇报的
   「契约变更建议」，由人类裁决。
5. 不改 requirements.txt、run.py、app/config.py，不安装新依赖。
6. 不提交 data/、.venv/、__pycache__ 等运行时产物；不执行 git push、
   git rebase、git reset --hard 等影响远端或改写历史的命令。
7. 不做与任务无关的重构；保持现有风格（类型标注、英文 docstring、
   面向用户的中文文案、代码标识用英文）。

## 3. 文件归属表（本任务：访问统计仪表盘）

| 路径 | Codex（agent/codex-api） | Claude（agent/claude-ui） |
|---|---|---|
| app/migrations.py | ✏️ 唯一可改 | 🚫 |
| app/db.py | ✏️ 唯一可改 | 🚫 |
| app/schemas.py | ✏️ 唯一可改 | 🚫 |
| app/services.py | ✏️ 唯一可改（如需要） | 🚫 |
| app/main.py | ✏️ 唯一可改（仅挂载 stats 路由） | 🚫 |
| app/api/stats.py | ➕ 新建 | 🚫 |
| tests/test_stats.py | ➕ 新建 | 🚫 |
| static/js/api.js | 🚫 | ✏️ 唯一可改 |
| static/js/app.js | 🚫 | ✏️ 唯一可改 |
| static/css/style.css | 🚫 | ✏️ 唯一可改 |
| static/js/components/stats-panel.js | 🚫 | ➕ 新建 |
| AGENTS.md / CLAUDE.md / docs/collab/* | 🔒 只读冻结 | 🔒 只读冻结 |

✏️ = 可修改且仅此一方可改；➕ = 新建；🚫 = 禁止触碰；🔒 = 只读冻结。

## 4. 工作方式

1. 开工顺序：本文件 → docs/collab/PLAN.md → docs/collab/CONTRACT.md
   → 你自己的 prompt（docs/collab/PROMPT_CODEX.md 或 PROMPT_CLAUDE.md）
   → 任务涉及的现有代码。
2. 小步提交，message 格式：`[codex-api] 中文描述` / `[claude-ui] 中文描述`。
3. 完成后自验（标准见各自 prompt）；不要替对方写代码，不要替对方改文件。
4. 最终汇报必含：改动文件清单、自验结果、契约变更建议（如有）、遗留问题。

## 5. 合并只由人类完成

agent 不执行任何 git merge / git switch 操作。