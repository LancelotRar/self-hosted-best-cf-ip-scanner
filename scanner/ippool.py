"""候选地址库处理：解析 / 网段合并 / 地址网格采样 / 端口分配。

地址库由使用者维护，脚本只读不改。要排除某个网段，在行首加 `#` 注释并写明
依据即可（比删除更易恢复，详见 README「维护 IP 库」）。
"""

from __future__ import annotations

import ipaddress
import random
from pathlib import Path

from .config import PROBE_PORTS

# 库内 `IP:端口` 条目解析出的固定端口：ip -> port
FixedPorts = dict[str, int]

# 视为表头而非数据的词（大小写不敏感）
_HEADER_WORDS = {"cidr", "ip", "ip address"}


def _parse_entry(line: str) -> tuple[ipaddress.IPv4Network, int | None] | None:
    """解析单行 -> (IPv4 网段, 固定端口或 None)；无法解析返回 None。

    支持三种写法：
      CIDR       104.16.0.0/22      -> 网段，参与采样
      单个 IP    104.16.1.5         -> 等价 /32
      IP:端口    104.16.1.5:8443    -> /32 + 固定端口，原样保留不参与采样
    IPv6 与非 IPv4 一律返回 None（由调用方计为跳过）；IPv6 含多个冒号，
    不会误入带端口分支。
    """
    text = line.strip()
    if not text:
        return None
    host, sep, port_text = text.partition(":")
    if sep and host and port_text.isdigit():
        try:
            address = ipaddress.IPv4Address(host)
        except ValueError:
            return None
        port = int(port_text)
        if not 1 <= port <= 65535:
            return None
        return ipaddress.IPv4Network(f"{address}/32"), port
    try:
        network = ipaddress.ip_network(text, strict=False)
    except ValueError:
        return None
    return (network, None) if isinstance(network, ipaddress.IPv4Network) else None


def read_library(path: str | Path) -> tuple[list[ipaddress.IPv4Network], FixedPorts, int]:
    """读取候选地址库，返回 (网段列表, 固定端口映射, 跳过行数)。

    每行支持 CIDR / 单个 IP / `IP:端口`；以 utf-8-sig 读取（自动剥离 BOM），
    跳过空行、`#` 注释与表头（如 cidr / ip）。

    **带端口的行不进入网段列表**，而是单独放进固定端口映射：这类条目表示
    "精确指定某 IP 的某端口"，不应被采样窗口替换成同段内的其它地址。
    调用方应把它们原样加入候选并保留端口。
    """
    content = Path(path).read_text(encoding="utf-8-sig", errors="ignore")
    networks: list[ipaddress.IPv4Network] = []
    fixed: FixedPorts = {}
    skipped = 0
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.casefold() in _HEADER_WORDS:
            continue  # 表头
        parsed = _parse_entry(line)
        if parsed is None:
            skipped += 1
            continue
        network, port = parsed
        if port is None:
            networks.append(network)
        else:
            fixed[str(network.network_address)] = port
    return networks, fixed, skipped


def library_errors(text: str) -> list[tuple[int, str]]:
    """逐行校验候选地址库，返回 `[(行号, 原文行)]`；行号从 1 开始。

    跳过空行、`#` 注释与表头；其余行用与扫描器相同的解析器判断。
    """
    errors: list[tuple[int, str]] = []
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip().lstrip("\ufeff").strip()
        if not line or line.startswith("#") or line.casefold() in _HEADER_WORDS:
            continue
        if _parse_entry(line) is None:
            errors.append((line_no, line))
    return errors


def merge_to_runs(networks: list[ipaddress.IPv4Network]) -> list[tuple[int, int]]:
    """把网段合并为最大连续地址区间，返回升序 [(首地址, 末地址)]（整数对）。

    重叠与首尾相接的网段并入同一区间；输入无需预排序。
    库内行可能重叠（如 /24 与其子 /25 并存），合并即消解重复。
    """
    runs: list[list[int]] = []
    for network in sorted(networks, key=lambda net: int(net.network_address)):
        start, end = int(network.network_address), int(network.broadcast_address)
        if runs and start <= runs[-1][1] + 1:
            runs[-1][1] = max(runs[-1][1], end)
        else:
            runs.append([start, end])
    return [(start, end) for start, end in runs]


def sample_representatives(runs: list[tuple[int, int]], stride: int, seed: int) -> list[str]:
    """按地址网格每个窗口抽取 1 个代表 IP，返回代表列表。

    窗口按**地址网格**对齐（窗口起点是 stride 的整数倍），而不是从区间起点
    锚定：stride 等于一个 /24 的长度时，窗口边界恒等于 /24 边界，因此等价于
    「每个 /24 抽 1 个」，与库内条目如何切分/合并无关；非 /24 对齐的条目也
    不会让后续窗口整体错位。同一地址永远落在同一窗口，同种子可复现。

    区间与窗口的交集非空才采样；末尾不足 stride 的窗口仍抽 1 个。
    区间互不重叠 => 代表互不重复。
    代表可能落在 .0/.255 上——对 Cloudflare anycast 段这些是正常可路由地址，
    不可达者由后续探测淘汰。
    """
    if stride < 1:
        raise ValueError(f"stride 必须 >= 1，当前 {stride}")
    rng = random.Random(seed)
    samples: list[str] = []
    for run_start, run_end in runs:
        position = (run_start // stride) * stride
        while position <= run_end:
            window_start = max(position, run_start)
            window_end = min(position + stride - 1, run_end)
            if window_start <= window_end:
                samples.append(
                    str(ipaddress.ip_address(rng.randrange(window_start, window_end + 1)))
                )
            position += stride
    return samples


def assign_ports(
    ips: list[str], seed: int, fixed_ports: FixedPorts | None = None
) -> dict[str, int]:
    """为每个代表 IP 分配探测端口，返回 {ip: port}。

    `fixed_ports` 命中的 IP 沿用库内 `IP:端口` 指定的端口；其余从 PROBE_PORTS
    用固定种子随机挑选。同种子同输入结果一致，便于复现。
    """
    rng = random.Random(seed)
    fixed = fixed_ports or {}
    ports: dict[str, int] = {}
    for ip in ips:
        ports[ip] = fixed[ip] if ip in fixed else rng.choice(PROBE_PORTS)
    return ports
