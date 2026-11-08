"""面板 SQLite：连接、迁移、依赖工厂。

单管理员、低并发，WAL 足够；数据库文件在 `/panel-data`，备份就是复制文件。
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 5

_SCHEMA: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS schema_version (
        version    INTEGER NOT NULL,
        applied_at TEXT    NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS users (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        username      TEXT    NOT NULL UNIQUE,
        password_hash TEXT    NOT NULL,
        created_at    TEXT    NOT NULL,
        updated_at    TEXT    NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS config_versions (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at  TEXT    NOT NULL,
        actor       TEXT    NOT NULL,
        sha256      TEXT    NOT NULL,
        values_json TEXT    NOT NULL,
        diff        TEXT    NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS runs (
        run_id       TEXT PRIMARY KEY,
        trigger      TEXT,
        started_at   TEXT,
        finished_at  TEXT,
        scan_exit    INTEGER,
        publish_exit INTEGER,
        duration_s   REAL,
        summary      TEXT,
        interrupted  INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit (
        id     INTEGER PRIMARY KEY AUTOINCREMENT,
        at     TEXT NOT NULL,
        actor  TEXT NOT NULL,
        action TEXT NOT NULL,
        target TEXT NOT NULL,
        detail TEXT NOT NULL,
        ip     TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_audit_at ON audit (at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_runs_started ON runs (started_at DESC)",
    # ---- v2：IP 库、机房映射与产物入库；容器卷里的同名文件只是交给扫描器的投影 ----
    """
    CREATE TABLE IF NOT EXISTS library (
        id         INTEGER PRIMARY KEY CHECK (id = 1),
        content    TEXT    NOT NULL,
        sha256     TEXT    NOT NULL,
        updated_at TEXT    NOT NULL,
        actor      TEXT    NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS library_versions (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT    NOT NULL,
        actor      TEXT    NOT NULL,
        sha256     TEXT    NOT NULL,
        content    TEXT    NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS locations (
        id         INTEGER PRIMARY KEY CHECK (id = 1),
        content    TEXT    NOT NULL,
        sha256     TEXT    NOT NULL,
        updated_at TEXT    NOT NULL,
        actor      TEXT    NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pinned (
        id         INTEGER PRIMARY KEY CHECK (id = 1),
        content    TEXT    NOT NULL,
        sha256     TEXT    NOT NULL,
        updated_at TEXT    NOT NULL,
        actor      TEXT    NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS artifacts (
        name              TEXT PRIMARY KEY,
        kind              TEXT    NOT NULL,
        size              INTEGER NOT NULL,
        mtime             TEXT    NOT NULL,
        sha256            TEXT    NOT NULL,
        preview           BLOB,
        count             INTEGER,
        preview_truncated INTEGER NOT NULL DEFAULT 0,
        imported_at       TEXT    NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_artifacts_mtime ON artifacts (mtime DESC)",
    # ---- v4：应用参数收敛到数据库，首次启动写入 schema 默认值 ----
    """
    CREATE TABLE IF NOT EXISTS settings (
        name       TEXT PRIMARY KEY,
        value      TEXT    NOT NULL,
        encrypted  INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT    NOT NULL,
        updated_by TEXT    NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS settings_meta (
        id         INTEGER PRIMARY KEY CHECK (id = 1),
        revision   INTEGER NOT NULL,
        updated_at TEXT    NOT NULL,
        updated_by TEXT    NOT NULL
    )
    """,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: Path) -> sqlite3.Connection:
    """打开（必要时创建）数据库；WAL + 5 秒忙碌等待。"""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(file_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _migrate_artifacts_v5(conn: sqlite3.Connection) -> None:
    """v4 -> v5：产物表只保留元数据与有界预览，移除整文件 BLOB。"""
    columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(artifacts)").fetchall()
    }
    if "content" not in columns:
        return
    conn.execute("DROP INDEX IF EXISTS idx_artifacts_mtime")
    conn.execute("ALTER TABLE artifacts RENAME TO artifacts_v4")
    conn.execute(
        """
        CREATE TABLE artifacts (
            name              TEXT PRIMARY KEY,
            kind              TEXT    NOT NULL,
            size              INTEGER NOT NULL,
            mtime             TEXT    NOT NULL,
            sha256            TEXT    NOT NULL,
            preview           BLOB,
            count             INTEGER,
            preview_truncated INTEGER NOT NULL DEFAULT 0,
            imported_at       TEXT    NOT NULL
        )
        """
    )
    conn.execute(
        "INSERT INTO artifacts"
        " (name, kind, size, mtime, sha256, preview, count, preview_truncated, imported_at)"
        " SELECT name, kind, size, mtime, sha256, NULL, NULL, 0, imported_at"
        " FROM artifacts_v4"
    )
    conn.execute("DROP TABLE artifacts_v4")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_artifacts_mtime ON artifacts (mtime DESC)"
    )


def migrate(conn: sqlite3.Connection) -> None:
    """幂等迁移；版本号记在 `PRAGMA user_version`。"""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    if current >= SCHEMA_VERSION:
        return
    with conn:
        for statement in _SCHEMA:
            conn.execute(statement)
        _migrate_artifacts_v5(conn)
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
            (SCHEMA_VERSION, _utc_now()),
        )
        conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")


def session(conn: sqlite3.Connection):
    """FastAPI 依赖工厂：直接复用进程内连接。"""
    yield conn


__all__ = ["SCHEMA_VERSION", "connect", "migrate", "session"]
