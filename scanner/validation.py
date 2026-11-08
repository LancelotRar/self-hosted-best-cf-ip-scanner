"""配置校验：集中拦截"会静默产出废结果"的配置。

校验分两层：

1. 语法层（类型/格式错误）在 `scanner.config` 导入时即终止进程，例如
   `PROBE_CONCURRENCY=abc`、`OVERALL_TOPS=abc`、`PROBE_PORTS=abc`。
2. 语义层（越界、必填缺失、代理未豁免）由本模块检查。调用点有两处：
   - 容器启动时 `docker/check-config.py`：不通过就不进入调度；
   - 每轮任务开始时 `run()`：再查一次，避免运行期被外部改动绕过。

这样两类错误都在"能立刻看见"的时机失败，而不是等到 6 小时后产出一批怪数据。
"""

from __future__ import annotations

import os
from collections.abc import Mapping

# 会被 curl_cffi 等客户端读取的代理环境变量
PROXY_VARS = (
    "HTTP_PROXY",
    "http_proxy",
    "HTTPS_PROXY",
    "https_proxy",
    "ALL_PROXY",
    "all_proxy",
)


def numeric_problems(
    *,
    concurrency: int,
    trace_timeout: int,
    sample_stride: int,
    tcp_attempts: int,
    tcp_min_success: int,
    tcp_timeout: float,
) -> list[str]:
    """校验数值型参数，返回问题描述列表（空 = 合法）。

    这些取值非法时不会抛异常，只会静默异常：`trace_timeout=0` 让 libcurl 无限等待、
    `concurrency<=0` 让线程池崩溃、`tcp_min_success > tcp_attempts` 则永远无法合格。
    """
    problems: list[str] = []
    if trace_timeout < 1:
        problems.append(f"TRACE_TIMEOUT 必须 >= 1 秒（当前 {trace_timeout}）")
    if concurrency < 1:
        problems.append(f"PROBE_CONCURRENCY 必须 >= 1（当前 {concurrency}）")
    if sample_stride < 1:
        problems.append(f"SAMPLE_STRIDE 必须 >= 1（当前 {sample_stride}）")
    if tcp_attempts < 1:
        problems.append(f"TCP_ATTEMPTS 必须 >= 1（当前 {tcp_attempts}）")
    if not 1 <= tcp_min_success <= tcp_attempts:
        problems.append(
            f"TCP_MIN_SUCCESS 必须在 1..{tcp_attempts} 之间（当前 {tcp_min_success}）"
        )
    if tcp_timeout <= 0:
        problems.append(f"TCP_TIMEOUT 必须 > 0（当前 {tcp_timeout}）")
    return problems


def ports_problems(ports: tuple[int, ...]) -> list[str]:
    """校验探测端口集合。空集合会让端口分配在运行期抛 IndexError。"""
    if not ports:
        return ["PROBE_PORTS 不能为空：至少填一个端口，如 443"]
    bad = [port for port in ports if not 1 <= port <= 65535]
    if bad:
        return [f"PROBE_PORTS 含非法端口 {bad}：必须在 1..65535"]
    return []


def top_problems(
    overall_tops: tuple[int, ...], country_enabled: bool, country_tops: dict[str, int]
) -> list[str]:
    """校验订阅条数：负数非法；0 表示不生成该项（合法）。"""
    problems: list[str] = []
    if any(size < 0 for size in overall_tops):
        problems.append(f"OVERALL_TOPS 的条数必须 >= 0（当前 {list(overall_tops)}）")
    if not country_enabled:
        return problems  # 国家列表关闭时，各国数值不参与校验
    for code, size in country_tops.items():
        if size < 0:
            problems.append(f"TOP_{code} 必须 >= 0（当前 {size}；0=不生成）")
    return problems


def list_filename_problems(
    overall_tops: tuple[int, ...],
    country_enabled: bool,
    country_tops: dict[str, int],
    filenames: Mapping[str, str],
    overall_enabled: bool = True,
) -> list[str]:
    """校验自定义列表文件名：不允许路径、空名或重复。"""
    keys = [f"GLOBAL{size}" for size in overall_tops if size > 0] if overall_enabled else []
    if country_enabled:
        keys += [f"{code}{size}" for code, size in country_tops.items() if size > 0]

    problems: list[str] = []
    seen: dict[str, str] = {}
    for key in keys:
        raw = str(filenames.get(key, key)).strip()
        stem = raw[:-4] if raw.lower().endswith(".txt") else raw
        if not stem or any(char in stem for char in ("/", "\\", "\x00")) or ".." in stem:
            problems.append(f"列表 {key} 的文件名非法：{raw!r}")
            continue
        lowered = stem.lower()
        if lowered in seen:
            problems.append(
                f"列表文件名重复：{seen[lowered]} 与 {key} 都使用 {stem}.txt"
            )
        else:
            seen[lowered] = key
    return problems


def probe_host_problems(
    probe_host: str, environ: Mapping[str, str] | None = None
) -> list[str]:
    """校验探测域名与代理豁免，返回问题描述列表（空 = 合法）。

    这两项配错的后果都是"静默跑出一批假优选 IP"，而不是报错：
    - 未配置 PROBE_HOST：请求 URL 退化成 https://:端口/...，必然全灭；
    - 配了出网代理但 NO_PROXY 未豁免该域名：代理的 CONNECT 以域名为目标，
      会绕过 curl RESOLVE 的钉 IP，所有候选实际落到代理出口的同一机房，
      结果看起来正常（curl 全部 200 + colo），但整体无效。
    """
    env = os.environ if environ is None else environ
    host = (probe_host or "").strip()
    if not host:
        return ["未配置 PROBE_HOST（探测域名）：见 docs/deployment.md 与 docs/configuration.md"]
    if "://" in host or "/" in host or ":" in host:
        return [f"PROBE_HOST 只能填域名（不带协议/端口/路径），当前为 {host!r}"]

    if not any(env.get(name) for name in PROXY_VARS):
        return []

    no_proxy = (env.get("NO_PROXY") or env.get("no_proxy") or "").lower()
    entries = [item.strip().lstrip(".") for item in no_proxy.split(",") if item.strip()]
    lowered = host.lower()
    exempt = any(
        entry == "*" or lowered == entry or lowered.endswith("." + entry) for entry in entries
    )
    if exempt:
        return []
    return [
        f"已配置出网代理，但 NO_PROXY 未豁免探测域名 {host}："
        "代理会绕过 curl RESOLVE 的钉 IP，所有候选将落到代理出口的同一机房"
    ]


def startup_problems() -> list[str]:
    """按当前生效配置做一次完整校验（容器启动时调用）。"""
    from . import config

    return (
        numeric_problems(
            concurrency=config.PROBE_CONCURRENCY,
            trace_timeout=config.TRACE_TIMEOUT,
            sample_stride=config.SAMPLE_STRIDE,
            tcp_attempts=config.TCP_ATTEMPTS,
            tcp_min_success=config.TCP_MIN_SUCCESS,
            tcp_timeout=config.TCP_TIMEOUT,
        )
        + ports_problems(config.PROBE_PORTS)
        + top_problems(config.OVERALL_TOPS, config.COUNTRY_FILTERS, config.COUNTRY_TOPS)
        + list_filename_problems(
            config.OVERALL_TOPS,
            config.COUNTRY_FILTERS,
            config.COUNTRY_TOPS,
            config.LIST_FILENAMES,
            config.OVERALL_ENABLED,
        )
        + probe_host_problems(config.PROBE_HOST)
    )
