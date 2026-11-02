"""探测：TCP 握手测量（初筛 + 排名基准）+ 边缘端点校验（终筛）。

两个阶段：
    measure_tcp_batch   对候选做多次 TCP 握手计时，统计成功次数、丢包率与
                        最小/平均/最大往返时延 —— 这是筛选与排名的依据。
                        代理客户端展示的"TCP 延迟"就是该口径，且它比
                        TLS+HTTP 廉价，适合作为第一道粗筛。
    check_endpoints     只对达标者请求一次 PROBE_HOST 的 PROBE_PATH，要求
                        HTTP 200 且响应体含合法 colo：同时完成"是否真 CF
                        边缘""是否 EIV 受限子池""边缘机房代码"三件事。
"""

from __future__ import annotations

import re
import socket
import time
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from curl_cffi import Curl, CurlInfo, CurlOpt
from curl_cffi.curl import CurlError

from .config import (
    PROBE_CONCURRENCY,
    PROBE_HEADERS,
    PROBE_HOST,
    PROBE_PATH,
    TCP_ATTEMPTS,
    TCP_MIN_SUCCESS,
    TCP_TIMEOUT,
    TRACE_ATTEMPTS,
    TRACE_TIMEOUT,
)


@dataclass(frozen=True)
class TcpMetrics:
    """TCP 握手测量的统计结果。

    qualified 表示 success_count >= min_success（相对门槛，不设绝对时延阈值）。
    """

    ip: str
    port: int
    attempts: int
    success_count: int
    loss_rate: float
    min_ms: float | None
    avg_ms: float | None
    max_ms: float | None
    error: str | None
    qualified: bool


@dataclass(frozen=True)
class EndpointResult:
    """一次边缘端点校验的结果。

    error 为 None 且 colo 有效才算通过；ttfb_ms 仅用于排查，不参与排名。
    """

    ttfb_ms: float | None
    colo: str | None
    country: str | None
    error: str | None


@dataclass(frozen=True)
class Candidate:
    """候选的完整判定结果：TCP 握手达标 且 端点校验通过，才算合格。"""

    ip: str
    port: int
    tcp: TcpMetrics
    endpoint: EndpointResult | None
    qualified: bool


def parse_endpoint_body(body: str) -> tuple[str | None, str | None]:
    """解析端点响应体，返回 (边缘机房代码, 客户端国家代码)。

    colo 是 IATA 三字码（如 HKG），loc 是客户端所在国家（如 HK）；
    缺失或格式非法时对应值为 None。
    """
    colo: str | None = None
    country: str | None = None
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("colo="):
            value = stripped[5:]
            colo = value if re.fullmatch(r"[A-Z]{3}", value) else None
        elif stripped.startswith("loc="):
            value = stripped[4:]
            country = value if re.fullmatch(r"[A-Z]{2}", value) else None
    return colo, country


def _getinfo_float(curl: Curl, info: CurlInfo) -> float:
    """读取 curl getinfo 数值并窄化为 float（getinfo 返回宽联合类型）。"""
    value: Any = curl.getinfo(info)
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _getinfo_int(curl: Curl, info: CurlInfo) -> int:
    """读取 curl getinfo 数值并窄化为 int。"""
    value: Any = curl.getinfo(info)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)
    return 0


def _request_endpoint(ip: str, port: int, timeout: int) -> tuple[float | None, int | None, str]:
    """向候选 IP:端口 发起一次 HTTPS 端点校验。

    通过 RESOLVE 把 PROBE_HOST 的解析固定到候选 IP:端口：SNI 与证书校验保持
    有效，而 TCP/TLS 实际拨号到候选地址。返回 (首字节延迟 ms, HTTP 状态码, 响应体)。
    失败时返回 (None, None, 错误信息)。
    """
    buff: list[bytes] = []
    url = f"https://{PROBE_HOST}:{port}{PROBE_PATH}"
    request_headers = [f"{k}: {v}".encode() for k, v in PROBE_HEADERS.items()]
    curl = Curl()
    try:
        curl.setopt(CurlOpt.URL, url)
        curl.setopt(CurlOpt.RESOLVE, [f"{PROBE_HOST}:{port}:{ip}"])
        # 代理隔离由容器侧的 NO_PROXY 域名豁免保证（见 compose.yaml）：
        # 代码不做代理干预，无代理环境下同样可直连。
        curl.setopt(CurlOpt.WRITEFUNCTION, buff.append)
        curl.setopt(CurlOpt.TIMEOUT_MS, timeout * 1000)
        curl.setopt(CurlOpt.NOPROGRESS, 1)
        curl.setopt(CurlOpt.HTTPHEADER, request_headers)
        curl.perform()
        ttfb_ms = _getinfo_float(curl, CurlInfo.STARTTRANSFER_TIME) * 1000.0
        status = _getinfo_int(curl, CurlInfo.RESPONSE_CODE)
        body = b"".join(buff).decode("utf-8", errors="replace")
        return ttfb_ms, status, body
    except CurlError as exc:
        return None, None, f"{type(exc).__name__}: {exc}"
    finally:
        curl.close()


# ------------------------------------------------------- TCP 握手测量（初筛） --
def tcp_rtt_once(ip: str, port: int, timeout: float = TCP_TIMEOUT) -> float | None:
    """做一次 TCP 握手并计时，返回往返毫秒；连接失败返回 None。

    只完成三次握手就断开，不做 TLS/HTTP —— 这正是代理客户端"TCP 延迟"的口径。
    """
    start = time.perf_counter()
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return (time.perf_counter() - start) * 1000.0
    except OSError:
        return None


def measure_tcp(
    ip: str,
    port: int,
    attempts: int = TCP_ATTEMPTS,
    min_success: int = TCP_MIN_SUCCESS,
    timeout: float = TCP_TIMEOUT,
) -> TcpMetrics:
    """重复 N 次 TCP 握手，汇总成功次数、丢包率与时延统计。

    loss_rate 以配置的 attempts 为分母；全部失败时 error 记录失败原因。
    成功次数达到 min_success 即 qualified（相对门槛）。
    """
    delays: list[float] = []
    for _ in range(attempts):
        elapsed = tcp_rtt_once(ip, port, timeout)
        if elapsed is not None:
            delays.append(elapsed)
    success_count = len(delays)
    if delays:
        min_ms: float | None = round(min(delays), 1)
        avg_ms: float | None = round(sum(delays) / len(delays), 1)
        max_ms: float | None = round(max(delays), 1)
    else:
        min_ms = avg_ms = max_ms = None
    return TcpMetrics(
        ip=ip,
        port=port,
        attempts=attempts,
        success_count=success_count,
        loss_rate=(attempts - success_count) / attempts,
        min_ms=min_ms,
        avg_ms=avg_ms,
        max_ms=max_ms,
        error=None if success_count > 0 else "tcp_connect_failed",
        qualified=success_count >= min_success,
    )


def measure_tcp_batch(
    pairs: list[tuple[str, int]],
    attempts: int = TCP_ATTEMPTS,
    min_success: int = TCP_MIN_SUCCESS,
    concurrency: int = PROBE_CONCURRENCY,
    timeout: float = TCP_TIMEOUT,
) -> list[TcpMetrics]:
    """并发测量全部 (ip, port)；单点异常降级为一条失败记录，不中断整批。"""
    results: list[TcpMetrics] = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [
            pool.submit(measure_tcp, ip, port, attempts, min_success, timeout)
            for ip, port in pairs
        ]
        for future, (ip, port) in zip(futures, pairs):
            try:
                results.append(future.result())
            except Exception as exc:  # 单点故障隔离，不放大为全局失败
                results.append(
                    TcpMetrics(
                        ip=ip,
                        port=port,
                        attempts=attempts,
                        success_count=0,
                        loss_rate=1.0,
                        min_ms=None,
                        avg_ms=None,
                        max_ms=None,
                        error=f"internal:{exc}",
                        qualified=False,
                    )
                )
    return results


# ---------------------------------------------------- 边缘端点校验（终筛） --
def check_endpoint(
    ip: str, port: int, timeout: int = TRACE_TIMEOUT, attempts: int = TRACE_ATTEMPTS
) -> EndpointResult:
    """校验单个候选是否落在 Cloudflare 边缘，并取回边缘机房代码。

    通过条件：HTTP 200 **且** 响应体含合法 colo。403 / error 1034（EIV 受限
    子池）与各类错误页都因拿不到 colo 被淘汰，这是本工具的核心准入门槛。

    重试策略（降低瞬时抖动误杀）：
    - 拿到 200 + colo 立即返回；
    - 确定性失败（非 5xx/429 且未通过，如固定 403）不重试；
    - 传输层失败与 5xx/429 视为瞬时，重试；
    - 全部失败时返回最后一次结果。
    """
    last = EndpointResult(None, None, None, "probe_failed")
    for _ in range(attempts):
        ttfb_ms, status, payload = _request_endpoint(ip, port, timeout)
        if ttfb_ms is None:
            last = EndpointResult(None, None, None, payload or "probe_failed")
            continue
        colo, country = parse_endpoint_body(payload)
        if status != 200 or colo is None:
            reason = f"no-colo-field(status={status})" if colo is None else f"status-{status}"
            last = EndpointResult(round(ttfb_ms, 1), colo, country, reason)
            if status is not None and status < 500 and status != 429:
                return last  # 确定性失败，重试无意义
            continue
        return EndpointResult(round(ttfb_ms, 1), colo, country, None)
    return last


def check_endpoints(
    pairs: list[tuple[str, int]],
    concurrency: int = PROBE_CONCURRENCY,
    timeout: int = TRACE_TIMEOUT,
) -> dict[tuple[str, int], EndpointResult]:
    """并发校验全部 (ip, port)；每个键都有一条结果（失败条目带 error）。"""
    results: dict[tuple[str, int], EndpointResult] = {}
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {
            pool.submit(check_endpoint, ip, port, timeout): (ip, port) for ip, port in pairs
        }
        for future, key in futures.items():
            try:
                results[key] = future.result()
            except Exception as exc:  # 单点故障隔离，不放大为全局失败
                results[key] = EndpointResult(None, None, None, f"internal:{exc}")
    return results


def combine_results(
    tcp_results: Sequence[TcpMetrics],
    endpoints: Mapping[tuple[str, int], EndpointResult],
) -> list[Candidate]:
    """合并两阶段结果并给出最终合格标记。

    最终合格 = TCP 握手达标 且 端点校验通过（无 error 且 colo 非空）。
    endpoint 缺失视为不合格（调用方只会对达标者发起校验）。
    error 必须一并判空：非 200 却带 colo 的异常响应已在校验阶段标记 error。
    """
    combined: list[Candidate] = []
    for tcp in tcp_results:
        endpoint = endpoints.get((tcp.ip, tcp.port))
        qualified = (
            tcp.qualified
            and endpoint is not None
            and endpoint.error is None
            and endpoint.colo is not None
        )
        combined.append(
            Candidate(ip=tcp.ip, port=tcp.port, tcp=tcp, endpoint=endpoint, qualified=qualified)
        )
    return combined
