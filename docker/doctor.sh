#!/bin/sh
# 只读自检：把"提 issue 需要的环境与连通性信息"一次性打印出来。
#
#   docker compose exec scanner /usr/local/bin/doctor.sh
#
# 不写产物、不改配置；输出可直接贴进 issue（先把令牌等敏感信息删掉）。
set -u

section() { printf '\n===== %s =====\n' "$1"; }

section "生效配置"
python /usr/local/bin/startup-report.py || echo "(配置报告失败)"

section "网络与连通性"
python - <<'PY' || echo "(连通性检查失败)"
import http.client
import os
import socket
import subprocess

PROBE_HOST = os.environ.get("PROBE_HOST", "").strip()
PROBE_PATH = os.environ.get("PROBE_PATH", "/cdn-cgi/trace")
proxy_enabled = any(
    os.environ.get(name)
    for name in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy")
)

print(f"探测域名: {PROBE_HOST or '<未配置>'}")
print(f"代理环境: {'已配置' if proxy_enabled else '未配置'}")

# 1) DNS
if PROBE_HOST:
    try:
        infos = socket.getaddrinfo(PROBE_HOST, 443, proto=socket.IPPROTO_TCP)
        addrs = sorted({item[4][0] for item in infos})
        print(f"DNS     : 解析成功 {', '.join(addrs[:4])}")
    except OSError as exc:
        print(f"DNS     : 解析失败 {type(exc).__name__}: {exc}")

    # 2) trace 端点（默认路径，可能经过代理）
    url = f"https://{PROBE_HOST}{PROBE_PATH}"
    try:
        import urllib.request

        with urllib.request.urlopen(url, timeout=15) as resp:  # noqa: S310 - 固定使用 https
            body = resp.read(400).decode("utf-8", "replace")
        print(f"trace(默认路径): HTTP {resp.status}")
        print("        " + " | ".join(body.splitlines()[:4]))
    except Exception as exc:  # noqa: BLE001 - 自检要报告任何失败
        print(f"trace(默认路径): 失败 {type(exc).__name__}: {exc}")

    # 3) trace 端点（强制直连：http.client 不读代理环境变量）
    try:
        conn = http.client.HTTPSConnection(PROBE_HOST, 443, timeout=15)
        conn.request("GET", PROBE_PATH, headers={"User-Agent": "best-cf-ip-scanner-doctor"})
        resp = conn.getresponse()
        body = resp.read(300).decode("utf-8", "replace")
        print(f"trace(强制直连): HTTP {resp.status}")
        print("        " + " | ".join(body.splitlines()[:4]))
        conn.close()
    except Exception as exc:  # noqa: BLE001
        print(f"trace(强制直连): 失败 {type(exc).__name__}: {exc}")

# 4) 候选 IP 抽样 TCP 握手
input_path = os.path.join(os.environ.get("DATA_DIR", "/data"), os.environ.get("LIBRARY_FILE", "ip-library.txt"))
targets = []
try:
    with open(input_path, encoding="utf-8-sig", errors="ignore") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or ":" in line:
                continue
            targets.append(line)
            if len(targets) >= 3:
                break
except OSError as exc:
    print(f"IP 库    : 读取失败 {exc}")

for entry in targets:
    target = entry.split("/")[0]
    try:
        with socket.create_connection((target, 443), timeout=5):
            print(f"TCP 443 : {target} 握手成功")
    except OSError as exc:
        print(f"TCP 443 : {target} 失败 {type(exc).__name__}: {exc}")

# 5) 发布目标可达性
repo = os.environ.get("GIT_REPO_URL", "").strip()
if not repo:
    print("发布目标: 未配置（GIT_REPO_URL 为空）")
else:
    token = os.environ.get("GIT_TOKEN", "")
    env = dict(os.environ)
    if token and repo.startswith(("http://", "https://")):
        import base64

        basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        env.update(
            GIT_CONFIG_COUNT="1",
            GIT_CONFIG_KEY_0="http.extraheader",
            GIT_CONFIG_VALUE_0=f"AUTHORIZATION: basic {basic}",
        )
    elif not token and repo.startswith(("http://", "https://")):
        print("提示    : GIT_TOKEN 未配置，HTTPS 远端可能匿名失败")
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--heads", repo],
            capture_output=True, text=True, timeout=30, env=env, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"发布目标: git ls-remote 无法执行 {type(exc).__name__}: {exc}")
    else:
        if result.returncode == 0:
            print(f"发布目标: git ls-remote 成功 {repo}")
        else:
            print(f"发布目标: git ls-remote 失败 {repo}")
            detail = (result.stderr or "").strip().splitlines()
            if detail:
                print(f"        {detail[-1]}")
PY

section "IP 库"
python - <<'PY'
import datetime
import os
import sys
from pathlib import Path

data_dir = Path(os.environ.get("DATA_DIR", "/data"))
name = os.environ.get("LIBRARY_FILE", "ip-library.txt")
path = data_dir / name

print(f"路径: {path}")
if not path.is_file():
    print("状态: 不存在（扫描会直接失败，请检查挂载目录与 LIBRARY_FILE）")
    raise SystemExit(0)

lines = path.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
comments = sum(1 for line in lines if line.strip().startswith("#"))
blank = sum(1 for line in lines if not line.strip())
print(f"总行数: {len(lines)}  注释行: {comments}  空行: {blank}")

try:
    sys.path.insert(0, "/app")
    from scanner.ippool import read_library

    networks, fixed, skipped = read_library(path)
    print(f"可解析: {len(networks)} 个网段 + {len(fixed)} 个 ip:port 固定条目  跳过非法行: {skipped}")
    if networks:
        print(f"首条: {networks[0]}   末条: {networks[-1]}")
except Exception as exc:  # noqa: BLE001 - 自检要报告任何异常
    print(f"解析失败: {type(exc).__name__}: {exc}")

stat = path.stat()
mtime = datetime.datetime.fromtimestamp(stat.st_mtime)
print(f"修改时间: {mtime:%Y-%m-%d %H:%M:%S}  大小: {stat.st_size} B")
print("改动在下一轮扫描自动生效，不需要重启容器或重建镜像")
PY

section "磁盘与权限"
for dir in /output /cache /data; do
  if [ -d "$dir" ]; then
    printf '%-6s %s  剩余 %s\n' "$dir" "$([ -w "$dir" ] && echo 可写 || echo 不可写)" \
      "$(df -h "$dir" 2>/dev/null | awk 'NR==2{print $4}')"
  else
    printf '%-6s 不存在\n' "$dir"
  fi
done

section "进程与调度"
if pidof supercronic >/dev/null 2>&1; then
  echo "supercronic 运行中 (pid: $(pidof supercronic))"
else
  echo "supercronic 未运行"
fi
echo "容器时间: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "输出目录内容:"
ls -l /output 2>/dev/null | head -10 || echo "  (还没有产物，等第一轮扫描完成)"

printf '\n把以上输出（可脱敏）附在 issue 里即可。\n'
