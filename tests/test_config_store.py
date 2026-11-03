import pytest

from panel.config_store import ConfigConflict, ConfigInvalid, read_env, save


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
