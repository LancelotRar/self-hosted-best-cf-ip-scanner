"""产物入库：把扫描器写进容器卷的文件同步成数据库快照。

扫描器仍然把产物写到 `/output`（命名卷，宿主不可见），那是"发布到 Git"要用的。
面板只从数据库读，所以丢卷也不会丢展示数据；同步按 (size, mtime) 判脏，
每个文件只在真的变化时重读一次。
"""

from __future__ import annotations

import csv
import hashlib
import io
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .files import MAX_CSV_BYTES, MAX_TEXT_BYTES


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _kind(name: str) -> str:
    suffix = Path(name).suffix.lower()
    if suffix == ".csv":
        return "csv"
    if suffix in {".txt", ""}:
        return "text"
    return "binary"


def migrate_legacy(settings) -> None:
    """把升级前落在宿主 `./output` 的产物搬进容器卷，一次性且幂等。"""
    target = Path(settings.output_dir)
    legacy = Path(settings.project_dir) / "output"
    if target.resolve() == legacy.resolve() or not legacy.is_dir():
        return
    target.mkdir(parents=True, exist_ok=True)
    for path in legacy.iterdir():
        if path.is_file() and not path.is_symlink():
            destination = target / path.name
            if not destination.exists():
                shutil.copy2(path, destination)


def sync(conn, settings) -> None:
    """把产物目录的内容对齐进数据库：新增/改动写入，消失的删除。"""
    root = Path(settings.output_dir)
    seen: dict[str, tuple[int, str, Path]] = {}
    if root.is_dir():
        for path in root.iterdir():
            if path.is_file() and not path.is_symlink():
                stat_result = path.stat()
                seen[path.name] = (
                    stat_result.st_size,
                    datetime.fromtimestamp(
                        stat_result.st_mtime, tz=timezone.utc
                    ).isoformat(),
                    path,
                )

    existing = {
        row["name"]: row
        for row in conn.execute("SELECT name, size, mtime FROM artifacts")
    }
    with conn:
        for name, (size, mtime, path) in seen.items():
            known = existing.get(name)
            if known is not None and known["size"] == size and known["mtime"] == mtime:
                continue
            data = path.read_bytes()
            conn.execute(
                "INSERT INTO artifacts (name, kind, size, mtime, sha256, content, imported_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(name) DO UPDATE SET"
                " kind = excluded.kind, size = excluded.size, mtime = excluded.mtime,"
                " sha256 = excluded.sha256, content = excluded.content,"
                " imported_at = excluded.imported_at",
                (
                    name,
                    _kind(name),
                    size,
                    mtime,
                    hashlib.sha256(data).hexdigest(),
                    data,
                    _now_iso(),
                ),
            )
        for name in set(existing) - set(seen):
            conn.execute("DELETE FROM artifacts WHERE name = ?", (name,))


def list_rows(conn) -> list[dict[str, object]]:
    rows = conn.execute(
        "SELECT name, size, mtime FROM artifacts ORDER BY mtime DESC, name"
    ).fetchall()
    return [dict(row) for row in rows]


def get(conn, name: str) -> dict[str, object] | None:
    row = conn.execute("SELECT * FROM artifacts WHERE name = ?", (name,)).fetchone()
    return dict(row) if row else None


def content_of(row: dict[str, object]) -> bytes:
    return row.get("content") or b""


def preview(row: dict[str, object], max_rows: int = 200) -> dict[str, object]:
    """TXT 取前 N 行、CSV 取前 N 行并拆出表头；与入库时记录的 sha256 一致。"""
    data = content_of(row)
    base = {
        "name": row["name"],
        "size": row["size"],
        "mtime": row["mtime"],
        "sha256": row["sha256"],
    }

    if row["kind"] == "csv":
        text = data[:MAX_CSV_BYTES].decode("utf-8", "replace")
        rows = list(csv.reader(io.StringIO(text)))
        headers = rows[0] if rows else []
        body = rows[1 : max_rows + 1]
        return {
            **base,
            "kind": "csv",
            "headers": headers,
            "rows": body,
            "truncated": len(rows) - 1 > max_rows,
        }

    if row["kind"] == "text":
        text = data[:MAX_TEXT_BYTES].decode("utf-8", "replace")
        lines = text.splitlines()
        return {
            **base,
            "kind": "text",
            "content": "\n".join(lines[:max_rows]),
            "line_count": len(lines),
            "truncated": len(lines) > max_rows or len(data) > MAX_TEXT_BYTES,
        }

    return {**base, "kind": "binary"}


__all__ = ["content_of", "get", "list_rows", "migrate_legacy", "preview", "sync"]
