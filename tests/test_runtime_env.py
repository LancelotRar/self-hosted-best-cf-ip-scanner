import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scanner.runtime_env import RuntimeConfigError, load

ROOT = Path(__file__).resolve().parents[1]


def _runtime(tmp_path, values):
    path = tmp_path / "runtime.json"
    path.write_text(json.dumps(values), encoding="utf-8")
    return path


def test_load_reads_json_object(tmp_path):
    path = _runtime(tmp_path, {"SAMPLE_STRIDE": "128", "PROBE_HOST": None})
    assert load(path) == {"SAMPLE_STRIDE": "128", "PROBE_HOST": ""}


def test_load_rejects_non_object(tmp_path):
    path = tmp_path / "runtime.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(RuntimeConfigError):
        load(path)


def test_export_skips_existing_and_empty(tmp_path):
    path = _runtime(tmp_path, {"SAMPLE_STRIDE": "128", "PROBE_HOST": ""})
    env = dict(os.environ, RUNTIME_CONFIG_PATH=str(path), SAMPLE_STRIDE="512")
    out = subprocess.check_output(
        [sys.executable, str(ROOT / "docker/export-runtime.py")], env=env, text=True
    )
    assert "SAMPLE_STRIDE" not in out
    assert "PROBE_HOST" not in out


def test_export_plain_omits_shell_export(tmp_path):
    path = _runtime(tmp_path, {"CRON_SCHEDULE": "30 */6 * * *"})
    env = {key: value for key, value in os.environ.items() if key != "CRON_SCHEDULE"}
    env["RUNTIME_CONFIG_PATH"] = str(path)
    out = subprocess.check_output(
        [sys.executable, str(ROOT / "docker/export-runtime.py"), "--plain"],
        env=env,
        text=True,
    )
    assert out.strip() == "CRON_SCHEDULE='30 */6 * * *'"
    assert "export " not in out


def test_export_quotes_shell_metacharacters(tmp_path):
    path = _runtime(tmp_path, {"PROBE_USER_AGENT": "a $(danger) b"})
    env = {key: value for key, value in os.environ.items() if key != "PROBE_USER_AGENT"}
    env["RUNTIME_CONFIG_PATH"] = str(path)
    out = subprocess.check_output(
        [sys.executable, str(ROOT / "docker/export-runtime.py")], env=env, text=True
    )
    assert "export PROBE_USER_AGENT='a $(danger) b'" in out
