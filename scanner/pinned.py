"""固定保留条目：不参与任何扫描，原样附加到全量订阅列表末尾。

每行一条：

    1.2.3.4:443#手动添加      # 带端口 + 自定义标注
    1.2.3.4                   # 省略端口时默认 443
    # 整行注释                # 行首 # 为注释，不会被带入

这些条目不做 TCP 探测、不做端点校验、也不做机房映射，因此不会出现在明细表与国家
列表里——只有全量列表（`GLOBAL{N}.txt`）会在排名结果之后把它们原样附上。
"""

from __future__ import annotations

import ipaddress
from pathlib import Path

DEFAULT_PORT = 443


def parse_line(line: str) -> tuple[str, int, str] | None:
    """解析单行 -> (IP, 端口, 标注)；空行/整行注释/非法行返回 None。"""
    text = line.strip()
    if not text or text.startswith("#"):
        return None
    address, _, label = text.partition("#")
    address = address.strip()
    label = label.strip()

    host, sep, port_text = address.partition(":")
    try:
        ip = ipaddress.IPv4Address(host)
    except ValueError:
        return None
    port = DEFAULT_PORT
    if sep:
        if not port_text.isdigit() or not 1 <= int(port_text) <= 65535:
            return None
        port = int(port_text)
    return str(ip), port, label


def format_line(entry: tuple[str, int, str]) -> str:
    """(IP, 端口, 标注) -> 订阅行；标注为空时不写 `#`。"""
    ip, port, label = entry
    return f"{ip}:{port}#{label}" if label else f"{ip}:{port}"


def parse_pinned(content: str) -> tuple[list[tuple[str, int, str]], int]:
    """解析固定保留文本，返回 (条目, 跳过行数)；重复条目只保留第一次出现。"""
    entries: list[tuple[str, int, str]] = []
    seen: set[tuple[str, int]] = set()
    skipped = 0
    for raw in content.splitlines():
        text = raw.strip()
        if not text or text.startswith("#"):
            continue
        parsed = parse_line(text)
        if parsed is None:
            skipped += 1
            continue
        key = (parsed[0], parsed[1])
        if key in seen:
            continue
        seen.add(key)
        entries.append(parsed)
    return entries, skipped


def read_pinned(path: str | Path) -> tuple[list[tuple[str, int, str]], int]:
    """读取固定保留文件；文件不存在时视为空列表。"""
    try:
        content = Path(path).read_text(encoding="utf-8-sig", errors="ignore")
    except OSError:
        return [], 0
    return parse_pinned(content)


def pinned_errors(text: str) -> list[tuple[int, str]]:
    """逐行校验（供面板使用），返回 [(行号, 原文)]；行号从 1 开始。"""
    errors: list[tuple[int, str]] = []
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if parse_line(line) is None:
            errors.append((line_no, line))
    return errors
