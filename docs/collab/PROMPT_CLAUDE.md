# 提示词 — 发给 Claude（agent/claude-ui worktree）

把以下内容作为首条消息发给 Claude：

---

你是本次双 agent 协作验证中的**前端 agent（claude-ui）**，当前 worktree 位于
`agent/claude-ui` 分支。另一个 agent（codex-api）正在另一个 worktree 并行开发后端。

请严格按顺序阅读并遵守：

1. `AGENTS.md`（协作铁律与文件归属表，最高优先级；该文件对你同样生效）
2. `docs/collab/PLAN.md`（任务全貌）
3. `docs/collab/CONTRACT.md`（接口契约，逐字照做）
4. 本文件

注意：根目录的 `CLAUDE.md` 是指针文件，规则正文在 `AGENTS.md`。

## 背景假设（后端由对方并行交付，你不要等待或自己实现）

- `GET /api/stats/overview?days=30` 将返回契约第 2 节定义的 JSON：
  `{ days, total_visits, daily:[{date,count}], top_sites:[{site_id,name,url,
  logo_url,visits}], groups:[{name,count}] }`。
- 埋点 `POST /api/sites/{id}/visit` 已存在，你不需要改动它。

## 你的任务

为「访问统计仪表盘」实现前端，仅限修改/新建归属表中分配给 claude-ui 的文件：

- 修改 `static/js/api.js`：新增一个 `statsOverview(days)` 方法调用上述接口，
  复用现有的 `api()` 封装与错误处理；不改动其他已有方法的行为。
- 新建 `static/js/components/stats-panel.js`：一个 Vue ESM 组件，props 为
  可见性开关（或按现有组件风格自行组织），内部负责拉取与展示：
  1. 7 / 30 / 90 天切换按钮，切换即重新请求；
  2. 窗口内总访问数 `total_visits`；
  3. `daily` 渲染为零依赖的内联 SVG 柱状图（高度按窗口内最大 count 归一化，
     全零数据时柱子高度为 0 且不报错）；每个柱带 `title`/`aria-label`
     显示日期与次数；
  4. `top_sites` 列表：logo 用 `logo_url`，为 null 时回退首字母头像
     （复用 utils 的 firstLetter/hueOf），点击在新标签打开 url；
  5. `groups` 分布（名称 + 计数 + 简单占比条），`name === ""` 显示「未分类」；
  6. loading 态、失败时通过事件交给父组件用现有 toast 展示，不白屏。
- 修改 `static/js/app.js`：注册并挂载该组件，在顶部视图导航增加「统计」入口
  （view 取值 `stats`，与现有 all/archived/broken 并列）；保持现有视图与
  交互不回归。
- 修改 `static/css/style.css`：新增统计视图所需样式，使用现有 design tokens
  与主题变量，浅色/深色、comfortable/compact 密度、390px 移动端均可用。

## 自验标准

1. 代码静态自检：无未使用导入、无 console.log 残留、模板中无硬编码颜色
   （一律用现有 CSS 变量/tokens）。
2. 因后端在另一分支，使用浏览器 DevTools / 本地 mock（例如在组件中临时
   fetch 一个你放在组件内的常量样例，**验证后必须移除**）确认三种数据形态：
   正常数据、空数据（daily 全 0、数组为空）、logo_url 为 null。
3. `git status` 确认只改了归属表内文件；不留下 mock 临时代码。
4. 提交：使用 `[claude-ui]` 前缀，可分多个小提交。
5. 合并后（人类操作）配合做一次真机联调；如后端字段与契约不符，由人类裁决，
   不要自行去改 app/ 下文件。

## 边界

- 不碰任何 `app/` 下文件，不碰 AGENTS.md/CLAUDE.md/docs/collab/*。
- 不改 index.html、requirements.txt、run.py，不引入任何新依赖或第三方图表库。
- 契约有问题不要自己改，写进最终汇报的「契约变更建议」。
- 不执行 git merge / git switch / push / rebase。

最终请汇报：改动文件清单、提交列表、三种数据形态的自验结果、
契约变更建议（如有）、遗留问题。