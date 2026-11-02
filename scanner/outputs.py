"""产物生成：合格候选 -> 明细表（CSV）+ 订阅列表（TXT）。

依赖方向：outputs -> {atomicio, config, timeutil, locations/probe（仅类型）}。
"""

from __future__ import annotations

import csv
import ipaddress
from collections.abc import Sequence
from pathlib import Path

from .atomicio import write_txt_atomic
from .config import COUNTRY_FILTERS, COUNTRY_TOPS, OVERALL_TOPS
from .locations import LocationMap
from .probe import Candidate
from .timeutil import beijing_timestamp


def _ip_sort_key(ip: str) -> tuple[int, int]:
    """IP 字符串 -> 数值排序键。

    返回 (非法标记, 数值)：合法 IP 为 (0, 地址整数)，非法值为 (1, 0) 统一排到
    合法 IP 之后；用元组作键，避免非法值抛异常中断排序。
    """
    try:
        return (0, int(ipaddress.ip_address(ip)))
    except ValueError:
        return (1, 0)


def _country_of(colo: str | None, location_map: LocationMap) -> str:
    """边缘机房代码 -> 国家代码（如 HKG -> HK）；无映射返回空串。"""
    if not colo:
        return ""
    return location_map.get(colo, "")


def flag_emoji(country_code: str | None) -> str:
    """国家代码 -> 国旗 emoji（US -> 🇺🇸）；非法输入返回空串。

    必须是"恰好两位大写英文字母"：数字、小写、长度不为 2 都判非法，
    否则会产生区域指示符区间之外的乱码字符。
    """
    if not country_code or len(country_code) != 2:
        return ""
    if not country_code.isascii() or not country_code.isupper() or not country_code.isalpha():
        return ""
    return "".join(chr(0x1F1E6 + ord(ch) - ord("A")) for ch in country_code)


def build_detail_rows(
    candidates: Sequence[Candidate], location_map: LocationMap
) -> list[list[str]]:
    """最终合格候选 -> 明细表行（按丢包率 -> 平均延迟 -> IP 数值升序）。

    仅收录最终合格者（TCP 握手达标 且 端点校验通过）。行顺序与
    config.DETAIL_COLUMNS 一致。国家由边缘机房代码经本地映射得到，
    无映射时国家/国旗留空。扫描时间对同一轮的全部行一致。
    """
    scanned_at = beijing_timestamp()
    rows: list[list[str]] = []
    for candidate in candidates:
        if not candidate.qualified or candidate.endpoint is None or candidate.endpoint.colo is None:
            continue
        tcp = candidate.tcp
        assert tcp.avg_ms is not None and tcp.min_ms is not None and tcp.max_ms is not None
        country = _country_of(candidate.endpoint.colo, location_map)
        ttfb = "" if candidate.endpoint.ttfb_ms is None else f"{candidate.endpoint.ttfb_ms:.1f}"
        rows.append(
            [
                candidate.ip,
                str(candidate.port),
                f"{tcp.avg_ms:.1f}",
                f"{tcp.min_ms:.1f}",
                f"{tcp.max_ms:.1f}",
                f"{tcp.loss_rate:.2f}",
                str(tcp.success_count),
                str(tcp.attempts),
                ttfb,
                candidate.endpoint.colo,
                country,
                flag_emoji(country),
                scanned_at,
            ]
        )
    rows.sort(key=lambda row: (float(row[5]), float(row[2]), _ip_sort_key(row[0])))
    return rows


def _subscription_line(ip: str, port: str, country: str, flag: str, colo: str) -> str:
    """构造订阅行：`IP:端口#国家代码 国旗`；无国家映射时回退为机房代码。"""
    if country:
        return f"{ip}:{port}#{country} {flag}".rstrip()
    return f"{ip}:{port}#{colo or 'UNK'}"


def _read_detail_csv(csv_path: Path) -> list[dict[str, str]]:
    """读回明细表（兼容 UTF-8 BOM），返回按列名索引的行。"""
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _rank_key(row: dict[str, str]) -> tuple[float, float, tuple[int, int]]:
    """统一排名键：丢包率升序 -> 平均延迟升序 -> IP 数值升序。"""
    return (
        float(row.get("TCP握手丢包率") or "1"),
        float(row.get("TCP握手平均延迟(ms)") or "inf"),
        _ip_sort_key(row.get("IP") or ""),
    )


def select_subscription_lines(
    rows: list[dict[str, str]],
    count: int,
    country: str | None = None,
    pre_sorted: bool = False,
) -> list[str]:
    """取前 count 行订阅文本；country 非空时先按国家代码过滤。

    pre_sorted=True 表示调用方已按排名键排序，跳过重复排序。
    缺关键列（IP/端口/平均延迟）的行直接跳过，不虚构数据。
    """
    if country is not None:
        rows = [row for row in rows if row.get("国家代码") == country]
    ordered = rows if pre_sorted else sorted(rows, key=_rank_key)
    lines: list[str] = []
    for row in ordered:
        if len(lines) >= count:  # 先判后加：count<=0 时输出 0 行
            break
        ip = row.get("IP") or ""
        port = row.get("端口") or ""
        delay = row.get("TCP握手平均延迟(ms)") or ""
        if not ip or not port or not delay:
            continue
        lines.append(
            _subscription_line(
                ip,
                port,
                row.get("国家代码") or "",
                row.get("国旗") or "",
                row.get("边缘机房代码") or "",
            )
        )
    return lines


def resolve_targets(
    overall_tops: tuple[int, ...] = OVERALL_TOPS,
    country_enabled: bool = COUNTRY_FILTERS,
    country_tops: dict[str, int] | None = None,
) -> list[tuple[str, int]]:
    """解析要生成的列表，返回 [(文件名主体, 条数)]。

    全量：overall_tops 里每个 N>0 生成 ("GLOBAL{N}", N)；
    国家：country_enabled 为真时，每个 N>0 的国家生成 ("{国家代码}{N}", N)。
    两组都为空时返回空列表（只产出明细表）。
    """
    tops = COUNTRY_TOPS if country_tops is None else country_tops
    specs: list[tuple[str, int]] = [
        (f"GLOBAL{size}", size) for size in overall_tops if size > 0
    ]
    if country_enabled:
        specs.extend((f"{code}{size}", size) for code, size in tops.items() if size > 0)
    return specs


def generate_subscriptions(
    csv_path: Path,
    output_dir: Path,
    overall_tops: tuple[int, ...] = OVERALL_TOPS,
    country_enabled: bool = COUNTRY_FILTERS,
    country_tops: dict[str, int] | None = None,
) -> dict[str, int]:
    """由明细表生成订阅列表（写入 output_dir，与明细表同目录），返回 {文件名: 行数}。

    - 全量排名：`GLOBAL{N}.txt`
    - 国家筛选：`{国家代码}{N}.txt`
    - 每个文件首行是注释头：条数、排名口径、扫描时间。
    """
    rows = _read_detail_csv(csv_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, int] = {}
    scanned_at = beijing_timestamp()  # 同一轮全部文件共用同一时间戳

    def _emit(name: str, body_lines: list[str]) -> None:
        header = f"# {len(body_lines)} 条 | 按 TCP 丢包率→平均延迟排序 | 扫描时间 {scanned_at}"
        write_txt_atomic(output_dir / name, [header, *body_lines])
        written[name] = len(body_lines)

    # 排序一次复用：不依赖明细表已排序，所有文件共享同一有序序列
    ordered_rows = sorted(rows, key=_rank_key)
    for kind, size in resolve_targets(overall_tops, country_enabled, country_tops):
        if kind.startswith("GLOBAL"):
            _emit(f"{kind}.txt", select_subscription_lines(ordered_rows, size, pre_sorted=True))
        else:  # 国家筛选：前缀两位是国家代码
            _emit(
                f"{kind}.txt",
                select_subscription_lines(ordered_rows, size, country=kind[:2], pre_sorted=True),
            )
    return written
