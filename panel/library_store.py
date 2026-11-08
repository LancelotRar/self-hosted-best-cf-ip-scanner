"""IP 库、机房映射与固定保留列表的数据库真源。

三类文档同构（单行内容 + sha256），差异只有表名、参数名与默认值。
数据库是唯一真源；容器卷里的同名文件只是**投影**，供扫描器读取——面板启动与每次保存
都会把数据库内容重新写出去，所以手工改卷内文件不会影响后续运行。
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from scanner.schema import BY_NAME

from . import settings_store
from .files import atomic_write

LIBRARY = "library"
LOCATIONS = "locations"
PINNED = "pinned"

# kind -> (表名, 参数名, schema 默认文件名)
_SPEC: dict[str, tuple[str, str, str]] = {
    LIBRARY: ("library", "LIBRARY_FILE", str(BY_NAME["LIBRARY_FILE"].default)),
    LOCATIONS: ("locations", "LOCATIONS_FILE", str(BY_NAME["LOCATIONS_FILE"].default)),
    PINNED: ("pinned", "PINNED_FILE", str(BY_NAME["PINNED_FILE"].default)),
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_path(conn, settings, kind: str) -> Path:
    """卷内投影文件的路径；文件名非法时退回 schema 默认值。"""
    _, param, default = _SPEC[kind]
    name = (settings_store.value(conn, settings, param) or "").strip() or default
    if not name or "/" in name or "\\" in name or ".." in name:
        name = default
    return Path(settings.data_dir) / name


def read(conn, kind: str) -> dict[str, str] | None:
    """读数据库里的文档；没有则返回 None。"""
    table, _, _ = _SPEC[kind]
    row = conn.execute(
        f"SELECT content, sha256, updated_at, actor FROM {table} WHERE id = 1"
    ).fetchone()
    return dict(row) if row else None


def save(conn, kind: str, content: str, actor: str = "admin") -> dict[str, str]:
    """写入数据库并返回新记录（不负责投影与备份）。"""
    table, _, _ = _SPEC[kind]
    digest = sha256_text(content)
    now = _now_iso()
    with conn:
        conn.execute(
            f"INSERT INTO {table} (id, content, sha256, updated_at, actor)"
            " VALUES (1, ?, ?, ?, ?)"
            " ON CONFLICT(id) DO UPDATE SET"
            " content = excluded.content, sha256 = excluded.sha256,"
            " updated_at = excluded.updated_at, actor = excluded.actor",
            (content, digest, now, actor),
        )
    return {"content": content, "sha256": digest, "updated_at": now, "actor": actor}


def project(conn, settings, kind: str, content: str) -> None:
    """把内容写成扫描器要读的文件（容器卷内，宿主不可见）。"""
    atomic_write(
        file_path(conn, settings, kind),
        content,
        mode=0o644,
        uid=settings.puid,
        gid=settings.pgid,
    )


def ensure(conn, settings) -> None:
    """首次启动把内容落到数据库，之后以数据库为准覆盖投影文件。

    数据库已有 -> 直接投影；否则从卷内文件导入镜像内置默认值。两步都幂等。
    """
    for kind in (LIBRARY, LOCATIONS, PINNED):
        if read(conn, kind) is None:
            candidate = file_path(conn, settings, kind)
            if candidate.is_file():
                save(
                    conn,
                    kind,
                    candidate.read_text(encoding="utf-8-sig", errors="replace"),
                    actor="migrate",
                )
        row = read(conn, kind)
        if row is not None:
            project(conn, settings, kind, row["content"])


# ------------------------------------------------------------------ 版本 --

BACKUP_KEEP = 30


def backup(conn, content: str, actor: str = "admin") -> None:
    """保存前留一份历史，只保留最近 `BACKUP_KEEP` 份。"""
    with conn:
        conn.execute(
            "INSERT INTO library_versions (created_at, actor, sha256, content)"
            " VALUES (?, ?, ?, ?)",
            (_now_iso(), actor, sha256_text(content), content),
        )
        conn.execute(
            "DELETE FROM library_versions WHERE id NOT IN"
            " (SELECT id FROM library_versions ORDER BY id DESC LIMIT ?)",
            (BACKUP_KEEP,),
        )


def versions(conn) -> list[dict[str, object]]:
    rows = conn.execute(
        "SELECT id, created_at, sha256, length(content) AS size"
        " FROM library_versions ORDER BY id DESC LIMIT ?",
        (BACKUP_KEEP,),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "name": f"{row['id']}.txt",
            "created_at": row["created_at"],
            "mtime": row["created_at"],
            "sha256": row["sha256"],
            "size": row["size"],
        }
        for row in rows
    ]


def version_content(conn, version_id: int) -> str | None:
    row = conn.execute(
        "SELECT content FROM library_versions WHERE id = ?", (version_id,)
    ).fetchone()
    return row["content"] if row else None


__all__ = [
    "BACKUP_KEEP",
    "LIBRARY",
    "LOCATIONS",
    "PINNED",
    "backup",
    "ensure",
    "file_path",
    "project",
    "read",
    "save",
    "sha256_text",
    "version_content",
    "versions",
]
