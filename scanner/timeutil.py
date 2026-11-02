"""北京时间工具与采样种子轮换。

全工具的时间口径统一为北京时间(UTC+8), 与产物时间戳一致。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .config import SEED_HOUR_FACTOR


def beijing_timestamp() -> str:
    """返回当前北京时间 YYYY-MM-DD HH:MM。"""
    return (datetime.now(timezone.utc) + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")


def beijing_hour() -> str:
    """返回当前北京时间 YYYYMMDDHH（小时粒度, 用于种子轮换）。"""
    return (datetime.now(timezone.utc) + timedelta(hours=8)).strftime("%Y%m%d%H")


def rotation_seed(base_seed: int, hour: str | None = None) -> int:
    """合成按小时轮换的种子: base_seed * SEED_HOUR_FACTOR + 北京小时整数(YYYYMMDDHH)。

    同一小时内多次运行种子一致(结果可复现/可增量重跑);
    跨小时自动轮换 -> 每个采样窗口的代表 IP 与端口分配逐小时变化,
    长期累计覆盖库内更多 IP 与端口组合。
    """
    hour_val = int(hour or beijing_hour())
    return base_seed * SEED_HOUR_FACTOR + hour_val
