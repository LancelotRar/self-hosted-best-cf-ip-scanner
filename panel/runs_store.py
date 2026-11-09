"""轮次记录：解析 `/data/runtime/runs.tsv` 并同步到 SQLite 索引。

`runs.tsv` 是权威来源（扫描器写、面板只读）；`panel.db.runs` 只是 UI 索引，
随时可以从 TSV 重建。START 无 END 视为「中断」，不猜结束时间。
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path

from .settings import Settings

_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    trigger: str | None
    started_at: str | None
    finished_at: str | None
    scan_exit: int | None
    publish_exit: int | None
    duration_s: float | None
    summary: str | None
    interrupted: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def runs_path(settings: Settings) -> Path:
    return settings.data_dir / "runtime" / "runs.tsv"


def metrics_dir(settings: Settings) -> Path:
    return settings.data_dir / "runtime" / "runs"


def metrics_path(settings: Settings, run_id: str) -> Path | None:
    """指标文件路径；run_id 只允许安全字符，避免被拼成路径穿越。"""
    if not _RUN_ID_RE.fullmatch(run_id):
        return None
    return metrics_dir(settings) / f"{run_id}.json"


def read_metrics(settings: Settings, run_id: str) -> dict[str, object] | None:
    """读取扫描器写下的结构化指标；缺失或损坏时返回 None，不影响页面。"""
    path = metrics_path(settings, run_id)
    if path is None or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def attach_metrics(
    settings: Settings, records: list[dict[str, object]]
) -> list[dict[str, object]]:
    """给轮次补 metrics 字段；只读最近轮次的小 JSON，成本可忽略。"""
    for item in records:
        run_id = item.get("run_id")
        item["metrics"] = read_metrics(settings, run_id) if isinstance(run_id, str) else None
    return records


def _as_int(raw: str) -> int | None:
    raw = raw.strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _as_float(raw: str) -> float | None:
    raw = raw.strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def parse(path: Path) -> list[RunRecord]:
    """解析轮次记录；格式错误行直接跳过（按出现顺序返回）。"""
    file_path = Path(path)
    if not file_path.is_file():
        return []
    records: dict[str, RunRecord] = {}
    order: list[str] = []
    try:
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []

    for line in lines:
        fields = line.split("\t")
        if len(fields) < 4 or fields[0] not in {"START", "END"}:
            continue
        kind, run_id, trigger, moment = fields[0], fields[1], fields[2], fields[3]
        if not run_id:
            continue
        if kind == "START":
            if run_id not in records:
                order.append(run_id)
            records[run_id] = RunRecord(
                run_id=run_id,
                trigger=trigger or None,
                started_at=moment or None,
                finished_at=None,
                scan_exit=None,
                publish_exit=None,
                duration_s=None,
                summary=None,
                interrupted=True,
            )
            continue
        records[run_id] = RunRecord(
            run_id=run_id,
            trigger=trigger or None,
            started_at=(records[run_id].started_at if run_id in records else None),
            finished_at=moment or None,
            scan_exit=_as_int(fields[4]) if len(fields) > 4 else None,
            publish_exit=_as_int(fields[5]) if len(fields) > 5 else None,
            duration_s=_as_float(fields[6]) if len(fields) > 6 else None,
            summary=(fields[7] if len(fields) > 7 and fields[7] else None),
            interrupted=False,
        )
        if run_id not in order:
            order.append(run_id)
    return [records[run_id] for run_id in order]


def sync(conn: sqlite3.Connection, path: Path, limit: int = 200) -> int:
    """把 TSV 写入 `runs` 索引表（幂等）；返回同步条数。"""
    records = parse(path)
    with conn:
        for record in records[-limit:]:
            conn.execute(
                "INSERT OR REPLACE INTO runs (run_id, trigger, started_at, finished_at,"
                " scan_exit, publish_exit, duration_s, summary, interrupted)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.run_id,
                    record.trigger,
                    record.started_at,
                    record.finished_at,
                    record.scan_exit,
                    record.publish_exit,
                    record.duration_s,
                    record.summary,
                    int(record.interrupted),
                ),
            )
    return len(records)


def with_status(
    records: list[RunRecord],
    lock_held: bool,
    active_ids: set[str] | frozenset[str] = frozenset(),
) -> list[dict[str, object]]:
    """给每条记录补 `status`：done / running / interrupted。

    START 没有 END 时不能一律算"中断"：正在跑的一轮也会先写 START。
    只有「未结束 + 不是当前活跃执行 + 没有持有扫描锁」才是中断。
    """
    last_unfinished = max(
        (index for index, record in enumerate(records) if not record.finished_at),
        default=None,
    )
    last_index = len(records) - 1
    decorated: list[dict[str, object]] = []
    for index, record in enumerate(records):
        if record.finished_at:
            status = "done"
        elif record.run_id in active_ids or (
            lock_held and index == last_unfinished and last_unfinished == last_index
        ):
            status = "running"
        else:
            status = "interrupted"
        item = record.to_dict()
        item["status"] = status
        decorated.append(item)
    return decorated


def scan_lock_held(settings: Settings) -> bool:
    """`/cache/scan.lock` 是否被占用；文件不存在视为空闲。

    只用只读 fd 试探：面板以 root 运行，不能在宿主目录里新建或改动属主。
    """
    try:
        import fcntl
    except ImportError:  # Windows 开发环境没有 fcntl；容器内一定存在
        return False

    path = settings.cache_dir / "scan.lock"
    if not path.exists():
        return False
    with path.open("rb") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return True
        else:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            return False


__all__ = [
    "RunRecord",
    "attach_metrics",
    "metrics_dir",
    "metrics_path",
    "parse",
    "read_metrics",
    "runs_path",
    "scan_lock_held",
    "sync",
    "with_status",
]
