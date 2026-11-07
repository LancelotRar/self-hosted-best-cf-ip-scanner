#!/usr/bin/env python3
"""best-cf-ip-scanner —— 统一入口。

从候选地址库（默认 DATA_DIR/ip-library.txt）抽取代表 IP，按两阶段筛选产出
可订阅的 Cloudflare 优选 IP 列表。全部可调项来自环境变量，默认值见
scanner/config.py；入口不接受命令行参数。

流程：
    1) 读取候选地址库：每行支持 CIDR / 单个 IP / `IP:端口`，跳过注释与表头；
       `IP:端口` 条目原样保留（不参与采样，端口不被替换）。
    2) 合并重叠/相邻网段为连续地址区间，按地址网格每 SAMPLE_STRIDE 个地址抽取
       1 个代表 IP（取 256，即一个 /24 的长度，等价于每个 /24 抽 1 个），并从
       PROBE_PORTS 为每个代表随机分配端口。采样种子按北京小时轮换：
       同一小时可复现，跨小时逐步覆盖不同代表 IP 与端口组合。
    3) TCP 握手测量（初筛 + 排名基准）：每个候选做 TCP_ATTEMPTS 次握手计时，
       统计成功次数、丢包率、最小/平均/最大往返时延；成功次数低于
       TCP_MIN_SUCCESS 者淘汰。
    4) 边缘端点校验（终筛）：达标者经 curl RESOLVE 把 PROBE_HOST 钉到候选
       IP:端口，请求 PROBE_PATH；要求 HTTP 200 且响应体含合法 colo。
       403 / error 1034（EIV 受限子池）在此淘汰。
    5) 产出：明细表（CSV，含全部合格候选与指标）+ 订阅列表（TXT，按
       丢包率 -> 平均延迟 -> IP 数值的相对排名取前 N）。

延迟是部署网络的视角数值，随部署位置与 Cloudflare 调度变化；这不是带宽
测速工具，只测 TCP 握手往返时延与边缘落点。仅处理 IPv4。
"""

from __future__ import annotations

import sys
import time
from collections import Counter
from pathlib import Path

# ---- 子模块引用（供编排与外部脚本按模块打桩） ----
from scanner import probe

# ---- 配置与公共 API 再导出 ----
from scanner.config import (
    DATA_DIR as DATA_DIR,
    COUNTRY_TOPS as COUNTRY_TOPS,
    DETAIL_COLUMNS as DETAIL_COLUMNS,
    DETAIL_CSV_NAME as DETAIL_CSV_NAME,
    COUNTRY_FILTERS as COUNTRY_FILTERS,
    OVERALL_TOPS as OVERALL_TOPS,
    LIBRARY_FILE as LIBRARY_FILE,
    PINNED_FILE as PINNED_FILE,
    PINNED_OUTPUT_NAME as PINNED_OUTPUT_NAME,
    LOCATIONS_FILE as LOCATIONS_FILE,
    OUTPUT_DIR as OUTPUT_DIR,
    PROBE_CONCURRENCY as PROBE_CONCURRENCY,
    SAMPLE_SEED as SAMPLE_SEED,
    SAMPLE_STRIDE as SAMPLE_STRIDE,
    SKIP_LOCATIONS as SKIP_LOCATIONS,
    TCP_ATTEMPTS as TCP_ATTEMPTS,
    TCP_MIN_SUCCESS as TCP_MIN_SUCCESS,
    TCP_TIMEOUT as TCP_TIMEOUT,
    TRACE_ATTEMPTS as TRACE_ATTEMPTS,
    TRACE_TIMEOUT as TRACE_TIMEOUT,
    PROBE_PORTS as PROBE_PORTS,
)
from scanner.timeutil import rotation_seed as rotation_seed
from scanner.ippool import (
    assign_ports as assign_ports,
    commented_networks as commented_networks,
    count_addresses as count_addresses,
    merge_to_runs as merge_to_runs,
    parse_library as parse_library,
    sample_representatives as sample_representatives,
    subtract_runs as subtract_runs,
)
from scanner.pinned import (
    format_line as format_line,
    read_pinned as read_pinned,
)
from scanner.probe import (
    Candidate as Candidate,
    EndpointResult as EndpointResult,
    TcpMetrics as TcpMetrics,
    check_endpoint as check_endpoint,
    check_endpoints as check_endpoints,
    combine_results as combine_results,
    measure_tcp as measure_tcp,
    measure_tcp_batch as measure_tcp_batch,
    parse_endpoint_body as parse_endpoint_body,
    tcp_rtt_once as tcp_rtt_once,
)
from scanner.validation import (
    numeric_problems as numeric_problems,
    ports_problems as ports_problems,
    probe_host_problems as probe_host_problems,
    top_problems as top_problems,
)
from scanner.locations import (
    LocationMap as LocationMap,
    load_locations as load_locations,
)
from scanner.atomicio import (
    write_csv_atomic as write_csv_atomic,
    write_json_atomic as write_json_atomic,
)
from scanner.outputs import (
    _subscription_line as _subscription_line,
    build_detail_rows as build_detail_rows,
    flag_emoji as flag_emoji,
    generate_subscriptions as generate_subscriptions,
    resolve_targets as resolve_targets,
    write_pinned_list as write_pinned_list,
)


def _failure_summary(reasons: "Counter[str]") -> str:
    """把失败原因计数压成一行 top-5，供日志与 issue 直接引用。"""
    if not reasons:
        return "n/a"
    return "; ".join(f"{kind} x{count}" for kind, count in reasons.most_common(5))


def _purge_previous_outputs(output_dir: Path) -> None:
    """清掉上一轮产物（*.csv / *.txt），保证产物集合是"本轮全量镜像"。

    只在两阶段筛选都通过后调用：任一阶段全灭时直接返回，上一次有效产物原样
    保留（"不覆盖"语义）。若不在成功路径上清理，把某个列表条数改成 0 后旧文件会
    一直留在目录里，发布脚本会把它们当成新一轮产物继续推送。
    """
    for pattern in ("*.csv", "*.txt"):
        for path in output_dir.glob(pattern):
            if path.is_file():
                path.unlink()


# ---------------------------------------------------------------- 主流程 --
def run(
    output_dir: str | Path,
    library_file: str | Path = LIBRARY_FILE,
    concurrency: int = PROBE_CONCURRENCY,
    trace_timeout: int = TRACE_TIMEOUT,
    sample_seed: int = SAMPLE_SEED,
    skip_locations: bool = SKIP_LOCATIONS,
    tcp_attempts: int = TCP_ATTEMPTS,
    tcp_min_success: int = TCP_MIN_SUCCESS,
    tcp_timeout: float = TCP_TIMEOUT,
    overall_tops: tuple[int, ...] = OVERALL_TOPS,
    country_enabled: bool = COUNTRY_FILTERS,
    country_tops: dict[str, int] | None = None,
    sample_stride: int = SAMPLE_STRIDE,
    pinned_output_name: str = PINNED_OUTPUT_NAME,
) -> int:
    """执行完整流程，返回进程退出码（0 成功；1 配置非法/输入缺失/筛选全灭）。

    全部可调项来自环境变量（经同名入参透传，便于按轮覆盖）。参数非法或任一
    阶段全灭时返回 1 且不写产物，避免用空结果覆盖上一次有效结果。
    """
    problems = numeric_problems(
        concurrency=concurrency,
        trace_timeout=trace_timeout,
        sample_stride=sample_stride,
        tcp_attempts=tcp_attempts,
        tcp_min_success=tcp_min_success,
        tcp_timeout=tcp_timeout,
    ) + ports_problems(PROBE_PORTS) + top_problems(
        overall_tops, country_enabled, COUNTRY_TOPS if country_tops is None else country_tops
    ) + probe_host_problems(probe.PROBE_HOST)
    if problems:
        print("[错误] 配置不合法：" + "；".join(problems), file=sys.stderr)
        return 1

    result_dir = Path(output_dir)
    result_dir.mkdir(parents=True, exist_ok=True)
    data_dir = Path(DATA_DIR)
    started = time.monotonic()

    library_path = Path(library_file)
    if not library_path.is_absolute():
        library_path = data_dir / library_path
    if not library_path.is_file():
        print(f"[错误] 未找到候选地址库：{library_path}", file=sys.stderr)
        return 1

    content = library_path.read_text(encoding="utf-8-sig", errors="ignore")
    networks, skipped_lines = parse_library(content)
    if not networks:
        print(f"[错误] 候选地址库中没有可解析的 IPv4 条目：{library_path}", file=sys.stderr)
        return 1
    if skipped_lines:
        print(
            f"[提示] 已跳过 {skipped_lines} 行地址库条目（空行/注释/表头/带端口条目不计）",
            file=sys.stderr,
        )

    pinned_path = Path(PINNED_FILE)
    if not pinned_path.is_absolute():
        pinned_path = data_dir / pinned_path
    pinned_entries, pinned_skipped = read_pinned(pinned_path)
    if pinned_skipped:
        print(
            f"[提示] 固定保留中有 {pinned_skipped} 行无法解析，已忽略", file=sys.stderr
        )

    # 注释掉的网段是"排除集"：从有效库里扣掉，支持只排除某个大段的子集。
    active_runs = merge_to_runs(networks)
    runs = subtract_runs(active_runs, merge_to_runs(commented_networks(content)))
    excluded_total = count_addresses(active_runs) - count_addresses(runs)
    if not runs:
        print("[错误] 排除后地址库没有可扫描的地址", file=sys.stderr)
        return 1

    effective_seed = rotation_seed(sample_seed)
    representatives = sample_representatives(runs, stride=sample_stride, seed=effective_seed)
    ports = assign_ports(representatives, seed=effective_seed)
    pairs = [(ip, ports[ip]) for ip in representatives]

    print(
        f"候选地址库：{library_path}（{len(networks)} 个网段 -> 排除 {excluded_total} 个地址 -> "
        f"{len(runs)} 个连续地址区间，每 {sample_stride} 个地址抽 1 个）共 {len(pairs)} 个候选 IP"
    )
    if pinned_entries:
        print(
            f"固定保留：{len(pinned_entries)} 条（不参与扫描，直接附加到全量列表）"
        )
    print(
        f"采样参数：种子 {effective_seed}（SAMPLE_SEED {sample_seed} × 1e6 + 北京小时），"
        f"端口池 {','.join(str(p) for p in PROBE_PORTS)}，并发 {concurrency}"
    )

    # 阶段 1：TCP 握手测量（初筛，同时是排名基准）
    stage_started = time.monotonic()
    tcp_results = measure_tcp_batch(
        pairs,
        attempts=tcp_attempts,
        min_success=tcp_min_success,
        concurrency=concurrency,
        timeout=tcp_timeout,
    )
    tcp_ok = [result for result in tcp_results if result.qualified]
    tcp_errors = Counter(
        (result.error or "tcp_connect_failed")[:40] for result in tcp_results if not result.qualified
    )
    print(
        f"TCP 握手测量：合格 {len(tcp_ok)}，淘汰 {len(pairs) - len(tcp_ok)}"
        f"（每候选 {tcp_attempts} 次，至少成功 {tcp_min_success} 次，超时 {tcp_timeout}s，"
        f"耗时 {time.monotonic() - stage_started:.1f}s）"
    )
    if tcp_errors:
        print(f"  未达标原因：{_failure_summary(tcp_errors)}")
    if not tcp_ok:
        print(
            f"[错误] TCP 握手测量 0/{len(pairs)} 合格（top 失败原因：{_failure_summary(tcp_errors)}），"
            "不生成产物以避免覆盖既有结果",
            file=sys.stderr,
        )
        return 1

    # 阶段 2：边缘端点校验（终筛）
    stage_started = time.monotonic()
    endpoints = check_endpoints(
        [(result.ip, result.port) for result in tcp_ok],
        concurrency=concurrency,
        timeout=trace_timeout,
    )
    candidates = combine_results(tcp_ok, endpoints)

    location_map: LocationMap = (
        {} if skip_locations else load_locations(data_dir / LOCATIONS_FILE)
    )
    rows = build_detail_rows(candidates, location_map)
    endpoint_errors = Counter(
        ((candidate.endpoint.error if candidate.endpoint is not None else None) or "unqualified")[:40]
        for candidate in candidates
        if not candidate.qualified
    )
    if endpoint_errors:
        print(f"  未通过原因：{_failure_summary(endpoint_errors)}")
    if not rows:
        print(
            f"[错误] 边缘端点校验后无合格候选（top 失败原因：{_failure_summary(endpoint_errors)}），"
            "不生成产物以避免覆盖既有结果",
            file=sys.stderr,
        )
        return 1

    detail_path = result_dir / f"{DETAIL_CSV_NAME}.csv"
    _purge_previous_outputs(result_dir)
    write_csv_atomic(detail_path, DETAIL_COLUMNS, rows)
    print(
        f"边缘端点校验：合格 {len(rows)}，淘汰 {len(tcp_ok) - len(rows)}"
        f"（TCP 握手达标 {len(tcp_ok)}/{len(pairs)}；耗时 {time.monotonic() - stage_started:.1f}s）"
    )
    print(f"  明细表：{detail_path}")

    # 阶段 3：生成订阅列表（与明细表同目录）
    written = generate_subscriptions(
        detail_path,
        result_dir,
        overall_tops=overall_tops,
        country_enabled=country_enabled,
        country_tops=country_tops,
    )
    for name, count in written.items():
        print(f"  订阅列表：{name}（{count} 条）")

    pinned_file = write_pinned_list(
        result_dir,
        pinned_output_name,
        [format_line(entry) for entry in pinned_entries],
    )
    if pinned_file:
        print(f"  固定保留：{pinned_file}（{len(pinned_entries)} 条，未参与扫描）")
    print(
        f"本轮完成：{len(written)} 个订阅列表 + 1 个明细表"
        + (" + 1 个固定保留列表" if pinned_file else "")
        + f" -> {result_dir}"
        f"  总耗时 {time.monotonic() - started:.1f}s"
    )
    return 0


def main() -> int:
    """运行入口：全部可调项取自环境变量，不接受命令行参数。

    输出根目录取自 OUTPUT_DIR（容器内由 compose 注入 /output）：
    明细表与订阅列表直接写在该目录下。
    """
    return run(output_dir=OUTPUT_DIR)


if __name__ == "__main__":
    sys.exit(main())
