#!/bin/sh
# 一轮任务：扫描 -> 成功则发布产物。
#
# 退出码语义（与扫描器一致，供 supercronic 记录、供运维判断）：
#   0  扫描成功且发布成功（或发布被显式关闭）
#   非 0 扫描或发布失败；本轮未产出 → 目标仓库保留上一次有效产物
#
# 不用 set -e：需要区分"扫描失败"与"发布失败"，并把各自的退出码原样传出。
set -u

# 手动 `docker compose exec` / `run` 进来时当前用户可能是 root：与定时任务一致地
# 降权，免得产物被写成 root 属主。
if [ "$(id -u)" = "0" ]; then
  exec su-exec "${PUID:-1000}:${PGID:-1000}" "$0" "$@"
fi

# 每轮都重新读 `.env`：扫描进程与 git/curl 子进程都能拿到最新值。
# 已存在的非空环境变量优先，不覆盖本轮显式覆盖。
PROJECT_DIR="${PROJECT_DIR:-/project}"
export DOTENV_PATH="${DOTENV_PATH:-$PROJECT_DIR/.env}"
if ! dotenv_exports="$(python "${EXPORT_DOTENV:-/usr/local/bin/export-dotenv.py}")"; then
  echo "[job] 读取 .env 失败，本轮跳过"
  exit 1
fi
eval "$dotenv_exports"

# 单实例锁：定时任务与 `scan-once` 可能同时被触发，两轮并发会互相清空产物目录。
# 拿不到锁说明已有一轮在跑，直接跳过（不算失败）。
LOCK_FILE="${SCAN_LOCK_FILE:-/cache/scan.lock}"
if ! exec 9>"$LOCK_FILE" 2>/dev/null; then
  echo "[job] 无法创建锁文件 $LOCK_FILE，跳过加锁继续执行"
elif ! flock -n 9; then
  echo "[job] 已有一轮扫描在运行，本次跳过（避免并发写产物）"
  exit 0
fi

APP_DIR="${APP_DIR:-/app}"
PUBLISH_SCRIPT="${PUBLISH_SCRIPT:-/usr/local/bin/publish.sh}"

log() { echo "[job] $(date '+%Y-%m-%d %H:%M:%S %Z') $*"; }

start=$(date +%s)
log "==================== 新一轮开始 ===================="
log "开始扫描"

if python "$APP_DIR/best_cf_ip_scanner.py"; then
  log "扫描成功，耗时 $(( $(date +%s) - start ))s"
else
  rc=$?
  log "扫描失败（退出码 $rc）：本轮不发布，保留上一次有效产物"
  exit "$rc"
fi

if "$PUBLISH_SCRIPT"; then
  log "本轮完成，总耗时 $(( $(date +%s) - start ))s"
  exit 0
else
  rc=$?
  log "发布失败（退出码 $rc）：产物已在本地 /output，目标仓库保持原样"
  exit "$rc"
fi
