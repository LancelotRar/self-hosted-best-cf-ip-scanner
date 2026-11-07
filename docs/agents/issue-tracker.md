# Issue tracker: GitHub

本仓库的 issue 与规格存放在 GitHub Issues 中，统一用 `gh` CLI 操作。

仓库：`LancelotRar/self-hosted-best-cf-ip-scanner`（非 fork，Issues 已开启）。

## 约定

- **创建 issue**：`gh issue create --title "..." --body "..."`。多行正文用 heredoc。
- **读取 issue**：`gh issue view <number> --json number,title,body,labels,comments`。
- **列出 issue**：`gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'`，配合 `--label`、`--state` 过滤。
- **把 issue 设为子 issue**：`gh issue create --parent <parent> ...`，或事后 `gh issue edit <parent> --add-sub-issue <child>`（`gh` 2.94+；本机为 2.103.0，可用）。旧版改用 `gh api --method POST repos/<owner>/<repo>/issues/<parent>/sub_issues -F sub_issue_id=<child-db-id>`（用数据库 id，见下文 **阻塞关系**）。若子 issue 不可用，就在子 issue 正文顶部写 `Part of #<parent>`。
- **阻塞关系**：优先用 GitHub 原生 issue dependencies（UI 可见的规范表示）。`gh issue create --blocked-by <n>,<n> ...` 或 `gh issue edit <child> --add-blocked-by <blocker>`（`gh` 2.94+）；旧版改用 `gh api --method POST repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>`，其中 `<blocker-db-id>` 是阻塞者的数字**数据库 id**（`gh api repos/<owner>/<repo>/issues/<n> --jq .id`，不是 `#number`，也不是 `node_id`）。环境不支持 dependencies 时，退化为在子 issue 正文顶部写 `Blocked by: #<n>, #<n>`。所有阻塞者关闭后，该 issue 才算 unblocked。
- **统计未关闭的阻塞者**：`gh api repos/<owner>/<repo>/issues/<n> --jq .issue_dependencies_summary.blocked_by`（只算开启中的阻塞者，0 表示可开工）。`gh issue view <n> --json blockedBy` 会连已关闭的阻塞者一起列出，需过滤：`--jq '[.blockedBy.nodes[] | select(.state == "OPEN")] | length'`。
- **评论**：`gh issue comment <number> --body "..."`。
- **打/去标签**：`gh issue edit <number> --add-label "..."` / `--remove-label "..."`。
- **关闭**：先 `gh issue comment <number> --body "..."` 说明原因，再 `gh issue close <number>`。对已关闭的 issue 用 `gh issue close --comment` 会丢掉评论但仍返回 0。

在克隆目录内运行时，`gh` 会自动从 `git remote -v` 推断仓库。

只向本用户自己的仓库提 issue。在 fork 中 `gh` 可能默认指向上游父仓库，因此每次会话首次 `gh issue create` 前，先用 `gh repo view --json nameWithOwner` 确认目标仓库；若结果不是本仓库，先与用户确认。

## PR 作为分诊入口

**PR 作为需求入口：否。**（若本仓库把外部 PR 当作功能请求处理，改为 `yes`；`/triage` 会读取这个开关。）

设为 `yes` 时，PR 与 issue 走同一套标签与状态，命令换成 `gh pr` 等价物：

- **读 PR**：`gh pr view <number>`，再看 `gh pr view <number> --comments`（非 TTY 下 `--comments` 只打印评论，不打印正文），diff 用 `gh pr diff <number>`。
- **列外部 PR 待分诊**：`gh api --paginate 'repos/{owner}/{repo}/pulls?state=open' --jq '.[] | select(.author_association | IN("OWNER","MEMBER","COLLABORATOR") | not) | {number, title, author: .user.login, author_association, labels: [.labels[].name]}'`。
- **评论 / 打标签 / 关闭**：`gh pr comment`、`gh pr edit --add-label`/`--remove-label`、`gh pr close`。

GitHub 的 issue 与 PR 共用一个编号空间，裸写 `#42` 可能是两者之一：先 `gh pr view 42`，失败再退回 `gh issue view 42`。

## 当某个 skill 说 "publish to the issue tracker"

创建一个 GitHub issue。

## 当某个 skill 说 "fetch the relevant ticket"

按上面 **读取 issue** 的方式读取。

## Wayfinding 操作

供 `/wayfinder` 使用。**map** 是一个 issue，**child** issue 是它的 ticket。

- **Map**：单个 issue，标签 `wayfinder:map`，正文承载 Notes / Decisions-so-far / Fog。`gh issue create --label wayfinder:map`。
- **Child ticket**：作为 map 的 GitHub 子 issue 关联（见 **把 issue 设为子 issue**）。子 issue 不可用时，把 child 加进 map 正文的任务列表，并在 child 正文顶部写 `Part of #<map>`。标签：`wayfinder:<type>`（`research`/`prototype`/`grilling`/`task`）。认领后指派给负责的开发者。
- **阻塞**：见上文 **阻塞关系**。
- **Frontier 查询**：列出 map 的开启子 issue（`gh issue list --state open`，限定为 map 的子 issue / 任务列表），剔除有未关闭阻塞者的（见 **统计未关闭的阻塞者**，或 `Blocked by` 行里指向的开启 issue）和被指派的；按 map 顺序取第一个。
- **认领**：`gh issue edit <n> --add-assignee @me`，这是本会话的第一次写操作。
- **结项**：`gh issue comment <n> --body "<answer>"`，然后 `gh issue close <n>`，最后在 map 的 Decisions-so-far 追加一条上下文指针（要点 + 链接）。
