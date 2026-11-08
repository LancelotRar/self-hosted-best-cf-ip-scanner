import json

import pytest

from panel import settings_store
from panel.config_store import (
    ConfigApplyFailed,
    ConfigConflict,
    ConfigInvalid,
    read_config,
    rollback,
    save,
    verify_effective,
)


def _hash(conn, settings) -> str:
    return read_config(conn, settings).sha256


def test_invalid_cron_and_tz_are_rejected_before_write(conn, settings):
    original = read_config(conn, settings)
    projection = settings.runtime_config_path.read_text(encoding="utf-8")
    with pytest.raises(ConfigInvalid):
        save(
            conn,
            settings,
            original.sha256,
            {"CRON_SCHEDULE": "bad cron"},
            actor="admin",
        )
    with pytest.raises(ConfigInvalid):
        save(
            conn,
            settings,
            original.sha256,
            {"TZ": "Mars/Olympus"},
            actor="admin",
        )
    assert read_config(conn, settings).sha256 == original.sha256
    assert settings.runtime_config_path.read_text(encoding="utf-8") == projection


def test_unsupported_value_syntax_is_rejected_before_write(conn, settings):
    original = read_config(conn, settings)
    with pytest.raises(ConfigInvalid):
        save(
            conn,
            settings,
            original.sha256,
            {"PROBE_HOST": "probe-${ENV}.example.com"},
            actor="admin",
        )
    assert read_config(conn, settings).sha256 == original.sha256


def test_removed_deployment_keys_are_rejected(conn, settings):
    for name in ("PUID", "PGID", "IMAGE_TAG", "PANEL_PORT", "CONTAINER_NAME"):
        with pytest.raises(ConfigInvalid):
            save(
                conn,
                settings,
                _hash(conn, settings),
                {name: "1"},
                actor="admin",
            )


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


def test_rollback_restores_non_secret_values(conn, settings, fake_controller):
    save(
        conn,
        settings,
        _hash(conn, settings),
        {"SAMPLE_STRIDE": "128"},
        actor="admin",
        controller=fake_controller,
    )
    version_id = conn.execute(
        "SELECT id FROM config_versions ORDER BY id LIMIT 1"
    ).fetchone()["id"]
    save(
        conn,
        settings,
        _hash(conn, settings),
        {"SAMPLE_STRIDE": "512"},
        actor="admin",
        controller=fake_controller,
    )
    result = rollback(
        conn,
        settings,
        version_id,
        _hash(conn, settings),
        actor="admin",
        controller=fake_controller,
    )
    assert result.written is True
    assert read_config(conn, settings).values["SAMPLE_STRIDE"] == "128"


def test_secret_is_encrypted_at_rest(conn, settings, fake_controller):
    save(
        conn,
        settings,
        _hash(conn, settings),
        {"GIT_TOKEN": "top-secret"},
        actor="admin",
        controller=fake_controller,
    )
    row = conn.execute(
        "SELECT value, encrypted FROM settings WHERE name = 'GIT_TOKEN'"
    ).fetchone()
    assert row["encrypted"] == 1
    assert "top-secret" not in row["value"]
    assert read_config(conn, settings).values["GIT_TOKEN"] == "top-secret"


def test_save_regenerates_projection(conn, settings, fake_controller):
    save(
        conn,
        settings,
        _hash(conn, settings),
        {"SAMPLE_STRIDE": "512"},
        actor="admin",
        controller=fake_controller,
    )
    text = settings.runtime_config_path.read_text(encoding="utf-8")
    assert json.loads(text)["SAMPLE_STRIDE"] == "512"

    settings.runtime_config_path.unlink()
    settings_store.project(conn, settings)
    restored = json.loads(settings.runtime_config_path.read_text(encoding="utf-8"))
    assert restored["SAMPLE_STRIDE"] == "512"


def test_publish_change_is_verified_against_scanner(conn, settings, fake_controller):
    fake_controller.effective = {"GIT_BRANCH": "old"}
    result = save(
        conn,
        settings,
        _hash(conn, settings),
        {"GIT_BRANCH": "new"},
        actor="admin",
        controller=fake_controller,
    )
    assert result.verification["status"] == "mismatch"
    assert result.verification["details"][0]["name"] == "GIT_BRANCH"


def test_manual_verify_skips_restart_class_keys(conn, settings, fake_controller):
    from scanner.schema import PARAMS, coerce

    document = read_config(conn, settings)
    effective: dict[str, object] = {}
    for spec in PARAMS:
        raw = document.values.get(spec.name)
        if spec.secret:
            continue
        effective[spec.name] = (
            coerce(spec, raw) if raw and raw.strip() else spec.default
        )
    effective["TZ"] = "UTC"  # 扫描器还没重启，仍跑旧时区
    fake_controller.effective = effective

    verification = verify_effective(conn, settings, fake_controller)
    assert verification["status"] == "verified"
    assert verification["details"] == []


def test_stale_hash_conflicts(conn, settings, fake_controller):
    document = read_config(conn, settings)
    save(
        conn,
        settings,
        document.sha256,
        {"SAMPLE_STRIDE": "128"},
        actor="admin",
        controller=fake_controller,
    )
    with pytest.raises(ConfigConflict):
        save(
            conn,
            settings,
            document.sha256,
            {"SAMPLE_STRIDE": "512"},
            actor="admin",
            controller=fake_controller,
        )


def test_invalid_candidate_does_not_write(conn, settings, fake_validator):
    original = read_config(conn, settings)
    projection = settings.runtime_config_path.read_text(encoding="utf-8")
    with pytest.raises(ConfigInvalid):
        save(
            conn,
            settings,
            original.sha256,
            {"TCP_MIN_SUCCESS": "99"},
            actor="admin",
        )
    assert read_config(conn, settings).sha256 == original.sha256
    assert settings.runtime_config_path.read_text(encoding="utf-8") == projection


def test_secret_is_masked_in_get(client, settings, fake_controller):
    document = client.get("/api/config").json()
    response = client.put(
        "/api/config",
        json={"hash": document["hash"], "values": {"GIT_TOKEN": "secret"}},
    )
    assert response.status_code == 200
    body = client.get("/api/config").json()
    token = next(p for p in body["params"] if p["name"] == "GIT_TOKEN")
    assert token["value"] is None and token["configured"] is True


def test_save_reads_back_and_reports_verification(conn, settings, fake_controller):
    fake_controller.effective = {"SAMPLE_STRIDE": 999}  # 模拟扫描器读到旧值
    result = save(
        conn,
        settings,
        _hash(conn, settings),
        {"SAMPLE_STRIDE": "512"},
        actor="admin",
        controller=fake_controller,
    )
    assert result.written is True
    assert result.verification["status"] == "mismatch"
    assert result.verification["details"][0]["name"] == "SAMPLE_STRIDE"


def test_container_offline_reports_unavailable(conn, settings, fake_controller):
    fake_controller.raise_unavailable = True
    result = save(
        conn,
        settings,
        _hash(conn, settings),
        {"SAMPLE_STRIDE": "512"},
        actor="admin",
        controller=fake_controller,
    )
    assert result.written is True
    assert result.verification["status"] == "unavailable"
    assert "下一轮" in " ".join(result.warnings)


def test_schedule_apply_failure_rolls_back(conn, settings, fake_controller):
    fake_controller.apply_exit = 1
    original = read_config(conn, settings)
    projection = settings.runtime_config_path.read_text(encoding="utf-8")
    with pytest.raises(ConfigApplyFailed):
        save(
            conn,
            settings,
            original.sha256,
            {"CRON_SCHEDULE": "0 * * * *"},
            actor="admin",
            controller=fake_controller,
        )
    restored = read_config(conn, settings)
    assert restored.values["CRON_SCHEDULE"] == original.values["CRON_SCHEDULE"]
    assert settings.runtime_config_path.read_text(encoding="utf-8") == projection


def test_seed_defaults_writes_schema_values_once(conn, settings):
    """首次启动把 schema 默认值写入数据库；再次调用不重复写入。"""
    document = read_config(conn, settings)
    assert document.values["SAMPLE_STRIDE"] == "256"
    assert document.values["PROBE_HOST"] == "cloudflare-ech.com"
    assert document.revision >= 1
    assert settings_store.seed_schema_defaults(conn, settings) is False
