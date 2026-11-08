"""Docker 控制 sidecar：只暴露固定操作，不接受任意容器/任意命令。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from panel.control_sidecar import create_sidecar


class FakeHandle:
    def __init__(self, payload: bytes = b"run-output\n", code: int = 0) -> None:
        self.payload = payload
        self.code = code
        self.run_id = "run-1"
        self.finished = False

    def stream(self):
        yield self.payload
        self.finished = True

    def wait(self, timeout_s: float = 3600) -> int:
        self.finished = True
        return self.code


class FakeController:
    def __init__(self) -> None:
        self.exec_calls: list[tuple[str, dict[str, str]]] = []
        self.restarted = 0
        self.stopped = 0
        self.started = 0

    def status(self):
        return {"name": "scanner", "state": "running", "health": "healthy"}

    def stats(self):
        return {"memory_usage": 1, "memory_limit": 2}

    def logs(self, tail=200, follow=True, timestamps=True):
        return iter([b"line-1\n"])

    def exec_script(self, script, env=None):
        self.exec_calls.append((script, dict(env or {})))
        return FakeHandle()

    def restart(self, timeout=150):
        self.restarted += 1

    def stop(self, timeout=30):
        self.stopped += 1

    def start(self):
        self.started += 1


def _client(controller=None, token=None) -> TestClient:
    return TestClient(create_sidecar(controller or FakeController(), token=token))


def test_health_status_and_stats():
    with _client() as client:
        assert client.get("/healthz").json()["status"] == "ok"
        assert client.get("/status").json()["state"] == "running"
        assert client.get("/stats").json()["memory_usage"] == 1


def test_exec_run_stream_and_wait():
    controller = FakeController()
    with _client(controller) as client:
        created = client.post("/exec/run", json={"env": {"RUN_ID": "r1"}})
        assert created.status_code == 200
        exec_id = created.json()["exec_id"]
        assert controller.exec_calls[0][1] == {"RUN_ID": "r1"}

        stream = client.get(f"/exec/{exec_id}/stream")
        assert b"run-output" in stream.content
        wait = client.get(f"/exec/{exec_id}/wait")
        assert wait.json()["exit_code"] == 0


def test_unknown_action_is_rejected():
    with _client() as client:
        assert client.post("/exec/rm-rf", json={}).status_code == 404


def test_logs_stream():
    with _client() as client:
        response = client.get("/logs?tail=10")
        assert b"line-1" in response.content


def test_token_is_required_when_configured():
    with _client(token="secret") as client:
        assert client.get("/status").status_code == 403
        assert (
            client.get("/status", headers={"X-Control-Token": "secret"}).status_code
            == 200
        )


def test_lifecycle_actions():
    controller = FakeController()
    with _client(controller) as client:
        assert client.post("/restart").status_code == 200
        assert client.post("/stop").status_code == 200
        assert client.post("/start").status_code == 200
    assert (controller.restarted, controller.stopped, controller.started) == (1, 1, 1)
