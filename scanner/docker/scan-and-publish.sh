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
# 降权，免得产物被写成 root 属主。运行身份属于部署参数，来自容器环境。
if [ "$(id -u)" = "0" ]; then
  exec su-exec "${PUID:-1000}:${PGID:-1000}" "$0" "$@"
fi

# 每轮都重新读运行配置投影：扫描进程与 git/curl 子进程都能拿到最新值。
# 已存在的非空环境变量优先，不覆盖本轮显式覆盖。
export RUNTIME_CONFIG_PATH="${RUNTIME_CONFIG_PATH:-/scanner-config/runtime.json}"
if ! runtime_exports="$(python "${EXPORT_RUNTIME:-/usr/local/bin/export-runtime.py}")"; then
  echo "[job] 读取运行配置失败，本轮跳过"
  exit 1
fi
eval "$runtime_exports"

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

# 轮次记录（权威来源）：/data/runtime/runs.tsv，面板只读。
# START/END 成对写入；只有 START 说明这一轮被中断（容器停止/被杀），不猜结束时间。
RUNS_FILE="${RUNS_FILE:-${DATA_DIR:-/data}/runtime/runs.tsv}"
RUN_ID="${RUN_ID:-$(date +%Y%m%dT%H%M%S-$$)}"
RUN_TRIGGER="${RUN_TRIGGER:-cron}"
SUMMARY_COMMAND="${SUMMARY_COMMAND:-/usr/local/bin/startup-report.py}"
mkdir -p "$(dirname "$RUNS_FILE")" 2>/dev/null || true

utc_now() { date -u +%Y-%m-%dT%H:%M:%SZ; }
record_start() {
  printf 'START\t%s\t%s\t%s\t\t\t\t\n' "$RUN_ID" "$RUN_TRIGGER" "$(utc_now)" \
    >> "$RUNS_FILE" 2>/dev/null || true
}
record_end() {
  printf 'END\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$RUN_ID" "$RUN_TRIGGER" "$(utc_now)" "$1" "$2" "$3" "$4" \
    >> "$RUNS_FILE" 2>/dev/null || true
}

# 每轮打印一行生效参数摘要，便于确认面板参数已生效（不含敏感值）。
summary="$(python "$SUMMARY_COMMAND" --short 2>/dev/null | head -n 1 | tr '\t\n' '  ')" || summary=""

start=$(date +%s)
log "==================== 新一轮开始 ===================="
record_start
log "生效参数: ${summary:-<不可用>}"
log "开始扫描"

if PYTHONPATH="$APP_DIR" python -m scanner; then
  log "扫描成功，耗时 $(( $(date +%s) - start ))s"
else
  rc=$?
  record_end "$rc" "" "$(( $(date +%s) - start ))" "扫描失败"
  log "扫描失败（退出码 $rc）：本轮不发布，保留上一次有效产物"
  exit "$rc"
fi

if "$PUBLISH_SCRIPT"; then
  record_end 0 0 "$(( $(date +%s) - start ))" "完成"
  log "本轮完成，总耗时 $(( $(date +%s) - start ))s"
  exit 0
else
  rc=$?
  record_end 0 "$rc" "$(( $(date +%s) - start ))" "发布失败"
  log "发布失败（退出码 $rc）：产物已在本地 /output，目标仓库保持原样"
  exit "$rc"
fi
