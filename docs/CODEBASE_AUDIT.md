# SiteUnit 代码库审计

审计时间：2026-08-31
审计基线：commit `9162b48`（初始提交）

本文档是对 SiteUnit 初始代码库的完整审计，用于指导后续渐进式重构与功能扩展。
原则：理解现有实现 → 小步重构 → 加测试 → 加能力，不机械覆盖。

---

## A. 当前架构

### 启动流程

1. `run.py` 解析 `--host/--port/--reload`，调用 `uvicorn.run("app.main:app", ...)`。
2. 导入 `app.main` 触发模块级代码：定义 `STATIC_DIR`、创建 `LOGO_DIR` 目录、`app.mount("/logos", ...)`、`app.mount("/static", ...)`。
3. FastAPI `lifespan` 在启动时执行 `db.init_db()`（`CREATE TABLE IF NOT EXISTS sites`）并 `LOGO_DIR.mkdir`。
4. 根路由 `/` 返回 `static/index.html`。

### FastAPI 初始化过程

- 单一 `app = FastAPI(title="SiteUnit", lifespan=lifespan)`。
- 无路由分组（全部端点写在 `main.py`）。
- 无异常处理器（直接 `raise HTTPException`，返回 FastAPI 默认 `{"detail": "..."}`）。
- 无 CORS、无鉴权、无依赖注入。
- 静态资源在模块导入时挂载，因此 `LOGO_DIR` 必须在导入时已存在（否则 `StaticFiles` 抛 `RuntimeError`——已踩过此坑并修复为导入时 `mkdir`）。

### API 路由

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/sites` | 列出全部站点（按 `grp, created_at, id` 排序） |
| POST | `/api/sites` | 新建站点：normalize URL → 抓取标题+logo → 入库 |
| PUT | `/api/sites/{id}` | 更新字段；改 URL 或勾选 `refetch_logo` 时重抓 logo |
| POST | `/api/sites/{id}/refetch-logo` | 仅重抓 logo |
| DELETE | `/api/sites/{id}` | 删除站点并清理 logo 文件 |
| GET | `/` | 返回前端 `index.html` |
| (mount) | `/static/*` | 前端静态资源 |
| (mount) | `/logos/*` | logo 图片 |

### SQLite 调用

- `app/db.py` 用标准库 `sqlite3`，每次操作新建连接（`with _connect() as conn`），靠上下文管理器在块结束时 commit。
- 未启用 `WAL`、`busy_timeout`、`foreign_keys`。
- `update_site` 用 `dict` 动态拼 `UPDATE ... SET k=?`，白名单固定为 `name/url/description/grp/logo`。
- 无连接池、无事务显式控制、无迁移系统。

### Logo 抓取流程

`app/logos.py::fetch_site_meta(client, url)`：

1. `GET url`；若 2xx 且 `text/html`，缓存 `page_html`。
2. 解析标题：`<title>` → `og:site_name` → hostname。
3. 候选图标：页面内 `<link rel=icon/shortcut icon/apple-touch-icon/...>` + `og:image`，按优先级排序后去重。
4. 依次下载候选（`_try_download_image`），第一个成功即返回。
5. 回落：`<根>/favicon.ico` → DuckDuckGo 图标服务 → Google `s2/favicons`。
6. 返回 `{title, logo: bytes|None, ext: str|None}`，网络失败不抛异常。

### 静态资源服务

- `/static` 指向项目根 `static/`（`index.html`、`css/`、`js/`、`vendor/vue.global.prod.js`）。
- `/logos` 指向 `data/logos/`（运行时创建）。
- 无缓存头控制、无 SPA fallback（只有单页 `/`）。

### Vue 初始化

- `index.html` 引入本地 `vue.global.prod.js`（full build，含编译器，支持 in-DOM 模板）。
- `app.js` 用 `createApp({...}).mount('#app')`，Options API。
- 模板即 `#app` 内的 HTML（`v-cloak` 防闪烁）。

### 页面状态管理

- `data()`: `sites`, `loading`, `search`, `busyIds: Set`, `toast`, `modal`。
- `computed`: `filtered`（按 `search` 模糊匹配 name/url/description/grp）、`groups`（按 `grp` 分组，"未分类"置后）、`allGroupNames`。
- 无持久化前端偏好（主题/密度/排序方式均未保存）。
- `busyIds` 用 `new Set(this.busyIds)` 手动触发响应式。

### API 调用（前端）

- `api(path, options)`：`fetch('/api'+path)`，非 2xx 读 `body.detail` 抛 `Error`。
- 所有动作（load/save/refetch/delete）直接 `await api(...)`，无并发去重、无乐观更新。

### 数据模型

`Site`（DB row，对应 `app/db.py` 的表）：

| 列 | 类型 | 约束 |
|---|---|---|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT |
| name | TEXT | NOT NULL |
| url | TEXT | NOT NULL |
| description | TEXT | NOT NULL DEFAULT '' |
| grp | TEXT | NOT NULL DEFAULT '' |
| logo | TEXT | NOT NULL DEFAULT '' |
| created_at | TEXT | NOT NULL |
| updated_at | TEXT | NOT NULL |

前端额外字段：`logo_url`（`/logos/{logo}` 或 `null`）、`_logoFailed`（前端运行时态）。

---

## B. 当前数据库 schema

- 表：`sites`（见上表）。
- 索引：无。
- 外键：无。
- 触发器：无。
- 版本表：无（无迁移系统）。

---

## C. 当前 API

见上「API 路由」表。请求/响应均为裸 dict，无 Pydantic 响应模型，OpenAPI 文档字段缺失。

---

## D. 当前存在的问题

### Bug / 正确性

- **D1（P0，安全）SSRF 无防护**：`fetch_site_meta` 会主动 `GET` 用户输入的任意 URL，无 scheme 白名单、无私网 IP 拦截、无 DNS 重绑定防护。本机/内网/云元数据（`169.254.169.254`）可被探测。这是项目最严重的问题。
- **D2（P0，正确性）`_candidate_icon_urls` 仍含死代码**：审计前已清理掉一段混乱表达式，但 `_ICON_REL_PATTERN` 正则已删，逻辑现以字符串比较为准——需确认无残留。
- **D3（P1）URL normalize 过弱**：`normalize_url` 仅在无 scheme 时补 `https://`。`example.com`、`https://example.com/`、`https://example.com/#abc` 被当作不同站点，无去重，可重复添加。
- **D4（P1）`fetch_site_meta` 用 `resp.url` 在异常分支可能未定义**：`except` 后 `page_html=None` 走 else 分支不用 `resp`，但 `if page_html is not None` 分支用 `str(resp.url)`——若 `GET` 返回非 HTML（`page_html` 仍为 `None`）则走 else，安全；若 HTML 解析失败……目前路径下 `resp` 已定义。脆弱，应显式。
- **D5（P1）logo 无内容校验**：只按 content-type / magic bytes 推断扩展名，不验证是否真为可解码图像；HTML 错误页若 magic bytes 碰巧命中（如以 `\x00\x00` 开头）会被当成 ico 保存。
- **D6（P1）logo 文件名随机 uuid**：每次重抓生成新文件，旧文件删除依赖调用方记得 `_remove_logo_file`；refetch 路径已处理，但缺乏 GC，长期可能残留孤儿。
- **D7（P2）`update_site` 白名单硬编码**：新增字段需同步改两处（`db.update_site` 白名单 + `main.py` 字段映射），易漏。

### Race condition

- **R1（P1）logo 重抓竞态**：`refetch-logo` 先下载新 logo、再删旧、再 update。若并发两次 refetch 同一站点，可能删掉刚写入的新文件。单用户低概率，但应原子化。
- **R2（P1）SQLite 写并发**：默认 journal mode，多请求并发写可能 `database is locked`。未设 `busy_timeout`，失败即抛。

### Security

- **S1（P0）SSRF**（见 D1）。
- **S2（P1）`verify=False`**：`_fetch_meta_for`/`_fetch_logo_for` 关闭 TLS 验证，易受中间人。本机自用可接受，但应可配置且默认更安全。
- **S3（P2）无鉴权**：`--host 0.0.0.0` 暴露局域网后任何人可读写。文档应明示风险，可选密码保护。
- **S4（P2）logo 文件名清理仅按正则**：`_remove_logo_file` 用 `[0-9a-f]{32}\.[a-z0-9]+` 防越权删除，OK；但导入/备份恢复路径尚未存在，需提前设计 path traversal 防护。

### Fragile / 重复 / 缺失

- **F1（P1）`httpx.AsyncClient` 在每个请求新建**：`_fetch_meta_for`、`_fetch_logo_for` 各开一个 client，未复用连接池。
- **F2（P2）`verify=False` 与超时 12s 是魔法常量**，散落两处。
- **F3（P2）前端 `busyIds` 响应式触发靠手动 `new Set`**，易漏。
- **F4（P2）错误提示依赖后端异常字符串**（前端 `body.detail` 直接展示），未结构化。
- **F5（P3）CSS 重复**：多个 `color-mix` / `box-shadow` 内联，无 design tokens 层。
- **F6（P2）无日志系统**：出错只在 HTTP 响应里，服务端无记录。
- **F7（P2）无测试**：零回归保护。
- **F8（P2）无迁移系统**：加字段只能改 `CREATE TABLE`，旧库不升级。
- **F9（P2）`StaticFiles` 在导入时挂载**：测试时无法替换 data 目录路径（路径硬编码 `Path(__file__).../data`）。
- **F10（P3）可访问性**：icon-only 按钮仅有 `title` 无 `aria-label`；modal 无 focus trap；`tabindex=0` 的 card 无 `role`/`aria`。

### Blocking IO / 性能

- **P1（P2）元数据抓取在请求路径同步执行**：`POST /api/sites` 阻塞等抓取，前端"抓取中…"可达数秒，超时无上限控制。
- **P2（P3）`list_sites` 无分页**：站点上千后一次性返回。

### Frontend state / 可访问性 / CSS

见 F3、F5、F10。另：主题仅靠 `prefers-color-scheme`，无手动切换、刷新有闪烁风险（实际上当前无内联主题脚本，首屏即应用系统主题，尚可，但加手动切换后需防闪）。

---

## E. 技术债务（P0–P3）

### P0（必须先修，正确性/数据安全/安全）

1. **SSRF 防护 + 安 URL fetcher**（D1/S1）——独立 `app/fetcher.py`，scheme 白名单、私网拦截、DNS 重绑定防护、超时/重定向/响应体上限。
2. **迁移系统**（F8）——`schema_version` + 幂等迁移 + 迁移前备份，为扩字段铺路。
3. **SQLite 可靠性**（R2）——WAL、`busy_timeout`、`foreign_keys`、合理连接生命周期。
4. **回归测试体系**（F7）——CRUD/校验/元数据(mock)/db/迁移/SSRF。
5. **配置系统**（F9/F2）——env+CLI 优先级，data 目录可覆盖（解锁测试）。

### P1（高价值，紧随其后）

6. URL normalize + 去重（D3）。
7. 统一错误模型（F4）。
8. Pydantic 请求/响应模型 + OpenAPI（C/F4）。
9. logo 内容校验 + 稳定命名 + GC（D5/D6）。
10. 元数据抓取重构为清晰 pipeline（D4/F1）。
11. 日志系统（F6）。
12. 扩展数据模型（tags/favorite/pinned/sort/visit/health/archived）。

### P2（产品力）

13. 访问统计 + 排序、收藏置顶、标签、高级搜索、命令面板、键盘导航、批量、归档、导入导出、备份恢复、健康检查、死链页、批量刷新、主题、密度、响应式、toast、a11y、CLI。

### P3（打磨）

14. PWA、性能文档、代码结构进一步拆分、前端 state 审计、dead code 清理。
