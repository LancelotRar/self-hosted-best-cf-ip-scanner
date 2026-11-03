"""cron 表达式解析与未来执行时间预览。

字段数与 supercronic（cronexpr）**完全一致**，因为它才是真正执行调度的一方：

- 5 段：`分 时 日 月 周`
- 6 段：`分 时 日 月 周 年`（**第 6 位是年，不是秒**）
- 7 段：`秒 分 时 日 月 周 年`

字段语法：`*`、数字、`a-b`、`a-b/step`、`*/step`、逗号列表；周字段 0-6（0=周日）。
不接受 `@daily` 这类宏（supercronic 虽支持，但本项目要求显式表达式）。

预览按分钟推进、分钟内按允许的秒集合展开：既避免逐秒扫描 366 天，也保证
秒级精度。DST 切换期间按本地墙钟推进，重复/缺失的小时以系统时区规则为准。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

MAX_DAYS = 366

_RANGES: dict[str, tuple[int, int]] = {
    "second": (0, 59),
    "minute": (0, 59),
    "hour": (0, 23),
    "dom": (1, 31),
    "month": (1, 12),
    "dow": (0, 6),
    "year": (1970, 2099),
}

_FIELD_ORDER = ("second", "minute", "hour", "dom", "month", "dow", "year")


class CronInvalid(ValueError):
    """cron 表达式非法。"""


def _parse_field(text: str, name: str) -> set[int]:
    low, high = _RANGES[name]
    values: set[int] = set()
    for chunk in text.split(","):
        part = chunk.strip()
        if not part:
            raise CronInvalid(f"{name} 字段存在空项")
        step = 1
        base = part
        if "/" in part:
            base, _, step_raw = part.partition("/")
            if not step_raw.isdigit() or int(step_raw) == 0:
                raise CronInvalid(f"{name} 字段步长非法：{part}")
            step = int(step_raw)
        if base in {"*", "?"}:
            start, end = low, high
        elif "-" in base:
            first, _, last = base.partition("-")
            if not (first.isdigit() and last.isdigit()):
                raise CronInvalid(f"{name} 字段范围非法：{part}")
            start, end = int(first), int(last)
        elif base.isdigit():
            start = end = int(base)
        else:
            raise CronInvalid(f"{name} 字段无法识别：{part}")
        if start < low or end > high or start > end:
            raise CronInvalid(f"{name} 字段超出范围 {low}-{high}：{part}")
        values.update(range(start, end + 1, step))
    return values


def _parse(expr: str) -> dict[str, set[int]]:
    """按 supercronic 的字段数解析：5 段、6 段（+年）、7 段（秒+5 段+年）。"""
    parts = expr.split()
    if len(parts) == 5:
        fields = ["0", *parts, "*"]
    elif len(parts) == 6:
        fields = ["0", *parts]
    elif len(parts) == 7:
        fields = list(parts)
    else:
        raise CronInvalid(
            "需要 5 段、6 段（第 6 位是年）或 7 段（含秒）；不支持 @daily 等宏"
        )
    return {
        name: _parse_field(text, name)
        for name, text in zip(_FIELD_ORDER, fields, strict=True)
    }


def _zone(tz: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz)
    except Exception as exc:  # noqa: BLE001 - 任何时区数据库问题都算非法
        raise CronInvalid(f"未知时区：{tz}") from exc


def _day_matches(moment: datetime, fields: dict[str, set[int]]) -> bool:
    """日与周都限定时按标准 cron 取"或"关系。"""
    dom_all = _RANGES["dom"]
    dow_all = _RANGES["dow"]
    dom_full = fields["dom"] == set(range(dom_all[0], dom_all[1] + 1))
    dow_full = fields["dow"] == set(range(dow_all[0], dow_all[1] + 1))
    dom_ok = moment.day in fields["dom"]
    dow_ok = (moment.weekday() + 1) % 7 in fields["dow"]  # Python 周一=0，cron 周日=0
    if dom_full and dow_full:
        return True
    if dom_full:
        return dow_ok
    if dow_full:
        return dom_ok
    return dom_ok or dow_ok


def next_runs(
    expr: str,
    tz: str,
    count: int = 5,
    now: datetime | None = None,
) -> list[datetime]:
    """返回严格晚于 `now` 的下 `count` 次执行时间。"""
    zone = _zone(tz)
    fields = _parse(expr)
    seconds = sorted(fields["second"])

    reference = (now or datetime.now(zone)).astimezone(zone).replace(microsecond=0)
    cursor = reference.replace(second=0)
    runs: list[datetime] = []
    limit = MAX_DAYS * 24 * 60
    for _ in range(limit):
        if (
            cursor.year in fields["year"]
            and cursor.month in fields["month"]
            and cursor.hour in fields["hour"]
            and cursor.minute in fields["minute"]
            and _day_matches(cursor, fields)
        ):
            for second in seconds:
                candidate = cursor.replace(second=second)
                if candidate <= reference:
                    continue
                runs.append(candidate)
                if len(runs) >= count:
                    return runs
        cursor += timedelta(minutes=1)
    return runs


def validate(expr: str, tz: str | None = None) -> None:
    """语法解析 + （可用时）`supercronic -test`；非法抛 `CronInvalid`。"""
    _parse(expr)
    if tz is not None:
        _zone(tz)
    binary = shutil.which("supercronic")
    if not binary:
        return
    descriptor, path = tempfile.mkstemp(suffix=".crontab")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(f"{expr} true\n")
        process = subprocess.run(
            [binary, "-test", path], capture_output=True, text=True, timeout=20,
            check=False,
        )
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    if process.returncode != 0:
        detail = (process.stderr or process.stdout or "").strip()
        raise CronInvalid(detail or "supercronic 拒绝了该表达式")


__all__ = ["CronInvalid", "MAX_DAYS", "next_runs", "validate"]
