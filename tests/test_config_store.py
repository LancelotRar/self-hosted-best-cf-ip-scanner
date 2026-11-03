import pytest

from panel import db as panel_db
from panel.config_store import (
    ConfigConflict,
    ConfigInvalid,
    read_env,
    rollback,
    save,
    verify_effective,
)


def test_invalid_cron_and_tz_are_rejected_before_write(settings):
    original = settings.env_path.read_text(encoding="utf-8")
    with pytest.raises(ConfigInvalid):
        save(
            settings,
            read_env(settings).sha256,
            {"CRON_SCHEDULE": "bad cron"},
            actor="admin",
        )
    with pytest.raises(ConfigInvalid):
        save(
            settings,
            read_env(settings).sha256,
            {"TZ": "Mars/Olympus"},
            actor="admin",
        )
    with pytest.raises(ConfigInvalid):
        save(
            settings,
            read_env(settings).sha256,
            {"PUID": "-1"},
            actor="admin",
        )
    assert settings.env_path.read_text(encoding="utf-8") == original


def test_unsupported_value_syntax_is_rejected_before_write(settings):
    original = settings.env_path.read_text(encoding="utf-8")
    with pytest.raises(ConfigInvalid):
        save(
            settings,
            read_env(settings).sha256,
            {"PROBE_HOST": "probe-${ENV}.example.com"},
            actor="admin",
        )
    assert settings.env_path.read_text(encoding="utf-8") == original


def test_dry_run_sees_candidate_proxy_values(tmp_path, monkeypatch):
    from panel.config_store import validate_candidate

    script = tmp_path / "check.py"
    script.write_text(
        "import os, sys\n"
        "sys.exit(0 if os.environ.get('HTTP_PROXY') == 'http://proxy:7890' else 1)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("panel.config_store.CHECK_CONFIG_SCRIPT", str(script))
    monkeypatch.delenv("HTTP_PROXY", raising=False)
    validate_candidate(
        {"PROBE_HOST": "probe.example.com", "HTTP_PROXY": "http://proxy:7890"}
    )


def test_rollback_survives_readonly_keys(settings, fake_controller):
    settings.env_path.write_text(
        "IMAGE_NAME=ghcr.io/example/scanner\nIMAGE_TAG=latest\n"
        "PANEL_PORT=8080\nMAX_CANDIDATES=0\n",
        encoding="utf-8",
    )
    save(
        settings,
        read_env(settings).sha256,
        {"MAX_CANDIDATES": "5"},
        actor="admin",
        controller=fake_controller,
    )
    conn = panel_db.connect(settings.db_path)
    version_id = conn.execute(
        "SELECT id FROM config_versions ORDER BY id LIMIT 1"
    ).fetchone()["id"]
    save(
        settings,
        read_env(settings).sha256,
        {"MAX_CANDIDATES": "6"},
        actor="admin",
        controller=fake_controller,
    )
    result = rollback(
        settings,
        conn,
        version_id,
        read_env(settings).sha256,
        actor="admin",
        controller=fake_controller,
    )
    assert result.written is True
    assert read_env(settings).values["MAX_CANDIDATES"] == "5"


def test_invalid_readonly_value_does_not_block_save(settings, fake_controller):
    settings.env_path.write_text("PANEL_PORT=abc\nMAX_CANDIDATES=0\n", encoding="utf-8")
    result = save(
        settings,
        read_env(settings).sha256,
        {"MAX_CANDIDATES": "7"},
        actor="admin",
        controller=fake_controller,
    )
    assert result.written is True
    assert read_env(settings).values["MAX_CANDIDATES"] == "7"


def test_publish_change_is_verified_against_scanner(settings, fake_controller):
    fake_controller.effective = {"GIT_BRANCH": "old"}
    result = save(
        settings,
        read_env(settings).sha256,
        {"GIT_BRANCH": "new"},
        actor="admin",
        controller=fake_controller,
    )
    assert result.verification["status"] == "mismatch"
    assert result.verification["details"][0]["name"] == "GIT_BRANCH"


def test_manual_verify_skips_restart_class_keys(settings, fake_controller):
    from scanner.schema import PARAMS, coerce

    settings.env_path.write_text("PUID=1001\nMAX_CANDIDATES=3\n", encoding="utf-8")
    document = read_env(settings)
    effective: dict[str, object] = {}
    for spec in PARAMS:
        raw = document.values.get(spec.name)
        if spec.secret:
            continue
        effective[spec.name] = (
            coerce(spec, raw) if raw and raw.strip() else spec.default
        )
    effective["PUID"] = 1000  # 扫描器还没重启，仍跑旧 UID
    fake_controller.effective = effective

    verification = verify_effective(settings, fake_controller)
    assert verification["status"] == "verified"
    assert verification["details"] == []



def test_save_preserves_comments_and_updates_value(settings):
    settings.env_path.write_text("# keep\nMAX_CANDIDATES=0\n", encoding="utf-8")
    doc = read_env(settings)
    result = save(settings, doc.sha256, {"MAX_CANDIDATES": "200"}, actor="admin")
    text = settings.env_path.read_text(encoding="utf-8")
    assert "# keep" in text
    assert "MAX_CANDIDATES=200" in text
    assert result.applied is True


def test_stale_hash_conflicts(settings):
    doc = read_env(settings)
    settings.env_path.write_text("MAX_CANDIDATES=1\n", encoding="utf-8")
    with pytest.raises(ConfigConflict):
        save(settings, doc.sha256, {"MAX_CANDIDATES": "2"}, actor="admin")


def test_invalid_candidate_does_not_write(settings, fake_validator):
    original = settings.env_path.read_text(encoding="utf-8")
    with pytest.raises(ConfigInvalid):
        save(
            settings,
            read_env(settings).sha256,
            {"TCP_MIN_SUCCESS": "99"},
            actor="admin",
        )
    assert settings.env_path.read_text(encoding="utf-8") == original


def test_secret_is_masked_in_get(settings, client):
    settings.env_path.write_text("GIT_TOKEN=secret\n", encoding="utf-8")
    body = client.get("/api/config").json()
    token = next(p for p in body["params"] if p["name"] == "GIT_TOKEN")
    assert token["value"] is None and token["configured"] is True


def test_save_reads_back_and_reports_verification(settings, fake_controller):
    fake_controller.effective = {"MAX_CANDIDATES": 999}  # 模拟扫描器读到旧值
    result = save(
        settings,
        read_env(settings).sha256,
        {"MAX_CANDIDATES": "200"},
        actor="admin",
        controller=fake_controller,
    )
    assert result.written is True
    assert result.verification["status"] == "mismatch"
    assert result.verification["details"][0]["name"] == "MAX_CANDIDATES"


def test_container_offline_reports_unavailable(settings, fake_controller):
    fake_controller.raise_unavailable = True
    result = save(
        settings,
        read_env(settings).sha256,
        {"MAX_CANDIDATES": "200"},
        actor="admin",
        controller=fake_controller,
    )
    assert result.written is True
    assert result.verification["status"] == "unavailable"
    assert "下一轮" in " ".join(result.warnings)


def test_schedule_apply_failure_rolls_back(settings, fake_controller):
    from panel.config_store import ConfigApplyFailed

    fake_controller.apply_exit = 1
    original = settings.env_path.read_text(encoding="utf-8")
    with pytest.raises(ConfigApplyFailed):
        save(
            settings,
            read_env(settings).sha256,
            {"CRON_SCHEDULE": "0 * * * *"},
            actor="admin",
            controller=fake_controller,
        )
    assert settings.env_path.read_text(encoding="utf-8") == original


def test_readonly_key_is_rejected(settings):
    with pytest.raises(ConfigInvalid):
        save(
            settings,
            read_env(settings).sha256,
            {"IMAGE_TAG": "1.2.3"},
            actor="admin",
        )
