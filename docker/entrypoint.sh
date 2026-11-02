#!/bin/sh
# 容器入口：准备挂载目录 -> 播种内置数据 -> 降权 -> 渲染 crontab -> 交给 supercronic。
#
# 设计取舍：
# - 以 root 启动只为两件事：把 bind mount 进来的宿主目录对齐到 PUID/PGID、
#   首次启动把镜像内置的 IP 库写进 /data。之后立刻 su-exec 降权，业务进程
#   全程非 root；
# - 调度交给 supercronic 而不是自己写 sleep 循环：保留标准 cron 语义（"每 6 小时
#   的第 30 分"这类精确时点），日志、信号、作业不重叠都由它处理；
# - exec 让 supercronic 成为 PID 1，docker stop 的 SIGTERM 才能被优雅处理；
# - 渲染结果写 /tmp：容器以只读根文件系统运行，/etc 不可写。
set -eu

PUID="${PUID:-1000}"
PGID="${PGID:-1000}"
DATA_DIR="${DATA_DIR:-/data}"
OUTPUT_DIR="${OUTPUT_DIR:-/output}"
STATE_DIR="${STATE_DIR:-/cache}"
DEFAULT_DATA_DIR="${DEFAULT_DATA_DIR:-/opt/default-data}"

CRON_SCHEDULE="${CRON_SCHEDULE:-30 */6 * * *}"
RUN_ON_START="${RUN_ON_START:-false}"
CRONTAB_TEMPLATE="${CRONTAB_TEMPLATE:-/etc/supercronic/crontab.template}"
CRONTAB_PATH="${CRONTAB_PATH:-/tmp/supercronic.crontab}"

log() { echo "[entrypoint] $*"; }

# ---------------------------------------------------------------- 特权阶段 --
if [ "$(id -u)" = "0" ]; then
  mkdir -p "$DATA_DIR" "$OUTPUT_DIR" "$STATE_DIR"

  # 首次启动：把镜像内置的 IP 库/IATA 映射播种到 /data。
  # 已存在的文件不覆盖 —— 用户改过的库在容器重建后必须保留。
  seeded=0
  if [ -d "$DEFAULT_DATA_DIR" ]; then
    for src in "$DEFAULT_DATA_DIR"/*; do
      [ -e "$src" ] || continue
      dest="$DATA_DIR/$(basename "$src")"
      if [ ! -e "$dest" ]; then
        cp "$src" "$dest"
        seeded=$((seeded + 1))
      fi
    done
  fi
  if [ "$seeded" -gt 0 ]; then
    log "已写入内置默认数据文件 ${seeded} 个 -> ${DATA_DIR}（后续可直接编辑维护）"
  fi

  # bind mount 的宿主目录由 Docker 以 root 创建，播种的文件也是 root 属主；
  # 统一对齐到 PUID:PGID，用户不需要在宿主机上手工 chown。
  # 放在播种之后，保证新写入的文件也归属业务用户。挂只读时忽略失败。
  chown -R "$PUID:$PGID" "$DATA_DIR" "$OUTPUT_DIR" "$STATE_DIR" 2>/dev/null || true

  # 降权后重新进入本脚本；此时 id -u != 0，走下面的普通路径。
  exec su-exec "$PUID:$PGID" "$0" "$@"
fi

# -------------------------------------------------------------- 普通用户阶段 --
log "启动 $(date '+%Y-%m-%d %H:%M:%S %Z')"

# 配置不合法就不进入调度：容器会按重启策略重试，日志里能直接看到原因。
python /usr/local/bin/check-config.py
python /usr/local/bin/startup-report.py
log "调度: CRON_SCHEDULE='${CRON_SCHEDULE}'  RUN_ON_START=${RUN_ON_START}"

# 目录可写性前置检查：即使降权失败也能给出可复制的修复命令，
# 比让它跑成 Python 的 traceback 有用得多。
ensure_writable() {
  if ! mkdir -p "$1" 2>/dev/null || [ ! -w "$1" ]; then
    log "[错误] 目录不可写: $1"
    log "        请确认它已挂载且属主为 ${PUID}:${PGID}，例如："
    log "          sudo chown -R ${PUID}:${PGID} ./data ./output ./cache"
    exit 1
  fi
}
ensure_writable "$OUTPUT_DIR"
ensure_writable "$STATE_DIR"

sed "s|@CRON_SCHEDULE@|${CRON_SCHEDULE}|" "$CRONTAB_TEMPLATE" > "$CRONTAB_PATH"

# 语法错误在启动期暴露：容器直接退出并重启，日志里能看到原因，
# 而不是带着一个永不触发的调度器"看起来健康"地空转。
supercronic -test "$CRONTAB_PATH"

if [ "$RUN_ON_START" = "true" ]; then
  # 放到后台执行：让 supercronic 立刻成为 PID 1 并接管信号，
  # 否则 docker stop 期间 shell 卡在这轮扫描上，TERM 无法传递（要等满宽限期才被杀）。
  # 首轮与后续调度共用同一把锁，不会并发。
  log "RUN_ON_START=true，后台执行一轮（与调度共用锁）"
  /usr/local/bin/scan-and-publish.sh &
fi

log "进入调度"
exec supercronic -split-logs "$CRONTAB_PATH"
