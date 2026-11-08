from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "docker" / "push-filter.py"


def _run(tmp_path, files, env_extra):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    for name in files:
        (source / name).write_text(f"{name}\n", encoding="utf-8")
    env = {
        key: value
        for key, value in os.environ.items()
        if key
        not in {
            "PUSH_LISTS",
            "LIST_FILENAMES",
            "DETAIL_CSV_NAME",
            "PINNED_OUTPUT_NAME",
        }
    }
    env.update(env_extra)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(source), str(target)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return result, {path.name for path in target.iterdir()} if target.is_dir() else set()


def test_empty_push_lists_copies_everything(tmp_path):
    result, names = _run(
        tmp_path,
        ["GLOBAL20.txt", "US100.txt", "detail.csv", "PINNED.txt"],
        {"PUSH_LISTS": "", "DETAIL_CSV_NAME": "detail", "PINNED_OUTPUT_NAME": "PINNED"},
    )
    assert result.returncode == 0, result.stderr
    assert names == {"GLOBAL20.txt", "US100.txt", "detail.csv", "PINNED.txt"}


def test_selected_push_lists_resolve_custom_names(tmp_path):
    result, names = _run(
        tmp_path,
        ["GLOBAL20.txt", "GLOBAL50.txt", "us-ips.txt", "detail.csv", "PINNED.txt"],
        {
            "PUSH_LISTS": '["GLOBAL20", "US100"]',
            "LIST_FILENAMES": '{"US100": "us-ips"}',
            "DETAIL_CSV_NAME": "detail",
            "PINNED_OUTPUT_NAME": "PINNED",
        },
    )
    assert result.returncode == 0, result.stderr
    assert names == {"GLOBAL20.txt", "us-ips.txt", "detail.csv", "PINNED.txt"}


def test_no_selected_lists_still_pushes_detail_and_pinned(tmp_path):
    result, names = _run(
        tmp_path,
        ["GLOBAL20.txt", "detail.csv", "PINNED.txt"],
        {"PUSH_LISTS": "[]", "DETAIL_CSV_NAME": "detail", "PINNED_OUTPUT_NAME": "PINNED"},
    )
    assert result.returncode == 0, result.stderr
    assert names == {"detail.csv", "PINNED.txt"}
