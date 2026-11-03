"""打印"本轮生效配置"摘要 —— 启动自检与 issue 诊断共用。

设计原则：
- 只读 scanner.config（环境变量 + 默认值的唯一解析处），所以报告内容
  不可能与真实运行参数漂移；
- 不输出任何敏感值：令牌只报"是否配置"，代理地址做脱敏，探测域名照常显示
  （它是使用者自己的域名，且是排障必需信息）。

用法：python /usr/local/bin/startup-report.py
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, "/app")

from curl_cffi import __version__ as curl_cffi_version  # noqa: E402

from scanner import config  # noqa: E402
from scanner.ippool import read_library  # noqa: E402
from scanner.locations import load_locations  # noqa: E402

PROXY_VARS = ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy")


def _mask_proxy(raw: str) -> str:
    """隐藏代理 URL 里的账号密码，只保留 scheme://host:port。"""
    scheme, _, rest = raw.partition("://")
    if not rest:
        return "<已配置,格式未识别>"
    host = rest.rsplit("@", 1)[-1]
    return f"{scheme}://{host}"


def _yes_no(value: bool) -> str:
    return "是" if value else "否"


def short_report() -> str:
    """一行生效参数摘要，写进轮次记录（不含敏感值）。"""
    ports = ",".join(str(port) for port in config.PROBE_PORTS)
    tops = ",".join(str(top) for top in config.OVERALL_TOPS) or "-"
    push = (os.environ.get("GIT_PUSH_ENABLED") or "false").strip().lower() in {
        "true",
        "1",
        "yes",
        "on",
    }
    return (
        f"PROBE_HOST={config.PROBE_HOST or '-'} ports={ports} "
        f"concurrency={config.PROBE_CONCURRENCY} max={config.MAX_CANDIDATES} "
        f"tops={tops} push={'on' if push else 'off'}"
    )


def _count_segments(path: Path) -> str:
    try:
        networks, fixed, skipped = read_library(path)
    except OSError as exc:
        return f"无法读取({exc})"
    return f"{len(networks)} 个网段 + {len(fixed)} 个 ip:port 固定条目, 跳过 {skipped} 行"


def _no_proxy_exempts(host: str) -> bool:
    entries = [
        item.strip().lstrip(".").lower()
        for item in (os.environ.get("NO_PROXY") or os.environ.get("no_proxy") or "").split(",")
        if item.strip()
    ]
    lowered = host.lower()
    return any(e == "*" or lowered == e or lowered.endswith("." + e) for e in entries)


def main() -> int:
    parser = argparse.ArgumentParser(description="打印本轮生效配置")
    parser.add_argument(
        "--short", action="store_true", help="只输出一行摘要（写轮次记录用）"
    )
    args = parser.parse_args()
    if args.short:
        print(short_report())
        return 0

    now = datetime.now(timezone.utc) + timedelta(hours=8)
    data_dir = Path(config.DATA_DIR)
    input_path = data_dir / config.LIBRARY_FILE
    locations_path = data_dir / config.LOCATIONS_FILE
    output_dir = Path(config.OUTPUT_DIR)
    # 产物目录要到第一轮扫描才创建，启动自检要报告"父目录可写"才有意义
    writable_dir = output_dir.parent if not output_dir.exists() else output_dir

    print("=" * 72)
    print("best-cf-ip-scanner 生效配置")
    print("=" * 72)
    print(f"时间            : {now:%Y-%m-%d %H:%M:%S} (UTC+8, TZ={os.environ.get('TZ', '未设置')})")
    print(f"版本            : python {sys.version.split()[0]} / curl_cffi {curl_cffi_version} "
          f"/ supercronic {os.environ.get('SUPERCRONIC_VERSION', '未知')}")
    print(f"探测端点        : PROBE_HOST={config.PROBE_HOST or '<未配置>'}  PROBE_PATH={config.PROBE_PATH}")
    print(f"探测端口        : {','.join(str(p) for p in config.PROBE_PORTS)}")
    print(f"探测参数        : 并发 {config.PROBE_CONCURRENCY}  "
          f"握手 {config.TCP_ATTEMPTS} 次/需成功 {config.TCP_MIN_SUCCESS} 次/超时 {config.TCP_TIMEOUT}s  "
          f"端点校验 {config.TRACE_ATTEMPTS} 次/超时 {config.TRACE_TIMEOUT}s")
    print(f"采样            : 每 {config.SAMPLE_STRIDE} 个地址 1 个  上限 {config.MAX_CANDIDATES}"
          f"(0=不限)  基础种子 {config.SAMPLE_SEED}")
    print(f"数据目录        : {data_dir}")
    print(f"  {input_path.name:<18}: {'存在' if input_path.is_file() else '缺失'}  {_count_segments(input_path)}")
    print(f"  {locations_path.name:<18}: {'存在' if locations_path.is_file() else '缺失'}  "
          f"{len(load_locations(locations_path))} 条机房映射")
    print(f"输出目录        : {output_dir}  (可写: {_yes_no(os.access(writable_dir, os.W_OK))})")

    configured = [name for name in PROXY_VARS if os.environ.get(name)]
    if configured:
        print(f"代理            : 已启用 {_mask_proxy(os.environ[configured[0]])}  "
              f"NO_PROXY 豁免探测域名: {_yes_no(_no_proxy_exempts(config.PROBE_HOST)) if config.PROBE_HOST else '不适用'}")
        if not _no_proxy_exempts(config.PROBE_HOST):
            print("                  警告: 未豁免探测域名时钉 IP 会被代理绕过, 结果无效(启动会被拒绝)")
    else:
        print("代理            : 未启用(直连)")

    publish = (os.environ.get("GIT_PUSH_ENABLED") or "true").lower() in {"true", "1", "yes", "on"}
    token = os.environ.get("GIT_TOKEN") or ""
    print(f"产物发布        : {'开启' if publish else '关闭'}  "
          f"{os.environ.get('GIT_REPO_URL') or '<未配置仓库>'}@"
          f"{os.environ.get('GIT_BRANCH') or 'main'}:{os.environ.get('GIT_OUTPUT_SUBDIR') or 'result'}/"
          f"  令牌: {'已配置' if token else '未配置'}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
