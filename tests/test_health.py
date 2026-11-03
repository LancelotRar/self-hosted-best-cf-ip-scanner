from fastapi.testclient import TestClient

from panel.app import create_app
from panel.settings import Settings


def test_healthz(tmp_path, monkeypatch):
    settings = Settings.for_tests(tmp_path)
    client = TestClient(create_app(settings))
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
