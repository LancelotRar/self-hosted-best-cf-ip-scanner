"""面板 SQLite：连接、迁移、依赖工厂。

单管理员、低并发，WAL 足够；数据库文件在 `/panel-data`，备份就是复制文件。
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 6

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
        updated_at    TEXT    NOT NULL,
        session_epoch INTEGER NOT NULL DEFAULT 0
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


class MaterializedRows:
    """SELECT 结果的只读物化视图。

    共享连接下，`execute()` 返回的游标会在另一个线程执行语句时被重置；
    把结果在锁内一次性取完，后续的迭代/取行就与连接状态无关。
    """

    __slots__ = ("_rows", "_index")

    def __init__(self, rows: list[sqlite3.Row]) -> None:
        self._rows = rows
        self._index = 0

    def fetchone(self) -> sqlite3.Row | None:
        if self._index >= len(self._rows):
            return None
        row = self._rows[self._index]
        self._index += 1
        return row

    def fetchmany(self, size: int = 1) -> list[sqlite3.Row]:
        end = min(self._index + size, len(self._rows))
        rows = self._rows[self._index:end]
        self._index = end
        return rows

    def fetchall(self) -> list[sqlite3.Row]:
        rows = self._rows[self._index:]
        self._index = len(self._rows)
        return rows

    def __iter__(self):
        return iter(self._rows)

    def __len__(self) -> int:
        return len(self._rows)


class LockedConnection:
    """把单个 SQLite 连接的访问串行化。

    FastAPI 的同步路由在线程池里执行，而整个应用共享一个连接。
    直接共享会让两个线程的 `with conn:` 事务交错；这里用可重入锁保证
    同一时刻只有一个线程进入事务，`execute` 之间也不会互相踩踏。
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._lock = threading.RLock()

    def execute(self, *args, **kwargs):
        with self._lock:
            cursor = self._conn.execute(*args, **kwargs)
            # 写语句没有结果集，保留游标以取 lastrowid；读语句直接物化。
            if cursor.description is None:
                return cursor
            return MaterializedRows(cursor.fetchall())

    def fetchone(self, sql: str, params: tuple = ()):
        """执行并立即取一行；整个过程持锁。

        共享连接下 `execute(...).fetchone()` 分两步，若另一线程在中间执行语句，
        游标结果会被重置并返回 None——认证检查会因此误判为未登录。
        """
        with self._lock:
            return self._conn.execute(sql, params).fetchone()

    def executemany(self, *args, **kwargs):
        with self._lock:
            return self._conn.executemany(*args, **kwargs)

    def executescript(self, *args, **kwargs):
        with self._lock:
            return self._conn.executescript(*args, **kwargs)

    def commit(self) -> None:
        with self._lock:
            self._conn.commit()

    def rollback(self) -> None:
        with self._lock:
            self._conn.rollback()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self):
        self._lock.acquire()
        self._conn.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            return self._conn.__exit__(exc_type, exc, tb)
        finally:
            self._lock.release()

    def __getattr__(self, name: str):
        attr = getattr(self._conn, name)
        if callable(attr):
            def locked(*args, **kwargs):
                with self._lock:
                    return attr(*args, **kwargs)

            return locked
        return attr


def connect(path: Path) -> LockedConnection:
    """打开（必要时创建）数据库；WAL + 5 秒忙碌等待。"""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(file_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return LockedConnection(conn)


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


def _migrate_users_v6(conn: sqlite3.Connection) -> None:
    """v5 -> v6：会话 epoch；改密后旧 Cookie 立即失效。"""
    columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()
    }
    if "session_epoch" not in columns:
        conn.execute(
            "ALTER TABLE users ADD COLUMN session_epoch INTEGER NOT NULL DEFAULT 0"
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
        _migrate_users_v6(conn)
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
            (SCHEMA_VERSION, _utc_now()),
        )
        conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")


def session(conn: sqlite3.Connection):
    """FastAPI 依赖工厂：直接复用进程内连接。"""
    yield conn


__all__ = ["SCHEMA_VERSION", "connect", "migrate", "session"]
