from panel.audit import record
from panel.db import connect, migrate
from panel.redact import redact_secrets


def test_migrate_is_idempotent(tmp_path):
    conn = connect(tmp_path / "panel.db")
    migrate(conn)
    migrate(conn)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 1


def test_audit_redacts_secret_values(tmp_path):
    conn = connect(tmp_path / "panel.db")
    migrate(conn)
    record(conn, "admin", "config.save", ".env", "GIT_TOKEN=abc123", "127.0.0.1")
    row = conn.execute("SELECT detail FROM audit").fetchone()
    assert "abc123" not in row[0]


def test_redact_masks_proxy_credentials_and_userinfo():
    text = "HTTP_PROXY=http://user:pass@proxy.local:7890  git https://user:pw@github.com/o/r.git"
    redacted = redact_secrets(text)
    assert "user:pass" not in redacted
    assert "user:pw" not in redacted
    assert "proxy.local:7890" in redacted
