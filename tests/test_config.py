import importlib

import pytest


def test_process_env_beats_dotenv(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SAMPLE_STRIDE=128\n", encoding="utf-8")
    monkeypatch.setenv("DOTENV_PATH", str(env_file))
    monkeypatch.setenv("SAMPLE_STRIDE", "512")
    import scanner.config as config

    importlib.reload(config)
    assert config.SAMPLE_STRIDE == 512


def test_dotenv_beats_default(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SAMPLE_STRIDE=128\nPROBE_PORTS=443,2053\n", encoding="utf-8")
    monkeypatch.setenv("DOTENV_PATH", str(env_file))
    monkeypatch.delenv("SAMPLE_STRIDE", raising=False)
    import scanner.config as config

    importlib.reload(config)
    assert config.SAMPLE_STRIDE == 128
    assert config.PROBE_PORTS == (443, 2053)


def test_empty_dotenv_value_falls_back_to_default(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SAMPLE_STRIDE=\n", encoding="utf-8")
    monkeypatch.setenv("DOTENV_PATH", str(env_file))
    monkeypatch.delenv("SAMPLE_STRIDE", raising=False)
    import scanner.config as config

    importlib.reload(config)
    assert config.SAMPLE_STRIDE == 256


def test_invalid_value_exits_with_param_name(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("PROBE_PORTS=abc\n", encoding="utf-8")
    monkeypatch.setenv("DOTENV_PATH", str(env_file))
    monkeypatch.delenv("PROBE_PORTS", raising=False)
    import scanner.config as config

    with pytest.raises(SystemExit):
        importlib.reload(config)
