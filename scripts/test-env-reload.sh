#!/bin/sh
# 在 CI 的 image-smoke job 里验证「`.env` 是唯一配置源、每轮重读」。
#
# 步骤：备份宿主 .env -> 写入 SAMPLE_STRIDE=512 -> 容器内 print-config 断言 512
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
if grep -q '^SAMPLE_STRIDE=' "$ENV_FILE" 2>/dev/null; then
  sed -i 's|^SAMPLE_STRIDE=.*|SAMPLE_STRIDE=512|' "$ENV_FILE"
else
  printf 'SAMPLE_STRIDE=512\n' >> "$ENV_FILE"
fi

value="$(docker compose exec -T scanner python /usr/local/bin/print-config.py --json \
  | python -c 'import json,sys; print(json.load(sys.stdin)["SAMPLE_STRIDE"]["value"])')"
if [ "$value" != "512" ]; then
  echo "print-config 读到 SAMPLE_STRIDE=$value，期望 512" >&2
  exit 1
fi

docker compose exec -T scanner /usr/local/bin/apply-config.sh
echo "env reload ok: SAMPLE_STRIDE=512"
