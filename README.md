# SiteUnit · 本地优先的个人站点导航

打开浏览器就是你的个人互联网首页。填入 URL → 自动抓取标题和 logo →
卡片化展示，分组 / 标签 / 搜索 / 键盘操作，几十上百个站点也能管得清。

Local-first · 零 Node 依赖 · FastAPI + SQLite + Vue 3（无构建）· 一条命令启动。

## 功能

- **添加站点**：只填 URL，标题与 favicon 自动抓取并缓存
- **分组 / 标签**：一个 site 一个分组 + 多标签，点击标签即过滤
- **搜索**：全文 + token 语法 `group:AI tag:coding fav:true pinned:true`
- **收藏 / 置顶**：pinned 卡片在各组内置顶
- **访问统计 + 排序**：最近访问 / 最常访问 / 最近添加 / 名称 / 自定义
- **拖拽排序**：卡片间拖动调整顺序，跨分组移动
- **命令面板**：`Ctrl/Cmd+K` 搜索站点、打开、添加、切换主题、视图切换
- **批量操作**：选择模式 → 批量删除 / 移动分组 / 加标签 / 归档 / 刷新元数据
- **归档 / 死链视图**：归档不删除可恢复；健康检查标记失效站点
- **导入导出**：JSON（merge/replace）/ CSV / 浏览器书签 HTML（带预览）
- **备份恢复**：一键 zip 备份（DB + logos），恢复有路径穿越防护
- **主题**：浅色 / 深色 / 跟随系统，无闪烁；密度 舒适 / 紧凑
- **响应式**：桌面到手机（`--host 0.0.0.0` 后手机可用）
- **安全**：SSRF 防护、scheme 白名单、响应体上限、TLS 可配置

## 安装

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   ·   macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

打开 http://127.0.0.1:8000

## 用法

```bash
python run.py                        # 默认 127.0.0.1:8000
python run.py --port 9000            # 换端口
python run.py --host 0.0.0.0         # 局域网访问（手机可用）
python run.py --reload               # 开发热重载
```

### 键盘快捷键

| 键 | 作用 |
|---|---|
| `Ctrl/Cmd+K` | 命令面板（搜索/打开/添加/主题/视图） |
| `/` | 聚焦搜索框 |
| `a` | 快速添加站点 |
| `s` | 打开设置 |
| `Esc` | 关闭弹窗 / 退出选择 |
| `Enter` | 打开卡片（聚焦时） |

### 搜索语法

直接输入关键词按名称/域名/描述/分组模糊匹配；也可加 token：
`claude group:AI tag:coding fav:true pinned:true`。

### 维护命令

```bash
python -m app.cli db-info            # 数据库概览
python -m app.cli backup             # 备份 sites.db
python -m app.cli cleanup-logos     # 清理无用 logo
python -m app.cli check-sites       # 全站健康检查
python -m app.cli refresh-metadata  # 全站刷新标题/logo
```

## 备份与迁移

所有重要数据都在 `data/` 下（`sites.db` + `logos/`）。换电脑只需复制
`data/` 目录即可恢复；也可用「设置 → 下载备份」生成 zip。导入支持
合并与替换两种模式（替换会先自动备份）。

## 配置（环境变量，CLI 优先级更高）

| 变量 | 默认 | 说明 |
|---|---|---|
| `SITEUNIT_HOST` | 127.0.0.1 | 绑定地址 |
| `SITEUNIT_PORT` | 8000 | 端口 |
| `SITEUNIT_DATA_DIR` | ./data | 数据目录 |
| `SITEUNIT_ALLOW_PRIVATE_NETWORK_FETCH` | true | 是否允许抓取内网/localhost |
| `SITEUNIT_VERIFY_TLS` | true | 抓取时是否校验 TLS |
| `SITEUNIT_FETCH_READ_TIMEOUT` | 10 | 读超时（秒） |
| `SITEUNIT_MAX_HTML_SIZE` | 2097152 | 单页 HTML 抓取上限 |
| `SITEUNIT_LOG_LEVEL` | INFO | 日志级别 |

## 安全须知

默认仅绑 `127.0.0.1`。`--host 0.0.0.0` 会暴露给局域网且**无鉴权**，
请在可信网络使用或放在带认证的反代后面。详见
[docs/SECURITY.md](docs/SECURITY.md)。

## 目录结构

```
run.py                 启动入口
app/
  config.py            配置（env + CLI）
  errors.py            统一错误模型
  urlnorm.py           URL 规范化 + 去重
  fetcher.py           SSRF-safe HTTP 客户端
  metadata.py          标题/logo 抓取 pipeline
  logos.py             图像校验 + 稳定命名 + GC
  migrations.py        幂等迁移系统
  db.py                SQLite 存取（WAL）
  services.py          编排层
  schemas.py           Pydantic 模型
  api/                 路由（sites/system/health/io）
  cli.py               维护命令
static/                前端（ESM，无构建）
data/                  运行时数据（自动创建，勿入库）
docs/                  CODEBASE_AUDIT / ROADMAP / ARCHITECTURE / SECURITY / PERFORMANCE
tests/                 pytest 回归套件
```

## 开发

```bash
pip install -r requirements.txt      # 含 pytest
pytest                               # 运行测试（70+ 用例）
```

## 故障排查

- **添加站点后没抓到 logo**：站点可能自签名证书（设
  `SITEUNIT_VERIFY_TLS=false`）、内网地址（确认
  `SITEUNIT_ALLOW_PRIVATE_NETWORK_FETCH=true`）或无 favicon（会显示首字母头像）。
- **`--host 0.0.0.0` 手机打不开**：确认防火墙放行端口、手机与电脑同网段。
- **数据库升级报错**：迁移失败会自动回滚并保留 `data/backups/` 里的备份。
