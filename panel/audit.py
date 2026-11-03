"""审计日志：登录、配置变更、回滚、手动执行、容器操作。

写库前统一脱敏；记录操作者、时间、动作、目标、结果摘要与来源 IP。
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from .redact import redact_secrets


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def record(
    conn: sqlite3.Connection,
    actor: str,
    action: str,
    target: str,
    detail: str,
    ip: str,
) -> None:
    """写一条审计；`detail` 中的敏感值会被替换成 `***`。"""
    with conn:
        conn.execute(
            "INSERT INTO audit (at, actor, action, target, detail, ip)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (_utc_now(), actor, action, target, redact_secrets(detail), ip),
        )


__all__ = ["record"]
