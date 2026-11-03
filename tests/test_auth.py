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
