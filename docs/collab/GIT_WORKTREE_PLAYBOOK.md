# Git Worktree 双 Agent 协作完整手册

> 本文是学习与复盘资产，不是接口契约。
> 执行协作任务时，仍以 `AGENTS.md` 与 `docs/collab/CONTRACT.md` 为准。
> 本文记录的是：如何从 main 开出两个 agent worktree、如何定义边界、如何合并、如何清理，以及每条命令的含义。

---

## 0. 先给结论

这次仓库状态本质上是：

```text
origin/main
  └── main
        ├── agent/claude-ui      已合并进 main
        └── agent/codex-api      比 main 多 2 个提交
```

最终正确做法不是：

```text
把 agent/codex-api 改名成 main
删除旧 main
```

而是：

```text
把 main 快进到 agent/codex-api 的最新提交
推送 main
删除已合并的 agent 分支
删除对应 worktree
```

一句话：

> **main 是长期主干，agent 分支是临时任务分支，worktree 是临时工作目录。任务合并后，保留 main，删除 agent 分支和 worktree。**

---

## 1. 核心心智模型

学习 git worktree 时，最重要的是先分清三个东西。

### 1.1 commit

真正的内容在 commit 里。

每个 commit 大概包含：

```text
文件快照
父提交
作者
时间
提交信息
commit hash，例如 e61cb1e
```

Git 的历史本质上是一个提交图。

### 1.2 branch

分支不是文件夹，也不是一份代码拷贝。

分支只是一个**指针**，指向某个 commit。

例如：

```text
main          -> 724b39b
agent/codex   -> e61cb1e
```

所以“把 codex-api 作为 main”，真正含义是：

```text
把 main 这个指针移动到 e61cb1e
```

不需要删除 main，也不需要改名。

### 1.3 worktree

worktree 是一个额外的工作目录。

它让你可以在不同目录里同时打开不同分支。

例如：

```text
website-unit          -> main
my-project-codex      -> agent/codex-api
my-project-claude     -> agent/claude-ui
```

它们共享同一个 Git 仓库对象库，但每个 worktree 有自己的：

```text
工作文件
HEAD
暂存区 index
未跟踪文件
```

重点：

> **worktree 不是 clone。它共享分支和提交对象。**

因此：

- `main` 分支只有一个
- `agent/codex-api` 分支只有一个
- 但它们可以在不同目录里分别被 checkout

---

## 2. 多 Agent 协作的总体流程

完整流程是：

```text
1. 准备 main
2. 从 main 开出两个 agent 分支
3. 为每个 agent 创建独立 worktree
4. 定义协作规范和接口契约
5. 两个 agent 在各自 worktree 中开发
6. 各自提交、自验
7. 人类作为集成者执行合并
8. 解决冲突
9. 运行测试
10. 推送 main
11. 删除 agent worktree
12. 删除 agent 分支
13. main 成为唯一主线
```

其中最重要的原则是：

> **agent 只开发，不合并；人类负责集成。**

---

## 3. 从 main 开出两个 agent 分支

假设主 worktree 在：

```text
C:\CodeSpace\VSCode\git-worktree-multiagents-learn\website-unit
```

你要创建：

```text
agent/codex-api
agent/claude-ui
```

对应目录：

```text
..\my-project-codex
..\my-project-claude
```

### 3.1 进入主 worktree

```powershell
Set-Location C:\CodeSpace\VSCode\git-worktree-multiagents-learn\website-unit
```

注释：

- `Set-Location`：PowerShell 的进入目录命令，等价于 `cd`
- 必须在 main worktree 里执行后续命令

### 3.2 更新 main

```powershell
git switch main
```

注释：

- `git`：Git 主命令
- `switch`：切换分支
- `main`：目标分支
- 这一步让主 worktree 停在 main 上

然后：

```powershell
git pull --ff-only
```

注释：

- `pull`：从远端拉取并整合更新
- `--ff-only`：只允许 fast-forward，不允许自动生成 merge commit
- 如果本地和远端分叉，它会失败，让你先检查，而不是悄悄合并

也可以先执行：

```powershell
git fetch --prune
```

注释：

- `fetch`：只下载远端对象和分支信息，不改工作区
- `--prune`：删除远端已经不存在的远端跟踪分支
- 例如远端删除了 `origin/old-branch`，本地对应的跟踪引用也会被清掉

### 3.3 创建 Codex worktree

```powershell
git worktree add -b agent/codex-api ..\my-project-codex main
```

逐词解释：

- `git`
  - Git 主命令
- `worktree`
  - 子命令，表示操作 worktree
- `add`
  - 添加一个 worktree
- `-b agent/codex-api`
  - 创建新分支，名字是 `agent/codex-api`
  - `-b` 是 `branch` 的缩写
- `..\my-project-codex`
  - 新 worktree 的路径
- `main`
  - 新分支的起点，也就是基于当前 main

这条命令实际做了两件事：

```text
创建分支 agent/codex-api
创建目录 my-project-codex 并 checkout 这个分支
```

### 3.4 创建 Claude worktree

```powershell
git worktree add -b agent/claude-ui ..\my-project-claude main
```

含义同上，只是：

```text
新分支名：agent/claude-ui
新目录：my-project-claude
起点：main
```

### 3.5 验证

```powershell
git worktree list
```

注释：

- `worktree`
  - worktree 子命令
- `list`
  - 列出所有 worktree

预期输出类似：

```text
C:/.../website-unit       main
C:/.../my-project-codex   agent/codex-api
C:/.../my-project-claude  agent/claude-ui
```

---

## 4. 如果分支已存在，如何挂 worktree

如果分支已经存在，不需要 `-b`：

```powershell
git worktree add ..\my-project-codex agent/codex-api
```

注释：

- `git worktree add`
  - 添加 worktree
- `..\my-project-codex`
  - worktree 路径
- `agent/codex-api`
  - 要 checkout 的已有分支

注意：

> **同一个分支不能同时被两个 worktree checkout。**

如果你尝试：

```powershell
git worktree add ..\another-codex agent/codex-api
```

而 `agent/codex-api` 已经在 `my-project-codex` 中 checkout，Git 会拒绝。

---

## 5. 应该定义哪些协作文档

这次项目之所以能跑通，核心不只是用了 worktree，而是先定义了规则。

建议至少有这几类文档。

### 5.1 AGENTS.md：最高协作规则

它应该定义：

#### 身份

```text
agent/codex-api：后端 agent
agent/claude-ui：前端 agent
```

#### worktree 位置

```text
主 worktree：../website-unit
Codex worktree：../my-project-codex
Claude worktree：../my-project-claude
```

#### 文件归属表

例如：

```text
app/api/stats.py             Codex 可改，Claude 禁止
tests/test_stats.py          Codex 可改，Claude 禁止
static/js/api.js             Claude 可改，Codex 禁止
static/js/app.js             Claude 可改，Codex 禁止
static/css/style.css         Claude 可改，Codex 禁止
docs/collab/*                双方只读冻结
```

#### 禁止行为

例如：

```text
不要读写对方 worktree
不要切换分支
不要操作主仓库
不要执行 merge
不要改契约文档
不要安装新依赖
不要提交运行时产物
不要 force push
不要 reset --hard
```

#### 汇报格式

最终报告必须包含：

```text
改动文件清单
自验结果
契约变更建议
遗留问题
```

### 5.2 docs/collab/PLAN.md：任务计划

它回答“这次要做什么”。

建议包含：

```text
目标
非目标
里程碑
验收标准
风险
分支划分
测试要求
```

示例结构：

```markdown
# 任务计划

## 目标
实现访问统计仪表盘。

## 非目标
不做用户登录。
不做多语言。

## 分工
Codex：后端接口、数据库、测试。
Claude：前端页面、交互、样式。

## 验收标准
- 后端测试通过
- 前端能展示 7/30/90 天统计
- API 字段与契约一致
```

### 5.3 docs/collab/CONTRACT.md：接口契约

这是双 Agent 协作里最重要的文档。

它回答“双方通过什么接口通信”。

建议包含：

```text
接口路径
HTTP 方法
查询参数
参数类型
合法取值
返回字段
字段类型
空值规则
错误码
错误响应结构
示例请求
示例响应
兼容性规则
```

例如：

```markdown
# API Contract

## GET /api/stats/overview

Query:
- days: integer
- allowed values: 7, 30, 90

Response:
{
  "days": 30,
  "total_events": 123,
  "daily": [...],
  "top_sites": [...]
}

Rules:
- 字段名必须完全一致
- 不允许一方私自新增字段
- 不允许把 number 改成 string
```

为什么要这样？

因为 Git 只能解决**文本冲突**，不能自动发现**语义冲突**。

例如：

```text
后端返回 total_events
前端读取 totalEvents
```

Git 不会报冲突，但程序会坏。

所以契约必须是唯一事实来源。

### 5.4 docs/collab/PROMPT_CODEX.md

这是给 Codex 的具体任务说明。

建议包含：

```text
角色
可修改文件
禁止修改文件
需要实现的接口
测试命令
提交格式
最终汇报格式
```

### 5.5 docs/collab/PROMPT_CLAUDE.md

同理，给 Claude 的具体任务说明。

---

## 6. 文档之间的优先级

建议按这个顺序：

```text
AGENTS.md
  ↓
docs/collab/CONTRACT.md
  ↓
docs/collab/PLAN.md
  ↓
PROMPT_CODEX.md / PROMPT_CLAUDE.md
```

原因是：

```text
AGENTS.md 管边界
CONTRACT.md 管接口
PLAN.md 管目标
PROMPT 管具体执行
```

最重要的一条：

> **契约文档应该冻结。**

如果 agent 发现契约有问题，不允许自己改，而应该在最终报告中写：

```text
契约变更建议：xxx
```

由人类决定是否修改。

---

## 7. Agent 行为边界设计

这次经验里，最关键的是这些边界。

### 7.1 分支即身份

```text
agent/codex-api 只做后端
agent/claude-ui 只做前端
```

这样有四个好处：

1. 分工清楚
2. 文件冲突少
3. 提交历史容易读
4. 出问题容易回滚

### 7.2 不碰对方 worktree

```text
Codex 不读写 my-project-claude
Claude 不读写 my-project-codex
```

原因：

- 避免互相污染
- 避免看到对方半成品
- 避免误改
- 保持任务隔离

### 7.3 不碰 main

agent 只在自己的分支上工作：

```text
agent/codex-api
agent/claude-ui
```

不执行：

```text
git switch main
git merge
git push origin main
```

原因：

> main 是集成结果，不是 agent 的工作区。

### 7.4 不改共享契约

契约是双方共同依赖的接口。

如果一方改了契约，另一方不知道，就会产生语义冲突。

正确流程是：

```text
发现问题
停止相关实现
在最终报告中提出契约变更建议
等待人类裁决
```

### 7.5 不做无关重构

例如任务是统计接口，就不要顺手：

```text
重排 import
格式化全文件
修改无关 typo
重构其他模块
```

原因：

- 会制造冲突
- 会污染 review
- 会掩盖真实任务改动

### 7.6 不提交运行时产物

例如：

```text
data/
.venv/
__pycache__/
node_modules/
dist/
```

这些应该被 `.gitignore` 排除。

---

## 8. Agent 的日常工作循环

以 Codex 为例。

### 8.1 进入自己的 worktree

```powershell
Set-Location C:\CodeSpace\VSCode\git-worktree-multiagents-learn\my-project-codex
```

### 8.2 检查当前状态

```powershell
git status --short --branch
```

注释：

- `status`
  - 查看工作区状态
- `--short`
  - 简短输出
- `--branch`
  - 显示当前分支

常见符号：

```text
##  当前分支
M   已修改但未暂存
A   已暂存的新文件
D   已删除
??  未跟踪文件
U   冲突未解决
```

### 8.3 查看改动

```powershell
git diff
```

注释：

- `diff`
  - 查看未暂存改动

如果已经 `git add`，要看暂存区：

```powershell
git diff --cached
```

注释：

- `--cached`
  - 查看已经暂存、等待 commit 的改动

### 8.4 暂存并提交

```powershell
git add app/api/stats.py
```

注释：

- `add`
  - 把文件加入暂存区
- 这不是“创建提交”，只是“准备提交”

然后：

```powershell
git commit -m "[codex-api] 实现访问统计接口"
```

注释：

- `commit`
  - 创建提交
- `-m`
  - message，提交说明
- `[codex-api]`
  - 标识这是哪个 agent 的改动

---

## 9. 合并前的检查

合并应该由人类在主 worktree 做。

进入：

```powershell
Set-Location C:\CodeSpace\VSCode\git-worktree-multiagents-learn\website-unit
```

检查：

```powershell
git status --short --branch
```

确认 main 是干净的。

再查看所有分支：

```powershell
git branch -avv
```

注释：

- `branch`
  - 分支管理命令
- `-a`
  - all，显示本地和远端分支
- `-vv`
  - very verbose，显示更详细信息

查看提交图：

```powershell
git log --oneline --decorate --graph --all -20
```

注释：

- `log`
  - 查看提交历史
- `--oneline`
  - 每个提交一行
- `--decorate`
  - 显示分支名、tag 等引用
- `--graph`
  - 显示图形结构
- `--all`
  - 显示所有分支
- `-20`
  - 最近 20 条

---

## 10. 合并策略：fast-forward 与 no-ff

### 10.1 fast-forward

如果 main 是 agent 分支的祖先，可以这样：

```powershell
git merge --ff-only agent/codex-api
```

注释：

- `merge`
  - 合并分支
- `--ff-only`
  - 只允许快进合并
- `agent/codex-api`
  - 被合并的分支

效果：

```text
main 直接移动到 agent/codex-api 的最新提交
不产生额外 merge commit
```

适合：

```text
main 没有分叉
希望历史线性
```

### 10.2 no-ff

如果想保留“这里发生过一次分支合并”的记录：

```powershell
git merge --no-ff agent/claude-ui
```

注释：

- `--no-ff`
  - no fast-forward
  - 即使可以快进，也强制创建 merge commit

效果：

```text
历史里会出现一个 merge commit
```

适合：

```text
希望保留任务边界
希望从 main 一眼看出哪些提交来自哪个 agent 分支
```

### 10.3 怎么判断能否 fast-forward

```powershell
git merge-base --is-ancestor main agent/codex-api
```

注释：

- `merge-base`
  - 查找共同祖先
- `--is-ancestor`
  - 判断第一个提交是否是第二个提交的祖先
- 如果 `main` 是 `agent/codex-api` 的祖先，说明可以 fast-forward

在 PowerShell 里可以这样看结果：

```powershell
git merge-base --is-ancestor main agent/codex-api
if ($LASTEXITCODE -eq 0) {
    "可以 fast-forward"
} else {
    "不能 fast-forward，需要 merge 或 rebase"
}
```

---

## 11. 双分支合并的推荐顺序

假设两个 agent 分支都从 main 开出：

```text
main
  ├── agent/codex-api
  └── agent/claude-ui
```

推荐流程：

```text
1. 合并第一个分支
2. 测试
3. 合并第二个分支
4. 测试
5. 推送 main
```

例如：

```powershell
git switch main
git merge --no-ff agent/claude-ui
```

然后运行测试。

再：

```powershell
git merge --no-ff agent/codex-api
```

再运行测试。

如果两个分支文件基本不重叠，第二合并通常比较顺利。

如果有共享文件或语义依赖，就要处理冲突。

---

## 12. 冲突解决

### 12.1 先看冲突文件

```powershell
git status
```

或者只列冲突文件：

```powershell
git diff --name-only --diff-filter=U
```

注释：

- `diff`
  - 查看差异
- `--name-only`
  - 只显示文件名
- `--diff-filter=U`
  - U 表示 unmerged，也就是冲突文件

### 12.2 理解冲突标记

文件里可能看到：

```text
<<<<<<< HEAD
days: int
=======
days: str
>>>>>>> agent/claude-ui
```

含义：

```text
<<<<<<< HEAD
当前分支的内容，也就是 main

=======
另一边的内容

>>>>>>> agent/claude-ui
来自哪个分支
```

注意：

- 在 merge 时，`HEAD` 是 main
- `agent/claude-ui` 是被合入的分支

### 12.3 手动解决

不要盲目选择一边。

正确做法是：

```text
看契约
看测试
看业务语义
再决定
```

例如契约说：

```text
days 是 integer
```

那正确结果应该是：

```python
days: int
```

而不是因为 `HEAD` 是 main 就必须选 main。

### 12.4 标记已解决

改完文件后：

```powershell
git add path/to/file.py
```

注释：

- `git add`
  - 在冲突场景中，表示“这个文件的冲突已经解决”

全部解决后：

```powershell
git commit
```

注释：

- `commit`
  - 完成这次 merge commit

### 12.5 如果搞砸了，中止合并

如果还没 commit，可以：

```powershell
git merge --abort
```

注释：

- `merge`
  - merge 子命令
- `abort`
  - 中止当前合并
- 会把仓库恢复到 merge 开始前的状态

---

## 13. ours 和 theirs 的含义

Git 里有两个容易误解的词：

```text
ours
theirs
```

在 merge 时：

```text
ours   = 当前分支，例如 main
theirs = 被合并进来的分支，例如 agent/claude-ui
```

可以选择某一侧：

```powershell
git checkout --ours path/to/file
```

注释：

- `checkout`
  - 恢复文件版本
- `--ours`
  - 使用当前分支版本

或者：

```powershell
git checkout --theirs path/to/file
```

注释：

- `--theirs`
  - 使用被合并分支版本

但注意：

> 不建议一开始就用这两个命令。

它们只适合你非常明确知道某一边是正确版本的时候。

多数情况下应该手动看语义。

另外，在 rebase 时，`ours/theirs` 的方向会反过来，这是新手最容易踩坑的地方。

---

## 14. 语义冲突比文本冲突更危险

Git 能检测这种情况：

```text
两个人改了同一个文件同一行
```

但 Git 检测不到：

```text
后端返回 total_events
前端读取 totalEvents
```

这就是语义冲突。

常见的语义冲突有：

```text
字段名不一致
类型不一致
空值规则不一致
错误码不一致
路由不一致
分页规则不一致
数据库 schema 不一致
前端调用时机不一致
```

解决办法：

1. 契约先行
2. 双方严格按契约实现
3. 合并后跑完整测试
4. 人类最终检查

---

## 15. 推送 main

合并完成后：

```powershell
git switch main
git push origin main
```

注释：

- `push`
  - 上传本地提交到远端
- `origin`
  - 默认远端名
- `main`
  - 要推送的分支

如果推送被拒绝，先不要 force：

```powershell
git fetch origin
git log --oneline --decorate --graph main origin/main
```

然后判断：

```powershell
git pull --ff-only
```

如果可以快进，再推送。

只有在极特殊情况下才考虑：

```powershell
git push --force-with-lease
```

但这次完全不需要。

---

## 16. 删除 worktree

合并完成后，worktree 就是临时产物了。

先关闭：

```text
编辑器
终端
dev server
agent 会话
```

然后回到 main worktree：

```powershell
Set-Location C:\CodeSpace\VSCode\git-worktree-multiagents-learn\website-unit
```

删除 Claude worktree：

```powershell
git worktree remove ..\my-project-claude
```

注释：

- `worktree`
  - worktree 子命令
- `remove`
  - 删除 worktree
- `..\my-project-claude`
  - 要删除的 worktree 路径

删除 Codex worktree：

```powershell
git worktree remove ..\my-project-codex
```

注意：

> 不要在 `my-project-codex` 里面删除它自己。

如果 worktree 有未提交文件，Git 可能拒绝删除。

先去检查：

```powershell
git status --short
```

不要随手使用：

```powershell
git worktree remove --force
```

除非你确定可以丢弃所有未提交内容。

---

## 17. 删除已合并分支

先确认哪些分支已经合并进 main：

```powershell
git branch --merged main
```

注释：

- `branch`
  - 分支命令
- `--merged`
  - 列出已经合并进指定分支的分支
- `main`
  - 判断基准

如果输出里有：

```text
agent/codex-api
agent/claude-ui
```

就可以安全删除：

```powershell
git branch -d agent/codex-api
git branch -d agent/claude-ui
```

注释：

- `-d`
  - delete
  - 安全删除，只删除已合并分支

如果 Git 拒绝：

```text
error: the branch is not fully merged
```

说明它认为分支还没合并。

这时不要直接用：

```powershell
git branch -D
```

因为 `-D` 是强制删除。

应该先检查历史。

---

## 18. 清理 worktree 元数据

如果你手动删除了 worktree 目录，而不是用：

```powershell
git worktree remove
```

Git 里可能留下过期记录。

执行：

```powershell
git worktree prune
```

注释：

- `prune`
  - 清理不再存在的 worktree 记录

然后验证：

```powershell
git worktree list
```

---

## 19. 如果远端也有 agent 分支

这次检查结果显示远端只有：

```text
origin/main
```

没有：

```text
origin/agent/codex-api
origin/agent/claude-ui
```

所以不需要删除远端分支。

如果以后你把 agent 分支推到了远端，例如：

```powershell
git push -u origin agent/codex-api
```

注释：

- `-u`
  - set upstream
  - 建立本地分支和远端分支的跟踪关系

合并后可以删除远端分支：

```powershell
git push origin --delete agent/codex-api
```

注释：

- `push`
  - 推送
- `origin`
  - 远端名
- `--delete`
  - 删除远端分支
- `agent/codex-api`
  - 要删除的分支

也可以合并后执行：

```powershell
git fetch --prune
```

清掉本地过期的远端跟踪分支。

---

## 20. 为什么不要删除或改名 main

技术上可以把 `agent/codex-api` 改名成 `main`，但不建议。

### 20.1 main 是指针，不是历史

你想要的结果是：

```text
main -> e61cb1e
```

用 fast-forward 就能实现：

```powershell
git merge --ff-only agent/codex-api
```

不需要删除 main。

### 20.2 main 通常被外部依赖

远端和工具链通常默认使用 main：

```text
origin/HEAD -> origin/main
CI 流水线
保护规则
部署脚本
协作者习惯
```

删除或改名会带来额外成本。

### 20.3 改名不会改变提交

即使你把 `agent/codex-api` 改名成 `main`，提交历史还是那些提交。

改名只是换标签，不会让代码“更正确”。

### 20.4 会造成远端混乱

本地删除 main，不等于远端删除 main。

远端默认分支还是要去 GitHub 设置里改。

如果处理不好，会出现：

```text
本地有 main
远端有另一个 main
协作者看到分支消失
CI 找不到默认分支
```

所以行业做法是：

> **保留 main，更新 main，删除临时分支。**

---

## 21. 行业内两种常见模式

### 21.1 本地集成模式

适合个人项目或本地多 agent：

```text
main
  ├── agent/codex-api
  └── agent/claude-ui

人类本地 merge 到 main
push main
删除 agent 分支和 worktree
```

这次用的就是这种。

### 21.2 PR 模式

适合团队协作：

```text
创建 agent 分支
push 到远端
创建 Pull Request
人类 review
在 GitHub 上 merge
删除远端分支
本地 pull main
删除本地分支和 worktree
```

典型命令：

```powershell
git push -u origin agent/codex-api
```

然后在 GitHub 创建 PR。

合并后：

```powershell
git switch main
git pull --ff-only
git branch -d agent/codex-api
```

如果远端 PR 已经删除分支，再执行：

```powershell
git fetch --prune
```

---

## 22. rebase、merge、squash 怎么选

### merge

```text
保留分支拓扑
产生 merge commit
适合多人并行任务
```

命令：

```powershell
git merge --no-ff agent/claude-ui
```

### fast-forward

```text
main 只是移动指针
历史线性
不产生 merge commit
适合 main 没有分叉时
```

命令：

```powershell
git merge --ff-only agent/codex-api
```

### rebase

```text
把一个分支的提交搬到另一个分支后面
历史更线性
但会改写提交
```

适合：

```text
个人分支同步最新 main
希望提交历史干净
```

但要小心：

> 不要对已经共享的分支随意 rebase。

### squash merge

```text
把一个分支多个提交压成一个提交
适合功能分支里有很多碎片提交
```

缺点：

```text
丢失细粒度历史
```

注意：

如果使用 squash merge，原来的 agent 分支提交不会被完整保留在 main 历史里，所以：

```powershell
git branch -d agent/xxx
```

可能会提示“未合并”。

这时要在确认 PR 已合并后，再删除分支。

---

## 23. 常用英文词解释

| 英文 | 含义 |
|---|---|
| `clone` | 克隆一个远端仓库 |
| `fetch` | 拉取远端对象和引用，不改工作区 |
| `pull` | fetch 后整合到当前分支 |
| `push` | 把本地提交上传到远端 |
| `origin` | 默认远端名 |
| `remote` | 远端仓库配置 |
| `branch` | 分支 |
| `switch` | 切换分支 |
| `checkout` | 旧版切分支/恢复文件命令 |
| `commit` | 提交 |
| `merge` | 合并 |
| `rebase` | 变基，把提交移到新的基底上 |
| `worktree` | 额外工作目录 |
| `add` | 添加 worktree，或暂存文件 |
| `remove` | 删除 worktree |
| `prune` | 清理过期引用 |
| `status` | 查看状态 |
| `diff` | 查看差异 |
| `log` | 查看历史 |
| `HEAD` | 当前所在位置，通常指向当前分支 |
| `ref` | 引用，例如分支、tag |
| `SHA` | commit 哈希，例如 `e61cb1e` |
| `staged` | 已暂存，等待提交 |
| `untracked` | 未跟踪文件 |
| `clean` | 工作区干净 |
| `dirty` | 工作区有未提交改动 |
| `ahead` | 本地比远端多提交 |
| `behind` | 本地比远端少提交 |
| `fast-forward` | 快进，只移动分支指针 |
| `ours` | merge 时的当前分支 |
| `theirs` | merge 时被合入的分支 |
| `upstream` | 上游跟踪分支 |

---

## 24. 常见命令状态符号

执行：

```powershell
git status --short --branch
```

如果看到：

```text
## main...origin/main [ahead 6]
```

含义：

```text
main 正在跟踪 origin/main
本地 main 比 origin/main 多 6 个提交
```

如果看到：

```text
M app/main.py
```

含义：

```text
app/main.py 已修改，但未暂存
```

如果看到：

```text
?? data/test.db
```

含义：

```text
data/test.db 是未跟踪文件
```

如果看到：

```text
UU app/main.py
```

含义：

```text
app/main.py 处于冲突状态
```

---

## 25. 反模式清单

这些不要做。

### 25.1 不要删除 main

```text
错误思路：删除 main，把 codex-api 改名成 main
```

正确做法：

```powershell
git merge --ff-only agent/codex-api
```

### 25.2 不要让 agent 自己 merge

agent 的职责是实现，不是集成。

合并时会出现：

```text
冲突判断
契约裁决
优先级判断
测试取舍
```

这些应该由人类完成。

### 25.3 不要双方都改契约

这会造成语义冲突。

### 25.4 不要在两个 worktree checkout 同一个分支

Git 会拒绝，而且会造成心智混乱。

### 25.5 不要随手 force push

```powershell
git push --force
```

风险很高。

如果真的必须，也优先：

```powershell
git push --force-with-lease
```

但这次完全不需要。

### 25.6 不要随手 reset --hard

```powershell
git reset --hard
```

会丢工作区改动。

### 25.7 不要随手 clean

```powershell
git clean -fdx
```

会删除未跟踪文件。

### 25.8 不要在当前 worktree 里删除它自己

先切到 main worktree，再删 agent worktree。

### 25.9 不要盲目 ours/theirs

先看契约和测试。

---

## 26. 当前仓库的最终收尾命令

这是针对当时状态的收尾流程。

先关闭 Codex / Claude 相关会话，然后在 main worktree 执行：

```powershell
Set-Location C:\CodeSpace\VSCode\git-worktree-multiagents-learn\website-unit
```

检查状态：

```powershell
git status --short --branch
```

更新远端信息：

```powershell
git fetch --prune
```

确认在 main：

```powershell
git switch main
```

更新 main：

```powershell
git pull --ff-only
```

把 main 快进到 `agent/codex-api` 最新提交：

```powershell
git merge --ff-only agent/codex-api
```

推送：

```powershell
git push origin main
```

删除 worktree：

```powershell
git worktree remove ..\my-project-claude
git worktree remove ..\my-project-codex
```

删除已合并分支：

```powershell
git branch -d agent/claude-ui
git branch -d agent/codex-api
```

清理 worktree 记录：

```powershell
git worktree prune
```

最终验证：

```powershell
git worktree list
git branch -avv
git log --oneline --decorate --graph --all -15
```

---

## 27. 最终理想状态

完成后应该是：

```text
main        -> e61cb1e
origin/main -> e61cb1e
```

本地只剩：

```text
main
```

worktree 只剩：

```text
website-unit
```

提交图大概变成：

```text
origin/main
  └── main
```

这就完成了：

```text
最新版成为 main
云端 main 更新
临时 agent 分支清理
临时 worktree 清理
```

---

## 28. 以后如何再次创建双 Agent 环境

如果以后还要做类似任务：

```powershell
Set-Location C:\CodeSpace\VSCode\git-worktree-multiagents-learn\website-unit

git switch main
git pull --ff-only

git worktree add -b agent/codex-api-2 ..\my-project-codex-2 main
git worktree add -b agent/claude-ui-2 ..\my-project-claude-2 main
```

然后重复：

```text
定义归属
定义契约
各自开发
各自提交
人类合并
清理
```

---

## 29. 一句话总结这次学到的最佳实践

> **用 worktree 解决“同时打开多个分支”的问题，用文件归属表解决“谁改哪里”的问题，用 CONTRACT 解决“接口怎么对齐”的问题，用人类 merge 解决“最终集成权”的问题，用 fast-forward 或 merge 把结果落回 main，最后删除临时分支和 worktree。**
