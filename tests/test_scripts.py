import py_compile
import subprocess
from pathlib import Path

import pytest

from scanner.dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def test_all_shell_scripts_parse():
    scripts = sorted((ROOT / "docker").glob("*.sh"))
    assert scripts
    for path in scripts:
        subprocess.run(["sh", "-n", str(path)], check=True)


def test_all_python_scripts_compile():
    for path in sorted((ROOT / "docker").glob("*.py")):
        py_compile.compile(str(path), doraise=True)


def test_env_example_is_parseable():
    values = load_dotenv(ROOT / ".env.example")
    assert "PROBE_HOST" in values
    assert "PANEL_PORT" in values
    assert "PANEL_TRUST_PROXY" in values


def test_compose_example_declares_panel_and_project_mount():
    import yaml

    document = yaml.safe_load((ROOT / "compose.example.yaml").read_text(encoding="utf-8"))
    services = document["services"]
    assert "panel" in services
    scanner_volumes = services["scanner"]["volumes"]
    assert any(str(volume).endswith(":/project:ro") for volume in scanner_volumes)
    assert "env_file" not in services["scanner"]


def test_cli_reset_password_keeps_audit(tmp_path, monkeypatch):
    from panel import db
    from panel.cli import reset_password
    from panel.security import verify_password
    from panel.settings import Settings

    settings = Settings.for_tests(tmp_path)
    reset_password(settings, "brand new password")

    conn = db.connect(settings.db_path)
    row = conn.execute("SELECT password_hash FROM users").fetchone()
    assert row is not None
    assert verify_password("brand new password", row["password_hash"])
    assert conn.execute("SELECT COUNT(*) FROM audit").fetchone()[0] == 1


def test_project_source_files_avoid_shell_true():
    for path in [*(ROOT / "panel").rglob("*.py"), *ROOT.glob("docker/*.py")]:
        text = path.read_text(encoding="utf-8")
        assert "shell=True" not in text, path


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
