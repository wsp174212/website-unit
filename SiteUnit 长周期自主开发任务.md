# SiteUnit 长周期自主开发任务

你现在作为 SiteUnit 项目的 Principal Engineer、产品工程师和代码所有者，对当前代码库进行一次完整的理解、评审、规划、开发、测试与持续改进。

不要只完成一个孤立的小功能。

你的目标是：

> 将 SiteUnit 从一个简单的个人网站导航页，逐步完善成一个“本地优先、零依赖部署、快速、可靠、精致”的个人互联网导航与工作台，同时保持项目简单、易维护、易迁移。

---

# 一、项目背景

SiteUnit 是一个个人自用的网站聚合与导航工具。

用户只需要输入 URL：

1. 后端自动访问网站；
2. 自动解析网页标题；
3. 自动识别 favicon / icon；
4. 自动下载并缓存 logo；
5. 保存到 SQLite；
6. 前端自动生成站点卡片；
7. 用户通过分组、搜索等方式管理大量日常网站。

当前技术栈：

- Python
- FastAPI
- SQLite
- Vue 3
- Vue 使用本地 vue.global.prod.js
- 无 npm
- 无 Node.js
- 无前端构建步骤
- 静态 HTML / CSS / JavaScript
- 本地单机优先
- data/sites.db 保存数据
- data/logos/ 保存图标

当前运行方式：

```bash
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe run.py
```

支持：

```bash
--port
--reload
--host
```

当前主要能力：

- 添加站点
- 根据 URL 自动获取网页标题
- 自动获取 favicon/logo
- 编辑站点
- 删除站点
- 重抓 logo
- 分组
- 搜索
- SQLite 持久化
- logo 本地缓存
- 局域网访问

---

# 二、核心产品原则

整个开发过程中必须保持以下原则。

## 1. Local First

SiteUnit 首先是个人本地工具，而不是 SaaS。

不能为了所谓“架构先进”无意义地引入：

- Redis
- PostgreSQL
- Kafka
- 微服务
- Kubernetes
- Node.js
- npm
- webpack
- Vite
- React

除非确实存在无法解决的问题，否则保持：

FastAPI + SQLite + 原生 Vue 3。

---

## 2. Zero Build

必须继续保证：

前端无需 Node.js。

Clone 项目、安装 Python dependencies 后应该可以直接运行。

---

## 3. Portable

用户迁移电脑时最好只需要复制：

```text
data/
```

即可恢复全部重要数据。

不要把关键用户状态散落到不可迁移的位置。

---

## 4. Progressive Enhancement

不要一次重写整个项目。

优先：

理解现有代码 → 小步重构 → 加测试 → 添加能力。

每一次修改都应尽可能保证旧功能仍然工作。

---

## 5. Useful over Fancy

不要为了展示技术而增加复杂度。

每增加一个功能都问：

- 用户是否真的会使用？
- 是否降低导航成本？
- 是否降低整理成本？
- 是否提高可靠性？
- 是否提高数据安全性？
- 是否让几十甚至几百个站点更容易管理？

---

# 三、第一阶段：完整代码库审计

首先不要立即修改代码。

完整阅读整个项目。

至少检查：

```text
run.py
app/
static/
requirements.txt
data schema
.gitignore
README
```

如果存在其他文件，也全部理解。

输出：

```text
docs/CODEBASE_AUDIT.md
```

内容包括：

### A. 当前架构

描述：

- 启动流程
- FastAPI 初始化过程
- API 路由
- SQLite 调用
- logo 抓取流程
- 静态资源服务
- Vue 初始化
- 页面状态管理
- API 调用
- 数据模型

### B. 当前数据库 schema

列出：

- table
- column
- type
- constraint
- index

### C. 当前 API

建立表格：

| Method | Endpoint | Purpose |
|---|---|---|

### D. 当前存在的问题

寻找：

- bug
- race condition
- security issue
- duplicated code
- fragile code
- missing validation
- poor error handling
- magic constants
- blocking IO
- SQLite concurrency issue
- frontend state inconsistency
- accessibility issue
- CSS scalability issue

### E. 技术债务

按照：

P0 / P1 / P2 / P3

分类。

---

# 四、建立测试体系

在大量开发之前，为现有关键能力建立测试。

优先使用：

```text
pytest
FastAPI TestClient / httpx
temporary SQLite database
temporary logo directory
```

至少测试：

### CRUD

- create site
- read sites
- update site
- delete site

### validation

- empty URL
- malformed URL
- duplicate URL
- unsupported scheme
- very long strings

### metadata fetching

使用 mock HTTP response，不要依赖公网测试。

覆盖：

- HTML title
- favicon
- relative favicon URL
- absolute favicon URL
- og:image
- no icon
- invalid HTML
- redirect
- timeout
- HTTP 404
- HTTP 500

### database

测试：

- initialization
- migration
- duplicate data
- ordering
- concurrent-ish access if relevant

目标：

建立一个可以反复运行的 regression test suite。

---

# 五、数据库 Migration 系统

目前项目仍然较小，但以后字段会持续增加。

不要依赖“如果 column 不存在就临时 ALTER”这类越来越混乱的逻辑。

设计一个轻量 migration 系统。

例如：

```text
schema_version
migration_001
migration_002
migration_003
```

要求：

- 不依赖 Alembic 也可以
- 保持简单
- 自动升级旧数据库
- migration 必须幂等或受到版本控制
- migration 前最好创建可恢复备份
- migration 失败不能默默损坏 DB

编写 migration tests。

---

# 六、扩展 Site 数据模型

在不破坏已有数据的情况下，评估逐步加入：

```text
id
url
normalized_url
name
description
group_name
tags
logo_path
logo_source
favorite
pinned
sort_order
created_at
updated_at
last_visited_at
visit_count
last_checked_at
status
http_status
archived
```

不要机械地全部加入。

根据实际代码设计合理 schema。

注意：

SQLite index 应当合理建立，例如：

- normalized_url
- group
- sort_order
- archived

---

# 七、URL Normalize 与去重

实现稳定的 URL normalization。

处理：

```text
example.com
https://example.com
https://example.com/
https://example.com/#abc
```

判断哪些应该视为同一个站点。

考虑：

- scheme
- trailing slash
- fragment
- hostname lowercase
- default ports
- query string

必须避免过度 normalize 导致不同 URL 被错误合并。

建立单独测试。

---

# 八、安全的 URL Fetcher

这是项目非常重要的一部分。

当前 SiteUnit 会根据用户输入主动访问 URL，因此需要系统检查 SSRF 与网络安全问题。

建立独立模块，例如：

```text
app/fetcher.py
```

或者根据当前架构选择更合理名称。

需要考虑：

### URL scheme

默认仅允许：

```text
http
https
```

拒绝：

```text
file:
ftp:
data:
javascript:
```

### SSRF

考虑阻止访问：

```text
127.0.0.0/8
0.0.0.0
localhost
::1
169.254.0.0/16
private IPv4 ranges
private IPv6 ranges
link-local
```

但是：

因为 SiteUnit 支持局域网导航，所以不要粗暴破坏合法 LAN website 使用能力。

设计一个配置：

```text
ALLOW_PRIVATE_NETWORK_FETCH
```

默认值根据项目本地工具属性做合理选择，并写清楚风险。

重点防止：

DNS resolution → redirect → private IP

绕过检查。

### HTTP Client

设置：

- connect timeout
- read timeout
- redirect limit
- max response size
- User-Agent

不要无限下载网页。

metadata fetch 通常只需要有限 HTML。

---

# 九、Metadata 抓取器重构

设计一个清晰 pipeline，例如：

```text
URL
 ↓
normalize
 ↓
fetch HTML
 ↓
parse metadata
 ↓
candidate icons
 ↓
rank icon candidates
 ↓
download
 ↓
validate image
 ↓
cache
```

标题优先级可以研究并设计：

```text
og:title
<title>
hostname
```

描述可以考虑：

```text
og:description
meta[name=description]
```

favicon candidate：

```text
apple-touch-icon
icon
shortcut icon
mask-icon
og:image
/favicon.ico
```

建立 candidate ranking。

---

# 十、Logo 系统增强

当前 logo 抓取是产品体验的重要组成部分。

完善：

### logo validation

检查：

- Content-Type
- 文件大小
- image 是否真的可解析
- 非 HTML 假图片
- 超大图片

### 缓存

logo 文件尽量使用稳定命名：

例如 URL hash。

避免：

- 重复下载
- 文件名冲突
- 删除站点后垃圾文件永久增长

### Garbage Collection

实现：

查找未被数据库引用的 logo 文件并清理。

可以：

- 提供 API
- 或启动时可选执行
- 或 maintenance command

---

# 十一、站点访问统计

用户点击站点时记录：

```text
visit_count
last_visited_at
```

注意不能明显降低点击跳转速度。

增加视图：

- 最近访问
- 常用站点
- 最近新增

首页可以支持排序：

```text
自定义
最近访问
访问最多
最近添加
名称
```

---

# 十二、收藏与置顶

实现：

```text
favorite
pinned
```

设计合理 UI。

不要让卡片按钮越来越拥挤。

可以考虑：

hover menu / more menu。

---

# 十三、拖拽排序

增加：

- group 顺序
- site 顺序

优先考虑无需 npm 的实现方式。

如果需要小型 vendor library，可以：

- 本地存储 vendor JS
- 不依赖 CDN
- 不依赖 npm build

也可以评估 HTML5 Drag & Drop 是否足够。

后端保存 sort_order。

必须考虑：

删除、移动、插入之后 sort_order 的一致性。

---

# 十四、标签系统

现在已有 group。

Group 与 Tag 是不同概念。

例如：

```text
Group:
AI

Tags:
coding
llm
agent
daily
```

支持：

- 一个 site 一个 group
- 一个 site 多个 tag

设计 SQLite schema。

不要用非常难维护的逗号字符串，如果关联表更合理就使用关联表。

支持：

点击 tag 过滤。

---

# 十五、高级搜索

当前搜索继续增强。

支持：

```text
name
domain
url
description
group
tag
```

可以考虑轻量 token syntax：

```text
group:AI
tag:coding
fav:true
```

例如：

```text
claude tag:ai
```

不要过度工程化成完整搜索引擎。

优先保持浏览器端快速搜索。

如果站点数量达到几千，再评估 SQLite FTS5。

---

# 十六、Command Palette

增加快捷键：

```text
Ctrl/Cmd + K
```

打开 Command Palette。

至少支持：

- 搜索站点
- 打开站点
- 添加站点
- 切换主题
- 导出数据
- 打开设置

键盘上下选择：

```text
↑
↓
Enter
Esc
```

继续保留：

```text
/
```

focus 搜索。

目标是让高级用户尽量不用鼠标。

---

# 十七、Keyboard Navigation

实现：

- Tab 顺序合理
- Enter 打开
- Esc 关闭 Modal
- Ctrl/Cmd + K
- /
- 快速添加

避免 shortcut 在 input / textarea 输入时误触发。

---

# 十八、批量操作

当站点数量达到几十甚至几百后，一个个编辑效率很低。

增加 selection mode。

支持：

- 批量删除
- 批量移动 group
- 批量添加 tag
- 批量 archive
- 批量 refresh metadata

所有 destructive operation 必须有明确确认。

---

# 十九、Archive

增加归档机制。

删除与归档区分：

删除：
真正删除。

Archive：
暂时从正常视图隐藏。

提供：

```text
Archived Sites
```

视图，可以恢复。

---

# 二十、Import / Export

这是 SiteUnit 非常重要的能力。

## JSON Export

导出完整数据：

```json
{
  "version": 1,
  "exported_at": "...",
  "sites": [],
  "groups": [],
  "tags": []
}
```

需要 schema version。

## JSON Import

支持：

- merge
- replace

replace 必须二次确认。

## CSV

提供 CSV 导入导出，至少：

```text
url
name
description
group
tags
```

---

# 二十一、浏览器书签导入

实现 Chrome / Edge / Firefox 常见 HTML bookmarks export 格式解析。

解析：

```html
<DL>
<DT>
<A HREF="">
```

将 folder 转换为 SiteUnit group。

处理：

- duplicate
- nested folders
- invalid URL
- empty folder
- description if available

导入前显示 preview：

```text
发现 147 个站点
新增 103
重复 39
无效 5
```

再确认导入。

---

# 二十二、Backup / Restore

实现稳定备份。

至少备份：

```text
sites.db
logos/
```

可以考虑生成：

```text
siteunit-backup-YYYYMMDD-HHMM.zip
```

同时提供恢复机制。

恢复时：

- validate archive
- 防止 path traversal
- backup current data before replace

---

# 二十三、站点健康检查

增加 Health Check。

对站点进行 HEAD / GET 检测。

记录：

```text
last_checked_at
status
http_status
```

分类：

```text
healthy
redirect
unreachable
timeout
error
```

UI 不要过度明显。

只有异常站点显示提示即可。

提供：

“检查全部站点”。

注意：

不要启动大量并发导致机器或网络压力。

设置 concurrency limit。

---

# 二十四、Broken Links 页面

增加维护视图：

```text
Broken / Unreachable Sites
```

帮助用户清理长期失效的网站。

支持：

- retry
- edit URL
- archive
- delete

---

# 二十五、批量刷新 Metadata

提供：

```text
Refresh metadata
```

允许：

- single site
- group
- selected sites
- all sites

处理 concurrency：

例如 semaphore。

不要一次发出几百个 HTTP 请求。

记录失败结果。

---

# 二十六、UI Design System

检查当前 CSS。

建立轻量 design tokens：

```css
--bg
--surface
--text
--text-secondary
--border
--radius
--shadow
--spacing
--accent
```

不要引入 Tailwind。

继续保持纯 CSS。

整理：

- button
- input
- modal
- card
- badge
- menu
- toast

减少重复 CSS。

---

# 二十七、主题

实现：

```text
Light
Dark
System
```

使用：

```text
prefers-color-scheme
```

保存用户设置。

避免页面刷新出现明显主题闪烁。

---

# 二十八、Card Density

增加：

```text
Comfortable
Compact
```

可选再提供：

```text
List
Grid
```

但不要让页面复杂。

---

# 二十九、响应式设计

重点测试：

```text
1920px
1440px
1366px
1024px
768px
430px
390px
```

尤其因为项目支持：

```bash
--host 0.0.0.0
```

手机访问应该真正可用。

检查：

- modal
- card
- menu
- touch target
- search
- navigation
- overflow

---

# 三十、Toast / Error UX

不要：

```text
alert()
```

作为主要交互。

建立统一 toast。

包括：

```text
success
warning
error
```

例如：

```text
站点添加成功
Logo 抓取失败，已使用默认图标
网络超时
URL 已存在
```

---

# 三十一、Loading / Optimistic UI

完善：

- 添加站点 loading
- refresh logo loading
- bulk operation progress
- metadata fetch progress

添加站点时不要让 UI 看起来卡死。

可以考虑：

先创建站点 → 后台抓 metadata。

但必须权衡复杂度。

如果当前同步抓取已经足够可靠，则不要为了“异步”而复杂化。

---

# 三十二、Accessibility

系统检查：

- aria-label
- keyboard navigation
- focus visible
- color contrast
- modal focus trap
- screen reader label
- icon-only button accessible name

---

# 三十三、PWA 可行性

评估：

SiteUnit 是否适合成为 PWA。

如果成本合理，实现：

```text
manifest.json
service-worker.js
icons
installable app
```

但是：

不要 aggressively cache API。

避免用户看到旧数据。

静态资源缓存与 API 数据缓存分开。

---

# 三十四、配置系统

整理配置。

例如：

```text
SITEUNIT_HOST
SITEUNIT_PORT
SITEUNIT_DATA_DIR
SITEUNIT_ALLOW_PRIVATE_NETWORK_FETCH
SITEUNIT_FETCH_TIMEOUT
SITEUNIT_MAX_HTML_SIZE
```

支持：

command line > environment > default

明确优先级。

保持 run.py 简单。

---

# 三十五、日志系统

建立 Python logging。

区分：

```text
INFO
WARNING
ERROR
DEBUG
```

记录：

- startup
- DB migration
- metadata fetch
- logo fetch
- health check
- exception

不要记录敏感信息。

避免刷屏。

---

# 三十六、统一 Error Model

API 返回统一结构。

例如：

```json
{
  "error": {
    "code": "SITE_ALREADY_EXISTS",
    "message": "..."
  }
}
```

前端根据错误 code 给出友好提示。

不要让 frontend 依赖 backend exception string。

---

# 三十七、API Schema

检查 Pydantic models。

确保：

request / response model 清晰。

避免直接把 sqlite row 原样暴露。

利用 FastAPI OpenAPI 自动文档。

---

# 三十八、性能检查

虽然这是个人项目，但进行合理优化。

检查：

- N+1 query
- unnecessary DB query
- SQLite index
- logo loading
- frontend render
- duplicate API request
- blocking network I/O

不要做无意义 benchmark。

但可以生成：

```text
docs/PERFORMANCE.md
```

记录关键发现。

---

# 三十九、SQLite Reliability

检查：

```text
WAL mode
busy_timeout
foreign_keys
transaction
connection lifecycle
```

根据实际使用场景决定是否启用。

不要 blindly copy configuration。

写清楚原因。

---

# 四十、Maintenance CLI

扩展 run.py 或建立独立 CLI。

例如：

```bash
python run.py
python run.py --port 9000

python -m app.cli backup
python -m app.cli cleanup-logos
python -m app.cli check-sites
python -m app.cli refresh-metadata
python -m app.cli db-info
```

保持命令设计简单。

---

# 四十一、README 重写

随着项目能力增加，更新 README。

至少包含：

- Screenshot placeholder
- Features
- Installation
- Usage
- Keyboard shortcuts
- Backup
- Import/export
- LAN usage
- Security notes
- Directory layout
- Troubleshooting

不要写营销废话。

---

# 四十二、Architecture 文档

创建：

```text
docs/ARCHITECTURE.md
```

描述：

```text
Browser
 ↓
FastAPI
 ↓
Service layer
 ↓
SQLite

Metadata Fetcher
 ↓
HTTP
 ↓
Website
```

解释模块职责和 dependency direction。

---

# 四十三、Security 文档

创建：

```text
docs/SECURITY.md
```

重点说明：

- SiteUnit 默认使用场景
- LAN exposure 风险
- SSRF
- untrusted HTML
- favicon download
- XSS
- import file
- backup restore
- path traversal
- authentication absence

---

# 四十四、不要盲目增加登录系统

当前 SiteUnit 是：

个人、本地优先。

如果只绑定：

```text
127.0.0.1
```

不一定需要登录。

如果：

```text
--host 0.0.0.0
```

则需要明确提示：

服务暴露给局域网。

可以研究：

optional password protection。

但是必须保持默认使用简单。

---

# 四十五、代码结构重构

如果目前：

```text
main.py
```

越来越庞大，可以适度拆分。

例如：

```text
app/
    main.py
    config.py
    db.py
    models.py
    schemas.py
    services/
        sites.py
        metadata.py
        logos.py
        backup.py
    routes/
        sites.py
        maintenance.py
```

但只有当当前规模值得时才拆。

不要为了目录好看而制造抽象。

---

# 四十六、Dead Code / Dependency Audit

检查：

- unused imports
- unused functions
- duplicate helpers
- obsolete CSS
- unused JS
- unnecessary Python dependencies

能删除就删除。

---

# 四十七、Frontend State Review

当前 Vue 是无 build 架构。

审计：

- reactive state
- computed
- watchers
- API calls
- modal state
- race condition

如果 JS 已经非常大，可以合理拆：

```text
static/js/api.js
static/js/app.js
static/js/utils.js
```

通过普通：

```html
<script>
```

或 ES module。

不要引入 bundler。

---

# 四十八、数据迁移安全测试

建立这样一个测试：

1. 创建旧版本数据库 fixture；
2. 放入真实格式数据；
3. 启动新版 SiteUnit；
4. 自动 migration；
5. 验证原数据完全存在；
6. 验证新增字段；
7. 验证 CRUD 正常。

这是非常重要的 regression test。

---

# 四十九、真实 Edge Cases

主动寻找并处理：

```text
URL 没有 scheme
IDN domain
中文 domain
超长 title
title 含 emoji
favicon 是 SVG
favicon 是 ICO
favicon redirect
favicon 403
favicon URL 包含 query
site redirect HTTP → HTTPS
gzip
brotli
bad TLS cert
invalid UTF-8
GBK website
empty HTML
huge HTML
Cloudflare page
basic auth
localhost site
IP address URL
IPv6 URL
duplicate URL
```

不要为了覆盖而写巨量 hacks。

优先设计健壮、通用的 parser/fetcher。

---

# 五十、最终目标

SiteUnit 最终应该给人这样的感觉：

打开浏览器以后，它是我的个人互联网首页。

我可以：

- 快速找到网站
- 快速打开网站
- 收藏重要网站
- 管理几十或几百个网站
- 看最近使用
- 看常用网站
- 用标签整理
- 用键盘完成大部分操作
- 批量管理
- 找出死链
- 自动抓取漂亮 logo
- 导入浏览器书签
- 备份所有数据
- 换电脑快速恢复

与此同时，它依然：

- 小
- 快
- 本地
- 无 Node
- 无云依赖
- SQLite
- 一条命令启动

---

# 工作方式要求

这是一个长期自主任务。

不要在完成一个很小的步骤之后立即停止并询问我：

“是否继续？”

而是在没有关键产品决策冲突的情况下持续推进。

工作循环：

```text
Inspect
↓
Plan
↓
Implement
↓
Test
↓
Review
↓
Fix
↓
Document
↓
Next improvement
```

每完成一个较大的阶段：

1. 运行相关测试；
2. 检查 regression；
3. 检查 git diff；
4. 自己 review 自己的代码；
5. 修复明显问题；
6. 更新 TODO / roadmap；
7. 继续下一个最高价值任务。

如果发现当前项目已有实现与本 Prompt 不一致：

以“理解现有实现并渐进改进”为优先，

不要机械覆盖现有设计。

---

# 自主决策权限

你可以自主：

- 创建文件
- 修改文件
- 删除明确废弃代码
- 添加测试
- 重构
- 修改 DB schema
- 添加 migration
- 改善 UI
- 添加 API
- 添加文档

但必须：

- 不删除用户数据
- 不破坏旧数据库
- 不引入 Node build requirement
- 不加入不必要的重型基础设施
- 不改变 Local First 核心定位

---

# 开始执行

现在开始：

## Step 1

完整读取代码库。

## Step 2

创建：

```text
docs/CODEBASE_AUDIT.md
```

## Step 3

创建：

```text
docs/ROADMAP.md
```

将问题分为：

```text
P0
P1
P2
P3
```

## Step 4

优先处理：

- correctness
- data safety
- regression tests
- security
- architecture problems

## Step 5

再逐步推进产品功能。

不要只输出计划。

真正修改代码、运行测试、发现问题、继续修改。

尽可能充分利用当前上下文持续推进整个项目。