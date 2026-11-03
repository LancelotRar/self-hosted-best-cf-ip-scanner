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


@pytest.fixture
def client(anon_client):
    """已登录并默认携带 CSRF 头的 TestClient。"""
    anon_client.post("/api/auth/setup", json={"password": TEST_PASSWORD})
    anon_client.post("/api/auth/login", json={"password": TEST_PASSWORD})
    anon_client.headers["X-CSRF-Token"] = anon_client.cookies["panel_csrf"]
    yield anon_client
