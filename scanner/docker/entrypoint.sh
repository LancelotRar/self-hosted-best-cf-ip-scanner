#!/bin/sh
# 容器入口：准备挂载目录 -> 降权 -> 读取运行配置 -> 渲染 crontab -> 交给 supercronic。
#
# 设计取舍：
# - 应用参数由面板写入 `/scanner-config/runtime.json`；扫描器不读数据库，也不读任何手工配置文件。
# - 以 root 启动只为两件事：把挂载目录对齐到 PUID/PGID（部署参数，来自 compose
#   环境），以及创建缺失的目录。之后立刻 su-exec 降权，业务进程全程非 root；
# - 调度交给 supercronic 而不是自己写 sleep 循环：保留标准 cron 语义（"每 6 小时
#   的第 30 分"这类精确时点），日志、信号、作业不重叠都由它处理；
# - exec 让 supercronic 成为 PID 1，docker stop 的 SIGTERM 才能被优雅处理；
# - 渲染结果写 /tmp：容器以只读根文件系统运行，/etc 不可写。
set -eu

# 面板生成的运行配置投影；面板先于扫描器启动并保证它存在。
export RUNTIME_CONFIG_PATH="${RUNTIME_CONFIG_PATH:-/scanner-config/runtime.json}"
EXPORT_RUNTIME="${EXPORT_RUNTIME:-/usr/local/bin/export-runtime.py}"

log() { echo "[entrypoint] $*"; }

# 与 schema 默认值保持一致：空值 = 未设置 = 用默认值（RUN_ON_START 默认 true）。
is_true() {
  case "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')" in
    1 | true | yes | on) return 0 ;;
    *) return 1 ;;
  esac
}

# 运行身份属于部署参数，只从容器环境读取；配置文件里没有也不应该有 UID/GID。
PUID="${PUID:-1000}"
PGID="${PGID:-1000}"

DATA_DIR="${DATA_DIR:-/data}"
OUTPUT_DIR="${OUTPUT_DIR:-/output}"
STATE_DIR="${STATE_DIR:-/cache}"

# ---------------------------------------------------------------- 特权阶段 --
if [ "$(id -u)" = "0" ]; then
  mkdir -p "$DATA_DIR" "$OUTPUT_DIR" "$STATE_DIR"
  # 定名卷首次创建时属主是 root；统一对齐到 PUID:PGID。挂只读时忽略失败。
  chown -R "$PUID:$PGID" "$DATA_DIR" "$OUTPUT_DIR" "$STATE_DIR" 2>/dev/null || true
  # 降权后重新进入本脚本；此时 id -u != 0，走下面的普通路径。
  exec su-exec "$PUID:$PGID" "$0" "$@"
fi

# -------------------------------------------------------------- 普通用户阶段 --
# 入口阶段只取调度相关键；其余参数由扫描进程每轮自行读取投影。
if ! runtime_exports="$(python "$EXPORT_RUNTIME" --plain --keys TZ,CRON_SCHEDULE,RUN_ON_START)"; then
  log "[错误] 读取运行配置失败（${RUNTIME_CONFIG_PATH}），容器不进入调度"
  exit 1
fi
eval "$runtime_exports"

# 镜像不再写死 TZ：时区由面板参数提供，缺省时退回默认值。
TZ="${TZ:-Asia/Shanghai}"
export TZ
CRON_SCHEDULE="${CRON_SCHEDULE:-30 */6 * * *}"
RUN_ON_START="${RUN_ON_START:-true}"
CRONTAB_TEMPLATE="${CRONTAB_TEMPLATE:-/etc/supercronic/crontab.template}"
CRONTAB_PATH="${CRONTAB_PATH:-/tmp/supercronic.crontab}"

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
    log "        请确认它已挂载且属主为 ${PUID}:${PGID}"
    exit 1
  fi
}
ensure_writable "$OUTPUT_DIR"
ensure_writable "$STATE_DIR"

sed "s|@CRON_SCHEDULE@|${CRON_SCHEDULE}|" "$CRONTAB_TEMPLATE" > "$CRONTAB_PATH"

# 语法错误在启动期暴露：容器直接退出并重启，日志里能看到原因，
# 而不是带着一个永不触发的调度器"看起来健康"地空转。
supercronic -test "$CRONTAB_PATH"

if is_true "$RUN_ON_START"; then
  # 放到后台执行：让 supercronic 立刻成为 PID 1 并接管信号，
  # 否则 docker stop 期间 shell 卡在这轮扫描上，TERM 无法传递（要等满宽限期才被杀）。
  # 首轮与后续调度共用同一把锁，不会并发。
  log "RUN_ON_START=true，后台执行一轮（与调度共用锁）"
  /usr/local/bin/scan-and-publish.sh &
fi

log "进入调度"
exec supercronic -split-logs "$CRONTAB_PATH"
