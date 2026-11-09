import json

from scanner.__main__ import _metrics_payload, _write_run_metrics


def test_write_run_metrics_is_atomic_json(tmp_path, monkeypatch):
    target = tmp_path / "runtime" / "runs" / "r1.json"
    monkeypatch.setenv("RUN_METRICS_PATH", str(target))
    _write_run_metrics(_metrics_payload(ok=True, candidates=12))
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["schema"] == 1
    assert data["ok"] is True
    assert data["candidates"] == 12
    assert data["finished_at"]


def test_write_run_metrics_without_path_is_noop(tmp_path, monkeypatch):
    monkeypatch.delenv("RUN_METRICS_PATH", raising=False)
    _write_run_metrics({"ok": True})
    assert not any(tmp_path.iterdir())


def test_write_run_metrics_does_not_fail_scan_on_oserror(tmp_path, monkeypatch, capsys):
    target = tmp_path / "metrics-dir"
    target.mkdir()
    monkeypatch.setenv("RUN_METRICS_PATH", str(target))
    _write_run_metrics({"ok": True})
    assert "无法写入轮次指标" in capsys.readouterr().err


def test_run_rejects_invalid_numeric_config(tmp_path, capsys):
    from scanner import __main__ as entry

    assert entry.run(tmp_path, concurrency=0) == 1
    assert "配置不合法" in capsys.readouterr().err
