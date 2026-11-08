import asyncio
import time

import pytest
from fastapi.testclient import TestClient

from panel.app import create_app
from panel.settings import Settings


def test_healthz(tmp_path, monkeypatch):
    settings = Settings.for_tests(tmp_path)
    client = TestClient(create_app(settings))
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_security_headers_are_present(tmp_path):
    settings = Settings.for_tests(tmp_path)
    with TestClient(create_app(settings)) as client:
        response = client.get("/healthz")
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert "default-src 'self'" in response.headers["content-security-policy"]

        api = client.get("/api/does-not-exist")
        assert api.headers["cache-control"] == "no-store"


def test_spa_deep_link_serves_index(tmp_path):
    settings = Settings.for_tests(tmp_path)
    with TestClient(create_app(settings)) as client:
        response = client.get("/config")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "<html" in response.text.lower()

        api = client.get("/api/does-not-exist")
        assert api.status_code == 404
        assert api.json()["code"] == "error"


@pytest.mark.asyncio
async def test_slow_log_stream_does_not_block_other_requests(settings, fake_controller):
    """SSE 生成器必须在工作线程里跑，不能卡住整个 uvicorn 事件循环。"""
    from httpx import ASGITransport, AsyncClient

    def slow_logs(tail=200, follow=True, timestamps=True):
        def generator():
            for _ in range(5):
                time.sleep(0.1)
                yield b"line\n"

        return generator()

    fake_controller.logs = slow_logs
    app = create_app(settings, controller=fake_controller)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        setup = await client.post(
            "/api/auth/setup", json={"password": "correct horse battery"}
        )
        assert setup.status_code == 201

        async def read_stream() -> bytes:
            async with client.stream("GET", "/api/logs/stream?tail=5") as response:
                chunks = [chunk async for chunk in response.aiter_bytes()]
            return b"".join(chunks)

        stream_task = asyncio.create_task(read_stream())
        await asyncio.sleep(0.15)

        started = time.perf_counter()
        health = await client.get("/healthz")
        elapsed = time.perf_counter() - started
        await stream_task

    assert health.status_code == 200
    assert elapsed < 0.2, f"事件循环被阻塞了 {elapsed:.2f}s"
