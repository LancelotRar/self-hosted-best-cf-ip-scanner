"""产物入库：把扫描器写进容器卷的文件同步成数据库元数据与有界预览。

扫描器仍然把产物写到 `/output`（命名卷，宿主不可见），那是"发布到 Git"要用的。
数据库只存文件名、大小、时间、sha256、条目数与**有界预览**；完整内容永远留在
文件卷里，下载时再从卷内读取。这样数据库不会随产物增大而无限膨胀。
"""

from __future__ import annotations

import csv
import hashlib
import io
from datetime import datetime, timezone
from pathlib import Path

# 单个文件最多入库的预览字节数；超出部分只保留元数据。
PREVIEW_BYTES = 128 * 1024


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _kind(name: str) -> str:
    suffix = Path(name).suffix.lower()
    if suffix == ".csv":
        return "csv"
    if suffix in {".txt", ""}:
        return "text"
    return "binary"


def _text_count(data: bytes) -> int:
    """列表文件的条目数：忽略空行与注释行。"""
    text = data.decode("utf-8", "replace")
    return sum(
        1
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def sync(conn, settings) -> None:
    """把产物目录的元数据对齐进数据库：新增/改动写入，消失的删除。"""
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
        for row in conn.execute("SELECT name, size, mtime, preview FROM artifacts")
    }
    with conn:
        for name, (size, mtime, path) in seen.items():
            known = existing.get(name)
            if (
                known is not None
                and known["size"] == size
                and known["mtime"] == mtime
                and known["preview"] is not None
            ):
                continue
            data = path.read_bytes()
            kind = _kind(name)
            conn.execute(
                "INSERT INTO artifacts"
                " (name, kind, size, mtime, sha256, preview, count,"
                "  preview_truncated, imported_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(name) DO UPDATE SET"
                " kind = excluded.kind, size = excluded.size, mtime = excluded.mtime,"
                " sha256 = excluded.sha256, preview = excluded.preview,"
                " count = excluded.count, preview_truncated = excluded.preview_truncated,"
                " imported_at = excluded.imported_at",
                (
                    name,
                    kind,
                    size,
                    mtime,
                    hashlib.sha256(data).hexdigest(),
                    data[:PREVIEW_BYTES],
                    _text_count(data) if kind == "text" else None,
                    1 if len(data) > PREVIEW_BYTES else 0,
                    _now_iso(),
                ),
            )
        for name in set(existing) - set(seen):
            conn.execute("DELETE FROM artifacts WHERE name = ?", (name,))


def list_rows(conn) -> list[dict[str, object]]:
    rows = conn.execute(
        "SELECT name, size, mtime, kind, count"
        " FROM artifacts ORDER BY mtime DESC, name"
    ).fetchall()
    return [
        {
            "name": row["name"],
            "size": row["size"],
            "mtime": row["mtime"],
            "count": row["count"],
        }
        for row in rows
    ]


def get(conn, name: str) -> dict[str, object] | None:
    row = conn.execute("SELECT * FROM artifacts WHERE name = ?", (name,)).fetchone()
    return dict(row) if row else None


def preview(row: dict[str, object], max_rows: int = 200) -> dict[str, object]:
    """TXT 取前 N 行、CSV 取前 N 行并拆出表头；只使用有界预览。"""
    data = row.get("preview") or b""
    base = {
        "name": row["name"],
        "size": row["size"],
        "mtime": row["mtime"],
        "sha256": row["sha256"],
    }

    if row["kind"] == "csv":
        text = data.decode("utf-8", "replace")
        rows = list(csv.reader(io.StringIO(text)))
        headers = rows[0] if rows else []
        body = rows[1 : max_rows + 1]
        return {
            **base,
            "kind": "csv",
            "headers": headers,
            "rows": body,
            "truncated": bool(row["preview_truncated"]) or len(rows) - 1 > max_rows,
        }

    if row["kind"] == "text":
        text = data.decode("utf-8", "replace")
        lines = text.splitlines()
        return {
            **base,
            "kind": "text",
            "content": "\n".join(lines[:max_rows]),
            "line_count": row.get("count") or len(lines),
            "truncated": bool(row["preview_truncated"]) or len(lines) > max_rows,
        }

    return {**base, "kind": "binary"}


def download(settings, row: dict[str, object]) -> bytes | None:
    """从卷内读取完整产物；文件已不存在时返回 None。"""
    name = str(row["name"])
    if not name or "/" in name or "\\" in name or ".." in name:
        return None
    path = Path(settings.output_dir) / name
    if not path.is_file() or path.is_symlink():
        return None
    return path.read_bytes()


__all__ = ["PREVIEW_BYTES", "download", "get", "list_rows", "preview", "sync"]
