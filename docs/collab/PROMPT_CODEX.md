# 提示词 — 发给 Codex（agent/codex-api worktree）

把以下内容作为首条消息发给 Codex：

---

你是本次双 agent 协作验证中的**后端 agent（codex-api）**，当前 worktree 位于
`agent/codex-api` 分支。另一个 agent（claude-ui）正在另一个 worktree 并行开发前端。

请严格按顺序阅读并遵守：

1. `AGENTS.md`（协作铁律与文件归属表，最高优先级）
2. `docs/collab/PLAN.md`（任务全貌）
3. `docs/collab/CONTRACT.md`（接口契约，逐字照做）
4. 本文件

## 你的任务

为「访问统计仪表盘」实现后端，仅限修改/新建归属表中分配给 codex-api 的文件：

- 修改 `app/migrations.py`：新增版本 3 的迁移，建立 `visit_events` 表
  （id / site_id / visited_at，site_id 外键级联删除）及契约要求的索引；
  新安装与从 v2 升级两条路径都要工作。
- 修改 `app/db.py`：
  1. 让 `visit_site` 在同一事务内追加写入一条 `visit_events`；
  2. 新增 `stats_overview(days)`，返回契约定义的 `days / total_visits /
     daily / top_sites / groups`，空日期桶在 Python 侧补齐，
     只统计未归档站点，已删除站点的事件不计入。
- 修改 `app/schemas.py`：为 overview 响应增加 Pydantic 模型并用于路由。
- 新建 `app/api/stats.py`：`GET /api/stats/overview?days=30`，
  days 仅接受 7/30/90（缺省 30，非法值 422，使用现有统一错误模型）。
- 修改 `app/main.py`：**仅**增加一行 stats 路由的 include_router，不做其他改动。
- 新建 `tests/test_stats.py`：覆盖
  - visit 后事件落库且与计数同事务（站点不存在返回 404）；
  - overview 的 daily 长度恰好等于 days、含前导零桶、按日期升序；
  - top_sites 降序、上限 10、并列时 site_id 升序、logo_url 可为 null；
  - groups 降序、空组名 ""；
  - days 白名单（7/30/90 与非法值）；
  - 归档站点不计入；站点删除后其事件不残留/不计入；
  - 旧 v2 schema 升级到 v3 后功能正常（可参考现有迁移测试写法）。

## 自验标准（完成后必须全部执行并汇报结果）

1. `pytest` 全量通过（含你新增的用例）。
2. 用临时数据手动验证：`python run.py --port 9011` 启动后，连续调用几次
   `POST /api/sites/{id}/visit`，再请求
   `GET /api/stats/overview?days=7`，确认 JSON 字段名/结构与契约逐字一致；
   验证完成后停止服务，不留下 data/ 改动。
3. `git status` 确认只改了归属表内文件，且未包含 data/、__pycache__ 等产物。
4. 提交：使用 `[codex-api]` 前缀，可分多个小提交。

## 边界

- 不碰任何 `static/` 文件，不碰 AGENTS.md/CLAUDE.md/docs/collab/*。
- 不改 requirements.txt、run.py、config.py，不加依赖。
- 契约有问题不要自己改，写进最终汇报的「契约变更建议」。
- 不执行 git merge / git switch / push / rebase。

最终请汇报：改动文件清单、提交列表、pytest 结果、手动验证结果、
契约变更建议（如有）、遗留问题。