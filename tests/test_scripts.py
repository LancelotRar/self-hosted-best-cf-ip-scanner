import py_compile
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_all_shell_scripts_parse():
    scripts = sorted([*(ROOT / "scanner/docker").glob("*.sh"), *(ROOT / "panel/docker").glob("*.sh"), *(ROOT / "docker").glob("*.sh"), *(ROOT / "tests" / "scripts").glob("*.sh")])
    assert scripts
    for path in scripts:
        subprocess.run(["sh", "-n", str(path)], check=True)


def test_all_python_scripts_compile():
    for path in sorted([*(ROOT / "scanner/docker").glob("*.py"), *(ROOT / "docker").glob("*.py")]):
        py_compile.compile(str(path), doraise=True)


def test_repository_has_no_env_template():
    """项目不再提供配置文件模板；部署参数只写在 compose.yaml。"""
    import re

    assert not (ROOT / ".env.example").exists()
    compose = (ROOT / "compose.example.yaml").read_text(encoding="utf-8")
    assert "env_file" not in compose
    # 只允许可选的容器控制变量通过环境注入，其余部署参数必须直接写在 compose 里。
    interpolated = set(re.findall(r"\$\{([A-Z_]+)", compose))
    assert interpolated <= {"SCANNER_CONTROL_URL", "SCANNER_CONTROL_TOKEN"}


def test_compose_example_wires_panel_and_config_projection():
    import yaml

    document = yaml.safe_load((ROOT / "compose.example.yaml").read_text(encoding="utf-8"))
    services = document["services"]
    assert "panel" in services
    assert "scanner-config" in document["volumes"]
    scanner_volumes = services["scanner"]["volumes"]
    assert any(str(volume).endswith(":/scanner-config:ro") for volume in scanner_volumes)
    assert not any(str(volume).endswith(":/project:ro") for volume in scanner_volumes)
    assert "env_file" not in services["scanner"]
    panel_volumes = services["panel"]["volumes"]
    assert any(str(volume).endswith(":/scanner-config") for volume in panel_volumes)
    assert not any(str(volume).endswith(":/project:ro") for volume in panel_volumes)
    assert services["scanner"]["depends_on"]["panel"]["condition"] == "service_healthy"


def test_entrypoint_reads_projection_and_keeps_params_out_of_long_running_env():
    text = (ROOT / "scanner/docker/entrypoint.sh").read_text(encoding="utf-8")
    # 只取调度相关键；PUID/PGID 属于部署参数，不再出现在配置文件里。
    assert "--plain --keys TZ,CRON_SCHEDULE,RUN_ON_START" in text
    assert "PUID,PGID,TZ" not in text
    assert "/scanner-config/runtime.json" in text
    assert "export-runtime.py" in text
    # 默认数据由面板播种，扫描器入口不再复制出厂文件。
    assert "DEFAULT_DATA_DIR" not in text
    # 旧的手工编辑监听已删除
    assert "config-watcher" not in text
    assert not (ROOT / "scanner/docker/config-watcher.sh").exists()


def test_apply_config_uses_supercronic_reload_signal():
    text = (ROOT / "scanner/docker/apply-config.sh").read_text(encoding="utf-8")
    # supercronic 用 SIGUSR2 重载；SIGHUP 会终止 PID 1 导致容器重启。
    assert "kill -USR2 1" in text
    assert "kill -HUP" not in text
    # 面板以 root exec 时必须在 sticky /tmp 里降权，才能替换业务用户的 crontab。
    assert 'su-exec "${PUID:-1000}:${PGID:-1000}"' in text


def test_shell_boolean_defaults_match_schema():
    entrypoint = (ROOT / "scanner/docker/entrypoint.sh").read_text(encoding="utf-8")
    publish = (ROOT / "scanner/docker/publish.sh").read_text(encoding="utf-8")
    # 空值 = 未设置 = schema 默认值；shell 默认值必须一致。
    assert 'RUN_ON_START="${RUN_ON_START:-true}"' in entrypoint
    assert 'GIT_PUSH_ENABLED="${GIT_PUSH_ENABLED:-false}"' in publish


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
    for path in [*(ROOT / "panel").rglob("*.py"), *ROOT.glob("scanner/docker/*.py"), *ROOT.glob("docker/*.py")]:
        text = path.read_text(encoding="utf-8")
        assert "shell=True" not in text, path


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
