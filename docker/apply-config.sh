#!/bin/sh
# 渲染 crontab -> 校验 -> 热重载。
#
# 退出码：
#   0  已应用，或渲染结果与当前一致（无需变更）
#   1  渲染/校验失败；旧 crontab 保持不变，调度器继续按旧表运行
#
# 面板保存 CRON_SCHEDULE 后会主动调用本脚本；手工改 .env 由 config-watcher.sh 兜底。
set -u

PROJECT_DIR="${PROJECT_DIR:-/project}"
export DOTENV_PATH="${DOTENV_PATH:-$PROJECT_DIR/.env}"
EXPORT_DOTENV="${EXPORT_DOTENV:-/usr/local/bin/export-dotenv.py}"
CRONTAB_TEMPLATE="${CRONTAB_TEMPLATE:-/etc/supercronic/crontab.template}"
CRONTAB_PATH="${CRONTAB_PATH:-/tmp/supercronic.crontab}"

log() { echo "[apply-config] $(date '+%Y-%m-%d %H:%M:%S %Z') $*"; }

if ! exports="$(python "$EXPORT_DOTENV" --keys CRON_SCHEDULE)"; then
  log "[错误] 读取 .env 失败，保留旧 crontab"
  exit 1
fi
eval "$exports"
CRON_SCHEDULE="${CRON_SCHEDULE:-30 */6 * * *}"

new_path="${CRONTAB_PATH}.new"
if ! sed "s|@CRON_SCHEDULE@|${CRON_SCHEDULE}|" "$CRONTAB_TEMPLATE" > "$new_path"; then
  log "[错误] 渲染 crontab 失败，保留旧 crontab"
  rm -f "$new_path"
  exit 1
fi

if [ -f "$CRONTAB_PATH" ] && cmp -s "$new_path" "$CRONTAB_PATH"; then
  rm -f "$new_path"
  log "调度未变化，无需重载"
  exit 0
fi

if ! supercronic -test "$new_path"; then
  log "[错误] supercronic -test 失败，保留旧 crontab"
  rm -f "$new_path"
  exit 1
fi

mv "$new_path" "$CRONTAB_PATH"
log "已应用 CRON_SCHEDULE='${CRON_SCHEDULE}'"
if ! kill -HUP 1 2>/dev/null; then
  log "SIGHUP 未送达（可能不在容器内）；新 crontab 已写入，下次启动生效"
fi
exit 0
