# SiteUnit · 个人站点导航

一个自己用的网站聚合页：填入 URL 即可添加站点，后端自动抓取网页标题和 logo（favicon），
前端以卡片分组展示，点击直达。

## 技术栈

- 后端：FastAPI + SQLite（单文件数据库，零配置）
- 前端：Vue 3（免构建，直接引用本地 `vue.global.prod.js`），无 Node 依赖
- logo 抓取：解析页面 `<link rel="icon">` / `og:image`，失败后回落到 `/favicon.ico`、DuckDuckGo、Google 图标服务

## 运行

```bash
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe run.py
```

浏览器打开 http://127.0.0.1:8000

可选参数：`--port 9000` 换端口；`--reload` 开发热重载；`--host 0.0.0.0` 局域网访问（手机也能用）。

## 使用

- **添加站点**：右上角「添加站点」，只填 URL 即可，名称留空会自动取网页标题，logo 自动抓取
- **分组**：添加/编辑时填分组名（如：工具、项目、学习），留空归入「未分类」
- **编辑 / 删除 / 重抓 logo**：鼠标悬停卡片右上角的按钮（↻ 重抓、✎ 编辑、🗑 删除）
- **搜索**：顶部搜索框按名称、域名、描述、分组过滤（快捷键 `/`）

## 数据

- `data/sites.db` — 站点列表（SQLite）
- `data/logos/` — 抓取到的 logo 图片缓存

备份/迁移只需拷贝 `data/` 目录。

## 目录结构

```
run.py            启动入口
app/              后端
  main.py         FastAPI 路由
  db.py           SQLite 存取
  logos.py        标题 & favicon 抓取
static/           前端（index.html / css / js / vendor）
data/             运行时数据（自动创建，勿入库）
```
