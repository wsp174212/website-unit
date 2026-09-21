# API 契约 — 访问统计仪表盘（冻结，双方均不得单方修改）

本文件是前后端唯一接口事实来源。字段命名、类型、空值规则照此实现；
未在本文件出现的字段不返回、不依赖。

## 1. 数据采集（埋点）

现有端点行为保持不变：`POST /api/sites/{id}/visit`。
后端在原有「`visit_count += 1`、刷新 `last_visited_at`」基础上，
额外向 `visit_events` 表插入一行（同事务）：

| 列 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | |
| site_id | INTEGER NOT NULL | 外键 → sites(id)，站点删除时级联删除 |
| visited_at | TEXT NOT NULL | UTC ISO8601，精度到秒，如 `2026-09-21T05:53:43+00:00`，与 `_now()` 格式一致 |

站点不存在时仍返回 404（沿用现有错误模型 `{"error":{"code","message"}}`）。

## 2. 聚合接口

```
GET /api/stats/overview?days=30
```

- `days`：可选，整数，白名单取值 `7 | 30 | 90`；缺省为 `30`；
  其他值返回 422（统一错误模型，code 使用参数校验错误）。
- 时间窗口：`[今天 UTC 0 点 - (days-1) 天, 现在]`，共 `days` 个桶，
  无数据的日期也要返回，计数为 0。
- 仅统计未归档站点（`archived = 0`）。若某站点在窗口内被删除，
  其历史事件不再计入任何聚合。
- 缓存：无需特殊缓存头。

### 200 响应体（字段名与结构逐字照此）

```json
{
  "days": 30,
  "total_visits": 128,
  "daily": [
    { "date": "2026-08-23", "count": 2 }
  ],
  "top_sites": [
    {
      "site_id": 3,
      "name": "Claude",
      "url": "https://claude.ai",
      "logo_url": "/logos/abc123.png",
      "visits": 42
    }
  ],
  "groups": [
    { "name": "AI", "count": 60 }
  ]
}
```

字段规则：

| 字段 | 规则 |
|---|---|
| `days` | 回显实际使用的天数（int） |
| `total_visits` | 窗口内访问总数（int），等于 `daily` 各项 count 之和 |
| `daily` | 长度恰好为 `days` 的数组，按 `date` 升序；`date` 为 `YYYY-MM-DD`（UTC 日期） |
| `top_sites` | 按 `visits` 降序、至多 10 条；visits 相同按 `site_id` 升序；`logo_url` 可能为 `null` |
| `groups` | 窗口内有访问的分组，按 `count` 降序；空分组名（未分类）使用 `""`，排在同 count 的最后；各 `count` 之和等于 `total_visits`；`name` 按 `group_name` 精确字符串分组且在返回内唯一，不做大小写折叠或去重 |

空数据时：`total_visits = 0`，`daily` 仍含 `days` 个 0 计数桶，
`top_sites = []`，`groups = []`。

## 3. 前端调用约定

- 前端只通过 `GET /api/stats/overview?days=N` 获取数据，不自行拼 visit 埋点
  （埋点仍走现有 `POST /api/sites/{id}/visit` 流程，本次不改）。
- 前端必须容忍 `logo_url: null`（回退首字母头像，与现有卡片一致）。
- 切换天数时重新请求；请求中展示 loading，失败用现有 toast 显示错误，不白屏。

## 4. 实现提示（非强制，仅供参考）

- 迁移：在 `app/migrations.py` 新增 `m003_visit_events`，版本号 3，
  建表 + 索引 `(visited_at)`、`(site_id, visited_at)`，并在 MIGRATIONS 注册。
- `db.py`：新增 `record_visit_event(conn_or_helper, site_id, ts)`（与计数更新同事务）、
  `stats_overview(days) -> dict`；可在 Python 侧补齐空日期桶。
- 路由：新建 `app/api/stats.py`，在 `app/main.py` 仅增加一行 `include_router`。
- 日期分桶按 visited_at 前 10 字符（`YYYY-MM-DD`）聚合即可。
