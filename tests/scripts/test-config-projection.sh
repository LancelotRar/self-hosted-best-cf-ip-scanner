#!/bin/sh
# 在 CI 的 image-smoke job 里验证「面板数据库 → 运行配置投影 → 扫描器每轮重读」。
#
# 步骤：通过 panel 容器写入 SAMPLE_STRIDE=512 并重投影
#       -> 扫描器内 print-config 断言 512
#       -> apply-config.sh 断言退出 0
#       -> 清除覆盖，恢复默认。
# 任一步失败都会 trap 恢复，避免污染测试栈。
set -eu

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

panel_set() {
  docker compose exec -T panel python - "$1" <<'PY'
import sys

from panel import db, settings_store
from panel.settings import Settings

settings = Settings.from_env()
conn = db.connect(settings.db_path)
try:
    with conn:
        settings_store.apply_overrides(
            conn, settings, {"SAMPLE_STRIDE": sys.argv[1]}, actor="ci"
        )
        settings_store.project(conn, settings)
finally:
    conn.close()
PY
}

restore() {
  panel_set "" >/dev/null 2>&1 || true
}
trap restore EXIT

panel_set 512

value="$(docker compose exec -T scanner python /usr/local/bin/print-config.py --json \
  | python -c 'import json,sys; print(json.load(sys.stdin)["SAMPLE_STRIDE"]["value"])')"
if [ "$value" != "512" ]; then
  echo "print-config 读到 SAMPLE_STRIDE=$value，期望 512" >&2
  exit 1
fi

docker compose exec -T scanner /usr/local/bin/apply-config.sh
echo "config projection reload ok: SAMPLE_STRIDE=512"
