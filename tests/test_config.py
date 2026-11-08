import importlib
import json

import pytest


def _write_runtime(tmp_path, values):
    path = tmp_path / "runtime.json"
    path.write_text(json.dumps(values), encoding="utf-8")
    return path


def test_process_env_beats_projection(monkeypatch, tmp_path):
    runtime = _write_runtime(tmp_path, {"SAMPLE_STRIDE": "128"})
    monkeypatch.setenv("RUNTIME_CONFIG_PATH", str(runtime))
    monkeypatch.setenv("SAMPLE_STRIDE", "512")
    import scanner.config as config

    importlib.reload(config)
    assert config.SAMPLE_STRIDE == 512


def test_projection_beats_default(monkeypatch, tmp_path):
    runtime = _write_runtime(
        tmp_path, {"SAMPLE_STRIDE": "128", "PROBE_PORTS": "443,2053"}
    )
    monkeypatch.setenv("RUNTIME_CONFIG_PATH", str(runtime))
    monkeypatch.delenv("SAMPLE_STRIDE", raising=False)
    import scanner.config as config

    importlib.reload(config)
    assert config.SAMPLE_STRIDE == 128
    assert config.PROBE_PORTS == (443, 2053)


def test_empty_projection_value_falls_back_to_default(monkeypatch, tmp_path):
    runtime = _write_runtime(tmp_path, {"SAMPLE_STRIDE": ""})
    monkeypatch.setenv("RUNTIME_CONFIG_PATH", str(runtime))
    monkeypatch.delenv("SAMPLE_STRIDE", raising=False)
    import scanner.config as config

    importlib.reload(config)
    assert config.SAMPLE_STRIDE == 256


def test_invalid_value_exits_with_param_name(monkeypatch, tmp_path):
    runtime = _write_runtime(tmp_path, {"PROBE_PORTS": "abc"})
    monkeypatch.setenv("RUNTIME_CONFIG_PATH", str(runtime))
    monkeypatch.delenv("PROBE_PORTS", raising=False)
    import scanner.config as config

    with pytest.raises(SystemExit):
        importlib.reload(config)
