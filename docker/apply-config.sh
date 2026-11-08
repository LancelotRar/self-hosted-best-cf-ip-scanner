#!/bin/sh
# 渲染 crontab -> 校验 -> 热重载。
#
# 退出码：
#   0  已应用，或渲染结果与当前一致（无需变更）
#   1  渲染/校验失败；旧 crontab 保持不变，调度器继续按旧表运行
#
# 面板保存 CRON_SCHEDULE 后会主动调用本脚本；运行配置由面板写入
# `/scanner-config/runtime.json`，不存在手工编辑路径。
set -u

export RUNTIME_CONFIG_PATH="${RUNTIME_CONFIG_PATH:-/scanner-config/runtime.json}"
EXPORT_RUNTIME="${EXPORT_RUNTIME:-/usr/local/bin/export-runtime.py}"
CRONTAB_TEMPLATE="${CRONTAB_TEMPLATE:-/etc/supercronic/crontab.template}"
CRONTAB_PATH="${CRONTAB_PATH:-/tmp/supercronic.crontab}"

log() { echo "[apply-config] $(date '+%Y-%m-%d %H:%M:%S %Z') $*"; }

# 面板通过 docker exec 以 root 调用；/tmp 是 sticky，而 crontab 属主是业务用户，
# root 直接覆盖会被 EPERM 拒绝。先按容器环境的 PUID/PGID 降权，与扫描任务一致。
if [ "$(id -u)" = "0" ]; then
  exec su-exec "${PUID:-1000}:${PGID:-1000}" "$0" "$@"
fi

if ! exports="$(python "$EXPORT_RUNTIME" --keys CRON_SCHEDULE)"; then
  log "[错误] 读取运行配置失败，保留旧 crontab"
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

if ! mv "$new_path" "$CRONTAB_PATH"; then
  log "[错误] 无法替换 crontab（权限不足？），保留旧 crontab"
  rm -f "$new_path"
  exit 1
fi
log "已应用 CRON_SCHEDULE='${CRON_SCHEDULE}'"
# supercronic 的 crontab 重载信号是 SIGUSR2（SIGHUP 会终止 PID 1 → 容器重启）
if ! kill -USR2 1 2>/dev/null; then
  log "SIGUSR2 未送达（可能不在容器内）；新 crontab 已写入，下次启动生效"
fi
exit 0
