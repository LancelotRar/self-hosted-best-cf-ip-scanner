"""面板到 sidecar 的 HTTP 控制器：只映射固定脚本，不传任意命令。"""

from __future__ import annotations

from dataclasses import replace

import pytest

from panel.deps import _build_controller
from panel.http_control import HttpController
from panel.settings import Settings


SCAN = "/usr/local/bin/scan-and-publish.sh"
PRINT = "/usr/local/bin/print-config.py"


def test_controller_selection_prefers_control_url(tmp_path):
    settings = replace(
        Settings.for_tests(tmp_path), control_url="http://control:8090"
    )
    assert isinstance(_build_controller(settings), HttpController)


def test_exec_maps_known_script_to_action(monkeypatch):
    controller = HttpController("http://control:8090", token="secret")
    calls: list[tuple[str, str, dict | None]] = []

    def fake_json(method, path, body=None, timeout=10):
        calls.append((method, path, body))
        return {"exec_id": "e1", "run_id": "r1"}

    monkeypatch.setattr(controller, "_json", fake_json)
    handle = controller.exec_script(SCAN, {"RUN_ID": "r1"})

    assert handle.run_id == "r1"
    assert calls == [("POST", "/exec/run", {"env": {"RUN_ID": "r1"}})]


def test_exec_rejects_unknown_script():
    controller = HttpController("http://control:8090")
    with pytest.raises(ValueError):
        controller.exec_script("/bin/sh", {})


def test_exec_stream_and_wait(monkeypatch):
    controller = HttpController("http://control:8090")
    monkeypatch.setattr(
        controller, "_json", lambda *a, **k: {"exec_id": "e1", "run_id": "r1"}
    )
    handle = controller.exec_script(PRINT, {})

    monkeypatch.setattr(controller, "_stream", lambda path: iter([b"a", b"b"]))
    assert b"".join(handle.stream()) == b"ab"

    monkeypatch.setattr(
        controller, "_json", lambda *a, **k: {"exit_code": 7}
    )
    assert handle.wait() == 7


def test_status_and_lifecycle(monkeypatch):
    controller = HttpController("http://control:8090")
    calls: list[tuple[str, str]] = []

    def fake_json(method, path, body=None, timeout=10):
        calls.append((method, path))
        return {"state": "running"} if path == "/status" else {"ok": True}

    monkeypatch.setattr(controller, "_json", fake_json)
    assert controller.status()["state"] == "running"
    controller.restart()
    controller.stop()
    controller.start()
    assert calls[1:] == [
        ("POST", "/restart"),
        ("POST", "/stop"),
        ("POST", "/start"),
    ]
