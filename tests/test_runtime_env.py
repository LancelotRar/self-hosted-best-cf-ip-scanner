import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_export_skips_existing_and_empty(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SAMPLE_STRIDE=128\nPROBE_HOST=\n", encoding="utf-8")
    env = dict(os.environ, DOTENV_PATH=str(env_file), SAMPLE_STRIDE="512")
    out = subprocess.check_output(
        [sys.executable, str(ROOT / "docker/export-dotenv.py")], env=env, text=True
    )
    assert "SAMPLE_STRIDE" not in out
    assert "PROBE_HOST" not in out


def test_export_plain_omits_shell_export(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("CRON_SCHEDULE=30 */6 * * *\n", encoding="utf-8")
    env = {key: value for key, value in os.environ.items() if key != "CRON_SCHEDULE"}
    env["DOTENV_PATH"] = str(env_file)
    out = subprocess.check_output(
        [sys.executable, str(ROOT / "docker/export-dotenv.py"), "--plain"],
        env=env,
        text=True,
    )
    assert out.strip() == "CRON_SCHEDULE='30 */6 * * *'"
    assert "export " not in out


def test_export_quotes_shell_metacharacters(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("PROBE_USER_AGENT='a $(danger) b'\n", encoding="utf-8")
    env = {key: value for key, value in os.environ.items() if key != "PROBE_USER_AGENT"}
    env["DOTENV_PATH"] = str(env_file)
    out = subprocess.check_output(
        [sys.executable, str(ROOT / "docker/export-dotenv.py")], env=env, text=True
    )
    assert "export PROBE_USER_AGENT='a $(danger) b'" in out
