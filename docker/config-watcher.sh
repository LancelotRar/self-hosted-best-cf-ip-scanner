#!/bin/sh
# 监听 `.env` 变化并热重载调度，兜住"手工编辑 .env"这条备用路径。
#
# 只处理调度：CRON_SCHEDULE 变化后重渲染 crontab 并 SIGHUP；
# PUID/PGID/TZ/RUN_ON_START 属于入口阶段参数，必须重启扫描容器才生效。
# 应用失败只记录日志，不退出——监听要一直活着，等用户修正 .env。
set -u

PROJECT_DIR="${PROJECT_DIR:-/project}"
export DOTENV_PATH="${DOTENV_PATH:-$PROJECT_DIR/.env}"
APPLY_CONFIG="${APPLY_CONFIG:-/usr/local/bin/apply-config.sh}"
WATCH_INTERVAL="${WATCH_INTERVAL:-5}"

log() { echo "[config-watcher] $(date '+%Y-%m-%d %H:%M:%S %Z') $*"; }

last_hash=""
while :; do
  current_hash="$(sha256sum "$DOTENV_PATH" 2>/dev/null | cut -d' ' -f1)"
  if [ "$current_hash" != "$last_hash" ]; then
    # 第一次只记录基线：启动时 crontab 已按 .env 渲染过，无需再应用一次。
    if [ -n "$last_hash" ] && [ -n "$current_hash" ]; then
      log ".env 已变化，应用调度"
      if "$APPLY_CONFIG"; then
        log "调度已重载"
      else
        log "调度重载失败，保留旧 crontab（修正 .env 后会自动重试）"
      fi
    fi
    last_hash="$current_hash"
  fi
  sleep "$WATCH_INTERVAL"
done
