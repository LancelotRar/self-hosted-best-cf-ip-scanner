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
def anon_client(settings: Settings, fake_controller):
    """未登录的 TestClient（控制器注入为内存实现）。"""
    from fastapi.testclient import TestClient

    from panel.app import create_app

    with TestClient(create_app(settings, controller=fake_controller)) as client:
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


class FakeExecHandle:
    def __init__(self, payload: bytes = b"", code: int = 0, run_id: str = "run-1") -> None:
        self.payload = payload
        self.code = code
        self.run_id = run_id

    def stream(self):
        return iter([self.payload] if self.payload else [])

    def wait(self) -> int:
        return self.code


def _effective_from_env(settings) -> dict[str, object]:
    """模拟扫描器按 `.env` 读到的生效值。"""
    from panel.config_store import read_env
    from scanner.schema import PARAMS, coerce

    document = read_env(settings)
    values: dict[str, object] = {}
    for spec in PARAMS:
        raw = document.values.get(spec.name)
        values[spec.name] = (
            None
            if spec.secret
            else (coerce(spec, raw) if raw and raw.strip() else spec.default)
        )
    return values


class FakeController:
    """内存版 ScannerController：可配置生效值与失败行为。"""

    def __init__(self, settings) -> None:
        self.settings = settings
        self.effective: dict[str, object] = {}
        self.raise_unavailable = False
        self.apply_exit = 0
        self.exec_calls: list[tuple[str, dict[str, str]]] = []
        self.log_chunks: list[bytes] = [b"line-1\nline-2\n"]

    def logs(self, tail=200, follow=True):
        from panel.docker_api import ScannerUnavailable

        if self.raise_unavailable:
            raise ScannerUnavailable("扫描容器不在线")
        return iter(self.log_chunks)

    def exec_script(self, script, env=None):
        from panel.docker_api import ScannerUnavailable

        if self.raise_unavailable:
            raise ScannerUnavailable("扫描容器不在线")
        self.exec_calls.append((script, dict(env or {})))
        if script.endswith("print-config.py"):
            import json

            values = self.effective or _effective_from_env(self.settings)
            payload = {
                name: {"value": value, "source": "dotenv"}
                for name, value in values.items()
            }
            return FakeExecHandle(json.dumps(payload).encode("utf-8"))
        if script.endswith("apply-config.sh"):
            return FakeExecHandle(b"", self.apply_exit)
        if script.endswith("scan-and-publish.sh"):
            return FakeExecHandle(b"run-output\n", 0)
        return FakeExecHandle(b"", 0)


@pytest.fixture
def fake_controller(settings) -> FakeController:
    return FakeController(settings)


@pytest.fixture
def fake_validator(monkeypatch):
    """替换候选配置校验器：只检查 TCP_MIN_SUCCESS 与 TCP_ATTEMPTS 的跨字段关系。"""
    calls: list[dict[str, str]] = []

    def validate(values, env=None):
        calls.append(dict(values))
        attempts = int(values.get("TCP_ATTEMPTS", 3))
        min_success = int(values.get("TCP_MIN_SUCCESS", 2))
        if min_success > attempts:
            raise ValueError([{"name": "TCP_MIN_SUCCESS", "message": "不得大于 TCP_ATTEMPTS"}])

    monkeypatch.setattr("panel.config_store.validate_candidate", validate)
    return calls


@pytest.fixture
def client(anon_client):
    """已登录并默认携带 CSRF 头的 TestClient。"""
    anon_client.post("/api/auth/setup", json={"password": TEST_PASSWORD})
    anon_client.post("/api/auth/login", json={"password": TEST_PASSWORD})
    anon_client.headers["X-CSRF-Token"] = anon_client.cookies["panel_csrf"]
    yield anon_client


@pytest.fixture
def output_dir(settings):
    """产物目录（`Settings.for_tests` 已创建）。"""
    return settings.output_dir


@pytest.fixture
def data_dir(settings):
    """数据目录（地址库与机房映射）。"""
    return settings.data_dir


@pytest.fixture
def runs_tsv(settings):
    """预置一份轮次记录：扫描成功、发布失败。"""
    path = settings.data_dir / "runtime" / "runs.tsv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "START\tr1\tpanel\t2026-11-03T00:00:00Z\t\t\t\t\n"
        "END\tr1\tpanel\t2026-11-03T00:02:00Z\t0\t1\t120\t完成\n",
        encoding="utf-8",
    )
    return path
