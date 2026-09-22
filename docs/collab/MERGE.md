# 合并与验收手册（仅人类执行）

两个 agent 都汇报完成后，在 main 的 worktree（`../website-unit`）操作。

## 1. 合并前检查（在各自 worktree 或用 git 命令核对）

```powershell
# 双方各自改动了哪些文件
git diff --name-only main...agent/codex-api
git diff --name-only main...agent/claude-ui
```

预期（脚手架已在 main 时，diff 不含 AGENTS.md/CLAUDE.md/docs/collab/*）：

- codex：`app/migrations.py`、`app/db.py`、`app/schemas.py`、`app/main.py`、
  `app/api/stats.py`、`tests/test_stats.py` 的子集
- claude：`static/js/api.js`、`static/js/app.js`、`static/css/style.css`、
  `static/js/components/stats-panel.js` 的子集

两个清单交集必须为空；如出现交集或冻结文件被改，先不要合并，按第 4 节处理。

## 2. 执行合并（顺序固定）

```powershell
cd ..\website-unit
git switch main
git merge agent/claude-ui
git merge agent/codex-api
```

- 两次 merge 预期均为无冲突（可能生成 merge commit，属正常）。
- 顺序选择：前端分支先合，后端分支后合，与任务书示例一致；
  由于文件集合不相交，反过来理论上也无冲突，可作为重复实验再验证一次。

## 3. 合并后验收

```powershell
# 1) 全量测试
.venv\Scripts\python.exe -m pytest          # 或先激活 venv 后 pytest

# 2) 启动并端到端验证
python run.py --port 8010
```

浏览器人工验收清单：

1. 打开首页，任意点击几个站点卡片（触发 visit）。
2. 进入「统计」视图：总访问数 > 0；daily 柱状图当天有柱；
   top_sites 出现刚点击的站点。
3. 切换 7 / 30 / 90 天：均能加载，daily 桶数分别为 7 / 30 / 90。
4. 空数据形态：清空 data/sites.db（或用全新 data 目录）后统计视图不白屏、
   不报错，柱子高度为 0。
5. logo 缺失站点显示首字母头像；分组占比中未分类显示「未分类」。
6. 原有功能回归：搜索、分组/标签过滤、收藏置顶、归档/死链视图、
   命令面板、移动端窄屏布局。

## 4. 出现问题时的处置

| 情况 | 处置 |
|---|---|
| Merge 报冲突 | 不要强行解冲突后直接交付；记录冲突文件，回溯是归属表违约还是契约缺失 |
| Agent 改了归属表外文件 | 让该 agent 在自己分支撤销越界改动并重新提交，再合并 |
| 字段与契约不一致 | 以契约为准，让责任方在自己分支修正；契约本身有缺陷则人类改 main 上的 CONTRACT.md，两个分支 rebase/merge main 后重做（罕见，属重要实验数据） |
| pytest 失败 | 先确认是否合并后才出现（双方各自分支单跑应通过）；合并后独有失败通常意味着契约理解分叉，据失败用例定位 |

## 5. 实验记录建议

记录以下数据用于对比 Claude / Codex 的协作表现：

- 各自分支提交数、改动行数
- merge 是否冲突、冲突文件数与冲突块数
- 契约变更建议数量
- 越界修改次数
- 合并后测试首次通过率
- 端到端验收发现的问题数