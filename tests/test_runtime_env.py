import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_export_skips_existing_and_empty(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("MAX_CANDIDATES=200\nPROBE_HOST=\n", encoding="utf-8")
    env = dict(os.environ, DOTENV_PATH=str(env_file), MAX_CANDIDATES="10")
    out = subprocess.check_output(
        [sys.executable, str(ROOT / "docker/export-dotenv.py")], env=env, text=True
    )
    assert "MAX_CANDIDATES" not in out
    assert "PROBE_HOST" not in out


def test_export_quotes_shell_metacharacters(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("PROBE_USER_AGENT='a $(danger) b'\n", encoding="utf-8")
    env = {key: value for key, value in os.environ.items() if key != "PROBE_USER_AGENT"}
    env["DOTENV_PATH"] = str(env_file)
    out = subprocess.check_output(
        [sys.executable, str(ROOT / "docker/export-dotenv.py")], env=env, text=True
    )
    assert "export PROBE_USER_AGENT='a $(danger) b'" in out
