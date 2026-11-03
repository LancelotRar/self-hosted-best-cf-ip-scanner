from __future__ import annotations

from pathlib import Path

import pytest

from panel.settings import Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """临时目录下的完整设置，附带一份最小 `.env`。"""
    resolved = Settings.for_tests(tmp_path)
    resolved.env_path.write_text(
        "PROBE_HOST=probe.example.com\nMAX_CANDIDATES=1\n", encoding="utf-8"
    )
    return resolved


@pytest.fixture
def anon_client(settings: Settings):
    """未登录的 TestClient。"""
    from fastapi.testclient import TestClient

    from panel.app import create_app

    with TestClient(create_app(settings)) as client:
        yield client


TEST_PASSWORD = "correct horse battery"


class FakeContainer:
    """内存版 docker 容器：记录本次调用参数，供断言使用。"""

    def __init__(self, name: str = "best-cf-ip-scanner", cid: str = "cid-1") -> None:
        self.id = cid
        self.name = name
        self.status = "running"
        self.attrs = {
            "State": {
                "Status": "running",
                "Health": {"Status": "healthy"},
                "StartedAt": "2026-11-03T00:00:00Z",
            },
            "Config": {"Image": "ghcr.io/example/scanner:test"},
        }
        self.exec_env: dict[str, str] = {}
        self.exec_cmd: list[str] = []
        self.exec_calls = 0
        self.restarted = 0
        self.stopped = 0
        self.started = 0
        self.log_chunks = [b"line-1\nline-2\n"]

    def logs(self, tail=100, follow=False, stream=True):
        return iter(self.log_chunks)

    def restart(self, timeout=150):
        self.restarted += 1

    def stop(self, timeout=10):
        self.stopped += 1
        self.status = "exited"

    def start(self):
        self.started += 1
        self.status = "running"

    def stats(self, stream=False):
        return {"memory_stats": {"usage": 1024, "limit": 4096}}


class FakeContainers:
    def __init__(self, containers: list[FakeContainer]) -> None:
        self._items = containers

    def get(self, ref: str):
        for container in self._items:
            if container.name == ref:
                return container
        raise KeyError(ref)

    def list(self, all=True, filters=None):
        return list(self._items)


class FakeDockerApi:
    """低层 API：exec_create / exec_start / exec_inspect 的最小实现。"""

    def __init__(self, containers: list[FakeContainer]) -> None:
        self._containers = containers
        self.exec_exit_code = 0

    def exec_create(self, container_id, cmd, environment=None, **kwargs):
        container = next(c for c in self._containers if c.id == container_id)
        container.exec_env = dict(environment or {})
        container.exec_cmd = list(cmd)
        container.exec_calls += 1
        return {"Id": "exec-1"}

    def exec_start(self, exec_id, stream=True, demux=False):
        return iter([b"run-output\n"])

    def exec_inspect(self, exec_id):
        return {"ExitCode": self.exec_exit_code}


class FakeDockerClient:
    def __init__(self, containers: list[FakeContainer] | None = None) -> None:
        self._items = (
            [FakeContainer()] if containers is None else list(containers)
        )
        self.containers = FakeContainers(self._items)
        self.api = FakeDockerApi(self._items)


@pytest.fixture
def fake_container() -> FakeContainer:
    return FakeContainer()


@pytest.fixture
def fake_client(fake_container: FakeContainer) -> FakeDockerClient:
    return FakeDockerClient([fake_container])


@pytest.fixture
def empty_docker_client() -> FakeDockerClient:
    return FakeDockerClient([])


@pytest.fixture
def client(anon_client):
    """已登录并默认携带 CSRF 头的 TestClient。"""
    anon_client.post("/api/auth/setup", json={"password": TEST_PASSWORD})
    anon_client.post("/api/auth/login", json={"password": TEST_PASSWORD})
    anon_client.headers["X-CSRF-Token"] = anon_client.cookies["panel_csrf"]
    yield anon_client
