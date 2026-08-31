# SiteUnit 开发路线图

基于 [代码库审计](./CODEBASE_AUDIT.md) 的问题分级，按 P0 → P1 → P2 → P3 推进。
原则：每一步都跑测试、检 regression、自 review、更新本文档。

任务清单见会话内 TaskList（6 个里程碑）。本文档跟踪交付状态。

---

## M1 — 基础设施与回归保护（P0 + 关键 P1）

> 不叠加任何产品功能，先把"安全、可靠、可测"的底座搭好。

- [x] 配置系统 `app/config.py`（CLI > env > 默认；`SITEUNIT_*` 环境变量；data 目录可覆盖）
- [x] 日志系统（`logging`，分级，不记敏感信息）
- [x] 统一错误模型 `app/errors.py`（`{"error":{"code","message"}}` + FastAPI handler）
- [x] URL normalize + 去重 `app/urlnorm.py`
- [x] 安全 fetcher `app/fetcher.py`（scheme 白名单、SSRF 拦截、DNS 重绑定防护、超时/重定向/响应体上限、可选 `ALLOW_PRIVATE_NETWORK_FETCH`）
- [x] 元数据 pipeline `app/metadata.py`（normalize→fetch HTML→parse→候选图标排序→下载→校验→缓存）
- [x] logo 服务 `app/logos.py`（内容校验、稳定命名 url-hash、GC、删除清理）
- [x] 迁移系统 `app/migrations.py`（`schema_version`、幂等、迁移前备份、失败不损坏）
- [x] SQLite 可靠性（WAL、`busy_timeout`、`foreign_keys`、连接生命周期）
- [x] Pydantic schema `app/schemas.py`（请求/响应模型，OpenAPI）
- [x] 测试体系（pytest + httpx MockTransport + temp DB）：CRUD / 校验 / 元数据 mock / db / 迁移安全 / urlnorm / SSRF / edge

## M2 — 扩展数据模型（P1）

- [x] 迁移 002：`normalized_url`、`group_name`(rename grp)、`logo_path`(rename logo)、`logo_source`、`favorite`、`pinned`、`sort_order`、`last_visited_at`、`visit_count`、`last_checked_at`、`status`、`http_status`、`archived`
- [x] `tags` + `site_tags` 关联表
- [x] 索引：`normalized_url`、`group_name`、`sort_order`、`archived`、`status`
- [x] 迁移安全测试：旧 schema fixture → 升级 → 数据全在 + 新字段 + CRUD 正常

## M3 — 产品功能后端（P2）

- [x] 访问统计 `POST /api/sites/{id}/visit` + 排序参数（recent/most/added/name/custom）
- [x] 收藏 / 置顶 toggle
- [x] 标签 CRUD + `?tag=` 过滤
- [x] 高级搜索 token 语法（`group:` `tag:` `fav:` `pinned:`）
- [x] 批量操作（删除/移动分组/加标签/归档/刷新元数据，带确认）
- [x] 归档（archive/restore，归档视图）
- [x] 导入导出 JSON（merge/replace）/ CSV / 浏览器书签 HTML
- [x] 备份 / 恢复 zip（path traversal 防护、恢复前自动备份）
- [x] 健康检查（HEAD/GET，并发上限，记录 status/http_status）
- [x] 死链页 + 批量刷新元数据（semaphore）

## M4 — 前端重写（P2）

- [x] ESM Vue build，JS 拆分模块（api/utils/components）
- [x] design tokens，主题 light/dark/system（无闪烁），密度 comfortable/compact
- [x] 命令面板 Ctrl/Cmd+K（搜索/打开/添加/主题/导出/设置），↑↓ Enter Esc
- [x] 键盘导航（Tab 顺序、Enter 打开、Esc 关闭、`/` 聚焦、`a` 快速添加）
- [x] 批量选择模式 + 批量操作工具条
- [x] 标签 UI（编辑、过滤）
- [x] 高级搜索 token 高亮
- [x] 归档视图、死链视图
- [x] 导入/导出/备份 UI（书签导入预览）
- [x] toast 统一（success/warning/error），loading/进度
- [x] 响应式（1920→390px），手机可用
- [x] 可访问性（aria-label、focus trap、对比度、icon 按钮可访问名）

## M5 — CLI + 文档 + 验证（P2/P3）

- [x] `app/cli.py`：backup / cleanup-logos / check-sites / refresh-metadata / db-info
- [x] docs：ARCHITECTURE / SECURITY / PERFORMANCE
- [x] README 重写
- [x] 全量测试 + 浏览器验证 + 最终提交

## M6 — 后续（P3，本轮回滚不深做）

- [ ] PWA（manifest+SW，静态缓存与 API 缓存分离）
- [ ] 前端 state 深度审计 / 进一步拆模块
- [ ] 性能基准（生成 `docs/PERFORMANCE.md` 基线数据）
- [ ] 可选密码保护（`--host 0.0.0.0` 场景）
