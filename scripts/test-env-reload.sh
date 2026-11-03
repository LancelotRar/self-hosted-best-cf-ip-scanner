#!/bin/sh
# 在 CI 的 image-smoke job 里验证「`.env` 是唯一配置源、每轮重读」。
#
# 步骤：备份宿主 .env -> 写入 MAX_CANDIDATES=1 -> 容器内 print-config 断言 1
#       -> apply-config.sh 断言退出 0 -> 恢复 .env。
# 任一步失败都会 trap 恢复原文件，避免污染工作区。
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ENV_FILE="${ENV_FILE:-.env}"
BACKUP="$(mktemp)"
if [ -f "$ENV_FILE" ]; then
  cp "$ENV_FILE" "$BACKUP"
fi
restore() {
  if [ -s "$BACKUP" ]; then
    cp "$BACKUP" "$ENV_FILE"
  fi
  rm -f "$BACKUP"
}
trap restore EXIT

# 只改一个键，其余保持测试环境
if grep -q '^MAX_CANDIDATES=' "$ENV_FILE" 2>/dev/null; then
  sed -i 's|^MAX_CANDIDATES=.*|MAX_CANDIDATES=1|' "$ENV_FILE"
else
  printf 'MAX_CANDIDATES=1\n' >> "$ENV_FILE"
fi

value="$(docker compose exec -T scanner python /usr/local/bin/print-config.py --json \
  | python -c 'import json,sys; print(json.load(sys.stdin)["MAX_CANDIDATES"]["value"])')"
if [ "$value" != "1" ]; then
  echo "print-config 读到 MAX_CANDIDATES=$value，期望 1" >&2
  exit 1
fi

docker compose exec -T scanner /usr/local/bin/apply-config.sh
echo "env reload ok: MAX_CANDIDATES=1"
