import threading
import time

from panel.audit import record
from panel.db import SCHEMA_VERSION, connect, migrate
from panel.redact import redact_secrets


def test_migrate_is_idempotent(tmp_path):
    conn = connect(tmp_path / "panel.db")
    migrate(conn)
    migrate(conn)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION


def test_migrate_creates_document_and_artifact_tables(tmp_path):
    conn = connect(tmp_path / "panel.db")
    migrate(conn)
    names = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert {"library", "library_versions", "locations", "artifacts"} <= names


def test_migrate_artifacts_v5_drops_full_content(tmp_path):
    conn = connect(tmp_path / "panel.db")
    conn.execute(
        "CREATE TABLE artifacts ("
        " name TEXT PRIMARY KEY, kind TEXT NOT NULL, size INTEGER NOT NULL,"
        " mtime TEXT NOT NULL, sha256 TEXT NOT NULL, content BLOB,"
        " imported_at TEXT NOT NULL)"
    )
    payload = b"x" * (200 * 1024)
    conn.execute(
        "INSERT INTO artifacts VALUES ('a.txt', 'text', ?, 't', 'h', ?, 't')",
        (len(payload), payload),
    )
    conn.execute("PRAGMA user_version=4")
    migrate(conn)

    columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(artifacts)").fetchall()
    }
    assert "content" not in columns
    row = conn.execute("SELECT preview, preview_truncated FROM artifacts").fetchone()
    assert row["preview"] is None
    assert row["preview_truncated"] == 0


def test_audit_redacts_secret_values(tmp_path):
    conn = connect(tmp_path / "panel.db")
    migrate(conn)
    record(conn, "admin", "config.save", "settings", "GIT_TOKEN=abc123", "127.0.0.1")
    row = conn.execute("SELECT detail FROM audit").fetchone()
    assert "abc123" not in row[0]


def test_writes_on_shared_connection_are_serialized(conn):
    start = threading.Barrier(2)
    state = {"active": 0, "max": 0}
    state_lock = threading.Lock()
    errors: list[BaseException] = []

    def worker(index: int) -> None:
        try:
            start.wait(timeout=2)
            with conn:
                with state_lock:
                    state["active"] += 1
                    state["max"] = max(state["max"], state["active"])
                time.sleep(0.05)
                conn.execute(
                    "INSERT INTO audit (at, actor, action, target, detail, ip)"
                    " VALUES ('t', 'admin', 'test', 'x', ?, '127.0.0.1')",
                    (str(index),),
                )
                with state_lock:
                    state["active"] -= 1
        except BaseException as exc:  # noqa: BLE001 - 测试收集线程异常
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=3)

    assert not errors, errors
    assert state["max"] == 1


def test_audit_retention_keeps_row_count_bounded(tmp_path, monkeypatch):
    from panel import audit

    monkeypatch.setattr(audit, "MAX_ROWS", 2)
    conn = connect(tmp_path / "panel.db")
    migrate(conn)
    for index in range(3):
        audit.record(conn, "admin", "test", "x", str(index), "127.0.0.1")
    assert conn.execute("SELECT COUNT(*) FROM audit").fetchone()[0] == 2


def test_redact_masks_proxy_credentials_and_userinfo():
    text = "HTTP_PROXY=http://user:pass@proxy.local:7890  git https://user:pw@github.com/o/r.git"
    redacted = redact_secrets(text)
    assert "user:pass" not in redacted
    assert "user:pw" not in redacted
    assert "proxy.local:7890" in redacted
