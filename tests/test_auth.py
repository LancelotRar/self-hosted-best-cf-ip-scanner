from dataclasses import replace

from fastapi.testclient import TestClient

from panel.app import create_app
from panel.settings import Settings

PASSWORD = "correct horse battery"


def test_setup_only_once_and_login_sets_cookies(anon_client):
    assert anon_client.get("/api/auth/status").json()["initialized"] is False
    assert (
        anon_client.post("/api/auth/setup", json={"password": PASSWORD}).status_code == 201
    )
    assert anon_client.post("/api/auth/setup", json={"password": "again"}).status_code == 409
    response = anon_client.post("/api/auth/login", json={"password": PASSWORD})
    assert response.status_code == 200
    assert "panel_session" in response.cookies


def test_write_without_csrf_is_rejected(client):
    del client.headers["X-CSRF-Token"]
    response = client.post("/api/auth/logout")
    assert response.status_code == 403


def test_login_is_rate_limited(anon_client):
    anon_client.post("/api/auth/setup", json={"password": PASSWORD})
    statuses = [
        anon_client.post("/api/auth/login", json={"password": "wrong"}).status_code
        for _ in range(6)
    ]
    assert statuses[:5] == [401] * 5
    assert statuses[5] == 429


def test_password_change_requires_current_password(client):
    response = client.post(
        "/api/auth/password",
        json={"current_password": "wrong", "new_password": "another secret"},
    )
    assert response.status_code == 403
    response = client.post(
        "/api/auth/password",
        json={"current_password": PASSWORD, "new_password": "another secret"},
    )
    assert response.status_code == 200
    assert client.post("/api/auth/login", json={"password": "another secret"}).status_code == 200


def test_login_limiter_window_expires(clock):
    from panel.security import LoginLimiter

    limiter = LoginLimiter(max_failures=2, window_s=60, clock=clock.now)
    limiter.record_failure("k")
    limiter.record_failure("k")
    assert limiter.allow("k") is False
    clock.tick(61)
    assert limiter.allow("k") is True


def test_password_change_invalidates_previous_session(client):
    old_session = client.cookies["panel_session"]
    response = client.post(
        "/api/auth/password",
        json={"current_password": PASSWORD, "new_password": "another secret"},
    )
    assert response.status_code == 200

    client.cookies.set("panel_session", old_session)
    assert client.get("/api/config").status_code == 401


def test_logout_invalidates_previous_session(client):
    old_session = client.cookies["panel_session"]
    assert client.post("/api/auth/logout").status_code == 200

    client.cookies.set("panel_session", old_session)
    assert client.get("/api/config").status_code == 401


def test_setup_token_is_required_when_configured(tmp_path, fake_controller):
    settings = replace(Settings.for_tests(tmp_path), setup_token="setup-secret")
    with TestClient(create_app(settings, controller=fake_controller)) as client:
        assert (
            client.post("/api/auth/setup", json={"password": PASSWORD}).status_code
            == 403
        )
        response = client.post(
            "/api/auth/setup",
            json={"password": PASSWORD},
            headers={"X-Setup-Token": "setup-secret"},
        )
        assert response.status_code == 201


def test_login_lockout_is_scoped_to_source_ip(tmp_path, fake_controller):
    settings = replace(Settings.for_tests(tmp_path), trust_proxy=True)
    with TestClient(create_app(settings, controller=fake_controller)) as client:
        client.post("/api/auth/setup", json={"password": PASSWORD})
        for _ in range(5):
            client.post(
                "/api/auth/login",
                json={"password": "wrong"},
                headers={"X-Forwarded-For": "1.1.1.1"},
            )
        assert (
            client.post(
                "/api/auth/login",
                json={"password": "wrong"},
                headers={"X-Forwarded-For": "1.1.1.1"},
            ).status_code
            == 429
        )
        # 另一个来源 IP 不应被上一个 IP 的失败次数锁死。
        assert (
            client.post(
                "/api/auth/login",
                json={"password": "wrong"},
                headers={"X-Forwarded-For": "2.2.2.2"},
            ).status_code
            == 401
        )


def test_login_limiter_has_bounded_memory(clock):
    from panel.security import LoginLimiter

    limiter = LoginLimiter(
        max_failures=1, window_s=60, clock=clock.now, max_keys=2
    )
    for key in ("a", "b", "c"):
        limiter.record_failure(key)
    assert limiter.allow("c") is False
    assert limiter.allow("a") is True
