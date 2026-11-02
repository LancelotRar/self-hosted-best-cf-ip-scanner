#!/bin/sh
# 把本轮产物（CSV + 订阅 txt）镜像到目标仓库并提交推送。
#
# 实现要点（都是踩过的坑）：
# 1. 令牌只经 http.extraheader 注入，不落进 .git/config、也不出现在 remote URL；
#    容器日志与 git remote -v 都不会泄漏它。
# 2. 每次发布前 fetch + reset 到远端最新，再整体覆盖产物目录：产物是全量再生成
#    文件，冲突时"本轮优先"，因此不需要 rebase，也就没有 rebase 残留卡死的问题。
# 3. 镜像语义：产物目录内旧 *.txt/*.csv 先删再拷，把某个列表条数改成 0 后不会留下
#    孤儿订阅文件。
# 4. 失败按 10s / 20s 退避重试（共 3 次），覆盖代理瞬断与并发推送被拒。
# 5. 无变化不提交：无谓的空提交会让仓库历史变成噪音。
set -u

log() { echo "[publish] $*"; }
err() { echo "[publish] $*" >&2; }

GIT_PUSH_ENABLED="${GIT_PUSH_ENABLED:-true}"
case "$GIT_PUSH_ENABLED" in
  true | 1 | yes | on) ;;
  *)
    log "GIT_PUSH_ENABLED=$GIT_PUSH_ENABLED，跳过发布"
    exit 0
    ;;
esac

: "${GIT_REPO_URL:?GIT_REPO_URL 未配置（见 .env.example）}"

GIT_BRANCH="${GIT_BRANCH:-main}"
GIT_REMOTE="${GIT_REMOTE:-origin}"
REPO_DIR="${GIT_REPO_DIR:-/cache/repo}"
TARGET_SUBDIR="${GIT_OUTPUT_SUBDIR:-result}"
OUTPUT_DIR="${OUTPUT_DIR:-/output}"
SRC_DIR="${OUTPUT_DIR}"
RETRY_MAX="${GIT_RETRY_MAX:-3}"
RETRY_DELAY="${GIT_RETRY_BASE_DELAY:-10}"
AUTHOR_NAME="${GIT_AUTHOR_NAME:-cf-ip-scanner-bot}"
AUTHOR_EMAIL="${GIT_AUTHOR_EMAIL:-cf-ip-scanner-bot@users.noreply.github.com}"

if [ ! -d "$SRC_DIR" ]; then
  err "产物目录不存在: $SRC_DIR"
  exit 1
fi

# 至少要有一个 txt，否则说明上游产物异常，不应把空目录同步进仓库。
has_txt=false
for f in "$SRC_DIR"/*.txt; do
  [ -e "$f" ] && has_txt=true && break
done
if [ "$has_txt" != "true" ]; then
  err "产物目录没有 txt 文件: $SRC_DIR"
  exit 1
fi

# ---- 令牌注入（只在本次进程的 git 配置里生效，不落盘） ----
# 仅 HTTP(S) 远端需要令牌；本地路径 / file:// 远端不注入，便于离线验证。
case "$GIT_REPO_URL" in
  http://* | https://*)
    : "${GIT_TOKEN:?GIT_TOKEN 未配置：HTTP(S) 远端需要具备 contents:write 权限的令牌（见 .env.example）}"
    BASIC_AUTH="$(printf 'x-access-token:%s' "$GIT_TOKEN" | base64 | tr -d '\n')"
    export GIT_CONFIG_COUNT=1
    export GIT_CONFIG_KEY_0="http.extraheader"
    export GIT_CONFIG_VALUE_0="AUTHORIZATION: basic ${BASIC_AUTH}"
    ;;
  *)
    log "远端非 HTTP(S)，跳过令牌注入"
    ;;
esac

git_q() { git -C "$REPO_DIR" "$@"; }

sync_repo() {
  if [ ! -d "$REPO_DIR/.git" ]; then
    mkdir -p "$REPO_DIR" || return 1
    git -C "$REPO_DIR" init --quiet || return 1
    log "初始化发布目录 ${REPO_DIR}"
  fi

  if git_q remote get-url "$GIT_REMOTE" >/dev/null 2>&1; then
    git_q remote set-url "$GIT_REMOTE" "$GIT_REPO_URL" || return 1
  else
    git_q remote add "$GIT_REMOTE" "$GIT_REPO_URL" || return 1
  fi

  # 每次只取最新一个提交 + 重置到远端：仓库里历史产物再多也不累积到本地。
  if fetch_err=$(git_q fetch --quiet --depth 1 "$GIT_REMOTE" "$GIT_BRANCH" 2>&1); then
    git_q checkout --quiet -B "$GIT_BRANCH" FETCH_HEAD || return 1
  else
    case "$fetch_err" in
      *"couldn't find remote ref"* | *"could not find remote ref"*)
        # 远端还没有该分支（新建的空仓库 / 首次发布）：提交时会创建分支
        log "远端分支 ${GIT_BRANCH} 不存在，按首次发布处理"
        git_q checkout --quiet -B "$GIT_BRANCH" 2>/dev/null || true
        ;;
      *)
        # 网络/鉴权问题：交由外层重试，不要在这里造一个空仓库
        err "拉取远端失败：${fetch_err}"
        return 1
        ;;
    esac
  fi

  git_q config user.name "$AUTHOR_NAME" || return 1
  git_q config user.email "$AUTHOR_EMAIL" || return 1
}

mirror_outputs() {
  dest="${REPO_DIR}/${TARGET_SUBDIR}"
  mkdir -p "$dest" || return 1
  # 先清掉上一轮留下的产物，再拷本轮全部文件（镜像语义）
  find "$dest" -maxdepth 1 -type f \( -name '*.txt' -o -name '*.csv' \) -exec rm -f {} + || return 1
  cp -f "$SRC_DIR"/*.txt "$SRC_DIR"/*.csv "$dest"/ 2>/dev/null || cp -f "$SRC_DIR"/*.txt "$dest"/ || return 1
}

commit_and_push() {
  git_q add -A -- "$TARGET_SUBDIR" || return 1
  if git_q diff --cached --quiet; then
    log "产物无变化，跳过提交"
    return 0
  fi
  git_q commit --quiet -m "top cf ips scanned $(TZ="${TZ:-UTC}" date '+%Y-%m-%d %H:%M') [skip ci]" || return 1
  # [skip ci] 抑制产物提交触发本仓库 CI；数据提交没有代码含义。
  git_q push --quiet "$GIT_REMOTE" "HEAD:${GIT_BRANCH}"
}

attempt=1
delay="$RETRY_DELAY"
while :; do
  if sync_repo && mirror_outputs && commit_and_push; then
    log "发布成功: ${GIT_REPO_URL} ${GIT_BRANCH}:${TARGET_SUBDIR}/（$(ls "$SRC_DIR"/*.txt 2>/dev/null | wc -l | tr -d ' ') 个 txt）"
    exit 0
  fi
  if [ "$attempt" -ge "$RETRY_MAX" ]; then
    err "发布失败：已尝试 ${attempt} 次。检查 GIT_REPO_URL / GIT_TOKEN 权限（contents:write）、网络与代理；产物仍保留在 ${SRC_DIR}"
    exit 1
  fi
  err "第 ${attempt} 次发布失败，${delay}s 后重试"
  sleep "$delay"
  attempt=$((attempt + 1))
  delay=$((delay * 2))
done
